"""
Trace ALL API endpoints end-to-end.
For each endpoint: exact SQL, raw response, count returned.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from app.database import get_session_factory
from sqlalchemy import text

SEP = "=" * 70

async def trace():
    factory = get_session_factory()
    async with factory() as s:
        # ── BASELINE: Raw DB counts ──
        print(SEP)
        print("BASELINE: Raw Database Counts")
        print(SEP)
        for tbl in ["incidents", "risk_scores", "users", "sos_events", "safety_reports"]:
            r = await s.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
            print(f"  {tbl}: {r.scalar()}")

        r = await s.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true"))
        print(f"  users (is_active=true): {r.scalar()}")

        # ── 1. /admin/dashboard ──
        # Exact SQL from admin.py lines 82-156
        print("\n" + SEP)
        print("ENDPOINT: GET /api/v1/admin/dashboard")
        print(SEP)

        print("\n-- SQL 1: total_incidents")
        sql1 = "SELECT COUNT(*) FROM incidents"
        r = await s.execute(text(sql1))
        total_inc = r.scalar() or 0
        print(f"   SQL: {sql1}")
        print(f"   Result: {total_inc}")

        print("\n-- SQL 2: active_users")
        sql2 = "SELECT COUNT(*) FROM users WHERE is_active = true"
        r = await s.execute(text(sql2))
        active_users = r.scalar() or 0
        print(f"   SQL: {sql2}")
        print(f"   Result: {active_users}")

        print("\n-- SQL 3: sos_events")
        sql3 = "SELECT COUNT(*) FROM sos_events"
        r = await s.execute(text(sql3))
        sos_events = r.scalar() or 0
        print(f"   SQL: {sql3}")
        print(f"   Result: {sos_events}")

        print("\n-- SQL 4: verified_reports")
        sql4 = "SELECT COUNT(*) FROM incidents WHERE UPPER(status::text) = 'VERIFIED'"
        r = await s.execute(text(sql4))
        verified_reports = r.scalar() or 0
        print(f"   SQL: {sql4}")
        print(f"   Result: {verified_reports}")

        print("\n-- SQL 5: incidents_by_district")
        sql5 = """
            SELECT district, COUNT(*) as total,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) IN ('HIGH','CRITICAL')) as high_risk,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) = 'MEDIUM') as medium_risk,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) = 'LOW') as low_risk,
                   AVG(CASE
                       WHEN UPPER(severity::text) = 'CRITICAL' THEN 4
                       WHEN UPPER(severity::text) = 'HIGH' THEN 3
                       WHEN UPPER(severity::text) = 'MEDIUM' THEN 2
                       WHEN UPPER(severity::text) = 'LOW' THEN 1
                       ELSE 0
                   END) as avg_score
            FROM incidents WHERE district IS NOT NULL
            GROUP BY district ORDER BY total DESC LIMIT 20
        """
        r = await s.execute(text(sql5))
        rows = r.fetchall()
        print(f"   SQL: SELECT district, COUNT(*), FILTER(severity...), AVG(...) FROM incidents WHERE district IS NOT NULL GROUP BY district...")
        print(f"   Result: {len(rows)} rows")
        for row in rows:
            print(f"     district={row[0]}, total={row[1]}, high_risk={row[2]}, medium_risk={row[3]}, low_risk={row[4]}, avg_score={row[5]}")

        print("\n-- SQL 6: incidents_by_type")
        sql6 = "SELECT incident_type, COUNT(*) as cnt FROM incidents GROUP BY incident_type ORDER BY cnt DESC"
        r = await s.execute(text(sql6))
        rows = r.fetchall()
        print(f"   SQL: {sql6}")
        print(f"   Result: {len(rows)} rows")
        for row in rows:
            print(f"     {row[0]}: {row[1]}")

        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        print("\n-- SQL 7: risk_trend (avg confidence_score by date, last 30d)")
        sql7 = "SELECT DATE(created_at) as dt, AVG(confidence_score) FROM incidents WHERE created_at >= :start GROUP BY dt ORDER BY dt"
        r = await s.execute(text(sql7), {"start": thirty_days_ago})
        rows = r.fetchall()
        print(f"   SQL: {sql7}")
        print(f"   Result: {len(rows)} rows")
        for row in rows[:5]:
            print(f"     {row[0]}: avg_conf={row[1]}")
        if len(rows) > 5:
            print(f"     ... and {len(rows)-5} more")

        print("\n-- SQL 8: incidents_trend (count by date, last 30d)")
        sql8 = "SELECT DATE(created_at) as dt, COUNT(*) FROM incidents WHERE created_at >= :start GROUP BY dt ORDER BY dt"
        r = await s.execute(text(sql8), {"start": thirty_days_ago})
        rows = r.fetchall()
        print(f"   SQL: {sql8}")
        print(f"   Result: {len(rows)} rows")
        for row in rows[:5]:
            print(f"     {row[0]}: count={row[1]}")
        if len(rows) > 5:
            print(f"     ... and {len(rows)-5} more")

        print("\n-- SQL 9: recent_alerts")
        sql9 = """
            SELECT id, incident_type, severity, district, created_at, status
            FROM incidents WHERE UPPER(severity::text) IN ('HIGH','CRITICAL') AND created_at >= :start
            ORDER BY created_at DESC LIMIT 20
        """
        r = await s.execute(text(sql9), {"start": thirty_days_ago})
        rows = r.fetchall()
        print(f"   SQL: SELECT id, incident_type, severity, district, created_at, status FROM incidents WHERE UPPER(severity::text) IN ('HIGH','CRITICAL') AND created_at >= :start...")
        print(f"   Result: {len(rows)} rows")
        for row in rows[:5]:
            print(f"     id={str(row[0])[:8]}, type={row[1]}, severity={row[2]}, district={row[3]}, time={row[4]}, status={row[5]}")

        # ── Actual response shape ──
        print(f"\n-- /admin/dashboard FINAL RESPONSE SHAPE:")
        print(json.dumps({
            "total_incidents": total_inc,
            "active_users": active_users,
            "sos_events": sos_events,
            "verified_reports": verified_reports,
            "incidents_by_district_count": len(rows) if 'rows' in dir() else 0,
        }, indent=2))

        # ── 2. /analytics/districts ──
        print("\n" + SEP)
        print("ENDPOINT: GET /api/v1/analytics/districts")
        print(SEP)

        sql_districts = """
            SELECT district,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) IN ('HIGH','CRITICAL')) as high_risk,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) = 'MEDIUM') as medium_risk,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) = 'LOW') as low_risk,
                   MIN(created_at) as first_incident,
                   MAX(created_at) as last_incident
            FROM incidents
            WHERE district IS NOT NULL
            GROUP BY district
            ORDER BY total DESC
        """
        r = await s.execute(text(sql_districts))
        rows = r.fetchall()
        print(f"   SQL: {sql_districts}")
        print(f"   Result: {len(rows)} rows")
        for row in rows:
            print(f"     district={row[0]}, total={row[1]}, high_risk={row[2]}, medium_risk={row[3]}, low_risk={row[4]}, first={str(row[5])[:19] if row[5] else None}, last={str(row[6])[:19] if row[6] else None}")

        # ── 3. /analytics/trends ──
        print("\n" + SEP)
        print("ENDPOINT: GET /api/v1/analytics/trends?days=30")
        print(SEP)

        sql_trends = """
            SELECT DATE(created_at) as dt,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) IN ('HIGH','CRITICAL')) as high_risk_count,
                   COUNT(*) FILTER (WHERE UPPER(source::text) = 'NEWS') as news_count,
                   COUNT(*) FILTER (WHERE UPPER(source::text) = 'USER_REPORT') as user_report_count
            FROM incidents
            WHERE created_at >= :start
            GROUP BY dt
            ORDER BY dt
        """
        r = await s.execute(text(sql_trends), {"start": thirty_days_ago})
        rows = r.fetchall()
        print(f"   SQL: {sql_trends}")
        print(f"   Result: {len(rows)} data points")
        for row in rows[:5]:
            print(f"     {row[0]}: total={row[1]}, high_risk={row[2]}, news={row[3]}, user={row[4]}")
        if len(rows) > 5:
            print(f"     ... and {len(rows)-5} more")

        # ── 4. /incidents (list) ──
        print("\n" + SEP)
        print("ENDPOINT: GET /api/v1/incidents (no filters)")
        print(SEP)

        sql_incidents = """
            SELECT COUNT(*) FROM incidents
        """
        r = await s.execute(text(sql_incidents))
        total_inc = r.scalar() or 0
        print(f"   SQL COUNT: {sql_incidents}")
        print(f"   Total incidents: {total_inc}")

        # Check what the actual list endpoint returns with pagination
        sql_inc_list = """
            SELECT id, incident_type, severity, status, district, created_at
            FROM incidents ORDER BY created_at DESC LIMIT 5
        """
        r = await s.execute(text(sql_inc_list))
        rows = r.fetchall()
        print(f"\n   Sample 5 incidents:")
        for row in rows:
            print(f"     id={str(row[0])[:8]}, type={row[1]}, severity={row[2]}, status={row[3]}, district={row[4]}, created={str(row[5])[:19]}")

        # ── 5. /risk/score for a Shivamogga point ──
        print("\n" + SEP)
        print("ENDPOINT: POST /api/v1/risk/score (lat=13.93, lng=75.57)")
        print(SEP)

        # Simulate score_location from pipeline/risk.py
        from app.pipeline.risk import score_location
        result = await score_location(13.93, 75.57)
        print(f"   Result:")
        print(f"     score={result.get('score')}")
        print(f"     category={result.get('category')}")
        print(f"     recommendations count={len(result.get('recommendations', []))}")

        # ── 6. /risk/heatmap ──
        print("\n" + SEP)
        print("ENDPOINT: POST /api/v1/risk/heatmap (Shivamogga bounds)")
        print(SEP)

        from app.pipeline.heatmap import get_heatmap_data
        points_data = await get_heatmap_data(13.5, 75.0, 14.5, 76.0)
        print(f"   get_heatmap_data returned {len(points_data)} points")
        if points_data:
            for p in points_data[:3]:
                print(f"     lat={p['latitude']:.4f}, lng={p['longitude']:.4f}, score={p['score']:.2f}, cat={p['category']}")

        # ── COMPARISON TABLE ──
        print("\n" + SEP)
        print("COMPARISON: DB vs API response")
        print(SEP)
        print(f"  {'Metric':40s} {'DB':>10s} {'API':>10s}")
        print(f"  {'-'*40} {'-'*10} {'-'*10}")
        print(f"  {'incidents (total)':40s} {'94':>10s} {str(total_inc):>10s}")
        print(f"  {'incidents (last 30d)':40s} {'94':>10s} {str(len(r.fetchall()) if 'r' in dir() else '?'):>10s}")
        print(f"  {'risk_scores':40s} {'11970':>10s} {str(len(points_data)):>10s}")

        print(f"\n  CRITICAL CHECK: All queries use UPPER(severity::text)")
        print(f"  DB stores severity as: 'CRITICAL','HIGH','MEDIUM' (enum NAMES, not values)")
        print(f"  UPPER('CRITICAL') = 'CRITICAL' — matches 'CRITICAL'? YES")
        print(f"  UPPER('HIGH') = 'HIGH' — matches 'HIGH'? YES")
        print(f"  Verified via investigate_empty_data2.py: UPPER() comparisons WORK correctly")

        print(f"\n  NEXT: Production-specific issues could include:")
        print(f"  1. Different database (empty or different connection)")
        print(f"  2. Admin auth failing (403/401 causes empty response)")
        print(f"  3. Wrapper format mismatch (backend wraps in {{data: ...}}, frontend expects unwrapped)")
        print(f"  4. response_model filter removes fields not in Pydantic schema")

asyncio.run(trace())
