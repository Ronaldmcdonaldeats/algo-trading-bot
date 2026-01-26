import sqlite3
import os

db_path = "trading_bot.db"

if not os.path.exists(db_path):
    print("[INFO] No database found yet. Bot may not have executed trades.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"[DB] Tables: {tables}")
    
    # Check trades
    try:
        cursor.execute("SELECT COUNT(*) FROM trades;")
        count = cursor.fetchone()[0]
        print(f"[DB] Total trades: {count}")
        
        if count > 0:
            cursor.execute("SELECT symbol, quantity, entry_price, status FROM trades ORDER BY created_at DESC LIMIT 10;")
            print("\n[Recent Trades]:")
            for row in cursor.fetchall():
                print(f"  {row}")
    except Exception as e:
        print(f"[DB] No trades table or error: {e}")
    
    conn.close()
