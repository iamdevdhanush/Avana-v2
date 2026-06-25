"""Check what articles are actually being returned by RSS feeds"""
import sys, os, logging
sys.path.insert(0, '.')
logging.basicConfig(level=logging.WARNING)
os.environ["MOCK_INTELLIGENCE_MODE"] = "false"

from app.services.news_scraper import NewsScraper

scraper = NewsScraper()
try:
    all_raw = scraper.fetch_all()
    seen = set()
    unique = []
    for a in all_raw:
        url = a.get("link", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(a)
    
    print(f"Total raw: {len(all_raw)}, Unique: {len(unique)}")
    print(f"\nFirst 20 articles by city tag:")
    for i, a in enumerate(unique[:20]):
        city = a.get("city", "??")
        title = a.get("title", "")[:70]
        link = a.get("link", "")[:40]
        print(f"  [{i+1:2d}] [{city:12s}] {title}")
        print(f"       {link}...")
    
    # Check which cities appear
    from collections import Counter
    cities = Counter(a.get("city", "") for a in unique)
    print(f"\nArticles by city:")
    for city, count in cities.most_common():
        print(f"  {city}: {count}")
    
    # Check for Karnataka keywords in titles
    karnataka_kw = ["karnataka", "bengaluru", "bangalore", "mysuru", "mysore", 
                    "mangaluru", "mangalore", "shivamogga", "shimoga", "udupi",
                    "hubli", "dharwad", "belagavi", "belgaum", "tumakuru",
                    "tumkur", "kolar", "chikkaballapur", "ramanagara"]
    
    karnataka_related = 0
    for a in unique:
        title = a.get("title", "").lower()
        if any(kw in title for kw in karnataka_kw):
            karnataka_related += 1
    
    print(f"\nKarnataka-related by title keyword: {karnataka_related}/{len(unique)}")
    
    # Check women's safety keywords
    ws_kw = ["woman", "women", "girl", "female", "harass", "assault", "rape",
             "molest", "dowry", "domestic", "stalking", "kidnap", "traffic",
             "murder", "sex", "abuse"]
    ws_articles = 0
    for a in unique:
        t = a.get("title", "").lower()
        s = a.get("summary", "").lower()
        combined = t + " " + s
        if any(kw in combined for kw in ws_kw):
            ws_articles += 1
    
    print(f"Women's safety-related by title/summary: {ws_articles}/{len(unique)}")
finally:
    scraper.close()
