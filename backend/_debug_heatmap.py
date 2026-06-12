"""Debug heatmap endpoint end-to-end. Simulates exactly what the API does."""
import asyncio
import json
from datetime import datetime, timezone
from app.database import get_session_factory
from sqlalchemy import text

async def debug():
    factory = get_session_factory()
    async with factory() as s:
        # 1. Total counts
        r = await s.execute(text("SELECT COUNT(*) FROM risk_scores"))
        total = r.scalar() or 0
        print(f"[CHECK] risk_scores total: {total}")

        # 2. Sample 5 rows
        r = await s.execute(text("""
            SELECT id, latitude, longitude, score, category, calculated_at, created_at
            FROM risk_scores LIMIT 5
        """))
        print(f"[CHECK] First 5 risk_scores:")
        for row in r:
            print(f"  lat={row.latitude:.4f}, lng={row.longitude:.4f}, score={row.score}, cat={row.category}, calc_at={row.calculated_at}")

        # 3. Score range
        r = await s.execute(text("SELECT MIN(score), MAX(score), AVG(score) FROM risk_scores"))
        row = r.fetchone()
        print(f"[CHECK] score range: {row[0]:.2f} - {row[1]:.2f}, avg={row[2]:.2f}")

        # 4. Simulate what get_heatmap_data returns — Karnataka-wide bounds
        sw_lat, sw_lng, ne_lat, ne_lng = 11.5, 74.0, 18.0, 78.5
        r = await s.execute(text("""
            SELECT DISTINCT ON (latitude, longitude)
                latitude, longitude, score, category
            FROM risk_scores
            WHERE latitude BETWEEN :sw_lat AND :ne_lat
              AND longitude BETWEEN :sw_lng AND :ne_lng
              AND calculated_at >= NOW() - INTERVAL '48 hours'
            ORDER BY latitude, longitude, calculated_at DESC
        """), {"sw_lat": sw_lat, "ne_lat": ne_lat, "sw_lng": sw_lng, "ne_lng": ne_lng})
        rows = r.fetchall()
        print(f"\n[CHECK] get_heatmap_data (Karnataka bounds, 48h filter): {len(rows)} points")
        if rows:
            print(f"[CHECK] First 3 rows:")
            for row in rows[:3]:
                print(f"  lat={float(row[0]):.4f}, lng={float(row[1]):.4f}, score={float(row[2]):.2f}, cat={row[3]}")
            # Check what the API response would look like
            print(f"\n[CHECK] Sample JSON response that would be returned:")
            sample = [
                {"latitude": float(r[0]), "longitude": float(r[1]),
                 "weight": float(r[2]), "risk_category": r[3]}
                for r in rows[:3]
            ]
            print(json.dumps(sample, indent=2, default=str))
        else:
            print("[CHECK] NO POINTS returned — this is the root cause!")
            # Check without time filter
            r2 = await s.execute(text("""
                SELECT DISTINCT ON (latitude, longitude)
                    latitude, longitude, score, category
                FROM risk_scores
                WHERE latitude BETWEEN :sw_lat AND :ne_lat
                  AND longitude BETWEEN :sw_lng AND :ne_lng
                ORDER BY latitude, longitude, calculated_at DESC
            """), {"sw_lat": sw_lat, "ne_lat": ne_lat, "sw_lng": sw_lng, "ne_lng": ne_lng})
            rows2 = r2.fetchall()
            print(f"[CHECK] Without time filter: {len(rows2)} points")
            if rows2:
                print(f"[CHECK] First 3 rows (no time filter):")
                for row in rows2[:3]:
                    print(f"  lat={float(row[0]):.4f}, lng={float(row[1]):.4f}, score={float(row[2]):.2f}, cat={row[3]}")

        # 5. Simulate typical frontend bounds (Shivamogga area at city zoom)
        sw_lat2, sw_lng2, ne_lat2, ne_lng2 = 13.8, 75.4, 14.0, 75.7
        r = await s.execute(text("""
            SELECT COUNT(*) FROM risk_scores
            WHERE latitude BETWEEN :sw_lat AND :ne_lat
              AND longitude BETWEEN :sw_lng AND :ne_lng
              AND calculated_at >= NOW() - INTERVAL '48 hours'
        """), {"sw_lat": sw_lat2, "ne_lat": ne_lat2, "sw_lng": sw_lng2, "ne_lng": ne_lng2})
        count = r.scalar() or 0
        print(f"\n[CHECK] Shivamogga city bounds (13.8-14.0, 75.4-75.7) + 48h: {count} points")

        # 6. Check data shape: what HeatmapResponse Pydantic model would output
        print(f"\n[CHECK] Pydantic HeatmapPoint field names: latitude, longitude, weight, risk_category")
        print(f"[CHECK] Frontend expects: lat, lng, weight (mapped in api.ts line 445-449)")
        print(f"[CHECK] Json response from FastAPI will have snake_case field names")

        # 7. Check if any risk_scores have NULL coordinates or score
        r = await s.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE latitude IS NULL OR longitude IS NULL) as null_coords,
                COUNT(*) FILTER (WHERE score IS NULL) as null_score,
                COUNT(*) FILTER (WHERE score < 0 OR score > 100) as out_of_range_score
            FROM risk_scores
        """))
        row = r.fetchone()
        print(f"\n[CHECK] Data quality: null_coords={row[0]}, null_score={row[1]}, out_of_range={row[2]}")

asyncio.run(debug())
