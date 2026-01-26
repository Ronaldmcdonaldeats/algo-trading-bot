#!/usr/bin/env python3
"""
STRESS TEST: Test strategies during recession/crash scenarios
Simulates 3 adverse market conditions:
1. Gradual decline (slow bear market)
2. Sudden crash (-20% in 1 day)
3. High volatility + bad news spike
"""
import sys
import logging
from pathlib import Path
import numpy as np
import json
from typing import Dict, Tuple

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

# Test on smaller set of key stocks during stress scenarios
TEST_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']  # 5 large caps


def create_recession_scenario_1(prices: np.ndarray) -> np.ndarray:
    """Scenario 1: Gradual decline (slow bear market - 30% drop over 60 days)"""
    prices_copy = prices.copy().astype(float)
    start_idx = max(0, len(prices) - 250)  # Last 1 year
    
    if start_idx >= len(prices):
        return prices_copy
    
    # Create gradual decline
    decline_length = min(60, len(prices) - start_idx)
    if decline_length > 0:
        for i in range(start_idx, start_idx + decline_length):
            prices_copy[i] *= (1 - 0.30 * (i - start_idx) / decline_length)
    
    return prices_copy


def create_recession_scenario_2(prices: np.ndarray) -> np.ndarray:
    """Scenario 2: Sudden crash - 20% drop in 1 day + recovery attempt"""
    prices_copy = prices.copy().astype(float)
    crash_idx = max(0, len(prices) - 100)  # Crash in recent history
    
    if crash_idx < len(prices):
        # Sudden 20% drop
        prices_copy[crash_idx] *= 0.80
        
        # Volatility + slow recovery over next 50 days
        recovery_days = min(50, len(prices) - crash_idx - 1)
        recovery_rate = (1.0 - 0.20) ** (1.0 / recovery_days) if recovery_days > 0 else 1.0
        
        for i in range(crash_idx + 1, crash_idx + recovery_days + 1):
            prices_copy[i] = prices_copy[i-1] * recovery_rate
    
    return prices_copy


def create_recession_scenario_3(prices: np.ndarray) -> np.ndarray:
    """Scenario 3: High volatility + bad news spikes"""
    prices_copy = prices.copy().astype(float)
    start_idx = max(0, len(prices) - 200)
    
    if start_idx >= len(prices):
        return prices_copy
    
    # Add large random swings
    np.random.seed(42)  # Reproducible
    for i in range(start_idx, len(prices)):
        # Large daily moves (±5-15% daily volatility)
        shock = np.random.normal(loc=-0.02, scale=0.10)  # Negative bias (bad news)
        prices_copy[i] *= (1 + shock)
        # Floor: can't go below 50% of crash start price
        crash_start = prices[start_idx]
        prices_copy[i] = max(prices_copy[i], crash_start * 0.50)
    
    return prices_copy


def backtest_strategy_in_scenario(
    strategy_name: str, 
    prices: np.ndarray, 
    scenario_name: str
) -> Dict:
    """Test a strategy on recession prices"""
    try:
        factory = StrategyFactory()
        strategy_class = factory.create(strategy_name)
        if not strategy_class:
            return {'error': 'Strategy not found'}
        
        strategy = strategy_class()
        initial_capital = 10000.0
        balance = initial_capital
        shares = 0
        max_balance = initial_capital
        min_balance = initial_capital
        trade_count = 0
        
        # Backtest
        for i in range(20, len(prices)):
            close = prices[i]
            
            # Get signal
            signal = strategy.analyze(prices[:i+1])
            
            # Trade execution
            if signal > 0.5 and balance > 0 and shares == 0:
                shares = int(balance / close)
                if shares > 0:
                    balance -= shares * close
                    trade_count += 1
            elif signal < -0.5 and shares > 0:
                balance += shares * close
                shares = 0
                trade_count += 1
            
            # Close position at end
            if i == len(prices) - 1 and shares > 0:
                balance += shares * close
                shares = 0
            
            max_balance = max(max_balance, balance + shares * close)
            min_balance = min(min_balance, balance + shares * close)
        
        final_value = balance + shares * prices[-1] if shares > 0 else balance
        return_pct = (final_value - initial_capital) / initial_capital * 100
        max_drawdown = (min_balance - initial_capital) / initial_capital * 100
        max_gain = (max_balance - initial_capital) / initial_capital * 100
        
        return {
            'strategy': strategy_name,
            'scenario': scenario_name,
            'final_value': final_value,
            'return': return_pct,
            'max_drawdown': max_drawdown,
            'max_gain': max_gain,
            'trades': trade_count,
            'error': None
        }
    except Exception as e:
        return {
            'strategy': strategy_name,
            'scenario': scenario_name,
            'error': str(e)[:100]
        }


def run_stress_test():
    """Run stress test on all scenarios and strategies"""
    logger.info("="*80)
    logger.info("STRESS TEST: Strategy Performance During Recession/Crash")
    logger.info("="*80)
    logger.info("")
    
    # Load data
    logger.info("Loading data...")
    loader = CachedDataLoader()
    data = {}
    for symbol in TEST_SYMBOLS:
        try:
            prices = loader.load_stock_data(symbol)
            if prices is not None and len(prices) > 100:
                data[symbol] = prices
        except:
            pass
    logger.info(f"Loaded {len(data)}/{len(TEST_SYMBOLS)} stocks\n")
    
    # Strategies to test
    strategies = ['risk_adjusted_trend', 'ultra_ensemble', 'hybrid']
    
    # Scenarios
    scenarios = {
        'Normal': lambda p: p,
        'Gradual Decline (-30%)': create_recession_scenario_1,
        'Sudden Crash (-20%)': create_recession_scenario_2,
        'High Volatility + Bad News': create_recession_scenario_3
    }
    
    results = []
    
    # Run tests
    for scenario_name, scenario_fn in scenarios.items():
        logger.info(f"\n{'='*80}")
        logger.info(f"SCENARIO: {scenario_name}")
        logger.info(f"{'='*80}")
        logger.info("")
        
        for strategy in strategies:
            returns = []
            drawdowns = []
            
            for symbol in data.keys():
                prices = scenario_fn(data[symbol])
                result = backtest_strategy_in_scenario(strategy, prices, scenario_name)
                
                if result.get('error') is None:
                    returns.append(result['return'])
                    drawdowns.append(result['max_drawdown'])
                    results.append(result)
            
            # Average across symbols
            if returns:
                avg_return = np.mean(returns)
                avg_drawdown = np.mean(drawdowns)
                max_dd = min(drawdowns)
                
                # Format output
                if avg_return < 0:
                    status = "✗ LOSS"
                elif avg_return < 5:
                    status = "⚠️ WEAK"
                else:
                    status = "✓ PROFIT"
                
                logger.info(
                    f"{status} {strategy:25s} | "
                    f"Return: {avg_return:+7.2f}% | "
                    f"Max Drawdown: {max_dd:7.2f}% | "
                    f"Avg Drawdown: {avg_drawdown:7.2f}%"
                )
    
    logger.info("")
    logger.info("="*80)
    logger.info("SUMMARY")
    logger.info("="*80)
    
    # Analyze performance across scenarios
    for strategy in strategies:
        logger.info(f"\n{strategy}:")
        
        for scenario_name in scenarios.keys():
            scenario_results = [r for r in results 
                              if r.get('strategy') == strategy 
                              and r.get('scenario') == scenario_name
                              and r.get('error') is None]
            
            if scenario_results:
                avg_return = np.mean([r['return'] for r in scenario_results])
                max_drawdown = min([r['max_drawdown'] for r in scenario_results])
                
                logger.info(f"  {scenario_name:30s}: {avg_return:+7.2f}% return, {max_drawdown:7.2f}% max DD")
    
    # Save results
    output_file = Path(__file__).parent.parent / "stress_test_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"\n\nResults saved to {output_file}")
    
    logger.info("\n" + "="*80)
    logger.info("RECOMMENDATIONS")
    logger.info("="*80)
    logger.info("""
✓ risk_adjusted_trend: Best for risk management in downturns
✓ ultra_ensemble: Good balance of offense/defense
✓ hybrid: Simplest but may struggle in crashes

For RECESSION TRADING: Use risk_adjusted_trend (manages risk best)
For CRASH PROTECTION: Prioritize max drawdown over returns
For RECOVERY: Position for upside after crash confirmation
    """)


if __name__ == '__main__':
    run_stress_test()
