from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
import logging
from datetime import datetime
import feedparser
import httpx
from bs4 import BeautifulSoup
import json
import asyncio
from sqlalchemy import select
from geoalchemy2.elements import WKTElement

from app.services.gemini import GeminiService
from app.database import async_session_factory
from app.models.incident import Incident, IncidentType, IncidentSeverity, IncidentSource, IncidentStatus

logger = logging.getLogger(__name__)

gemini_service = GeminiService()

CITY_SOURCES = [
    {
        "city": "Bengaluru",
        "state": "Karnataka",
        "feeds": [
            "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms",
            "https://www.thehindu.com/news/cities/bangalore/feeder/default.rss",
            "https://www.deccanherald.com/rss/karnataka/bengaluru.rss",
        ],
    },
    {
        "city": "Mysuru",
        "state": "Karnataka",
        "feeds": [
            "https://www.thehindu.com/news/national/karnataka/mysore/feeder/default.rss",
            "https://timesofindia.indiatimes.com/rssfeeds/1078976505.cms",
        ],
    },
    {
        "city": "Mangaluru",
        "state": "Karnataka",
        "feeds": [
            "https://www.thehindu.com/news/national/karnataka/mangalore/feeder/default.rss",
            "https://timesofindia.indiatimes.com/rssfeeds/2452244.cms",
        ],
    },
    {
        "city": "Hubballi",
        "state": "Karnataka",
        "feeds": [
            "https://www.thehindu.com/news/national/karnataka/hubli/feeder/default.rss",
        ],
    },
    {
        "city": "Belagavi",
        "state": "Karnataka",
        "feeds": [
            "https://www.thehindu.com/news/national/karnataka/belagavi/feeder/default.rss",
        ],
    },
    {
        "city": "Karnataka",
        "state": "Karnataka",
        "feeds": [
            "https://www.thehindu.com/news/national/karnataka/feeder/default.rss",
            "https://timesofindia.indiatimes.com/rssfeeds/2962392.cms",
            "https://www.deccanherald.com/rss/karnataka.rss",
        ],
    },
]


class NewsState(TypedDict):
    sources: List[dict]
    articles: List[dict]
    extracted_incidents: List[dict]
    geocoded_incidents: List[dict]
    saved_count: int
    errors: List[str]


def _clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


async def fetch_news_sources(state: NewsState) -> dict:
    articles = []
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for source in CITY_SOURCES:
            for feed_url in source["feeds"]:
                try:
                    response = await client.get(feed_url)
                    if response.status_code != 200:
                        logger.warning(f"RSS feed returned {response.status_code}: {feed_url}")
                        continue
                    parsed = feedparser.parse(response.text)
                    for entry in parsed.entries[:10]:
                        articles.append({
                            "city": source["city"],
                            "state": source["state"],
                            "title": entry.get("title", ""),
                            "link": entry.get("link", ""),
                            "summary": entry.get("summary", entry.get("description", "")),
                            "published": entry.get("published", ""),
                            "feed_url": feed_url,
                        })
                except Exception as e:
                    logger.error(f"Failed to fetch RSS feed {feed_url}: {e}")
    logger.info(f"Fetched {len(articles)} articles from {sum(len(s['feeds']) for s in CITY_SOURCES)} feeds")
    return {"articles": articles, "sources": CITY_SOURCES}


async def fetch_article_content(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Avana-SafetyBot/2.0"})
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                    tag.decompose()
                paragraphs = soup.find_all("p")
                text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
                return text[:8000]
    except Exception as e:
        logger.warning(f"Failed to fetch article content from {url}: {e}")
    return ""


async def parse_articles(state: NewsState) -> dict:
    articles = state.get("articles", [])
    logger.info(f"Parsing {len(articles)} articles for full text")
    for article in articles:
        if article.get("link"):
            full_text = await fetch_article_content(article["link"])
            article["full_text"] = full_text or article.get("summary", "")
        else:
            article["full_text"] = article.get("summary", "")
    return {"articles": articles}


INCIDENT_TYPES_LIST = [t.value for t in IncidentType]


async def extract_incidents(state: NewsState) -> dict:
    articles = state.get("articles", [])
    extracted = []
    for article in articles:
        text_content = article.get("full_text", "")
        if not text_content or len(text_content) < 50:
            continue
        prompt = (
            "Extract safety incidents from this news article. "
            "Return a JSON array of objects with these fields:\n"
            f"- incident_type: one of [{', '.join(INCIDENT_TYPES_LIST)}]\n"
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
        try:
            response = gemini_service.generate(
                prompt,
                system_instruction=(
                    "You are a safety incident extraction AI for Karnataka, India. "
                    "Extract structured incident data from news articles. "
                    "Return ONLY valid JSON. No markdown, no explanations."
                ),
            )
            cleaned = _clean_json_response(response)
            incidents = json.loads(cleaned)
            if isinstance(incidents, dict):
                incidents = [incidents]
            for inc in incidents:
                inc["source_url"] = article.get("link", "")
                inc["source_city"] = article.get("city", "")
                inc["article_title"] = article.get("title", "")
            extracted.extend(incidents)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error(f"Failed to parse Gemini output for article '{article.get('title', '')}': {e}")
    logger.info(f"Extracted {len(extracted)} incidents from {len(articles)} articles")
    return {"extracted_incidents": extracted}


async def geocode_incidents(state: NewsState) -> dict:
    from app.services.nominatim import NominatimService
    nominatim = NominatimService()
    geocoded = []
    for inc in state.get("extracted_incidents", []):
        location_str = inc.get("location", "")
        if not location_str:
            inc["latitude"] = None
            inc["longitude"] = None
            geocoded.append(inc)
            continue
        try:
            query = f"{location_str}, Karnataka, India"
            result = nominatim.geocode(query)
            if result:
                inc["latitude"] = float(result["lat"])
                inc["longitude"] = float(result["lng"])
                inc["display_name"] = result.get("display_name", "")
                inc["place_id"] = result.get("place_id", "")
            else:
                inc["latitude"] = None
                inc["longitude"] = None
                inc["display_name"] = ""
            geocoded.append(inc)
        except Exception as e:
            logger.error(f"Geocoding failed for '{location_str}': {e}")
            inc["latitude"] = None
            inc["longitude"] = None
            geocoded.append(inc)
    return {"geocoded_incidents": geocoded}


async def save_incidents(state: NewsState) -> dict:
    saved = 0
    errors = list(state.get("errors", []))
    async with async_session_factory() as session:
        for inc in state.get("geocoded_incidents", []):
            lat = inc.get("latitude")
            lng = inc.get("longitude")
            if lat is None or lng is None:
                continue
            try:
                source_url = inc.get("source_url", "")
                if source_url:
                    result = await session.execute(
                        select(Incident).where(Incident.source_url == source_url).limit(1)
                    )
                    if result.scalar_one_or_none():
                        continue
                incident_type_str = inc.get("incident_type", "other")
                try:
                    incident_type = IncidentType(incident_type_str)
                except ValueError:
                    incident_type = IncidentType.OTHER
                severity_str = inc.get("severity", "medium")
                try:
                    severity = IncidentSeverity(severity_str)
                except ValueError:
                    severity = IncidentSeverity.MEDIUM
                confidence = float(inc.get("confidence", 0.7))
                confidence = max(0.0, min(1.0, confidence))
                incident = Incident(
                    incident_type=incident_type,
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
                    incident_date=datetime.utcnow(),
                    source_url=source_url,
                    ai_classified=True,
                )
                session.add(incident)
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save incident: {e}")
                errors.append(str(e))
        await session.commit()
    logger.info(f"Saved {saved} new incidents")
    return {"saved_count": saved, "errors": errors}


def build_news_graph() -> StateGraph:
    workflow = StateGraph(NewsState)
    workflow.add_node("fetch_news_sources", fetch_news_sources)
    workflow.add_node("parse_articles", parse_articles)
    workflow.add_node("extract_incidents", extract_incidents)
    workflow.add_node("geocode_incidents", geocode_incidents)
    workflow.add_node("save_incidents", save_incidents)
    workflow.set_entry_point("fetch_news_sources")
    workflow.add_edge("fetch_news_sources", "parse_articles")
    workflow.add_edge("parse_articles", "extract_incidents")
    workflow.add_edge("extract_incidents", "geocode_incidents")
    workflow.add_edge("geocode_incidents", "save_incidents")
    workflow.add_edge("save_incidents", END)
    return workflow.compile()


async def run() -> dict:
    initial_state: NewsState = {
        "sources": [],
        "articles": [],
        "extracted_incidents": [],
        "geocoded_incidents": [],
        "saved_count": 0,
        "errors": [],
    }
    graph = build_news_graph()
    result = await graph.ainvoke(initial_state)
    logger.info(
        f"News intelligence pipeline completed: "
        f"{result['saved_count']} incidents saved, "
        f"{len(result['errors'])} errors"
    )
    return result


def run_scheduled() -> dict:
    return asyncio.run(run())
