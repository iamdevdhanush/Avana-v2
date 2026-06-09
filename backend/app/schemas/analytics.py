from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel


class DistrictStats(BaseModel):
    district: str
    total: int
    high_risk: int
    medium_risk: int
    low_risk: int
    avg_score: float


class TypeStats(BaseModel):
    incident_type: str
    count: int
    percentage: float


class TrendPoint(BaseModel):
    date: str
    value: float


class AlertItem(BaseModel):
    id: UUID
    type: str
    severity: str
    district: str
    time: datetime
    status: str


class DashboardStats(BaseModel):
    total_incidents: int
    active_users: int
    sos_events: int
    verified_reports: int
    incidents_by_district: List[DistrictStats]
    incidents_by_type: List[TypeStats]
    risk_trend: List[TrendPoint]
    incidents_trend: List[TrendPoint]
    recent_alerts: List[AlertItem]
