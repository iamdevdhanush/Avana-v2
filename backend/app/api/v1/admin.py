import uuid
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_admin
from app.models.audit_log import AuditLog
from app.models.incident import Incident, IncidentStatus
from app.models.safety_report import SafetyReport
from app.models.user import User, UserRole
from app.schemas.admin import (
    ModerateAction,
    UserManagementResponse,
)
from app.schemas.analytics import DashboardStats, DistrictStats, TypeStats, TrendPoint, AlertItem
# Agent orchestrator — primary execution path
from app.pipeline.orchestrator import orchestrator as _orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])

# TASK 7: Pipeline execution lock — prevents concurrent runs
_pipeline_locks: dict[str, asyncio.Lock] = {}

async def _acquire_pipeline_lock(pipeline_name: str) -> bool:
    """Try to acquire pipeline lock. Returns True if acquired, False if already running."""
    if pipeline_name not in _pipeline_locks:
        _pipeline_locks[pipeline_name] = asyncio.Lock()
    lock = _pipeline_locks[pipeline_name]
    acquired = await lock.acquire() if not lock.locked() else False
    if acquired:
        logger.info(f"[LOCK] Pipeline '{pipeline_name}' lock acquired")
    else:
        logger.warning(f"[LOCK] Pipeline '{pipeline_name}' already running — rejected")
    return acquired

def _release_pipeline_lock(pipeline_name: str):
    lock = _pipeline_locks.get(pipeline_name)
    if lock and lock.locked():
        lock.release()
        logger.info(f"[LOCK] Pipeline '{pipeline_name}' lock released")


async def _log_admin_action(
    request: Request,
    db: AsyncSession,
    admin: User,
    action: str,
    resource_type: str,
    resource_id: str = None,
    details: dict = None,
    severity: str = "info",
):
    log = AuditLog(
        id=uuid.uuid4(),
        user_id=admin.id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500],
        severity=severity,
    )
    db.add(log)


@router.get("/dashboard", response_model=DashboardStats)
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    total_inc = await db.execute(text("SELECT COUNT(*) FROM incidents"))
    total_incidents = total_inc.scalar() or 0
    logger.info(f"[DASHBOARD] total incidents: {total_incidents}")

    active = await db.execute(text("SELECT COUNT(*) FROM users WHERE is_active = true"))
    active_users = active.scalar() or 0

    sos = await db.execute(text("SELECT COUNT(*) FROM sos_events"))
    sos_events = sos.scalar() or 0

    verified = await db.execute(text("SELECT COUNT(*) FROM incidents WHERE UPPER(status::text) = 'VERIFIED'"))
    verified_reports = verified.scalar() or 0

    by_district = await db.execute(
        text("""
            SELECT district, COUNT(*) as total,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) IN ('HIGH','CRITICAL')) as high_risk,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) = 'MEDIUM') as medium_risk,
                   COUNT(*) FILTER (WHERE UPPER(severity::text) = 'LOW') as low_risk,
                   AVG(CASE
                       WHEN UPPER(severity::text) = 'CRITICAL' THEN 4
                       WHEN UPPER(severity::text) = 'HIGH' THEN 3
                       WHEN UPPER(severity::text) = 'MEDIUM' THEN 2
                       WHEN UPPER(severity::text) = 'LOW' THEN 1
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
    logger.info(f"[DASHBOARD] district count: {len(incidents_by_district)}")

    total_all = max(total_incidents, 1)
    by_type = await db.execute(
        text("SELECT incident_type, COUNT(*) as cnt FROM incidents GROUP BY incident_type ORDER BY cnt DESC")
    )
    incidents_by_type = [
        TypeStats(incident_type=r[0], count=int(r[1]), percentage=round(int(r[1]) / total_all * 100, 1))
        for r in by_type.fetchall()
    ]

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
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
    logger.info(f"[DASHBOARD] trend count: {len(incidents_trend)}")

    recent_alerts_rows = await db.execute(
        text("""
            SELECT id, incident_type, severity, district, created_at, status
            FROM incidents WHERE UPPER(severity::text) IN ('HIGH','CRITICAL') AND created_at >= :start
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


@router.get("/metrics")
async def admin_metrics(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM incidents) as total_incidents,
                (SELECT COUNT(*) FROM incidents WHERE created_at >= NOW() - INTERVAL '24 hours') as incidents_24h,
                (SELECT COUNT(*) FROM incidents WHERE created_at >= NOW() - INTERVAL '7 days') as incidents_7d,
                (SELECT COUNT(*) FROM risk_scores) as risk_score_count,
                (SELECT COUNT(*) FROM risk_scores WHERE calculated_at >= NOW() - INTERVAL '48 hours') as risk_scores_fresh,
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM users WHERE is_active = true) as active_users,
                (SELECT COUNT(*) FROM sos_events) as sos_events,
                (SELECT COUNT(*) FROM safety_reports) as safety_reports,
                (SELECT COUNT(*) FROM audit_logs WHERE created_at >= NOW() - INTERVAL '7 days') as audit_logs_7d
        """)
    )
    row = result.fetchone()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_incidents": int(row[0]),
        "incidents_24h": int(row[1]),
        "incidents_7d": int(row[2]),
        "risk_score_count": int(row[3]),
        "risk_scores_fresh_48h": int(row[4]),
        "total_users": int(row[5]),
        "active_users": int(row[6]),
        "sos_events": int(row[7]),
        "safety_reports": int(row[8]),
        "audit_logs_7d": int(row[9]),
    }


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
    request: Request,
    body: ModerateAction,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(Incident).where(Incident.id == id))
    incident = result.scalar_one_or_none()
    if not incident:
        logger.warning(f"[MODERATE] Incident {id} not found — admin={admin.email}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    logger.info(
        f"[MODERATE] admin={admin.email} incident={id} "
        f"requested_status={body.status} current_status={incident.status.value}"
    )

    try:
        incident.status = IncidentStatus(body.status)
    except ValueError:
        logger.error(f"[MODERATE] Invalid status '{body.status}' for incident {id}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {body.status}")

    incident.moderated_by = admin.id
    incident.updated_at = datetime.now(timezone.utc)
    if body.moderation_notes:
        meta = dict(incident.meta_data or {})
        meta["review_notes"] = body.moderation_notes
        meta["reviewed_at"] = datetime.now(timezone.utc).isoformat()
        meta["reviewed_by"] = str(admin.id)
        incident.meta_data = meta
    await _log_admin_action(request, db, admin, "moderate_incident", "incident", str(incident.id), {
        "status": body.status, "notes": body.moderation_notes,
    })
    await db.flush()

    logger.info(
        f"[MODERATE] SUCCESS: incident={id} "
        f"from={incident.status.value} to={body.status} "
        f"by={admin.email}"
    )

    return {
        "id": str(incident.id),
        "status": incident.status.value if hasattr(incident.status, "value") else incident.status,
        "moderated_by": str(admin.id),
        "moderation_notes": body.moderation_notes,
        "review_complete": body.status in ("VERIFIED", "DISMISSED", "DUPLICATE", "SPAM", "RESOLVED"),
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
    request: Request,
    role: str = Query(..., description="New role: user, admin, moderator"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_role = user.role.value if hasattr(user.role, "value") else user.role
    try:
        user.role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role: {role}")

    user.updated_at = datetime.now(timezone.utc)
    await _log_admin_action(request, db, admin, "change_user_role", "user", str(user.id), {
        "old_role": old_role, "new_role": role,
    })
    await db.flush()
    return {"id": str(user.id), "role": user.role.value if hasattr(user.role, "value") else user.role}


@router.put("/users/{id}/status")
async def change_user_status(
    id: uuid.UUID,
    request: Request,
    is_active: bool = Query(..., description="Set user active or inactive"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_status = user.is_active
    user.is_active = is_active
    user.updated_at = datetime.now(timezone.utc)
    await _log_admin_action(request, db, admin, "change_user_status", "user", str(user.id), {
        "old_active": old_status, "new_active": is_active,
    })
    await db.flush()
    return {"id": str(user.id), "is_active": user.is_active}


@router.get("/pipeline/status")
async def get_pipeline_status(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Returns pipeline status enriched with last-run data from audit_logs."""
    # Fetch last run timestamps for each pipeline from audit_logs
    last_runs = await db.execute(
        text("""
            SELECT resource_id, MAX(created_at) as last_run,
                   (array_agg(details ORDER BY created_at DESC))[1] as last_details
            FROM audit_logs
            WHERE action = 'run_pipeline'
              AND severity = 'info'
            GROUP BY resource_id
        """)
    )
    last_run_map = {}
    for row in last_runs.fetchall():
        last_run_map[row[0]] = {
            "last_run": row[1].isoformat() if row[1] else None,
            "details": row[2] or {},
        }

    pipelines = [
        {"name": "intelligence", "status": "idle", "schedule_minutes": 360},
        {"name": "community",    "status": "idle", "schedule_minutes": 5},
        {"name": "risk_scoring", "status": "available"},
        {"name": "heatmap",      "status": "idle"},
    ]
    for p in pipelines:
        run_info = last_run_map.get(p["name"])
        if run_info:
            p["last_run_at"] = run_info["last_run"]
            p["last_run_details"] = run_info["details"]

    return {
        "pipelines": pipelines,
        "pipeline": "operational",
    }


@router.post("/pipeline/run/{pipeline_name}")
async def run_pipeline(
    pipeline_name: str,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a named intelligence pipeline via the PipelineOrchestrator.

    Supported names: news | community | risk | heatmap
    Legacy aliases: intelligence → news

    Execution is recorded in pipeline_runs table for full observability.
    """
    # Legacy name alias for backward compatibility
    _name_map = {"intelligence": "news"}
    resolved_name = _name_map.get(pipeline_name, pipeline_name)

    _valid = {"news", "community", "risk", "heatmap"}
    if resolved_name not in _valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown pipeline: '{pipeline_name}'. Available: intelligence, news, community, risk, heatmap",
        )

    acquired = await _acquire_pipeline_lock(resolved_name)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": f"Pipeline '{resolved_name}' is already running"},
        )

    try:
        from app.utils.timing import Timer
        with Timer("1. PIPELINE ENDPOINT (_orchestrator.run)"):
            result = await _orchestrator.run(
                pipeline_name=resolved_name,
                triggered_by=f"admin:{admin.email}",
            )

        # Persist audit log entry (keeps existing audit trail working)
        summary = result.get("summary", {})
        steps = result.get("steps", {})
        log_details = {
            "pipeline": resolved_name,
            "status": result.get("status", "completed"),
            "run_id": result.get("run_id"),
            "articles_fetched": summary.get("articles_fetched", 0),
            "incidents_extracted": summary.get("incidents_extracted", 0),
            "incidents_created": summary.get("incidents_saved", 0),
            "risk_scores_updated": summary.get("risk_scores_updated", 0),
            "heatmap_cells_updated": summary.get("heatmap_points", 0),
            "duration_seconds": result.get("duration_seconds", 0),
            "failed_steps": summary.get("failed_steps", []),
        }
        action = "run_pipeline" if result.get("status") != "failed" else "run_pipeline_failed"
        severity = "info" if result.get("status") != "failed" else "error"
        await _log_admin_action(
            request, db, admin, action, "pipeline",
            resolved_name, log_details, severity=severity,
        )
        await db.commit()

        return {
            "pipeline": resolved_name,
            "status": result.get("status", "completed"),
            "run_id": result.get("run_id"),
            "result": result,
        }

    except Exception as exc:
        await _log_admin_action(
            request, db, admin, "run_pipeline_failed", "pipeline",
            resolved_name,
            {"pipeline": resolved_name, "status": "failed", "error": str(exc)},
            "error",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline run failed: {exc}",
        )
    finally:
        _release_pipeline_lock(resolved_name)


@router.get("/pipeline/last-run")
async def get_last_pipeline_run(
    pipeline_name: str = "intelligence",
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Returns the most recent pipeline execution summary from audit_logs."""
    result = await db.execute(
        text("""
            SELECT details, created_at
            FROM audit_logs
            WHERE action = 'run_pipeline'
              AND resource_id = :name
              AND severity = 'info'
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"name": pipeline_name},
    )
    row = result.fetchone()
    if not row:
        return {"found": False, "pipeline": pipeline_name}
    return {
        "found": True,
        "pipeline": pipeline_name,
        "ran_at": row[1].isoformat() if row[1] else None,
        **row[0],
    }


@router.get("/debug/heatmap-state")
async def debug_heatmap_state(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Diagnostic endpoint: dump incident + risk_score state to find production/localhost mismatches."""
    result = {}

    # Total incidents
    total_inc = await db.execute(text("SELECT COUNT(*) FROM incidents"))
    result["incidents_total"] = total_inc.scalar() or 0

    # Incidents with coordinates
    with_coords = await db.execute(text("SELECT COUNT(*) FROM incidents WHERE latitude IS NOT NULL AND longitude IS NOT NULL"))
    result["incidents_geocoded"] = with_coords.scalar() or 0

    # Incidents with no coordinates
    no_coords = await db.execute(text("SELECT COUNT(*) FROM incidents WHERE latitude IS NULL OR longitude IS NULL"))
    result["incidents_no_coords"] = no_coords.scalar() or 0

    # Incidents with women_safety_category
    ws_inc = await db.execute(text("SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NOT NULL"))
    result["incidents_with_women_safety"] = ws_inc.scalar() or 0

    # Incidents by source
    by_source = await db.execute(text("SELECT source, COUNT(*) FROM incidents GROUP BY source"))
    result["incidents_by_source"] = {str(r[0]): int(r[1]) for r in by_source.fetchall()}

    # Districts with incidents
    districts = await db.execute(text("""
        SELECT district, COUNT(*),
               COUNT(*) FILTER (WHERE metadata->>'women_safety_category' IS NOT NULL) as ws_count
        FROM incidents WHERE district IS NOT NULL
        GROUP BY district ORDER BY COUNT(*) DESC
    """))
    result["districts"] = [
        {"district": str(r[0]), "total": int(r[1]), "with_women_safety": int(r[2])}
        for r in districts.fetchall()
    ]

    # Sample incidents (first 5)
    samples = await db.execute(text("""
        SELECT id, incident_type, severity, latitude, longitude,
               metadata->>'women_safety_category' as ws_cat,
               district, city, created_at
        FROM incidents ORDER BY created_at DESC LIMIT 5
    """))
    result["sample_incidents"] = []
    for r in samples.fetchall():
        result["sample_incidents"].append({
            "id": str(r[0]),
            "incident_type": str(r[1]),
            "severity": str(r[2]),
            "latitude": float(r[3]) if r[3] else None,
            "longitude": float(r[4]) if r[4] else None,
            "women_safety_category": str(r[5]) if r[5] else None,
            "district": str(r[6]) if r[6] else None,
            "city": str(r[7]) if r[7] else None,
            "created_at": r[8].isoformat() if r[8] else None,
        })

    # Risk scores
    total_rs = await db.execute(text("SELECT COUNT(*) FROM risk_scores"))
    result["risk_scores_total"] = total_rs.scalar() or 0

    fresh_rs = await db.execute(text("SELECT COUNT(*) FROM risk_scores WHERE calculated_at >= NOW() - INTERVAL '48 hours'"))
    result["risk_scores_recent_48h"] = fresh_rs.scalar() or 0

    stale_rs = await db.execute(text("SELECT COUNT(*) FROM risk_scores WHERE calculated_at < NOW() - INTERVAL '7 days'"))
    result["risk_scores_stale_7d"] = stale_rs.scalar() or 0

    # Risk score sample
    rs_samples = await db.execute(text("""
        SELECT latitude, longitude, score, category, calculated_at
        FROM risk_scores ORDER BY calculated_at DESC LIMIT 10
    """))
    result["sample_risk_scores"] = [
        {
            "latitude": float(r[0]),
            "longitude": float(r[1]),
            "score": float(r[2]),
            "category": str(r[3]),
            "calculated_at": r[4].isoformat() if r[4] else None,
        }
        for r in rs_samples.fetchall()
    ]

    # Latest pipeline run
    last_run = await db.execute(text("""
        SELECT details, created_at FROM audit_logs
        WHERE action IN ('run_pipeline', 'run_pipeline_failed', 'run_pipeline_skipped')
        ORDER BY created_at DESC LIMIT 1
    """))
    row = last_run.fetchone()
    if row:
        result["last_pipeline_run"] = {
            "at": row[1].isoformat() if row[1] else None,
            "details": row[0] if row[0] else {},
        }
    else:
        result["last_pipeline_run"] = None

    return result


@router.get("/debug/data-integrity")
async def debug_data_integrity(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Diagnostic endpoint: dump exact incident vs risk_score state per user request."""
    result = {}

    # Mock mode status
    from app.config import settings
    result["mock_mode_enabled"] = settings.MOCK_INTELLIGENCE_MODE

    # AI provider status
    from app.services.ai.factory import get_ai_provider
    ai = get_ai_provider()
    ai_status = ai.get_status()
    result["ai_provider"] = ai.name
    result["ai_status"] = ai_status.get("status", "unknown")
    result["ai_error"] = ai_status.get("error")


    # Incident counts
    total_inc = await db.execute(text("SELECT COUNT(*) FROM incidents"))
    result["incidents_total"] = total_inc.scalar() or 0

    geocoded = await db.execute(text("SELECT COUNT(*) FROM incidents WHERE latitude IS NOT NULL AND longitude IS NOT NULL"))
    result["incidents_geocoded"] = geocoded.scalar() or 0

    missing = await db.execute(text("SELECT COUNT(*) FROM incidents WHERE latitude IS NULL OR longitude IS NULL"))
    result["incidents_missing_coords"] = missing.scalar() or 0

    ws = await db.execute(text("SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NOT NULL"))
    result["incidents_with_women_safety"] = ws.scalar() or 0

    no_ws = await db.execute(text("SELECT COUNT(*) FROM incidents WHERE metadata->>'women_safety_category' IS NULL"))
    result["incidents_without_women_safety"] = no_ws.scalar() or 0

    by_source = await db.execute(text("SELECT source, COUNT(*) FROM incidents GROUP BY source"))
    result["incidents_by_source"] = {str(r[0]): int(r[1]) for r in by_source.fetchall()}

    # Risk score counts
    total_rs = await db.execute(text("SELECT COUNT(*) FROM risk_scores"))
    result["risk_scores_total"] = total_rs.scalar() or 0

    fresh_rs = await db.execute(text("SELECT COUNT(*) FROM risk_scores WHERE calculated_at >= NOW() - INTERVAL '48 hours'"))
    result["risk_scores_recent_48h"] = fresh_rs.scalar() or 0

    # Check if risk_scores come from real data or bootstrap
    # Bootstrap points have specific hardcoded coords; real ones generated from incidents
    bootstrap_coords = [
        (12.9716, 77.5946), (12.2958, 76.6394), (12.9141, 74.8560),
        (15.3647, 75.1240), (17.3290, 76.8344), (14.4419, 75.9172),
        (15.8573, 74.5069), (15.8497, 74.4977), (13.3409, 74.7421),
        (13.9299, 75.5681),
    ]
    for lat, lng in bootstrap_coords:
        match_rs = await db.execute(
            text("SELECT COUNT(*) FROM risk_scores WHERE ABS(latitude - :lat) < 0.001 AND ABS(longitude - :lng) < 0.001"),
            {"lat": lat, "lng": lng},
        )
        if (match_rs.scalar() or 0) > 0:
            result["risk_scores_source"] = "BOOTSTRAP_FALLBACK"
            result["risk_scores_bootstrap_match"] = {"lat": lat, "lng": lng}
            break
    else:
        result["risk_scores_source"] = "REAL_INCIDENTS"

    # Sample 5 incidents
    samples = await db.execute(text("""
        SELECT id, incident_type, severity, latitude, longitude,
               metadata->>'women_safety_category' as ws_cat,
               district, city, source, created_at
        FROM incidents ORDER BY created_at DESC LIMIT 5
    """))
    result["sample_incidents"] = []
    for r in samples.fetchall():
        result["sample_incidents"].append({
            "id": str(r[0]),
            "incident_type": str(r[1]),
            "severity": str(r[2]),
            "latitude": float(r[3]) if r[3] else None,
            "longitude": float(r[4]) if r[4] else None,
            "women_safety_category": str(r[5]) if r[5] else None,
            "district": str(r[6]) if r[6] else None,
            "city": str(r[7]) if r[7] else None,
            "source": str(r[8]),
            "created_at": r[9].isoformat() if r[9] else None,
        })

    # Sample 10 risk scores
    rs_samples = await db.execute(text("""
        SELECT latitude, longitude, score, category, calculated_at
        FROM risk_scores ORDER BY calculated_at DESC LIMIT 10
    """))
    result["sample_risk_scores"] = [
        {
            "latitude": float(r[0]),
            "longitude": float(r[1]),
            "score": float(r[2]),
            "category": str(r[3]),
            "calculated_at": r[4].isoformat() if r[4] else None,
        }
        for r in rs_samples.fetchall()
    ]

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Observability Endpoints (backed by pipeline_runs table)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/pipeline/runs")
async def list_pipeline_runs(
    pipeline_type: str = Query(None, description="Filter by pipeline type: news, community, risk, heatmap"),
    limit: int = Query(20, ge=1, le=100),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns recent pipeline execution records from pipeline_runs table.
    Each row includes step-level metrics and final status.
    """
    filters = "WHERE 1=1"
    params: dict = {"limit": limit}
    if pipeline_type:
        filters += " AND pipeline_type = :pipeline_type"
        params["pipeline_type"] = pipeline_type

    rows = await db.execute(
        text(f"""
            SELECT id, pipeline_type, status, triggered_by,
                   steps, summary, error, duration_ms,
                   started_at, completed_at
            FROM pipeline_runs
            {filters}
            ORDER BY started_at DESC
            LIMIT :limit
        """),
        params,
    )
    return {
        "runs": [
            {
                "id": str(r[0]),
                "pipeline_type": r[1],
                "status": r[2],
                "triggered_by": r[3],
                "steps": r[4] or {},
                "summary": r[5] or {},
                "error": r[6],
                "duration_ms": r[7],
                "started_at": r[8].isoformat() if r[8] else None,
                "completed_at": r[9].isoformat() if r[9] else None,
            }
            for r in rows.fetchall()
        ]
    }


@router.get("/pipeline/runs/{run_id}")
async def get_pipeline_run(
    run_id: str,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Returns full detail for a single pipeline run including all step metrics."""
    row = await db.execute(
        text("""
            SELECT id, pipeline_type, status, triggered_by,
                   steps, summary, error, duration_ms,
                   started_at, completed_at
            FROM pipeline_runs
            WHERE id = :run_id
        """),
        {"run_id": run_id},
    )
    r = row.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail=f"Pipeline run '{run_id}' not found")
    return {
        "id": str(r[0]),
        "pipeline_type": r[1],
        "status": r[2],
        "triggered_by": r[3],
        "steps": r[4] or {},
        "summary": r[5] or {},
        "error": r[6],
        "duration_ms": r[7],
        "started_at": r[8].isoformat() if r[8] else None,
        "completed_at": r[9].isoformat() if r[9] else None,
    }


@router.post("/seed")
async def admin_seed(
    request: Request,
    force: bool = False,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger seed data population. Offline-first — no AI required."""
    import os
    from scripts.seed_police_hospitals import seed_police_stations, seed_hospitals
    from scripts.seed_incidents import seed_incidents
    from scripts.seed_risk_scores import seed_risk_scores, seed_heatmap_grid

    _file_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(os.path.dirname(os.path.dirname(_file_dir)))
    SEED_DIR = os.path.join(_project_root, "seed_data")

    results = {}

    ps = await seed_police_stations(os.path.join(SEED_DIR, "police_stations.csv"), truncate=force)
    results["police_stations"] = ps

    hs = await seed_hospitals(os.path.join(SEED_DIR, "hospitals.csv"), truncate=force)
    results["hospitals"] = hs

    inc = await seed_incidents(os.path.join(SEED_DIR, "incidents.csv"), truncate=force)
    results["incidents"] = inc

    risk = await seed_risk_scores(truncate=force)
    results["risk_scores"] = risk

    heat = await seed_heatmap_grid()
    results["heatmap"] = heat

    await _log_admin_action(
        request, db, admin, "seed_data", "seed",
        details={"force": force, "results": results},
    )
    return {"status": "ok", "results": results}


# ─────────────────────────────────────────────────────────────────────────────
# Intelligence Observability Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/intelligence/observability")
async def intelligence_observability(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Comprehensive intelligence pipeline observability metrics."""

    # Articles processed from news_articles
    articles_total = await db.execute(text("SELECT COUNT(*) FROM news_articles"))
    articles_processed = await db.execute(
        text("SELECT COUNT(*) FROM news_articles WHERE is_processed = true")
    )

    # Incidents by status
    incidents_total = await db.execute(text("SELECT COUNT(*) FROM incidents"))
    incidents_verified = await db.execute(
        text("SELECT COUNT(*) FROM incidents WHERE status::text IN ('verified', 'VERIFIED')")
    )
    incidents_pending = await db.execute(
        text("SELECT COUNT(*) FROM incidents WHERE status::text IN ('pending', 'PENDING')")
    )
    incidents_rejected = await db.execute(
        text("SELECT COUNT(*) FROM incidents WHERE status::text IN ('dismissed', 'DISMISSED', 'duplicate', 'DUPLICATE', 'spam', 'SPAM')")
    )

    # Confidence distribution
    conf_distribution = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE confidence_score >= 0.8) as high_confidence,
            COUNT(*) FILTER (WHERE confidence_score >= 0.5 AND confidence_score < 0.8) as medium_confidence,
            COUNT(*) FILTER (WHERE confidence_score < 0.5) as low_confidence
        FROM incidents
    """))
    conf_row = conf_distribution.fetchone()

    # Geocoding success rate
    geocoded = await db.execute(
        text("SELECT COUNT(*) FROM incidents WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    )
    geocode_total = await db.execute(text("SELECT COUNT(*) FROM incidents"))
    geo_total_count = geocode_total.scalar() or 1

    # Geocoding confidence breakdown
    geo_confidence = await db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE metadata->>'geocoding_confidence' = 'HIGH') as high,
            COUNT(*) FILTER (WHERE metadata->>'geocoding_confidence' = 'MEDIUM') as medium,
            COUNT(*) FILTER (WHERE metadata->>'geocoding_confidence' = 'LOW') as low,
            COUNT(*) FILTER (WHERE metadata->>'geocoding_confidence' IS NULL) as unknown
        FROM incidents
    """))
    geo_conf_row = geo_confidence.fetchone()

    # Source breakdown
    by_source = await db.execute(
        text("SELECT source, COUNT(*) as cnt FROM incidents GROUP BY source ORDER BY cnt DESC")
    )

    # Pipeline runs
    pipeline_runs_total = await db.execute(text("SELECT COUNT(*) FROM pipeline_runs"))
    pipeline_runs_success = await db.execute(
        text("SELECT COUNT(*) FROM pipeline_runs WHERE status = 'completed'")
    )
    pipeline_runs_failed = await db.execute(
        text("SELECT COUNT(*) FROM pipeline_runs WHERE status = 'failed'")
    )
    pipeline_runs_total_count = pipeline_runs_total.scalar() or 0
    pipeline_success_rate = round(
        (pipeline_runs_success.scalar() or 0) / max(pipeline_runs_total_count, 1) * 100, 1
    )

    # Last 10 pipeline runs
    last_runs = await db.execute(
        text("""
            SELECT pipeline_type, status, duration_ms, started_at, completed_at
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT 10
        """)
    )

    # Security incidents by type
    by_type = await db.execute(
        text("SELECT incident_type, COUNT(*) as cnt FROM incidents GROUP BY incident_type ORDER BY cnt DESC")
    )

    # Risk score distribution
    risk_categories = await db.execute(text("""
        SELECT category, COUNT(*) as cnt
        FROM risk_scores
        GROUP BY category
        ORDER BY cnt DESC
    """))

    # AI provider usage from pipeline runs metadata
    ai_provider_usage = await db.execute(text("""
        SELECT
            COALESCE(steps->'news'->>'provider', 'unknown') as provider,
            COUNT(*) as cnt
        FROM pipeline_runs
        WHERE pipeline_type = 'news'
        GROUP BY provider
        ORDER BY cnt DESC
    """))

    return {
        "articles": {
            "total": articles_total.scalar() or 0,
            "processed": articles_processed.scalar() or 0,
        },
        "incidents": {
            "total": incidents_total.scalar() or 0,
            "verified": incidents_verified.scalar() or 0,
            "pending_review": incidents_pending.scalar() or 0,
            "rejected": incidents_rejected.scalar() or 0,
        },
        "confidence_distribution": {
            "high_confidence": int(conf_row[0]) if conf_row else 0,
            "medium_confidence": int(conf_row[1]) if conf_row else 0,
            "low_confidence": int(conf_row[2]) if conf_row else 0,
        },
        "geocoding": {
            "success_rate": round((geocoded.scalar() or 0) / geo_total_count * 100, 1),
            "geocoded": geocoded.scalar() or 0,
            "total": geo_total_count,
            "confidence_breakdown": {
                "high": int(geo_conf_row[0]) if geo_conf_row else 0,
                "medium": int(geo_conf_row[1]) if geo_conf_row else 0,
                "low": int(geo_conf_row[2]) if geo_conf_row else 0,
                "unknown": int(geo_conf_row[3]) if geo_conf_row else 0,
            },
        },
        "sources": {str(r[0]): int(r[1]) for r in by_source.fetchall()},
        "incident_types": {str(r[0]): int(r[1]) for r in by_type.fetchall()},
        "risk_category_distribution": {str(r[0]): int(r[1]) for r in risk_categories.fetchall()},
        "pipeline": {
            "total_runs": pipeline_runs_total_count,
            "success_rate": pipeline_success_rate,
            "failed_runs": pipeline_runs_failed.scalar() or 0,
            "last_10_runs": [
                {
                    "pipeline_type": r[0],
                    "status": r[1],
                    "duration_ms": r[2],
                    "started_at": r[3].isoformat() if r[3] else None,
                    "completed_at": r[4].isoformat() if r[4] else None,
                }
                for r in last_runs.fetchall()
            ],
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
