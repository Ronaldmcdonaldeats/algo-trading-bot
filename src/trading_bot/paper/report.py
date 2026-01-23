from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from trading_bot.db.repository import SqliteRepository


def paper_report(*, db_path: str, limit: int = 20) -> int:
    repo = SqliteRepository(db_path=Path(db_path))
    snap = repo.latest_portfolio_snapshot()
    fills = repo.recent_fills(limit=int(limit))

    console = Console()

    if snap is None:
        console.print(f"No snapshots found in {db_path}")
        return 1

    console.print(
        f"Latest snapshot: {snap.ts.isoformat(timespec='seconds')}Z  cash={snap.cash:,.2f} "
        f"equity={snap.equity:,.2f} unrealized={snap.unrealized_pnl:,.2f} "
        f"fees={snap.fees_paid:,.2f}"
    )

    t = Table(title=f"Recent fills (last {min(int(limit), len(fills))})")
    t.add_column("ts")
    t.add_column("symbol")
    t.add_column("side")
    t.add_column("qty", justify="right")
    t.add_column("price", justify="right")
    t.add_column("fee", justify="right")
    t.add_column("note")

    for f in fills:
        t.add_row(
            f.ts.isoformat(timespec="seconds"),
            f.symbol,
            f.side,
            str(f.qty),
            f"{f.price:,.2f}",
            f"{f.fee:,.2f}",
            f.note,
        )

    console.print(t)
    return 0
