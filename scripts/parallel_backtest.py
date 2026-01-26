#!/usr/bin/env python3
"""
Parallel Backtest - Run multiple strategies simultaneously for speed
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import json
from multiprocessing import Pool, cpu_count

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cached_data_loader import CachedDataLoader
from scripts.strategies import StrategyFactory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('ParallelBacktest')


def backtest_strategy(args: Tuple[str, Dict]) -> Tuple[str, Dict]:
    """Test single strategy on all stocks (worker function for parallel processing)"""
    strategy_name, data = args
    
    try:
        strategy = StrategyFactory.create(strategy_name)
        if strategy is None:
            return strategy_name, {'error': 'Not found'}
        
        annuals = []
        for symbol, prices in data.items():
            try:
                annual = strategy.backtest(prices)
                annuals.append(annual)
            except:
                pass
        
        if not annuals:
            return strategy_name, {'error': 'No results'}
        
        avg = np.mean(annuals)
        outperform = avg - 0.101
        beats_sp = sum(1 for a in annuals if a > 0.101)
        sharpe = (avg - 0.01) / max(np.std(annuals), 0.001)
        
        return strategy_name, {
            'return': avg,
            'outperform': outperform,
            'beats_sp': beats_sp,
            'sharpe': sharpe
        }
    except Exception as e:
        return strategy_name, {'error': str(e)[:50]}


def run_parallel_backtest():
    """Run all strategies in parallel"""
    loader = CachedDataLoader()
    symbols = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
        'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
        'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
        'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
        'CPRT', 'CHKP'
    ]
    
    logger.info("=" * 80)
    logger.info("PARALLEL BACKTEST - 19 Strategies x 34 Stocks (ALL AT ONCE)")
    logger.info("=" * 80)
    
    # Load data
    logger.info("\nLoading data...")
    data = loader.load_all_stocks(symbols)
    logger.info(f"✓ Loaded {len(data)} stocks\n")
    
    # Get all strategies
    strategies = sorted(StrategyFactory.list_strategies())
    logger.info(f"Testing {len(strategies)} strategies in parallel:\n")
    
    # Prepare work items (strategy_name, data) tuples
    work_items = [(name, data) for name in strategies]
    
    # Run in parallel using all CPU cores
    num_workers = min(cpu_count(), len(strategies))
    logger.info(f"Using {num_workers} parallel workers...\n")
    
    results = {}
    with Pool(processes=num_workers) as pool:
        for strategy_name, metrics in pool.imap_unordered(backtest_strategy, work_items):
            if 'error' in metrics:
                logger.info(f"  ✗ {strategy_name:30s}: {metrics['error']}")
            else:
                status = "✓" if metrics['outperform'] > 0 else "✗"
                logger.info(
                    f"  {status} {strategy_name:28s}: {metrics['return']:7.4f} | "
                    f"{metrics['outperform']:+7.4f} | {metrics['beats_sp']}/34"
                )
                results[strategy_name] = metrics
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("FINAL RANKING")
    logger.info("=" * 80)
    
    ranked = sorted(results.items(), key=lambda x: x[1]['outperform'], reverse=True)
    
    logger.info(f"\n{'Rank':<6} {'Strategy':<30} {'Return':<10} {'vs SPY':<10} {'Sharpe':<8}")
    logger.info("-" * 70)
    
    for i, (name, metrics) in enumerate(ranked, 1):
        logger.info(
            f"{i:<6} {name:<30} {metrics['return']:>9.4f}  "
            f"{metrics['outperform']:>+9.4f}  {metrics['sharpe']:>7.3f}"
        )
    
    logger.info("\n" + "=" * 80)
    if ranked:
        top_3 = [name for name, _ in ranked[:3]]
        logger.info(f"TOP 3: {' > '.join(top_3)}")
        logger.info("=" * 80)
    
    # Save results
    results_file = Path(__file__).parent / 'backtest_results_full.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"\n✓ Results saved to: {results_file}\n")
    
    return results


if __name__ == '__main__':
    run_parallel_backtest()
