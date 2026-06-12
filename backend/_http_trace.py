"""
Simulate EXACT HTTP requests the frontend makes to each endpoint.
Compares behavior with auth, without auth, and with expired tokens.
"""
import asyncio
import json
import httpx
from app.main import app
from app.database import get_session_factory
from app.utils.security import create_access_token, decode_token
from app.dependencies import get_current_user, require_user, require_admin
from sqlalchemy import text

BASE = "http://test/api/v1"
SEP = "=" * 70

async def simulate():
    factory = get_session_factory()
    async with factory() as db:
        # ── Get a real admin token ──
        from app.models.user import User
        from sqlalchemy import select
        r = await db.execute(select(User).where(User.role == "admin"))
        admin_user = r.scalar_one_or_none()
        if not admin_user:
            print("NO ADMIN USER FOUND! This is a problem.")
            print("Users in DB:")
            r = await db.execute(select(User))
            for u in r.scalars():
                print(f"  {u.email} role={u.role} is_active={u.is_active}")
            return
        print(f"Admin user: {admin_user.email} role={admin_user.role} id={admin_user.id}")

        valid_token = create_access_token({"sub": str(admin_user.id), "type": "access"})
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInR5cGUiOiJhY2Nlc3MiLCJleHAiOjE3MDAwMDAwMDB9.dGhpcyBpcyBpbnZhbGlk"
        invalid_token = "not-a-valid-jwt"
        no_token = ""

        test_cases = [
            ("Valid Admin Token", valid_token),
            ("No Token (public)", no_token),
            ("Invalid JWT", invalid_token),
        ]

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for case_name, token in test_cases:
                headers = {"Authorization": f"Bearer {token}"} if token else {}
                print(f"\n{'#' * 70}")
                print(f"# TEST CASE: {case_name}")
                print(f"{'#' * 70}")

                # 1. GET /admin/dashboard
                print(f"\n--- GET /api/v1/admin/dashboard ---")
                r = await client.get(f"{BASE}/admin/dashboard", headers=headers)
                print(f"  Status: {r.status_code}")
                if r.status_code == 200:
                    j = r.json()
                    inner = j.get("data", j)
                    print(f"  total_incidents: {inner.get('total_incidents', 'MISSING')}")
                    print(f"  verified_reports: {inner.get('verified_reports', 'MISSING')}")
                    print(f"  active_users: {inner.get('active_users', 'MISSING')}")
                    print(f"  sos_events: {inner.get('sos_events', 'MISSING')}")
                    print(f"  incidents_by_district: {len(inner.get('incidents_by_district', []))} items")
                    print(f"  incidents_by_type: {len(inner.get('incidents_by_type', []))} items")
                    print(f"  recent_alerts: {len(inner.get('recent_alerts', []))} items")
                    print(f"  risk_trend: {len(inner.get('risk_trend', []))} items")
                    print(f"  incidents_trend: {len(inner.get('incidents_trend', []))} items")
                else:
                    print(f"  Response: {r.text[:200]}")

                # 2. GET /analytics/districts
                print(f"\n--- GET /api/v1/analytics/districts ---")
                r = await client.get(f"{BASE}/analytics/districts", headers=headers)
                print(f"  Status: {r.status_code}")
                if r.status_code == 200:
                    j = r.json()
                    inner = j.get("data", j) if isinstance(j, dict) else j
                    if isinstance(inner, list):
                        print(f"  Items: {len(inner)}")
                        for item in inner[:3]:
                            print(f"    {item.get('district', '?' )}: total={item.get('total_incidents', item.get('total', '?'))}")
                    else:
                        print(f"  Response: {json.dumps(inner, default=str)[:200]}")
                else:
                    print(f"  Response: {r.text[:200]}")

                # 3. GET /analytics/trends?days=30
                print(f"\n--- GET /api/v1/analytics/trends?days=30 ---")
                r = await client.get(f"{BASE}/analytics/trends?days=30", headers=headers)
                print(f"  Status: {r.status_code}")
                if r.status_code == 200:
                    j = r.json()
                    inner = j.get("data", j)
                    data = inner.get("data", inner) if isinstance(inner, dict) else inner
                    if isinstance(data, list):
                        print(f"  Data points: {len(data)}")
                        for d in data[:3]:
                            print(f"    {d.get('date', '?')}: total={d.get('total', '?')}")
                    else:
                        print(f"  Response: {json.dumps(inner, default=str)[:200]}")
                else:
                    print(f"  Response: {r.text[:200]}")

                # 4. GET /incidents (public, but test with auth too)
                print(f"\n--- GET /api/v1/incidents?limit=3 ---")
                r = await client.get(f"{BASE}/incidents?limit=3", headers=headers)
                print(f"  Status: {r.status_code}")
                if r.status_code == 200:
                    j = r.json()
                    inner = j.get("data", j)
                    items = inner.get("items", inner if isinstance(inner, list) else [])
                    if isinstance(items, list):
                        print(f"  Items: {len(items)}, total: {inner.get('total', '?' if isinstance(inner, dict) else 'N/A')}")
                        for item in items[:3]:
                            print(f"    {item.get('id', '?')[:8]}: type={item.get('incident_type', '?')} severity={item.get('severity', '?')} district={item.get('district', '?')}")
                    else:
                        print(f"  Response: {json.dumps(inner, default=str)[:200]}")
                else:
                    print(f"  Response: {r.text[:200]}")

                # 5. POST /risk/score
                print(f"\n--- POST /api/v1/risk/score ---")
                r = await client.post(f"{BASE}/risk/score", json={"latitude": 13.93, "longitude": 75.57}, headers=headers)
                print(f"  Status: {r.status_code}")
                if r.status_code == 200:
                    j = r.json()
                    inner = j.get("data", j)
                    print(f"  score: {inner.get('score', 'MISSING')}, category: {inner.get('category', 'MISSING')}")
                else:
                    print(f"  Response: {r.text[:200]}")

                # 6. POST /risk/heatmap
                print(f"\n--- POST /api/v1/risk/heatmap ---")
                r = await client.post(f"{BASE}/risk/heatmap", json={"sw_lat": 12.5, "sw_lng": 74.5, "ne_lat": 14.5, "ne_lng": 76.5, "zoom": 10}, headers=headers)
                print(f"  Status: {r.status_code}")
                if r.status_code == 200:
                    j = r.json()
                    inner = j.get("data", j)
                    points = inner.get("points", [])
                    print(f"  Points: {len(points)}")
                    if points:
                        print(f"  First point: lat={points[0].get('latitude', points[0].get('lat', '?'))}, lng={points[0].get('longitude', points[0].get('lng', '?'))}, weight={points[0].get('weight', '?')}")
                    summaries = inner.get("district_summaries", [])
                    print(f"  District summaries: {len(summaries)}")
                else:
                    print(f"  Response: {r.text[:200]}")

    print(f"\n{'=' * 70}")
    print("SUMMARY OF FINDINGS")
    print(f"{'=' * 70}")
    print("""
If admin endpoints return 401/403 WITHOUT auth but 200 WITH valid admin token:
  → The issue is authentication. User isn't logged in with admin role.

If ALL endpoints return 200 with data:
  → The issue is in the frontend data flow (error handling, response parsing).

If public endpoints (incidents, risk/score, risk/heatmap) return 0:
  → The issue is in the query filters or database.
""")

asyncio.run(simulate())
