import logging
import time
import httpx
import feedparser
from bs4 import BeautifulSoup
from typing import List, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class FeedHealth:
    __slots__ = ("url", "status_code", "articles_found", "response_time_ms", "error", "city", "language")

    def __init__(self, url: str = "", status_code: int = 0, articles_found: int = 0,
                 response_time_ms: int = 0, error: str = "", city: str = "", language: str = "en"):
        self.url = url
        self.status_code = status_code
        self.articles_found = articles_found
        self.response_time_ms = response_time_ms
        self.error = error
        self.city = city
        self.language = language

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "articles_found": self.articles_found,
            "response_time_ms": self.response_time_ms,
            "error": self.error,
        }


class NewsScraper:
    RSS_FEEDS: Dict[str, List[str]] = {
        "Bengaluru": [
            "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms",
            "https://www.thehindu.com/news/cities/bangalore/feeder/default.rss",
            "https://www.deccanherald.com/feed",
        ],
        "Mysuru": [
            "https://timesofindia.indiatimes.com/rssfeeds/1078976505.cms",
        ],
        "Mangaluru": [
            "https://timesofindia.indiatimes.com/rssfeeds/2452244.cms",
        ],
        "Karnataka": [
            "https://www.thehindu.com/news/national/karnataka/feeder/default.rss",
            "https://timesofindia.indiatimes.com/rssfeeds/2962392.cms",
            "https://www.deccanherald.com/feed",
        ],
    }

    def __init__(self):
        self.client = httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Avana-SafetyBot/2.0 (karnataka-safety-app)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        # Track per-feed health across a fetch_all() cycle
        self._last_health: List[FeedHealth] = []

    def fetch_rss(self, url: str) -> List[dict]:
        articles = []
        health = FeedHealth(url=url)
        start_ms = int(time.time() * 1000)
        try:
            response = self.client.get(url)
            response.raise_for_status()
            health.status_code = response.status_code
            parsed = feedparser.parse(response.text)
            for entry in parsed.entries:
                published = entry.get("published", "")
                published_parsed = entry.get("published_parsed")
                if published_parsed:
                    try:
                        published = datetime(*published_parsed[:6]).isoformat()
                    except (ValueError, TypeError):
                        pass
                articles.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", entry.get("description", "")),
                    "published": published,
                    "source": url,
                    "feed_title": parsed.feed.get("title", ""),
                })
            health.articles_found = len(articles)
            logger.info(f"[RSS] Feed: {url}")
            logger.info(f"[RSS] Status: {health.status_code}")
            logger.info(f"[RSS] Articles: {health.articles_found}")
        except httpx.TimeoutException:
            health.error = "timeout"
            logger.warning(f"[RSS] Feed: {url}")
            logger.warning(f"[RSS] Status: timeout")
            logger.warning(f"[RSS] Articles: 0")
        except httpx.HTTPStatusError as e:
            health.status_code = e.response.status_code
            health.error = f"HTTP {e.response.status_code}"
            logger.warning(f"[RSS] Feed: {url}")
            logger.warning(f"[RSS] Status: {e.response.status_code}")
            logger.warning(f"[RSS] Articles: 0")
        except Exception as e:
            health.error = str(e)
            logger.error(f"[RSS] Feed: {url}")
            logger.error(f"[RSS] Status: error")
            logger.error(f"[RSS] Articles: 0 — {e}")
        health.response_time_ms = int(time.time() * 1000) - start_ms
        self._last_health.append(health)
        return articles

    def check_feed_health(self, url: str, city: str = "", language: str = "en") -> FeedHealth:
        start_ms = int(time.time() * 1000)
        try:
            response = self.client.get(url)
            response.raise_for_status()
            parsed = feedparser.parse(response.text)
            entry_count = len(parsed.entries)
            elapsed = int(time.time() * 1000) - start_ms
            return FeedHealth(
                url=url, status_code=response.status_code,
                articles_found=entry_count, response_time_ms=elapsed,
                city=city, language=language,
            )
        except httpx.TimeoutException:
            elapsed = int(time.time() * 1000) - start_ms
            return FeedHealth(url=url, error="timeout", response_time_ms=elapsed, city=city, language=language)
        except httpx.HTTPStatusError as e:
            elapsed = int(time.time() * 1000) - start_ms
            return FeedHealth(
                url=url, status_code=e.response.status_code,
                error=f"HTTP {e.response.status_code}", response_time_ms=elapsed,
                city=city, language=language,
            )
        except Exception as e:
            elapsed = int(time.time() * 1000) - start_ms
            return FeedHealth(url=url, error=str(e), response_time_ms=elapsed, city=city, language=language)

    def check_all_feeds_health(self) -> dict:
        healthy = []
        failed = []
        for city, feeds in self.RSS_FEEDS.items():
            for feed_url in feeds:
                health = self.check_feed_health(feed_url, city=city)
                if health.status_code == 200 and not health.error:
                    healthy.append(health.to_dict())
                else:
                    failed.append(health.to_dict())
        return {"healthy": healthy, "failed": failed, "feeds": healthy + failed}

    def fetch_article_content(self, url: str) -> Optional[str]:
        try:
            response = self.client.get(url)
            if response.status_code != 200:
                logger.warning(f"Article fetch returned {response.status_code}: {url}")
                return None
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "svg", "form"]):
                tag.decompose()
            for tag in soup.find_all(class_=["advertisement", "sidebar", "comments", "related-articles"]):
                tag.decompose()
            paragraphs = soup.find_all("p")
            text = " ".join(
                p.get_text(strip=True) for p in paragraphs
                if len(p.get_text(strip=True)) > 20
            )
            if not text:
                div_texts = []
                for div in soup.find_all("div", class_=["article-body", "story-body", "content", "article-content"]):
                    div_texts.append(div.get_text(strip=True))
                text = " ".join(div_texts)
            return text[:10000] if text else None
        except httpx.TimeoutException:
            logger.warning(f"Article fetch timeout: {url}")
            return None
        except Exception as e:
            logger.error(f"Article fetch error for {url}: {e}")
            return None

    def fetch_all(self) -> List[dict]:
        self._last_health = []
        all_articles = []
        for city, feeds in self.RSS_FEEDS.items():
            for feed_url in feeds:
                articles = self.fetch_rss(feed_url)
                for article in articles:
                    article["city"] = city
                all_articles.extend(articles)
        healthy = sum(1 for h in self._last_health if not h.error and h.status_code == 200)
        failed = sum(1 for h in self._last_health if h.error or h.status_code != 200)
        logger.info(f"[RSS SUMMARY] Healthy feeds: {healthy}")
        logger.info(f"[RSS SUMMARY] Failed feeds: {failed}")
        logger.info(f"[RSS SUMMARY] Total articles: {len(all_articles)}")
        return all_articles

    def fetch_city_news(self, city: str) -> List[dict]:
        feeds = self.RSS_FEEDS.get(city)
        if not feeds:
            logger.warning(f"No RSS feeds configured for city: {city}")
            return []
        articles = []
        for feed_url in feeds:
            city_articles = self.fetch_rss(feed_url)
            for article in city_articles:
                article["city"] = city
            articles.extend(city_articles)
        logger.info(f"Fetched {len(articles)} articles for {city}")
        return articles

    def close(self):
        self.client.close()

    def __del__(self):
        self.close()
