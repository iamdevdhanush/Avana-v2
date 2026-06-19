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
from app.services.gemini import GeminiQuotaExceeded
from app.pipeline.intelligence import run_intelligence_pipeline
from app.pipeline.community import process_pending_reports
from app.pipeline.risk import recalculate_all_risk_scores
from app.pipeline.heatmap import generate_heatmap_for_bounds

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    try:
        incident.status = IncidentStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {body.status}")

    incident.moderated_by = admin.id
    incident.updated_at = datetime.now(timezone.utc)
    await _log_admin_action(request, db, admin, "moderate_incident", "incident", str(incident.id), {
        "status": body.status, "notes": body.moderation_notes,
    })
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
    pipeline_map = {
        "intelligence": run_intelligence_pipeline,
        "community": process_pending_reports,
        "risk": recalculate_all_risk_scores,
        "heatmap": lambda: generate_heatmap_for_bounds(11.5, 74.0, 18.0, 78.5, zoom="city"),
    }

    runner = pipeline_map.get(pipeline_name)
    if not runner:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown pipeline: {pipeline_name}. Available: {list(pipeline_map.keys())}",
        )

    acquired = await _acquire_pipeline_lock(pipeline_name)
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": f"Pipeline '{pipeline_name}' is already running"},
        )

    try:
        result = await runner()

        if result.get("status") == "skipped":
            reason = result.get("reason", "gemini_unavailable")
            log_details = {
                "pipeline": pipeline_name,
                "status": "skipped",
                "reason": reason,
                "duration_seconds": result.get("duration_seconds", 0),
            }
            await _log_admin_action(
                request, db, admin, "run_pipeline_skipped", "pipeline",
                pipeline_name, log_details, severity="warning",
            )
            return {"pipeline": pipeline_name, "status": "skipped", "result": result}

        # Build structured log details with execution counts for observability
        summary = result.get("summary", {})
        steps = result.get("steps", {})
        log_details = {
            "pipeline": pipeline_name,
            "status": "completed",
            "articles_fetched": summary.get("articles_fetched") or steps.get("fetch", {}).get("count", 0),
            "incidents_extracted": summary.get("incidents_extracted") or steps.get("extract", {}).get("count", 0),
            "incidents_created": summary.get("incidents_saved") or steps.get("save", {}).get("saved", 0),
            "risk_scores_updated": summary.get("risk_scores_updated") or steps.get("risk_recalc", {}).get("updated", 0),
            "heatmap_cells_updated": summary.get("heatmap_points_generated") or steps.get("heatmap", {}).get("points_generated", 0),
            "duration_seconds": result.get("duration_seconds") or summary.get("duration_seconds", 0),
            "completed_at": summary.get("completed_at"),
            "step_errors": [
                f"{k}: {v.get('error','')}"
                for k, v in steps.items()
                if isinstance(v, dict) and v.get("status") == "failed"
            ],
        }
        await _log_admin_action(
            request, db, admin, "run_pipeline", "pipeline",
            pipeline_name, log_details, severity="info",
        )
        return {"pipeline": pipeline_name, "status": "triggered", "result": result}
    except GeminiQuotaExceeded as e:
        err_str = str(e)
        log_details = {
            "error": err_str,
            "pipeline": pipeline_name,
            "status": "failed",
            "reason": "GEMINI_QUOTA_EXCEEDED",
        }
        await _log_admin_action(
            request, db, admin, "run_pipeline_failed", "pipeline",
            pipeline_name,
            log_details,
            "error",
        )
        await db.commit()
        from app.services.gemini import gemini_service
        gs = gemini_service.get_status()
        retry_after = gs.get("retry_after_seconds", 900)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "reason": "quota_exceeded",
                "error": "Gemini API quota exceeded",
                "retry_after_seconds": retry_after,
                "retry_after_minutes": round(retry_after / 60, 1),
            },
        )
    except Exception as e:
        err_str = str(e)
        log_details = {
            "error": err_str,
            "pipeline": pipeline_name,
            "status": "failed",
        }
        await _log_admin_action(
            request, db, admin, "run_pipeline_failed", "pipeline",
            pipeline_name,
            log_details,
            "error",
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline run failed: {str(e)}",
        )
    finally:
        _release_pipeline_lock(pipeline_name)


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
