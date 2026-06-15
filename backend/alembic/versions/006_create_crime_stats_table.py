"""create crime_stats table for Karnataka Police dataset ingestion

Revision ID: 006
Revises: 005
Create Date: 2026-06-15

Stores raw crime statistics extracted from Karnataka Police datasets
(PDF/CSV/XLSX) before normalization and ingestion into the existing
incidents/heatmap pipeline.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "crime_stats" not in tables:
        op.create_table(
            "crime_stats",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("district", sa.String(100), nullable=False),
            sa.Column("city", sa.String(100), nullable=True),
            sa.Column("crime_type", sa.String(200), nullable=False),
            sa.Column("crime_category", sa.String(100), nullable=True),
            sa.Column("crime_count", sa.Integer, nullable=False),
            sa.Column("year", sa.Integer, nullable=False),
            sa.Column("month", sa.Integer, nullable=True),
            sa.Column("latitude", sa.Float, nullable=True),
            sa.Column("longitude", sa.Float, nullable=True),
            sa.Column("source_file", sa.String(500), nullable=True),
            sa.Column("source_name", sa.String(200), nullable=True),
            sa.Column("source_row", sa.String(200), nullable=True),
            sa.Column("is_normalized", sa.Boolean, server_default=sa.text("false")),
            sa.Column("is_ingested", sa.Boolean, server_default=sa.text("false")),
            sa.Column("ingestion_batch", sa.String(64), nullable=True),
            sa.Column("metadata", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        )

        op.create_index("idx_crime_stats_district", "crime_stats", ["district"])
        op.create_index("idx_crime_stats_crime_category", "crime_stats", ["crime_category"])
        op.create_index("idx_crime_stats_year_month", "crime_stats", ["year", "month"])
        op.create_index("idx_crime_stats_ingested", "crime_stats", ["is_ingested"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "crime_stats" in tables:
        op.drop_index("idx_crime_stats_ingested", table_name="crime_stats")
        op.drop_index("idx_crime_stats_year_month", table_name="crime_stats")
        op.drop_index("idx_crime_stats_crime_category", table_name="crime_stats")
        op.drop_index("idx_crime_stats_district", table_name="crime_stats")
        op.drop_table("crime_stats")
