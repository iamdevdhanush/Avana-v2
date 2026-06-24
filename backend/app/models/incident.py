import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Text, Boolean, JSON, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from app.database import Base
import enum


class IncidentType(str, enum.Enum):
    # Values MUST match DB enum 'incidenttype' labels exactly (UPPERCASE)
    THEFT = "THEFT"
    ASSAULT = "ASSAULT"
    HARASSMENT = "HARASSMENT"
    ROBBERY = "ROBBERY"
    STALKING = "STALKING"
    DOMESTIC_VIOLENCE = "DOMESTIC_VIOLENCE"
    TRAFFIC_ACCIDENT = "TRAFFIC_ACCIDENT"
    PICKPOCKETING = "PICKPOCKETING"
    BURGLARY = "BURGLARY"
    MURDER = "MURDER"
    KIDNAPPING = "KIDNAPPING"
    RIOT = "RIOT"
    VANDALISM = "VANDALISM"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    OTHER = "OTHER"


class IncidentSeverity(str, enum.Enum):
    # Values MUST match DB enum 'incidentseverity' labels exactly (UPPERCASE)
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentSource(str, enum.Enum):
    # Values MUST match DB enum 'incidentsource' labels exactly (UPPERCASE)
    NEWS = "NEWS"
    COMMUNITY_REPORT = "COMMUNITY_REPORT"
    SOS = "SOS"
    USER_REPORT = "USER_REPORT"
    POLICE = "POLICE"
    SYSTEM = "SYSTEM"


class IncidentStatus(str, enum.Enum):
    # Values MUST match DB enum 'incidentstatus' labels exactly (UPPERCASE)
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    DISMISSED = "DISMISSED"
    DUPLICATE = "DUPLICATE"
    SPAM = "SPAM"
    RESOLVED = "RESOLVED"


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("idx_incidents_geom_gist", "geom", postgresql_using="gist"),
        Index("idx_incidents_created_at", "created_at"),
        Index("idx_incidents_severity", "severity"),
        Index("idx_incidents_district", "district"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # create_type=False: reference existing DB enum types, do not recreate them
    incident_type: Mapped[IncidentType] = mapped_column(
        SAEnum(IncidentType, name="incidenttype", create_type=False), nullable=False
    )
    severity: Mapped[IncidentSeverity] = mapped_column(
        SAEnum(IncidentSeverity, name="incidentseverity", create_type=False), nullable=False, index=True
    )
    source: Mapped[IncidentSource] = mapped_column(
        SAEnum(IncidentSource, name="incidentsource", create_type=False), nullable=False
    )
    status: Mapped[IncidentStatus] = mapped_column(
        SAEnum(IncidentStatus, name="incidentstatus", create_type=False), default=IncidentStatus.PENDING
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    # DB constraint is NOT NULL — always set geom when creating Incident objects.
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    district: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    taluk: Mapped[str] = mapped_column(String(100), nullable=True)
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source_url: Mapped[str] = mapped_column(String(2048), nullable=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=True)
    meta_data: Mapped[dict] = mapped_column("metadata", JSON().with_variant(JSONB, "postgresql"), default=dict)
    ai_classified: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    moderated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
