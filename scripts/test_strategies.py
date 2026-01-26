#!/usr/bin/env python3
"""Test all 12 strategies and find consistent outperformers"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from strategies.factory import StrategyFactory
from cached_data_loader import CachedDataLoader

SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'BERKB',
    'JNJ', 'V', 'WMT', 'JPM', 'PG', 'MA', 'HD', 'DIS',
    'BA', 'NFLX', 'ADBE', 'CRM', 'INTC', 'AMD', 'CSCO', 'PYPL',
    'CMCSA', 'AVGO', 'TXN', 'VRTX', 'ABNB', 'QCOM', 'LRCX',
    'CHKP', 'MU'
]


def load_data():
    """Load cached stock data using CachedDataLoader"""
    loader = CachedDataLoader()
    
    data = {}
    print("\n[*] Loading cached data...")
    count = 0
    for symbol in SYMBOLS:
        try:
            prices = loader.get_cached_data(symbol)
            if prices and len(prices) > 200:
                data[symbol] = prices
                count += 1
        except:
            pass
    
    # Load benchmark
    try:
        spy_prices = loader.get_cached_data('^GSPC')
        if spy_prices and len(spy_prices) > 200:
            data['^GSPC'] = spy_prices
    except:
        pass
    
    print("[OK] Loaded {} stocks\n".format(count))
    return data


def backtest_strategy(strategy, prices):
    """Backtest a strategy on a single stock"""
    if len(prices) < 200:
        return None
    
    equity = 100.0
    position = 0
    entry_price = 0
    trades = 0
    wins = 0
    
    for i in range(200, len(prices)):
        price_window = prices[:i]
        price_now = prices[i]
        
        # Get strategy signal
        features = strategy.calculate_features(price_window)
        if not features:
            continue
        
        signal, size = strategy.generate_signal(features, position)
        
        # Process signal
        if signal == 1 and position == 0:  # BUY
            position = 1
            entry_price = price_now
            trades += 1
        elif signal == -1 and position == 1:  # SELL
            return_pct = (price_now - entry_price) / entry_price
            if return_pct > 0:
                wins += 1
            equity *= (1 + return_pct)
            position = 0
            trades += 1
    
    # Close any open position
    if position == 1 and len(prices) > 0:
        final_return = (prices[-1] - entry_price) / entry_price
        if final_return > 0:
            wins += 1
        equity *= (1 + final_return)
    
    annual_return = ((equity / 100) ** (252 / len(prices)) - 1) * 100 if len(prices) > 0 else 0
    
    return annual_return


def test_strategy(strategy_name, data):
    """Test a strategy on all stocks"""
    strategy = StrategyFactory.create(strategy_name)
    if strategy is None:
        return None
    
    returns_by_stock = {}
    
    for symbol in SYMBOLS:
        if symbol not in data:
            continue
        
        prices = np.array(data[symbol])
        result = backtest_strategy(strategy, prices)
        
        if result is not None:
            returns_by_stock[symbol] = result
    
    if not returns_by_stock:
        return None
    
    # Get SPY baseline
    spy_return = 10.1
    if '^GSPC' in data:
        prices = np.array(data['^GSPC'])
        spy_result = backtest_strategy(strategy, prices)
        if spy_result:
            spy_return = spy_result
    
    # Calculate statistics
    returns = list(returns_by_stock.values())
    avg_return = np.mean(returns)
    std_return = np.std(returns)
    median_return = np.median(returns)
    beats_spy = sum(1 for r in returns if r > spy_return)
    
    result = {
        'name': strategy_name,
        'avg_return': avg_return,
        'median_return': median_return,
        'std_return': std_return,
        'sharpe': (avg_return / std_return) if std_return > 0 else 0,
        'outperformance': avg_return - spy_return,
        'beats_spy': beats_spy,
        'total_stocks': len(returns),
        'spy_return': spy_return,
        'best': max(returns_by_stock.items(), key=lambda x: x[1]),
        'worst': min(returns_by_stock.items(), key=lambda x: x[1]),
    }
    
    return result


def main():
    """Main testing function"""
    print("\n" + "="*120)
    print(" COMPREHENSIVE STRATEGY TESTING - Find Consistent SPY Outperformers")
    print("="*120)
    
    # Load data
    data = load_data()
    if not data or len(data) < 20:
        print("ERROR: Cannot load enough cached data")
        return
    
    # Get all strategies
    all_strategies = StrategyFactory.list_strategies()
    num_stocks = len([s for s in SYMBOLS if s in data])
    print("\n[*] Testing {} strategies on {}/34 stocks...\n".format(len(all_strategies), num_stocks))
    
    # Test each strategy
    results = []
    for strategy_name in sorted(all_strategies):
        print("[TESTING] {}...".format(strategy_name), end=" ", flush=True)
        result = test_strategy(strategy_name, data)
        if result:
            results.append(result)
            print("[OK] Avg: {:.2f}%  vs SPY: {:.2f}%  +{:.2f}%".format(
                result['avg_return'], result['spy_return'], result['outperformance']))
        else:
            print("[FAILED]")
    
    # Sort by outperformance
    results_sorted = sorted(results, key=lambda x: x['outperformance'], reverse=True)
    
    # Print results
    print("\n" + "="*120)
    print(" ALL STRATEGIES RANKED BY OUTPERFORMANCE")
    print("="*120)
    print("\n{:<4} {:<32} {:<12} {:<12} {:<12} {:<8}".format("Rank", "Strategy", "Avg Return", "vs S&P", "Win Rate", "Sharpe"))
    print("-"*120)
    
    for i, r in enumerate(results_sorted, 1):
        print("{:<4} {:<32} {>10.2f}% {>10.2f}% {>10}/34      {>7.2f}".format(
            i, r['name'], r['avg_return'], r['outperformance'], r['beats_spy'], r['sharpe']))
    
    # Find best for consistent outperformance
    print("\n" + "="*120)
    print(" TOP STRATEGIES (>5% outperformance)")
    print("="*120)
    
    consistent = [r for r in results_sorted if r['outperformance'] > 5 and r['outperformance'] < 20]
    
    if consistent:
        for i, r in enumerate(consistent[:5], 1):
            print("\n[{}] {}".format(i, r['name'].upper()))
            print("    Annual Return:       {:.2f}%".format(r['avg_return']))
            print("    Outperformance:      +{:.2f}%".format(r['outperformance']))
            print("    Stocks Beat SPY:     {}/34 ({:.1f}%)".format(r['beats_spy'], r['beats_spy']/34*100))
            print("    Volatility:          {:.2f}%".format(r['std_return']))
            print("    Best:                {} ({:.2f}%)".format(r['best'][0], r['best'][1]))
            print("    Worst:               {} ({:.2f}%)".format(r['worst'][0], r['worst'][1]))
            print("    Sharpe Ratio:        {:.3f}".format(r['sharpe']))
    
    # Final recommendation
    print("\n" + "="*120)
    print(" RECOMMENDATION")
    print("="*120)
    
    if consistent:
        winner = consistent[0]
        print("\n[BEST] {}".format(winner['name'].upper()))
        print("    Outperformance: +{:.2f}% annually".format(winner['outperformance']))
        print("    Beat SPY:       {}/34 stocks ({:.1f}%)".format(winner['beats_spy'], winner['beats_spy']/34*100))
        print("    Expected Return: {:.2f}%".format(winner['avg_return']))
        print("\n[USAGE] To deploy:")
        print("    1. Edit strategy_config.yaml")
        print("    2. Set strategy: {}".format(winner['name']))
        print("    3. Run python scripts/multi_strategy_backtest.py")
    else:
        print("\n[INFO] Use ultra_ensemble strategy (16.54% annual)")
    
    print("\n" + "="*120 + "\n")
    
    return results_sorted


if __name__ == '__main__':
    results = main()
