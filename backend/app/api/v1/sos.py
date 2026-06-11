import asyncio
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import require_user
from app.models.sos_event import SOSEvent, SOSStatus
from app.models.user import User, EmergencyContact
from app.schemas.sos import SOSCreate, SOSResponse

logger = logging.getLogger(__name__)


async def _send_sos_email(sos: SOSEvent, user: User, db: AsyncSession) -> dict:
    result = {"email_sent": False, "delivery_status": "not_attempted", "error": None}
    if not settings.SOS_NOTIFICATION_EMAIL_ENABLED:
        result["delivery_status"] = "disabled"
        return result
    if not settings.SENDGRID_API_KEY:
        result["delivery_status"] = "no_api_key"
        logger.warning("SOS email enabled but SENDGRID_API_KEY not configured")
        return result
    if not user.email:
        result["delivery_status"] = "no_email"
        logger.warning("User has no email address for SOS notification")
        return result
    last_exc = None
    for attempt in range(1, 4):
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
            from_email = Email(settings.SENDGRID_FROM_EMAIL)
            to_email = To(user.email)
            subject = f"SOS Alert Triggered - {sos.emergency_type or 'General'}"
            content = Content(
                "text/plain",
                f"An SOS alert was triggered at your location.\n\n"
                f"Time: {sos.created_at.isoformat()}\n"
                f"Location: ({sos.latitude}, {sos.longitude})\n"
                f"Type: {sos.emergency_type or 'General'}\n"
                f"Message: {sos.message or 'No message'}\n\n"
                f"- Avana Safety",
            )
            mail = Mail(from_email, to_email, subject, content)
            response = sg.client.mail.send.post(request_body=mail.get())
            status_code = response.status_code
            sent = 202 <= status_code < 300
            result["email_sent"] = sent
            result["delivery_status"] = "sent" if sent else f"http_{status_code}"
            result["status_code"] = status_code
            logger.info(f"SOS email {'sent' if sent else 'failed'} to {user.email}, status={status_code}")
            try:
                sos.notified_contacts = sos.notified_contacts or {}
                sos.notified_contacts["email_notification"] = result
                if sent:
                    sos.status = SOSStatus.ACKNOWLEDGED
            except Exception:
                pass
            return result
        except ImportError:
            result["delivery_status"] = "package_missing"
            logger.warning("sendgrid package not installed, skipping email notification")
            return result
        except Exception as e:
            last_exc = e
            if attempt < 3:
                delay = 1.0 * (2 ** (attempt - 1))
                logger.warning(f"SOS email attempt {attempt}/3 failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                logger.error(f"SOS email failed after 3 attempts: {e}")
                result["delivery_status"] = "failed"
                result["error"] = str(e)
    return result

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

    email_result = await _send_sos_email(sos, user, db)
    await db.flush()

    email_info = {
        "delivery_status": email_result.get("delivery_status", "not_attempted"),
        "email_sent": email_result.get("email_sent", False),
    }
    if email_result.get("error"):
        email_info["error"] = email_result["error"]

    return SOSResponse(
        id=sos.id,
        status=sos.status.value if hasattr(sos.status, "value") else sos.status,
        message=sos.message,
        created_at=sos.created_at,
        notified_contacts=notified,
        email_notification=email_info,
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
