"""
Schema inspection script — run from backend/ directory
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from app.config import settings


async def inspect():
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    url = settings.build_database_url()
    print(f'Connecting to: {url[:50]}...')
    engine = create_async_engine(url, echo=False)

    async with engine.connect() as conn:
        # Get all tables
        tables = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
        )
        rows = tables.fetchall()
        print('\n=== PUBLIC TABLES ===')
        for r in rows:
            print(f'  {r[0]}')

        # Check safety_reports columns
        print('\n=== safety_reports columns ===')
        cols = await conn.execute(
            text("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name='safety_reports' ORDER BY ordinal_position")
        )
        for r in cols.fetchall():
            print(f'  {r[0]:35} {r[1]:25} nullable={r[2]}  default={r[3]}')

        # Check incidents columns
        print('\n=== incidents columns ===')
        cols = await conn.execute(
            text("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name='incidents' ORDER BY ordinal_position")
        )
        for r in cols.fetchall():
            print(f'  {r[0]:35} {r[1]:25} nullable={r[2]}  default={r[3]}')

        # Check risk_scores columns
        print('\n=== risk_scores columns ===')
        cols = await conn.execute(
            text("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name='risk_scores' ORDER BY ordinal_position")
        )
        for r in cols.fetchall():
            print(f'  {r[0]:35} {r[1]:25} nullable={r[2]}  default={r[3]}')

        # Check locations columns
        print('\n=== locations columns ===')
        cols = await conn.execute(
            text("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name='locations' ORDER BY ordinal_position")
        )
        for r in cols.fetchall():
            print(f'  {r[0]:35} {r[1]:25} nullable={r[2]}  default={r[3]}')

        # Check geocoding_cache
        print('\n=== geocoding_cache columns ===')
        cols = await conn.execute(
            text("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name='geocoding_cache' ORDER BY ordinal_position")
        )
        for r in cols.fetchall():
            print(f'  {r[0]:35} {r[1]:25} nullable={r[2]}  default={r[3]}')

        # Check enum types
        print('\n=== ENUM TYPES ===')
        enums = await conn.execute(
            text("SELECT t.typname, e.enumlabel FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid ORDER BY t.typname, e.enumsortorder")
        )
        current_type = None
        for r in enums.fetchall():
            if r[0] != current_type:
                current_type = r[0]
                print(f'  [{r[0]}]')
            print(f'    {r[1]}')

        # Check alembic version
        print('\n=== ALEMBIC VERSION ===')
        try:
            ver = await conn.execute(text("SELECT version_num FROM alembic_version"))
            for r in ver.fetchall():
                print(f'  current: {r[0]}')
        except Exception as e:
            print(f'  ERROR: {e}')

        # Quick count of safety_reports
        print('\n=== ROW COUNTS ===')
        for tbl in ['safety_reports', 'incidents', 'risk_scores', 'locations']:
            try:
                cnt = await conn.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                print(f'  {tbl}: {cnt.scalar()} rows')
            except Exception as e:
                print(f'  {tbl}: ERROR - {e}')

        # Show sample safety_reports pending
        print('\n=== PENDING SAFETY REPORTS (sample) ===')
        try:
            rows = await conn.execute(text("SELECT id, incident_type, severity, status, latitude, longitude FROM safety_reports WHERE status::text='pending' LIMIT 5"))
            for r in rows.fetchall():
                print(f'  {r}')
            if not rows.rowcount:
                print('  (no pending reports - pipeline will return early with no work)')
        except Exception as e:
            print(f'  ERROR: {e}')

asyncio.run(inspect())
