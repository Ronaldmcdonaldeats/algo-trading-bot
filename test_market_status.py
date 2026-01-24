#!/usr/bin/env python
"""Test if market is open and attempt a trade."""

from datetime import datetime
from trading_bot.schedule.us_equities import is_market_open, to_eastern

now = datetime.now()
is_open = is_market_open(now)
eastern = to_eastern(now)

print(f"Current UTC time: {now}")
print(f"Current Eastern time: {eastern}")
print(f"Market status: {'OPEN ✓' if is_open else 'CLOSED ✗'}")
print()

# Test paper trading regardless of market hours
print("Testing paper trading capability...")
from trading_bot.paper.runner import run_paper_trading

# Quick test: 2 iterations with minimal symbols
result = run_paper_trading(
    config_path="configs/default.yaml",
    symbols=["SPY"],
    period="30d",
    interval="1d",
    start_cash=10_000.0,
    db_path="data/trades.sqlite",
    sleep_seconds=0.1,
    iterations=2,
    ui=False,
    commission_bps=0.0,
    slippage_bps=0.0,
)

print(f"Paper trading completed: {result}")
print()
print("✓ Trading works regardless of market hours in paper mode!")
