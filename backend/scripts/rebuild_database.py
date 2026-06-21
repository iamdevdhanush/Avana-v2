"""
Full database rebuild from scratch.
Drops all tables, recreates schema, seeds all data.

Usage:
    python -m scripts.rebuild_database

WARNING: This destroys ALL existing data.
"""

import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.database import Base, get_engine

from scripts.seed_police_hospitals import seed_police_stations, seed_hospitals
from scripts.seed_incidents import seed_incidents
from scripts.seed_risk_scores import seed_risk_scores, seed_heatmap_grid

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("rebuild")


async def drop_all_tables():
    logger.warning("[REBUILD] Dropping all tables...")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        tables = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        for row in tables:
            table_name = row[0]
            await conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
            logger.info(f"[REBUILD] Dropped table: {table_name}")


async def recreate_schema():
    logger.info("[REBUILD] Recreating schema...")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("[REBUILD] Schema recreated")


async def rebuild_database():
    logger.info("=" * 60)
    logger.info("REBUILD DATABASE — Complete Destruction & Recreation")
    logger.info("=" * 60)

    confirm = input("This will DROP ALL TABLES and recreate from scratch. Type 'YES' to continue: ")
    if confirm != "YES":
        logger.info("[REBUILD] Aborted")
        return {"status": "aborted"}

    await drop_all_tables()
    await recreate_schema()

    logger.info("[REBUILD] Seeding data...")
    police = await seed_police_stations(truncate=False)
    hospitals = await seed_hospitals(truncate=False)
    incidents = await seed_incidents(truncate=False)
    risk = await seed_risk_scores(truncate=True)
    heatmap = await seed_heatmap_grid()

    logger.info("=" * 60)
    logger.info("REBUILD COMPLETE")
    logger.info(f"  Police stations: {police.get('inserted', 0)}")
    logger.info(f"  Hospitals: {hospitals.get('inserted', 0)}")
    logger.info(f"  Incidents: {incidents.get('inserted', 0)}")
    logger.info(f"  Risk scores: {risk.get('updated', 0)}")
    logger.info(f"  Heatmap points: {heatmap.get('points_generated', 0)}")
    logger.info("=" * 60)

    return {
        "status": "ok",
        "police_stations": police.get("inserted", 0),
        "hospitals": hospitals.get("inserted", 0),
        "incidents": incidents.get("inserted", 0),
        "risk_scores": risk.get("updated", 0),
        "heatmap_points": heatmap.get("points_generated", 0),
    }


if __name__ == "__main__":
    asyncio.run(rebuild_database())
