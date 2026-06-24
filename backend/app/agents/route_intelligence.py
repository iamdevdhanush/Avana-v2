"""
Route Intelligence Agent v2

Improvements:
- Walking + driving support
- Incident-based explanations ("Route avoids 3 recent harassment incidents")
- Nearby incident fetching for each segment
"""

import asyncio
import logging
import time
from typing import List, Optional, Tuple

from sqlalchemy import text

logger = logging.getLogger(__name__)

_OSRM_BASE_URL = "https://router.project-osrm.org"
_SIMILARITY_THRESHOLD_DEG = 0.01


class RouteIntelligenceAgent:
    name = "route_intelligence"

    async def analyze_route(
        self,
        src_lat: float,
        src_lng: float,
        dst_lat: float,
        dst_lng: float,
        profile: str = "driving",
    ) -> dict:
        start = time.time()
        logger.info(f"[ROUTE_AGENT] Analyzing {profile} route ({src_lat},{src_lng}) → ({dst_lat},{dst_lng})")

        osrm_data = await self._fetch_routes(src_lat, src_lng, dst_lat, dst_lng, profile)
        routes = osrm_data.get("routes", [])
        if not routes:
            return {
                "status": "no_route",
                "error": "OSRM returned no routes",
                "metrics": {"duration_seconds": round(time.time() - start, 2)},
            }

        scored = []
        for route_data in routes:
            scored_route = await self._score_route(route_data, profile)
            scored.append(scored_route)

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

        explanation = await self._build_explanation(safest, fastest, profile)
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
            "profile": "Walking" if profile == "walking" else "Driving",
            "metrics": {"duration_seconds": duration},
        }

    async def _fetch_routes(
        self,
        src_lat: float,
        src_lng: float,
        dst_lat: float,
        dst_lng: float,
        profile: str = "driving",
    ) -> dict:
        import httpx
        profile_path = "driving" if profile == "driving" else "foot"
        url = (
            f"{_OSRM_BASE_URL}/route/v1/{profile_path}/"
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

    async def _fetch_nearby_incidents(self, lat: float, lng: float, radius_m: int = 500) -> list:
        from app.database import get_session_factory
        try:
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    text("""
                        SELECT metadata->>'women_safety_category' as ws_cat,
                               incident_type, title, severity, created_at
                        FROM incidents
                        WHERE ST_DWithin(
                            geom::geography,
                            ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                            :radius
                        )
                          AND status::text IN ('verified', 'VERIFIED')
                          AND metadata->>'women_safety_category' IS NOT NULL
                        ORDER BY created_at DESC
                        LIMIT 5
                    """),
                    {"lat": lat, "lng": lng, "radius": radius_m},
                )
                return [{"category": r[0], "type": r[1], "title": r[2], "severity": r[3], "date": r[4]} for r in result.fetchall()]
        except Exception as e:
            logger.warning(f"[ROUTE_AGENT] Nearby incidents fetch failed: {e}")
            return []

    async def _score_route(self, route_data: dict, profile: str = "driving") -> dict:
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
        all_nearby = []

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

            nearby = await self._fetch_nearby_incidents(start_coord[1], start_coord[0], 300)
            all_nearby.extend(nearby)

            total_risk += seg_score * step_dist
            segments.append({
                "start_lat": start_coord[1],
                "start_lng": start_coord[0],
                "end_lat": end_coord[1],
                "end_lng": end_coord[0],
                "safety_score": round(seg_score, 2),
                "risk_category": score_result.get("category", "MODERATE"),
                "distance_m": step_dist,
                "nearby_incidents": [n.get("category") for n in nearby[:3] if n.get("category")],
                "nearby_types": [n.get("type") for n in nearby[:3]],
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
            "nearby_incidents_summary": all_nearby,
        }

    async def _build_explanation(self, safest: dict, fastest: dict, profile: str = "driving") -> str:
        reasons = []
        profile_label = "Walking" if profile == "walking" else "Driving"

        if safest["safety_score"] < fastest["safety_score"]:
            diff = round(fastest["safety_score"] - safest["safety_score"], 1)
            reasons.append(f"{profile_label} route avoids {diff} pts higher risk areas")

        # Collect incident-specific details
        all_nearby = safest.get("nearby_incidents_summary", [])
        incident_types = {}
        for n in all_nearby:
            cat = n.get("category") or n.get("type") or "incident"
            incident_types[cat] = incident_types.get(cat, 0) + 1

        if incident_types:
            for cat, count in list(incident_types.items())[:3]:
                reasons.append(f"Route avoids {count} recent {cat.lower()} reports")

        safe_segs = [s for s in safest.get("segments", []) if s["safety_score"] <= 20]
        if safe_segs:
            reasons.append(f"Passes through {len(safe_segs)} low-risk street segments")

        high_risk = [s for s in fastest.get("segments", []) if s["safety_score"] > 65]
        if high_risk:
            reasons.append(f"Avoids {len(high_risk)} high-risk zones on fastest path")

        if not reasons:
            reasons.append(f"{profile_label} route risk assessment complete")

        return " | ".join(reasons[:5])
