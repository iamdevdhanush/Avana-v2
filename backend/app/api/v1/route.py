import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.route import (
    RouteRequest,
    RouteResponse,
    RouteOption,
    RouteSegment,
)
from app.pipeline.risk import score_location

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/route", tags=["Route Intelligence"])

OSRM_BASE_URL = "https://router.project-osrm.org"
SIMILARITY_THRESHOLD_DEG = 0.01


async def _fetch_route(
    source_lat: float,
    source_lng: float,
    dest_lat: float,
    dest_lng: float,
    profile: str = "driving",
) -> dict:
    import httpx
    profile_path = "driving" if profile == "driving" else "foot"
    url = (
        f"{OSRM_BASE_URL}/route/v1/{profile_path}/"
        f"{source_lng},{source_lat};{dest_lng},{dest_lat}"
        f"?overview=full&geometries=geojson&steps=true&alternatives=3"
    )
    last_exc = None
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    if resp.status_code in (429, 503, 502) and attempt < 3:
                        delay = 1.0 * (2 ** (attempt - 1))
                        logger.warning(f"OSRM HTTP {resp.status_code} (attempt {attempt}/3). Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        continue
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Route service returned {resp.status_code}",
                    )
                return resp.json()
        except HTTPException:
            raise
        except Exception as e:
            last_exc = e
            if attempt < 3:
                delay = 1.0 * (2 ** (attempt - 1))
                logger.warning(f"OSRM error (attempt {attempt}/3): {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"OSRM failed after 3 attempts: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Route service unavailable after 3 retries: {str(e)}",
                )
    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Route service unavailable")


async def _fetch_nearby_incidents(lat: float, lng: float, radius_m: int = 500) -> list:
    """Fetch nearby incidents with human-readable details for route explanations."""
    try:
        async with get_db() as db:
            result = await db.execute(
                text("""
                    SELECT incident_type, severity,
                           metadata->>'women_safety_category' as ws_cat,
                           title, created_at,
                           ST_Distance(
                               geom::geography,
                               ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography
                           ) as dist
                    FROM incidents
                    WHERE ST_DWithin(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
                        :radius
                    )
                      AND status::text IN ('verified', 'VERIFIED')
                      AND metadata->>'women_safety_category' IS NOT NULL
                    ORDER BY dist ASC
                    LIMIT 10
                """),
                {"lat": lat, "lng": lng, "radius": radius_m},
            )
            return [{"type": r[0], "severity": r[1], "category": r[2], "title": r[3], "created_at": r[4], "distance_m": float(r[5])} for r in result.fetchall()]
    except Exception as e:
        logger.warning(f"[ROUTE] Nearby incidents fetch failed: {e}")
        return []


async def _score_segment(seg_start_lat: float, seg_start_lng: float, db=None) -> dict:
    try:
        result = await score_location(seg_start_lat, seg_start_lng)
        return {"score": result["score"], "category": result["category"], "factors": result["factors"]}
    except Exception as e:
        logger.warning(f"Segment risk scoring failed: {e}")
        return {"score": 50.0, "category": "MODERATE", "factors": {}}


async def _osrm_to_route_option(route_data: dict, route_type: str, profile: str = "driving") -> RouteOption:
    if not route_data:
        return RouteOption(
            type=route_type,
            duration_minutes=0,
            distance_km=0,
            safety_score=0,
            segments=[],
            geometry=[],
        )
    leg = route_data.get("legs", [{}])[0]
    steps = leg.get("steps", [])
    segments = []
    geometry_coords = []
    coords = route_data.get("geometry", {}).get("coordinates", [])
    for coord in coords:
        geometry_coords.append([coord[1], coord[0]])

    total_risk = 0.0
    total_distance = 0.0
    for step in steps:
        seg_coords = step.get("geometry", {}).get("coordinates", [])
        if seg_coords:
            start = seg_coords[0]
            end = seg_coords[-1]
            step_dist = step.get("distance", 0)
            total_distance += step_dist
            seg_result = await _score_segment(start[1], start[0])
            seg_score = seg_result["score"]
            total_risk += seg_score * step_dist
            # Fetch nearby incidents for explanation
            nearby = await _fetch_nearby_incidents(start[1], start[0], 300)
            nearby_categories = [n["category"] for n in nearby if n.get("category")]
            nearby_types = [n["type"] for n in nearby]
            segments.append(RouteSegment(
                start_lat=start[1],
                start_lng=start[0],
                end_lat=end[1],
                end_lng=end[0],
                safety_score=seg_score,
                risk_category=seg_result["category"],
                distance_m=step_dist,
                risk_factors=seg_result.get("factors"),
                nearby_incidents=nearby_categories[:3],
                nearby_types=nearby_types[:3],
            ))

    safety_score = round(total_risk / total_distance, 2) if total_distance > 0 else 50.0
    duration = round((route_data.get("duration", 0) or 0) / 60, 2)
    distance = round(total_distance / 1000, 2)
    profile_label = "Walking" if profile == "walking" else "Driving"

    return RouteOption(
        type=route_type,
        duration_minutes=duration,
        distance_km=distance,
        safety_score=safety_score,
        segments=segments,
        geometry=geometry_coords,
        profile=profile_label,
    )


async def _build_reasons(safest: RouteOption, fastest: RouteOption, balanced: RouteOption, profile: str = "driving") -> str:
    reasons = []
    if safest.safety_score < fastest.safety_score:
        diff = round(fastest.safety_score - safest.safety_score, 1)
        reasons.append(f"{'Walking' if profile == 'walking' else 'Driving'} route avoids {diff} pts higher risk areas")

    # Collect incident-specific details from safest route segments
    total_incidents_avoided = 0
    incident_types_seen = set()
    for seg in safest.segments:
        nearby_types = getattr(seg, "nearby_types", []) or []
        for t in nearby_types:
            incident_types_seen.add(t)
        total_incidents_avoided += len(getattr(seg, "nearby_incidents", []) or [])

    if total_incidents_avoided > 0:
        types_str = ", ".join(list(incident_types_seen)[:3])
        reasons.append(
            f"Route avoids {total_incidents_avoided} recent {types_str.lower()} incidents"
        )

    # Check risk category breakdown for fastest route
    high_risk_segments = [s for s in fastest.segments if s.safety_score > 65] if fastest.segments else []
    mod_risk_segments = [s for s in safest.segments if s.safety_score <= 20] if safest.segments else []

    if high_risk_segments:
        reasons.append(f"Avoids {len(high_risk_segments)} high-risk zones on fastest path")

    if mod_risk_segments:
        reasons.append(f"Passes through {len(mod_risk_segments)} low-risk street segments")

    for seg in safest.segments:
        factors = getattr(seg, "risk_factors", {}) or {}
        police = factors.get("nearby_police_stations", 0)
        if police > 0:
            reasons.append(f"Passes near {police} police station(s)")
            break

    if not reasons:
        reasons.append("Route risk assessment complete")

    return " | ".join(reasons[:5])


def _compute_similarity(r1: dict, r2: dict) -> float:
    c1 = r1.get("geometry", {}).get("coordinates", [])
    c2 = r2.get("geometry", {}).get("coordinates", [])
    if not c1 or not c2:
        return 0.0
    samples = min(10, len(c1), len(c2))
    match_count = 0
    for i in range(samples):
        idx1 = int(i * len(c1) / samples)
        idx2 = int(i * len(c2) / samples)
        p1, p2 = c1[idx1], c2[idx2]
        if abs(p1[0] - p2[0]) < SIMILARITY_THRESHOLD_DEG and abs(p1[1] - p2[1]) < SIMILARITY_THRESHOLD_DEG:
            match_count += 1
    return match_count / samples


@router.post("/safe", response_model=RouteResponse)
async def get_safe_route(
    body: RouteRequest,
    user: User = Depends(get_current_user),
):
    profile = getattr(body, "profile", "driving")
    try:
        osrm_data = await _fetch_route(
            body.source_lat, body.source_lng,
            body.dest_lat, body.dest_lng,
            profile,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Route fetch failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Route calculation failed: {str(e)}")

    routes = osrm_data.get("routes", [])
    if not routes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No route found")

    route_options = []
    for r in routes:
        option = await _osrm_to_route_option(r, "candidate", profile)
        option.safety_score = round(min(100.0, max(0.0, option.safety_score)), 2)
        route_options.append({"data": r, "option": option})

    route_options.sort(key=lambda x: x["option"].duration_minutes)
    fastest_opt = route_options[0]["option"]
    fastest_opt.type = "fastest"

    route_options.sort(key=lambda x: x["option"].safety_score)
    safest_opt = route_options[0]["option"]
    safest_opt.type = "safest"

    if len(route_options) > 1:
        alt_routes = [r for r in route_options if r["option"] is not safest_opt and r["option"] is not fastest_opt]
        if alt_routes:
            alt_routes.sort(key=lambda x: x["option"].safety_score + x["option"].duration_minutes * 0.5)
            balanced_opt = alt_routes[0]["option"]
            balanced_opt.type = "balanced"
        else:
            balanced_opt = fastest_opt
            balanced_opt.type = "balanced"
    else:
        balanced_opt = fastest_opt
        balanced_opt.type = "balanced"

    explanation = await _build_reasons(safest_opt, fastest_opt, balanced_opt, profile)

    return RouteResponse(
        source=(body.source_lat, body.source_lng),
        destination=(body.dest_lat, body.dest_lng),
        safest=safest_opt,
        fastest=fastest_opt,
        balanced=balanced_opt,
        explanation=explanation,
        profile="Walking" if profile == "walking" else "Driving",
    )


@router.get("/health")
async def route_health():
    import httpx
    import time
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{OSRM_BASE_URL}/nearest/v1/driving/77.5946,12.9716",
                timeout=5.0,
            )
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        if resp.status_code == 200:
            status = "degraded" if elapsed_ms > 2000 else "healthy"
            return {
                "status": status,
                "service": "Route Intelligence",
                "provider": "OSRM",
                "response_ms": elapsed_ms,
            }
        logger.warning(f"OSRM probe returned HTTP {resp.status_code}")
        return {
            "status": "degraded",
            "service": "Route Intelligence",
            "provider": "OSRM",
            "detail": f"OSRM returned HTTP {resp.status_code}",
            "response_ms": elapsed_ms,
        }
    except Exception as e:
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        logger.warning(f"OSRM health probe failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "offline",
                "service": "Route Intelligence",
                "provider": "OSRM",
                "detail": str(e),
                "response_ms": elapsed_ms,
            },
        )
