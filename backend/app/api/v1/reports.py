import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user
from app.models.safety_report import SafetyReport, IncidentType, Severity, ReportStatus
from app.models.user import User


class ReportCreate(BaseModel):
    incident_type: str
    severity: str
    latitude: float
    longitude: float
    description: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    is_anonymous: bool = False


router = APIRouter(prefix="/reports", tags=["Safety Reports"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_report(
    body: ReportCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if not (-90 <= body.latitude <= 90) or not (-180 <= body.longitude <= 180):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid coordinates")
    try:
        inc_type = IncidentType(body.incident_type)
        sev = Severity(body.severity)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid value: {e}")

    report = SafetyReport(
        id=uuid.uuid4(),
        user_id=user.id,
        incident_type=inc_type,
        severity=sev,
        latitude=body.latitude,
        longitude=body.longitude,
        geom=WKTElement(f"POINT({body.longitude} {body.latitude})", srid=4326),
        description=body.description,
        address=body.address,
        district=body.district,
        city=body.city,
        status=ReportStatus.PENDING,
        is_anonymous=body.is_anonymous,
        is_verified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    await db.flush()

    return {
        "id": str(report.id),
        "incident_type": report.incident_type.value if hasattr(report.incident_type, "value") else report.incident_type,
        "severity": report.severity.value if hasattr(report.severity, "value") else report.severity,
        "status": report.status.value if hasattr(report.status, "value") else report.status,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "description": report.description,
        "district": report.district,
        "city": report.city,
        "is_anonymous": report.is_anonymous,
        "created_at": report.created_at.isoformat(),
    }


@router.get("")
async def list_reports(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(SafetyReport)
        .where(SafetyReport.user_id == user.id)
        .order_by(SafetyReport.created_at.desc())
    )
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    reports = result.scalars().all()

    return {
        "items": [
            {
                "id": str(r.id),
                "incident_type": r.incident_type.value if hasattr(r.incident_type, "value") else r.incident_type,
                "severity": r.severity.value if hasattr(r.severity, "value") else r.severity,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "description": r.description,
                "district": r.district,
                "city": r.city,
                "is_anonymous": r.is_anonymous,
                "is_verified": r.is_verified,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{id}")
async def get_report_detail(
    id: uuid.UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SafetyReport).where(
            SafetyReport.id == id,
            SafetyReport.user_id == user.id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    return {
        "id": str(report.id),
        "incident_type": report.incident_type.value if hasattr(report.incident_type, "value") else report.incident_type,
        "severity": report.severity.value if hasattr(report.severity, "value") else report.severity,
        "status": report.status.value if hasattr(report.status, "value") else report.status,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "description": report.description,
        "address": report.address,
        "district": report.district,
        "city": report.city,
        "is_anonymous": report.is_anonymous,
        "is_verified": report.is_verified,
        "confidence_score": report.confidence_score,
        "moderation_notes": report.moderation_notes,
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }
