from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from rich.align import Align
from rich.console import Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from trading_bot.engine.paper import PaperEngineUpdate

_SPARK_CHARS = "▁▂▃▄▅▆▇█"


class ActivityLog:
    """Track recent activity for dashboard display"""
    def __init__(self, max_size: int = 20):
        self.activities: list[dict] = []
        self.max_size = max_size
        self.current_action = "Initializing..."
        self.current_symbol = ""
        self.current_detail = ""

    def add(self, action: str, symbol: str = "", detail: str = ""):
        """Add activity to log"""
        self.current_action = action
        self.current_symbol = symbol
        self.current_detail = detail
        
        self.activities.append({
            "timestamp": datetime.now().isoformat(timespec='seconds'),
            "action": action,
            "symbol": symbol,
            "detail": detail,
        })
        # Keep only recent activities
        if len(self.activities) > self.max_size:
            self.activities = self.activities[-self.max_size:]

    def get_status_text(self) -> str:
        """Get formatted status text"""
        if self.current_symbol:
            return f"📊 {self.current_action} | {self.current_symbol} | {self.current_detail}"
        else:
            return f"📊 {self.current_action} | {self.current_detail}"


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


def _get_action_status(update: PaperEngineUpdate, state: DashboardState) -> str:
    """Generate human-readable status of what's happening right now"""
    pf = update.portfolio
    
    # Check what happened this iteration
    if update.fills:
        buy_count = sum(1 for f in update.fills if f.side == "BUY")
        sell_count = sum(1 for f in update.fills if f.side == "SELL")
        
        if buy_count > 0 and sell_count == 0:
            symbols = ", ".join([f.symbol for f in update.fills if f.side == "BUY"][:3])
            return f"🟢 BUYING {buy_count} position(s): {symbols}"
        elif sell_count > 0 and buy_count == 0:
            symbols = ", ".join([f.symbol for f in update.fills if f.side == "SELL"][:3])
            return f"🔴 SELLING {sell_count} position(s): {symbols}"
        elif buy_count > 0 and sell_count > 0:
            return f"🔄 REBALANCING | Bought {buy_count}, Sold {sell_count}"
        else:
            return f"✓ Executed {len(update.fills)} fills"
    
    if update.rejections:
        reasons = ", ".join([r.reason for r in update.rejections[:2]])
        return f"⚠️  {len(update.rejections)} order(s) rejected: {reasons[:50]}"
    
    # Check for any signals but no fills (holding/waiting)
    if update.signals:
        positive_signals = sum(1 for s in update.signals.values() if s == 1)
        negative_signals = sum(1 for s in update.signals.values() if s == -1)
        
        if positive_signals > 0 and len(pf.positions) > 0:
            return f"📊 ANALYZING {len(update.signals)} stocks | Holding {len(pf.positions)} positions"
        elif positive_signals > 0:
            return f"📊 ANALYZING {len(update.signals)} stocks | Found {positive_signals} buy signals"
        else:
            return f"📊 ANALYZING {len(update.signals)} stocks | Waiting for signals"
    
    return "🔄 Processing data..."


@dataclass
class DashboardState:
    equity_history: list[float]
    max_history: int = 1440  # Keep max 1440 points (prevents unbounded memory growth)
    activity_log: ActivityLog = None
    
    def __post_init__(self):
        if self.activity_log is None:
            self.activity_log = ActivityLog()


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

    # Determine action status based on what happened this iteration
    action_text = _get_action_status(update, state)
    
    header = Text(
        f"Paper Trading  |  iter={update.iteration}  |  {update.ts.isoformat(timespec='seconds')}Z",
        style="bold",
    )
    
    # Current action status panel
    status_panel = Panel(
        Text(action_text, style="cyan bold"),
        title="Current Activity",
        border_style="cyan",
    )

    summary = Table.grid(padding=(0, 1))
    summary.add_column(justify="right")
    summary.add_column(justify="left")
    summary.add_row("Available Cash", f"${pf.cash:,.2f}")
    summary.add_row("Total Value", f"${equity:,.2f}")
    summary.add_row("Unrealized Profit/Loss", f"${unreal:,.2f}")
    summary.add_row("Realized Profit/Loss", f"${realized:,.2f}")
    summary.add_row("Trading Fees Paid", f"${pf.fees_paid:,.2f}")

    positions = Table(title="Current Positions", expand=True)
    positions.add_column("Stock")
    positions.add_column("Shares", justify="right")
    positions.add_column("Avg Price", justify="right")
    positions.add_column("Current Price", justify="right")
    positions.add_column("Profit/Loss", justify="right")
    positions.add_column("Stop Loss", justify="right")
    positions.add_column("Take Profit", justify="right")

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

    fills = Table(title="Recent Trades (This Update)", expand=True)
    fills.add_column("Stock")
    fills.add_column("Type")
    fills.add_column("Shares", justify="right")
    fills.add_column("Price", justify="right")
    fills.add_column("Fee", justify="right")
    fills.add_column("What Happened", justify="left")

    if update.fills:
        for f in update.fills[-10:]:
            # Determine action description based on side
            if f.side == "BUY":
                action = "🟢 BOUGHT"
                action_type = "Purchase"
            elif f.side == "SELL":
                action = "🔴 SOLD"
                action_type = "Sell"
            else:
                action = f.side
                action_type = f.side
            
            fills.add_row(
                f.symbol,
                action_type,
                str(f.qty),
                f"${f.price:,.2f}",
                f"${f.fee:,.2f}",
                f"{action} - {f.note}",
            )
    else:
        fills.add_row("-", "-", "-", "-", "-", "-")

    rejs = Table(title="Failed Orders (This Update)", expand=True)
    rejs.add_column("Stock")
    rejs.add_column("Action")
    rejs.add_column("Shares", justify="right")
    rejs.add_column("Why It Failed")
    if update.rejections:
        for r in update.rejections[-10:]:
            action_type = "Buy" if r.order.side == "BUY" else "Sell"
            rejs.add_row(r.order.symbol, action_type, str(r.order.qty), r.reason)
    else:
        rejs.add_row("-", "-", "-", "-")

    equity_panel = Panel(
        Align.center(
            Group(
                Text(f"Account Value: ${equity:,.2f}", style="bold"),
                Text(_sparkline(state.equity_history, width=60), style="cyan"),
            ),
            vertical="middle",
        ),
        title="Portfolio Growth",
    )

    layout = Layout()
    layout.split_column(
        Layout(Panel(header), size=3),
        Layout(status_panel, size=4),
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
