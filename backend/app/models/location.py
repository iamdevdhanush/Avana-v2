import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from geoalchemy2 import Geometry
from app.database import Base


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    place_id: Mapped[str] = mapped_column(String(255), nullable=True, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    district: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True, index=True)
    taluk: Mapped[str] = mapped_column(String(100), nullable=True)
    ward: Mapped[str] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str] = mapped_column(String(10), nullable=True)
    location_type: Mapped[str] = mapped_column(String(50), nullable=True)
    meta_data: Mapped[dict] = mapped_column("metadata", JSON().with_variant(JSONB, "postgresql"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
