"""add missing database indexes for performance

Revision ID: add_missing_indexes
Revises: (previous revision)
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

revision = "add_missing_indexes"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # incidents
    op.create_index("ix_incidents_women_safety_category", "incidents",
                    [sa.text("(metadata->>'women_safety_category')")],
                    postgresql_using="btree",
                    postgresql_concurrently=True)
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"],
                    postgresql_using="btree",
                    postgresql_concurrently=True)
    op.create_index("ix_incidents_district", "incidents", ["district"],
                    postgresql_using="btree",
                    postgresql_concurrently=True)

    # risk_scores
    op.create_index("ix_risk_scores_calculated_at", "risk_scores", ["calculated_at"],
                    postgresql_using="btree",
                    postgresql_concurrently=True)
    op.create_index("ix_risk_scores_lat_lng", "risk_scores",
                    ["latitude", "longitude"],
                    postgresql_using="btree",
                    postgresql_concurrently=True)

    # geocoding_cache
    op.create_index("ix_geocoding_cache_location_text", "geocoding_cache", ["location_text"],
                    postgresql_using="btree",
                    postgresql_concurrently=True)

    # GiST spatial indexes — critical for ST_DWithin joins
    op.create_index("ix_incidents_geom_gist", "incidents", ["geom"],
                    postgresql_using="gist",
                    postgresql_concurrently=True,
                    postgresql_ops={"geom": "geography_ops"})
    op.create_index("ix_police_stations_geom_gist", "police_stations", ["geom"],
                    postgresql_using="gist",
                    postgresql_concurrently=True,
                    postgresql_ops={"geom": "geography_ops"})
    op.create_index("ix_hospitals_geom_gist", "hospitals", ["geom"],
                    postgresql_using="gist",
                    postgresql_concurrently=True,
                    postgresql_ops={"geom": "geography_ops"})


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
