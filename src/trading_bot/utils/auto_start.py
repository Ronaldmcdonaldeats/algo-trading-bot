"""
Auto-start module for automatic learning and trading.
Handles initialization of strategy learning and automatic paper trading.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

from trading_bot.learn.strategy_learner import StrategyLearner

logger = logging.getLogger(__name__)


def auto_initialize_learning() -> StrategyLearner:
    """Initialize the strategy learner and load cached strategies."""
    logger.info("Initializing strategy learner...")
    learner = StrategyLearner()
    
    # Load cached strategies if available
    cache_dir = Path("/app/.cache/strategies")
    if cache_dir.exists():
        logger.info(f"Loading cached strategies from {cache_dir}")
        try:
            learner.load_cache()
        except Exception as e:
            logger.warning(f"Could not load cached strategies: {e}")
    
    return learner


def auto_start_paper_trading(
    symbols: list[str] | None = None,
    iterations: int = 1000,
    auto_select: bool = True,
    auto_learn: bool = True,
    config_path: str | None = None,
    start_cash: float = 100000.0,
    db_path: str | None = None,
    period: str = "1y",
    interval: str = "1d",
    ui: bool = False,
    alpaca_key: str | None = None,
    alpaca_secret: str | None = None,
):
    """Start automatic paper trading with learning."""
    logger.info("=" * 60)
    logger.info("STARTING AUTOMATIC PAPER TRADING WITH LEARNING")
    logger.info(f"Start Time: {datetime.now().isoformat()}")
    logger.info(f"Symbols: {symbols or 'Auto-selected'}")
    logger.info(f"Start Cash: ${start_cash:,.2f}")
    logger.info(f"Iterations: {iterations}")
    logger.info("=" * 60)
    
    # Initialize learning system
    learner = auto_initialize_learning()
    logger.info("Strategy learner initialized successfully")
    
    # Determine configuration path
    if config_path is None:
        config_path = os.getenv("TRADING_BOT_CONFIG", "configs/default.yaml")
    
    if db_path is None:
        db_path = os.getenv("TRADING_BOT_DB", "data/trades.sqlite")
    
    if symbols is None:
        # Let the live runner auto-select best symbols
        symbols = None  # Will be expanded to top 10 S&P 500 stocks in live runner

    
    # Check if Alpaca credentials are available
    use_alpaca = False
    if alpaca_key or alpaca_secret:
        use_alpaca = True
        logger.info("Alpaca credentials detected - using Alpaca paper trading")
    elif os.getenv("APCA_API_KEY_ID") and os.getenv("APCA_API_SECRET_KEY"):
        use_alpaca = True
        logger.info("Alpaca credentials found in environment - using Alpaca paper trading")
    else:
        logger.info("No Alpaca credentials - using local paper trading")
    
    # Start appropriate trading runner
    if use_alpaca:
        from trading_bot.live.runner import run_live_paper_trading
        logger.info("Starting Alpaca paper trading runner...")
        run_live_paper_trading(
            config_path=config_path,
            symbols=symbols,
            period=period,
            interval=interval,
            start_cash=start_cash,
            db_path=db_path,
            iterations=iterations,
            alpaca_key=alpaca_key,
            alpaca_secret=alpaca_secret,
            ui=ui
        )
    else:
        from trading_bot.paper.runner import run_paper_trading
        logger.info("Starting local paper trading runner...")
        run_paper_trading(
            config_path=config_path,
            symbols=symbols,
            period=period,
            interval=interval,
            start_cash=start_cash,
            db_path=db_path,
            iterations=iterations,
            ui=ui
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    auto_start_paper_trading()
