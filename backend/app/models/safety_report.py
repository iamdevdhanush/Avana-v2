import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Text, Boolean, Enum as SAEnum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
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


class Severity(str, enum.Enum):
    # Values MUST match DB enum 'severity' labels exactly (UPPERCASE)
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReportStatus(str, enum.Enum):
    # Values MUST match DB enum 'reportstatus' labels exactly (UPPERCASE)
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class SafetyReport(Base):
    __tablename__ = "safety_reports"
    __table_args__ = (
        Index("idx_safety_reports_status", "status"),
        Index("idx_safety_reports_district", "district"),
        Index("idx_safety_reports_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # create_type=False: use the existing DB enum instead of recreating it
    incident_type: Mapped[IncidentType] = mapped_column(
        SAEnum(IncidentType, name="incidenttype", create_type=False), nullable=False
    )
    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, name="severity", create_type=False), nullable=False
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    district: Mapped[str] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, name="reportstatus", create_type=False), default=ReportStatus.PENDING
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Added by migration 004 — marks community reports that are duplicates of existing incidents
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    moderated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    moderation_notes: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="safety_reports")
