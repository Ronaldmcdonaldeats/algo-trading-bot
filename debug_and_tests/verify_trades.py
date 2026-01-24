import sqlite3
import json

conn = sqlite3.connect('data/trades.sqlite')
cursor = conn.cursor()

print("=" * 80)
print("TRADE EXECUTION VERIFICATION")
print("=" * 80)

# Check orders
cursor.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
print("\n[ORDERS BY STATUS]")
for status, count in cursor.fetchall():
    print(f"  {status}: {count}")

# Check accepted/filled orders
cursor.execute("""
SELECT symbol, side, quantity, status, created_at 
FROM orders 
WHERE status IN ('ACCEPTED', 'FILLED', 'PARTIALLY_FILLED')
LIMIT 10
""")
rows = cursor.fetchall()
print(f"\n[ACCEPTED/FILLED ORDERS (showing {len(rows)} of matched)]")
if rows:
    for symbol, side, qty, status, created in rows:
        print(f"  {symbol:6} {side:6} {qty:6} shares - {status:15} ({created})")
else:
    print("  No accepted/filled orders found")

# Check portfolio
cursor.execute("""
SELECT timestamp, cash, equity, total_value, pnl 
FROM portfolio_snapshots 
ORDER BY timestamp DESC 
LIMIT 5
""")
print("\n[PORTFOLIO SNAPSHOTS (last 5)]")
for ts, cash, equity, total, pnl in cursor.fetchall():
    print(f"  {ts} | Cash: ${cash:10,.2f} | Equity: ${equity:10,.2f} | Total: ${total:10,.2f} | PnL: ${pnl:8,.2f}")

# Check fills
cursor.execute("SELECT COUNT(*) FROM fills")
fills_count = cursor.fetchone()[0]
print(f"\n[FILLS] Total fills recorded: {fills_count}")

if fills_count > 0:
    cursor.execute("SELECT symbol, side, quantity, fill_price, filled_at FROM fills LIMIT 5")
    for symbol, side, qty, price, filled in cursor.fetchall():
        print(f"  {symbol} {side} {qty} @ ${price} ({filled})")

# Check strategy decisions
cursor.execute("SELECT COUNT(*) FROM strategy_decisions")
decisions = cursor.fetchone()[0]
print(f"\n[STRATEGY DECISIONS] Total signals: {decisions}")

# Check if positions exist
cursor.execute("""
SELECT symbol, quantity, avg_entry_price, current_price, unrealized_pnl
FROM positions
WHERE quantity != 0
""")
rows = cursor.fetchall()
print(f"\n[OPEN POSITIONS] {len(rows)} symbols with open positions:")
if rows:
    for symbol, qty, entry, current, pnl in rows:
        print(f"  {symbol}: {qty} shares @ ${entry:.2f} (current: ${current:.2f}, PnL: ${pnl:.2f})")
else:
    print("  No open positions (all cash)")

# Overall summary
cursor.execute("SELECT SUM(quantity) FROM orders WHERE status IN ('ACCEPTED', 'FILLED', 'PARTIALLY_FILLED')")
total_filled = cursor.fetchone()[0] or 0
print(f"\n[SUMMARY]")
print(f"  Total filled quantity: {total_filled} shares")
print(f"  Trades executed: {'YES ✓' if total_filled > 0 else 'NO ✗'}")

conn.close()
