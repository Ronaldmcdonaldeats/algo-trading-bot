from __future__ import annotations

from dataclasses import dataclass

from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from trading_bot.engine.paper import PaperEngineUpdate

_SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _sparkline(values: list[float], *, width: int = 40) -> str:
    if not values:
        return ""

    if len(values) > width:
        step = max(1, len(values) // width)
        vals = values[::step]
    else:
        vals = values

    lo = min(vals)
    hi = max(vals)
    if hi <= lo:
        return _SPARK_CHARS[0] * len(vals)

    out = []
    for v in vals:
        n = int((float(v) - lo) / (hi - lo) * (len(_SPARK_CHARS) - 1))
        out.append(_SPARK_CHARS[max(0, min(n, len(_SPARK_CHARS) - 1))])
    return "".join(out)


@dataclass
class DashboardState:
    equity_history: list[float]
    max_history: int = 1440  # Keep max 1440 points (prevents unbounded memory growth)


def render_paper_dashboard(update: PaperEngineUpdate, state: DashboardState) -> Layout:
    prices = update.prices
    pf = update.portfolio

    equity = pf.equity(prices)
    unreal = pf.unrealized_pnl(prices)
    realized = pf.realized_pnl()

    state.equity_history.append(float(equity))
    # Prevent unbounded memory growth - keep only recent history
    if len(state.equity_history) > state.max_history:
        state.equity_history = state.equity_history[-state.max_history:]

    header = Text(
        f"Paper Trading  |  iter={update.iteration}  |  {update.ts.isoformat(timespec='seconds')}Z",
        style="bold",
    )

    summary = Table.grid(padding=(0, 1))
    summary.add_column(justify="right")
    summary.add_column(justify="left")
    summary.add_row("Cash", f"{pf.cash:,.2f}")
    summary.add_row("Equity", f"{equity:,.2f}")
    summary.add_row("Unrealized", f"{unreal:,.2f}")
    summary.add_row("Realized", f"{realized:,.2f}")
    summary.add_row("Fees", f"{pf.fees_paid:,.2f}")

    positions = Table(title="Positions", expand=True)
    positions.add_column("Symbol")
    positions.add_column("Qty", justify="right")
    positions.add_column("Avg", justify="right")
    positions.add_column("Last", justify="right")
    positions.add_column("Unrl PnL", justify="right")
    positions.add_column("SL", justify="right")
    positions.add_column("TP", justify="right")

    any_pos = False
    for sym, pos in sorted(pf.positions.items()):
        if pos.qty == 0:
            continue
        any_pos = True
        last = float(prices.get(sym, 0.0))
        upnl = pos.unrealized_pnl(last)
        positions.add_row(
            sym,
            str(pos.qty),
            f"{pos.avg_price:,.2f}",
            f"{last:,.2f}",
            f"{upnl:,.2f}",
            "" if pos.stop_loss is None else f"{pos.stop_loss:,.2f}",
            "" if pos.take_profit is None else f"{pos.take_profit:,.2f}",
        )

    if not any_pos:
        positions.add_row("-", "-", "-", "-", "-", "-", "-")

    fills = Table(title="Recent fills (this tick)", expand=True)
    fills.add_column("Symbol")
    fills.add_column("Side")
    fills.add_column("Qty", justify="right")
    fills.add_column("Price", justify="right")
    fills.add_column("Fee", justify="right")
    fills.add_column("Note")

    if update.fills:
        for f in update.fills[-10:]:
            fills.add_row(
                f.symbol,
                f.side,
                str(f.qty),
                f"{f.price:,.2f}",
                f"{f.fee:,.2f}",
                f.note,
            )
    else:
        fills.add_row("-", "-", "-", "-", "-", "-")

    rejs = Table(title="Rejections (this tick)", expand=True)
    rejs.add_column("Symbol")
    rejs.add_column("Side")
    rejs.add_column("Qty", justify="right")
    rejs.add_column("Reason")
    if update.rejections:
        for r in update.rejections[-10:]:
            rejs.add_row(r.order.symbol, r.order.side, str(r.order.qty), r.reason)
    else:
        rejs.add_row("-", "-", "-", "-")

    equity_panel = Panel(
        Align.center(
            Group(
                Text(f"Equity: {equity:,.2f}", style="bold"),
                Text(_sparkline(state.equity_history, width=60), style="cyan"),
            ),
            vertical="middle",
        ),
        title="Equity curve",
    )

    layout = Layout()
    layout.split_column(
        Layout(Panel(header), size=3),
        Layout(name="body"),
    )

    layout["body"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=1),
    )

    layout["left"].split_column(
        Layout(Panel(summary, title="Portfolio"), size=8),
        Layout(Panel(positions)),
        Layout(Panel(Group(fills, rejs))),
    )

    layout["right"].update(equity_panel)
    return layout
