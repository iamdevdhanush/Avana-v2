from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.incident import IncidentType, IncidentSeverity


class IncidentCreate(BaseModel):
    incident_type: IncidentType
    severity: IncidentSeverity
    latitude: float
    longitude: float
    description: Optional[str] = None
    title: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    is_anonymous: bool = False


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_type: str
    severity: str
    source: str
    status: str
    confidence_score: float
    latitude: float
    longitude: float
    description: Optional[str] = None
    title: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    incident_date: Optional[datetime] = None
    created_at: datetime
    distance: Optional[float] = None


class IncidentListResponse(BaseModel):
    items: List[IncidentResponse]
    total: int
    page: int
    page_size: int


class IncidentFilterParams(BaseModel):
    incident_type: Optional[str] = None
    severity: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_km: float = 5.0
    page: int = 1
    page_size: int = 20
