"""Record working time

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-26 23:36:04.356574
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("bug_hunt_jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("working_seconds", sa.Double(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bug_hunt_jobs", schema=None) as batch_op:
        batch_op.drop_column("working_seconds")
