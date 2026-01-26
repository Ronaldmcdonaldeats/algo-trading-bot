#!/usr/bin/env python3
"""
Fast Strategy Comparison - Quick backtest of all 17 strategies
"""

import sys
import logging
from pathlib import Path
from typing import Dict
import json

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cached_data_loader import CachedDataLoader
from scripts.strategies import StrategyFactory

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger('Backtest')


def run_backtest():
    """Simple fast backtest of all strategies"""
    loader = CachedDataLoader()
    symbols = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
        'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO', 'TMUS',
        'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS', 'PCAR',
        'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST',
        'CPRT', 'CHKP'
    ]
    benchmark_annual = 0.101  # SPY baseline
    
    logger.info("=" * 80)
    logger.info("FULL STRATEGY BACKTEST - 19 Strategies x 34 Stocks")
    logger.info("=" * 80)
    
    # Load data
    logger.info("\nLoading data...")
    data = loader.load_all_stocks(symbols)
    logger.info(f"✓ Loaded {len(data)} stocks\n")
    
    # Get all strategies
    strategies = sorted(StrategyFactory.list_strategies())
    logger.info(f"Testing {len(strategies)} strategies:\n")
    
    results = {}
    
    for strategy_name in strategies:
        try:
            strategy = StrategyFactory.create(strategy_name)
            if strategy is None:
                logger.info(f"  {strategy_name:30s}: FAILED (not found)")
                continue
            
            annuals = []
            for symbol, prices in data.items():
                try:
                    annual = strategy.backtest(prices)
                    annuals.append(annual)
                except:
                    pass
            
            if not annuals:
                logger.info(f"  {strategy_name:30s}: FAILED (no results)")
                continue
            
            avg = np.mean(annuals)
            outperform = avg - benchmark_annual
            beats_sp = sum(1 for a in annuals if a > benchmark_annual)
            sharpe = (avg - 0.01) / max(np.std(annuals), 0.001)
            
            results[strategy_name] = {
                'return': avg,
                'outperform': outperform,
                'beats_sp': beats_sp,
                'sharpe': sharpe
            }
            
            status = "✓" if outperform > 0 else "✗"
            logger.info(f"  {status} {strategy_name:28s}: {avg:7.4f} | {outperform:+7.4f} | {beats_sp}/34")
            
        except Exception as e:
            logger.info(f"  ✗ {strategy_name:28s}: ERROR - {str(e)[:40]}")
    
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
    top_3 = [name for name, _ in ranked[:3]]
    logger.info(f"TOP 3 PERFORMERS: {', '.join(top_3)}")
    logger.info("=" * 80)
    
    # Save results
    results_file = Path(__file__).parent / 'backtest_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"\n✓ Results saved to: {results_file}\n")
    
    return results


if __name__ == '__main__':
    run_backtest()
