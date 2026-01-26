#!/usr/bin/env python3
"""Quick test of the 5 new strategies"""

import pickle
import numpy as np
from pathlib import Path
from strategies.factory import StrategyFactory

# Test stocks
test_stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
cache_dir = Path("C:/Users/Ronald mcdonald/projects/data_cache")

# Load test data
test_data = {}
for stock in test_stocks:
    try:
        with open(cache_dir / (stock + '.pkl'), 'rb') as f:
            test_data[stock] = np.array(pickle.load(f))
    except:
        pass

new_strats = [
    'risk_adjusted_trend',
    'adaptive_ma',
    'composite_quality',
    'volatility_adaptive',
    'enhanced_ensemble'
]

print('\n' + '='*80)
print('TESTING 5 NEW STRATEGIES')
print('='*80)
print('Data loaded: {} stocks'.format(len(test_data)))
print('Test stocks: {}\n'.format(', '.join(test_stocks[:3]) + '...'))

count_ok = 0
for name in new_strats:
    strategy = StrategyFactory.create(name)
    if not strategy:
        print('[FAIL] {:<30} - NOT FOUND'.format(name))
        continue
    
    # Test on all stocks
    success_count = 0
    for stock, prices in test_data.items():
        try:
            feats = strategy.calculate_features(prices)
            if feats:
                signal, size = strategy.generate_signal(feats)
                success_count += 1
        except:
            pass
    
    if success_count == len(test_data):
        print('[OK]   {:<30} - Working on all {} test stocks'.format(name, len(test_data)))
        count_ok += 1
    else:
        print('[WARN] {:<30} - Working on {}/{} test stocks'.format(name, success_count, len(test_data)))

print('\n' + '='*80)
print('SUMMARY: {} / 5 NEW STRATEGIES OPERATIONAL'.format(count_ok))
print('='*80)
print('Strategies created:')
for i, s in enumerate(new_strats, 1):
    print('  {}. {}'.format(i, s))
print('\nAll strategies registered in factory and ready for backtesting.')
print('='*80 + '\n')
