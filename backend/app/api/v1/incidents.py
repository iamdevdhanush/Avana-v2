import uuid
from datetime import datetime
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_user
from app.models.incident import Incident, IncidentStatus, IncidentSource, IncidentType, IncidentSeverity
from app.models.user import User
from app.schemas.incident import (
    IncidentCreate,
    IncidentResponse,
    IncidentListResponse,
    IncidentFilterParams,
)

router = APIRouter(prefix="/incidents", tags=["Incidents"])


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return R * 2 * asin(sqrt(a))


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    incident_type: str = Query(None),
    severity: str = Query(None),
    district: str = Query(None),
    city: str = Query(None),
    status: str = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    lat: float = Query(None),
    lng: float = Query(None),
    radius_km: float = Query(5.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    query = select(Incident).order_by(Incident.created_at.desc())

    if incident_type:
        query = query.where(Incident.incident_type == incident_type)
    if severity:
        query = query.where(Incident.severity == severity)
    if district:
        query = query.where(Incident.district == district)
    if city:
        query = query.where(Incident.city == city)
    if status:
        query = query.where(Incident.status == status)
    if start_date:
        query = query.where(Incident.created_at >= start_date)
    if end_date:
        query = query.where(Incident.created_at <= end_date)

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    incidents = result.scalars().all()

    items = []
    for inc in incidents:
        distance = None
        if lat is not None and lng is not None:
            distance = round(_haversine(lat, lng, inc.latitude, inc.longitude), 3)
        items.append(
            IncidentResponse(
                id=inc.id,
                incident_type=inc.incident_type.value if hasattr(inc.incident_type, "value") else inc.incident_type,
                severity=inc.severity.value if hasattr(inc.severity, "value") else inc.severity,
                source=inc.source.value if hasattr(inc.source, "value") else inc.source,
                status=inc.status.value if hasattr(inc.status, "value") else inc.status,
                confidence_score=inc.confidence_score,
                latitude=inc.latitude,
                longitude=inc.longitude,
                description=inc.description,
                title=inc.title,
                district=inc.district,
                city=inc.city,
                incident_date=inc.incident_date,
                created_at=inc.created_at,
                distance=distance,
            )
        )

    return IncidentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/nearby", response_model=list[IncidentResponse])
async def get_nearby_incidents(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius: float = Query(5.0, description="Radius in km"),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    radius_meters = radius * 1000
    dialect_name = db.get_bind().dialect.name
    geography_cast = "::geography" if dialect_name == "postgresql" else ""
    result = await db.execute(
        text(f"""
            SELECT id, incident_type, severity, source, status, confidence_score,
                   latitude, longitude, description, title, district, city,
                   incident_date, created_at,
                   ST_Distance(geom{geography_cast}, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326){geography_cast}) as dist_meters
            FROM incidents
            WHERE ST_DWithin(geom{geography_cast}, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326){geography_cast}, :radius)
            ORDER BY dist_meters ASC
            LIMIT :lim
        """),
        {"lat": lat, "lng": lng, "radius": radius_meters, "lim": limit},
    )
    rows = result.fetchall()
    return [
        IncidentResponse(
            id=row[0],
            incident_type=row[1],
            severity=row[2],
            source=row[3],
            status=row[4],
            confidence_score=float(row[5]),
            latitude=float(row[6]),
            longitude=float(row[7]),
            description=row[8],
            title=row[9],
            district=row[10],
            city=row[11],
            incident_date=row[12],
            created_at=row[13],
            distance=round(float(row[14]) / 1000, 3) if row[14] else None,
        )
        for row in rows
    ]


@router.get("/stats")
async def get_incident_stats(
    district: str = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    db: AsyncSession = Depends(get_db),
):
    filters = "WHERE 1=1"
    params = {}
    if district:
        filters += " AND district = :district"
        params["district"] = district
    if start_date:
        filters += " AND created_at >= :start_date"
        params["start_date"] = start_date
    if end_date:
        filters += " AND created_at <= :end_date"
        params["end_date"] = end_date

    by_district = await db.execute(
        text(f"""
            SELECT district, COUNT(*) as cnt
            FROM incidents {filters}
            GROUP BY district ORDER BY cnt DESC LIMIT 20
        """),
        params,
    )

    by_type = await db.execute(
        text(f"""
            SELECT incident_type, COUNT(*) as cnt
            FROM incidents {filters}
            GROUP BY incident_type ORDER BY cnt DESC
        """),
        params,
    )

    total_row = await db.execute(
        text(f"SELECT COUNT(*) FROM incidents {filters}"),
        params,
    )

    return {
        "total_incidents": total_row.scalar() or 0,
        "by_district": [{"district": r[0], "count": r[1]} for r in by_district.fetchall()],
        "by_type": [{"incident_type": r[0], "count": r[1]} for r in by_type.fetchall()],
    }


@router.get("/{id}", response_model=IncidentResponse)
async def get_incident(id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).where(Incident.id == id))
    inc = result.scalar_one_or_none()
    if not inc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return IncidentResponse(
        id=inc.id,
        incident_type=inc.incident_type.value if hasattr(inc.incident_type, "value") else inc.incident_type,
        severity=inc.severity.value if hasattr(inc.severity, "value") else inc.severity,
        source=inc.source.value if hasattr(inc.source, "value") else inc.source,
        status=inc.status.value if hasattr(inc.status, "value") else inc.status,
        confidence_score=inc.confidence_score,
        latitude=inc.latitude,
        longitude=inc.longitude,
        description=inc.description,
        title=inc.title,
        district=inc.district,
        city=inc.city,
        incident_date=inc.incident_date,
        created_at=inc.created_at,
    )


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    body: IncidentCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import geoalchemy2
    incident = Incident(
        id=uuid.uuid4(),
        incident_type=body.incident_type,
        severity=body.severity,
        source=IncidentSource.USER_REPORT,
        status=IncidentStatus.PENDING,
        confidence_score=0.0,
        latitude=body.latitude,
        longitude=body.longitude,
        geom=WKTElement(f"POINT({body.longitude} {body.latitude})", srid=4326),
        description=body.description,
        title=body.title,
        address=body.address,
        district=body.district,
        city=body.city,
        is_duplicate=False,
        user_id=user.id if user else None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(incident)
    await db.flush()
    return IncidentResponse(
        id=incident.id,
        incident_type=incident.incident_type.value if hasattr(incident.incident_type, "value") else incident.incident_type,
        severity=incident.severity.value if hasattr(incident.severity, "value") else incident.severity,
        source=incident.source.value if hasattr(incident.source, "value") else incident.source,
        status=incident.status.value if hasattr(incident.status, "value") else incident.status,
        confidence_score=incident.confidence_score,
        latitude=incident.latitude,
        longitude=incident.longitude,
        description=incident.description,
        title=incident.title,
        district=incident.district,
        city=incident.city,
        incident_date=incident.incident_date,
        created_at=incident.created_at,
    )
