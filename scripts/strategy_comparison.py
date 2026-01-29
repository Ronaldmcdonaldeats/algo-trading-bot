"""
Strategy Comparison - Gen 364 vs Alternative Strategies
Compare evolved strategy against baselines: buy-hold, momentum, mean reversion, RSI-only
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

def backtest_strategy(strategy_name, entry_logic, exit_logic):
    """Generic backtest framework"""
    data = get_all_data()
    
    initial_capital = 100000
    cash = initial_capital
    positions = {}  # symbol -> {shares, entry_price, entry_date}
    trades = []
    equity_curve = [initial_capital]
    
    symbols = list(data.keys())  # Use all available symbols
    print(f"  Symbols loaded: {len(symbols)}")
    
    # Get date range
    all_dates = set()
    for symbol in symbols:
        for row in data[symbol]:
            all_dates.add(row[0])
    
    sorted_dates = sorted(list(all_dates))
    
    # Process each trading day
    for date in sorted_dates:
        day_equity = cash
        
        # Check exits
        symbols_to_remove = []
        for symbol in positions:
            entry_price = positions[symbol]['entry_price']
            
            # Get current price
            symbol_prices = {row[0]: row[4] for row in data[symbol]}
            current_price = symbol_prices.get(date, entry_price)
            
            # Exit logic
            should_exit = exit_logic(symbol, current_price, entry_price, data[symbol], date)
            
            if should_exit:
                profit = positions[symbol]['shares'] * (current_price - entry_price)
                cash += positions[symbol]['shares'] * current_price
                trades.append({
                    'symbol': symbol,
                    'return': (current_price - entry_price) / entry_price,
                    'profit': profit
                })
                symbols_to_remove.append(symbol)
        
        for symbol in symbols_to_remove:
            del positions[symbol]
        
        # Check entries
        if cash > 0 and len(positions) < 20:
            for symbol in symbols:
                if symbol not in positions:
                    symbol_prices = {row[0]: row[4] for row in data[symbol]}
                    current_price = symbol_prices.get(date)
                    
                    if current_price:
                        # Entry logic
                        should_enter = entry_logic(symbol, current_price, data[symbol], date)
                        
                        if should_enter:
                            shares = int((cash * 0.05) / current_price)
                            if shares > 0:
                                cost = shares * current_price
                                cash -= cost
                                positions[symbol] = {
                                    'shares': shares,
                                    'entry_price': current_price,
                                    'entry_date': date
                                }
        
        # Calculate daily equity
        for symbol in positions:
            symbol_prices = {row[0]: row[4] for row in data[symbol]}
            current_price = symbol_prices.get(date, positions[symbol]['entry_price'])
            day_equity += positions[symbol]['shares'] * current_price
        
        equity_curve.append(day_equity)
    
    # Results
    final_equity = equity_curve[-1] if equity_curve else initial_capital
    total_return = (final_equity - initial_capital) / initial_capital * 100
    
    wins = sum(1 for t in trades if t['return'] > 0)
    losses = sum(1 for t in trades if t['return'] <= 0)
    
    # Sharpe ratio
    returns = np.diff(equity_curve) / equity_curve[:-1]
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    
    # Max drawdown
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (np.array(equity_curve) - peak) / peak
    max_drawdown = np.min(drawdown) * 100
    
    return {
        'strategy': strategy_name,
        'final_equity': final_equity,
        'total_return': total_return,
        'profit': final_equity - initial_capital,
        'trades': len(trades),
        'wins': wins,
        'losses': losses,
        'win_rate': wins / len(trades) * 100 if len(trades) > 0 else 0,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_drawdown
    }

def gen364_entry(symbol, price, symbol_data, date):
    """Gen 364 strategy entry logic"""
    # Find current row
    for i, row in enumerate(symbol_data):
        if row[0] == date and i >= 10:
            prices = [x[4] for x in symbol_data[:i+1]]
            rsi = calculate_rsi(prices)
            momentum = calculate_momentum(prices)
            
            # Gen 364 logic (simplified)
            momentum_signal = max(0, min(1, (momentum + 50) / 100))
            rsi_signal = 1 - (rsi / 100)
            
            ml_score = 0.2172 * momentum_signal + 0.1000 * rsi_signal
            
            return ml_score >= 0.7756
    return False

def gen364_exit(symbol, price, entry_price, symbol_data, date):
    """Gen 364 strategy exit logic"""
    ret = (price - entry_price) / entry_price
    return ret >= 0.1287 or ret <= -0.0927

def buyandholdall_entry(symbol, price, symbol_data, date):
    """Buy and hold - buy once"""
    # Check if this is first appearance
    for row in symbol_data:
        if row[0] == date:
            return True
    return False

def buyandholdall_exit(symbol, price, entry_price, symbol_data, date):
    """Never exit"""
    return False

def momentum_entry(symbol, price, symbol_data, date):
    """Momentum strategy - enter if strong uptrend"""
    for i, row in enumerate(symbol_data):
        if row[0] == date and i >= 20:
            prices = [x[4] for x in symbol_data[:i+1]]
            momentum = calculate_momentum(prices)
            return momentum > 5  # 5% momentum threshold
    return False

def momentum_exit(symbol, price, entry_price, symbol_data, date):
    """Exit on 10% profit or 5% loss"""
    ret = (price - entry_price) / entry_price
    return ret >= 0.10 or ret <= -0.05

def meanreversion_entry(symbol, price, symbol_data, date):
    """Mean reversion - enter on oversold"""
    for i, row in enumerate(symbol_data):
        if row[0] == date and i >= 14:
            prices = [x[4] for x in symbol_data[:i+1]]
            rsi = calculate_rsi(prices)
            return rsi < 30  # Oversold
    return False

def meanreversion_exit(symbol, price, entry_price, symbol_data, date):
    """Exit on 8% profit or 3% loss"""
    ret = (price - entry_price) / entry_price
    return ret >= 0.08 or ret <= -0.03

def rsionly_entry(symbol, price, symbol_data, date):
    """RSI-only strategy - buy oversold"""
    for i, row in enumerate(symbol_data):
        if row[0] == date and i >= 14:
            prices = [x[4] for x in symbol_data[:i+1]]
            rsi = calculate_rsi(prices)
            return rsi < 35  # Oversold threshold
    return False

def rsionly_exit(symbol, price, entry_price, symbol_data, date):
    """Exit on 5% profit or 4% loss"""
    ret = (price - entry_price) / entry_price
    return ret >= 0.05 or ret <= -0.04

def main():
    print("\n" + "="*90)
    print("STRATEGY COMPARISON - GEN 364 vs ALTERNATIVES")
    print("="*90)
    
    results = []
    
    # Test each strategy
    print("\nRunning Gen 364 Strategy...")
    results.append(backtest_strategy("Gen 364 (Evolved)", gen364_entry, gen364_exit))
    
    print("Running Buy & Hold All...")
    results.append(backtest_strategy("Buy & Hold All", buyandholdall_entry, buyandholdall_exit))
    
    print("Running Momentum Strategy...")
    results.append(backtest_strategy("Momentum (>5%)", momentum_entry, momentum_exit))
    
    print("Running Mean Reversion Strategy...")
    results.append(backtest_strategy("Mean Reversion (RSI<30)", meanreversion_entry, meanreversion_exit))
    
    print("Running RSI-Only Strategy...")
    results.append(backtest_strategy("RSI-Only (RSI<35)", rsionly_entry, rsionly_exit))
    
    # Display results
    print(f"\n{'='*90}")
    print("RESULTS SUMMARY")
    print('='*90)
    print(f"\n{'Strategy':<30} {'Return':<12} {'Sharpe':<10} {'Max DD':<12} {'Trades':<8} {'Win Rate'}")
    print('-'*90)
    
    for r in sorted(results, key=lambda x: x['total_return'], reverse=True):
        print(f"{r['strategy']:<30} {r['total_return']:>7.2f}%  {r['sharpe_ratio']:>8.2f}  {r['max_drawdown']:>10.2f}% {r['trades']:>7} {r['win_rate']:>7.1f}%")
    
    print('='*90)
    
    # Key metrics
    gen364 = next(r for r in results if r['strategy'] == 'Gen 364 (Evolved)')
    buyhold = next(r for r in results if r['strategy'] == 'Buy & Hold All')
    best = max(results, key=lambda x: x['total_return'])
    worst = min(results, key=lambda x: x['total_return'])
    
    print(f"\nBest Strategy:   {best['strategy']:<25} +{best['total_return']:>6.2f}%")
    print(f"Worst Strategy:  {worst['strategy']:<25} {worst['total_return']:>6.2f}%")
    print(f"Gen 364 vs B&H:  {gen364['total_return'] - buyhold['total_return']:>+6.2f}pp advantage")
    print(f"Avg Sharpe Ratio: {np.mean([r['sharpe_ratio'] for r in results]):>6.2f}")
    
    print('='*90)
    print("\nConclusion:")
    print(f"  Gen 364 achieved {gen364['total_return']:.2f}% return with Sharpe {gen364['sharpe_ratio']:.2f}")
    print(f"  {best['strategy']} is best at {best['total_return']:.2f}%")
    print(f"  Gen 364 outperforms buy-hold by {gen364['total_return'] - buyhold['total_return']:.2f}pp")
    
    # Save results
    with open('scripts/strategy_comparison_results.json', 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    main()
