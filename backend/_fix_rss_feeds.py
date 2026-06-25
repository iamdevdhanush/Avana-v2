"""Diagnose and find working RSS feed URLs for Karnataka cities."""
import sys, os, logging, httpx
sys.path.insert(0, '.')
logging.basicConfig(level=logging.WARNING)
os.environ["MOCK_INTELLIGENCE_MODE"] = "false"

# Test feed URLs
test_feeds = {
    "TOI Bangalore (current -2128838597)": "https://timesofindia.indiatimes.com/rssfeeds/-2128838597.cms",
    "TOI Bangalore (2950723)": "https://timesofindia.indiatimes.com/rssfeeds/2950723.cms",
    "TOI Bangalore (alternate)": "https://timesofindia.indiatimes.com/rssfeeds/1221638.cms",
    "TOI Bangalore (city)": "https://timesofindia.indiatimes.com/rssfeeds/1104171.cms",
    "TOI Mysuru (current)": "https://timesofindia.indiatimes.com/rssfeeds/1078976505.cms",
    "TOI Mysuru (alt)": "https://timesofindia.indiatimes.com/rssfeeds/1078976505.cms",
    "TOI Karnataka (current)": "https://timesofindia.indiatimes.com/rssfeeds/2962392.cms",
    "TOI Mangaluru (current)": "https://timesofindia.indiatimes.com/rssfeeds/2452244.cms",
    "The Hindu Bengaluru": "https://www.thehindu.com/news/cities/bangalore/feeder/default.rss",
    "The Hindu Karnataka": "https://www.thehindu.com/news/national/karnataka/feeder/default.rss",
    "Deccan Herald": "https://www.deccanherald.com/feed",
    "TV9 Kannada": "https://tv9kannada.com/rss",
    "Asianet News Crime": "https://kannada.asianetnews.com/rss/crime",
    "Asianet News": "https://kannada.asianetnews.com/rss",
    "Public TV": "https://publictv.in/rss",
}

import feedparser

client = httpx.Client(timeout=15.0, follow_redirects=True, headers={
    "User-Agent": "Avana-SafetyBot/2.0 (karnataka-safety-app)",
    "Accept": "application/rss+xml,application/xml,text/xml,*/*",
})

for name, url in test_feeds.items():
    try:
        resp = client.get(url)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
        entries = len(parsed.entries)
        
        # Check where the first few articles are from
        cities = set()
        karnataka_count = 0
        for e in parsed.entries[:10]:
            title = e.get("title", "")
            link = e.get("link", "")
            # Extract location from title or URL
            title_lower = title.lower()
            # Check if it's Karnataka
            is_ka = any(kw in title_lower for kw in [
                "karnataka", "bengaluru", "bangalore", "mysuru", "mysore",
                "mangaluru", "mangalore", "belagavi", "hubli", "dharwad",
                "shivamogga", "udupi", "tumakuru", "ballari", "kalaburagi",
                "hassan", "davangere", "mandya", "chitradurga", "raichur",
                "bidar", "koppal", "gadag", "haveri", "vijayapura"
            ])
            if is_ka:
                karnataka_count += 1
            
            # Extract city hint from URL
            if "/city/" in link:
                city_part = link.split("/city/")[1].split("/")[0]
                cities.add(city_part)
        
        status = "OK" if resp.status_code == 200 else f"HTTP {resp.status_code}"
        print(f"[{status}] {name}")
        print(f"       URL: {url}")
        print(f"       Articles: {entries} | KA in first 10: {karnataka_count}/10 | Cities: {cities}")
        
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
    
    print()

client.close()
