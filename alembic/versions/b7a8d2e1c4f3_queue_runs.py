"""Add persisted queue run state."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7a8d2e1c4f3"
down_revision: str | Sequence[str] | None = "6e5c0b2d1a44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "queue_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=True),
        sa.Column("max_workers", sa.Integer(), nullable=False),
        sa.Column("started_by_user_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("stop_requested_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("attempted", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["started_by_user_id"],
            ["users.id"],
            name=op.f("fk_queue_runs_started_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_queue_runs")),
    )
    op.create_index(op.f("ix_queue_runs_started_at"), "queue_runs", ["started_at"], unique=False)
    op.create_index(op.f("ix_queue_runs_status"), "queue_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_queue_runs_status"), table_name="queue_runs")
    op.drop_index(op.f("ix_queue_runs_started_at"), table_name="queue_runs")
    op.drop_table("queue_runs")
