from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ModerateAction(BaseModel):
    incident_id: UUID
    status: str
    moderation_notes: Optional[str] = None


class AdminAction(BaseModel):
    moderate: ModerateAction


class UserManagementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    total_reports: int
    created_at: datetime
