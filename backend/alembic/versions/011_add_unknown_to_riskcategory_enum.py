"""add UNKNOWN to riskcategory enum for no-data detection

Revision ID: 011
Revises: 010
Create Date: 2026-06-24

Adds the UNKNOWN label to the PostgreSQL riskcategory enum type,
used by risk_scores and incidents tables to represent areas with
insufficient data (never infer safety from absence of data).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE riskcategory ADD VALUE IF NOT EXISTS 'UNKNOWN'")


def downgrade() -> None:
    # Removing a value from a PostgreSQL enum requires PG16+ (ALTER TYPE ... DROP VALUE).
    # On older versions, this is a multi-step process: create new type, migrate, drop old.
    # Since UNKNOWN is purely additive and unused by existing data, skipping downgrade
    # is safe — the value will simply remain unused after rollback.
    pass
