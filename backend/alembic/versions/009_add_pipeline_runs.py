"""add pipeline_runs table for observability

Revision ID: 009
Revises: 008
Create Date: 2026-06-23

Adds the pipeline_runs table used by PipelineOrchestrator to record
per-run metrics, step results, and failure information.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_type", sa.String(50), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("triggered_by", sa.String(50), nullable=False, server_default="admin"),
        sa.Column("steps", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("summary", postgresql.JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_pipeline_runs_type_started",
        "pipeline_runs",
        ["pipeline_type", "started_at"],
        postgresql_using="btree",
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_type_started", table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
