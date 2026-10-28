"""Store model reasoning

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-26 22:41:35.673395
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages", schema=None) as batch_op:
        batch_op.drop_column("reasoning")
