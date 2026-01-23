from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BacktestResult:
    sharpe: float | None = None
    max_drawdown: float | None = None


def run_backtest(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Placeholder for a backtrader/zipline-based backtest runner.

    The next step is to:
    - translate `generate_signals` into a backtrader Strategy
      (or compute indicators inside backtrader)
    - add analyzers for Sharpe + drawdown
    - add walk-forward optimization + Monte Carlo
    """
    raise NotImplementedError("Backtesting engine not wired up yet")
