import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def go():
    url = "postgresql+asyncpg://avana:nS4I8GMBNjY48VcYMvkffue3Mo0T9qwE@dpg-d8kqc06k1jcs73a922s0-a.oregon-postgres.render.com:5432/avana_v2"
    e = create_async_engine(url)
    async with e.connect() as c:
        r = await c.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        print("Tables in public schema:")
        for row in r:
            print(f"  {row[0]}")
        r = await c.execute(text("SELECT COUNT(*) FROM incidents"))
        print(f"Incidents: {r.scalar()}")
        r = await c.execute(text("SELECT COUNT(*) FROM incidents WHERE status = 'verified'"))
        print(f"Verified: {r.scalar()}")
        r = await c.execute(text("SELECT incident_type, COUNT(*) as cnt FROM incidents GROUP BY incident_type ORDER BY cnt DESC"))
        for row in r:
            print(f"  Type: {row[0]}, Count: {row[1]}")
    await e.dispose()

asyncio.run(go())
