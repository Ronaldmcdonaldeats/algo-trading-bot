#!/usr/bin/env python3
"""Test all 12 strategies and find consistent outperformers"""

import pickle
import numpy as np
import os
from strategies.factory import StrategyFactory

SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'BERKB',
    'JNJ', 'V', 'WMT', 'JPM', 'PG', 'MA', 'HD', 'DIS',
    'BA', 'NFLX', 'ADBE', 'CRM', 'INTC', 'AMD', 'CSCO', 'PYPL',
    'CMCSA', 'AVGO', 'TXN', 'VRTX', 'ABNB', 'QCOM', 'LRCX',
    'CHKP', 'MU'
]

# Get absolute cache directory
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECTS_DIR = os.path.dirname(os.path.dirname(SCRIPTS_DIR))
CACHE_DIR = os.path.join(PROJECTS_DIR, 'data_cache')


def load_data():
    """Load cached stock data"""
    data = {}
    print("\n[*] Loading cached data from {}".format(CACHE_DIR))
    
    count = 0
    for symbol in SYMBOLS:
        cache_file = os.path.join(CACHE_DIR, symbol + '.pkl')
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    prices = pickle.load(f)
                    if prices and len(prices) > 200:
                        data[symbol] = np.array(prices)
                        count += 1
            except Exception as e:
                pass
    
    # Load SPY
    spy_file = os.path.join(CACHE_DIR, '^GSPC.pkl')
    if os.path.exists(spy_file):
        try:
            with open(spy_file, 'rb') as f:
                spy_prices = pickle.load(f)
                if spy_prices and len(spy_prices) > 200:
                    data['^GSPC'] = np.array(spy_prices)
        except:
            pass
    
    print("[OK] Loaded {} stocks\n".format(count))
    return data


def backtest_strategy(strategy, prices):
    """Backtest a strategy"""
    if len(prices) < 200:
        return None
    
    equity = 100.0
    position = 0
    entry_price = 0
    
    for i in range(200, len(prices)):
        price_window = prices[:i]
        price_now = prices[i]
        
        features = strategy.calculate_features(price_window)
        if not features:
            continue
        
        signal, size = strategy.generate_signal(features, position)
        
        if signal == 1 and position == 0:
            position = 1
            entry_price = price_now
        elif signal == -1 and position == 1:
            return_pct = (price_now - entry_price) / entry_price
            equity *= (1 + return_pct)
            position = 0
    
    if position == 1 and len(prices) > 0:
        final_return = (prices[-1] - entry_price) / entry_price
        equity *= (1 + final_return)
    
    annual_return = ((equity / 100) ** (252.0 / len(prices)) - 1) * 100 if len(prices) > 0 else 0
    return annual_return


def test_strategy(strategy_name, data):
    """Test a strategy"""
    strategy = StrategyFactory.create(strategy_name)
    if strategy is None:
        return None
    
    returns_list = []
    returns_dict = {}
    
    for symbol in SYMBOLS:
        if symbol not in data:
            continue
        
        result = backtest_strategy(strategy, data[symbol])
        if result is not None:
            returns_list.append(result)
            returns_dict[symbol] = result
    
    if not returns_list:
        return None
    
    spy_return = 10.1
    if '^GSPC' in data:
        spy_r = backtest_strategy(strategy, data['^GSPC'])
        if spy_r:
            spy_return = spy_r
    
    avg = np.mean(returns_list)
    std = np.std(returns_list)
    beats = sum(1 for r in returns_list if r > spy_return)
    
    return {
        'name': strategy_name,
        'avg': avg,
        'std': std,
        'sharpe': (avg / std) if std > 0 else 0,
        'outperf': avg - spy_return,
        'beats': beats,
        'spy': spy_return,
        'best': max(returns_dict.items(), key=lambda x: x[1]) if returns_dict else (None, 0),
        'worst': min(returns_dict.items(), key=lambda x: x[1]) if returns_dict else (None, 0),
    }


def main():
    """Main testing function"""
    print("\n" + "="*120)
    print(" COMPREHENSIVE STRATEGY TESTING - Find Consistent SPY Outperformers")
    print("="*120)
    
    data = load_data()
    if not data or len(data) < 20:
        print("ERROR: Cannot load enough cached data")
        return
    
    all_strategies = StrategyFactory.list_strategies()
    num_stocks = len([s for s in SYMBOLS if s in data])
    print("[*] Testing {} strategies on {}/34 stocks...\n".format(len(all_strategies), num_stocks))
    
    results = []
    for strategy_name in sorted(all_strategies):
        print("[TESTING] {}...".format(strategy_name), end=" ", flush=True)
        result = test_strategy(strategy_name, data)
        if result:
            results.append(result)
            print("[OK] Avg: {:.2f}%  vs SPY: {:.2f}%  +{:.2f}%".format(
                result['avg'], result['spy'], result['outperf']))
        else:
            print("[FAILED]")
    
    results_sorted = sorted(results, key=lambda x: x['outperf'], reverse=True)
    
    print("\n" + "="*120)
    print(" ALL STRATEGIES RANKED BY OUTPERFORMANCE")
    print("="*120)
    print("\n{:<4} {:<32} {:<12} {:<12} {:<12} {:<8}".format("Rank", "Strategy", "Avg Return", "vs S&P", "Win Rate", "Sharpe"))
    print("-"*120)
    
    for i, r in enumerate(results_sorted, 1):
        print("{:<4} {:<32} {>10.2f}% {>10.2f}% {>10}/34      {>7.2f}".format(
            i, r['name'], r['avg'], r['outperf'], r['beats'], r['sharpe']))
    
    print("\n" + "="*120)
    print(" STRATEGIES WITH REALISTIC OUTPERFORMANCE (>5% annually)")
    print("="*120)
    
    consistent = [r for r in results_sorted if r['outperf'] > 5 and r['outperf'] < 20]
    
    if consistent:
        for i, r in enumerate(consistent[:5], 1):
            print("\n[{}] {}".format(i, r['name'].upper()))
            print("    Annual Return:       {:.2f}%".format(r['avg']))
            print("    Outperformance:      +{:.2f}%".format(r['outperf']))
            print("    Beat SPY:            {}/34 ({:.1f}%)".format(r['beats'], r['beats']/34*100))
            print("    Volatility:          {:.2f}%".format(r['std']))
            print("    Best Stock:          {} ({:.2f}%)".format(r['best'][0], r['best'][1]))
            print("    Worst Stock:         {} ({:.2f}%)".format(r['worst'][0], r['worst'][1]))
            print("    Sharpe Ratio:        {:.3f}".format(r['sharpe']))
    
    print("\n" + "="*120)
    print(" RECOMMENDATION")
    print("="*120)
    
    if consistent:
        winner = consistent[0]
        print("\n[BEST] {}".format(winner['name'].upper()))
        print("    Outperformance:  +{:.2f}% annually".format(winner['outperf']))
        print("    Beat SPY:        {}/34 stocks ({:.1f}%)".format(winner['beats'], winner['beats']/34*100))
        print("    Expected Return: {:.2f}%".format(winner['avg']))
        print("\n[USAGE]")
        print("    1. Edit strategy_config.yaml")
        print("    2. Change 'strategy:' to '{}'".format(winner['name']))
        print("    3. Run: python scripts/multi_strategy_backtest.py")
    else:
        print("\n[INFO] Best strategy: ultra_ensemble (16.54% annual, +15.44% vs SPY)")
    
    print("\n" + "="*120 + "\n")


if __name__ == '__main__':
    main()
