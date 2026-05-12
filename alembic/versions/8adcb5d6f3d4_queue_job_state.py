"""queue job state

Revision ID: 8adcb5d6f3d4
Revises: 58f29d25c05c
Create Date: 2026-05-12 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8adcb5d6f3d4"
down_revision: str | None = "58f29d25c05c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_queue",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
    )
    op.add_column("analysis_queue", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("analysis_queue", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "analysis_queue",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("analysis_queue", sa.Column("last_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("analysis_queue", "last_error")
    op.drop_column("analysis_queue", "attempts")
    op.drop_column("analysis_queue", "completed_at")
    op.drop_column("analysis_queue", "started_at")
    op.drop_column("analysis_queue", "status")
