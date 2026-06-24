"""cleanup mock incidents from initial mock pipeline runs

Revision ID: 013
Revises: 012
Create Date: 2026-06-24

Removes incidents that were saved during initial mock pipeline runs
(source_url LIKE 'https://mock-source.local/%'). These are synthetic
test incidents created by intelligence_mock.py that block real AI-
extracted incidents from being saved due to source_url duplicate checks.

Run once after deploying all code fixes. Safe to run multiple times
(idempotent - second run deletes 0 rows).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM incidents WHERE source_url LIKE 'https://mock-source.local/%'"
    )


def downgrade() -> None:
    pass
