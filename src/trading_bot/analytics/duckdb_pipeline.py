from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine


@dataclass(frozen=True)
class PerformanceSummary:
    start_ts: datetime
    end_ts: datetime
    start_equity: float
    end_equity: float
    total_return: float
    max_drawdown: float


def _require_duckdb():
    try:
        import duckdb  # type: ignore

        return duckdb
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "duckdb is not installed (or unsupported on this Python). "
            "DuckDB's Python package requires Python >=3.9. "
            "Install with: python -m pip install -e '.[analytics]'"
        ) from e


def build_analytics_db(*, sqlite_db: Path, duckdb_db: Path) -> None:
    """Rebuild analytics DuckDB from the SQLite event store."""

    duckdb = _require_duckdb()

    engine = create_engine(f"sqlite:///{sqlite_db}")

    tables = {
        "orders": pd.read_sql_query("select * from orders", engine),
        "fills": pd.read_sql_query("select * from fills", engine),
        "portfolio_snapshots": pd.read_sql_query("select * from portfolio_snapshots", engine),
        "position_snapshots": pd.read_sql_query("select * from position_snapshots", engine),
    }

    con = duckdb.connect(str(duckdb_db))
    try:
        for name, df in tables.items():
            con.register("df", df)
            con.execute(f"create or replace table {name} as select * from df")
            con.unregister("df")
    finally:
        con.close()


def performance_summary(*, duckdb_db: Path) -> PerformanceSummary:
    duckdb = _require_duckdb()

    con = duckdb.connect(str(duckdb_db), read_only=True)
    try:
        df = con.execute(
            "select ts, equity from portfolio_snapshots order by ts asc"
        ).fetchdf()  # type: ignore[attr-defined]
    finally:
        con.close()

    if df is None or df.empty:
        raise ValueError("No portfolio snapshots found")

    equity = df["equity"].astype(float)
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0

    start_eq = float(equity.iloc[0])
    end_eq = float(equity.iloc[-1])

    total_ret = 0.0 if start_eq == 0 else (end_eq / start_eq - 1.0)
    max_dd = float(drawdown.min())

    return PerformanceSummary(
        start_ts=pd.to_datetime(df["ts"].iloc[0]).to_pydatetime(),
        end_ts=pd.to_datetime(df["ts"].iloc[-1]).to_pydatetime(),
        start_equity=start_eq,
        end_equity=end_eq,
        total_return=float(total_ret),
        max_drawdown=max_dd,
    )
