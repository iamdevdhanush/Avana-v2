from fastapi import APIRouter, Depends, HTTPException, status

from app.agents.route_intelligence import run as route_run
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.route import (
    RouteRequest,
    RouteResponse,
    RouteOption,
    RouteSegment,
)

router = APIRouter(prefix="/route", tags=["Route Intelligence"])


@router.post("/safe", response_model=RouteResponse)
async def get_safe_route(
    body: RouteRequest,
    user: User = Depends(get_current_user),
):
    try:
        result = await route_run(
            (body.source_lat, body.source_lng),
            (body.dest_lat, body.dest_lng),
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Route calculation failed: {str(e)}")

    def _build_option(route_data: dict, route_type: str) -> RouteOption:
        if not route_data:
            return RouteOption(
                type=route_type,
                duration_minutes=0,
                distance_km=0,
                safety_score=0,
                segments=[],
                geometry=[],
            )
        segments = [
            RouteSegment(
                start_lat=s.get("start", [0, 0])[0],
                start_lng=s.get("start", [0, 0])[1],
                end_lat=s.get("end", [0, 0])[0],
                end_lng=s.get("end", [0, 0])[1],
                safety_score=s.get("score", 50.0),
                risk_category=s.get("risk_category", "Moderate"),
                distance_m=s.get("length_meters", 0),
            )
            for s in (route_data.get("segments") or [])
        ]
        return RouteOption(
            type=route_type,
            duration_minutes=round((route_data.get("duration_seconds", 0) or 0) / 60, 2),
            distance_km=round((route_data.get("distance_meters", 0) or 0) / 1000, 2),
            safety_score=route_data.get("avg_safety_score", 50.0),
            segments=segments,
            geometry=[],
        )

    return RouteResponse(
        source=(body.source_lat, body.source_lng),
        destination=(body.dest_lat, body.dest_lng),
        safest=_build_option(result.get("safest_route"), "safest"),
        fastest=_build_option(result.get("fastest_route"), "fastest"),
        balanced=_build_option(result.get("balanced_route"), "balanced"),
    )


@router.get("/health")
async def route_health():
    return {
        "status": "healthy",
        "service": "Route Intelligence",
        "provider": "OSRM",
    }
