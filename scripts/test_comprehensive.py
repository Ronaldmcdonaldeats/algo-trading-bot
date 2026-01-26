#!/usr/bin/env python3
"""Comprehensive test all 12 strategies and find consistent outperformers"""

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
    print("📥 Loading cached data...")
    for symbol in SYMBOLS:
        try:
            prices = loader.get_cached_data(symbol)
            if prices and len(prices) > 200:
                data[symbol] = prices
        except Exception as e:
            pass
    
    # Load benchmark
    try:
        spy_prices = loader.get_cached_data('^GSPC')
        if spy_prices and len(spy_prices) > 200:
            data['^GSPC'] = spy_prices
    except:
        pass
    
    print(f"✅ Loaded {len([s for s in SYMBOLS if s in data])}/{len(SYMBOLS)} stocks")
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


def test_strategy_on_all_stocks(strategy_name, data):
    """Test a strategy on all stocks"""
    strategy = StrategyFactory.create(strategy_name)
    if strategy is None:
        print(f"❌ {strategy_name}: Strategy not found")
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
        print(f"❌ {strategy_name}: No valid backtests")
        return None
    
    # Get SPY baseline
    spy_return = 10.1  # Default
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
    
    print(f"✅ {strategy_name:<30} {avg_return:>8.2f}%  (vs SPY: {spy_return:>6.2f}%, +{result['outperformance']:>6.2f}%)")
    return result


def main():
    """Main testing function"""
    print("\n" + "="*110)
    print("🚀 COMPREHENSIVE STRATEGY TESTING - Find Consistent SPY Outperformers")
    print("="*110)
    
    # Load data
    data = load_data()
    if not data or len(data) < 20:
        print("❌ Cannot load enough cached data. Run phase12_fast.py first.")
        return
    
    # Get all strategies
    all_strategies = StrategyFactory.list_strategies()
    print(f"\n📊 Testing {len(all_strategies)} strategies on {len([s for s in SYMBOLS if s in data])}/34 stocks...")
    print("-" * 110)
    
    # Test each strategy
    results = []
    for strategy_name in sorted(all_strategies):
        result = test_strategy_on_all_stocks(strategy_name, data)
        if result:
            results.append(result)
    
    # Sort by outperformance
    results_sorted = sorted(results, key=lambda x: x['outperformance'], reverse=True)
    
    # Print results
    print("\n" + "="*110)
    print("📈 ALL STRATEGIES RANKED BY OUTPERFORMANCE OVER S&P 500")
    print("="*110)
    print(f"\n{'Rank':<4} {'Strategy':<30} {'Avg Return':<12} {'vs S&P':<12} {'Stocks Win':<12} {'Sharpe':<8}")
    print("-" * 110)
    
    for i, r in enumerate(results_sorted, 1):
        print(f"{i:<4} {r['name']:<30} {r['avg_return']:>10.2f}% {r['outperformance']:>10.2f}% {r['beats_spy']:>10}/34      {r['sharpe']:>7.2f}")
    
    # Find best for consistent outperformance
    print("\n" + "="*110)
    print("🏆 STRATEGIES WITH REALISTIC CONSISTENT OUTPERFORMANCE (>5% annually)")
    print("="*110)
    
    consistent = [r for r in results_sorted if r['outperformance'] > 5 and r['outperformance'] < 20]
    
    if consistent:
        for i, r in enumerate(consistent[:5], 1):
            print(f"\n{i}. {r['name'].upper()}")
            print(f"   Average Annual Return: {r['avg_return']:.2f}%")
            print(f"   Outperformance vs S&P: +{r['outperformance']:.2f}%")
            print(f"   Stocks Beating S&P: {r['beats_spy']}/34")
            print(f"   Volatility (Std Dev): {r['std_return']:.2f}%")
            print(f"   Best Performer: {r['best'][0]} ({r['best'][1]:.2f}%)")
            print(f"   Worst Performer: {r['worst'][0]} ({r['worst'][1]:.2f}%)")
            print(f"   Risk-Adjusted (Sharpe): {r['sharpe']:.3f}")
    
    # Final recommendation
    print("\n" + "="*110)
    print("💡 RECOMMENDATION")
    print("="*110)
    
    if consistent:
        winner = consistent[0]
        print(f"\n✅ BEST CHOICE: {winner['name'].upper()}")
        print(f"   Realistic outperformance: +{winner['outperformance']:.2f}% annually")
        print(f"   Beat S&P in {winner['beats_spy']}/34 stocks ({winner['beats_spy']/34*100:.1f}%)")
        print(f"   Expected annual return: {winner['avg_return']:.2f}%")
        print(f"\n📝 To use this strategy:")
        print(f"   1. Edit strategy_config.yaml")
        print(f"   2. Change: strategy: {winner['name']}")
        print(f"   3. Run: python scripts/multi_strategy_backtest.py")
    else:
        print("\n❌ No strategies found with realistic outperformance")
        print("Use the ultra_ensemble strategy as default (16.54% annual return)")
    
    print("\n" + "="*110 + "\n")
    
    return results_sorted


if __name__ == '__main__':
    results = main()
