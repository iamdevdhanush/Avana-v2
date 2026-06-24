"""add RESOLVED to incidentstatus enum for incident moderation

Revision ID: 012
Revises: 011
Create Date: 2026-06-24

Adds the RESOLVED label to the PostgreSQL incidentstatus enum type,
enabling admin moderation to mark incidents as resolved.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE incidentstatus ADD VALUE IF NOT EXISTS 'RESOLVED'")


def downgrade() -> None:
    pass
