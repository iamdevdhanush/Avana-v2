"""
Shivamogga News Collector — Scrapes local news sources for incident data.
No Gemini dependency — uses regex/heuristics for extraction.

Usage (from backend/):
    python -m app.pipeline.shivamogga_collector

Flow:
    1. Fetch articles from Google News RSS + Karnataka news feeds
    2. Filter for Shivamogga-related content
    3. Extract incident data via regex/heuristics
    4. Geocode locations (known map → Nominatim → fallback)
    5. Deduplicate against existing incidents
    6. Insert into database
    7. Recalculate risk scores
    8. Regenerate heatmap
"""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
from sqlalchemy import select, text, or_, func
from geoalchemy2.elements import WKTElement

from app.database import get_session_factory
from app.models.incident import (
    Incident, IncidentType, IncidentSeverity,
    IncidentSource, IncidentStatus,
)
from app.pipeline.women_safety import (
    WOMEN_SAFETY_CATEGORIES, INCIDENT_TYPE_TO_WOMEN_SAFETY,
    WOMEN_SAFETY_TO_INCIDENT_TYPE, get_women_safety_details,
    is_women_safety_category,
)
from app.services.news_scraper import NewsScraper
from app.services.nominatim import NominatimService

logger = logging.getLogger(__name__)

# ─── Known Shivamogga localities & coordinates ─────────────────────────────
# Shivamogga city ~13.9299, 75.5681
SHIVAMOGGA_CENTER = (13.9299, 75.5681)

SHIVAMOGGA_LOCALITIES: Dict[str, Tuple[float, float]] = {
    "shivamogga": (13.9299, 75.5681),
    "shimoga": (13.9299, 75.5681),
    "vidyanagar": (13.9200, 75.5700),
    "gandhi nagar": (13.9250, 75.5750),
    "gandhinagar": (13.9250, 75.5750),
    "ashok nagar": (13.9300, 75.5600),
    "ashoknagar": (13.9300, 75.5600),
    "doddapete": (13.9280, 75.5620),
    "doddapet": (13.9280, 75.5620),
    "sulebailu": (13.9350, 75.5800),
    "neetinagara": (13.9220, 75.5780),
    "neetinagar": (13.9220, 75.5780),
    "jayanagar": (13.9170, 75.5730),
    "k r extension": (13.9250, 75.5650),
    "k.r. extension": (13.9250, 75.5650),
    "kumara parvathi": (13.9210, 75.5750),
    "gopal nagar": (13.9320, 75.5580),
    "gopalnagar": (13.9320, 75.5580),
    "navile": (13.9120, 75.5800),
    "harakere": (13.9180, 75.5900),
    "mantagudi": (13.9100, 75.5950),
    "anandapura": (13.9350, 75.5550),
    "gurukula colony": (13.9360, 75.5620),
    "shivamogga fort": (13.9275, 75.5650),
    "b h road": (13.9260, 75.5640),
    "sagara": (14.1650, 75.0350),
    "sagar": (14.1650, 75.0350),
    "bhadravathi": (13.8480, 75.7050),
    "bhadravati": (13.8480, 75.7050),
    "bhadravati town": (13.8480, 75.7050),
    "shikaripura": (14.2700, 75.3500),
    "shikaripur": (14.2700, 75.3500),
    "sorab": (14.3800, 75.1100),
    "hosanagara": (13.9200, 75.0700),
    "hosa nagar": (13.9200, 75.0700),
    "tirthahalli": (13.6900, 75.2400),
    "thirthahalli": (13.6900, 75.2400),
    "thirthahally": (13.6900, 75.2400),
    "agumbe": (13.5050, 75.0900),
    "jog falls": (14.2269, 74.8069),
    "jog": (14.2269, 74.8069),
    "kavaledurga": (13.7900, 75.2300),
    "kuppalli": (13.9400, 75.6000),
    "kuppally": (13.9400, 75.6000),
    "holehonnur": (13.7800, 75.7400),
    "hammigi": (14.1200, 75.4100),
    "kumsi": (13.8150, 75.3850),
    "mandagadde": (14.0170, 75.5900),
    "anegundi": (13.8400, 75.7100),
    "beguvalli": (14.1000, 75.2000),
    "mayakonda": (14.2200, 75.6200),
    "harige": (13.9800, 75.2000),
    "kargal": (13.8770, 75.5890),
}

# ─── News Sources ──────────────────────────────────────────────────────────

GOOGLE_NEWS_QUERIES = [
    "https://news.google.com/rss/search?q=Shivamogga+crime+incident+Karnataka&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Shimoga+crime+attack+Karnataka&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Shivamogga+murder+robbery+assault&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=Shivamogga+theft+accident+violence&hl=en-IN&gl=IN&ceid=IN:en",
    "https://news.google.com/rss/search?q=%E0%B2%B6%E0%B2%BF%E0%B2%B5%E0%B2%AE%E0%B3%8A%E0%B2%97%E0%B3%8D%E0%B2%97+%E0%B2%85%E0%B2%AA%E0%B2%B0%E0%B2%BE%E0%B2%A7&hl=kn-IN&gl=IN&ceid=IN:kn",
]

KARNATAKA_RSS_FEEDS = [
    ("Deccan Herald", "https://www.deccanherald.com/feed"),
    ("The Hindu Karnataka", "https://www.thehindu.com/news/national/karnataka/feeder/default.rss"),
    ("Times of India Karnataka", "https://timesofindia.indiatimes.com/rssfeeds/2962392.cms"),
    ("Times of India Bengaluru", "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms"),
]

# ─── Keyword -> IncidentType mapping ──────────────────────────────────────

INCIDENT_KEYWORDS: List[Tuple[str, IncidentType, IncidentSeverity]] = [
    # Murder (must appear before generic patterns)
    (r"\bmurder", IncidentType.MURDER, IncidentSeverity.CRITICAL),
    (r"\bkilled", IncidentType.MURDER, IncidentSeverity.CRITICAL),
    (r"\bhomicide\b", IncidentType.MURDER, IncidentSeverity.CRITICAL),
    (r"\bdeath\b", IncidentType.MURDER, IncidentSeverity.CRITICAL),
    (r"\bdied\b", IncidentType.MURDER, IncidentSeverity.CRITICAL),
    (r"\bkill(?:ed|ing|er)?\b", IncidentType.MURDER, IncidentSeverity.CRITICAL),
    (r"\bdead body\b", IncidentType.MURDER, IncidentSeverity.CRITICAL),
    (r"stab(?:bed|bing)?\b", IncidentType.ASSAULT, IncidentSeverity.HIGH),
    (r"\battack(?:ed|ing)?\b", IncidentType.ASSAULT, IncidentSeverity.HIGH),
    (r"\bassault(?:ed)?\b", IncidentType.ASSAULT, IncidentSeverity.HIGH),
    (r"\bbeat(?:en|ing)?\b", IncidentType.ASSAULT, IncidentSeverity.HIGH),
    (r"\bthrash(?:ed|ing)?\b", IncidentType.ASSAULT, IncidentSeverity.HIGH),
    (r"hit (?:with|by)\b", IncidentType.ASSAULT, IncidentSeverity.HIGH),
    (r"\briot\b", IncidentType.RIOT, IncidentSeverity.CRITICAL),
    (r"\bclash(?:es|ed)?\b", IncidentType.RIOT, IncidentSeverity.HIGH),
    (r"\bcommunal\b", IncidentType.RIOT, IncidentSeverity.HIGH),
    (r"\bmob\b", IncidentType.RIOT, IncidentSeverity.HIGH),
    (r"\bkidnap(?:ped|ping)?\b", IncidentType.KIDNAPPING, IncidentSeverity.CRITICAL),
    (r"\babduct(?:ed|ion)?\b", IncidentType.KIDNAPPING, IncidentSeverity.CRITICAL),
    (r"\bmissing\b", IncidentType.KIDNAPPING, IncidentSeverity.HIGH),
    (r"\brobbery\b", IncidentType.ROBBERY, IncidentSeverity.HIGH),
    (r"\brobbed\b", IncidentType.ROBBERY, IncidentSeverity.HIGH),
    (r"\bloot(?:ed|ing)?\b", IncidentType.ROBBERY, IncidentSeverity.HIGH),
    (r"\bchain snatch(?:ing|ed)?\b", IncidentType.ROBBERY, IncidentSeverity.HIGH),
    (r"\bsnatch(?:ing|ed)?\b", IncidentType.ROBBERY, IncidentSeverity.HIGH),
    (r"\bdacoity\b", IncidentType.ROBBERY, IncidentSeverity.CRITICAL),
    (r"\btheft\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\bstolen\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\bsteal(?:ing)?\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\bburglary\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\bbreak[-\s]in\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\bthief\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\bthieves\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\baccident\b", IncidentType.TRAFFIC_ACCIDENT, IncidentSeverity.HIGH),
    (r"\bcrash(?:ed|es)?\b", IncidentType.TRAFFIC_ACCIDENT, IncidentSeverity.HIGH),
    (r"\bcollision\b", IncidentType.TRAFFIC_ACCIDENT, IncidentSeverity.HIGH),
    (r"hit[-\s]and[-\s]run\b", IncidentType.TRAFFIC_ACCIDENT, IncidentSeverity.HIGH),
    (r"\bmissile\b", IncidentType.OTHER, IncidentSeverity.HIGH),
    (r"\bharass(?:ment|ed)?\b", IncidentType.HARASSMENT, IncidentSeverity.MEDIUM),
    (r"\bmolest(?:ation|ed)?\b", IncidentType.HARASSMENT, IncidentSeverity.HIGH),
    (r"\bstalking\b", IncidentType.HARASSMENT, IncidentSeverity.MEDIUM),
    (r"\babuse\b", IncidentType.HARASSMENT, IncidentSeverity.MEDIUM),
    (r"\bdowry\b", IncidentType.DOMESTIC_VIOLENCE, IncidentSeverity.HIGH),
    (r"domestic (?:violence|abuse|dispute)\b", IncidentType.DOMESTIC_VIOLENCE, IncidentSeverity.HIGH),
    (r"\bvandalism\b", IncidentType.VANDALISM, IncidentSeverity.MEDIUM),
    (r"\barson\b", IncidentType.VANDALISM, IncidentSeverity.HIGH),
    (r"\bset fire\b", IncidentType.VANDALISM, IncidentSeverity.HIGH),
    (r"\bburn(?:t|ing)?\b", IncidentType.VANDALISM, IncidentSeverity.HIGH),
    (r"suspicious (?:activity|person|object)\b", IncidentType.SUSPICIOUS_ACTIVITY, IncidentSeverity.LOW),
    (r"\bcyber\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\bfraud\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\bcheating\b", IncidentType.THEFT, IncidentSeverity.MEDIUM),
    (r"\bscam\b", IncidentType.THEFT, IncidentSeverity.HIGH),
    (r"\brap(?:e|ed|ist)?\b", IncidentType.ASSAULT, IncidentSeverity.CRITICAL),
    (r"\brain(?:ing)?\b", IncidentType.TRAFFIC_ACCIDENT, IncidentSeverity.MEDIUM),
]

# ─── Location extraction patterns ─────────────────────────────────────────

LOCATION_PATTERNS = [
    # "in <location>, Shivamogga" or "at <location>, Shivamogga"
    r"(?:in|at|near)\s+([A-Za-z\s.]+?)(?:,?\s*(?:Shivamogga|Shimoga))",
    # "Shivamogga's <location>" or "Shivamogga <location>"
    r"(?:Shivamogga|Shimoga)(?:'s)?\s+(?:area|locality|town|village)\s+([A-Za-z\s.]+)",
    # "in <location> area" or "in <location> locality"
    r"(?:in|at|near)\s+([A-Za-z\s.]+?)\s+(?:area|locality|colony|layout)",
    # standalone locality names near Shivamogga keywords
    r"(?:at|in|near)\s+([A-Za-z\s.]+?)(?:\s+(?:in|,))?\s+(?:Shivamogga|Shimoga)",
]


def find_locality_in_text(text: str) -> Optional[Tuple[str, Tuple[float, float]]]:
    """Scan text for known Shivamogga locality names. Returns (name, coords)."""
    if not text:
        return None
    text_lower = text.lower()
    # Sort by length descending to match longer (more specific) names first
    sorted_localities = sorted(SHIVAMOGGA_LOCALITIES.items(), key=lambda x: -len(x[0]))
    for loc_name, coords in sorted_localities:
        if loc_name in text_lower:
            return (loc_name.title(), coords)
    return None


def extract_location_name(text: str) -> Optional[str]:
    """Extract a location name from article text using regex patterns."""
    if not text:
        return None
    # First check for known locality names appearing directly in text
    found = find_locality_in_text(text)
    if found:
        return found[0]
    text_lower = text.lower()
    for pattern in LOCATION_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            loc = m.group(1).strip().strip(",")
            if loc and len(loc) > 2 and len(loc) < 50:
                return loc.title()
    return None


def lookup_locality(name: str) -> Optional[Tuple[float, float]]:
    """Check if the extracted location name is a known Shivamogga locality."""
    if not name:
        return None
    key = name.strip().lower()
    if key in SHIVAMOGGA_LOCALITIES:
        return SHIVAMOGGA_LOCALITIES[key]
    if key.endswith("s") and key[:-1] in SHIVAMOGGA_LOCALITIES:
        return SHIVAMOGGA_LOCALITIES[key[:-1]]
    for loc_name, coords in SHIVAMOGGA_LOCALITIES.items():
        if loc_name in key or key in loc_name:
            return coords
    return None


def classify_incident(text: str) -> Tuple[IncidentType, IncidentSeverity, float]:
    """Classify incident type and severity using keyword matching."""
    text_lower = text.lower()
    best_type = IncidentType.OTHER
    best_severity = IncidentSeverity.MEDIUM
    best_confidence = 0.3

    for pattern, itype, severity in INCIDENT_KEYWORDS:
        if re.search(pattern, text_lower):
            # Higher specificity → higher confidence
            # Murder keywords: 0.9, assault: 0.75, theft: 0.7
            conf_map = {
                IncidentType.MURDER: 0.90,
                IncidentType.ASSAULT: 0.75,
                IncidentType.ROBBERY: 0.75,
                IncidentType.THEFT: 0.70,
                IncidentType.TRAFFIC_ACCIDENT: 0.75,
                IncidentType.KIDNAPPING: 0.80,
                IncidentType.RIOT: 0.75,
                IncidentType.HARASSMENT: 0.65,
                IncidentType.DOMESTIC_VIOLENCE: 0.65,
                IncidentType.VANDALISM: 0.60,
                IncidentType.SUSPICIOUS_ACTIVITY: 0.50,
                IncidentType.OTHER: 0.35,
            }
            confidence = conf_map.get(itype, 0.6)
            if confidence > best_confidence:
                best_type = itype
                best_severity = severity
                best_confidence = confidence

    return best_type, best_severity, best_confidence


# Women-safety keyword overrides — if these match, force a women_safety_category
_WOMEN_SAFETY_KEYWORDS: Dict[str, str] = {
    "rape": "Rape",
    "molest": "Molestation",
    "molestation": "Molestation",
    "sexual assault": "Sexual Assault",
    "sexual harassment": "Sexual Harassment",
    "stalking": "Stalking",
    "cyber stalking": "Cyber Stalking",
    "domestic violence": "Domestic Violence",
    "dowry": "Dowry Harassment",
    "acid attack": "Acid Attack",
    "chain snatch": "Chain Snatching",
    "eve teasing": "Public Harassment",
    "women safety": "Public Harassment",
    "harassment of women": "Public Harassment",
    "woman harassed": "Public Harassment",
    "girl harassed": "Public Harassment",
}


def classify_women_safety_category(text: str, incident_type_str: str) -> Optional[str]:
    """Derive women_safety_category from text or fallback to incident_type mapping."""
    text_lower = text.lower()

    # Check keyword overrides first (more specific)
    for keyword, category in _WOMEN_SAFETY_KEYWORDS.items():
        if keyword in text_lower:
            return category

    # Fallback: map incident_type to women_safety_category
    return INCIDENT_TYPE_TO_WOMEN_SAFETY.get(incident_type_str.upper())


def extract_date_from_text(text: str) -> Optional[str]:
    """Try to extract a date from article text."""
    # Match patterns like "on November 15, 2025" or "Nov 15, 2025" or "15 November 2025"
    patterns = [
        r"(?:on|dated?)\s+(\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+\s+\d{4})",
        r"(?:on|dated?)\s+([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})",
        r"([A-Z][a-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s*\d{4})",
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            date_str = m.group(1)
            for fmt in [
                "%d %B %Y", "%B %d, %Y", "%B %d %Y",
                "%d-%m-%Y", "%m-%d-%Y", "%d/%m/%Y",
            ]:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return None


def extract_newspaper_articles(scraper: NewsScraper, max_articles: int = 120) -> List[dict]:
    """
    Fetch articles from all Shivamogga-related news sources.
    Returns deduplicated list of article dicts.
    """
    all_articles = []
    seen_urls = set()

    # 1. Google News RSS queries
    for url in GOOGLE_NEWS_QUERIES:
        logger.info(f"Fetching Google News RSS: {url[:80]}...")
        articles = scraper.fetch_rss(url)
        for a in articles:
            link = a.get("link", "")
            if link and link not in seen_urls:
                seen_urls.add(link)
                a["source_type"] = "google_news"
                all_articles.append(a)
        logger.info(f"  Got {len(articles)} articles")
        time.sleep(0.3)  # Rate limiting

    # 2. Karnataka RSS feeds — filter for Shivamogga mentions
    for name, feed_url in KARNATAKA_RSS_FEEDS:
        logger.info(f"Fetching {name}: {feed_url}")
        articles = scraper.fetch_rss(feed_url)
        for a in articles:
            title = (a.get("title") or "").lower()
            summary = (a.get("summary") or "").lower()
            combined = title + " " + summary
            # Only keep articles mentioning Shivamogga or nearby towns
            if any(kw in combined for kw in [
                "shivamogga", "shimoga", "bhadravathi", "bhadravati",
                "shikaripura", "sagar", "sagara", "tirthahalli",
            ]):
                link = a.get("link", "")
                if link and link not in seen_urls:
                    seen_urls.add(link)
                    a["source_type"] = "rss"
                    a["feed_name"] = name
                    all_articles.append(a)
        logger.info(f"  Got {len(articles)} from {name}, kept {len([a for a in articles if a.get('link','')])} filtered")

    # 3. Fetch full article content for articles with shallow summaries
    logger.info(f"Total unique articles before content fetch: {len(all_articles)}")
    if len(all_articles) > max_articles:
        all_articles = all_articles[:max_articles]
        logger.info(f"Limited to {max_articles} articles")

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {}
        for article in all_articles:
            link = article.get("link", "")
            summary = article.get("summary", "")
            # Only fetch if summary is short or missing
            if not summary or len(summary) < 100:
                future = pool.submit(scraper.fetch_article_content, link)
                futures[future] = article
        for future in as_completed(futures):
            article = futures[future]
            try:
                content = future.result()
                if content:
                    article["full_text"] = content
            except Exception as e:
                logger.warning(f"Content fetch failed: {e}")

    logger.info(f"Total articles for processing: {len(all_articles)}")
    return all_articles


async def geocode_location(location_name: str, nominatim: NominatimService) -> Optional[Tuple[float, float, str]]:
    """Geocode a location name using cache -> known locality -> Nominatim."""
    if not location_name:
        return None

    # 1. Check known localities map first (fast, no API call)
    coords = lookup_locality(location_name)
    if coords:
        return (coords[0], coords[1], f"{location_name}, Shivamogga, Karnataka")

    # 2. Try Nominatim with cache
    query = f"{location_name}, Shivamogga, Karnataka, India"
    try:
        result = await nominatim.geocode(query)
        if result:
            lat = float(result.get("lat", 0))
            lng = float(result.get("lng", 0))
            display_name = result.get("display_name", "")
            if lat and lng:
                return (lat, lng, display_name)
    except Exception as e:
        logger.warning(f"Nominatim geocode failed for '{query}': {e}")

    return None


async def process_article(
    article: dict,
    nominatim: NominatimService,
    existing_urls: set,
    existing_titles: list,
) -> Optional[dict]:
    """Process a single article into an incident record."""
    title = article.get("title", "")
    summary = article.get("summary", "")
    full_text = article.get("full_text", "")
    link = article.get("link", "")
    source_type = article.get("source_type", "google_news")

    # Skip if URL already exists
    if link in existing_urls:
        return None

    combined_text = f"{title} {summary} {full_text[:3000]}"
    if not combined_text.strip() or len(combined_text) < 30:
        return None

    # Extract location name — prioritize title (has clearest location info)
    location_name = extract_location_name(title)
    if not location_name:
        location_name = extract_location_name(combined_text)

    # Track whether this was specifically geocoded or fallback
    geocode_source = "fallback"

    # Geocode
    geo_result = await geocode_location(location_name, nominatim) if location_name else None
    if geo_result:
        lat, lng, display = geo_result
        geocode_source = "geocoded"
    else:
        # Fallback to Shivamogga city center with small random offset to spread points
        import random
        lat = SHIVAMOGGA_CENTER[0] + random.uniform(-0.02, 0.02)
        lng = SHIVAMOGGA_CENTER[1] + random.uniform(-0.02, 0.02)
        display = "Shivamogga, Karnataka"

    # Classify incident type and severity
    itype, severity, confidence = classify_incident(combined_text)

    # Extract date
    incident_date_str = extract_date_from_text(combined_text)
    incident_date = None
    if incident_date_str:
        try:
            incident_date = datetime.strptime(incident_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # Check title similarity against existing incidents
    title_words = set(title.lower().split()) if title else set()
    for existing_title in existing_titles:
        existing_words = set(existing_title.lower().split())
        if title_words and existing_words:
            intersection = title_words & existing_words
            union = title_words | existing_words
            similarity = len(intersection) / len(union)
            if similarity >= 0.6:
                return None  # Duplicate by title

    source = article.get("source", link)
    description = summary or title

    # Derive women_safety_category
    ws_cat = classify_women_safety_category(combined_text, itype.value)
    ws_weight = None
    if ws_cat and is_women_safety_category(ws_cat):
        _tier, _risk_wt, ws_weight, _base_sev = get_women_safety_details(ws_cat)

    return {
        "title": title[:500],
        "description": description[:1000],
        "incident_type": itype.value,
        "severity": severity.value,
        "women_safety_category": ws_cat,
        "women_safety_weight": ws_weight,
        "confidence": round(confidence, 2),
        "latitude": round(lat, 6),
        "longitude": round(lng, 6),
        "display_name": display,
        "district": "Shivamogga",
        "city": "Shivamogga",
        "source_url": link,
        "source_id": link[:254] if link else link,
        "incident_date": incident_date,
        "incident_date_str": incident_date_str or "",
        "location_name": location_name or "Shivamogga",
        "geocode_source": geocode_source,
    }


async def run_collection(dry_run: bool = False) -> dict:
    """
    Main collection function.
    Returns summary dict with saved/skipped/error counts.
    """
    start = time.time()
    logger.info("=" * 60)
    logger.info("SHIVAMOGGA NEWS COLLECTOR STARTED")
    logger.info("=" * 60)

    scraper = NewsScraper()
    nominatim = NominatimService()
    factory = get_session_factory()

    results = {
        "fetched": 0,
        "processed": 0,
        "geocoded": 0,
        "saved": 0,
        "skipped_dedup": 0,
        "skipped_noloc": 0,
        "errors": [],
        "incidents": [],
    }

    try:
        # Step 1: Fetch articles
        logger.info("Step 1: Fetching Shivamogga news articles...")
        articles = extract_newspaper_articles(scraper)
        results["fetched"] = len(articles)
        logger.info(f"Fetched {len(articles)} articles")

        if not articles:
            logger.warning("No articles fetched — nothing to process")
            results["duration_seconds"] = round(time.time() - start, 2)
            return results

        # Step 2: Load existing data for dedup
        logger.info("Step 2: Loading existing incidents for dedup...")
        existing_urls = set()
        existing_titles = []

        async with factory() as session:
            try:
                existing_result = await session.execute(
                    select(Incident).where(
                        or_(
                            Incident.source == IncidentSource.NEWS,
                            Incident.district.ilike("%shivamogga%"),
                            Incident.district.ilike("%shimoga%"),
                        )
                    ).limit(500)
                )
                existing_incidents = existing_result.scalars().all()
                for inc in existing_incidents:
                    if inc.source_url:
                        existing_urls.add(inc.source_url)
                    if inc.title:
                        existing_titles.append(inc.title)

                # Also check for URLs already in DB from any source
                url_check = await session.execute(
                    select(Incident.source_url).where(
                        Incident.source_url.isnot(None)
                    )
                )
                for row in url_check.fetchall():
                    if row[0]:
                        existing_urls.add(row[0])
            except Exception as e:
                logger.warning(f"Failed to load existing incidents: {e}")

        logger.info(f"Loaded {len(existing_urls)} existing URLs, {len(existing_titles)} titles for dedup")

        # Step 3: Process each article
        logger.info("Step 3: Processing articles...")
        processed_incidents = []

        for i, article in enumerate(articles):
            try:
                incident = await process_article(article, nominatim, existing_urls, existing_titles)
                if incident:
                    processed_incidents.append(incident)
                    existing_urls.add(incident["source_url"])
                    if incident["title"]:
                        existing_titles.append(incident["title"])
                else:
                    results["skipped_dedup"] += 1
            except Exception as e:
                logger.warning(f"Failed to process article {i}: {e}")
                results["errors"].append(str(e))

        results["processed"] = len(processed_incidents)
        geocoded = sum(1 for i in processed_incidents if i.get("geocode_source") == "geocoded")
        fallback = sum(1 for i in processed_incidents if i.get("geocode_source") != "geocoded")
        results["geocoded"] = geocoded
        results["fallback_coords"] = fallback
        logger.info(f"Processed {len(processed_incidents)} incidents ({geocoded} geocoded, {fallback} fallback)")

        results["incidents"] = processed_incidents

        if dry_run:
            logger.info("DRY RUN — skipping database insert")
            results["dry_run"] = True
            results["duration_seconds"] = round(time.time() - start, 2)
            return results

        # Step 4: Insert into database
        logger.info("Step 4: Inserting incidents into database...")
        async with factory() as session:
            saved_count = 0
            for inc in processed_incidents:
                try:
                    ws_cat = inc.get("women_safety_category")
                    ws_weight = inc.get("women_safety_weight")
                    meta = {}
                    if ws_cat and is_women_safety_category(ws_cat):
                        meta["women_safety_category"] = ws_cat
                        meta["women_safety_weight"] = ws_weight
                        # Map to correct IncidentType
                        mapped_type = WOMEN_SAFETY_TO_INCIDENT_TYPE.get(ws_cat)
                        if mapped_type:
                            inc["incident_type"] = mapped_type
                    else:
                        meta["women_safety_category"] = None
                        meta["women_safety_weight"] = None

                    incident = Incident(
                        incident_type=IncidentType(inc["incident_type"]),
                        severity=IncidentSeverity(inc["severity"]),
                        source=IncidentSource.NEWS,
                        status=IncidentStatus.PENDING,
                        confidence_score=inc["confidence"],
                        latitude=inc["latitude"],
                        longitude=inc["longitude"],
                        geom=WKTElement(f"POINT({inc['longitude']} {inc['latitude']})", srid=4326),
                        description=inc["description"],
                        title=inc["title"],
                        address=inc["display_name"],
                        district=inc["district"],
                        city=inc["city"],
                        incident_date=inc["incident_date"] or datetime.now(timezone.utc),
                        source_url=inc["source_url"],
                        source_id=inc["source_id"],
                        ai_classified=True,
                        meta_data=meta,
                    )
                    session.add(incident)
                    saved_count += 1
                except Exception as e:
                    logger.error(f"Failed to save incident: {e}")
                    results["errors"].append(str(e))

            await session.commit()
            results["saved"] = saved_count
            logger.info(f"Saved {saved_count} new incidents to database")

        # Step 5: Recalculate risk scores
        logger.info("Step 5: Recalculating risk scores...")
        try:
            from app.pipeline.risk import recalculate_all_risk_scores
            risk_result = await recalculate_all_risk_scores()
            results["risk_scores_updated"] = risk_result.get("updated", 0)
            logger.info(f"Risk scores updated: {results['risk_scores_updated']}")
        except Exception as e:
            logger.error(f"Risk score update failed: {e}")
            results["errors"].append(f"Risk: {str(e)}")

        # Step 6: Regenerate heatmap
        logger.info("Step 6: Regenerating heatmap...")
        try:
            from app.pipeline.heatmap import compute_localized_bounds
            from app.pipeline.intelligence import update_heatmap_for_bounds

            bounds_list = await compute_localized_bounds(buffer_degrees=0.05, max_cells_per=1000)
            if bounds_list:
                total_points = 0
                for sw_lat, sw_lng, ne_lat, ne_lng in bounds_list:
                    heat_result = await update_heatmap_for_bounds(sw_lat, sw_lng, ne_lat, ne_lng)
                    total_points += heat_result.get("points_generated", 0)
                results["heatmap_points"] = total_points
                logger.info(f"Heatmap: {total_points} points across {len(bounds_list)} zones")
            else:
                # Fallback to Shivamogga region bounds
                sw_lat, sw_lng = 13.6, 74.8
                ne_lat, ne_lng = 14.5, 75.8
                heat_result = await update_heatmap_for_bounds(sw_lat, sw_lng, ne_lat, ne_lng)
                results["heatmap_points"] = heat_result.get("points_generated", 0)
                logger.info(f"Heatmap (fallback): {results['heatmap_points']} points")
        except Exception as e:
            logger.error(f"Heatmap generation failed: {e}")
            results["errors"].append(f"Heatmap: {str(e)}")

    finally:
        scraper.close()
        await nominatim.aclose()

    results["duration_seconds"] = round(time.time() - start, 2)
    results["completed_at"] = datetime.now(timezone.utc).isoformat()

    logger.info("=" * 60)
    logger.info(f"COLLECTION COMPLETE in {results['duration_seconds']}s")
    logger.info(f"  Fetched: {results['fetched']} articles")
    logger.info(f"  Processed: {results['processed']} new incidents")
    logger.info(f"  Saved: {results['saved']} to database")
    logger.info(f"  Risk scores: {results.get('risk_scores_updated', 0)}")
    logger.info(f"  Heatmap points: {results.get('heatmap_points', 0)}")
    logger.info(f"  Errors: {len(results['errors'])}")
    logger.info("=" * 60)

    return results


async def main():
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    import sys
    dry_run = "--dry-run" in sys.argv

    result = await run_collection(dry_run=dry_run)

    print()
    print("=" * 60)
    print("COLLECTION RESULT")
    print("=" * 60)
    for key, value in result.items():
        if key == "incidents":
            continue
        print(f"  {key}: {value}")

    if result.get("incidents"):
        print()
        print(f"Top {min(10, len(result['incidents']))} incidents:")
        for i, inc in enumerate(result["incidents"][:10]):
            print(f"  {i+1}. [{inc['incident_type']}/{inc['severity']}] {inc['title'][:70]}...")
            print(f"       at ({inc['latitude']:.4f}, {inc['longitude']:.4f}) — {inc.get('location_name', '')}")

    return result


if __name__ == "__main__":
    asyncio.run(main())
