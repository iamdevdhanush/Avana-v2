"""
pipeline_run ORM model

Tracks every pipeline execution with step-level metrics and duration.
Written by PipelineOrchestrator; read by admin /pipeline/runs endpoints.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # running | completed | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    # scheduler | admin | bootstrap | test
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False, default="admin")
    # Per-step metrics: {fetch:{status,count}, extract:{...}, ...}
    steps: Mapped[dict] = mapped_column(
        "steps",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )
    # Final aggregate metrics
    summary: Mapped[dict] = mapped_column(
        "summary",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
    )
    error: Mapped[str] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
