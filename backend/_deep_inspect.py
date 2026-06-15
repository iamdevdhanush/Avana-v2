"""Deep schema investigation script"""
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
        # Full safety_reports schema
        print("=== safety_reports FULL columns ===")
        cols = await conn.execute(text(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_name='safety_reports' ORDER BY ordinal_position"
        ))
        for r in cols.fetchall():
            print(f"  {r[0]:35} {r[1]:25} nullable={r[2]}  default={r[3]}")

        print()
        print("=== Does safety_reports have is_duplicate/duplicate_of? ===")
        cols = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='safety_reports' AND column_name IN ('is_duplicate','duplicate_of')"
        ))
        found = cols.fetchall()
        if found:
            for r in found:
                print(f"  FOUND: {r[0]}")
        else:
            print("  NOT FOUND -- safety_reports MISSING is_duplicate/duplicate_of")

        print()
        print("=== reportstatus enum values ===")
        try:
            e = await conn.execute(text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname='reportstatus' ORDER BY e.enumsortorder"
            ))
            for r in e.fetchall():
                print(f"  [{r[0]}]")
        except Exception as ex:
            print(f"  ERROR: {ex}")

        print()
        print("=== Testing pipeline query (status::text = pending) ===")
        try:
            r = await conn.execute(text(
                "SELECT COUNT(*) FROM safety_reports WHERE status::text = 'pending'"
            ))
            print(f"  Rows with pending status: {r.scalar()}")
        except Exception as ex:
            print(f"  ERROR: {ex}")

        print()
        print("=== Testing PostGIS ST_DWithin ===")
        try:
            r = await conn.execute(text(
                "SELECT ST_DWithin("
                "ST_SetSRID(ST_MakePoint(77.0, 13.0),4326)::geography,"
                "ST_SetSRID(ST_MakePoint(77.1, 13.1),4326)::geography,"
                "1000)"
            ))
            print(f"  ST_DWithin works: {r.scalar()}")
        except Exception as ex:
            print(f"  ERROR: {ex}")

        print()
        print("=== incidents.geom nullable? ===")
        r = await conn.execute(text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name='incidents' AND column_name='geom'"
        ))
        row = r.fetchone()
        print(f"  incidents.geom nullable in DB={row[0] if row else 'N/A'} (ORM model says nullable=True)")

        print()
        print("=== Does incidents table have is_duplicate / duplicate_of? ===")
        cols = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='incidents' AND column_name IN ('is_duplicate','duplicate_of')"
        ))
        found = cols.fetchall()
        if found:
            for r in found:
                print(f"  FOUND: {r[0]}")
        else:
            print("  NOT FOUND -- incidents table MISSING is_duplicate/duplicate_of")

        print()
        print("=== risk_scores has location_id? ===")
        cols = await conn.execute(text(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_name='risk_scores' AND column_name='location_id'"
        ))
        row = cols.fetchone()
        if row:
            print(f"  FOUND: location_id nullable={row[1]}")
        else:
            print("  NOT FOUND")

        print()
        print("=== Try actual community pipeline UPDATE query ===")
        try:
            r = await conn.execute(text(
                "EXPLAIN SELECT id, user_id, incident_type, severity, latitude, longitude, "
                "description, confidence_score, created_at "
                "FROM safety_reports WHERE status::text = 'pending' LIMIT 50"
            ))
            print(f"  SELECT works: OK")
        except Exception as ex:
            print(f"  ERROR: {ex}")

        print()
        print("=== Try UPDATE to safety_reports (dry-run EXPLAIN) ===")
        try:
            r = await conn.execute(text(
                "EXPLAIN UPDATE safety_reports SET status='pending', incident_type='theft', "
                "severity='low', confidence_score=0.5, is_duplicate=false, "
                "duplicate_of=NULL, moderated_by=NULL, updated_at=NOW() "
                "WHERE id='00000000-0000-0000-0000-000000000001'::uuid"
            ))
            print("  UPDATE with is_duplicate: OK")
        except Exception as ex:
            print(f"  ERROR (CRITICAL): {ex}")

asyncio.run(main())
