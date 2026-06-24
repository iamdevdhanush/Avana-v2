"""
News Intelligence Agent

Owns the full news-to-incident pipeline:
  1. Fetch RSS feeds from configured city sources
  2. Scrape full article text (parallel ThreadPoolExecutor)
  3. Extract structured women-safety incidents via AI
  4. Write raw articles to news_articles table (audit trail)
  5. Return extracted incidents to orchestrator -> GeospatialAgent next
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List

from app.models.incident import IncidentType
from app.pipeline.women_safety import WOMEN_SAFETY_CATEGORIES
from app.services.ai.factory import get_ai_provider
from app.services.news_scraper import NewsScraper
from app.utils.timing import Timer

logger = logging.getLogger(__name__)

_INCIDENT_TYPES = [t.value for t in IncidentType]
_MAX_ARTICLES = 50

_CITY_SOURCES = [
    {
        "city": "Bengaluru",
        "feeds": [
            "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms",
            "https://www.thehindu.com/news/cities/bangalore/feeder/default.rss",
            "https://www.deccanherald.com/feed",
        ],
    },
    {
        "city": "Mysuru",
        "feeds": ["https://timesofindia.indiatimes.com/rssfeeds/1078976505.cms"],
    },
    {
        "city": "Mangaluru",
        "feeds": ["https://timesofindia.indiatimes.com/rssfeeds/2452244.cms"],
    },
    {
        "city": "Karnataka",
        "feeds": [
            "https://www.thehindu.com/news/national/karnataka/feeder/default.rss",
            "https://timesofindia.indiatimes.com/rssfeeds/2962392.cms",
            "https://www.deccanherald.com/feed",
        ],
    },
]

# Kannada-language news sources
_KANNADA_SOURCES = [
    {
        "city": "Karnataka",
        "feeds": [
            "https://kannada.oneindia.com/rss/news-karnataka-fb.xml",
            "https://kannada.oneindia.com/rss/news-karnataka.xml",
            "https://vijaykarnataka.com/rssfeeds/29716808.cms",
            "https://kannada.news18.com/rss/uttara-karnataka.xml",
        ],
        "language": "kn",
    },
]

# Source credibility weights (higher = more trusted)
SOURCE_CREDIBILITY_WEIGHTS = {
    "police": 1.0,
    "government": 0.95,
    "verified_community": 0.9,
    "community_report": 0.7,
    "news_english": 0.6,
    "news_kannada": 0.5,
    "user_report": 0.5,
    "sos": 0.4,
    "system": 0.3,
}


class NewsIntelligenceAgent:
    name = "news_intelligence"

    def __init__(self):
        self._categories_list = sorted(WOMEN_SAFETY_CATEGORIES.keys())
        self._ai = get_ai_provider()

    @staticmethod
    def _get_source_credibility(source_url: str, source_city: str) -> float:
        base_weight = SOURCE_CREDIBILITY_WEIGHTS.get("news_english", 0.6)
        if not source_url:
            return base_weight
        url_lower = source_url.lower()
        if any(kw in url_lower for kw in [".gov.in", ".police.", "data.gov"]):
            return SOURCE_CREDIBILITY_WEIGHTS["government"]
        if any(kw in url_lower for kw in ["kannada", "vijaykarnataka", "oneindia", "news18"]):
            return SOURCE_CREDIBILITY_WEIGHTS["news_kannada"]
        return base_weight

    async def run(self, mock_mode: bool = False) -> dict:
        with Timer("3. NewsIntelligenceAgent.run()"):
            start = time.time()
            logger.info("[NEWS_AGENT] Starting news intelligence cycle")

            if not mock_mode:
                from app.config import settings
                mock_mode = settings.MOCK_INTELLIGENCE_MODE
                if not mock_mode and not self._ai.is_available():
                    logger.info("[NEWS_AGENT] AI provider unavailable -- switching to mock mode")
                    mock_mode = True

            if mock_mode:
                result = await self._run_mock(start)
            else:
                result = await self._run_live(start)
            return result

    async def _run_live(self, start: float) -> dict:
        try:
            articles = await self._fetch_articles()
            fetch_metric = {"status": "ok", "count": len(articles), "source": "live"}
        except Exception as exc:
            logger.error(f"[NEWS_AGENT] Fetch failed: {exc}")
            return {
                "status": "failed",
                "step": "fetch",
                "error": str(exc),
                "articles": [],
                "incidents": [],
                "metrics": {"fetch": {"status": "failed", "error": str(exc)}, "duration_seconds": round(time.time() - start, 2)},
            }

        persist_count = await self._persist_articles(articles)
        logger.info(f"[NEWS_AGENT] Articles persisted: {persist_count}/{len(articles)}")

        incidents: List[dict] = []
        ai_success = 0
        ai_failure = 0
        sem = asyncio.Semaphore(5)
        async def _extract_one(a: dict) -> List[dict]:
            nonlocal ai_success, ai_failure
            async with sem:
                try:
                    result = await self._extract_incidents(a)
                    if result:
                        ai_success += 1
                    else:
                        ai_failure += 1
                    return result
                except Exception as exc:
                    logger.warning(f"[NEWS_AGENT] Extraction failed for '{a.get('title', '')}': {exc}")
                    ai_failure += 1
                    return []
        results = await asyncio.gather(*[_extract_one(a) for a in articles], return_exceptions=True)
        for r in results:
            if isinstance(r, list):
                incidents.extend(r)

        logger.info(
            f"[NEWS_AGENT] Extraction: {ai_success} AI calls succeeded, "
            f"{ai_failure} failed, {len(incidents)} incidents extracted"
        )

        if not incidents and not self._ai.is_available():
            logger.warning("[NEWS_AGENT] All AI providers failed — falling back to mock")
            mock_result = await self._run_mock(start)
            mock_result["metrics"]["fetch"] = fetch_metric
            mock_result["metrics"]["extract"] = {
                "status": "ok", "count": len(mock_result.get("incidents", [])),
                "source": "mock_fallback", "ai_success": ai_success, "ai_failure": ai_failure,
            }
            return mock_result

        extract_metric = {
            "status": "ok", "count": len(incidents),
            "ai_success": ai_success, "ai_failure": ai_failure,
        }
        duration = round(time.time() - start, 2)
        logger.info(
            f"[NEWS_AGENT] Complete: {len(articles)} articles -> "
            f"{len(incidents)} incidents ({duration}s). "
            f"AI calls: {ai_success} success, {ai_failure} failed"
        )

        return {
            "status": "ok",
            "articles": articles,
            "incidents": incidents,
            "metrics": {
                "fetch": fetch_metric,
                "extract": extract_metric,
                "duration_seconds": duration,
                "persist_count": persist_count,
            },
        }

    async def _run_mock(self, start: float) -> dict:
        from app.pipeline.intelligence_mock import get_mock_incidents
        mock_incidents = get_mock_incidents()
        duration = round(time.time() - start, 2)
        logger.info(f"[NEWS_AGENT] Mock mode: {len(mock_incidents)} incidents")
        return {
            "status": "ok",
            "articles": [],
            "incidents": mock_incidents,
            "metrics": {
                "fetch": {"status": "ok", "count": 5, "source": "mock"},
                "extract": {"status": "ok", "count": len(mock_incidents), "source": "mock"},
                "duration_seconds": duration,
            },
        }

    async def _fetch_articles(self) -> List[dict]:
        with Timer("4. RSS feed fetch + article scraping"):
            scraper = NewsScraper()
            articles = []
            try:
                all_raw = scraper.fetch_all()
                # Also fetch Kannada-language sources
                for entry in _KANNADA_SOURCES:
                    for feed_url in entry["feeds"]:
                        try:
                            kannada_articles = scraper.fetch_rss(feed_url)
                            for ka in kannada_articles:
                                ka["city"] = entry["city"]
                                ka["language"] = entry.get("language", "kn")
                            all_raw.extend(kannada_articles)
                        except Exception as exc:
                            logger.warning(f"[NEWS_AGENT] Kannada feed fetch failed: {exc}")

                seen_urls: set = set()
                unique = []
                for a in all_raw:
                    url = a.get("link", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        unique.append(a)

                if len(unique) > _MAX_ARTICLES:
                    unique = unique[:_MAX_ARTICLES]

                logger.info(f"[NEWS_AGENT] {len(unique)} unique articles to scrape ({len(unique) - sum(1 for a in all_raw if a.get('link') in seen_urls)} new)")

                loop = asyncio.get_event_loop()
                articles = await loop.run_in_executor(
                    None,
                    lambda: self._fetch_content_parallel(scraper, unique),
                )
            finally:
                scraper.close()
            return articles

    @staticmethod
    def _fetch_content_parallel(scraper: NewsScraper, articles: List[dict]) -> List[dict]:
        results = []
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                pool.submit(scraper.fetch_article_content, a.get("link", "")): a
                for a in articles
            }
            for future in as_completed(futures):
                article = futures[future]
                try:
                    full_text = future.result()
                    results.append({
                        "city": article.get("city", ""),
                        "title": article.get("title", ""),
                        "link": article.get("link", ""),
                        "summary": article.get("summary", ""),
                        "full_text": full_text or article.get("summary", ""),
                    })
                except Exception as exc:
                    logger.warning(f"[NEWS_AGENT] Content fetch failed: {exc}")
        return results

    async def _persist_articles(self, articles: List[dict]) -> int:
        with Timer("11a. DB insert - news_articles"):
            if not articles:
                return 0
            from sqlalchemy import text
            from app.database import get_session_factory

            factory = get_session_factory()
            written = 0
            async with factory() as session:
                for a in articles:
                    url = a.get("link", "")
                    if not url:
                        continue
                    try:
                        result = await session.execute(
                            text("""
                                INSERT INTO news_articles
                                    (id, title, url, source, source_type,
                                     published_at, fetched_at, content, summary,
                                     is_processed, created_at)
                                VALUES (
                                    gen_random_uuid(),
                                    :title, :url, :source, 'rss',
                                    NOW(), NOW(), :content, :summary,
                                    false, NOW()
                                )
                                ON CONFLICT (url) DO NOTHING
                            """),
                            {
                                "title": (a.get("title") or "")[:500],
                                "url": url[:2048],
                                "source": a.get("city", "")[:100],
                                "content": (a.get("full_text") or "")[:10000],
                                "summary": (a.get("summary") or "")[:2000],
                            },
                        )
                        written += result.rowcount if hasattr(result, "rowcount") else 1
                    except Exception as exc:
                        logger.warning(f"[NEWS_AGENT] Failed to persist article '{url[:60]}': {exc}")
                await session.commit()
            logger.info(f"[NEWS_AGENT] Persisted {written} articles to news_articles")
            return written

    async def _extract_incidents(self, article: dict) -> List[dict]:
        with Timer("7+8+9. AI request (OpenRouter) + JSON parsing"):
            text_content = article.get("full_text", "")
            if not text_content or len(text_content) < 50:
                return []

            source_language = article.get("language", "en")
            language_note = ""
            if source_language == "kn":
                language_note = " This article is in Kannada language. Translate to English before extracting."

            prompt = (
                "Extract WOMEN'S SAFETY incidents from this news article."
                + language_note +
                "ONLY extract incidents relevant to women's safety (crimes against women/girls). "
                "Skip generic crimes like theft, fraud, accidents, riots, vandalism.\n\n"
                "Return a JSON array of objects with these fields:\n"
                f"- incident_type: one of [{', '.join(_INCIDENT_TYPES)}]\n"
                "- severity: one of [low, medium, high, critical]\n"
                "- women_safety_category: one of [" + ", ".join(self._categories_list) + "]\n"
                "- location: the specific location name mentioned\n"
                "- district: the Karnataka district\n"
                "- city: the city name\n"
                "- description: brief description (max 200 chars)\n"
                "- confidence: float 0.0-1.0\n"
                "- incident_date: date in YYYY-MM-DD if mentioned, else null\n\n"
                "IMPORTANT: women_safety_category is REQUIRED.\n"
                "If no valid incidents, return [].\n\n"
                f"Title: {article.get('title', '')}\n"
                f"Text: {text_content[:6000]}"
            )
            system = (
                "You are a women's safety incident extraction AI for Karnataka, India. "
                "ONLY extract crimes against women. Return ONLY valid JSON. No markdown."
            )

            import json
            response = await self._ai.generate(prompt, system_instruction=system)
            if not response:
                return []

            cleaned = response.strip()
            for prefix in ("```json", "```"):
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix):]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            try:
                incidents = json.loads(cleaned.strip())
                if isinstance(incidents, dict):
                    incidents = [incidents]
                source_cred = self._get_source_credibility(
                    article.get("link", ""),
                    article.get("city", ""),
                )
                for inc in incidents:
                    inc["source_url"] = article.get("link", "")
                    inc["source_city"] = article.get("city", "")
                    inc["article_title"] = article.get("title", "")
                    inc["source_credibility"] = source_cred
                    inc["language"] = source_language
                    # Adjust AI confidence by source credibility
                    ai_conf = float(inc.get("confidence", 0.7))
                    adjusted_conf = ai_conf * (0.5 + 0.5 * source_cred)
                    inc["confidence"] = round(min(1.0, adjusted_conf), 2)
                return incidents
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(f"[NEWS_AGENT] Failed to parse AI JSON: {exc}")
                return []
