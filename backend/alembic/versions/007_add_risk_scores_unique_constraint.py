"""add UNIQUE(latitude, longitude) constraint to risk_scores

Revision ID: 007
Revises: 006
Create Date: 2026-06-15

The model RiskScore defines:
    __table_args__ = (
        UniqueConstraint("latitude", "longitude", name="uq_risk_scores_lat_lng"),
    )
but this constraint was never created in the database. Without it, every
INSERT INTO risk_scores ... ON CONFLICT (latitude, longitude) DO UPDATE SET
fails with InvalidColumnReferenceError: there is no unique or exclusion
constraint matching the ON CONFLICT specification.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    constraints = [c["name"] for c in inspector.get_unique_constraints("risk_scores")]

    if "uq_risk_scores_lat_lng" in constraints:
        return

    # Remove duplicate (latitude, longitude) rows before creating the constraint.
    # Keep only the row with the latest calculated_at for each duplicate pair.
    conn.execute(sa.text("""
        DELETE FROM risk_scores
        WHERE id NOT IN (
            SELECT DISTINCT ON (latitude, longitude) id
            FROM risk_scores
            ORDER BY latitude, longitude, calculated_at DESC NULLS LAST
        )
    """))
    op.create_unique_constraint(
        "uq_risk_scores_lat_lng",
        "risk_scores",
        ["latitude", "longitude"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    constraints = [c["name"] for c in inspector.get_unique_constraints("risk_scores")]
    if "uq_risk_scores_lat_lng" in constraints:
        op.drop_constraint("uq_risk_scores_lat_lng", "risk_scores", type_="unique")
