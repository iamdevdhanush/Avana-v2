from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin, require_user
from app.models.user import User
from app.schemas.analytics import (
    DashboardStats,
    DistrictStats,
    TypeStats,
    TrendPoint,
    AlertItem,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    total_inc = await db.execute(text("SELECT COUNT(*) FROM incidents"))
    total_incidents = total_inc.scalar() or 0

    active = await db.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true"))
    active_users = active.scalar() or 0

    sos = await db.execute(text("SELECT COUNT(*) FROM sos_events"))
    sos_events = sos.scalar() or 0

    verified = await db.execute(text("SELECT COUNT(*) FROM incidents WHERE status = 'verified'"))
    verified_reports = verified.scalar() or 0

    by_district = await db.execute(
        text("""
            SELECT district, COUNT(*) as total,
                   COUNT(*) FILTER (WHERE severity IN ('high','critical')) as high_risk,
                   COUNT(*) FILTER (WHERE severity = 'medium') as medium_risk,
                   COUNT(*) FILTER (WHERE severity = 'low') as low_risk,
                   AVG(CASE
                       WHEN severity = 'critical' THEN 4
                       WHEN severity = 'high' THEN 3
                       WHEN severity = 'medium' THEN 2
                       WHEN severity = 'low' THEN 1
                       ELSE 0
                   END) as avg_score
            FROM incidents WHERE district IS NOT NULL
            GROUP BY district ORDER BY total DESC LIMIT 20
        """)
    )
    incidents_by_district = [
        DistrictStats(
            district=r[0],
            total=int(r[1]),
            high_risk=int(r[2]),
            medium_risk=int(r[3]),
            low_risk=int(r[4]),
            avg_score=round(float(r[5]) / 4.0 * 100, 2) if r[5] else 0,
        )
        for r in by_district.fetchall()
    ]

    total_all = max(total_incidents, 1)
    by_type = await db.execute(
        text("""
            SELECT incident_type, COUNT(*) as cnt
            FROM incidents GROUP BY incident_type ORDER BY cnt DESC
        """)
    )
    incidents_by_type = [
        TypeStats(incident_type=r[0], count=int(r[1]), percentage=round(int(r[1]) / total_all * 100, 1))
        for r in by_type.fetchall()
    ]

    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    risk_trend_rows = await db.execute(
        text("""
            SELECT DATE(created_at) as dt, AVG(confidence_score) as avg_conf
            FROM incidents WHERE created_at >= :start
            GROUP BY dt ORDER BY dt
        """),
        {"start": thirty_days_ago},
    )
    risk_trend = [
        TrendPoint(date=str(r[0]), value=float(r[1]) if r[1] else 0)
        for r in risk_trend_rows.fetchall()
    ]

    inc_trend_rows = await db.execute(
        text("""
            SELECT DATE(created_at) as dt, COUNT(*) as cnt
            FROM incidents WHERE created_at >= :start
            GROUP BY dt ORDER BY dt
        """),
        {"start": thirty_days_ago},
    )
    incidents_trend = [
        TrendPoint(date=str(r[0]), value=float(r[1]))
        for r in inc_trend_rows.fetchall()
    ]

    recent_alerts_rows = await db.execute(
        text("""
            SELECT id, incident_type, severity, district, created_at, status
            FROM incidents
            WHERE severity IN ('high', 'critical') AND created_at >= :start
            ORDER BY created_at DESC LIMIT 20
        """),
        {"start": thirty_days_ago},
    )
    recent_alerts = [
        AlertItem(id=r[0], type=r[1], severity=r[2], district=r[3] or "Unknown", time=r[4], status=r[5])
        for r in recent_alerts_rows.fetchall()
    ]

    return DashboardStats(
        total_incidents=total_incidents,
        active_users=active_users,
        sos_events=sos_events,
        verified_reports=verified_reports,
        incidents_by_district=incidents_by_district,
        incidents_by_type=incidents_by_type,
        risk_trend=risk_trend,
        incidents_trend=incidents_trend,
        recent_alerts=recent_alerts,
    )


@router.get("/districts")
async def get_district_analytics(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    result = await db.execute(
        text("""
            SELECT district,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE severity IN ('high','critical')) as high_risk,
                   COUNT(*) FILTER (WHERE severity = 'medium') as medium_risk,
                   COUNT(*) FILTER (WHERE severity = 'low') as low_risk,
                   MIN(created_at) as first_incident,
                   MAX(created_at) as last_incident
            FROM incidents
            WHERE district IS NOT NULL
            GROUP BY district
            ORDER BY total DESC
        """)
    )
    rows = result.fetchall()
    return [
        {
            "district": r[0],
            "total_incidents": int(r[1]),
            "high_risk": int(r[2]),
            "medium_risk": int(r[3]),
            "low_risk": int(r[4]),
            "first_incident": r[5].isoformat() if r[5] else None,
            "last_incident": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]


@router.get("/trends")
async def get_trends(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = await db.execute(
        text("""
            SELECT DATE(created_at) as dt,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE severity IN ('high','critical')) as high_risk_count,
                   COUNT(*) FILTER (WHERE source = 'news') as news_count,
                   COUNT(*) FILTER (WHERE source = 'user_report') as user_report_count
            FROM incidents
            WHERE created_at >= :start
            GROUP BY dt
            ORDER BY dt
        """),
        {"start": start},
    )
    rows = result.fetchall()
    return {
        "period_days": days,
        "data": [
            {
                "date": str(r[0]),
                "total": int(r[1]),
                "high_risk": int(r[2]),
                "news_sourced": int(r[3]),
                "user_reported": int(r[4]),
            }
            for r in rows
        ],
    }


@router.get("/reports")
async def get_report_analytics(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin),
):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = await db.execute(
        text("""
            SELECT DATE(created_at) as dt,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE status = 'approved') as approved,
                   COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
                   COUNT(*) FILTER (WHERE status = 'pending') as pending
            FROM safety_reports
            WHERE created_at >= :start
            GROUP BY dt
            ORDER BY dt
        """),
        {"start": start},
    )
    rows = result.fetchall()
    return {
        "period_days": days,
        "data": [
            {
                "date": str(r[0]),
                "total": int(r[1]),
                "approved": int(r[2]),
                "rejected": int(r[3]),
                "pending": int(r[4]),
            }
            for r in rows
        ],
    }
