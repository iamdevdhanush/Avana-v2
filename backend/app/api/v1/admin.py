import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.incident import Incident, IncidentStatus
from app.models.safety_report import SafetyReport
from app.models.user import User, UserRole
from app.schemas.admin import (
    ModerateAction,
    UserManagementResponse,
)
from app.schemas.analytics import DashboardStats, DistrictStats, TypeStats, TrendPoint, AlertItem
from app.pipeline.intelligence import run_intelligence_pipeline
from app.pipeline.community import process_pending_reports
from app.pipeline.risk import recalculate_all_risk_scores
from app.pipeline.heatmap import generate_heatmap_for_bounds

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard", response_model=DashboardStats)
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
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
        text("SELECT incident_type, COUNT(*) as cnt FROM incidents GROUP BY incident_type ORDER BY cnt DESC")
    )
    incidents_by_type = [
        TypeStats(incident_type=r[0], count=int(r[1]), percentage=round(int(r[1]) / total_all * 100, 1))
        for r in by_type.fetchall()
    ]

    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    risk_trend_rows = await db.execute(
        text("SELECT DATE(created_at) as dt, AVG(confidence_score) FROM incidents WHERE created_at >= :start GROUP BY dt ORDER BY dt"),
        {"start": thirty_days_ago},
    )
    risk_trend = [TrendPoint(date=str(r[0]), value=float(r[1]) if r[1] else 0) for r in risk_trend_rows.fetchall()]

    inc_trend_rows = await db.execute(
        text("SELECT DATE(created_at) as dt, COUNT(*) FROM incidents WHERE created_at >= :start GROUP BY dt ORDER BY dt"),
        {"start": thirty_days_ago},
    )
    incidents_trend = [TrendPoint(date=str(r[0]), value=float(r[1])) for r in inc_trend_rows.fetchall()]

    recent_alerts_rows = await db.execute(
        text("""
            SELECT id, incident_type, severity, district, created_at, status
            FROM incidents WHERE severity IN ('high','critical') AND created_at >= :start
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


@router.get("/incidents")
async def list_incidents_moderation(
    status: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = select(Incident).order_by(Incident.created_at.desc())
    if status:
        query = query.where(Incident.status == status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    incidents = result.scalars().all()

    return {
        "items": [
            {
                "id": str(inc.id),
                "incident_type": inc.incident_type.value if hasattr(inc.incident_type, "value") else inc.incident_type,
                "severity": inc.severity.value if hasattr(inc.severity, "value") else inc.severity,
                "source": inc.source.value if hasattr(inc.source, "value") else inc.source,
                "status": inc.status.value if hasattr(inc.status, "value") else inc.status,
                "latitude": inc.latitude,
                "longitude": inc.longitude,
                "description": inc.description,
                "district": inc.district,
                "city": inc.city,
                "confidence_score": inc.confidence_score,
                "created_at": inc.created_at.isoformat(),
            }
            for inc in incidents
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/incidents/{id}/moderate")
async def moderate_incident(
    id: uuid.UUID,
    body: ModerateAction,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(Incident).where(Incident.id == id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    try:
        incident.status = IncidentStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {body.status}")

    incident.moderated_by = admin.id
    incident.updated_at = datetime.now(timezone.utc)
    await db.flush()

    return {
        "id": str(incident.id),
        "status": incident.status.value if hasattr(incident.status, "value") else incident.status,
        "moderated_by": str(admin.id),
        "moderation_notes": body.moderation_notes,
    }


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = select(User).order_by(User.created_at.desc())
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()

    items = []
    for u in users:
        reports_q = await db.execute(
            select(func.count()).where(SafetyReport.user_id == u.id)
        )
        total_reports = reports_q.scalar() or 0
        items.append(
            UserManagementResponse(
                id=u.id,
                email=u.email,
                name=u.name,
                role=u.role.value if hasattr(u.role, "value") else u.role,
                is_active=u.is_active,
                is_verified=u.is_verified,
                total_reports=total_reports,
                created_at=u.created_at,
            )
        )

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.put("/users/{id}/role")
async def change_user_role(
    id: uuid.UUID,
    role: str = Query(..., description="New role: user, admin, moderator"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        user.role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {role}")

    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"id": str(user.id), "role": user.role.value if hasattr(user.role, "value") else user.role}


@router.put("/users/{id}/status")
async def change_user_status(
    id: uuid.UUID,
    is_active: bool = Query(..., description="Set user active or inactive"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = is_active
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return {"id": str(user.id), "is_active": user.is_active}


@router.get("/pipeline/status")
async def get_pipeline_status(
    admin: User = Depends(require_admin),
):
    return {
        "pipelines": [
            {"name": "intelligence", "status": "idle", "schedule_minutes": 360},
            {"name": "community", "status": "idle", "schedule_minutes": 5},
            {"name": "risk_scoring", "status": "available"},
            {"name": "heatmap", "status": "idle"},
        ],
        "pipeline": "operational",
    }


@router.post("/pipeline/run/{pipeline_name}")
async def run_pipeline(
    pipeline_name: str,
    admin: User = Depends(require_admin),
):
    pipeline_map = {
        "intelligence": run_intelligence_pipeline,
        "community": process_pending_reports,
        "risk": recalculate_all_risk_scores,
    }

    runner = pipeline_map.get(pipeline_name)
    if not runner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown pipeline: {pipeline_name}. Available: {list(pipeline_map.keys())}",
        )

    try:
        result = await runner()
        return {"pipeline": pipeline_name, "status": "triggered", "result": result}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline run failed: {str(e)}",
        )
