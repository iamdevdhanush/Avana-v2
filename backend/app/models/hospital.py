import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Text, Boolean, Integer, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from app.database import Base
import enum


class HospitalType(str, enum.Enum):
    GOVERNMENT = "government"
    PRIVATE = "private"
    TRUST = "trust"


class Hospital(Base):
    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=True)
    district: Mapped[str] = mapped_column(String(100), nullable=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    taluk: Mapped[str] = mapped_column(String(100), nullable=True)
    hospital_type: Mapped[HospitalType] = mapped_column(SAEnum(HospitalType, create_type=False), nullable=False)
    emergency_services: Mapped[bool] = mapped_column(Boolean, default=False)
    ambulance_available: Mapped[bool] = mapped_column(Boolean, default=False)
    beds_available: Mapped[int] = mapped_column(Integer, default=0)
    trauma_center: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
