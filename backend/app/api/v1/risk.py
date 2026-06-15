import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_current_user
from app.models.user import User
from app.pipeline.risk import score_location
from app.pipeline.heatmap import get_heatmap_data
from app.pipeline.explain import explain_risk
from app.schemas.risk import (
    RiskScoreRequest,
    RiskScoreResponse,
    HeatmapRequest,
    HeatmapResponse,
    HeatmapPoint,
    DistrictSummary,
    ExplainRequest,
    ExplainResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk", tags=["Risk Assessment"])


def _score_to_heat_attrs(score: float) -> tuple:
    normalized = max(0.0, min(1.0, score / 100.0))
    if normalized >= 0.75:
        t = (normalized - 0.75) / 0.25
        intensity = round(0.8 + t * 0.2, 2)
        radius = min(40 + int(t * 20), 60)
    elif normalized >= 0.5:
        t = (normalized - 0.5) / 0.25
        intensity = round(0.6 + t * 0.2, 2)
        radius = 30 + int(t * 10)
    elif normalized >= 0.25:
        t = (normalized - 0.25) / 0.25
        intensity = round(0.4 + t * 0.2, 2)
        radius = 20 + int(t * 10)
    else:
        t = normalized / 0.25
        intensity = round(0.2 + t * 0.2, 2)
        radius = 10 + int(t * 10)
    return intensity, radius


def _make_heatmap_point(lat: float, lng: float, score: float, category: str) -> HeatmapPoint:
    intensity, radius = _score_to_heat_attrs(score)
    return HeatmapPoint(
        latitude=lat,
        longitude=lng,
        weight=score,
        risk_category=category,
        intensity=intensity,
        radius=radius,
    )


@router.post("/score", response_model=RiskScoreResponse)
async def calculate_risk_score(
    body: RiskScoreRequest,
    user: User = Depends(get_current_user),
):
    try:
        result = await score_location(body.latitude, body.longitude)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Risk scoring failed: {str(e)}")

    return RiskScoreResponse(
        score=result.get("score", 50.0),
        category=result.get("category", "Moderate"),
        factors=result.get("factors", {}),
        recommendations=result.get("recommendations", []),
    )


@router.post("/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    body: HeatmapRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        points_data = await get_heatmap_data(
            body.sw_lat, body.sw_lng,
            body.ne_lat, body.ne_lng,
            min_score=body.min_score,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Heatmap query failed: {str(e)}")

    logger.info(f"[HEATMAP] API endpoint: {len(points_data)} points returned from get_heatmap_data")

    points = [
        _make_heatmap_point(p.get("latitude", 0), p.get("longitude", 0), p.get("score", 50.0), p.get("category", "Moderate"))
        for p in points_data
    ]
    logger.info("[HEATMAP_DEBUG] Returning %s points", len(points))

    district_result = await db.execute(
        text("""
            SELECT district,
                   AVG(confidence_score) as avg_score,
                   COUNT(*) as total_incidents,
                   CASE
                       WHEN AVG(confidence_score) < 30 THEN 'improving'
                       WHEN AVG(confidence_score) < 60 THEN 'stable'
                       ELSE 'worsening'
                   END as trend
            FROM incidents
            WHERE latitude BETWEEN :sw_lat AND :ne_lat
              AND longitude BETWEEN :sw_lng AND :ne_lng
              AND district IS NOT NULL
              AND metadata->>'women_safety_category' IS NOT NULL
            GROUP BY district
        """),
        {"sw_lat": body.sw_lat, "ne_lat": body.ne_lat, "sw_lng": body.sw_lng, "ne_lng": body.ne_lng},
    )
    district_rows = district_result.fetchall()
    logger.info(f"[HEATMAP] district summaries: {len(district_rows)} rows")

    summaries = [
        DistrictSummary(
            district=r[0],
            avg_score=round(float(r[1]), 2),
            total_incidents=int(r[2]),
            trend=r[3],
        )
        for r in district_rows
    ]

    return HeatmapResponse(
        points=points,
        generated_at=datetime.now(timezone.utc).isoformat(),
        district_summaries=summaries if summaries else None,
    )


@router.post("/explain", response_model=ExplainResponse)
async def explain_risk_score(
    body: ExplainRequest,
):
    try:
        result = await explain_risk(body.latitude, body.longitude, body.radius_km)
        return ExplainResponse(**result)
    except Exception as e:
        logger.exception(f"[EXPLAIN] Failed for ({body.latitude}, {body.longitude}): {e}")
        # Return safe default instead of 500 — better to show partial data than crash
        return ExplainResponse(risk_score=50.0, risk_category="Moderate", incident_count=0, sources=[])


@router.get("/district/{district}")
async def get_district_risk(
    district: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("""
            SELECT
                COUNT(*) as total_incidents,
                AVG(CASE
                    WHEN UPPER(severity::text) = 'CRITICAL' THEN 4
                    WHEN UPPER(severity::text) = 'HIGH' THEN 3
                    WHEN UPPER(severity::text) = 'MEDIUM' THEN 2
                    WHEN UPPER(severity::text) = 'LOW' THEN 1
                    ELSE 0
                END) as avg_severity_score,
                COUNT(*) FILTER (WHERE UPPER(severity::text) IN ('HIGH', 'CRITICAL')) as high_risk_count,
                COUNT(*) FILTER (WHERE UPPER(severity::text) = 'MEDIUM') as medium_risk_count,
                COUNT(*) FILTER (WHERE UPPER(severity::text) = 'LOW') as low_risk_count
            FROM incidents
            WHERE district = :district
              AND UPPER(status::text) != 'DISMISSED'
              AND metadata->>'women_safety_category' IS NOT NULL
        """),
        {"district": district},
    )
    row = result.fetchone()
    if not row or row[0] == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data found for district")

    avg_severity = float(row[1]) if row[1] else 0
    risk_score = min(100, (avg_severity / 4.0) * 100)
    if risk_score <= 30:
        category = "Safe"
    elif risk_score <= 60:
        category = "Moderate"
    else:
        category = "High Risk"

    return {
        "district": district,
        "risk_score": round(risk_score, 2),
        "risk_category": category,
        "total_incidents": int(row[0]),
        "high_risk_incidents": int(row[2]),
        "medium_risk_incidents": int(row[3]),
        "low_risk_incidents": int(row[4]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
