"""add hashed_password column to users

Revision ID: 001
Revises:
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = "000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Table is now fully created in migration 000."""


def downgrade() -> None:
    op.drop_column("users", "hashed_password")
