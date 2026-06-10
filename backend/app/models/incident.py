import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, Boolean, JSON, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from app.database import Base
import enum


class IncidentType(str, enum.Enum):
    THEFT = "theft"
    ASSAULT = "assault"
    HARASSMENT = "harassment"
    ROBBERY = "robbery"
    STALKING = "stalking"
    DOMESTIC_VIOLENCE = "domestic_violence"
    TRAFFIC_ACCIDENT = "traffic_accident"
    PICKPOCKETING = "pickpocketing"
    BURGLARY = "burglary"
    MURDER = "murder"
    KIDNAPPING = "kidnapping"
    RIOT = "riot"
    VANDALISM = "vandalism"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    OTHER = "other"


class IncidentSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentSource(str, enum.Enum):
    NEWS = "news"
    COMMUNITY_REPORT = "community_report"
    SOS = "sos"
    USER_REPORT = "user_report"
    POLICE = "police"
    SYSTEM = "system"


class IncidentStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    DISMISSED = "dismissed"
    DUPLICATE = "duplicate"
    SPAM = "spam"


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("idx_incidents_geom_gist", "geom", postgresql_using="gist"),
        Index("idx_incidents_created_at", "created_at"),
        Index("idx_incidents_severity", "severity"),
        Index("idx_incidents_district", "district"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_type: Mapped[IncidentType] = mapped_column(SAEnum(IncidentType), nullable=False)
    severity: Mapped[IncidentSeverity] = mapped_column(SAEnum(IncidentSeverity), nullable=False, index=True)
    source: Mapped[IncidentSource] = mapped_column(SAEnum(IncidentSource), nullable=False)
    status: Mapped[IncidentStatus] = mapped_column(SAEnum(IncidentStatus), default=IncidentStatus.PENDING)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    district: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    taluk: Mapped[str] = mapped_column(String(100), nullable=True)
    incident_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=True)
    source_id: Mapped[str] = mapped_column(String(255), nullable=True)
    meta_data: Mapped[dict] = mapped_column("metadata", JSON().with_variant(JSONB, "postgresql"), default=dict)
    ai_classified: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    moderated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
