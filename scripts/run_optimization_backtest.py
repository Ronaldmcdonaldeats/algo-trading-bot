#!/usr/bin/env python3
"""
Option A: Run backtest on 2024-2026 data to validate optimizations

Tests all 4 optimization phases on real market data
"""

import sys
import os
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trading_bot.backtest.engine import run_backtest
from trading_bot.configs import load_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_optimization_validation_backtest():
    """Run backtest to validate optimizations on 2024-2026 data"""
    
    # Configuration
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX']
    
    logger.info("=" * 70)
    logger.info("OPTION A: BACKTEST 2024-2026 DATA")
    logger.info("=" * 70)
    logger.info(f"Symbols: {', '.join(symbols)}")
    logger.info(f"Period: 2024-01-01 to 2026-01-27 (2+ years)")
    logger.info(f"Strategy: Ensemble with optimizations")
    logger.info(f"Capital: $100,000")
    logger.info("")
    
    try:
        # Run backtest with optimizations enabled
        logger.info("Running backtest with Phase 1-4 optimizations enabled...")
        logger.info("- Phase 1: Vectorized calculations + caching")
        logger.info("- Phase 2: Centralized parameters")
        logger.info("- Phase 3: Dynamic stops + volatility adjustment")
        logger.info("- Phase 4: Adaptive ML parameters")
        logger.info("")
        
        result = run_backtest(
            config_path='configs/default.yaml',
            symbols=symbols,
            period='2y',  # ~2 years to cover 2024-2026
            interval='1d',
            start_cash=100_000.0,
            commission_bps=1.0,  # Realistic 1 bp commission
            slippage_bps=0.5,    # Realistic 0.5 bp slippage
            min_fee=0.0,
            strategy_mode='ensemble',
            data_source='yahoo'  # Most reliable data source
        )
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("BACKTEST RESULTS (2024-2026)")
        logger.info("=" * 70)
        
        # Display key metrics
        metrics_display = f"""
PERFORMANCE METRICS:
  Total Return:        {result.total_return:>10.2%}
  Annual Return:       {result.annual_return:>10.2%}
  Sharpe Ratio:        {result.sharpe_ratio:>10.2f}
  Max Drawdown:        {result.max_drawdown:>10.2%}
  Win Rate:            {result.win_rate:>10.2%}
  Profit Factor:       {result.profit_factor:>10.2f}
  Calmar Ratio:        {result.calmar_ratio:>10.2f}

TRADE STATISTICS:
  Total Trades:        {result.total_trades:>10d}
  Winning Trades:      {result.num_winning_trades:>10d}
  Losing Trades:       {result.num_losing_trades:>10d}
  Avg Win:             {result.avg_win:>10.2%}
  Avg Loss:            {result.avg_loss:>10.2%}

PORTFOLIO:
  Final Equity:        ${result.final_equity:>10,.2f}
  Start Equity:        ${result.start_equity:>10,.2f}
  Ending Date:         {result.end_date}
"""
        logger.info(metrics_display)
        
        return result
        
    except Exception as e:
        logger.error(f"Backtest failed: {e}", exc_info=True)
        return None


if __name__ == '__main__':
    result = run_optimization_validation_backtest()
    
    if result:
        logger.info("✅ Backtest completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Backtest failed")
        sys.exit(1)
