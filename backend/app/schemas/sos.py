from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SOSCreate(BaseModel):
    latitude: float
    longitude: float
    message: Optional[str] = None
    emergency_type: str = "general"


class SOSResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    message: Optional[str] = None
    created_at: datetime
    notified_contacts: Optional[list] = None
    email_notification: Optional[dict] = None
