"""Simulate exact API response that frontend receives."""
import asyncio
from app.database import get_session_factory
from sqlalchemy import text

async def q():
    factory = get_session_factory()
    async with factory() as s:
        bounds = {"sw_lat": 12.8, "sw_lng": 77.3, "ne_lat": 13.1, "ne_lng": 77.8}
        r = await s.execute(
            text("""
                SELECT DISTINCT ON (latitude, longitude)
                    latitude, longitude, score, category
                FROM risk_scores
                WHERE latitude BETWEEN :sw_lat AND :ne_lat
                  AND longitude BETWEEN :sw_lng AND :ne_lng
                  AND calculated_at >= NOW() - INTERVAL '48 hours'
                ORDER BY latitude, longitude, calculated_at DESC
            """),
            bounds,
        )
        rows = r.fetchall()
        print(f"EXACT API response: {len(rows)} points")
        if rows:
            for i, row in enumerate(rows[:3]):
                print(f"  lat={float(row[0]):.4f}, lng={float(row[1]):.4f}, weight={float(row[2]):.2f}, cat={row[3]}")
            weights = [float(r[2]) for r in rows]
            print(f"weight stats: min={min(weights):.2f} max={max(weights):.2f} avg={sum(weights)/len(weights):.2f}")
            print(f"all weights > 1? {all(w>1 for w in weights)}")
            print(f"Problem: leaflet.heat max=1, but weights are {min(weights):.2f}-{max(weights):.2f}")
            print(f"All weights clamped to 1 — no gradient visible, everything flat max intensity")
            print(f"BUT even flat max intensity should show PURPLE overlay (#7c3aed)")
        else:
            print("NO POINTS returned!")
            r2 = await s.execute(text("SELECT COUNT(*) FROM risk_scores"))
            print(f"Total risk_scores: {r2.scalar()}")
            r3 = await s.execute(text("SELECT MIN(latitude), MAX(latitude), MIN(longitude), MAX(longitude) FROM risk_scores"))
            row = r3.fetchone()
            print(f"risk_scores bounds: lat [{row[0]:.4f},{row[1]:.4f}] lng [{row[2]:.4f},{row[3]:.4f}]")

asyncio.run(q())
