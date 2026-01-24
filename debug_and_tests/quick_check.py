import sqlite3

conn = sqlite3.connect('data/trades.sqlite')
cursor = conn.cursor()

cursor.execute('SELECT status, COUNT(*) FROM orders GROUP BY status')
print("Order Statuses:")
for status, count in cursor.fetchall():
    print(f"  {status}: {count}")

cursor.execute('SELECT COUNT(*) FROM fills')
fills = cursor.fetchone()[0]
print(f"\nTotal Fills: {fills}")

cursor.execute('SELECT cash FROM portfolio_snapshots ORDER BY timestamp DESC LIMIT 1')
cash = cursor.fetchone()
print(f"Final Cash: ${cash[0]:,.2f}" if cash else "No data")

conn.close()
