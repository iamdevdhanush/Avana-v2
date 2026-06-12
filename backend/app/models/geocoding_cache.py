import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GeocodingCache(Base):
    __tablename__ = "geocoding_cache"
    __table_args__ = (
        UniqueConstraint("location_text", name="uq_geocoding_cache_text"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    location_text: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    display_name: Mapped[str] = mapped_column(String(1000), nullable=True)
    last_verified: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))