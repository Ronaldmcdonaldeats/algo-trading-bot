import sqlite3
import json

# Database should exist from the last test
conn = sqlite3.connect('data/trades.sqlite')
cursor = conn.cursor()

print("=" * 80)
print("CHECKING SIGNALS FROM LAST BACKTEST")
print("=" * 80)

cursor.execute("""
SELECT ts, symbol, mode, signal, confidence, votes_json
FROM strategy_decisions
ORDER BY ts
LIMIT 10
""")

rows = cursor.fetchall()
print(f"\nSignals found: {len(rows)}\n")

for ts, symbol, mode, signal, confidence, votes_json in rows:
    print(f"{ts} | {symbol:6} | {mode:10} | Signal: {signal:+d} | Conf: {confidence:.2f}")
    if votes_json:
        votes = json.loads(votes_json)
        print(f"  Votes: {votes}")

conn.close()
