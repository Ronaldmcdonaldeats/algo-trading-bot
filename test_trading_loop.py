#!/usr/bin/env python
"""Test script to verify trading loop execution"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

logger.info("=" * 60)
logger.info("Testing Trading Bot Paper Engine")
logger.info("=" * 60)

try:
    from trading_bot.engine.paper import PaperEngineConfig, run_paper_engine
    from trading_bot.data.providers import MockDataProvider
    
    logger.info("✓ Imports successful")
    
    # Create config
    config = PaperEngineConfig(
        config_path="configs/default.yaml",
        db_path="test_trading_bot.db",
        symbols=['AAPL', 'GOOGL', 'MSFT'],
        period="6mo",
        interval="1d",
        start_cash=100000.0,
        sleep_seconds=0,  # No sleep for testing
        iterations=5,  # Just 5 iterations for testing
        strategy_mode='ensemble',
        enable_learning=False,  # Disable learning for faster test
        tune_weekly=False,
    )
    
    logger.info("✓ PaperEngineConfig created")
    logger.info(f"  - Symbols: {config.symbols}")
    logger.info(f"  - Start cash: ${config.start_cash}")
    logger.info(f"  - Iterations: {config.iterations}")
    
    # Use mock data provider
    provider = MockDataProvider()
    logger.info("✓ MockDataProvider initialized")
    
    # Run the engine
    logger.info("\nStarting trading loop...")
    iteration_count = 0
    
    for update in run_paper_engine(cfg=config, provider=provider):
        iteration_count += 1
        logger.info(f"\n[Iteration {iteration_count}]")
        logger.info(f"  Timestamp: {update.ts}")
        logger.info(f"  Mode: {update.mode}")
        logger.info(f"  Signals: {update.signals}")
        logger.info(f"  Fills: {len(update.fills)} trades")
        if update.fills:
            for fill in update.fills:
                logger.info(f"    - {fill.symbol}: {fill.quantity} @ ${fill.price}")
        
        portfolio_value = update.portfolio.equity if update.portfolio else 0
        logger.info(f"  Portfolio Value: ${portfolio_value:.2f}")
        logger.info(f"  Sharpe Ratio: {update.sharpe_ratio:.4f}")
        logger.info(f"  Max Drawdown: {update.max_drawdown_pct:.2f}%")
        logger.info(f"  Win Rate: {update.win_rate:.2f}")
    
    logger.info(f"\n✓ Trading loop completed {iteration_count} iterations successfully!")
    
except Exception as e:
    logger.error(f"✗ Error: {e}", exc_info=True)
    sys.exit(1)
