"""user identity request history

Revision ID: 6e5c0b2d1a44
Revises: 8adcb5d6f3d4
Create Date: 2026-05-13 00:00:00.000000

"""

import getpass
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6e5c0b2d1a44"
down_revision: str | None = "8adcb5d6f3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    with op.batch_alter_table("analyses") as batch_op:
        batch_op.add_column(sa.Column("created_by_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_analyses_created_by_user_id_users",
            "users",
            ["created_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("analysis_queue") as batch_op:
        batch_op.add_column(sa.Column("requested_by_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_analysis_queue_requested_by_user_id_users",
            "users",
            ["requested_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_table(
        "analysis_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("queue_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["queue_id"], ["analysis_queue.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_analysis_requests_ticker"), "analysis_requests", ["ticker"], unique=False
    )

    now = datetime.now(UTC)
    default_username = _default_username()
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer()),
        sa.column("username", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("last_seen_at", sa.DateTime()),
    )
    op.bulk_insert(
        users_table,
        [
            {
                "username": default_username,
                "created_at": now,
                "last_seen_at": now,
            }
        ],
    )
    default_user_id = (
        op.get_bind()
        .execute(sa.select(users_table.c.id).where(users_table.c.username == default_username))
        .scalar_one()
    )

    op.execute(
        f"UPDATE analyses SET created_by_user_id = {default_user_id} "
        "WHERE created_by_user_id IS NULL"
    )
    op.execute(
        f"UPDATE analysis_queue SET requested_by_user_id = {default_user_id} "
        "WHERE requested_by_user_id IS NULL"
    )
    op.execute(
        "INSERT INTO analysis_requests "
        "(user_id, ticker, trade_date, analysis_id, queue_id, source, status, "
        "requested_at, completed_at, error_message) "
        f"SELECT {default_user_id}, ticker, trade_date, id, NULL, 'backfill_analysis', status, "
        "run_at, completed_at, error_message FROM analyses"
    )
    op.execute(
        "INSERT INTO analysis_requests "
        "(user_id, ticker, trade_date, analysis_id, queue_id, source, status, "
        "requested_at, completed_at, error_message) "
        f"SELECT {default_user_id}, ticker, trade_date, analysis_id, id, 'backfill_queue', status, "
        "queued_at, completed_at, last_error FROM analysis_queue"
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_requests_ticker"), table_name="analysis_requests")
    op.drop_table("analysis_requests")

    with op.batch_alter_table("analysis_queue") as batch_op:
        batch_op.drop_constraint(
            "fk_analysis_queue_requested_by_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("requested_by_user_id")

    with op.batch_alter_table("analyses") as batch_op:
        batch_op.drop_constraint("fk_analyses_created_by_user_id_users", type_="foreignkey")
        batch_op.drop_column("created_by_user_id")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")


def _default_username() -> str:
    username = getpass.getuser().strip()
    return username or "local"
