"""enable postgis extension

Revision ID: 014
Revises: 013
Create Date: 2026-06-25

Enables the PostGIS extension for geospatial queries.
Previously this was only done via init-postgis.sql in the Docker
entrypoint, which does not apply to Supabase or other managed
PostgreSQL providers.

Also validates that required enum types exist (created implicitly
by earlier create_all calls or by create_type=False patterns).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    required_enums = [
        "incidenttype",
        "incidentseverity",
        "incidentsource",
        "incidentstatus",
        "riskcategory",
        "severity",
        "reportstatus",
    ]
    for enum_name in required_enums:
        op.execute(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') "
            f"THEN RAISE EXCEPTION 'required enum type % does not exist', '{enum_name}'; END IF; END $$"
        )


def downgrade() -> None:
    pass
