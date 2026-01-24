#!/usr/bin/env python
"""Direct test of the paper trading engine."""

from trading_bot.paper.runner import run_paper_trading

print("Starting paper trading backtest on last week of data...")
print("Symbols: AAPL, MSFT, GOOGL, TSLA")
print()

try:
    summary = run_paper_trading(
        config_path="configs/default.yaml",
        symbols=["AAPL", "MSFT", "GOOGL", "TSLA"],
        period="1w",
        interval="1d",
        start_cash=100_000.0,
        db_path="data/trades.sqlite",
        iterations=1,
        ui=False,  # No UI, just run backtest
    )
    print(f"\n✓ Backtest completed. Ran {summary.iterations} iteration(s)")
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
