import sqlite3
import os

db_path = "trading_bot.db"

if not os.path.exists(db_path):
    print("[INFO] No database found yet.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check fills table (where trades are recorded)
    try:
        cursor.execute("SELECT COUNT(*) FROM fills;")
        count = cursor.fetchone()[0]
        print(f"[DB] Total fills (executions): {count}")
        
        if count > 0:
            cursor.execute("SELECT symbol, quantity, fill_price, timestamp FROM fills ORDER BY timestamp DESC LIMIT 20;")
            print("\n[Recent Fills]:")
            for row in cursor.fetchall():
                print(f"  {row[0]}: {row[1]} shares @ ${row[2]:.2f} at {row[3]}")
    except Exception as e:
        print(f"[DB] Error checking fills: {e}")
    
    # Check orders
    try:
        cursor.execute("SELECT COUNT(*) FROM orders;")
        count = cursor.fetchone()[0]
        print(f"\n[DB] Total orders: {count}")
        
        if count > 0:
            cursor.execute("SELECT symbol, qty, side, status FROM orders ORDER BY created_at DESC LIMIT 10;")
            print("\n[Recent Orders]:")
            for row in cursor.fetchall():
                print(f"  {row[0]}: {row[1]} {row[2]} ({row[3]})")
    except Exception as e:
        print(f"[DB] Error checking orders: {e}")
    
    conn.close()
