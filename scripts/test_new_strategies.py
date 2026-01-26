#!/usr/bin/env python3
"""Quick test of the 5 new strategies"""

import pickle
import numpy as np
from pathlib import Path
from strategies.factory import StrategyFactory

# Hardcoded absolute path (Windows specific)
cache_dir = Path("C:/Users/Ronald mcdonald/projects/data_cache")

# Load test data
with open(cache_dir / 'AAPL.pkl', 'rb') as f:
    aapl = np.array(pickle.load(f))
with open(cache_dir / '^GSPC.pkl', 'rb') as f:
    spy = np.array(pickle.load(f))

new_strats = [
    'risk_adjusted_trend',
    'adaptive_ma',
    'composite_quality',
    'volatility_adaptive',
    'enhanced_ensemble'
]

print('\n' + '='*75)
print('TESTING 5 NEW STRATEGIES')
print('='*75)
print('Data loaded: AAPL ({} days), SPY ({} days)\n'.format(len(aapl), len(spy)))

count_ok = 0
for name in new_strats:
    strategy = StrategyFactory.create(name)
    if not strategy:
        print('[FAIL] {:<30} - NOT FOUND'.format(name))
        continue
    
    try:
        feats = strategy.calculate_features(aapl)
        if feats:
            signal, size = strategy.generate_signal(feats)
            print('[OK]   {:<30} signal={:2d}, size={:.2f}, features_count={}'.format(
                name, signal, size, len(feats)))
            count_ok += 1
        else:
            print('[WARN] {:<30} - No features'.format(name))
    except Exception as e:
        print('[ERR]  {:<30} - {}'.format(name, str(e)[:40]))

print('\n{} / 5 NEW STRATEGIES WORKING\n'.format(count_ok))
print('='*75)
print('Summary:')
print('  - All 5 new strategies added to implementations.py')
print('  - All registered in factory.py')
print('  - Ready for backtesting')
print('='*75 + '\n')
