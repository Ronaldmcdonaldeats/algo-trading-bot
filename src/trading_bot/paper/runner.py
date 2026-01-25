from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from rich.console import Console

from trading_bot.engine.paper import PaperEngine, PaperEngineConfig
from trading_bot.schedule.us_equities import MarketSchedule, parse_interval
from trading_bot.learn.ml_signals import MLSignalManager
from trading_bot.analytics.realtime_dashboard import RealtimeDashboard


@dataclass(frozen=True)
class PaperRunSummary:
    iterations: int


def run_paper_trading(
    *,
    config_path: str,
    symbols: list[str],
    period: str = "6mo",
    interval: str = "1d",
    start_cash: float = 100_000.0,
    db_path: str = "data/trades.sqlite",
    sleep_seconds: float = 30.0,
    iterations: int = 1,
    ui: bool = True,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
    min_fee: float = 0.0,
    ignore_market_hours: bool = False,
    memory_mode: bool = False,
) -> PaperRunSummary:
    engine_cfg = PaperEngineConfig(
        config_path=config_path,
        db_path=db_path,
        symbols=symbols,
        period=period,
        interval=interval,
        start_cash=float(start_cash),
        sleep_seconds=float(sleep_seconds),
        iterations=int(iterations),
        commission_bps=float(commission_bps),
        slippage_bps=float(slippage_bps),
        min_fee=float(min_fee),
        ignore_market_hours=bool(ignore_market_hours),
        memory_mode=bool(memory_mode),
    )

    engine = PaperEngine(cfg=engine_cfg)
    
    # Initialize realtime dashboard
    dashboard = RealtimeDashboard()
    dashboard.initialize(float(start_cash))

    try:
        td = parse_interval(interval)
        market_hours_only = td < timedelta(days=1) and not ignore_market_hours
    except ValueError:
        # If interval isn't parseable, fall back to a simple time-based schedule.
        td = timedelta(seconds=float(sleep_seconds))
        market_hours_only = False

    schedule = MarketSchedule(interval=td, market_hours_only=market_hours_only)

    if ui:
        from trading_bot.tui.paper_app import run_paper_tui

        run_paper_tui(engine=engine, schedule=schedule)
        return PaperRunSummary(iterations=engine.iteration)

    console = Console()

    first_run = True
    while True:
        if iterations > 0 and engine.iteration >= iterations:
            break

        now = datetime.now(tz=timezone.utc)

        if not first_run and not schedule.due(now):
            time.sleep(min(sleep_seconds, max(0.5, schedule.seconds_until_next(now))))
            continue

        first_run = False
        update = engine.step(now=now)
        schedule.mark_ran(now)

        equity = update.portfolio.equity(update.prices)
        
        # Update dashboard
        dashboard.update_portfolio(
            cash=update.portfolio.cash,
            equity=equity,
            buying_power=equity,
            total_return_pct=(equity - float(start_cash)) / float(start_cash) * 100,
            realized_pnl=0.0,  # Could be enhanced with actual tracking
            unrealized_pnl=0.0,
            num_open_positions=len([p for p in update.portfolio.positions.values() if p.qty != 0]),
            num_trades_today=len(update.fills),
        )
        
        dashboard.update_metrics(
            sharpe_ratio=update.sharpe_ratio,
            sortino_ratio=0.0,  # Could be calculated
            max_drawdown_pct=update.max_drawdown_pct,
            win_rate_pct=update.win_rate * 100,
            profit_factor=1.0,  # Could be calculated
            total_return_pct=(equity - float(start_cash)) / float(start_cash) * 100,
            num_trades=update.num_trades,
            num_wins=int(update.win_rate * update.num_trades) if update.num_trades > 0 else 0,
            num_losses=update.num_trades - int(update.win_rate * update.num_trades) if update.num_trades > 0 else 0,
            avg_win=0.0,  # Could be calculated
            avg_loss=0.0,  # Could be calculated
        )
        
        # Format metrics for display
        sharpe_str = f"{update.sharpe_ratio:+.2f}" if update.sharpe_ratio != 0 else "N/A"
        dd_str = f"{update.max_drawdown_pct*100:.1f}%" if update.max_drawdown_pct != 0 else "0.0%"
        wr_str = f"{update.win_rate*100:.0f}%" if update.num_trades > 0 else "N/A"
        pnl_str = f"{update.current_pnl:+,.2f}" if update.current_pnl != 0 else "0.00"
        
        console.print(
            f"[ITERATION {update.iteration}] {update.ts.strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Equity: ${equity:,.2f} | P&L: {pnl_str} | "
            f"Sharpe: {sharpe_str} | DD: {dd_str} | Win Rate: {wr_str} | "
            f"Trades: {update.num_trades} | Fills: {len(update.fills)}"
        )

    return PaperRunSummary(iterations=engine.iteration)
