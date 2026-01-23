from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytest.importorskip("duckdb")

from trading_bot.analytics.duckdb_pipeline import build_analytics_db, performance_summary
from trading_bot.core.models import Portfolio
from trading_bot.db.repository import SqliteRepository


def test_build_and_report(tmp_path) -> None:
    sqlite_path = tmp_path / "events.sqlite"
    duckdb_path = tmp_path / "analytics.duckdb"

    repo = SqliteRepository(db_path=sqlite_path)
    repo.init_db()

    # Two snapshots with increasing equity.
    pf = Portfolio(cash=1000.0)
    repo.log_snapshot(ts=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc), portfolio=pf, prices={})
    pf.cash = 1100.0
    repo.log_snapshot(ts=datetime(2026, 1, 2, 0, 0, tzinfo=timezone.utc), portfolio=pf, prices={})

    build_analytics_db(sqlite_db=sqlite_path, duckdb_db=duckdb_path)
    summary = performance_summary(duckdb_db=duckdb_path)

    assert summary.start_equity == 1000.0
    assert summary.end_equity == 1100.0
    assert summary.total_return == pytest.approx(0.1)
