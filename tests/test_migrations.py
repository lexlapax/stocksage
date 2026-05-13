"""Migration smoke tests for schema backfill behavior."""

import os
import subprocess
import sys

from sqlalchemy import create_engine, text


def test_user_identity_migration_backfills_existing_rows(tmp_path):
    db_path = tmp_path / "stocksage-migration.db"
    database_url = f"sqlite:///{db_path}"
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    env["STOCKSAGE_DATA_DIR"] = str(tmp_path / "data")

    _run_alembic("upgrade", "8adcb5d6f3d4", env)
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO analyses "
                "(ticker, trade_date, run_at, completed_at, status, rating) "
                "VALUES ('AAPL', '2026-01-02', '2026-01-02 09:00:00', "
                "'2026-01-02 09:05:00', 'completed', 'Overweight')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO analysis_queue "
                "(ticker, trade_date, priority, queued_at, analysis_id, status, "
                "started_at, completed_at, attempts, last_error) "
                "VALUES ('MSFT', '2026-01-03', 1, '2026-01-03 09:00:00', "
                "NULL, 'queued', NULL, NULL, 0, NULL)"
            )
        )

    _run_alembic("upgrade", "head", env)
    with engine.connect() as conn:
        users = conn.execute(text("SELECT id, username FROM users")).all()
        analysis_user = conn.execute(text("SELECT created_by_user_id FROM analyses")).scalar_one()
        queue_user = conn.execute(
            text("SELECT requested_by_user_id FROM analysis_queue")
        ).scalar_one()
        request_sources = (
            conn.execute(text("SELECT source FROM analysis_requests ORDER BY source"))
            .scalars()
            .all()
        )

    assert len(users) == 1
    assert analysis_user == users[0].id
    assert queue_user == users[0].id
    assert request_sources == ["backfill_analysis", "backfill_queue"]


def _run_alembic(command: str, revision: str, env: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", command, revision],
        cwd=os.getcwd(),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
