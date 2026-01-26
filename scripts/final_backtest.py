#!/usr/bin/env python3
"""
Final backtest - Test remaining 4 strategies sequentially
Tests: enhanced_ensemble, premium_hybrid, smart_hybrid, volatility_adaptive
"""
import json
import logging
from pathlib import Path
import sys
from typing import Dict
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cached_data_loader import CachedDataLoader
from strategies.factory import StrategyFactory

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO',
    'ASML', 'NFLX', 'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST',
    'TMUS', 'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS',
    'PCAR', 'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST', 'CPRT', 'CHKP'
]

SPY_ANNUAL_RETURN = 0.101


def backtest_strategy_simple(strategy_name: str, data_cache: Dict) -> Dict:
    """Backtest a single strategy on all symbols"""
    try:
        factory = StrategyFactory()
        strategy_class = factory.create(strategy_name)
        if not strategy_class:
            return {
                'strategy': strategy_name,
                'avg_return': 0.0,
                'outperformance': -SPY_ANNUAL_RETURN,
                'beats_spy': 0,
                'symbol_count': 0,
                'status': 'NOT_FOUND'
            }
        
        total_return = 0.0
        beats_count = 0
        successful_symbols = 0
        
        for symbol in SYMBOLS:
            try:
                if symbol not in data_cache:
                    continue
                
                prices = data_cache[symbol]
                if len(prices) < 30:
                    continue
                    
                successful_symbols += 1
                
                strategy = strategy_class()
                initial_capital = 10000.0
                shares = 0
                balance = initial_capital
                
                # Backtest - use numpy prices array
                for i in range(20, len(prices)):
                    close = prices[i]
                    
                    # Get signal - strategy expects prices array
                    signal = strategy.analyze(prices[:i+1])
                    
                    # Trade
                    if signal > 0.5 and balance > 0 and shares == 0:
                        shares = int(balance / close)
                        balance -= shares * close
                    elif signal < -0.5 and shares > 0:
                        balance += shares * close
                        shares = 0
                
                # Close position
                if shares > 0:
                    final_close = prices[-1]
                    balance += shares * final_close
                    shares = 0
                
                annual_return = (balance - initial_capital) / initial_capital
                total_return += annual_return
                
                if annual_return > SPY_ANNUAL_RETURN:
                    beats_count += 1
                    
            except Exception as e:
                logger.debug(f"  Error on {symbol}: {e}")
                continue
        
        if successful_symbols == 0:
            return {
                'strategy': strategy_name,
                'avg_return': 0.0,
                'outperformance': -SPY_ANNUAL_RETURN,
                'beats_spy': 0,
                'symbol_count': 0,
                'status': 'NO_DATA'
            }
        
        avg_return = total_return / successful_symbols
        outperformance = avg_return - SPY_ANNUAL_RETURN
        
        return {
            'strategy': strategy_name,
            'avg_return': avg_return,
            'outperformance': outperformance,
            'beats_spy': beats_count,
            'symbol_count': successful_symbols,
            'status': 'OK'
        }
        
    except Exception as e:
        logger.error(f"ERROR in {strategy_name}: {e}")
        return {
            'strategy': strategy_name,
            'avg_return': 0.0,
            'outperformance': -SPY_ANNUAL_RETURN,
            'beats_spy': 0,
            'symbol_count': 0,
            'status': f'ERROR: {str(e)[:50]}'
        }


if __name__ == '__main__':
    # Load all data once
    logger.info("Loading data for remaining strategies...")
    loader = CachedDataLoader()
    data_cache = loader.load_all_stocks(SYMBOLS)
    logger.info(f"Loaded {len(data_cache)}/{len(SYMBOLS)} stocks")
    logger.info("")
    
    # Test 4 remaining strategies
    remaining_strategies = [
        'volatility_adaptive',
        'enhanced_ensemble',
        'premium_hybrid',
        'smart_hybrid'
    ]
    
    logger.info("Testing remaining 4 strategies sequentially...")
    logger.info("")
    
    results = {}
    
    for strategy in remaining_strategies:
        logger.info(f"Testing {strategy}...")
        result = backtest_strategy_simple(strategy, data_cache)
        results[strategy] = result
        
        # Output result
        avg_ret = result['avg_return'] * 100
        outperf = result['outperformance'] * 100
        beats = result['beats_spy']
        total = result['symbol_count']
        status = result['status']
        
        if status == 'OK':
            if beats == 0:
                symbol = "✗"
            else:
                symbol = "✓"
            logger.info(f"{symbol} {strategy:25s} : {avg_ret:7.2f}% | {outperf:+7.2f}% | {beats}/{total}")
        else:
            logger.info(f"✗ {strategy:25s} : {status}")
        
        logger.info("")
    
    # Save
    output_file = Path(__file__).parent.parent / "backtest_results_final.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to {output_file}")
