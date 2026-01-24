import sqlite3

conn = sqlite3.connect('data/trades.sqlite')
cursor = conn.cursor()

print("=" * 80)
print("TRADE EXECUTION TEST RESULTS")
print("=" * 80)

# Check orders
cursor.execute("SELECT status, COUNT(*) FROM orders GROUP BY status")
orders = cursor.fetchall()
print("\n[ORDERS BY STATUS]")
if orders:
    for status, count in orders:
        print(f"  {status}: {count}")
else:
    print("  No orders found")

# Check for any rejected orders
cursor.execute("SELECT reject_reason, COUNT(*) FROM orders WHERE reject_reason IS NOT NULL GROUP BY reject_reason")
rejected = cursor.fetchall()
if rejected:
    print("\n[REJECTION REASONS]")
    for reason, count in rejected:
        print(f"  {reason}: {count}")

# Check fills
cursor.execute("SELECT COUNT(*) FROM fills")
fills_count = cursor.fetchone()[0]
print(f"\n[FILLS] Total: {fills_count}")
if fills_count > 0:
    cursor.execute("SELECT symbol, side, qty, price FROM fills LIMIT 3")
    for symbol, side, qty, price in cursor.fetchall():
        print(f"  {symbol} {side} {qty} @ ${price:.2f}")

# Check portfolio
cursor.execute("SELECT COUNT(*) FROM portfolio_snapshots")
snap_count = cursor.fetchone()[0]
print(f"\n[PORTFOLIO SNAPSHOTS] Total: {snap_count}")
if snap_count > 0:
    cursor.execute("SELECT cash, equity FROM portfolio_snapshots ORDER BY ts DESC LIMIT 1")
    cash, equity = cursor.fetchone()
    print(f"  Final: Cash=${cash:,.2f}, Equity=${equity:,.2f}")

# Check positions
cursor.execute("SELECT COUNT(*) FROM position_snapshots WHERE qty != 0")
pos_count = cursor.fetchone()[0]
print(f"\n[OPEN POSITIONS] {pos_count} snapshots with positions")
if pos_count > 0:
    cursor.execute("SELECT DISTINCT symbol FROM position_snapshots WHERE qty != 0")
    symbols = [s[0] for s in cursor.fetchall()]
    print(f"  Symbols: {', '.join(symbols)}")

# Check strategy signals
cursor.execute("SELECT COUNT(*) FROM strategy_decisions")
decisions = cursor.fetchone()[0]
print(f"\n[STRATEGY SIGNALS] Total: {decisions}")

print("\n" + "=" * 80)
print("TEST RESULT: ", end="")
if fills_count > 0:
    print("✓ TRADES EXECUTED SUCCESSFULLY")
    print("The bot CAN buy and sell stocks!")
else:
    print("✗ NO TRADES EXECUTED")
    if orders:
        cursor.execute("SELECT reject_reason FROM orders LIMIT 1")
        reason = cursor.fetchone()[0]
        print(f"Reason: {reason}")
print("=" * 80)

conn.close()
