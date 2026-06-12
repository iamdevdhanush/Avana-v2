"""Investigate why UI shows empty — check severity casing and endpoint queries."""
import asyncio
from datetime import datetime, timezone, timedelta
from app.database import get_session_factory
from sqlalchemy import text

async def q():
    factory = get_session_factory()
    async with factory() as s:
        # Check severity values actual stored values
        print("=== SEVERITY VALUES IN DB ===")
        r = await s.execute(text("""
            SELECT severity, COUNT(*),
                   severity::text as sev_text,
                   severity::text = 'high' as eq_lower_high,
                   severity::text = 'HIGH' as eq_upper_high,
                   severity::text = 'critical' as eq_lower_critical,
                   severity::text = 'CRITICAL' as eq_upper_critical,
                   severity::text IN ('high','critical') as in_lower,
                   severity::text IN ('HIGH','CRITICAL') as in_upper
            FROM incidents
            GROUP BY severity
        """))
        for row in r:
            print(f"  severity={str(row.severity):15s} count={row.count}")
            print(f"    ::text='{row.sev_text}'")
            print(f"    ='high': {row.eq_lower_high}  ='HIGH': {row.eq_upper_high}")
            print(f"    ='critical': {row.eq_lower_critical}  ='CRITICAL': {row.eq_upper_critical}")
            print(f"    IN ('high','critical'): {row.in_lower}")
            print(f"    IN ('HIGH','CRITICAL'): {row.in_upper}")

        # Same for incident_type
        print("\n=== INCIDENT_TYPE VALUES IN DB ===")
        r = await s.execute(text("""
            SELECT incident_type, COUNT(*),
                   incident_type::text = 'murder' as eq_lower,
                   incident_type::text = 'MURDER' as eq_upper
            FROM incidents
            GROUP BY incident_type
        """))
        for row in r:
            print(f"  type={str(row.incident_type):20s} count={row.count}  ='murder': {row.eq_lower}  ='MURDER': {row.eq_upper}")

        # Simulate the dashboard high_risk FILTER query
        print("\n=== SIMULATE DASHBOARD HIGH_RISK FILTER ===")
        for sev_filter in [['high','critical'], ['HIGH','CRITICAL'], ['High','Critical']]:
            r = await s.execute(
                text(f"""
                    SELECT COUNT(*) FILTER (WHERE severity::text IN {tuple(sev_filter)}) as high_risk
                    FROM incidents
                """)
            )
            row = r.fetchone()
            print(f"  severity::text IN {sev_filter}: high_risk={row.high_risk}")

        # Simulate heatmap query
        print("\n=== SIMULATE HEATMAP QUERY ===")
        # Typical Bengaluru bounds
        bounds = {"sw_lat": 12.8, "sw_lng": 77.3, "ne_lat": 13.1, "ne_lng": 77.8}
        r = await s.execute(
            text("""
                SELECT COUNT(*) as cnt
                FROM risk_scores
                WHERE latitude BETWEEN :sw_lat AND :ne_lat
                  AND longitude BETWEEN :sw_lng AND :ne_lng
                  AND calculated_at >= NOW() - INTERVAL '48 hours'
            """),
            bounds,
        )
        print(f"  Bengaluru bounds (12.8-13.1, 77.3-77.8): {r.scalar()} points")

        # Shivamogga bounds
        bounds2 = {"sw_lat": 13.5, "sw_lng": 74.5, "ne_lat": 14.5, "ne_lng": 76.0}
        r = await s.execute(
            text("""
                SELECT COUNT(*) as cnt
                FROM risk_scores
                WHERE latitude BETWEEN :sw_lat AND :ne_lat
                  AND longitude BETWEEN :sw_lng AND :ne_lng
                  AND calculated_at >= NOW() - INTERVAL '48 hours'
            """),
            bounds2,
        )
        print(f"  Shivamogga bounds (13.5-14.5, 74.5-76.0): {r.scalar()} points")

        # Total risk_scores
        r = await s.execute(text("SELECT COUNT(*) FROM risk_scores"))
        print(f"\n  Total risk_scores in DB: {r.scalar()}")

        # Check the enum definition
        print("\n=== ENUM DEFINITIONS ===")
        r = await s.execute(text("""
            SELECT t.typname, e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON t.oid = e.enumtypid
            WHERE t.typname IN ('severity', 'riskcategory', 'incidenttype')
            ORDER BY t.typname, e.enumsortorder
        """))
        for row in r:
            print(f"  enum {row.typname}: {row.enumlabel}")

asyncio.run(q())
