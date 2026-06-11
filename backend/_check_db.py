import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    url = os.environ.get('DATABASE_URL', '')
    print(f'DB URL: {url[:url.index("@")+1]}***@{url.split("@")[1].split(":")[0]}:****@{url.split("@")[1]}')
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        rows = await conn.execute(text('SELECT current_database(), inet_server_addr(), inet_server_port()'))
        r = rows.fetchone()
        print(f'Connected to DB: {r[0]} at {r[1]}:{r[2]}')
        try:
            rows = await conn.execute(text('SELECT email FROM users'))
            print('Existing users:')
            for row in rows:
                print(f'  - {row[0]}')
        except Exception as e:
            print(f'users table error: {e}')
        try:
            cnt = await conn.execute(text('SELECT COUNT(*) FROM police_stations'))
            print(f'Police stations: {cnt.scalar()}')
        except Exception as e:
            print(f'police_stations error: {e}')
    await engine.dispose()

asyncio.run(check())
