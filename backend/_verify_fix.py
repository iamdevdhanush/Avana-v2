"""Production hotfix verification script.
Run: python _verify_fix.py
Reports exact state of all data sources.
"""
import asyncio
import json
from app.database import get_session_factory
from sqlalchemy import text

async def verify():
    factory = get_session_factory()
    async with factory() as s:
        print("=" * 60)
        print("AVANA PRODUCTION HOTFIX — VERIFICATION REPORT")
        print("=" * 60)

        # 1. incident counts
        r = await s.execute(text("SELECT COUNT(*) FROM incidents"))
        inc_total = r.scalar() or 0
        print(f"\n== incidents count:              {inc_total}")

        r = await s.execute(text("SELECT COUNT(*) FROM incidents WHERE created_at >= NOW() - INTERVAL '30 days'"))
        inc_30d = r.scalar() or 0
        print(f"== incidents (last 30d):         {inc_30d}")

        r = await s.execute(text("SELECT COUNT(*) FILTER (WHERE district IS NOT NULL) FROM incidents"))
        inc_with_district = r.scalar() or 0
        print(f"== incidents with district:      {inc_with_district}")

        r = await s.execute(text("SELECT COUNT(*) FROM incidents WHERE UPPER(status::text) = 'VERIFIED'"))
        inc_verified = r.scalar() or 0
        print(f"== incidents verified:           {inc_verified}")

        # 2. risk_scores
        r = await s.execute(text("SELECT COUNT(*) FROM risk_scores"))
        rs_total = r.scalar() or 0
        print(f"\n== risk_scores count:            {rs_total}")

        r = await s.execute(text("SELECT COUNT(*) FROM risk_scores WHERE calculated_at >= NOW() - INTERVAL '48 hours'"))
        rs_recent = r.scalar() or 0
        print(f"== risk_scores (< 48h old):      {rs_recent}")

        r = await s.execute(text("SELECT MIN(calculated_at) as min_ts, MAX(calculated_at) as max_ts FROM risk_scores"))
        row = r.fetchone()
        print(f"== risk_scores age range:        {row.min_ts} to {row.max_ts}")

        # 3. Sample bounds check (Shivamogga area)
        r = await s.execute(text("""
            SELECT COUNT(*) FROM risk_scores
            WHERE latitude BETWEEN 13.5 AND 14.5
              AND longitude BETWEEN 75.0 AND 76.0
        """))
        shiv_bounds = r.scalar() or 0
        print(f"\n== risk_scores in Shivamogga bounds (13.5-14.5, 75-76): {shiv_bounds}")

        r = await s.execute(text("""
            SELECT COUNT(*) FROM risk_scores
            WHERE latitude BETWEEN 13.5 AND 14.5
              AND longitude BETWEEN 75.0 AND 76.0
              AND calculated_at >= NOW() - INTERVAL '48 hours'
        """))
        shiv_recent = r.scalar() or 0
        print(f"== risk_scores Shivamogga bounds + < 48h: {shiv_recent}")

        # 4. Sample bounds — Karnataka wide
        r = await s.execute(text("""
            SELECT COUNT(*) FROM risk_scores
            WHERE latitude BETWEEN 11.5 AND 18.0
              AND longitude BETWEEN 74.0 AND 78.5
        """))
        kar_bounds = r.scalar() or 0
        print(f"\n== risk_scores in Karnataka bounds (11.5-18, 74-78.5): {kar_bounds}")

        r = await s.execute(text("""
            SELECT COUNT(*) FROM risk_scores
            WHERE latitude BETWEEN 11.5 AND 18.0
              AND longitude BETWEEN 74.0 AND 78.5
              AND calculated_at >= NOW() - INTERVAL '48 hours'
        """))
        kar_recent = r.scalar() or 0
        print(f"== risk_scores Karnataka bounds + < 48h: {kar_recent}")

        # 5. Table list
        r = await s.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
        """))
        tables = [row[0] for row in r.fetchall()]
        print(f"\n== Tables ({len(tables)}): {', '.join(tables)}")

        # 6. Check for location_id column in risk_scores
        r = await s.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'risk_scores' ORDER BY ordinal_position
        """))
        cols = [row[0] for row in r.fetchall()]
        print(f"\n== risk_scores columns: {', '.join(cols)}")
        has_location_id = 'location_id' in cols
        print(f"== Has location_id column: {has_location_id}")

        # 7. Severity distribution
        r = await s.execute(text("""
            SELECT severity::text, COUNT(*)
            FROM incidents GROUP BY severity ORDER BY severity
        """))
        print(f"\n== Severity distribution:")
        for row in r:
            print(f"   {str(row[0]):12s}: {row[1]}")

        # 8. District distribution (top 10)
        r = await s.execute(text("""
            SELECT COALESCE(district, '(null)') as d, COUNT(*) as cnt
            FROM incidents GROUP BY district ORDER BY cnt DESC LIMIT 10
        """))
        print(f"\n== Top districts:")
        for row in r:
            print(f"   {str(row[0]):20s}: {row[1]}")

        # 9. Check heatmap_points table existence
        has_heatmap_points = 'heatmap_points' in tables
        print(f"\n== heatmap_points table exists: {has_heatmap_points}")

        # 10. Simulate /admin/dashboard query
        r = await s.execute(text("SELECT COUNT(*) FROM incidents"))
        print(f"\n== Simulated /admin/dashboard total_incidents: {r.scalar()}")

        r = await s.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true"))
        print(f"== Simulated /admin/dashboard active_users: {r.scalar()}")

        r = await s.execute(text("SELECT COUNT(*) FROM sos_events"))
        print(f"== Simulated /admin/dashboard sos_events: {r.scalar()}")

        r = await s.execute(text("SELECT COUNT(*) FROM incidents WHERE UPPER(status::text) = 'VERIFIED'"))
        print(f"== Simulated /admin/dashboard verified_reports: {r.scalar()}")

        # 11. Simulate /analytics/trends
        r = await s.execute(text("""
            SELECT COUNT(*) FROM incidents
            WHERE created_at >= NOW() - INTERVAL '30 days'
        """))
        print(f"\n== Simulated /analytics/trends (30d): {r.scalar()} incidents in period")

        # 12. Health check: enum values
        r = await s.execute(text("""
            SELECT t.typname, e.enumlabel
            FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname IN ('incidenttype', 'severity', 'incidentstatus')
            ORDER BY t.typname, e.enumsortorder
        """))
        print(f"\n== Enum values:")
        for row in r:
            print(f"   {row.typname}.{row.enumlabel}")

        # 13. Check severity::text comparison directly
        print(f"\n== Case comparison check (UPPER vs actual):")
        r = await s.execute(text("""
            SELECT DISTINCT severity::text as sv,
                   UPPER(severity::text) as upper_sv,
                   UPPER(severity::text) IN ('HIGH','CRITICAL') as matches_high_critical
            FROM incidents
        """))
        for row in r:
            print(f"   severity='{row.sv}' -> UPPER='{row.upper_sv}' -> IN ('HIGH','CRITICAL') = {row.matches_high_critical}")

        print("\n" + "=" * 60)
        print("VERIFICATION COMPLETE")
        print("=" * 60)

asyncio.run(verify())
