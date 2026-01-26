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
print(f'Loaded {len(prices)} prices')
print(f'Price range: {prices.min():.2f} to {prices.max():.2f}')

factory = StrategyFactory()
strategy = factory.create('ultimate_hybrid')
print(f'Created strategy: {strategy}')
print(f'Strategy type: {type(strategy)}')
print(f'Has calculate_features: {hasattr(strategy, "calculate_features")}')
print(f'Has generate_signal: {hasattr(strategy, "generate_signal")}')

if prices is not None:
    try:
        # Use ALL prices  
        test_prices = prices
        print(f'\nTesting with {len(test_prices)} prices')
        features = strategy.calculate_features(test_prices)
        print(f'Features: {features}')
        if features:
            signal, strength = strategy.generate_signal(features)
            print(f'Signal: {signal}, Strength: {strength}')
            print('SUCCESS!')
        else:
            print('ERROR: Features dict is empty!')
    except Exception as e:
        import traceback
        print(f'Error: {e}')
        traceback.print_exc()
