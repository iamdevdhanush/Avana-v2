"""add ai_provider_configs table for dynamic AI provider configuration

Revision ID: 010
Revises: 009
Create Date: 2026-06-23

Stores per-provider configuration (provider type, model, encrypted API key)
so admins can configure AI providers through the dashboard without redeploying.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("encrypted_api_key", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_status", sa.String(20), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("ai_provider_configs")
