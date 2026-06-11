"""
Heatmap Engine — Simplified.
Generates grid points within bounds and scores each via the risk engine.
Stores results to risk_scores table.
"""

import logging
import math
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from sqlalchemy import text

from app.database import async_session_factory
from app.pipeline.risk import score_location

logger = logging.getLogger(__name__)

GRID_SIZE_DEGREES = 0.009  # ~1km


def _generate_grid(sw_lat: float, sw_lng: float, ne_lat: float, ne_lng: float) -> List[Tuple[float, float]]:
    points = []
    lat = sw_lat
    while lat <= ne_lat:
        lng = sw_lng
        while lng <= ne_lng:
            points.append((round(lat, 6), round(lng, 6)))
            lng += GRID_SIZE_DEGREES
        lat += GRID_SIZE_DEGREES
    return points


async def generate_heatmap_for_bounds(
    sw_lat: float, sw_lng: float,
    ne_lat: float, ne_lng: float,
    zoom: str = "city",
) -> dict:
    grid = _generate_grid(sw_lat, sw_lng, ne_lat, ne_lng)
    logger.info(f"Generating heatmap for {len(grid)} grid points")
    results = []
    batch_size = 20
    for i in range(0, len(grid), batch_size):
        batch = grid[i:i + batch_size]
        for lat, lng in batch:
            try:
                sr = await score_location(lat, lng)
                results.append({
                    "latitude": lat,
                    "longitude": lng,
                    "score": sr["score"],
                    "category": sr["category"],
                    "factors": sr["factors"],
                })
            except Exception as e:
                logger.warning(f"Heatmap point failed ({lat}, {lng}): {e}")
                results.append({
                    "latitude": lat,
                    "longitude": lng,
                    "score": 50.0,
                    "category": "Moderate",
                    "factors": {},
                })
    async with async_session_factory() as session:
        for r in results:
            try:
                await session.execute(
                    text("""
                        INSERT INTO risk_scores
                            (latitude, longitude, score, category,
                             calculated_at, created_at, location_id)
                        VALUES (:lat, :lng, :score, :cat, NOW(), NOW(),
                                gen_random_uuid())
                        ON CONFLICT (latitude, longitude) DO UPDATE
                        SET score = EXCLUDED.score,
                            category = EXCLUDED.category,
                            calculated_at = NOW()
                    """),
                    {"lat": r["latitude"], "lng": r["longitude"],
                     "score": r["score"], "cat": r["category"]},
                )
            except Exception as e:
                logger.error(f"Failed to save heatmap point: {e}")
        await session.commit()
    return {
        "points_generated": len(results),
        "bounds": {"sw_lat": sw_lat, "sw_lng": sw_lng, "ne_lat": ne_lat, "ne_lng": ne_lng},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_heatmap_data(
    sw_lat: float, sw_lng: float,
    ne_lat: float, ne_lng: float,
) -> List[dict]:
    async with async_session_factory() as session:
        result = await session.execute(
            text("""
                SELECT DISTINCT ON (latitude, longitude)
                    latitude, longitude, score, category
                FROM risk_scores
                WHERE latitude BETWEEN :sw_lat AND :ne_lat
                  AND longitude BETWEEN :sw_lng AND :ne_lng
                  AND calculated_at >= NOW() - INTERVAL '48 hours'
                ORDER BY latitude, longitude, calculated_at DESC
            """),
            {"sw_lat": sw_lat, "ne_lat": ne_lat,
             "sw_lng": sw_lng, "ne_lng": ne_lng},
        )
        rows = result.fetchall()
        return [
            {"latitude": float(r[0]), "longitude": float(r[1]),
             "score": float(r[2]), "category": r[3]}
            for r in rows
        ]
