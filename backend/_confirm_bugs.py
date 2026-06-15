"""Confirm all community pipeline failure points"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
from app.config import settings
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def main():
    url = settings.build_database_url()
    engine = create_async_engine(url, echo=False)
    async with engine.connect() as conn:

        print("=== [BUG 1] reportstatus ENUM case mismatch ===")
        print("DB has: PENDING, APPROVED, REJECTED (uppercase)")
        print("Pipeline uses: status::text = 'pending' (lowercase) -> might work with cast")
        print("Pipeline UPDATE uses: status = 'pending' -> FAILS, enum expects 'PENDING'")
        try:
            r = await conn.execute(text(
                "SELECT COUNT(*) FROM safety_reports WHERE status = 'PENDING'"
            ))
            print(f"  status = 'PENDING' (uppercase): {r.scalar()} rows")
        except Exception as ex:
            print(f"  ERROR: {ex}")

        try:
            r = await conn.execute(text(
                "SELECT COUNT(*) FROM safety_reports WHERE status::text = 'pending'"
            ))
            print(f"  status::text = 'pending' (lowercase cast): {r.scalar()} rows")
        except Exception as ex:
            print(f"  ERROR: {ex}")

        print()
        print("=== [BUG 2] safety_reports MISSING is_duplicate / duplicate_of columns ===")
        print("Pipeline UPDATE uses: is_duplicate=:is_dup, duplicate_of=:dup_of")
        print("These columns DO NOT EXIST in the DB -> UPDATE will fail at runtime")
        try:
            r = await conn.execute(text(
                "EXPLAIN UPDATE safety_reports SET status='PENDING', "
                "incident_type='theft', severity='low', confidence_score=0.5, "
                "is_duplicate=false, duplicate_of=NULL, moderated_by=NULL, updated_at=NOW() "
                "WHERE id='00000000-0000-0000-0000-000000000001'::uuid"
            ))
            print("  UPDATE: OK (columns exist)")
        except Exception as ex:
            print(f"  ERROR: {ex}")

        print()
        print("=== [BUG 3] incidents.geom NOT NULL in DB but nullable=True in model ===")
        print("Pipeline does: Incident(geom=WKTElement(...)) -> geom is set -> OK")
        print("But if geom is NOT set for any reason, INSERT will fail on NOT NULL constraint")
        r = await conn.execute(text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name='incidents' AND column_name='geom'"
        ))
        row = r.fetchone()
        print(f"  DB: incidents.geom nullable={row[0] if row else 'N/A'}")
        print("  ORM model: nullable=True -> MISMATCH (model wrong)")

        print()
        print("=== [BUG 4] ReportStatus enum mismatch between model and DB ===")
        print("Model SafetyReport.status uses: ReportStatus.PENDING = 'pending' (lowercase)")
        print("DB enum reportstatus has: PENDING, APPROVED, REJECTED (UPPERCASE)")
        print("Pipeline query: WHERE status::text = 'pending' -> works (casting)")
        print("Pipeline UPDATE: SET status = :status where status='pending' -> FAILS")
        print()
        print("=== [BUG 5] risk_scores UniqueConstraint vs pipeline INSERT ===")
        print("risk_scores has UniqueConstraint on (latitude, longitude)")
        print("But the pipeline uses plain INSERT (not UPSERT) with gen_random_uuid() id")
        print("If the same lat/lng is run twice -> UNIQUE VIOLATION on 2nd run")
        try:
            r = await conn.execute(text(
                "SELECT constraint_name, constraint_type FROM information_schema.table_constraints "
                "WHERE table_name='risk_scores'"
            ))
            for row in r.fetchall():
                print(f"  {row[0]}: {row[1]}")
        except Exception as ex:
            print(f"  ERROR: {ex}")

asyncio.run(main())
