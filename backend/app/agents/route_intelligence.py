"""
Route Intelligence Agent

Owns safe route analysis:
  1. Fetch routes from OSRM (primary + alternatives)
  2. Score each route segment against the risk score surface
  3. Rank routes: safest / fastest / balanced
  4. Build human-readable explanation

All OSRM interaction is via the existing route.py logic re-exposed here
as a composable agent method. The API endpoint (api/v1/route.py) is unchanged —
it continues to call its own internal helpers. This agent exists for use by
the pipeline orchestrator and any future scheduled analysis.
"""

import asyncio
import logging
import time
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_OSRM_BASE_URL = "https://router.project-osrm.org"
_SIMILARITY_THRESHOLD_DEG = 0.01


class RouteIntelligenceAgent:
    """
    Analyses route safety between two coordinates.

    Usage:
        agent = RouteIntelligenceAgent()
        result = await agent.analyze_route(src_lat, src_lng, dst_lat, dst_lng)
        # result["safest"]   → dict with safety_score, segments, geometry
        # result["fastest"]  → dict
        # result["balanced"] → dict
        # result["explanation"] → str
    """

    name = "route_intelligence"

    async def analyze_route(
        self,
        src_lat: float,
        src_lng: float,
        dst_lat: float,
        dst_lng: float,
    ) -> dict:
        start = time.time()
        logger.info(f"[ROUTE_AGENT] Analyzing route ({src_lat},{src_lng}) → ({dst_lat},{dst_lng})")

        # Step 1 — fetch from OSRM
        osrm_data = await self._fetch_routes(src_lat, src_lng, dst_lat, dst_lng)
        routes = osrm_data.get("routes", [])
        if not routes:
            return {
                "status": "no_route",
                "error": "OSRM returned no routes",
                "metrics": {"duration_seconds": round(time.time() - start, 2)},
            }

        # Step 2 — score each route
        scored = []
        for route_data in routes:
            scored_route = await self._score_route(route_data)
            scored.append(scored_route)

        # Step 3 — rank
        by_safety = sorted(scored, key=lambda r: r["safety_score"])
        by_speed = sorted(scored, key=lambda r: r["duration_seconds"])

        safest = {**by_safety[0], "type": "safest"}
        fastest = {**by_speed[0], "type": "fastest"}

        alternatives = [
            r for r in scored
            if r is not by_safety[0] and r is not by_speed[0]
        ]
        if alternatives:
            balanced_raw = sorted(
                alternatives,
                key=lambda r: r["safety_score"] * 0.4 + r["duration_seconds"] * 0.6 / 60.0,
            )[0]
            balanced = {**balanced_raw, "type": "balanced"}
        else:
            balanced = {**fastest, "type": "balanced"}

        explanation = self._build_explanation(safest, fastest)
        duration = round(time.time() - start, 2)

        logger.info(
            f"[ROUTE_AGENT] Routes analysed: safest_score={safest['safety_score']:.1f}, "
            f"fastest_score={fastest['safety_score']:.1f} ({duration}s)"
        )

        return {
            "status": "ok",
            "safest": safest,
            "fastest": fastest,
            "balanced": balanced,
            "explanation": explanation,
            "metrics": {"duration_seconds": duration},
        }

    # ──────────────────────────────────────────────────────────────────
    # OSRM
    # ──────────────────────────────────────────────────────────────────

    async def _fetch_routes(
        self,
        src_lat: float,
        src_lng: float,
        dst_lat: float,
        dst_lng: float,
    ) -> dict:
        import httpx
        url = (
            f"{_OSRM_BASE_URL}/route/v1/driving/"
            f"{src_lng},{src_lat};{dst_lng},{dst_lat}"
            "?overview=full&geometries=geojson&steps=true&alternatives=3"
        )
        for attempt in range(1, 4):
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp.json()
            except Exception as exc:
                if attempt < 3:
                    await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
                else:
                    logger.error(f"[ROUTE_AGENT] OSRM failed after 3 attempts: {exc}")
                    return {"routes": []}
        return {"routes": []}

    # ──────────────────────────────────────────────────────────────────
    # Risk scoring
    # ──────────────────────────────────────────────────────────────────

    async def _score_route(self, route_data: dict) -> dict:
        from app.pipeline.risk import score_location

        leg = route_data.get("legs", [{}])[0]
        steps = leg.get("steps", [])
        geometry_coords = [
            [coord[1], coord[0]]
            for coord in route_data.get("geometry", {}).get("coordinates", [])
        ]

        total_risk = 0.0
        total_distance = 0.0
        segments = []

        for step in steps:
            seg_coords = step.get("geometry", {}).get("coordinates", [])
            if not seg_coords:
                continue
            start_coord = seg_coords[0]
            end_coord = seg_coords[-1]
            step_dist = step.get("distance", 0)
            total_distance += step_dist

            try:
                score_result = await score_location(start_coord[1], start_coord[0])
                seg_score = score_result["score"]
            except Exception:
                seg_score = 50.0
                score_result = {"category": "MODERATE", "factors": {}}

            total_risk += seg_score * step_dist
            segments.append({
                "start_lat": start_coord[1],
                "start_lng": start_coord[0],
                "end_lat": end_coord[1],
                "end_lng": end_coord[0],
                "safety_score": round(seg_score, 2),
                "risk_category": score_result.get("category", "MODERATE"),
                "distance_m": step_dist,
            })

        avg_safety = round(total_risk / total_distance, 2) if total_distance > 0 else 50.0
        duration_s = route_data.get("duration", 0) or 0
        distance_km = round(total_distance / 1000, 2)

        return {
            "safety_score": round(min(100.0, max(0.0, avg_safety)), 2),
            "duration_seconds": duration_s,
            "duration_minutes": round(duration_s / 60, 2),
            "distance_km": distance_km,
            "segments": segments,
            "geometry": geometry_coords,
        }

    # ──────────────────────────────────────────────────────────────────
    # Explanation
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_explanation(safest: dict, fastest: dict) -> str:
        reasons = []
        if safest["safety_score"] < fastest["safety_score"]:
            diff = round(fastest["safety_score"] - safest["safety_score"], 1)
            reasons.append(f"Avoids {diff} pts higher risk areas")

        safe_segs = [s for s in safest.get("segments", []) if s["safety_score"] <= 33]
        if safe_segs:
            reasons.append(f"Passes through {len(safe_segs)} safer segments")

        high_risk = [s for s in fastest.get("segments", []) if s["safety_score"] > 66]
        if high_risk:
            reasons.append(f"Avoids {len(high_risk)} high-risk zones on fastest path")

        if not reasons:
            reasons.append("Route risk assessment complete")

        return " | ".join(reasons[:4])
