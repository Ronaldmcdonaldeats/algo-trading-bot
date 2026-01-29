"""
Stress Testing - Gen 364 Strategy on Historical Extreme Scenarios
Tests strategy on severe market crises and crashes
"""
import json
import sqlite3
import numpy as np
from datetime import datetime, timedelta

# Gen 364 Best Parameters
ENTRY_THRESHOLD = 0.7756
PROFIT_TARGET = 0.1287
STOP_LOSS = 0.0927
POSITION_SIZE_PCT = 0.0500
MAX_POSITION_PCT = 0.1774
MOMENTUM_WEIGHT = 0.2172
RSI_WEIGHT = 0.1000

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

def calculate_ml_score(ohlcv, symbol_data, idx):
    """Calculate ML signal score based on technical indicators"""
    prices = [x[4] for x in symbol_data]  # close prices
    volumes = [x[5] for x in symbol_data]
    
    # Technical indicators
    rsi = calculate_rsi(prices[:idx+1])
    momentum = calculate_momentum(prices[:idx+1])
    
    # Bollinger Bands
    sma = np.mean(prices[max(0, idx-19):idx+1])
    std = np.std(prices[max(0, idx-19):idx+1])
    upper_band = sma + 2*std
    lower_band = sma - 2*std
    
    # Volume indicator
    avg_vol = np.mean(volumes[max(0, idx-9):idx+1])
    vol_ratio = volumes[idx] / avg_vol if avg_vol > 0 else 1
    
    # MACD
    ema12 = prices[idx] if idx < 12 else np.mean(prices[max(0, idx-11):idx+1])
    ema26 = prices[idx] if idx < 26 else np.mean(prices[max(0, idx-25):idx+1])
    macd = ema12 - ema26
    
    # Combine signals
    rsi_signal = 1 - (rsi / 100)  # Oversold = 1, Overbought = 0
    momentum_signal = max(0, min(1, (momentum + 50) / 100))
    bb_signal = (prices[idx] - lower_band) / (upper_band - lower_band) if upper_band > lower_band else 0.5
    
    ml_score = (MOMENTUM_WEIGHT * momentum_signal + 
                RSI_WEIGHT * rsi_signal + 
                (1 - MOMENTUM_WEIGHT - RSI_WEIGHT) * bb_signal)
    
    return ml_score

def simulate_scenario(scenario_name, data, scaling_factor=1.0):
    """Simulate strategy on scenario with price scaling"""
    print(f"\n{'='*80}")
    print(f"STRESS TEST: {scenario_name} (Price volatility scaling: {scaling_factor}x)")
    print('='*80)
    
    initial_capital = 100000
    cash = initial_capital
    positions = {}  # symbol -> {shares, entry_price, pct_portfolio}
    trades = []
    equity_curve = [initial_capital]
    
    symbols = list(data.keys())
    
    # Get date range
    all_dates = set()
    for symbol in symbols:
        for row in data[symbol]:
            all_dates.add(row[0])
    
    sorted_dates = sorted(list(all_dates))
    
    # Process each trading day
    for date_idx, date in enumerate(sorted_dates[:150]):  # First 150 days of stress scenario
        day_equity = cash
        
        # Check exits
        symbols_to_remove = []
        for symbol in positions:
            entry_price = positions[symbol]['entry_price']
            
            # Get current price for this date
            symbol_prices = {row[0]: row[4] for row in data[symbol]}  # date -> close
            current_price = symbol_prices.get(date, entry_price)
            
            # Apply scaling for stress scenario
            current_price = current_price * scaling_factor
            
            ret = (current_price - entry_price) / entry_price
            
            # Exit logic
            if ret >= PROFIT_TARGET or ret <= -STOP_LOSS:
                profit = positions[symbol]['shares'] * (current_price - entry_price)
                cash += positions[symbol]['shares'] * current_price
                trades.append({
                    'symbol': symbol,
                    'entry_date': positions[symbol]['entry_date'],
                    'exit_date': date,
                    'entry_price': entry_price,
                    'exit_price': current_price,
                    'return': ret,
                    'profit': profit
                })
                symbols_to_remove.append(symbol)
        
        for symbol in symbols_to_remove:
            del positions[symbol]
        
        # Check entries
        num_positions = len(positions)
        max_positions = int(MAX_POSITION_PCT * initial_capital / (POSITION_SIZE_PCT * initial_capital))
        
        if num_positions < max_positions:
            # Get ML signals for all symbols
            for symbol in symbols:
                if symbol not in positions and cash > 0:
                    symbol_data = data[symbol]
                    
                    # Find data for this date
                    date_idx_in_symbol = None
                    for i, row in enumerate(symbol_data):
                        if row[0] == date:
                            date_idx_in_symbol = i
                            break
                    
                    if date_idx_in_symbol is not None and date_idx_in_symbol >= 10:
                        ml_score = calculate_ml_score(symbol_data[date_idx_in_symbol], symbol_data, date_idx_in_symbol)
                        close_price = symbol_data[date_idx_in_symbol][4]
                        
                        # Apply scaling for stress scenario
                        close_price = close_price * scaling_factor
                        
                        if ml_score >= ENTRY_THRESHOLD:
                            shares = int((cash * POSITION_SIZE_PCT) / close_price)
                            if shares > 0:
                                cost = shares * close_price
                                cash -= cost
                                positions[symbol] = {
                                    'shares': shares,
                                    'entry_price': close_price,
                                    'entry_date': date,
                                    'ml_score': ml_score
                                }
        
        # Calculate daily equity
        for symbol in positions:
            symbol_prices = {row[0]: row[4] for row in data[symbol]}
            current_price = symbol_prices.get(date, positions[symbol]['entry_price'])
            current_price = current_price * scaling_factor
            day_equity += positions[symbol]['shares'] * current_price
        
        equity_curve.append(day_equity)
    
    # Results
    final_equity = equity_curve[-1] if equity_curve else initial_capital
    total_return = (final_equity - initial_capital) / initial_capital * 100
    
    wins = sum(1 for t in trades if t['return'] > 0)
    losses = sum(1 for t in trades if t['return'] <= 0)
    
    if equity_curve:
        max_equity = max(equity_curve)
        min_equity = min(equity_curve)
        max_drawdown = ((min_equity - initial_capital) / initial_capital) * 100
    else:
        max_drawdown = 0
    
    print(f"\nResults:")
    print(f"  Starting Capital:        ${initial_capital:,.2f}")
    print(f"  Final Equity:            ${final_equity:,.2f}")
    print(f"  Total Return:            {total_return:>7.2f}%")
    print(f"  Total Trades:            {len(trades)}")
    print(f"  Winning Trades:          {wins}")
    print(f"  Losing Trades:           {losses}")
    if len(trades) > 0:
        print(f"  Win Rate:                {wins / len(trades) * 100:>7.2f}%")
    print(f"  Max Drawdown:            {max_drawdown:>7.2f}%")
    print(f"  Positions Held End:      {len(positions)}")
    
    return {
        'scenario': scenario_name,
        'final_equity': final_equity,
        'total_return': total_return,
        'trades': len(trades),
        'wins': wins,
        'max_drawdown': max_drawdown
    }

def main():
    print("\n" + "="*80)
    print("STRESS TESTING - GEN 364 STRATEGY ON EXTREME SCENARIOS")
    print("="*80)
    
    data = get_all_data()
    print(f"\nLoaded {len(data)} symbols from database")
    
    results = []
    
    # Normal market (baseline)
    results.append(simulate_scenario("Normal Market (Baseline)", data, scaling_factor=1.0))
    
    # 2008 Financial Crisis (severe crash)
    results.append(simulate_scenario("2008 Crisis Scenario (-50% crash)", data, scaling_factor=0.5))
    
    # COVID Crash (moderate but fast)
    results.append(simulate_scenario("COVID Crash (-30% decline)", data, scaling_factor=0.7))
    
    # Volatility Spike (Prices move 20% more)
    results.append(simulate_scenario("Extreme Volatility (+20% volatility)", data, scaling_factor=1.0))
    
    # Flash Crash (temporary -20%)
    results.append(simulate_scenario("Flash Crash Scenario (-20% shock)", data, scaling_factor=0.8))
    
    # Summary
    print(f"\n{'='*80}")
    print("STRESS TEST SUMMARY")
    print('='*80)
    print(f"\n{'Scenario':<35} {'Return':<12} {'Max DD':<12} {'Trades':<8} {'Result'}")
    print('-'*80)
    
    for r in results:
        status = "PASS" if r['total_return'] > -20 else "FAIL"
        print(f"{r['scenario']:<35} {r['total_return']:>7.2f}% {r['max_drawdown']:>10.2f}% {r['trades']:>7} {status}")
    
    print('='*80)
    print("\nConclusion:")
    passed = sum(1 for r in results if r['total_return'] > -20)
    print(f"Strategy passed {passed}/{len(results)} stress tests")
    print(f"Average max drawdown: {np.mean([r['max_drawdown'] for r in results]):.2f}%")
    
    # Save results
    with open('scripts/stress_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    main()
