"""
Position Sizing Validation - Verify Gen 364 Position Risk Management
Check: 5% per trade rule, 17.74% max position concentration, portfolio risk exposure
"""
import json
import sqlite3
import numpy as np

def get_all_data():
    """Load all market data from database"""
    conn = sqlite3.connect('data/real_market_data.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT symbol FROM daily_prices ORDER BY symbol")
    symbols = [row[0] for row in cursor.fetchall()]
    
    data = {}
    for symbol in symbols:
        cursor.execute("""
            SELECT date, open, high, low, close, volume 
            FROM daily_prices 
            WHERE symbol = ? 
            ORDER BY date
        """, (symbol,))
        rows = cursor.fetchall()
        if rows:
            data[symbol] = rows
    
    conn.close()
    return data

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    if len(prices) < period:
        return 50
    
    deltas = np.diff(prices[-period-1:])
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    
    rs = up / down if down else 0
    rsi = 100 - 100 / (1 + rs)
    return rsi

def calculate_momentum(prices, period=10):
    """Calculate momentum indicator"""
    if len(prices) < period:
        return 0
    return ((prices[-1] - prices[-period-1]) / prices[-period-1]) * 100

def validate_position_sizing():
    """Validate position sizing during backtest"""
    
    data = get_all_data()
    
    initial_capital = 100000
    cash = initial_capital
    positions = {}  # symbol -> {shares, entry_price, entry_date}
    
    symbols = list(data.keys())[:140]
    
    # Get date range
    all_dates = set()
    for symbol in symbols:
        for row in data[symbol]:
            all_dates.add(row[0])
    
    sorted_dates = sorted(list(all_dates))
    
    # Tracking metrics
    daily_logs = []
    violations = {
        'position_size_over_5pct': 0,
        'concentration_over_17pct': 0,
        'portfolio_risk_over_limit': 0
    }
    
    max_positions = 0
    max_concentration = 0
    max_portfolio_risk = 0
    
    # Process each trading day
    for date_idx, date in enumerate(sorted_dates):
        day_equity = cash
        
        # Calculate day equity and position sizes
        for symbol in positions:
            entry_price = positions[symbol]['entry_price']
            symbol_prices = {row[0]: row[4] for row in data[symbol]}
            current_price = symbol_prices.get(date, entry_price)
            day_equity += positions[symbol]['shares'] * current_price
        
        # Check exits first
        symbols_to_remove = []
        for symbol in positions:
            entry_price = positions[symbol]['entry_price']
            symbol_prices = {row[0]: row[4] for row in data[symbol]}
            current_price = symbol_prices.get(date, entry_price)
            
            ret = (current_price - entry_price) / entry_price
            
            # Exit on profit/loss targets
            if ret >= 0.1287 or ret <= -0.0927:
                position_value = positions[symbol]['shares'] * current_price
                cash += position_value
                symbols_to_remove.append(symbol)
        
        for symbol in symbols_to_remove:
            del positions[symbol]
        
        # Recalculate day equity
        day_equity = cash
        for symbol in positions:
            entry_price = positions[symbol]['entry_price']
            symbol_prices = {row[0]: row[4] for row in data[symbol]}
            current_price = symbol_prices.get(date, entry_price)
            day_equity += positions[symbol]['shares'] * current_price
        
        # Check entries
        num_positions = len(positions)
        max_positions = max(max_positions, num_positions)
        
        if num_positions < 20 and cash > 0:  # max 20 positions
            for symbol in symbols:
                if symbol not in positions and cash > 0:
                    symbol_data = data[symbol]
                    
                    # Find data for this date
                    for i, row in enumerate(symbol_data):
                        if row[0] == date and i >= 10:
                            prices = [x[4] for x in symbol_data[:i+1]]
                            rsi = calculate_rsi(prices)
                            momentum = calculate_momentum(prices)
                            close_price = row[4]
                            
                            # Entry logic
                            momentum_signal = max(0, min(1, (momentum + 50) / 100))
                            rsi_signal = 1 - (rsi / 100)
                            ml_score = 0.2172 * momentum_signal + 0.1000 * rsi_signal
                            
                            if ml_score >= 0.7756:
                                # Position size = 5% of portfolio
                                position_amount = day_equity * 0.05
                                shares = int(position_amount / close_price)
                                
                                if shares > 0:
                                    cost = shares * close_price
                                    
                                    # Validate position sizing
                                    position_pct = (cost / day_equity) * 100
                                    
                                    # Flag if position > 5%
                                    if position_pct > 5.0:
                                        violations['position_size_over_5pct'] += 1
                                        print(f"WARNING: {symbol} position {position_pct:.2f}% > 5% on {date}")
                                    
                                    if cost <= cash:
                                        cash -= cost
                                        positions[symbol] = {
                                            'shares': shares,
                                            'entry_price': close_price,
                                            'entry_date': date,
                                            'position_pct': position_pct
                                        }
        
        # Calculate daily concentration and risk
        day_equity = cash
        total_position_value = 0
        max_single_position = 0
        
        for symbol in positions:
            entry_price = positions[symbol]['entry_price']
            symbol_prices = {row[0]: row[4] for row in data[symbol]}
            current_price = symbol_prices.get(date, entry_price)
            position_value = positions[symbol]['shares'] * current_price
            total_position_value += position_value
            day_equity += position_value
            max_single_position = max(max_single_position, position_value)
        
        # Check concentration limit (17.74% max per position)
        if day_equity > 0:
            max_position_pct = (max_single_position / day_equity) * 100
            max_concentration = max(max_concentration, max_position_pct)
            
            if max_position_pct > 17.74:
                violations['concentration_over_17pct'] += 1
        
        # Check portfolio risk (max loss across all positions)
        portfolio_at_risk = 0
        for symbol in positions:
            position_value = positions[symbol]['shares'] * positions[symbol]['entry_price']
            max_loss_per_position = position_value * 0.0927  # Stop loss
            portfolio_at_risk += max_loss_per_position
        
        portfolio_risk_pct = (portfolio_at_risk / day_equity) * 100 if day_equity > 0 else 0
        max_portfolio_risk = max(max_portfolio_risk, portfolio_risk_pct)
        
        if portfolio_risk_pct > 10:  # Flag if >10% total portfolio risk
            violations['portfolio_risk_over_limit'] += 1
        
        # Daily log
        daily_logs.append({
            'date': date,
            'portfolio_value': day_equity,
            'num_positions': len(positions),
            'max_position_pct': max_position_pct if day_equity > 0 else 0,
            'portfolio_risk_pct': portfolio_risk_pct,
            'cash_available': cash
        })
    
    return {
        'violations': violations,
        'max_positions_held': max_positions,
        'max_position_concentration': max_concentration,
        'max_portfolio_risk': max_portfolio_risk,
        'daily_logs': daily_logs[:50]  # First 50 days
    }

def main():
    print("\n" + "="*90)
    print("POSITION SIZING VALIDATION - GEN 364 STRATEGY")
    print("="*90)
    
    results = validate_position_sizing()
    
    print("\nVALIDATION RULES:")
    print("  ✓ Position Size: Max 5% of portfolio per trade")
    print("  ✓ Max Concentration: No single position > 17.74% of portfolio")
    print("  ✓ Portfolio Risk: Total max loss <= 10% of portfolio")
    print("  ✓ Max Positions: <= 20 concurrent positions")
    
    print(f"\n{'='*90}")
    print("RESULTS")
    print('='*90)
    
    print(f"\nMax Positions Held Concurrently:  {results['max_positions_held']}")
    print(f"Max Position Concentration:      {results['max_position_concentration']:.2f}%")
    print(f"Max Portfolio Risk:              {results['max_portfolio_risk']:.2f}%")
    
    print(f"\n{'='*90}")
    print("VIOLATION SUMMARY")
    print('='*90)
    
    violations = results['violations']
    total_violations = sum(violations.values())
    
    print(f"\nPosition Size Violations (>5%):    {violations['position_size_over_5pct']}")
    print(f"Concentration Violations (>17.74%): {violations['concentration_over_17pct']}")
    print(f"Portfolio Risk Violations (>10%):  {violations['portfolio_risk_over_limit']}")
    print(f"\nTotal Violations:                  {total_violations}")
    
    print(f"\n{'='*90}")
    print("SAMPLE DAILY POSITIONS (First 20 Days)")
    print('='*90)
    
    print(f"\n{'Date':<15} {'Portfolio':<15} {'Positions':<12} {'Max Pos %':<12} {'Risk %':<10}")
    print('-'*90)
    
    for log in results['daily_logs'][:20]:
        print(f"{log['date']:<15} ${log['portfolio_value']:>12,.0f} {log['num_positions']:>10} {log['max_position_pct']:>10.2f}% {log['portfolio_risk_pct']:>8.2f}%")
    
    print('='*90)
    print("\nCONCLUSION:")
    
    if total_violations == 0:
        print("  ✓ PASS: Position sizing rules strictly enforced")
        print(f"  ✓ Max concentration {results['max_position_concentration']:.2f}% is within 17.74% limit")
        print(f"  ✓ Portfolio risk never exceeded 10% total exposure")
    else:
        print(f"  ✗ FAIL: {total_violations} position sizing violations detected")
    
    print('='*90)
    
    # Save results
    with open('scripts/position_sizing_validation.json', 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    main()
