import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.route import (
    RouteRequest,
    RouteResponse,
    RouteOption,
    RouteSegment,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/route", tags=["Route Intelligence"])

OSRM_BASE_URL = "https://router.project-osrm.org"


async def _fetch_route(source_lat: float, source_lng: float, dest_lat: float, dest_lng: float) -> dict:
    import asyncio
    import httpx
    url = (
        f"{OSRM_BASE_URL}/route/v1/driving/"
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


def _osrm_to_route_option(route_data: dict, route_type: str) -> RouteOption:
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

    for step in steps:
        seg_coords = step.get("geometry", {}).get("coordinates", [])
        if seg_coords:
            start = seg_coords[0]
            end = seg_coords[-1]
            intersection = step.get("intersections", [{}])[0]
            segments.append(RouteSegment(
                start_lat=start[1],
                start_lng=start[0],
                end_lat=end[1],
                end_lng=end[0],
                safety_score=50.0,
                risk_category="Moderate",
                distance_m=step.get("distance", 0),
            ))

    duration = round((route_data.get("duration", 0) or 0) / 60, 2)
    distance = round((route_data.get("distance", 0) or 0) / 1000, 2)

    return RouteOption(
        type=route_type,
        duration_minutes=duration,
        distance_km=distance,
        safety_score=50.0,
        segments=segments,
        geometry=geometry_coords,
    )


@router.post("/safe", response_model=RouteResponse)
async def get_safe_route(
    body: RouteRequest,
    user: User = Depends(get_current_user),
):
    try:
        osrm_data = await _fetch_route(
            body.source_lat, body.source_lng,
            body.dest_lat, body.dest_lng,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Route fetch failed")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Route calculation failed: {str(e)}")

    routes = osrm_data.get("routes", [])
    if not routes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No route found")

    sorted_routes = sorted(routes, key=lambda r: r.get("duration", float("inf")))

    return RouteResponse(
        source=(body.source_lat, body.source_lng),
        destination=(body.dest_lat, body.dest_lng),
        safest=_osrm_to_route_option(sorted_routes[0], "safest"),
        fastest=_osrm_to_route_option(sorted_routes[0] if len(sorted_routes) == 1 else sorted_routes[0], "fastest"),
        balanced=_osrm_to_route_option(sorted_routes[-1] if len(sorted_routes) > 1 else sorted_routes[0], "balanced"),
    )


@router.get("/health")
async def route_health():
    return {
        "status": "healthy",
        "service": "Route Intelligence",
        "provider": "OSRM",
    }
