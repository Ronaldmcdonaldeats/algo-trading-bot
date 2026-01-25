"""
Phase 10: Bayesian Optimization Loop
- Intelligently searches parameter space
- Target: Beat S&P 500 by 5% (6.1% annual return)
- Uses scikit-optimize for efficient parameter tuning
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, Tuple
from skopt import gp_minimize, space
from skopt.utils import use_named_args
import json
import os

from src.trading_bot.historical_data import fetch_stock_data
from src.trading_bot.phase10_optimizer_strategy import (
    Phase10Backtester, PhasePhase10Config
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase10Optimizer:
    """Bayesian optimizer for Phase 10 strategy"""
    
    TARGET_ANNUAL_RETURN = 0.061  # 6.1% (S&P 500 1.1% + 5%)
    STOCKS = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX',
        'ADBE', 'INTC', 'AMD', 'CSCO', 'QCOM', 'COST', 'AVGO'
    ]  # Use 15 stocks for faster optimization
    
    def __init__(self):
        self.best_config = None
        self.best_return = 0.0
        self.best_params = None
        self.iteration = 0
        self.results = []
    
    def load_data(self) -> Dict[str, np.ndarray]:
        """Load historical data for all stocks"""
        logger.info("Loading historical data for optimization...")
        data = {}
        
        for symbol in self.STOCKS:
            try:
                df = fetch_stock_data(symbol, start_date='2000-01-01', end_date='2025-01-25')
                if df is not None and len(df) > 100:
                    data[symbol] = df['Close'].values
                    logger.info(f"  {symbol}: {len(df)} days loaded")
            except Exception as e:
                logger.warning(f"  {symbol}: Failed to load - {e}")
        
        logger.info(f"Loaded data for {len(data)} stocks")
        return data
    
    def objective(self, params: Tuple) -> float:
        """
        Objective function for optimization
        Minimize negative average annual return
        """
        self.iteration += 1
        
        # Unpack parameters
        sma_fast, sma_slow, rsi_oversold, rsi_overbought, ma_window = params
        
        # Create config
        config = PhasePhase10Config(
            ma_window=int(ma_window),
            sma_fast=int(sma_fast),
            sma_slow=int(sma_slow),
            rsi_oversold=int(rsi_oversold),
            rsi_overbought=int(rsi_overbought),
            # Keep other params fixed
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            bb_window=20,
            bb_std_dev=2.0,
        )
        
        # Backtest on all stocks
        backtester = Phase10Backtester(config)
        returns = []
        
        for symbol, prices in self.data.items():
            if len(prices) < config.ma_window + 50:
                continue
            
            try:
                total_ret, annual_ret, max_dd, sharpe, trades = backtester.backtest(prices)
                returns.append(annual_ret)
            except Exception as e:
                logger.warning(f"  Backtest failed for {symbol}: {e}")
                continue
        
        if not returns:
            avg_return = 0.0
        else:
            avg_return = np.mean(returns)
        
        # Log iteration
        logger.info(
            f"[Iteration {self.iteration}] "
            f"SMA({sma_fast},{sma_slow}) RSI({rsi_oversold},{rsi_overbought}) MA{ma_window} "
            f"→ Avg Annual: {avg_return:.2%}"
        )
        
        # Track best
        if avg_return > self.best_return:
            self.best_return = avg_return
            self.best_params = {
                'sma_fast': int(sma_fast),
                'sma_slow': int(sma_slow),
                'rsi_oversold': int(rsi_oversold),
                'rsi_overbought': int(rsi_overbought),
                'ma_window': int(ma_window),
                'avg_annual_return': avg_return
            }
            logger.info(f"  ✓ NEW BEST: {avg_return:.2%} with {self.best_params}")
        
        # Check if target reached
        if avg_return >= self.TARGET_ANNUAL_RETURN:
            logger.info(f"✅ TARGET REACHED! {avg_return:.2%} >= {self.TARGET_ANNUAL_RETURN:.2%}")
            self.best_config = config
            return 0.0  # Stop optimization
        
        # Objective: minimize negative return
        return -avg_return
    
    def optimize(self, n_calls: int = 50):
        """Run Bayesian optimization"""
        logger.info(f"Starting Phase 10 Bayesian Optimization (target: {self.TARGET_ANNUAL_RETURN:.2%})")
        logger.info(f"Max iterations: {n_calls}")
        
        # Load data
        self.data = self.load_data()
        if not self.data:
            logger.error("No data loaded!")
            return None
        
        # Define parameter space
        param_space = [
            space.Integer(10, 30, name='sma_fast'),      # 10-30
            space.Integer(40, 100, name='sma_slow'),     # 40-100
            space.Integer(20, 35, name='rsi_oversold'),  # 20-35
            space.Integer(65, 80, name='rsi_overbought'),# 65-80
            space.Integer(100, 300, name='ma_window'),   # 100-300
        ]
        
        # Run optimization
        result = gp_minimize(
            self.objective,
            param_space,
            n_calls=n_calls,
            n_initial_points=10,
            acq_func='EI',  # Expected Improvement
            random_state=42,
        )
        
        logger.info("\n" + "="*80)
        logger.info("OPTIMIZATION COMPLETE")
        logger.info("="*80)
        logger.info(f"Best configuration found:")
        logger.info(f"  SMA Fast: {self.best_params['sma_fast']}")
        logger.info(f"  SMA Slow: {self.best_params['sma_slow']}")
        logger.info(f"  RSI Oversold: {self.best_params['rsi_oversold']}")
        logger.info(f"  RSI Overbought: {self.best_params['rsi_overbought']}")
        logger.info(f"  MA Window: {self.best_params['ma_window']}")
        logger.info(f"  Avg Annual Return: {self.best_return:.2%}")
        logger.info("="*80 + "\n")
        
        return self.best_params
    
    def save_best_config(self, output_path: str = 'phase10_best_config.json'):
        """Save best configuration found"""
        if self.best_params is None:
            logger.warning("No best config to save")
            return
        
        output_path = os.path.join(
            os.path.dirname(__file__),
            '../../phase10_results',
            output_path
        )
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(self.best_params, f, indent=2)
        
        logger.info(f"Saved best config to {output_path}")


if __name__ == '__main__':
    optimizer = Phase10Optimizer()
    best_params = optimizer.optimize(n_calls=40)  # 40 iterations
    
    if best_params:
        optimizer.save_best_config()
