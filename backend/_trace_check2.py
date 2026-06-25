"""Check pipeline state"""
import asyncio, sys
sys.path.insert(0, '.')
from app.database import get_session_factory
from sqlalchemy import text
from datetime import datetime, timezone, timedelta

async def q():
    factory = get_session_factory()
    async with factory() as s:
        r = await s.execute(text("SELECT COUNT(*) FROM incidents WHERE source='NEWS' AND status='PENDING'"))
        print(f"Pending news incidents: {r.scalar()}")
        
        r = await s.execute(text("SELECT COUNT(*) FROM news_articles"))
        print(f"news_articles: {r.scalar()}")
        
        r = await s.execute(text("SELECT id, pipeline_type, status, summary, completed_at FROM pipeline_runs ORDER BY completed_at DESC NULLS LAST LIMIT 5"))
        for row in r:
            print(f"Run: {str(row[0])[:8]} type={row[1]} status={row[2]} at={row[4]} summary={row[3]}")

        print("\n--- Last 10 news incidents ---")
        r = await s.execute(text("""
            SELECT title, incident_type, severity, latitude, longitude,
                   source_url, created_at, metadata->>'women_safety_category' as wscat
            FROM incidents WHERE source='NEWS'
            ORDER BY created_at DESC LIMIT 10
        """))
        for row in r:
            print(f"  Title: {(row[0] or 'null')[:50]}")
            print(f"    type={row[1]} sev={row[2]} lat={row[3]} lng={row[4]} wscat={row[7]}")
            print(f"    url={row[5]}")

        print("\n--- geocoding_cache count ---")
        r = await s.execute(text("SELECT COUNT(*) FROM geocoding_cache"))
        print(f"  {r.scalar()}")

        print("\n--- Incident type distribution (NEWS) ---")
        r = await s.execute(text("SELECT incident_type, COUNT(*) FROM incidents WHERE source='NEWS' GROUP BY incident_type ORDER BY COUNT(*) DESC"))
        for row in r:
            print(f"  {row[0]}: {row[1]}")

asyncio.run(q())
