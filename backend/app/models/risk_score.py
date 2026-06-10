import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, JSON, Enum as SAEnum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from app.database import Base
import enum


class RiskCategory(str, enum.Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"


class RiskScore(Base):
    __tablename__ = "risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[RiskCategory] = mapped_column(SAEnum(RiskCategory), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    taluk: Mapped[str] = mapped_column(String(100), nullable=True)
    ward: Mapped[str] = mapped_column(String(100), nullable=True)
    population_density: Mapped[float] = mapped_column(Float, nullable=True)
    police_presence: Mapped[float] = mapped_column(Float, nullable=True)
    hospital_accessibility: Mapped[float] = mapped_column(Float, nullable=True)
    night_factor: Mapped[float] = mapped_column(Float, nullable=True)
    historical_risk: Mapped[float] = mapped_column(Float, nullable=True)
    recent_reports_impact: Mapped[float] = mapped_column(Float, nullable=True)
    meta_data: Mapped[dict] = mapped_column("metadata", JSON().with_variant(JSONB, "postgresql"), default=dict)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
