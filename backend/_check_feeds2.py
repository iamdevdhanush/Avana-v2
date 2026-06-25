"""Check per-feed article counts to understand first-50 selection"""
import sys, os, logging
sys.path.insert(0, '.')
logging.basicConfig(level=logging.WARNING)
os.environ["MOCK_INTELLIGENCE_MODE"] = "false"

from app.services.news_scraper import NewsScraper

# Simulate what NewsIntelligenceAgent._fetch_articles does
from collections import Counter
from app.agents.news_intelligence import _KANNADA_SOURCES

scraper = NewsScraper()

try:
    # Part 1: English feeds (what fetch_all returns)
    all_en = scraper.fetch_all()
    
    # Part 2: Kannada feeds
    all_kn = []
    for entry in _KANNADA_SOURCES:
        for feed_url in entry["feeds"]:
            ka = scraper.fetch_rss(feed_url)
            for a in ka:
                a["city"] = entry["city"]
                a["language"] = entry.get("language", "kn")
            all_kn.extend(ka)
    
    # Combined in order
    all_raw = all_en + all_kn
    print(f"English articles: {len(all_en)}")
    print(f"Kannada articles: {len(all_kn)}")
    print(f"Total: {len(all_raw)}")
    
    # Dedup by URL (preserving order)
    seen = set()
    unique = []
    for a in all_raw:
        url = a.get("link", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(a)
    
    print(f"\nUnique: {len(unique)}")
    
    # Show first 50 articles with their feed source
    from app.services.news_scraper import NewsScraper as NS
    en_feed_urls = []
    for city, feeds in NS.RSS_FEEDS.items():
        for f in feeds:
            en_feed_urls.append(f)
    
    print(f"\nFirst {min(50, len(unique))} articles (in order):")
    sources = Counter()
    karnataka_kw = ["karnataka", "bengaluru", "bangalore", "mysuru", "mysore", 
                    "mangaluru", "mangalore", "shivamogga", "shimoga", "udupi",
                    "hubli", "dharwad", "belagavi", "belgaum", "tumakuru",
                    "tumkur", "kolar", "chikkaballapur", "ramanagara",
                    "dakshina", "kannada", "bellary", "ballari", "gulbarga",
                    "kalaburagi", "raichur", "bidar", "hassan", "chitradurga",
                    "davanagere", "mandya", "haveri", "gadag", "bagalkot",
                    "bagalkote", "koppal", "yadgir", "vijayapura", "bijapur",
                    "chikkodi", "nalgonda", "karwar", "honnavar", "bhatkal",
                    "puttur", "sullia", "madikeri", "virajpet", "sakleshpur",
                    "tirthahalli", "shivaji nagar", "jayanagar", "koramangala",
                    "indiranagar", "whitefield", "malleswaram", "bannerghatta",
                    "electronic city", "marathahalli", "hebbal", "yeshwanthpur",
                    "rajajinagar", "basavanagudi", "k.r. market", "k r market",
                    "mg road", "brigade road", "commercial street", "lalbagh",
                    "cubbon park", "vidhana soudha", "karnataka", "ballari",
                    "urapakkam", "kengeri", "banashankari", "padmanabhanagar",
                    "kumaraswamy layout", "btm layout", "hsr layout"]
    
    for i, a in enumerate(unique[:50]):
        source = a.get("source", a.get("link", "")[:50])
        source_label = "?"
        for f in en_feed_urls:
            if f in source:
                source_label = f.split("/")[-1][:25]
                break
        if "tv9kannada" in source:
            source_label = "tv9kannada"
        elif "asianetnews" in source:
            source_label = "asianetnews"
        elif "publictv" in source:
            source_label = "publictv"
        elif "timesofindia" in source:
            source_label = "TOI"
        elif "thehindu" in source:
            source_label = "TheHindu"
        elif "deccanherald" in source:
            source_label = "DH"
        
        title = a.get("title", "")
        in_ka = any(kw in title.lower() for kw in karnataka_kw)
        sources[source_label] += 1
        ka_flag = "KA" if in_ka else "  "
        print(f"  [{i+1:2d}] [{source_label:15s}] [{ka_flag}] {title[:60]}")
    
    print(f"\nSource distribution (first 50):")
    for src, count in sources.most_common():
        print(f"  {src}: {count}")
    
    # Now try the actual pipeline fetch
    print(f"\n--- Now simulating pipeline selection ---")
    print(f"Pipeline limits to {min(50, len(unique))} articles")
    print(f"After dedup, unique = {len(unique)}")
    
finally:
    scraper.close()
