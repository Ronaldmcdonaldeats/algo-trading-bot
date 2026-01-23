from __future__ import annotations

from pathlib import Path

from rich.console import Console

from trading_bot.analytics.duckdb_pipeline import build_analytics_db, performance_summary


def paper_analytics_build(*, db_path: str, duckdb_path: str) -> int:
    build_analytics_db(sqlite_db=Path(db_path), duckdb_db=Path(duckdb_path))
    Console().print(f"Built DuckDB analytics DB: {duckdb_path} (from {db_path})")
    return 0


def paper_analytics_report(*, duckdb_path: str) -> int:
    summary = performance_summary(duckdb_db=Path(duckdb_path))
    Console().print(
        f"Performance: start={summary.start_ts} end={summary.end_ts} "
        f"start_eq={summary.start_equity:,.2f} end_eq={summary.end_equity:,.2f} "
        f"return={summary.total_return*100:.2f}% max_dd={summary.max_drawdown*100:.2f}%"
    )
    return 0
