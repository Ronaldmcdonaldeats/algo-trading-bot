from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from rich.console import Console

from trading_bot.engine.paper import PaperEngine, PaperEngineConfig
from trading_bot.schedule.us_equities import MarketSchedule, parse_interval


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
    db_path: str = "trades.sqlite",
    sleep_seconds: float = 60.0,
    iterations: int = 1,
    ui: bool = True,
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
    min_fee: float = 0.0,
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
    )

    engine = PaperEngine(cfg=engine_cfg)

    try:
        td = parse_interval(interval)
        market_hours_only = td < timedelta(days=1)
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

    while True:
        if iterations > 0 and engine.iteration >= iterations:
            break

        now = datetime.now(tz=timezone.utc)

        if not schedule.due(now):
            time.sleep(min(60.0, max(0.5, schedule.seconds_until_next(now))))
            continue

        update = engine.step(now=now)
        schedule.mark_ran(now)

        equity = update.portfolio.equity(update.prices)
        console.print(
            f"[paper] iter={update.iteration} cash={update.portfolio.cash:,.2f} "
            f"equity={equity:,.2f} fills={len(update.fills)} rejections={len(update.rejections)}"
        )

    return PaperRunSummary(iterations=engine.iteration)
