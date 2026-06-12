"""
Full pipeline end-to-end test using MOCK_INTELLIGENCE_MODE.

Verifies: incidents → geocode → dedup → save → risk scores → heatmap → dashboard → analytics
"""

import os, sys, asyncio, json, time

os.environ["MOCK_INTELLIGENCE_MODE"] = "true"

sys.path.insert(0, ".")

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("test")

from app.config import settings
assert settings.MOCK_INTELLIGENCE_MODE is True, "MOCK_INTELLIGENCE_MODE not set"

from app.database import get_session_factory
from sqlalchemy import text


# -- Helpers --------------------------------------------------------------

async def count_rows(table: str, where: str = "1=1") -> int:
    async with get_session_factory()() as s:
        r = await s.execute(text(f"SELECT COUNT(*) FROM {table} WHERE {where}"))
        return int(r.scalar() or 0)


async def fetch_rows(table: str, columns: str = "*", where: str = "1=1") -> list:
    async with get_session_factory()() as s:
        r = await s.execute(text(f"SELECT {columns} FROM {table} WHERE {where} ORDER BY created_at DESC"))
        return r.fetchall()


async def delete_mock_incidents():
    """Clean up any previous mock run data."""
    async with get_session_factory()() as s:
        await s.execute(text("DELETE FROM incidents WHERE source_url LIKE 'https://mock-source.local/%'"))
        await s.commit()
    n = await count_rows("incidents", "source_url LIKE 'https://mock-source.local/%'")
    logger.info(f"  Cleaned mock incidents: remaining={n}")


async def preload_geocoding_cache():
    """Pre-populate geocoding cache so Nominatim is not called."""
    entries = [
        ("City Bus Stand, Mysuru, Karnataka, India", 12.2958, 76.6394, "City Bus Stand, Mysuru"),
        ("KR Market, Bengaluru, Karnataka, India", 12.9626, 77.5757, "KR Market, Bengaluru"),
        ("Kengeri, Bengaluru, Karnataka, India", 12.9118, 77.4823, "Kengeri, Bengaluru"),
        ("Mangaluru City Center, Karnataka, India", 12.9141, 74.8560, "Mangaluru City Center"),
        ("Jayanagar, Bengaluru, Karnataka, India", 12.9310, 77.5930, "Jayanagar 4th Block, Bengaluru"),
    ]
    async with get_session_factory()() as s:
        for loc, lat, lng, dn in entries:
            await s.execute(
                text("""
                    INSERT INTO geocoding_cache
                        (id, location_text, latitude, longitude, display_name, last_verified, created_at)
                    VALUES (gen_random_uuid(), :q, :lat, :lng, :dn, NOW(), NOW())
                    ON CONFLICT (location_text) DO UPDATE
                        SET latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
                            display_name = EXCLUDED.display_name, last_verified = NOW()
                """),
                {"q": loc, "lat": lat, "lng": lng, "dn": dn},
            )
        await s.commit()
    logger.info(f"  Pre-loaded {len(entries)} geocoding cache entries")


# -- Verifiers ------------------------------------------------------------

async def verify_incidents() -> dict:
    print("\n-- Incidents Table --")
    count = await count_rows("incidents", "source_url LIKE 'https://mock-source.local/%'")
    rows = await fetch_rows(
        "incidents",
        "id, incident_type, severity, status, confidence_score, district, city, latitude, longitude, source_url",
        "source_url LIKE 'https://mock-source.local/%'",
    )
    print(f"  Total mock incidents: {count}")
    for r in rows:
        print(f"    [{r[1]:20s}] sev={r[2]:8s} status={r[3]:8s} dist={r[5]:20s} city={r[6]:12s} lat={r[7]:.4f} lng={r[8]:.4f}")

    types = {}
    for r in rows:
        types[r[1]] = types.get(r[1], 0) + 1
    return {"count": count, "rows": rows, "types": types}


async def verify_risk_scores() -> dict:
    print("\n-- Risk Scores Table --")
    async with get_session_factory()() as s:
        r = await s.execute(text("""
            SELECT latitude, longitude, score, category, calculated_at
            FROM risk_scores
            WHERE calculated_at >= NOW() - INTERVAL '5 minutes'
            ORDER BY calculated_at DESC
        """))
        rows = r.fetchall()
    print(f"  Risk scores updated (last 5min): {len(rows)}")
    for r in rows[:10]:
        print(f"    lat={float(r[0]):.4f} lng={float(r[1]):.4f} score={float(r[2]):.1f} cat={r[3]:12s}")
    if len(rows) > 10:
        print(f"    ... and {len(rows)-10} more")
    return {"count": len(rows), "rows": rows}


async def verify_heatmap() -> dict:
    print("\n-- Heatmap Data --")
    from app.config import settings as cfg
    bounds = [float(x) for x in cfg.KARNATAKA_BOUNDS.split(",")]
    from app.pipeline.heatmap import get_heatmap_data
    data = await get_heatmap_data(bounds[0], bounds[2], bounds[1], bounds[3])
    print(f"  Heatmap points (48h window): {len(data)}")
    cats = {}
    for d in data[:5]:
        cats[d["category"]] = cats.get(d["category"], 0) + 1
        print(f"    lat={d['latitude']:.4f} lng={d['longitude']:.4f} score={d['score']:.1f} cat={d['category']}")
    if len(data) > 5:
        print(f"    ... and {len(data)-5} more")
    return {"count": len(data), "categories": cats}


async def verify_dashboard() -> dict:
    print("\n-- Dashboard Metrics --")
    async with get_session_factory()() as s:
        total = (await s.execute(text("SELECT COUNT(*) FROM incidents"))).scalar() or 0
        by_district = (await s.execute(
            text("""
                SELECT district, COUNT(*) as total,
                       COUNT(*) FILTER (WHERE severity::text IN ('high','critical')) as high_risk,
                       COUNT(*) FILTER (WHERE severity::text = 'medium') as medium_risk,
                       COUNT(*) FILTER (WHERE severity::text = 'low') as low_risk
                FROM incidents WHERE district IS NOT NULL
                GROUP BY district ORDER BY total DESC
            """)
        )).fetchall()
        by_type = (await s.execute(
            text("SELECT incident_type, COUNT(*) FROM incidents GROUP BY incident_type ORDER BY COUNT(*) DESC")
        )).fetchall()

    print(f"  Total incidents (all): {total}")
    for d in by_district:
        print(f"    District {d[0]:20s} total={int(d[1]):2d} high={int(d[2]):2d} med={int(d[3]):2d} low={int(d[4]):2d}")
    for t in by_type:
        print(f"    Type {t[0]:20s} count={int(t[1])}")
    return {"total": total, "by_district": by_district, "by_type": by_type}


async def verify_analytics() -> dict:
    print("\n-- Analytics --")
    async with get_session_factory()() as s:
        trend = (await s.execute(
            text("SELECT DATE(created_at) as dt, COUNT(*) FROM incidents WHERE created_at >= NOW() - INTERVAL '30 days' GROUP BY dt ORDER BY dt")
        )).fetchall()
    print(f"  Today's incidents: {trend[-1][1] if trend else 0}")
    for t in trend:
        print(f"    {t[0]} count={int(t[1])}")
    return {"trend": trend}


# -- Main ----------------------------------------------------------------─

async def main():
    print("=" * 60)
    print("AVANA PIPELINE — MOCK MODE END-TO-END TEST")
    print("=" * 60)
    print(f"  MOCK_INTELLIGENCE_MODE = {settings.MOCK_INTELLIGENCE_MODE}")
    print()

    # 1. Clean previous mock data
    print("-- Setup --")
    await delete_mock_incidents()
    await preload_geocoding_cache()

    # 2. Run pipeline
    print("\n-- Pipeline Execution --")
    from app.pipeline.intelligence import run_intelligence_pipeline
    start = time.time()
    result = await run_intelligence_pipeline()
    elapsed = time.time() - start
    print(f"\n  Pipeline completed in {elapsed:.2f}s")
    print(f"  Result status: {result.get('status')}")
    print(f"  Steps: {json.dumps(result.get('steps', {}), indent=2)}")
    print(f"  Summary: {json.dumps(result.get('summary', {}), indent=2)}")

    print("\n" + "=" * 60)
    print("VERIFICATION RESULTS")
    print("=" * 60)

    # 3. Verify each layer
    inc = await verify_incidents()
    risk = await verify_risk_scores()
    heat = await verify_heatmap()
    dash = await verify_dashboard()
    anl = await verify_analytics()

    # 4. Generate report
    print("\n" + "=" * 60)
    print("TEST REPORT")
    print("=" * 60)
    errors = []
    if inc["count"] == 0:
        errors.append("FAIL: 0 incidents saved")
    elif inc["count"] < 5:
        errors.append(f"WARN: Only {inc['count']}/5 incidents saved (dedup/skip)")
    else:
        print(f"  PASS: Incidents created: {inc['count']}")

    if risk["count"] == 0:
        errors.append("FAIL: 0 risk scores computed")
    else:
        print(f"  PASS: Risk scores computed: {risk['count']}")

    if heat["count"] == 0:
        errors.append("FAIL: 0 heatmap points generated")
    else:
        print(f"  PASS: Heatmap points generated: {heat['count']}")

    if dash["total"] == 0:
        errors.append("FAIL: Dashboard shows 0 incidents")
    elif inc["count"] > 0 and dash["total"] >= inc["count"]:
        print(f"  PASS: Dashboard metrics: {dash['total']} incidents tracked")
    else:
        errors.append(f"WARN: Dashboard total ({dash['total']}) < mock count ({inc['count']})")

    mock_districts = {"Mysuru", "Bengaluru Urban", "Dakshina Kannada"}
    found_districts = {str(d[0]) for d in dash["by_district"]}
    missing = mock_districts - found_districts
    if missing:
        errors.append(f"WARN: Missing districts in dashboard: {missing}")
    else:
        print(f"  PASS: Dashboard districts: {len(found_districts)} districts present")

    if anl["trend"]:
        print(f"  PASS: Analytics trend: {len(anl['trend'])} data points")
    else:
        errors.append("FAIL: No analytics trend data")

    print()
    if errors:
        print("  FAIL: ISSUES:")
        for e in errors:
            print(f"     - {e}")
    else:
        print("  PASS: ALL CHECKS PASSED")

    # 5. Summary
    print(f"\n-- Summary --")
    print(f"  Pipeline duration:     {elapsed:.2f}s")
    print(f"  Pipeline status:       {result.get('status', 'N/A')}")
    print(f"  Incidents count:       {inc['count']}")
    print(f"  Incident types:        {json.dumps(inc.get('types', {}))}")
    print(f"  Risk scores:           {risk['count']}")
    print(f"  Heatmap points:        {heat['count']}")
    print(f"  Dashboard total:       {dash['total']}")
    print(f"  Analytics data points: {len(anl['trend'])}")
    print()

    return errors


if __name__ == "__main__":
    errs = asyncio.run(main())
    sys.exit(1 if errs else 0)
