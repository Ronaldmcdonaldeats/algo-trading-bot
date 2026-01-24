import sqlite3

conn = sqlite3.connect('data/trades.sqlite')
cursor = conn.cursor()

# Check orders
try:
    cursor.execute('SELECT * FROM orders LIMIT 3')
    cols = [description[0] for description in cursor.description]
    print('Order structure:')
    for col in cols:
        print(f'  - {col}')
    print()
    
    # Get recent orders
    cursor.execute('SELECT * FROM orders ORDER BY rowid DESC LIMIT 5')
    print('Recent orders:')
    for row in cursor.fetchall():
        row_dict = dict(zip(cols, row))
        print(f"\nOrder ID: {row_dict.get('id')}")
        for k, v in row_dict.items():
            if v is not None and v != '':
                print(f"  {k}: {v}")
except Exception as e:
    print(f'Error: {e}')

# Check portfolio snapshots
try:
    print('\n' + '='*50)
    print('Portfolio snapshots:')
    cursor.execute('SELECT * FROM portfolio_snapshots ORDER BY rowid DESC LIMIT 1')
    cols = [description[0] for description in cursor.description]
    for row in cursor.fetchall():
        row_dict = dict(zip(cols, row))
        for k, v in row_dict.items():
            if v is not None:
                if len(str(v)) > 100:
                    print(f"  {k}: {str(v)[:100]}...")
                else:
                    print(f"  {k}: {v}")
except Exception as e:
    print(f'Error: {e}')

# Check strategy decisions
try:
    print('\n' + '='*50)
    print('Strategy decisions:')
    cursor.execute('SELECT COUNT(*) FROM strategy_decisions')
    count = cursor.fetchone()[0]
    print(f'Total decisions: {count}')
    
    cursor.execute('SELECT * FROM strategy_decisions LIMIT 1')
    cols = [description[0] for description in cursor.description]
    print('Columns:', cols)
    
    cursor.execute('''
        SELECT symbol, signal, confidence 
        FROM strategy_decisions 
        GROUP BY symbol 
        ORDER BY rowid DESC 
        LIMIT 5
    ''')
    print('\nLast signal per symbol:')
    for row in cursor.fetchall():
        print(f"  {row[0]}: signal={row[1]}, confidence={row[2]}")
except Exception as e:
    print(f'Error: {e}')

conn.close()
print('\n✅ Check complete')
