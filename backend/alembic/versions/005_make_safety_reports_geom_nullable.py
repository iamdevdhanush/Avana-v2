"""make safety_reports.geom nullable

Revision ID: 005
Revises: 004
Create Date: 2026-06-15

The safety_reports.geom column was NOT NULL in the DB but the ORM model marks
it as nullable=True. Some code paths (e.g. direct SQL inserts without geom)
would fail with a NOT NULL violation. Making it nullable allows the pipeline to
process reports even when PostGIS geometry isn't explicitly set.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "safety_reports" in tables:
        # Make geom nullable so records without explicit geometry can be inserted
        op.execute("ALTER TABLE safety_reports ALTER COLUMN geom DROP NOT NULL")

    # Also make incidents.geom nullable to match the original ORM model intent
    # (we changed the model to nullable=False to match DB reality, but this ensures
    # both tables are consistent — safety_reports can exist without PostGIS geom)
    # incidents.geom remains NOT NULL (pipeline always sets it), no change needed there.


def downgrade() -> None:
    # Reversing this would force NOT NULL which could break existing NULL rows
    pass
