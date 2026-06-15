import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, DateTime, Boolean, JSON, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CrimeStat(Base):
    __tablename__ = "crime_stats"
    __table_args__ = (
        Index("idx_crime_stats_district", "district"),
        Index("idx_crime_stats_crime_category", "crime_category"),
        Index("idx_crime_stats_year_month", "year", "month"),
        Index("idx_crime_stats_ingested", "is_ingested"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=True)
    crime_type: Mapped[str] = mapped_column(String(200), nullable=False)
    crime_category: Mapped[str] = mapped_column(String(100), nullable=True)
    crime_count: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)
    source_file: Mapped[str] = mapped_column(String(500), nullable=True)
    source_name: Mapped[str] = mapped_column(String(200), nullable=True)
    source_row: Mapped[str] = mapped_column(String(200), nullable=True)
    is_normalized: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ingested: Mapped[bool] = mapped_column(Boolean, default=False)
    ingestion_batch: Mapped[str] = mapped_column(String(64), nullable=True)
    meta_data: Mapped[dict] = mapped_column("metadata", JSON().with_variant(JSONB, "postgresql"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
