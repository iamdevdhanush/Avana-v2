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
from app.schemas.risk import (
    RiskScoreRequest,
    RiskScoreResponse,
    HeatmapRequest,
    HeatmapResponse,
    HeatmapPoint,
    DistrictSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/risk", tags=["Risk Assessment"])


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
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Heatmap query failed: {str(e)}")

    logger.info(f"[HEATMAP] API endpoint: {len(points_data)} points returned from get_heatmap_data")

    points = [
        HeatmapPoint(
            latitude=p.get("latitude", 0),
            longitude=p.get("longitude", 0),
            weight=p.get("score", 50.0),
            risk_category=p.get("category", "Moderate"),
        )
        for p in points_data
    ]

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
            WHERE district = :district AND UPPER(status::text) != 'DISMISSED'
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
