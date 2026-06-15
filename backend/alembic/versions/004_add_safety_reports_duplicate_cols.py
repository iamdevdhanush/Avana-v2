"""add is_duplicate and duplicate_of to safety_reports

Revision ID: 004
Revises: 003
Create Date: 2026-06-15

Root cause: community pipeline UPDATE referenced is_duplicate/duplicate_of
columns that never existed in safety_reports (only incidents had them).
This migration adds those columns so the full schema matches the ORM intent.

Additionally fixes:
- Aligns safety_reports.status enum values with what the pipeline uses
  (DB stores PENDING/APPROVED/REJECTED — already correct, no change needed)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Ensure safety_reports table exists before modifying
    tables = inspector.get_table_names()
    if "safety_reports" not in tables:
        return

    existing_cols = {col["name"] for col in inspector.get_columns("safety_reports")}

    # Add is_duplicate (boolean) if missing
    if "is_duplicate" not in existing_cols:
        op.add_column(
            "safety_reports",
            sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    # Add duplicate_of (UUID FK nullable) if missing
    if "duplicate_of" not in existing_cols:
        op.add_column(
            "safety_reports",
            sa.Column("duplicate_of", UUID(as_uuid=True), nullable=True),
        )

    # Also ensure incidents.geom allows NULL at DB level (model says nullable=True)
    if "incidents" in tables:
        incident_cols = {col["name"]: col for col in inspector.get_columns("incidents")}
        geom_col = incident_cols.get("geom")
        if geom_col and not geom_col.get("nullable", True):
            op.alter_column("incidents", "geom", nullable=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "safety_reports" in tables:
        existing_cols = {col["name"] for col in inspector.get_columns("safety_reports")}
        if "duplicate_of" in existing_cols:
            op.drop_column("safety_reports", "duplicate_of")
        if "is_duplicate" in existing_cols:
            op.drop_column("safety_reports", "is_duplicate")
