import logging
import httpx
import feedparser
from bs4 import BeautifulSoup
from typing import List, Optional, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class NewsScraper:
    RSS_FEEDS: Dict[str, List[str]] = {
        "Bengaluru": [
            "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms",
            "https://www.thehindu.com/news/cities/bangalore/feeder/default.rss",
            "https://www.deccanherald.com/rss/karnataka/bengaluru.rss",
        ],
        "Mysuru": [
            "https://www.thehindu.com/news/national/karnataka/mysore/feeder/default.rss",
            "https://timesofindia.indiatimes.com/rssfeeds/1078976505.cms",
        ],
        "Mangaluru": [
            "https://www.thehindu.com/news/national/karnataka/mangalore/feeder/default.rss",
            "https://timesofindia.indiatimes.com/rssfeeds/2452244.cms",
        ],
        "Hubballi": [
            "https://www.thehindu.com/news/national/karnataka/hubli/feeder/default.rss",
        ],
        "Belagavi": [
            "https://www.thehindu.com/news/national/karnataka/belagavi/feeder/default.rss",
        ],
        "Dharwad": [
            "https://www.thehindu.com/news/national/karnataka/dharwad/feeder/default.rss",
        ],
        "Kalaburagi": [
            "https://www.thehindu.com/news/national/karnataka/kalaburagi/feeder/default.rss",
        ],
        "Shivamogga": [
            "https://www.thehindu.com/news/national/karnataka/shivamogga/feeder/default.rss",
        ],
        "Karnataka": [
            "https://www.thehindu.com/news/national/karnataka/feeder/default.rss",
            "https://timesofindia.indiatimes.com/rssfeeds/2962392.cms",
            "https://www.deccanherald.com/rss/karnataka.rss",
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

    def fetch_rss(self, url: str) -> List[dict]:
        articles = []
        try:
            response = self.client.get(url)
            response.raise_for_status()
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
            logger.info(f"Fetched {len(articles)} articles from {url}")
        except httpx.TimeoutException:
            logger.warning(f"RSS fetch timeout: {url}")
        except httpx.HTTPStatusError as e:
            logger.warning(f"RSS fetch HTTP {e.response.status_code}: {url}")
        except Exception as e:
            logger.error(f"RSS fetch error for {url}: {e}")
        return articles

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
        all_articles = []
        for city, feeds in self.RSS_FEEDS.items():
            for feed_url in feeds:
                articles = self.fetch_rss(feed_url)
                for article in articles:
                    article["city"] = city
                all_articles.extend(articles)
        logger.info(f"Total articles fetched from all feeds: {len(all_articles)}")
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
