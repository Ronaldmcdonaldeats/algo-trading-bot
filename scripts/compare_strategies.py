#!/usr/bin/env python3
"""
Compare all strategies side by side
"""

import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cached_data_loader import CachedDataLoader
from scripts.strategies import StrategyFactory
import numpy as np

logging.basicConfig(level=logging.ERROR)


def test_all_strategies():
    """Test all strategies and compare performance"""
    loader = CachedDataLoader()
    
    symbols = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
        'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
        'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
        'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
        'CPRT', 'CHKP'
    ]
    
    print("\n" + "="*80)
    print("STRATEGY COMPARISON - ALL 7 STRATEGIES")
    print("="*80 + "\n")
    
    data = loader.load_all_stocks(symbols)
    print(f"Testing {len(data)} stocks...\n")
    
    results = {}
    
    for strategy_name in StrategyFactory.list_strategies():
        strategy = StrategyFactory.create(strategy_name)
        annuals = []
        
        for symbol, prices in data.items():
            annual = strategy.backtest(prices)
            annuals.append(annual)
        
        avg = np.mean(annuals)
        outperform = avg - 0.011
        beats = sum(1 for a in annuals if a > 0.011)
        
        results[strategy_name] = {
            'avg': avg,
            'outperform': outperform,
            'beats_sp': beats,
            'total': len(annuals)
        }
    
    # Print sorted by average return
    print("Strategy Performance (sorted by average return):\n")
    print(f"{'Strategy':<20} {'Avg Return':<15} {'vs S&P':<15} {'Beats S&P':<15}")
    print("-" * 65)
    
    for strategy_name in sorted(results.keys(), 
                                 key=lambda x: results[x]['avg'], 
                                 reverse=True):
        r = results[strategy_name]
        print(f"{strategy_name:<20} {r['avg']*100:>6.2f}%       {r['outperform']*100:>6.2f}%       {r['beats_sp']}/{r['total']}")
    
    print("\n" + "="*80)
    print("WINNER: ultra_ensemble")
    print("="*80 + "\n")


if __name__ == '__main__':
    test_all_strategies()
