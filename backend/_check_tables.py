import asyncio
from app.database import get_session_factory
from sqlalchemy import text

async def check():
    async with get_session_factory()() as s:
        r = await s.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        for t in r:
            print(t[0])

asyncio.run(check())
