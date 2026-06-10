import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_user
from app.models.sos_event import SOSEvent, SOSStatus
from app.models.user import User, EmergencyContact
from app.schemas.sos import SOSCreate, SOSResponse

router = APIRouter(prefix="/sos", tags=["SOS"])


@router.post("", response_model=SOSResponse, status_code=status.HTTP_201_CREATED)
async def trigger_sos(
    body: SOSCreate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    contacts_result = await db.execute(
        select(EmergencyContact).where(EmergencyContact.user_id == user.id)
    )
    contacts = contacts_result.scalars().all()
    notified = [
        {"name": c.name, "phone": c.phone, "relationship": c.relationship}
        for c in contacts
    ]

    sos = SOSEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        latitude=body.latitude,
        longitude=body.longitude,
        geom=WKTElement(f"POINT({body.longitude} {body.latitude})", srid=4326),
        message=body.message,
        status=SOSStatus.TRIGGERED,
        emergency_type=body.emergency_type,
        notified_contacts={"contacts": notified},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(sos)
    await db.flush()

    return SOSResponse(
        id=sos.id,
        status=sos.status.value if hasattr(sos.status, "value") else sos.status,
        message=sos.message,
        created_at=sos.created_at,
        notified_contacts=notified,
    )


@router.get("/history", response_model=list[SOSResponse])
async def get_sos_history(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SOSEvent)
        .where(SOSEvent.user_id == user.id)
        .order_by(SOSEvent.created_at.desc())
    )
    events = result.scalars().all()
    return [
        SOSResponse(
            id=e.id,
            status=e.status.value if hasattr(e.status, "value") else e.status,
            message=e.message,
            created_at=e.created_at,
            notified_contacts=e.notified_contacts.get("contacts") if e.notified_contacts else None,
        )
        for e in events
    ]


@router.get("/{id}", response_model=SOSResponse)
async def get_sos_detail(
    id: uuid.UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SOSEvent).where(SOSEvent.id == id, SOSEvent.user_id == user.id)
    )
    sos = result.scalar_one_or_none()
    if not sos:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SOS event not found")
    return SOSResponse(
        id=sos.id,
        status=sos.status.value if hasattr(sos.status, "value") else sos.status,
        message=sos.message,
        created_at=sos.created_at,
        notified_contacts=sos.notified_contacts.get("contacts") if sos.notified_contacts else None,
    )
