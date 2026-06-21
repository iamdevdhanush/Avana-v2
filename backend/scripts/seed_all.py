"""
Master seed script — runs all seeders in dependency order.
Offline-first: no AI, no Gemini, no external APIs required.

Usage:
    python -m scripts.seed_all              # seed if empty
    python -m scripts.seed_all --force      # truncate & reseed
    python -m scripts.seed_all --skip-risk  # skip risk score generation
"""

import argparse
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.seed_police_hospitals import seed_police_stations, seed_hospitals
from scripts.seed_incidents import seed_incidents
from scripts.seed_risk_scores import seed_risk_scores, seed_heatmap_grid

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("seed_all")


async def seed_all(force: bool = False, skip_risk: bool = False):
    logger.info("=" * 60)
    logger.info("SEED ALL — Offline-First Data Population")
    logger.info("=" * 60)

    police_result = await seed_police_stations(truncate=force)
    logger.info(f"[SEED] Police stations: {police_result.get('status')} ({police_result.get('inserted', 0)} inserted)")

    hospital_result = await seed_hospitals(truncate=force)
    logger.info(f"[SEED] Hospitals: {hospital_result.get('status')} ({hospital_result.get('inserted', 0)} inserted)")

    incident_result = await seed_incidents(truncate=force)
    logger.info(f"[SEED] Incidents: {incident_result.get('status')} ({incident_result.get('inserted', 0)} inserted)")

    if not skip_risk:
        risk_result = await seed_risk_scores(truncate=force)
        logger.info(f"[SEED] Risk scores: {risk_result.get('status')} ({risk_result.get('updated', 0)} updated)")

        heatmap_result = await seed_heatmap_grid()
        logger.info(f"[SEED] Heatmap: {heatmap_result.get('points_generated', 0)} points generated")

    logger.info("=" * 60)
    logger.info("SEED ALL COMPLETE")
    logger.info("=" * 60)

    return {
        "police_stations": police_result,
        "hospitals": hospital_result,
        "incidents": incident_result,
        "risk_scores": risk_result if not skip_risk else {"status": "skipped"},
        "heatmap": heatmap_result if not skip_risk else {"status": "skipped"},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed all offline data")
    parser.add_argument("--force", action="store_true", help="Truncate and reseed")
    parser.add_argument("--skip-risk", action="store_true", help="Skip risk score generation")
    args = parser.parse_args()
    asyncio.run(seed_all(force=args.force, skip_risk=args.skip_risk))
