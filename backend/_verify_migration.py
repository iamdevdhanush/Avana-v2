"""Post-migration verification"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv; load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def verify():
    engine = create_async_engine(settings.build_database_url(), echo=False)
    async with engine.connect() as conn:
        ver = await conn.execute(text("SELECT version_num FROM alembic_version"))
        print("Alembic version:", ver.scalar())

        cols = await conn.execute(text(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name='safety_reports' AND column_name IN ('is_duplicate','duplicate_of')"
        ))
        rows = cols.fetchall()
        print("safety_reports new columns:")
        for r in rows:
            print(f"  {r[0]:20} {r[1]:15} nullable={r[2]}")
        if not rows:
            print("  MISSING! Migration may have failed.")

        # Verify the UPDATE syntax works with new schema
        try:
            await conn.execute(text(
                "EXPLAIN UPDATE safety_reports "
                "SET status='PENDING'::reportstatus, confidence_score=0.5, "
                "is_duplicate=false, duplicate_of=NULL, "
                "moderated_by=NULL, updated_at=NOW() "
                "WHERE id='00000000-0000-0000-0000-000000000001'::uuid"
            ))
            print("UPDATE with is_duplicate/duplicate_of: OK")
        except Exception as ex:
            print(f"UPDATE ERROR: {ex}")

        # Verify the new community pipeline SELECT query works
        try:
            r = await conn.execute(text(
                "SELECT COUNT(*) FROM safety_reports WHERE status = 'PENDING'"
            ))
            print(f"SELECT WHERE status = 'PENDING': {r.scalar()} rows")
        except Exception as ex:
            print(f"SELECT ERROR: {ex}")

asyncio.run(verify())
