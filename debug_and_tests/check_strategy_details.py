#!/usr/bin/env python
"""Check what strategies are generating."""

import sqlite3
import json

# Run backtest first
from trading_bot.paper.runner import run_paper_trading

print("Running backtest...")
run_paper_trading(
    config_path="configs/default.yaml",
    symbols=["AAPL", "MSFT"],
    period="1w",
    interval="1d",
    iterations=1,
    ui=False,
)

# Now check what signals were generated
conn = sqlite3.connect('data/trades.sqlite')
cursor = conn.cursor()

print("\n" + "="*80)
print("STRATEGY SIGNALS FROM BACKTEST")
print("="*80)

cursor.execute("""
SELECT ts, symbol, mode, signal, confidence, votes_json, explanations_json
FROM strategy_decisions
ORDER BY ts
""")

decisions = cursor.fetchall()
print(f"\nTotal decisions: {len(decisions)}\n")

for ts, symbol, mode, signal, confidence, votes_json, explanations_json in decisions:
    print(f"{ts} | {symbol} | {mode}")
    print(f"  Signal: {signal:+d}  Confidence: {confidence:.2f}")
    
    if votes_json:
        try:
            votes = json.loads(votes_json)
            print(f"  Votes: {votes}")
        except:
            pass
    
    if explanations_json:
        try:
            explanations = json.loads(explanations_json)
            if explanations:
                print(f"  Why: {list(explanations.values())[0][:60]}...")
        except:
            pass
    print()

# Check orders
cursor.execute("SELECT COUNT(*) FROM orders")
order_count = cursor.fetchone()[0]
print(f"Orders created: {order_count}")

if order_count > 0:
    cursor.execute("SELECT symbol, side, qty, status FROM orders LIMIT 5")
    for symbol, side, qty, status in cursor.fetchall():
        print(f"  {symbol} {side} {qty} - {status}")

conn.close()
