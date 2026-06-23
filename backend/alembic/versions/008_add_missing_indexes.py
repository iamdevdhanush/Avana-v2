"""add missing database indexes for performance

Revision ID: 008
Revises: 007
Create Date: 2026-06-19

Identified from production audit:
1. incidents.women_safety_category btree — filters 100% of risk/heatmap queries
2. incidents.created_at btree — used by recency queries, district GROUP BY
3. incidents.district btree — used by GROUP BY district queries
4. risk_scores.calculated_at btree — used by freshness checks
5. risk_scores.latitude, risk_scores.longitude btree — used by bounds queries
6. geocoding_cache.location_text btree — used by geocode lookups
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_index_if_not_exists(index_name: str, table: str, *columns, **kw):
    """Create index with IF NOT EXISTS guard against ORM-created duplicates."""
    col_expr = ", ".join(columns)
    using = kw.pop("using", "btree")
    extra = ""
    if "postgresql_ops" in kw:
        ops = kw["postgresql_ops"]
        col_expr = ", ".join(f"{c} {ops[c]}" for c in columns)
    if using == "gist":
        col_expr = f"({col_expr} {', '.join(f'{k} {v}' for k, v in kw.get('postgresql_ops', {}).items())})" if kw.get("postgresql_ops") else f"({', '.join(columns)})"
    stmt = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} USING {using} ({col_expr})"
    op.execute(stmt)


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incidents_women_safety_category "
        "ON incidents USING btree ((metadata->>'women_safety_category'))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incidents_created_at "
        "ON incidents USING btree (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incidents_district "
        "ON incidents USING btree (district)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_risk_scores_calculated_at "
        "ON risk_scores USING btree (calculated_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_risk_scores_lat_lng "
        "ON risk_scores USING btree (latitude, longitude)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_geocoding_cache_location_text "
        "ON geocoding_cache USING btree (location_text)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incidents_geom_gist "
        "ON incidents USING gist (geom)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_police_stations_geom_gist "
        "ON police_stations USING gist (geom)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hospitals_geom_gist "
        "ON hospitals USING gist (geom)"
    )


def downgrade() -> None:
    op.drop_index("ix_incidents_women_safety_category", table_name="incidents")
    op.drop_index("ix_incidents_created_at", table_name="incidents")
    op.drop_index("ix_incidents_district", table_name="incidents")
    op.drop_index("ix_risk_scores_calculated_at", table_name="risk_scores")
    op.drop_index("ix_risk_scores_lat_lng", table_name="risk_scores")
    op.drop_index("ix_geocoding_cache_location_text", table_name="geocoding_cache")
    op.drop_index("ix_incidents_geom_gist", table_name="incidents")
    op.drop_index("ix_police_stations_geom_gist", table_name="police_stations")
    op.drop_index("ix_hospitals_geom_gist", table_name="hospitals")
