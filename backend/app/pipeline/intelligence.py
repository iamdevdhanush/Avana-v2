"""
Intelligence Pipeline — Simplified, no LangGraph.

Flow: Admin triggers → fetch news → parse → Gemini extract → geocode → save → update risk → regenerate heatmap

All async, single process. No Celery, no Redis, no state machines.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, text
from geoalchemy2.elements import WKTElement

from app.database import get_session_factory
from app.models.incident import (
    Incident, IncidentType, IncidentSeverity,
    IncidentSource, IncidentStatus,
)
from app.services.gemini import gemini_service
from app.services.news_scraper import NewsScraper
from app.services.nominatim import NominatimService

logger = logging.getLogger(__name__)

_CITY_SOURCES = [
    {"city": "Bengaluru", "feeds": [
        "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms",
        "https://www.thehindu.com/news/cities/bangalore/feeder/default.rss",
        "https://www.deccanherald.com/rss/karnataka/bengaluru.rss",
    ]},
    {"city": "Mysuru", "feeds": [
        "https://www.thehindu.com/news/national/karnataka/mysore/feeder/default.rss",
        "https://timesofindia.indiatimes.com/rssfeeds/1078976505.cms",
    ]},
    {"city": "Mangaluru", "feeds": [
        "https://www.thehindu.com/news/national/karnataka/mangalore/feeder/default.rss",
        "https://timesofindia.indiatimes.com/rssfeeds/2452244.cms",
    ]},
    {"city": "Hubballi", "feeds": [
        "https://www.thehindu.com/news/national/karnataka/hubli/feeder/default.rss",
    ]},
    {"city": "Belagavi", "feeds": [
        "https://www.thehindu.com/news/national/karnataka/belagavi/feeder/default.rss",
    ]},
    {"city": "Karnataka", "feeds": [
        "https://www.thehindu.com/news/national/karnataka/feeder/default.rss",
        "https://timesofindia.indiatimes.com/rssfeeds/2962392.cms",
        "https://www.deccanherald.com/rss/karnataka.rss",
    ]},
]

_INCIDENT_TYPES = [t.value for t in IncidentType]


async def fetch_all_articles() -> List[dict]:
    articles = []
    scraper = NewsScraper()
    try:
        all_raw = scraper.fetch_all()
        seen_urls = set()
        for a in all_raw:
            url = a.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                full_text = scraper.fetch_article_content(url)
                articles.append({
                    "city": a.get("city", ""),
                    "title": a.get("title", ""),
                    "link": url,
                    "summary": a.get("summary", ""),
                    "full_text": full_text or a.get("summary", ""),
                })
        logger.info(f"Fetched {len(articles)} unique articles")
    finally:
        scraper.close()
    return articles


async def extract_incidents_from_article(article: dict) -> List[dict]:
    text_content = article.get("full_text", "")
    if not text_content or len(text_content) < 50:
        return []
    prompt = (
        "Extract safety incidents from this news article. "
        "Return a JSON array of objects with these fields:\n"
        f"- incident_type: one of [{', '.join(_INCIDENT_TYPES)}]\n"
        "- severity: one of [low, medium, high, critical]\n"
        "- location: the specific location name mentioned\n"
        "- district: the Karnataka district\n"
        "- city: the city name\n"
        "- description: brief description (max 200 chars)\n"
        "- confidence: float 0.0-1.0\n"
        "- incident_date: the date in YYYY-MM-DD format if mentioned, else null\n\n"
        "If no valid incidents are found, return an empty array [].\n\n"
        f"Title: {article.get('title', '')}\n"
        f"Text: {text_content[:6000]}"
    )
    system = (
        "You are a safety incident extraction AI for Karnataka, India. "
        "Extract structured incident data from news articles. "
        "Return ONLY valid JSON. No markdown, no explanations."
    )
    response = gemini_service.generate(prompt, system_instruction=system)
    if not response:
        return []
    cleaned = response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    try:
        incidents = json.loads(cleaned.strip())
        if isinstance(incidents, dict):
            incidents = [incidents]
        for inc in incidents:
            inc["source_url"] = article.get("link", "")
            inc["source_city"] = article.get("city", "")
            inc["article_title"] = article.get("title", "")
        return incidents
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse Gemini output: {e}")
        return []


async def geocode_incidents(incidents: List[dict]) -> List[dict]:
    nominatim = NominatimService()
    try:
        for inc in incidents:
            location_str = inc.get("location", "")
            if not location_str:
                inc["latitude"] = None
                inc["longitude"] = None
                continue
            try:
                query = f"{location_str}, Karnataka, India"
                result = await nominatim.geocode(query)
                if result:
                    inc["latitude"] = float(result["lat"])
                    inc["longitude"] = float(result["lng"])
                    inc["display_name"] = result.get("display_name", "")
                else:
                    inc["latitude"] = None
                    inc["longitude"] = None
            except Exception as e:
                logger.warning(f"Geocode failed for '{location_str}': {e}")
                inc["latitude"] = None
                inc["longitude"] = None
        return incidents
    finally:
        await nominatim.aclose()


async def save_incidents(incidents: List[dict]) -> dict:
    saved = 0
    skipped = 0
    errors = []
    factory = get_session_factory()
    async with factory() as session:
        for inc in incidents:
            lat = inc.get("latitude")
            lng = inc.get("longitude")
            if lat is None or lng is None:
                skipped += 1
                continue
            source_url = inc.get("source_url", "")
            if source_url:
                result = await session.execute(
                    select(Incident).where(Incident.source_url == source_url).limit(1)
                )
                if result.scalar_one_or_none():
                    skipped += 1
                    continue
            try:
                itype_str = inc.get("incident_type", "other")
                try:
                    itype = IncidentType(itype_str)
                except ValueError:
                    itype = IncidentType.OTHER
                sev_str = inc.get("severity", "medium")
                try:
                    severity = IncidentSeverity(sev_str)
                except ValueError:
                    severity = IncidentSeverity.MEDIUM
                confidence = max(0.0, min(1.0, float(inc.get("confidence", 0.7))))
                incident = Incident(
                    incident_type=itype,
                    severity=severity,
                    source=IncidentSource.NEWS,
                    status=IncidentStatus.PENDING,
                    confidence_score=confidence,
                    latitude=lat,
                    longitude=lng,
                    geom=WKTElement(f"POINT({lng} {lat})", srid=4326),
                    description=(inc.get("description") or inc.get("article_title", ""))[:500],
                    title=(inc.get("article_title", ""))[:500],
                    address=inc.get("display_name", ""),
                    district=inc.get("district", inc.get("source_city", "")),
                    city=inc.get("city", inc.get("source_city", "")),
                    incident_date=datetime.now(timezone.utc),
                    source_url=source_url,
                    ai_classified=True,
                )
                session.add(incident)
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save incident: {e}")
                errors.append(str(e))
        await session.commit()
    return {"saved": saved, "skipped": skipped, "errors": errors, "total": len(incidents)}


async def run_intelligence_pipeline() -> dict:
    start = time.time()
    logger.info("=" * 60)
    logger.info("INTELLIGENCE PIPELINE STARTED")
    logger.info("=" * 60)
    results = {"steps": {}}
    try:
        articles = await fetch_all_articles()
        results["steps"]["fetch"] = {"status": "ok", "count": len(articles)}
        logger.info(f"Step 1 complete: {len(articles)} articles fetched")
    except Exception as e:
        results["steps"]["fetch"] = {"status": "failed", "error": str(e)}
        logger.error(f"Step 1 failed: {e}")
        return results
    all_incidents = []
    for article in articles:
        try:
            extracted = await extract_incidents_from_article(article)
            all_incidents.extend(extracted)
        except Exception as e:
            logger.warning(f"Extraction failed for '{article.get('title', '')}': {e}")
    results["steps"]["extract"] = {"status": "ok", "count": len(all_incidents)}
    logger.info(f"Step 2 complete: {len(all_incidents)} incidents extracted")
    try:
        all_incidents = await geocode_incidents(all_incidents)
        geocoded = sum(1 for i in all_incidents if i.get("latitude") is not None)
        results["steps"]["geocode"] = {"status": "ok", "geocoded": geocoded, "total": len(all_incidents)}
        logger.info(f"Step 3 complete: {geocoded}/{len(all_incidents)} geocoded")
    except Exception as e:
        results["steps"]["geocode"] = {"status": "failed", "error": str(e)}
        logger.error(f"Step 3 failed: {e}")
    try:
        save_result = await save_incidents(all_incidents)
        results["steps"]["save"] = {"status": "ok", **save_result}
        logger.info(f"Step 4 complete: saved {save_result['saved']}")
    except Exception as e:
        results["steps"]["save"] = {"status": "failed", "error": str(e)}
        logger.error(f"Step 4 failed: {e}")
    results["duration_seconds"] = round(time.time() - start, 2)
    logger.info(f"Pipeline complete in {results['duration_seconds']}s")
    logger.info("=" * 60)
    return results


async def run_community_pipeline() -> dict:
    from app.pipeline.community import process_pending_reports
    return await process_pending_reports()


async def update_heatmap_for_bounds(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float, zoom: str = "city") -> dict:
    from app.pipeline.heatmap import generate_heatmap_for_bounds
    return await generate_heatmap_for_bounds(sw_lat, sw_lng, ne_lat, ne_lng, zoom)


async def recalculate_risk_scores() -> dict:
    from app.pipeline.risk import recalculate_all_risk_scores
    return await recalculate_all_risk_scores()
