"""ensure users table has all required columns

Revision ID: 002
Revises: 001
Create Date: 2026-06-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("users")]

    if "hashed_password" not in columns:
        op.add_column("users", sa.Column("hashed_password", sa.String(255), nullable=True))
        op.execute("UPDATE users SET hashed_password = '' WHERE hashed_password IS NULL")
        op.alter_column("users", "hashed_password", nullable=False, server_default="")

    if "is_active" not in columns:
        op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))

    if "avatar_url" not in columns:
        op.add_column("users", sa.Column("avatar_url", sa.String(512), nullable=True))

    if "phone" not in columns:
        op.add_column("users", sa.Column("phone", sa.String(20), nullable=True))

    if "supabase_uid" not in columns:
        op.add_column("users", sa.Column("supabase_uid", sa.String(255), nullable=True, unique=True))
        op.create_index("ix_users_supabase_uid", "users", ["supabase_uid"])

    if "last_login" not in columns:
        op.add_column("users", sa.Column("last_login", sa.DateTime(timezone=True), nullable=True))

    if "is_verified" not in columns:
        op.add_column("users", sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    pass
