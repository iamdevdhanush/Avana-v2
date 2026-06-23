"""
Risk Intelligence Agent

Owns risk scoring and heatmap generation:
  1. Recalculate risk scores for all incident locations (full refresh)
  2. Generate spatial heatmap grid over affected bounds
  3. Expose incremental scoring for a single location (used by Route Agent)

All spatial math is delegated to pipeline/risk.py and pipeline/heatmap.py -
those modules are pure computation and remain unchanged.
"""

import logging
import time

from app.pipeline.risk import recalculate_all_risk_scores, score_location
from app.pipeline.heatmap import generate_heatmap_for_bounds, compute_localized_bounds
from app.utils.timing import Timer

logger = logging.getLogger(__name__)


class RiskIntelligenceAgent:
    name = "risk_intelligence"

    async def run(self, full_heatmap: bool = True) -> dict:
        with Timer("3c. RiskIntelligenceAgent.run()"):
            start = time.time()
            logger.info("[RISK_AGENT] Starting risk intelligence cycle")

        try:
            with Timer("12. Risk scoring (recalculate_all_risk_scores)"):
                risk_result = await recalculate_all_risk_scores()
            risk_metric = {"status": "ok", **risk_result}
            logger.info(f"[RISK_AGENT] Risk recalculation: {risk_result}")
        except Exception as exc:
            logger.error(f"[RISK_AGENT] Risk recalculation failed: {exc}")
            risk_metric = {"status": "failed", "error": str(exc)}

        heatmap_metric: dict = {}
        if full_heatmap:
            heatmap_metric = await self._regenerate_heatmap()

        duration = round(time.time() - start, 2)
        logger.info(f"[RISK_AGENT] Complete ({duration}s)")

        return {
            "status": "ok",
            "metrics": {
                "risk_recalc": risk_metric,
                "heatmap": heatmap_metric,
                "duration_seconds": duration,
            },
        }

    async def score_point(self, lat: float, lng: float) -> dict:
        return await score_location(lat, lng)

    async def _regenerate_heatmap(self) -> dict:
        try:
            bounds_list = await compute_localized_bounds(buffer_degrees=0.05, max_cells_per=1000)
            if bounds_list:
                total_points = 0
                zone_errors = []
                for i, (sw_lat, sw_lng, ne_lat, ne_lng) in enumerate(bounds_list):
                    logger.info(
                        f"[RISK_AGENT] Heatmap zone {i + 1}/{len(bounds_list)}: "
                        f"({sw_lat:.4f},{sw_lng:.4f}) -> ({ne_lat:.4f},{ne_lng:.4f})"
                    )
                    heat_result = await generate_heatmap_for_bounds(sw_lat, sw_lng, ne_lat, ne_lng)
                    if "error" in heat_result:
                        zone_errors.append(heat_result["error"])
                    total_points += heat_result.get("points_generated", 0)

                metric = {"status": "ok" if total_points > 0 else "failed", "points_generated": total_points}
                if zone_errors:
                    metric["zone_errors"] = zone_errors
                logger.info(f"[RISK_AGENT] Heatmap: {total_points} points across {len(bounds_list)} zone(s)")
            else:
                from app.config import settings
                bounds = [float(x) for x in settings.KARNATAKA_BOUNDS.split(",")]
                sw_lat, sw_lng, ne_lat, ne_lng = bounds[0], bounds[2], bounds[1], bounds[3]
                heat_result = await generate_heatmap_for_bounds(sw_lat, sw_lng, ne_lat, ne_lng)
                metric = {
                    "status": "ok" if heat_result.get("points_generated", 0) > 0 else "failed",
                    **heat_result,
                }

            return metric

        except Exception as exc:
            logger.error(f"[RISK_AGENT] Heatmap generation failed: {exc}")
            return {"status": "failed", "error": str(exc)}
