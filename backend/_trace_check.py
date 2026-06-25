"""Check DB state"""
import asyncio, sys
sys.path.insert(0, '.')
from app.database import get_session_factory
from sqlalchemy import text

async def q():
    factory = get_session_factory()
    async with factory() as s:
        r = await s.execute(text("SELECT COUNT(*) FROM incidents"))
        print(f"Total incidents: {r.scalar()}")
        r = await s.execute(text("SELECT COUNT(*) FROM incidents WHERE source='NEWS'"))
        print(f"News incidents: {r.scalar()}")
        r = await s.execute(text("SELECT COUNT(*) FROM incidents WHERE source='NEWS' AND status='PENDING'"))
        print(f"Pending news incidents: {r.scalar()}")
        r = await s.execute(text("SELECT COUNT(*) FROM news_articles"))
        print(f"News articles table: {r.scalar()}")
        r = await s.execute(text("SELECT COUNT(*) FROM pipeline_runs ORDER BY created_at DESC"))
        print(f"Pipeline runs: {r.scalar()}")
        r = await s.execute(text("""
            SELECT summary->>'articles_fetched' as articles,
                   summary->>'incidents_extracted' as extracted,
                   summary->>'incidents_saved' as saved
            FROM pipeline_runs ORDER BY created_at DESC LIMIT 5
        """))
        for row in r:
            print(f"  Articles={row[0]} Extracted={row[1]} Saved={row[2]}")

asyncio.run(q())
