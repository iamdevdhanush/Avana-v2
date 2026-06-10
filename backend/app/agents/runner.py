import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from app.agents.news_intelligence import run as news_run, run_scheduled as news_scheduled
from app.agents.community_intelligence import run as community_run, run_scheduled as community_scheduled
from app.agents.geocoding import run as geocoding_run, batch_geocode
from app.agents.risk_scoring import run as risk_scoring_run, batch_calculate
from app.agents.heatmap import generate_heatmap, get_heatmap_data
from app.agents.route_intelligence import run as route_run
from app.agents.safety_recommendation import run as recommendation_run

logger = logging.getLogger(__name__)


async def run_news_pipeline() -> dict:
    logger.info("=" * 60)
    logger.info("Starting News Intelligence Pipeline")
    logger.info("=" * 60)
    start = datetime.now(timezone.utc)
    try:
        news_result = await news_run()
        logger.info(f"News pipeline: {news_result.get('saved_count', 0)} incidents saved")
        return {
            "pipeline": "news",
            "status": "completed",
            "incidents_saved": news_result.get("saved_count", 0),
            "errors": news_result.get("errors", []),
            "duration_seconds": (datetime.now(timezone.utc) - start).total_seconds(),
        }
    except Exception as e:
        logger.error(f"News pipeline failed: {e}")
        return {
            "pipeline": "news",
            "status": "failed",
            "error": str(e),
            "duration_seconds": (datetime.now(timezone.utc) - start).total_seconds(),
        }


async def run_community_pipeline() -> dict:
    logger.info("=" * 60)
    logger.info("Starting Community Intelligence Pipeline")
    logger.info("=" * 60)
    start = datetime.now(timezone.utc)
    try:
        community_result = await community_run()
        logger.info(
            f"Community pipeline: {community_result.get('saved_count', 0)} reports processed, "
            f"{len(community_result.get('duplicates_found', []))} duplicates, "
            f"{len(community_result.get('spam_detected', []))} spam"
        )
        return {
            "pipeline": "community",
            "status": "completed",
            "reports_processed": community_result.get("saved_count", 0),
            "duplicates": len(community_result.get("duplicates_found", [])),
            "spam": len(community_result.get("spam_detected", [])),
            "errors": community_result.get("errors", []),
            "duration_seconds": (datetime.now(timezone.utc) - start).total_seconds(),
        }
    except Exception as e:
        logger.error(f"Community pipeline failed: {e}")
        return {
            "pipeline": "community",
            "status": "failed",
            "error": str(e),
            "duration_seconds": (datetime.now(timezone.utc) - start).total_seconds(),
        }


async def run_risk_scoring_pipeline(
    lat: float, lng: float,
    district: Optional[str] = None,
) -> dict:
    logger.info(f"Running risk scoring for ({lat}, {lng})")
    try:
        result = await risk_scoring_run(lat, lng, district)
        return {
            "pipeline": "risk_scoring",
            "status": "completed",
            "score": result.get("score"),
            "category": result.get("category"),
            "factors": result.get("factors", {}),
        }
    except Exception as e:
        logger.error(f"Risk scoring pipeline failed: {e}")
        return {"pipeline": "risk_scoring", "status": "failed", "error": str(e)}


async def run_heatmap_pipeline(
    zoom_level: str = "district",
    district: Optional[str] = None,
    city: Optional[str] = None,
) -> dict:
    logger.info(f"Running heatmap pipeline: {zoom_level}/{district or city or 'all'}")
    try:
        result = await generate_heatmap(zoom_level, district, city)
        return {
            "pipeline": "heatmap",
            "status": "completed",
            "points_generated": len(result.get("heatmap_data", [])),
            "zoom_level": zoom_level,
            "generated_at": result.get("generated_at", ""),
        }
    except Exception as e:
        logger.error(f"Heatmap pipeline failed: {e}")
        return {"pipeline": "heatmap", "status": "failed", "error": str(e)}


async def run_route_pipeline(
    source_lat: float, source_lng: float,
    dest_lat: float, dest_lng: float,
) -> dict:
    logger.info(f"Running route pipeline: ({source_lat},{source_lng}) -> ({dest_lat},{dest_lng})")
    try:
        result = await route_run((source_lat, source_lng), (dest_lat, dest_lng))
        return {
            "pipeline": "route",
            "status": "completed",
            "safest_route": result.get("safest_route"),
            "fastest_route": result.get("fastest_route"),
            "balanced_route": result.get("balanced_route"),
            "all_routes": result.get("all_routes", []),
        }
    except Exception as e:
        logger.error(f"Route pipeline failed: {e}")
        return {"pipeline": "route", "status": "failed", "error": str(e)}


async def run_recommendation_pipeline(
    lat: float, lng: float,
    user_id: Optional[str] = None,
) -> dict:
    logger.info(f"Running recommendation pipeline for ({lat}, {lng})")
    try:
        result = await recommendation_run(lat, lng, user_id)
        return {
            "pipeline": "recommendation",
            "status": "completed",
            "risk_score": result.get("risk_score"),
            "risk_category": result.get("risk_category"),
            "recommendations": result.get("recommendations", []),
        }
    except Exception as e:
        logger.error(f"Recommendation pipeline failed: {e}")
        return {"pipeline": "recommendation", "status": "failed", "error": str(e)}


async def run_all_agents() -> dict:
    logger.info("=" * 60)
    logger.info("RUNNING ALL AVANA AGENTS")
    logger.info("=" * 60)
    start = datetime.now(timezone.utc)
    results = {}
    results["news"] = await run_news_pipeline()
    results["community"] = await run_community_pipeline()
    results["heatmap_district"] = await run_heatmap_pipeline("district")
    logger.info("=" * 60)
    logger.info("ALL AGENTS COMPLETED")
    logger.info("=" * 60)
    results["_meta"] = {
        "started_at": start.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "total_duration_seconds": (datetime.now(timezone.utc) - start).total_seconds(),
    }
    for name, res in results.items():
        if name == "_meta":
            continue
        status = res.get("status", "unknown")
        logger.info(f"  {name}: {status}")
    return results


def run_all_scheduled() -> dict:
    return asyncio.run(run_all_agents())


def schedule_all() -> dict:
    schedules = {
        "news_intelligence": {
            "task": "app.agents.news_intelligence.run_scheduled",
            "schedule": 360,
            "description": "Scrape Karnataka news every 6 hours",
        },
        "community_intelligence": {
            "task": "app.agents.community_intelligence.run_scheduled",
            "schedule": 5,
            "description": "Process community reports every 5 minutes",
        },
        "heatmap_district": {
            "task": "app.agents.heatmap.generate_heatmap",
            "schedule": 360,
            "description": "Generate district-level heatmap every 6 hours",
        },
    }
    logger.info("Registered scheduled tasks:")
    for name, config in schedules.items():
        logger.info(f"  {name}: every {config['schedule']} min - {config['description']}")
    return schedules
