import uuid
from datetime import datetime
from sqlalchemy import String, Float, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from app.database import Base


class PoliceStation(Base):
    __tablename__ = "police_stations"

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
    jurisdiction: Mapped[str] = mapped_column(Text, nullable=True)
    station_type: Mapped[str] = mapped_column(String(50), nullable=True)
    has_emergency_number: Mapped[bool] = mapped_column(Boolean, default=False)
    officer_in_charge: Mapped[str] = mapped_column(String(255), nullable=True)
    opening_hours: Mapped[str] = mapped_column(String(255), nullable=True)
    rating: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
