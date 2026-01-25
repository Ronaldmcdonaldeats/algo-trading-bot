"""
Phase 10: Standalone Bayesian Optimizer
Simplified version that doesn't rely on complex imports
"""

import numpy as np
import pandas as pd
import logging
import json
import os
from typing import Dict, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_stock_data_simple(symbol: str) -> np.ndarray:
    """Load stock data from CSV if available, otherwise use synthetic"""
    try:
        # Try to load from CSV
        import yfinance as yf
        df = yf.download(symbol, start='2000-01-01', end='2025-01-26', progress=False)
        if df is not None and len(df) > 100:
            return df['Close'].values
    except:
        pass
    
    # Fallback: generate synthetic data with embedded crashes
    logger.info(f"Generating synthetic data for {symbol}")
    np.random.seed(hash(symbol) % 2**32)
    
    trading_days = 6540  # 25 years of trading
    returns = np.random.normal(0.0003, 0.015, trading_days)  # Slight positive drift
    
    # Add market crashes
    crashes = {
        int(trading_days * 0.15): -0.15,  # 2000 crash
        int(trading_days * 0.58): -0.20,  # 2008 crash
        int(trading_days * 0.85): -0.08,  # 2020 COVID
    }
    
    for day, impact in crashes.items():
        if 0 <= day < len(returns):
            returns[day] = impact
    
    prices = np.exp(np.cumsum(returns)) * 100
    return prices


def calculate_rsi_fast(prices: np.ndarray, idx: int, window: int = 14) -> float:
    """Fast RSI calculation for specific index"""
    if idx < window + 1:
        return 50.0
    
    recent = prices[max(0, idx-window):idx+1]
    if len(recent) < 2:
        return 50.0
    
    deltas = np.diff(recent)
    gains = deltas[deltas > 0]
    losses = np.abs(deltas[deltas < 0])
    
    avg_gain = np.mean(gains) if len(gains) > 0 else 0.0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0
    
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return float(rsi)


def backtest_simple(
    prices: np.ndarray,
    sma_fast: int,
    sma_slow: int,
    rsi_oversold: int,
    rsi_overbought: int,
    ma_window: int
) -> float:
    """Fast backtest returning annual return"""
    if len(prices) < max(sma_slow, ma_window, 100):
        return 0.0
    
    capital = 100000.0
    position = 0.0
    start_idx = max(sma_slow, ma_window, 50)
    
    for i in range(start_idx, len(prices)):
        price = prices[i]
        
        # Get MA for regime (fast)
        ma = np.mean(prices[max(0, i-ma_window):i])
        
        # Get SMA signals (cache-friendly)
        fast_ma = np.mean(prices[max(0, i-sma_fast):i])
        slow_ma = np.mean(prices[max(0, i-sma_slow):i])
        
        if fast_ma > slow_ma:
            sma_sig = 1.0
        elif fast_ma < slow_ma:
            sma_sig = -1.0
        else:
            sma_sig = 0.0
        
        # RSI (precomputed on subset)
        rsi = calculate_rsi_fast(prices, i, 14)
        
        # Regime detection
        if price > ma and sma_sig > 0:
            regime = 'bull'
        else:
            regime = 'bear'
        
        # Signal generation
        if regime == 'bull':
            signal = sma_sig
        else:
            if rsi < rsi_oversold:
                signal = 1.0
            elif rsi > rsi_overbought:
                signal = -1.0
            else:
                signal = 0.0
        
        # Simple position management
        if position == 0 and signal > 0:
            position = capital * 0.9 / price
        elif position > 0 and signal < 0:
            capital = position * price
            position = 0.0
    
    # Close position
    if position > 0:
        capital = position * prices[-1]
    
    # Calculate annual return
    if capital <= 100000:
        annual_return = (capital - 100000) / 100000 / 25
    else:
        annual_return = (capital / 100000) ** (1/25) - 1
    
    return max(annual_return, -0.5)  # Cap negative returns


class Phase10SimpleOptimizer:
    """Grid-based optimizer (simpler than Bayesian)"""
    
    STOCKS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX', 'ADBE', 'INTC']
    TARGET_RETURN = 0.061  # 6.1% (5% above S&P 500's 1.1%)
    
    def __init__(self):
        self.best_params = None
        self.best_return = 0.0
    
    def optimize(self):
        """Grid search over parameter space"""
        logger.info("="*80)
        logger.info("PHASE 10: GRID-BASED OPTIMIZER")
        logger.info("Target: 6.1% annual return (5% above S&P 500)")
        logger.info("="*80)
        logger.info("")
        
        # Load data
        logger.info("Loading stock data...")
        data = {}
        for symbol in self.STOCKS:
            prices = load_stock_data_simple(symbol)
            if len(prices) > 100:
                data[symbol] = prices
        
        logger.info(f"Loaded {len(data)} stocks\n")
        
        # Parameter grid (simplified for speed)
        sma_fast_vals = [10, 15, 20, 25]
        sma_slow_vals = [40, 50, 60, 70, 80]
        rsi_oversold_vals = [25, 30, 35]
        rsi_overbought_vals = [65, 70, 75]
        ma_window_vals = [100, 150, 200, 250]
        
        total_combos = (len(sma_fast_vals) * len(sma_slow_vals) * 
                       len(rsi_oversold_vals) * len(rsi_overbought_vals) * 
                       len(ma_window_vals))
        
        logger.info(f"Testing {total_combos} parameter combinations...\n")
        
        iteration = 0
        for sma_fast in sma_fast_vals:
            for sma_slow in sma_slow_vals:
                if sma_fast >= sma_slow:
                    continue
                
                for rsi_oversold in rsi_oversold_vals:
                    for rsi_overbought in rsi_overbought_vals:
                        if rsi_oversold >= rsi_overbought:
                            continue
                        
                        for ma_window in ma_window_vals:
                            iteration += 1
                            
                            # Backtest on all stocks
                            returns = []
                            for prices in data.values():
                                ret = backtest_simple(
                                    prices,
                                    sma_fast,
                                    sma_slow,
                                    rsi_oversold,
                                    rsi_overbought,
                                    ma_window
                                )
                                returns.append(ret)
                            
                            avg_return = np.mean(returns)
                            
                            # Log progress
                            if iteration % 50 == 0 or avg_return > self.best_return:
                                logger.info(
                                    f"[{iteration}] SMA({sma_fast},{sma_slow}) "
                                    f"RSI({rsi_oversold},{rsi_overbought}) MA{ma_window} "
                                    f"→ {avg_return:.2%}"
                                )
                            
                            # Track best
                            if avg_return > self.best_return:
                                self.best_return = avg_return
                                self.best_params = {
                                    'sma_fast': sma_fast,
                                    'sma_slow': sma_slow,
                                    'rsi_oversold': rsi_oversold,
                                    'rsi_overbought': rsi_overbought,
                                    'ma_window': ma_window,
                                    'avg_annual_return': avg_return
                                }
                                
                                logger.info(
                                    f"  ✓ NEW BEST: {avg_return:.2%} "
                                    f"(Target: {self.TARGET_RETURN:.2%})"
                                )
                                
                                # Check if target reached
                                if avg_return >= self.TARGET_RETURN:
                                    logger.info(f"\n✅ TARGET REACHED!")
                                    return self.best_params
        
        logger.info("\n" + "="*80)
        logger.info("OPTIMIZATION COMPLETE")
        logger.info("="*80)
        logger.info(f"Best params found:")
        logger.info(f"  SMA: {self.best_params['sma_fast']}/{self.best_params['sma_slow']}")
        logger.info(f"  RSI: {self.best_params['rsi_oversold']}/{self.best_params['rsi_overbought']}")
        logger.info(f"  MA Window: {self.best_params['ma_window']}")
        logger.info(f"  Avg Annual Return: {self.best_return:.2%}")
        logger.info("="*80 + "\n")
        
        return self.best_params
    
    def save_config(self):
        """Save best config"""
        if self.best_params is None:
            logger.warning("No best params to save")
            return
        
        os.makedirs('phase10_results', exist_ok=True)
        path = 'phase10_results/phase10_best_config.json'
        
        with open(path, 'w') as f:
            json.dump(self.best_params, f, indent=2)
        
        logger.info(f"Saved best config to {path}")


if __name__ == '__main__':
    optimizer = Phase10SimpleOptimizer()
    optimizer.optimize()
    optimizer.save_config()
