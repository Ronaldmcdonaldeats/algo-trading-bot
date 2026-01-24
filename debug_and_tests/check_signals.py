import sqlite3
import json

conn = sqlite3.connect('data/trades.sqlite')
cursor = conn.cursor()

print("Strategy Decisions Details:")
cursor.execute("""
SELECT ts, symbol, mode, signal, confidence, votes_json 
FROM strategy_decisions 
ORDER BY ts
""")

for ts, symbol, mode, signal, confidence, votes_json in cursor.fetchall():
    print(f"\n{ts} | {symbol} | {mode}")
    print(f"  Signal: {signal} (conf: {confidence:.2f})")
    if votes_json:
        try:
            votes = json.loads(votes_json)
            print(f"  Votes: {votes}")
        except:
            pass

conn.close()
