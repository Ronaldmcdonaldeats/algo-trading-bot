#!/usr/bin/env python3
"""
Parallel backtest using threading (Windows-compatible)
Tests all strategies simultaneously using thread pool
"""
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys
import time
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trading_bot.data.providers import get_cached_data
from trading_bot.core.models import Position, PositionType, Trade
from trading_bot.strategy.factory import list_strategies, get_strategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 34 tech stocks
SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO',
    'ASML', 'NFLX', 'ADBE', 'CRM', 'INTU', 'CHKP', 'PYPL', 'SHOP',
    'SNPS', 'CDNS', 'ARM', 'LRCX', 'CRWD', 'PSTG', 'OKTA', 'DDOG',
    'ANET', 'MU', 'ORCL', 'IBM', 'CSCO', 'ACN', 'GWRE', 'KLAC', 'MRVL'
]

SPY_ANNUAL_RETURN = 0.101  # 10.1%


def backtest_strategy(strategy_name: str, all_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test one strategy on all symbols"""
    try:
        strategy_class = get_strategy(strategy_name)
        if not strategy_class:
            return {
                'strategy': strategy_name,
                'avg_return': 0.0,
                'outperformance': -SPY_ANNUAL_RETURN,
                'beats_spy': 0,
                'symbol_count': 0,
                'error': f'Strategy not found'
            }
        
        total_return = 0.0
        beats_count = 0
        successful_symbols = 0
        
        for symbol in SYMBOLS:
            if symbol not in all_data:
                continue
                
            data = all_data[symbol]
            if len(data) < 20:
                continue
            
            successful_symbols += 1
            
            # Initialize strategy
            strategy = strategy_class()
            
            # Run backtest
            initial_capital = 10000.0
            balance = initial_capital
            
            # Backtest loop
            for i in range(20, len(data)):
                close_price = data['close'].iloc[i]
                
                # Get signal from strategy
                signal = strategy.analyze(data.iloc[:i+1])
                
                # Simple trade execution
                if signal > 0.5 and balance > 0:  # Long
                    # Buy 1 share
                    shares = int(balance / close_price)
                    if shares > 0:
                        balance -= shares * close_price
                elif signal < -0.5 and balance >= 0:  # Exit
                    # Sell shares
                    balance += shares * close_price
            
            # Final price
            final_price = data['close'].iloc[-1]
            if 'shares' in locals() and shares > 0:
                balance += shares * final_price
            
            annual_return = (balance - initial_capital) / initial_capital
            total_return += annual_return
            
            if annual_return > SPY_ANNUAL_RETURN:
                beats_count += 1
        
        avg_return = total_return / max(successful_symbols, 1)
        outperformance = avg_return - SPY_ANNUAL_RETURN
        
        return {
            'strategy': strategy_name,
            'avg_return': avg_return,
            'outperformance': outperformance,
            'beats_spy': beats_count,
            'symbol_count': successful_symbols,
            'error': None
        }
        
    except Exception as e:
        return {
            'strategy': strategy_name,
            'avg_return': 0.0,
            'outperformance': -SPY_ANNUAL_RETURN,
            'beats_spy': 0,
            'symbol_count': 0,
            'error': str(e)
        }


def run_threaded_backtest():
    """Run all strategies in parallel using threads"""
    logger.info("Loading data for 34 stocks...")
    
    # Load all data once
    all_data = {}
    for symbol in SYMBOLS:
        try:
            data = get_cached_data(symbol)
            all_data[symbol] = data
        except Exception as e:
            logger.warning(f"Failed to load {symbol}: {e}")
    
    logger.info(f"Loaded {len(all_data)}/{len(SYMBOLS)} stocks")
    
    # Get all strategies
    strategies = list_strategies()
    logger.info(f"Testing {len(strategies)} strategies in parallel...")
    
    results = {}
    start_time = time.time()
    
    # Use ThreadPoolExecutor for parallel execution
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Submit all tasks
        futures = {
            executor.submit(backtest_strategy, strategy, all_data): strategy
            for strategy in strategies
        }
        
        # Process results as they complete
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            strategy_name = result['strategy']
            results[strategy_name] = result
            completed += 1
            
            # Format output
            avg_ret = result['avg_return'] * 100
            outperf = result['outperformance'] * 100
            beats = result['beats_spy']
            symbol_count = result['symbol_count']
            
            # Status indicator
            if result['error']:
                status = f"✗ ERROR: {result['error']}"
            elif result['beats_spy'] == 0:
                status = "✗"
            else:
                status = "✓"
            
            logger.info(
                f"{status} {strategy_name:25s} | "
                f"{avg_ret:7.2f}% | {outperf:+7.2f}% | {beats}/{symbol_count}"
            )
    
    elapsed = time.time() - start_time
    logger.info(f"\nCompleted in {elapsed:.1f} seconds")
    
    # Save results
    output_file = Path(__file__).parent.parent / "backtest_results_threaded.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results saved to {output_file}")
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("SUMMARY - Top Performers:")
    
    sorted_results = sorted(
        results.items(),
        key=lambda x: x[1]['outperformance'],
        reverse=True
    )
    
    for name, result in sorted_results[:5]:
        if not result['error']:
            outperf = result['outperformance'] * 100
            logger.info(f"  {name:25s}: {outperf:+7.2f}% vs SPY ({result['beats_spy']}/{result['symbol_count']} beats)")


if __name__ == '__main__':
    run_threaded_backtest()
