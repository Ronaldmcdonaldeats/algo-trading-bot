#!/usr/bin/env python3
"""Comprehensive test all 12 strategies and find consistent outperformers"""

import pickle
import json
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from strategies.factory import StrategyFactory

# Load cached data
CACHE_FILE = Path(__file__).parent / 'cached_stock_data.pkl'

SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'BERKB',
    'JNJ', 'V', 'WMT', 'JPM', 'PG', 'MA', 'HD', 'DIS',
    'BA', 'NFLX', 'ADBE', 'CRM', 'INTC', 'AMD', 'CSCO', 'PYPL',
    'CMCSA', 'AVGO', 'TXN', 'VRTX', 'ABNB', 'QCOM', 'LRCX',
    'CHKP', 'MU'
]


def load_data():
    """Load cached stock data"""
    if not CACHE_FILE.exists():
        print(f"❌ Cache file not found: {CACHE_FILE}")
        return None
    
    with open(CACHE_FILE, 'rb') as f:
        data = pickle.load(f)
        print(f"✅ Loaded data for {len(data)} assets")
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
    trade_returns = []
    
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
            trade_returns.append(return_pct)
            if return_pct > 0:
                wins += 1
            equity *= (1 + return_pct)
            position = 0
            trades += 1
    
    # Close any open position
    if position == 1 and len(prices) > 0:
        final_return = (prices[-1] - entry_price) / entry_price
        trade_returns.append(final_return)
        if final_return > 0:
            wins += 1
        equity *= (1 + final_return)
    
    annual_return = ((equity / 100) ** (252 / len(prices)) - 1) * 100 if len(prices) > 0 else 0
    win_rate = (wins / trades * 100) if trades > 0 else 0
    
    return {
        'equity': equity,
        'annual_return': annual_return,
        'trades': trades,
        'wins': wins,
        'win_rate': win_rate,
        'total_return': (equity - 100) / 100 * 100
    }


def test_strategy_on_all_stocks(strategy_name, data):
    """Test a strategy on all 34 stocks"""
    print(f"\n🔬 Testing: {strategy_name}...", end=" ", flush=True)
    
    strategy = StrategyFactory.create(strategy_name)
    if strategy is None:
        print(f"❌ NOT FOUND")
        return None
    
    returns_by_stock = {}
    win_counts = []
    trade_counts = []
    
    for symbol in SYMBOLS:
        if symbol not in data:
            continue
        
        prices = np.array(data[symbol])
        result = backtest_strategy(strategy, prices)
        
        if result:
            returns_by_stock[symbol] = result['annual_return']
            win_counts.append(result['wins'])
            trade_counts.append(result['trades'])
    
    if not returns_by_stock:
        print("❌ NO DATA")
        return None
    
    # Get SPY baseline
    if '^GSPC' in data:
        spy_prices = np.array(data['^GSPC'])
        spy_result = backtest_strategy(strategy, spy_prices)
        spy_return = spy_result['annual_return'] if spy_result else 0
    else:
        spy_return = 10.1  # Default S&P return
    
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
        'win_rate': (np.sum(win_counts) / np.sum(trade_counts) * 100) if np.sum(trade_counts) > 0 else 0,
        'beats_spy': beats_spy,
        'total_stocks': len(returns),
        'spy_return': spy_return,
        'consistency': len([r for r in returns if abs(r - avg_return) < std_return]) / len(returns) * 100,
        'best': max(returns_by_stock.items(), key=lambda x: x[1]),
        'worst': min(returns_by_stock.items(), key=lambda x: x[1]),
    }
    
    print(f"✅ {avg_return:.2f}% (vs SPY: {spy_return:.2f}%)")
    return result


def main():
    """Main testing function"""
    print("\n" + "="*100)
    print("🚀 COMPREHENSIVE STRATEGY TESTING - Find Consistent SPY Outperformers")
    print("="*100)
    
    # Load data
    data = load_data()
    if data is None:
        print("❌ Cannot load cached data. Run phase12_fast.py first to cache data.")
        return
    
    # Get all strategies
    all_strategies = StrategyFactory.list_strategies()
    print(f"\n📊 Testing {len(all_strategies)} strategies:")
    for s in sorted(all_strategies):
        print(f"   • {s}")
    
    # Test each strategy
    results = []
    for strategy_name in sorted(all_strategies):
        result = test_strategy_on_all_stocks(strategy_name, data)
        if result:
            results.append(result)
    
    # Sort by outperformance
    results_sorted = sorted(results, key=lambda x: x['outperformance'], reverse=True)
    
    # Print results
    print("\n" + "="*100)
    print("📈 ALL STRATEGIES RANKED BY OUTPERFORMANCE OVER S&P 500")
    print("="*100)
    print(f"\n{'Rank':<4} {'Strategy':<30} {'Avg Return':<12} {'vs S&P':<12} {'Stocks Win':<12} {'Consistency':<12} {'Sharpe':<8}")
    print("-" * 100)
    
    for i, r in enumerate(results_sorted, 1):
        print(f"{i:<4} {r['name']:<30} {r['avg_return']:>10.2f}% {r['outperformance']:>10.2f}% {r['beats_spy']:>10}/34      {r['consistency']:>10.1f}%  {r['sharpe']:>7.2f}")
    
    # Find best for consistent outperformance
    print("\n" + "="*100)
    print("🏆 STRATEGIES WITH REALISTIC CONSISTENT OUTPERFORMANCE (>5% annually)")
    print("="*100)
    
    consistent = [r for r in results_sorted if r['outperformance'] > 5 and r['outperformance'] < 20]
    
    if consistent:
        for i, r in enumerate(consistent[:5], 1):
            print(f"\n{i}. {r['name'].upper()}")
            print(f"   Average Annual Return: {r['avg_return']:.2f}%")
            print(f"   Outperformance vs S&P: +{r['outperformance']:.2f}%")
            print(f"   Stocks Beating S&P: {r['beats_spy']}/34 ({r['beats_spy']/34*100:.1f}%)")
            print(f"   Consistency: {r['consistency']:.1f}% of stocks within 1 std dev")
            print(f"   Volatility (Std Dev): {r['std_return']:.2f}%")
            print(f"   Best Performer: {r['best'][0]} ({r['best'][1]:.2f}%)")
            print(f"   Worst Performer: {r['worst'][0]} ({r['worst'][1]:.2f}%)")
            print(f"   Risk-Adjusted (Sharpe): {r['sharpe']:.3f}")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = Path(__file__).parent.parent / f'strategy_comprehensive_results_{timestamp}.json'
    
    output = {
        'timestamp': timestamp,
        'total_strategies': len(results),
        'strategies': [
            {
                'rank': i,
                'name': r['name'],
                'avg_return': r['avg_return'],
                'outperformance': r['outperformance'],
                'beats_spy': r['beats_spy'],
                'consistency': r['consistency'],
                'sharpe': r['sharpe']
            }
            for i, r in enumerate(results_sorted, 1)
        ]
    }
    
    with open(results_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Full results saved to: {results_file}")
    
    # Final recommendation
    print("\n" + "="*100)
    print("💡 RECOMMENDATION")
    print("="*100)
    
    if consistent:
        winner = consistent[0]
        print(f"\n✅ USE: {winner['name'].upper()}")
        print(f"   Why: Realistic outperformance of +{winner['outperformance']:.2f}% annually")
        print(f"   Beat S&P in {winner['beats_spy']}/34 stocks ({winner['beats_spy']/34*100:.1f}%)")
        print(f"   Expected annual return: {winner['avg_return']:.2f}%")
        print(f"\n📝 To use this strategy:")
        print(f"   1. Edit strategy_config.yaml")
        print(f"   2. Change: strategy: {winner['name']}")
        print(f"   3. Run: python scripts/multi_strategy_backtest.py")
    
    print("\n" + "="*100)
    
    return results_sorted


if __name__ == '__main__':
    results = main()
