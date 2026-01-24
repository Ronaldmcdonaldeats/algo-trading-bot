import sqlite3
import json

conn = sqlite3.connect('data/trades.sqlite')
cursor = conn.cursor()

# Get table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Available tables:')
for t in tables:
    print(f'  - {t[0]}')
print()

# Check each table
for table_name in [t[0] for t in tables]:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'{table_name}: {count} records')
    except:
        pass

# Check if fills exist
try:
    cursor.execute('SELECT * FROM fills ORDER BY timestamp DESC LIMIT 5')
    cols = [description[0] for description in cursor.description]
    print('\nRecent fills:')
    print('Columns:', cols)
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print('  ', row)
    else:
        print('  (No fills recorded)')
except Exception as e:
    print(f'Error checking fills: {e}')

# Check trades
try:
    cursor.execute('SELECT COUNT(*) FROM trades')
    trade_count = cursor.fetchone()[0]
    print(f'\nTotal trades in database: {trade_count}')
    
    if trade_count > 0:
        cursor.execute('SELECT * FROM trades ORDER BY timestamp DESC LIMIT 3')
        cols = [description[0] for description in cursor.description]
        print('Recent trades:')
        for row in cursor.fetchall():
            print('  ', dict(zip(cols, row)))
except Exception as e:
    print(f'Error checking trades: {e}')

conn.close()
print('\n✅ Database check complete')
