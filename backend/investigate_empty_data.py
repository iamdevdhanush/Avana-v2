"""Investigate why UI shows empty data despite records existing."""
import asyncio
from datetime import datetime, timezone, timedelta
from app.database import get_session_factory
from sqlalchemy import text

async def q():
    factory = get_session_factory()
    async with factory() as s:
        # 1. Total counts
        print("=== COUNTS ===")
        for tbl in ("incidents", "risk_scores"):
            r = await s.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
            print(f"  {tbl}: {r.scalar()}")

        # 2. Heatmap endpoint returns risk_scores — check recent ones
        print("\n=== RISK SCORES (recent 5) ===")
        r = await s.execute(text("""
            SELECT id, latitude, longitude, score, category, calculated_at
            FROM risk_scores
            ORDER BY calculated_at DESC
            LIMIT 5
        """))
        for row in r:
            print(f"  id={str(row.id)[:8]} lat={row.latitude:.4f} lng={row.longitude:.4f} score={row.score} cat={row.category} at={row.calculated_at}")

        # 3. Check district names in incidents
        print("\n=== INCIDENTS: district/city/severity distribution ===")
        r = await s.execute(text("""
            SELECT
                COALESCE(district, '(NULL)') as district,
                COALESCE(city, '(NULL)') as city,
                severity,
                COUNT(*) as cnt
            FROM incidents
            GROUP BY district, city, severity
            ORDER BY cnt DESC
        """))
        for row in r:
            print(f"  district={row.district:20s} city={row.city:20s} severity={row.severity:10s} count={row.cnt}")

        # 4. Check timestamps — analytics queries typically filter by last 30 days
        print("\n=== INCIDENT TIMESTAMPS ===")
        r = await s.execute(text("""
            SELECT
                MIN(created_at) as min_ts,
                MAX(created_at) as max_ts,
                MIN(incident_date) as min_date,
                MAX(incident_date) as max_date
            FROM incidents
        """))
        row = r.fetchone()
        print(f"  created_at range: {row.min_ts} to {row.max_ts}")
        print(f"  incident_date range: {row.min_date} to {row.max_date}")

        # 5. Check how many incidents have NULL districts
        print("\n=== NULL CHECKS ===")
        r = await s.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE district IS NULL) as null_district,
                COUNT(*) FILTER (WHERE city IS NULL) as null_city,
                COUNT(*) FILTER (WHERE latitude IS NULL) as null_lat,
                COUNT(*) FILTER (WHERE longitude IS NULL) as null_lng,
                COUNT(*) FILTER (WHERE severity IS NULL) as null_severity,
                COUNT(*) FILTER (WHERE incident_type IS NULL) as null_type,
                COUNT(*) FILTER (WHERE incident_date IS NULL) as null_date
            FROM incidents
        """))
        row = r.fetchone()
        print(f"  null_district={row.null_district} null_city={row.null_city} null_lat={row.null_lat}")
        print(f"  null_lng={row.null_lng} null_severity={row.null_severity}")
        print(f"  null_type={row.null_type} null_date={row.null_date}")

        # 6. Check if risk_scores have valid lat/lng
        print("\n=== RISK SCORE VALIDITY ===")
        r = await s.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE latitude IS NULL OR longitude IS NULL) as null_coords,
                COUNT(*) FILTER (WHERE score IS NULL) as null_score,
                COUNT(*) FILTER (WHERE category IS NULL) as null_category,
                COUNT(*) FILTER (WHERE latitude < -90 OR latitude > 90) as bad_lat,
                COUNT(*) FILTER (WHERE longitude < -180 OR longitude > 180) as bad_lng,
                MIN(score) as min_score,
                MAX(score) as max_score
            FROM risk_scores
        """))
        row = r.fetchone()
        print(f"  null_coords={row.null_coords} null_score={row.null_score} null_category={row.null_category}")
        print(f"  bad_lat={row.bad_lat} bad_lng={row.bad_lng}")
        print(f"  score range: {row.min_score} to {row.max_score}")

asyncio.run(q())
