"""
Forensic Trace: News Intelligence Pipeline
Traces every stage from RSS → AI → Parser → Validator → Database
"""
import asyncio, sys, json, logging, time, os
sys.path.insert(0, '.')
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
os.environ["MOCK_INTELLIGENCE_MODE"] = "false"

from app.services.news_scraper import NewsScraper
from app.agents.news_intelligence import NewsIntelligenceAgent, _INCIDENT_TYPES
from app.pipeline.women_safety import WOMEN_SAFETY_CATEGORIES

_METRICS = {
    "articles_fetched": 0, "articles_scraped": 0,
    "ai_requests_sent": 0, "ai_failures": 0,
    "empty_ai_responses": 0, "json_parse_failures": 0,
    "validation_failures": 0, "duplicate_incidents": 0,
    "db_insert_failures": 0, "incidents_saved": 0,
    "short_content_rejected": 0,
}

class TraceItem:
    def __init__(self, article):
        self.title = article.get("title", "")
        self.link = article.get("link", "")
        self.city = article.get("city", "")
        self.summary_len = len(article.get("summary", ""))
        self.full_text_len = len(article.get("full_text", ""))
        self.prompt = None
        self.raw_response = None
        self.model_output = None
        self.parsed_json = None
        self.num_incidents = 0
        self.validation_result = None
        self.rejection_reason = None
        self.db_insert_attempted = False
        self.db_insert_succeeded = False

    def __str__(self):
        return f"Trace({self.title[:50]}, text={self.full_text_len}, incidents={self.num_incidents})"

async def trace_article(agent, article) -> TraceItem:
    t = TraceItem(article)
    
    print(f"\n{'='*70}")
    print(f"ARTICLE: {article.get('title', '')[:80]}")
    print(f"{'='*70}")
    print(f"  City: {article.get('city', '')}")
    print(f"  Link: {article.get('link', '')}")
    print(f"  Summary length: {len(article.get('summary', ''))}")
    print(f"  Full text length: {len(article.get('full_text', ''))}")
    
    text_content = article.get("full_text", "")
    
    # Stage 1: Short content check
    if not text_content or len(text_content) < 50:
        print(f"  ↓")
        print(f"  REJECTED: text < 50 chars ({len(text_content)})")
        print(f"  File: app/agents/news_intelligence.py")
        print(f"  Function: _extract_incidents")
        print(f"  Line: 356-357")
        print(f"  Condition: len(text_content) < 50")
        _METRICS["short_content_rejected"] += 1
        return t
    
    print(f"  ↓")
    
    # Stage 2: Build prompt
    categories_list = sorted(WOMEN_SAFETY_CATEGORIES.keys())
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
        "- women_safety_category: one of [" + ", ".join(categories_list) + "]\n"
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
    
    print(f"  ↓")
    print(f"  PROMPT sent to OpenRouter ({len(prompt)} chars):")
    for line in prompt.split('\n')[:5]:
        print(f"    {line}")
    print(f"    ...")
    
    _METRICS["ai_requests_sent"] += 1
    t.prompt = prompt
    
    # We can't actually call OpenRouter without API key
    # Simulate the AI call failure (this is what would happen with no API key)
    ai_available = agent._ai.is_available()
    print(f"  [AI Provider available: {ai_available}]")
    
    if not ai_available:
        print(f"  ↓")
        print(f"  AI UNAVAILABLE: No API key configured")
        print(f"  File: app/services/ai/openrouter_provider.py")
        print(f"  Function: generate")
        print(f"  Line: 80-82")
        print(f"  Condition: not self._available -> return \"\"")
        _METRICS["ai_failures"] += 1
        _METRICS["empty_ai_responses"] += 1
        return t
    
    # This path won't be reached without API key
    t.model_output = "(simulated - would call OpenRouter)"
    t.parsed_json = []
    t.num_incidents = 0
    t.validation_result = "no_incidents"
    
    return t

async def main():
    print("=" * 70)
    print("FORENSIC TRACE: News Intelligence Pipeline")
    print("=" * 70)
    
    # Fetch real RSS articles (Stage 1)
    print(f"\n{'='*70}")
    print("STAGE 1: RSS FEED FETCH")
    print(f"{'='*70}")
    
    scraper = NewsScraper()
    try:
        all_raw = scraper.fetch_all()
        seen_urls = set()
        unique = []
        for a in all_raw:
            url = a.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(a)
        
        print(f"Raw RSS entries: {len(all_raw)}")
        print(f"Unique articles: {len(unique)}")
        
        # Limit to 5 for detailed trace
        first_5 = unique[:5]
        _METRICS["articles_fetched"] = len(first_5)
        
        print(f"Tracing first {len(first_5)} articles...")
        
        # Scrape content for these articles (Stage 2)
        print(f"\n{'='*70}")
        print("STAGE 2: CONTENT SCRAPING")
        print(f"{'='*70}")
        
        from app.agents.news_intelligence import NewsIntelligenceAgent
        articles_with_content = NewsIntelligenceAgent._fetch_content_parallel(scraper, first_5)
        _METRICS["articles_scraped"] = len(articles_with_content)
        
        print(f"Scraped {len(articles_with_content)}/{len(first_5)} articles")
        for a in articles_with_content:
            fl = len(a.get("full_text", ""))
            print(f"  {a.get('title', '')[:60]:60s} text={fl}")
        
        # Stage 3: Trace AI extraction for each
        print(f"\n{'='*70}")
        print("STAGE 3: AI EXTRACTION TRACE")
        print(f"{'='*70}")
        
        agent = NewsIntelligenceAgent()
        traces = []
        for article in articles_with_content:
            trace = await trace_article(agent, article)
            traces.append(trace)
    finally:
        scraper.close()
    
    # Print aggregate statistics
    print(f"\n{'='*70}")
    print("AGGREGATE STATISTICS")
    print(f"{'='*70}")
    for key, val in _METRICS.items():
        print(f"  {key}: {val}")
    
    # Identify first stage where count drops to zero
    print(f"\n{'='*70}")
    print("ROOT CAUSE ANALYSIS")
    print(f"{'='*70}")
    
    if _METRICS["articles_fetched"] > 0 and _METRICS["articles_scraped"] == 0:
        print("FAILURE STAGE: Content scraping (Stage 2)")
        print("All articles failed content scraping")
    elif _METRICS["articles_scraped"] > 0 and _METRICS["ai_requests_sent"] == 0:
        print("FAILURE STAGE: AI extraction (Stage 3)")
        print("No AI requests were sent - all articles had < 50 chars")
    elif _METRICS["ai_requests_sent"] > 0 and _METRICS["ai_failures"] == _METRICS["ai_requests_sent"]:
        print("FAILURE STAGE: AI provider (Stage 3)")
        print("All AI requests failed")
    else:
        print("Need full AI trace to determine exact failure point")
    
    print(f"\n{'='*70}")
    print("CONCLUSION")
    print(f"{'='*70}")
    print(f"Pipeline fetches {_METRICS['articles_fetched']} articles successfully.")
    print(f"Without a configured OpenRouter API key, the AI provider is UNAVAILABLE.")
    print(f"OpenRouterProvider.generate() returns '' because not self._available.")
    print(f"NewsIntelligenceAgent then falls back to mock mode.")
    print(f"In production with an API key, if incidents_extracted=0 for 50 articles:")
    print(f"  → The AI is either returning empty responses, or JSON parsing fails for all responses.")

if __name__ == "__main__":
    asyncio.run(main())
