"""
News Intelligence Agent

Owns the full news-to-incident pipeline:
  1. Fetch RSS feeds from configured city sources
  2. Scrape full article text (parallel ThreadPoolExecutor)
  3. Extract structured women-safety incidents via Gemini
  4. Write raw articles to news_articles table (audit trail)
  5. Return extracted incidents to orchestrator → GeospatialAgent next
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import List

from app.models.incident import IncidentType
from app.pipeline.women_safety import WOMEN_SAFETY_CATEGORIES
from app.services.gemini import gemini_service, GeminiQuotaExceeded
from app.services.news_scraper import NewsScraper

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


class NewsIntelligenceAgent:
    """
    Collects news articles and extracts women-safety incidents via Gemini.

    Usage:
        agent = NewsIntelligenceAgent()
        result = await agent.run()
        # result["articles"]  → List[dict] raw articles
        # result["incidents"] → List[dict] extracted incidents (pre-geocode)
        # result["metrics"]   → execution metrics dict
    """

    name = "news_intelligence"

    def __init__(self):
        self._categories_list = sorted(WOMEN_SAFETY_CATEGORIES.keys())

    # ──────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────

    async def run(self, mock_mode: bool = False) -> dict:
        """
        Execute the full news intelligence cycle.

        Returns a structured result consumed by PipelineOrchestrator.
        """
        start = time.time()
        logger.info("[NEWS_AGENT] Starting news intelligence cycle")

        # Resolve mock mode if not forced externally
        if not mock_mode:
            from app.config import settings
            mock_mode = settings.MOCK_INTELLIGENCE_MODE
            if not mock_mode and gemini_service.get_unavailable_reason():
                logger.info("[NEWS_AGENT] Gemini unavailable — switching to mock mode")
                mock_mode = True

        if mock_mode:
            return await self._run_mock(start)

        return await self._run_live(start)

    # ──────────────────────────────────────────────────────────────────
    # Live pipeline
    # ──────────────────────────────────────────────────────────────────

    async def _run_live(self, start: float) -> dict:
        # Step 1 — fetch
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

        # Step 2 — write raw articles to news_articles table
        await self._persist_articles(articles)

        # Step 3 — extract incidents via Gemini
        incidents: List[dict] = []
        for article in articles:
            try:
                extracted = await self._extract_incidents(article)
                incidents.extend(extracted)
            except GeminiQuotaExceeded:
                logger.error("[NEWS_AGENT] Gemini quota exhausted mid-extraction — stopping early")
                break
            except Exception as exc:
                logger.warning(f"[NEWS_AGENT] Extraction failed for '{article.get('title', '')}': {exc}")

        extract_metric = {"status": "ok", "count": len(incidents)}
        duration = round(time.time() - start, 2)
        logger.info(f"[NEWS_AGENT] Complete: {len(articles)} articles → {len(incidents)} incidents ({duration}s)")

        return {
            "status": "ok",
            "articles": articles,
            "incidents": incidents,
            "metrics": {
                "fetch": fetch_metric,
                "extract": extract_metric,
                "duration_seconds": duration,
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

    # ──────────────────────────────────────────────────────────────────
    # Article fetching
    # ──────────────────────────────────────────────────────────────────

    async def _fetch_articles(self) -> List[dict]:
        scraper = NewsScraper()
        articles = []
        try:
            all_raw = scraper.fetch_all()
            seen_urls: set = set()
            unique = []
            for a in all_raw:
                url = a.get("link", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique.append(a)

            if len(unique) > _MAX_ARTICLES:
                unique = unique[:_MAX_ARTICLES]

            logger.info(f"[NEWS_AGENT] {len(unique)} unique articles to scrape")

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

    # ──────────────────────────────────────────────────────────────────
    # Article persistence (news_articles table)
    # ──────────────────────────────────────────────────────────────────

    async def _persist_articles(self, articles: List[dict]) -> None:
        """Write raw articles to news_articles for audit trail."""
        if not articles:
            return
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
                    await session.execute(
                        text("""
                            INSERT INTO news_articles
                                (id, title, url, source, source_type,
                                 published_at, content, summary,
                                 is_processed, created_at)
                            VALUES (
                                gen_random_uuid(),
                                :title, :url, :source, 'rss',
                                NOW(), :content, :summary,
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
                    written += 1
                except Exception as exc:
                    logger.warning(f"[NEWS_AGENT] Failed to persist article '{url[:60]}': {exc}")
            await session.commit()
        logger.info(f"[NEWS_AGENT] Persisted {written} articles to news_articles")

    # ──────────────────────────────────────────────────────────────────
    # Gemini extraction
    # ──────────────────────────────────────────────────────────────────

    async def _extract_incidents(self, article: dict) -> List[dict]:
        """Run Gemini extraction prompt against one article."""
        text_content = article.get("full_text", "")
        if not text_content or len(text_content) < 50:
            return []

        prompt = (
            "Extract WOMEN'S SAFETY incidents from this news article. "
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
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: gemini_service.generate(prompt, system_instruction=system),
        )
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
            for inc in incidents:
                inc["source_url"] = article.get("link", "")
                inc["source_city"] = article.get("city", "")
                inc["article_title"] = article.get("title", "")
            return incidents
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"[NEWS_AGENT] Failed to parse Gemini JSON: {exc}")
            return []
