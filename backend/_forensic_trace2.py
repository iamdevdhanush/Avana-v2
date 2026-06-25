"""
Forensic Trace v2: News Intelligence Pipeline
Traces every stage from RSS -> AI -> Parser -> Validator -> Database
Uses ASCII-only output for Windows terminal compatibility.
"""
import asyncio, sys, json, logging, time, os, io
sys.path.insert(0, '.')
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
os.environ["MOCK_INTELLIGENCE_MODE"] = "false"

from app.services.news_scraper import NewsScraper
from app.agents.news_intelligence import NewsIntelligenceAgent, _INCIDENT_TYPES
from app.pipeline.women_safety import WOMEN_SAFETY_CATEGORIES
from app.services.ai.factory import get_ai_provider
from app.database import get_session_factory
from sqlalchemy import text

_METRICS = {
    "articles_fetched": 0, "articles_scraped": 0,
    "ai_requests_sent": 0, "ai_attempts": 0,
    "ai_failures": 0, "ai_empty_responses": 0,
    "json_parse_failures": 0, "validation_failures": 0,
    "duplicate_incidents": 0, "db_insert_attempts": 0,
    "db_insert_failures": 0, "incidents_saved": 0,
    "short_content_rejected": 0, "articles_no_incidents": 0,
}

async def full_trace():
    print("=" * 70)
    print("FORENSIC TRACE: News Intelligence Pipeline")
    print("=" * 70)

    # ---- STAGE 1: RSS FEED FETCH ----
    print()
    print("=" * 70)
    print("STAGE 1: RSS FEED FETCH")
    print("=" * 70)
    
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
        
        _MAX = 5
        batch = unique[:_MAX]
        _METRICS["articles_fetched"] = len(batch)
        
        print(f"Raw RSS entries: {len(all_raw)}")
        print(f"Unique articles: {len(unique)}")
        print(f"Tracing first {len(batch)} articles:")
        
        for i, a in enumerate(batch, 1):
            print(f"  [{i}] {a.get('title', '')[:70]}")
            print(f"       City={a.get('city','')} Link={a.get('link','')[:60]}...")

        # ---- STAGE 2: CONTENT SCRAPING ----
        print()
        print("=" * 70)
        print("STAGE 2: CONTENT SCRAPING")
        print("=" * 70)
        
        articles = NewsIntelligenceAgent._fetch_content_parallel(scraper, batch)
        _METRICS["articles_scraped"] = len(articles)
        
        print(f"Scraped: {len(articles)}/{len(batch)}")
        for a in articles:
            fl = len(a.get("full_text", ""))
            sl = len(a.get("summary", ""))
            print(f"  title={a.get('title','')[:50]} | full_text={fl} chars | summary={sl} chars")

        # ---- STAGE 3: AI EXTRACTION TRACE ----
        print()
        print("=" * 70)
        print("STAGE 3: AI EXTRACTION (per-article trace)")
        print("=" * 70)
        
        if not articles:
            print("NO ARTICLES to process after scraping")
            return _METRICS
        
        ai_provider = get_ai_provider()
        ai_avail = ai_provider.is_available()
        print(f"AI Provider: {ai_provider.name} | Available: {ai_avail}")
        
        for idx, article in enumerate(articles, 1):
            print()
            print("-" * 70)
            print(f"ARTICLE #{idx}: {article.get('title', '')[:70]}")
            print("-" * 70)
            
            text_content = article.get("full_text", "")
            print(f"  City: {article.get('city', '')}")
            print(f"  Text length: {len(text_content)} chars")
            print(f"  Text preview: {text_content[:200]}...")
            
            # ---- Sub-stage 3a: Short content check ----
            print(f"  [CHECK] full_text < 50 chars? {len(text_content) < 50}")
            if not text_content or len(text_content) < 50:
                print(f"  >> REJECTED at news_intelligence.py:356-357")
                print(f"  >> Condition: not text_content or len(text_content) < 50")
                print(f"  >> Result: return [] (empty list)")
                _METRICS["short_content_rejected"] += 1
                continue
            
            # ---- Sub-stage 3b: Build prompt ----
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
            
            print(f"  [BUILD] Prompt ({len(prompt)} chars)")
            print(f"  [BUILD] System instruction set")
            
            # ---- Sub-stage 3c: AI call ----
            _METRICS["ai_attempts"] += 1
            
            if not ai_avail:
                print(f"  >> AI UNAVAILABLE - OpenRouterProvider.generate() returns ''")
                print(f"  >> File: app/services/ai/openrouter_provider.py:80-82")
                print(f"  >> Condition: not self._available -> return \"\"")
                print(f"  >> Then: _extract_incidents() checks 'if not response: return []'")
                print(f"  >> Result: [] (empty list)")
                _METRICS["ai_failures"] += 1
                _METRICS["ai_empty_responses"] += 1
                continue
            
            _METRICS["ai_requests_sent"] += 1
            
            # If AI is available, make the actual call
            try:
                response = await ai_provider.generate(prompt, system_instruction=system)
                if not response:
                    print(f"  >> AI returned EMPTY response")
                    print(f"  >> Condition: if not response: return [] (news_intelligence.py:391-392)")
                    _METRICS["ai_empty_responses"] += 1
                    continue
                
                print(f"  [AI] Raw response ({len(response)} chars):")
                print(f"  {response[:500]}")
                _METRICS["ai_empty_responses"] += 0  # not empty
                
                # ---- Sub-stage 3d: JSON parsing ----
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
                    
                    print(f"  [PARSE] Parsed JSON: {json.dumps(incidents, indent=2)[:500]}")
                    
                    if not incidents:
                        print(f"  >> AI returned [] - no women's safety incidents found")
                        print(f"  >> This is a VALID response, not a failure")
                        _METRICS["articles_no_incidents"] += 1
                        continue
                    
                    # Add metadata
                    for inc in incidents:
                        inc["source_url"] = article.get("link", "")
                        inc["source_city"] = article.get("city", "")
                        inc["article_title"] = article.get("title", "")
                        inc["source_credibility"] = 0.6
                        inc["language"] = source_language
                        ai_conf = float(inc.get("confidence", 0.7))
                        inc["confidence"] = round(min(1.0, ai_conf * (0.5 + 0.5 * 0.6)), 2)
                    
                    print(f"  [EXTRACTED] {len(incidents)} incident(s)")
                    for i, inc in enumerate(incidents):
                        print(f"    [{i+1}] type={inc.get('incident_type','?')} sev={inc.get('severity','?')} loc={inc.get('location','?')} dist={inc.get('district','?')} ws={inc.get('women_safety_category','?')}")
                    
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"  >> JSON PARSE FAILED: {e}")
                    print(f"  >> File: app/agents/news_intelligence.py:420-422")
                    print(f"  >> Condition: json.JSONDecodeError on cleaned text")
                    print(f"  >> Cleaned text: {cleaned[:200]}")
                    _METRICS["json_parse_failures"] += 1
                    continue
                    
            except Exception as e:
                print(f"  >> AI call EXCEPTION: {e}")
                _METRICS["ai_failures"] += 1
    
    finally:
        scraper.close()
    
    # ---- AGGREGATE STATISTICS ----
    print()
    print("=" * 70)
    print("AGGREGATE STATISTICS")
    print("=" * 70)
    for key, val in _METRICS.items():
        print(f"  {key}: {val}")
    
    # ---- IDENTIFY FAILURE STAGE ----
    print()
    print("=" * 70)
    print("FAILURE STAGE IDENTIFICATION")
    print("=" * 70)
    
    failure_chain = []
    if _METRICS["articles_fetched"] == 0:
        failure_chain.append("STAGE 1: RSS Feed Fetch - NO articles fetched")
    elif _METRICS["articles_scraped"] == 0:
        failure_chain.append("STAGE 2: Content Scraping - All articles failed to scrape")
    
    if _METRICS["articles_scraped"] > 0 and _METRICS["short_content_rejected"] == _METRICS["articles_scraped"]:
        failure_chain.append("STAGE 3a: All articles had <50 chars text")
    
    if _METRICS["ai_attempts"] > 0 and _METRICS["ai_failures"] == _METRICS["ai_attempts"]:
        failure_chain.append("STAGE 3c: AI Provider failures - ALL AI calls failed")
    
    if _METRICS["ai_requests_sent"] > 0 and _METRICS["ai_empty_responses"] == _METRICS["ai_requests_sent"]:
        failure_chain.append("STAGE 3c: AI returned empty for ALL articles")
    
    if _METRICS["ai_requests_sent"] > 0 and _METRICS["json_parse_failures"] == _METRICS["ai_requests_sent"]:
        failure_chain.append("STAGE 3d: JSON parsing failed for ALL AI responses")
    
    if _METRICS["articles_no_incidents"] > 0 and all(
        _METRICS[k] == 0 for k in ["json_parse_failures", "ai_empty_responses", "ai_failures"]
    ):
        failure_chain.append("STAGE 3 final: AI returned [] for all articles - no women's safety incidents found")
    
    if failure_chain:
        print("Failure chain:")
        for f in failure_chain:
            print(f"  -> {f}")
        print()
        print("FIRST failure stage:", failure_chain[0])
    else:
        print("No failure detected in the traced portion")
    
    print()
    print("=" * 70)
    print("PRODUCTION DATA ANALYSIS")
    print("=" * 70)
    
    fd = get_session_factory()
    async with fd() as s:
        r = await s.execute(text("""
            SELECT summary->>'incidents_extracted' as extracted,
                   summary->>'incidents_saved' as saved,
                   summary->>'articles_fetched' as fetched
            FROM pipeline_runs
            WHERE pipeline_type='news'
            ORDER BY completed_at DESC
            LIMIT 5
        """))
        for row in r:
            print(f"  Pipeline run: articles={row[0]} extracted={row[1]} saved={row[2]}")
    
    print()
    _METRICS["summary"] = "AI extraction returns 0 incidents for all articles"
    return _METRICS


if __name__ == "__main__":
    asyncio.run(full_trace())
