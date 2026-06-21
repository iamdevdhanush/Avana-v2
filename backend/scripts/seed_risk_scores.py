"""
Generate risk scores from seeded incidents + crime stats + geo data.
Completely offline — no AI dependency.

Uses the same scoring logic as app/pipeline/risk.py but works directly
from the database, not from live API responses.
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import List, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.database import Base, get_session_factory
from app.pipeline.risk import score_location, ensure_default_location

logger = logging.getLogger(__name__)


async def seed_risk_scores(truncate: bool = False) -> dict:
    """
    Generate risk scores from all incident locations with women_safety_category.
    Uses the same score_location() function as the real pipeline.
    """
    factory = get_session_factory()

    async with factory() as db:
        if truncate:
            await db.execute(text("DELETE FROM risk_scores"))
            await db.commit()
            logger.info("[SEED] Truncated risk_scores table")

        result = await db.execute(
            text("""
                SELECT DISTINCT latitude, longitude, district
                FROM incidents
                WHERE latitude IS NOT NULL
                  AND metadata->>'women_safety_category' IS NOT NULL
            """)
        )
        points = result.fetchall()

    if not points:
        logger.warning("[SEED] No incidents with women_safety_category found")
        loc_id = await ensure_default_location()
        async with factory() as db:
            await db.execute(
                text("""
                    INSERT INTO risk_scores
                        (id, location_id, latitude, longitude, score, category,
                         metadata, calculated_at, created_at)
                    VALUES (
                        gen_random_uuid(), :loc_id, 12.9716, 77.5946,
                        50.0, 'MODERATE', '{}'::jsonb, NOW(), NOW()
                    )
                """),
                {"loc_id": loc_id},
            )
            await db.commit()
        return {"status": "fallback", "reason": "no women-safety incidents found, created default score"}

    total = len(points)
    updated = 0
    errors = 0

    for lat, lng, district in points:
        try:
            result = await score_location(lat, lng, district)
            async with factory() as db:
                await db.execute(
                    text("""
                        INSERT INTO risk_scores
                            (id, location_id, latitude, longitude, score, category,
                             metadata, calculated_at, created_at)
                        VALUES (
                            gen_random_uuid(),
                            :location_id, :lat, :lng, :score, :cat,
                            '{}'::jsonb, NOW(), NOW()
                        )
                        ON CONFLICT (latitude, longitude)
                        DO UPDATE SET
                            score = EXCLUDED.score,
                            category = EXCLUDED.category,
                            calculated_at = NOW()
                    """),
                    {
                        "lat": lat,
                        "lng": lng,
                        "score": result["score"],
                        "cat": result["category"],
                        "location_id": (await ensure_default_location()),
                    },
                )
                await db.commit()
                updated += 1
        except Exception as e:
            logger.error(f"[SEED] Risk score failed for ({lat}, {lng}): {e}")
            errors += 1

    logger.info(f"[SEED] risk_scores: {updated} updated, {errors} errors from {total} points")
    return {"status": "ok", "total": total, "updated": updated, "errors": errors}


async def seed_heatmap_grid() -> dict:
    """Generate the full heatmap grid using the same scoring as the pipeline."""
    from app.pipeline.heatmap import generate_heatmap_for_bounds
    from app.config import settings as cfg

    bounds = [float(x) for x in cfg.KARNATAKA_BOUNDS.split(",")]
    sw_lat, sw_lng, ne_lat, ne_lng = bounds[0], bounds[2], bounds[1], bounds[3]
    result = await generate_heatmap_for_bounds(sw_lat, sw_lng, ne_lat, ne_lng, zoom="state")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_risk_scores())
