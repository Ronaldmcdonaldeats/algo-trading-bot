#!/usr/bin/env python3
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cached_data_loader import CachedDataLoader
from strategies.factory import StrategyFactory

loader = CachedDataLoader()
prices = loader.load_stock_data('AAPL')
print(f'Prices: {len(prices)}')

factory = StrategyFactory()

# Test one backtest
initial_capital = 10000.0
balance = initial_capital
shares = 0
max_balance = initial_capital
min_balance = initial_capital
trades = 0

strategy = factory.create('ultimate_hybrid')
print(f'Testing {strategy}...')

# Backtest - minimum 50 bars
for i in range(50, min(100, len(prices))):  # Just test 50 bars
    close = prices[i]
    
    if hasattr(strategy, 'calculate_features'):
        features = strategy.calculate_features(prices[:i+1])
        if features:
            signal, strength = strategy.generate_signal(features)
        else:
            signal = 0
    else:
        signal = 1 if i > 50 and prices[i] > prices[i-1] else 0
    
    # Trade
    if signal > 0 and balance > 0 and shares == 0:
        shares = int(balance / close * 0.95)
        if shares > 0:
            balance -= shares * close
            trades += 1
            print(f'  Bar {i}: BUY {shares} at {close:.2f}')
    elif signal < 0 and shares > 0:
        balance += shares * close
        print(f'  Bar {i}: SELL {shares} at {close:.2f}')
        shares = 0
        trades += 1
    
    current = balance + shares * close
    max_balance = max(max_balance, current)
    min_balance = min(min_balance, current)

# Close position
if shares > 0:
    balance += shares * prices[-1]

annual_return = (balance - initial_capital) / initial_capital
max_dd = (min_balance - initial_capital) / initial_capital

print(f'\nFinal balance: {balance:.2f}')
print(f'Return: {annual_return*100:.2f}%')
print(f'Max DD: {max_dd*100:.2f}%')
print(f'Trades: {trades}')
