"""
Intelligence Pipeline — Simplified, no LangGraph.

Flow: Admin triggers → fetch news → parse → AI extract → geocode → save → update risk → regenerate heatmap

All async, single process. No Celery, no Redis, no state machines.
"""

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List
from sqlalchemy import select, text
from geoalchemy2.elements import WKTElement

from app.database import get_session_factory
from app.models.incident import (
    Incident, IncidentType, IncidentSeverity,
    IncidentSource, IncidentStatus,
)
from app.pipeline.women_safety import (
    WOMEN_SAFETY_CATEGORIES, WOMEN_SAFETY_TO_INCIDENT_TYPE,
    get_women_safety_details, is_women_safety_category,
)
from app.services.news_scraper import NewsScraper
from app.services.ai.factory import get_ai_provider

_ai_provider = None

def _get_provider():
    global _ai_provider
    if _ai_provider is None:
        _ai_provider = get_ai_provider()
    return _ai_provider

class GeminiQuotaExceeded(Exception):
    pass
from app.services.nominatim import NominatimService
from app.utils.dedup import is_duplicate_by_title_and_proximity

_MOCK_CACHE = None


def _get_mock_incidents():
    global _MOCK_CACHE
    if _MOCK_CACHE is None:
        from app.pipeline.intelligence_mock import get_mock_incidents
        _MOCK_CACHE = get_mock_incidents()
    return _MOCK_CACHE

logger = logging.getLogger(__name__)

_CITY_SOURCES = [
    {"city": "Bengaluru", "feeds": [
        "https://www.thehindu.com/news/cities/bangalore/feeder/default.rss",
        "https://www.deccanherald.com/feed",
    ]},
    {"city": "Karnataka", "feeds": [
        "https://www.thehindu.com/news/national/karnataka/feeder/default.rss",
        "https://www.deccanherald.com/feed",
    ]},
]

_INCIDENT_TYPES = [t.value for t in IncidentType]


_MAX_ARTICLES = 100


def _fetch_article_content_for_url(scraper: NewsScraper, article: dict) -> dict:
    url = article.get("link", "")
    full_text = scraper.fetch_article_content(url)
    return {
        "city": article.get("city", ""),
        "title": article.get("title", ""),
        "link": url,
        "summary": article.get("summary", ""),
        "full_text": full_text or article.get("summary", ""),
    }


async def fetch_all_articles() -> List[dict]:
    articles = []
    scraper = NewsScraper()
    try:
        from app.agents.news_intelligence import _KANNADA_SOURCES
        kn_articles = []
        for entry in _KANNADA_SOURCES:
            for feed_url in entry["feeds"]:
                try:
                    kannada_articles = scraper.fetch_rss(feed_url)
                    for ka in kannada_articles:
                        ka["city"] = entry["city"]
                        ka["language"] = entry.get("language", "kn")
                    kn_articles.extend(kannada_articles)
                except Exception as exc:
                    logger.warning(f"[PIPELINE] Kannada feed fetch failed: {exc}")

        en_raw = scraper.fetch_all()
        all_raw = kn_articles + en_raw
        seen_urls = set()
        unique = []
        for a in all_raw:
            url = a.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(a)
        logger.info(f"Unique articles: {len(unique)} (Kannada first)")
        if len(unique) > _MAX_ARTICLES:
            unique = unique[:_MAX_ARTICLES]
            logger.info(f"Limited to {_MAX_ARTICLES} articles for this run")
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_fetch_article_content_for_url, scraper, a) for a in unique]
            for future in as_completed(futures):
                try:
                    articles.append(future.result())
                except Exception as e:
                    logger.warning(f"Article fetch failed: {e}")
        logger.info(f"Fetched content for {len(articles)} articles")
    finally:
        scraper.close()
    return articles


async def extract_incidents_from_article(article: dict) -> List[dict]:
    text_content = article.get("full_text", "")
    if not text_content or len(text_content) < 50:
        return []
    categories_list = sorted(WOMEN_SAFETY_CATEGORIES.keys())
    prompt = (
        "Extract WOMEN'S SAFETY incidents from this news article. "
        "ONLY extract incidents relevant to women's safety (crimes against women/girls). "
        "Skip generic crimes like theft, fraud, accidents, riots, vandalism.\n\n"
        "Return a JSON array of objects with these fields:\n"
        f"- incident_type: one of [{', '.join(_INCIDENT_TYPES)}]\n"
        "- severity: one of [low, medium, high, critical]\n"
        "- women_safety_category: one of [" + ", ".join(categories_list) + "]\n"
        "- location: the specific location name mentioned\n"
        "- district: the Karnataka district\n"
        "- city: the city name\n"
        "- description: brief description (max 200 chars)\n"
        "- confidence: float 0.0-1.0\n"
        "- incident_date: the date in YYYY-MM-DD format if mentioned, else null\n\n"
        "IMPORTANT: women_safety_category is REQUIRED. Pick the most specific match.\n"
        "If an incident is NOT a women's safety crime, EXCLUDE it entirely.\n\n"
        "If no valid incidents are found, return an empty array [].\n\n"
        f"Title: {article.get('title', '')}\n"
        f"Text: {text_content[:6000]}"
    )
    system = (
        "You are a women's safety incident extraction AI for Karnataka, India. "
        "ONLY extract crimes against women and girls. Exclude all other crime types. "
        "Return ONLY valid JSON. No markdown, no explanations."
    )
    response = await _get_provider().generate(prompt, system_instruction=system)
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
        logger.warning(f"Failed to parse AI output: {e}")
        return []


async def geocode_incidents(incidents: List[dict]) -> List[dict]:
    nominatim = NominatimService()
    cache_hits = 0
    cache_misses = 0
    existing_coords_kept = 0
    factory = get_session_factory()
    async with factory() as session:
        try:
            for inc in incidents:
                had_coords = inc.get("latitude") is not None and inc.get("longitude") is not None
                location_str = inc.get("location", "")
                if not location_str and not had_coords:
                    inc["latitude"] = None
                    inc["longitude"] = None
                    continue
                query = f"{location_str}, Karnataka, India"
                try:
                    result = await session.execute(
                        text("SELECT latitude, longitude, display_name FROM geocoding_cache WHERE location_text = :q"),
                        {"q": query},
                    )
                    cached = result.fetchone()
                    if cached:
                        inc["latitude"] = float(cached[0])
                        inc["longitude"] = float(cached[1])
                        inc["display_name"] = cached[2] or ""
                        await session.execute(
                            text("UPDATE geocoding_cache SET last_verified = NOW() WHERE location_text = :q"),
                            {"q": query},
                        )
                        cache_hits += 1
                        continue
                    cache_misses += 1
                    named_result = await nominatim.geocode(query)
                    if named_result:
                        inc["latitude"] = float(named_result["lat"])
                        inc["longitude"] = float(named_result["lng"])
                        inc["display_name"] = named_result.get("display_name", "")
                        await session.execute(
                            text("""
                                INSERT INTO geocoding_cache
                                    (id, location_text, latitude, longitude, display_name, last_verified, created_at)
                                VALUES (gen_random_uuid(), :q, :lat, :lng, :dn, NOW(), NOW())
                                ON CONFLICT (location_text) DO NOTHING
                            """),
                            {"q": query, "lat": inc["latitude"], "lng": inc["longitude"], "dn": inc.get("display_name", "")},
                        )
                    else:
                        if had_coords:
                            existing_coords_kept += 1
                            logger.info(f"[GEOCODE] Nominatim failed for '{location_str}' — preserving existing coords ({inc['latitude']}, {inc['longitude']})")
                        else:
                            inc["latitude"] = None
                            inc["longitude"] = None
                except Exception as e:
                    logger.warning(f"Geocode failed for '{location_str}': {e}")
                    if not had_coords:
                        inc["latitude"] = None
                        inc["longitude"] = None
                    else:
                        existing_coords_kept += 1
                        logger.info(f"[GEOCODE] Exception for '{location_str}' — preserving existing coords ({inc['latitude']}, {inc['longitude']})")
            await session.commit()
        finally:
            await nominatim.aclose()
    total = cache_hits + cache_misses
    if total > 0:
        logger.info(f"Geocoding cache: {cache_hits}/{total} hits ({cache_hits/total*100:.1f}%)")
    if existing_coords_kept > 0:
        logger.info(f"[GEOCODE] Preserved existing coordinates for {existing_coords_kept} incidents (Nominatim unavailable)")
    return incidents


def _is_duplicate(candidate: dict, existing_title: str, existing_lat: float, existing_lng: float) -> bool:
    title = (candidate.get("article_title") or candidate.get("title") or "").lower()
    lat = candidate.get("latitude")
    lng = candidate.get("longitude")
    return is_duplicate_by_title_and_proximity(
        title, existing_title.lower(),
        lat, lng,
        existing_lat, existing_lng,
    )


async def save_incidents(incidents: List[dict]) -> dict:
    saved = 0
    skipped = 0
    errors = []
    has_coords = sum(1 for i in incidents if i.get("latitude") is not None and i.get("longitude") is not None)
    has_ws = sum(1 for i in incidents if i.get("women_safety_category"))
    logger.info(f"[SAVE_DEBUG] Received {len(incidents)} incidents: {has_coords} with coords, {has_ws} with women_safety_category")
    factory = get_session_factory()
    async with factory() as session:
        existing = await session.execute(
            select(Incident).where(Incident.source == IncidentSource.NEWS).limit(500)
        )
        existing_incidents = existing.scalars().all()
        logger.info(f"[SAVE_DEBUG] {len(existing_incidents)} existing incidents in DB")
        for inc in incidents:
            lat = inc.get("latitude")
            lng = inc.get("longitude")
            if lat is None or lng is None:
                if skipped < 5:
                    logger.info(f"[SAVE_DEBUG] Skipping incident (no coords): {inc.get('location', 'unknown')} lat={lat} lng={lng}")
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
            is_dup = False
            for existing_inc in existing_incidents:
                if _is_duplicate(
                    inc,
                    existing_inc.title or "",
                    existing_inc.latitude or 0,
                    existing_inc.longitude or 0,
                ):
                    is_dup = True
                    break
            if is_dup:
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

                # Women-safety category handling
                ws_cat = inc.get("women_safety_category", "")
                ws_details = None
                meta = {}
                if ws_cat and is_women_safety_category(ws_cat):
                    tier, risk_weight, sev_weight, base_sev = get_women_safety_details(ws_cat)
                    ws_details = {"women_safety_category": ws_cat, "women_safety_weight": sev_weight}
                    meta["women_safety_category"] = ws_cat
                    meta["women_safety_weight"] = sev_weight
                    meta["women_safety_tier"] = tier
                    # Override incident_type from the women_safety mapping for consistency
                    mapped_type = WOMEN_SAFETY_TO_INCIDENT_TYPE.get(ws_cat)
                    if mapped_type:
                        try:
                            itype = IncidentType(mapped_type)
                        except ValueError:
                            pass
                    # Override severity based on tier
                    if tier == 1:
                        severity = IncidentSeverity.CRITICAL
                    elif tier == 2:
                        severity = IncidentSeverity.HIGH
                else:
                    meta["women_safety_category"] = None
                    meta["women_safety_weight"] = None

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
                    meta_data=meta,
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
    logger.info("[PIPELINE_START] run_intelligence_pipeline entered")
    logger.info("=" * 60)
    logger.info("INTELLIGENCE PIPELINE STARTED")
    logger.info("=" * 60)
    results = {"steps": {}}

    from app.config import settings

    mock_mode = settings.MOCK_INTELLIGENCE_MODE

    if mock_mode:
        logger.info("MOCK_INTELLIGENCE_MODE enabled — using mock data")
    else:
        if not _get_provider().is_available():
            logger.info("[PIPELINE] AI provider unavailable — falling back to mock data automatically")
            mock_mode = True

    if mock_mode:
        all_incidents = _get_mock_incidents()
        results["steps"]["fetch"] = {"status": "ok", "count": 5, "source": "mock"}
        logger.info(f"Step 1 complete: 5 mock articles generated")
    else:
        try:
            articles = await fetch_all_articles()
            results["steps"]["fetch"] = {"status": "ok", "count": len(articles)}
            logger.info(f"Step 1 complete: {len(articles)} articles fetched")
        except Exception as e:
            results["steps"]["fetch"] = {"status": "failed", "error": str(e)}
            logger.error(f"Step 1 failed: {e}")
            results["duration_seconds"] = round(time.time() - start, 2)
            logger.info("[PIPELINE_END] Fetch failed — pipeline aborted")
            return results

    if mock_mode:
        results["steps"]["extract"] = {"status": "ok", "count": len(all_incidents), "source": "mock"}
        logger.info(f"Step 2 complete: {len(all_incidents)} mock incidents extracted")
    else:
        all_incidents = []
        for article in articles:
            try:
                extracted = await extract_incidents_from_article(article)
                all_incidents.extend(extracted)
            except GeminiQuotaExceeded:
                logger.error("Gemini quota exhausted — failing pipeline immediately")
                raise
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
        logger.info(f"Step 4 complete: saved {save_result['saved']} of {save_result['total']} (skipped {save_result['skipped']})")
        if save_result["saved"] == 0 and save_result["total"] > 0:
            logger.error("[PIPELINE] 0 incidents saved — likely geocoding failed for all. Aborting.")
            results["steps"]["save"]["status"] = "failed"
            results["steps"]["save"]["error"] = "All incidents lacked coordinates — geocoding failure"
            results["duration_seconds"] = round(time.time() - start, 2)
            logger.info("[PIPELINE_END] 0 saved — pipeline aborted")
            return results
    except Exception as e:
        results["steps"]["save"] = {"status": "failed", "error": str(e)}
        logger.error(f"Step 4 failed: {e}")
        results["duration_seconds"] = round(time.time() - start, 2)
        logger.info("[PIPELINE_END] Save failed — pipeline aborted")
        return results

    try:
        risk_result = await recalculate_risk_scores()
        results["steps"]["risk_recalc"] = {"status": "ok", **risk_result}
        logger.info(f"Step 5 complete: {risk_result.get('updated', 0)} risk scores updated")
    except Exception as e:
        results["steps"]["risk_recalc"] = {"status": "failed", "error": str(e)}
        logger.error(f"Step 5 failed: {e}")

    try:
        from app.pipeline.heatmap import compute_localized_bounds
        bounds_list = await compute_localized_bounds(buffer_degrees=0.05, max_cells_per=1000)
        if bounds_list:
            total_points = 0
            zone_errors = []
            for i, (sw_lat, sw_lng, ne_lat, ne_lng) in enumerate(bounds_list):
                logger.info(f"[PIPELINE] Heatmap zone {i+1}/{len(bounds_list)}: ({sw_lat:.4f},{sw_lng:.4f}) to ({ne_lat:.4f},{ne_lng:.4f})")
                heat_result = await update_heatmap_for_bounds(sw_lat, sw_lng, ne_lat, ne_lng)
                if "error" in heat_result:
                    logger.warning(f"[PIPELINE] Heatmap zone {i+1} returned error: {heat_result['error']}")
                    zone_errors.append(heat_result["error"])
                total_points += heat_result.get("points_generated", 0)
            heatmap_status = "failed" if (total_points == 0 and zone_errors) else "ok"
            heat_result = {"points_generated": total_points}
            if zone_errors:
                heat_result["zone_errors"] = zone_errors
            results["steps"]["heatmap"] = {"status": heatmap_status, **heat_result}
            logger.info(f"Step 6 complete: {total_points} heatmap points across {len(bounds_list)} zone(s)")
        else:
            from app.config import settings
            bounds = [float(x) for x in settings.KARNATAKA_BOUNDS.split(",")]
            sw_lat, sw_lng, ne_lat, ne_lng = bounds[0], bounds[2], bounds[1], bounds[3]
            logger.info(f"[PIPELINE] No recent incident clusters — fallback to state bounds")
            heat_result = await update_heatmap_for_bounds(sw_lat, sw_lng, ne_lat, ne_lng)
            heatmap_status = "failed" if ("error" in heat_result and heat_result.get("points_generated", 0) == 0) else "ok"
            results["steps"]["heatmap"] = {"status": heatmap_status, **heat_result}
    except Exception as e:
        results["steps"]["heatmap"] = {"status": "failed", "error": str(e)}
        logger.error(f"Step 6 failed: {e}")

    saved_count = save_result.get("saved", 0)
    risk_count = results.get("steps", {}).get("risk_recalc", {}).get("updated", 0)
    heat_count = results.get("steps", {}).get("heatmap", {}).get("points_generated", 0)
    results["summary"] = {
        "articles_fetched": results.get("steps", {}).get("fetch", {}).get("count", 0),
        "incidents_extracted": results.get("steps", {}).get("extract", {}).get("count", 0),
        "incidents_saved": saved_count,
        "risk_scores_updated": risk_count,
        "heatmap_points_generated": heat_count,
        "duration_seconds": round(time.time() - start, 2),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    results["duration_seconds"] = round(time.time() - start, 2)
    logger.info(f"[PIPELINE_END] Pipeline complete in {results['duration_seconds']}s")
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
