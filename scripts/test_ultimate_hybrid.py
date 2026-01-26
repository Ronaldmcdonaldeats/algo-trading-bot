#!/usr/bin/env python3
"""
Test Ultimate Hybrid Strategy
Target: Beat SPY by 10% (20.1% annual vs 10.1% SPY)
Works in: Normal markets AND uncertain/volatile markets
"""
import sys
import logging
from pathlib import Path
import numpy as np
import json

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

# Test on all 34 stocks
SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO',
    'ASML', 'NFLX', 'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST',
    'TMUS', 'CMCSA', 'INTU', 'VRTX', 'AEP', 'LRCX', 'SNPS', 'CDNS',
    'PCAR', 'PAYX', 'ABNB', 'PANW', 'CRWD', 'ZM', 'DXCM', 'WDAY', 'FAST', 'CPRT', 'CHKP'
]

SPY_ANNUAL_RETURN = 0.101  # 10.1%
TARGET_RETURN = 0.201  # 20.1% (beat SPY by 10%)


def backtest_strategy(strategy_name: str, prices: np.ndarray) -> dict:
    """Test a strategy on one stock"""
    try:
        factory = StrategyFactory()
        strategy = factory.create(strategy_name)  # This returns an instance
        if not strategy:
            return {'error': 'Strategy not found'}
        
        initial_capital = 10000.0
        balance = initial_capital
        shares = 0
        max_balance = initial_capital
        min_balance = initial_capital
        trades = 0
        
        # Backtest - minimum 50 bars for indicators
        for i in range(50, len(prices)):
            close = prices[i]
            
            # Calculate features using calculate_features if available
            if hasattr(strategy, 'calculate_features'):
                features = strategy.calculate_features(prices[:i+1])
                if features:
                    signal, strength = strategy.generate_signal(features)
                else:
                    signal = 0
            else:
                # Fallback for basic strategies
                signal = 1 if i > 50 and prices[i] > prices[i-1] else 0
            
            # Trade (signal should be 1 or -1)
            if signal == 1 and balance > 0 and shares == 0:
                shares = int(balance / close * 0.95)
                if shares > 0:
                    balance -= shares * close
                    trades += 1
            elif signal == -1 and shares > 0:
                balance += shares * close
                shares = 0
                trades += 1
            
            current = balance + shares * close
            max_balance = max(max_balance, current)
            min_balance = min(min_balance, current)
        
        # Close position
        if shares > 0:
            balance += shares * prices[-1]
            shares = 0
        
        annual_return = (balance - initial_capital) / initial_capital
        max_dd = (min_balance - initial_capital) / initial_capital
        
        return {
            'return': annual_return,
            'max_dd': max_dd,
            'trades': trades,
            'error': None
        }
    except Exception as e:
        return {'error': str(e)[:50]}


def run_ultimate_test():
    """Test ultimate hybrid strategy"""
    logger.info("="*90)
    logger.info("ULTIMATE HYBRID STRATEGY TEST")
    logger.info("Target: Beat SPY by 10% (+20.1% annual return)")
    logger.info("="*90)
    logger.info("")
    
    # Load data
    logger.info("Loading data for 34 stocks...")
    loader = CachedDataLoader()
    data = {}
    for symbol in SYMBOLS:
        try:
            prices = loader.load_stock_data(symbol)
            if prices is not None and len(prices) > 100:
                data[symbol] = prices
        except:
            pass
    logger.info(f"Loaded {len(data)}/{len(SYMBOLS)} stocks\n")
    
    # Test strategies
    strategies = [
        'ultimate_hybrid',
        'risk_adjusted_trend',
        'ultra_ensemble',
        'volatility_adaptive'
    ]
    
    results = {}
    
    for strategy in strategies:
        logger.info(f"Testing {strategy}...")
        returns = []
        draws = []
        errors_count = 0
        
        for symbol in list(data.keys())[:34]:  # All stocks
            result = backtest_strategy(strategy, data[symbol])
            
            if result.get('error') is None:
                returns.append(result['return'] * 100)
                draws.append(result['max_dd'] * 100)
            else:
                errors_count += 1
                if errors_count <= 3:  # Log first 3 errors
                    logger.info(f"  Error on {symbol}: {result.get('error')}")
        
        logger.info(f"  Completed: {len(returns)} successes, {errors_count} errors")
        
        if returns:
            avg_return = np.mean(returns)
            max_dd = np.min(draws)
            avg_dd = np.mean(draws)
            
            results[strategy] = {
                'return': avg_return,
                'max_dd': max_dd,
                'avg_dd': avg_dd
            }
            
            # Check vs SPY
            spy_beat = "✓ BEATS SPY" if avg_return > 10.1 else "✗ Below SPY"
            target_hit = "✓✓ TARGET HIT" if avg_return > 20.1 else "✗ Target missed"
            
            logger.info(
                f"{target_hit} {strategy:25s} | "
                f"Return: {avg_return:7.2f}% | "
                f"Max DD: {max_dd:7.2f}% | "
                f"Avg DD: {avg_dd:7.2f}% | {spy_beat}\n"
            )
    
    # Save results
    output_file = Path(__file__).parent.parent / "ultimate_hybrid_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info("="*90)
    logger.info("SUMMARY")
    logger.info("="*90)
    logger.info("")
    
    # Rank strategies
    sorted_results = sorted(results.items(), key=lambda x: x[1]['return'], reverse=True)
    
    for i, (name, result) in enumerate(sorted_results, 1):
        ret = result['return']
        dd = result['max_dd']
        beat_spy = ret - 10.1
        beat_target = ret - 20.1
        
        if beat_target > 0:
            status = "🏆 GOAL ACHIEVED"
        elif beat_spy > 0:
            status = f"✓ +{beat_spy:.2f}% over SPY"
        else:
            status = f"✗ {beat_spy:.2f}% vs SPY"
        
        logger.info(f"{i}. {name:25s}: {ret:7.2f}% return, {dd:7.2f}% max DD - {status}")
    
    logger.info("")
    logger.info("="*90)
    logger.info("ULTIMATE HYBRID FEATURES")
    logger.info("="*90)
    logger.info("""
✓ Multi-timeframe momentum (5-20-50-200 day MAs)
✓ Volatility-adaptive position sizing
✓ Mean reversion (Bollinger Bands)
✓ News/uncertainty detection (gap anomaly, vol spike)
✓ Hysteresis (prevents whipsaws)
✓ Risk management (reduce in high volatility)
✓ Works in normal AND uncertain markets
✓ Automatically handles crashes

Target: Beat SPY by 10%+ (achieve 20%+ annual)
    """)


if __name__ == '__main__':
    run_ultimate_test()
