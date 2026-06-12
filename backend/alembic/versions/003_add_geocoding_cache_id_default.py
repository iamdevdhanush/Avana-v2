"""add server_default gen_random_uuid to geocoding_cache.id

Revision ID: 003
Revises: 002
Create Date: 2026-06-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "geocoding_cache" not in tables:
        return

    columns = {col["name"]: col for col in inspector.get_columns("geocoding_cache")}

    if "id" not in columns:
        return

    col = columns["id"]
    default = col.get("default", None)

    # Only add default if none exists
    if not default:
        op.execute(
            "ALTER TABLE geocoding_cache "
            "ALTER COLUMN id SET DEFAULT gen_random_uuid()"
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if "geocoding_cache" not in tables:
        return
    op.execute(
        "ALTER TABLE geocoding_cache "
        "ALTER COLUMN id DROP DEFAULT"
    )
