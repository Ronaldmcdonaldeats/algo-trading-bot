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
from trading_bot.paper.runner import run_paper_trading

logger = logging.getLogger(__name__)


def auto_initialize_learning() -> StrategyLearner:
    """Initialize the strategy learner and load cached strategies."""
    learner = StrategyLearner()
    
    # Load cached strategies if they exist
    cached_count = len(learner.learned_strategies)
    cached_hybrids = len(learner.hybrid_strategies)
    
    if cached_count > 0:
        logger.info(f"✓ Loaded {cached_count} learned strategies from cache")
    if cached_hybrids > 0:
        logger.info(f"✓ Loaded {cached_hybrids} hybrid strategies from cache")
    
    if cached_count == 0:
        logger.info("ℹ No cached strategies found. System will learn from paper trading results.")
    
    return learner


def auto_start_paper_trading(
    *,
    symbols: list[str] | None = None,
    iterations: int = 0,
    auto_select: bool = True,
    auto_learn: bool = True,
    config_path: str = "configs/default.yaml",
    start_cash: float = 100_000.0,
    db_path: str = "data/trades.sqlite",
    period: str = "60d",
    interval: str = "1d",
    sleep_seconds: float = 30.0,
    ui: bool = True,
    alpaca_key: str | None = None,
    alpaca_secret: str | None = None,
) -> int:
    """
    Automatically start paper trading with strategy learning integration.
    
    Args:
        symbols: List of stock symbols to trade (if auto_select=False)
        iterations: Number of trading iterations (0 = infinite loop)
        auto_select: Use smart stock selection instead of manual symbols
        auto_learn: Learn from trading results automatically
        config_path: Path to trading config file
        start_cash: Initial portfolio cash
        db_path: Path to trades database
        period: Historical data period
        interval: Trading interval
        sleep_seconds: Seconds between iterations
        ui: Enable terminal UI
        alpaca_key: Alpaca API key
        alpaca_secret: Alpaca API secret
    
    Returns:
        Exit code (0 = success, 1 = error)
    """
    
    # Load environment variables if provided
    if alpaca_key:
        os.environ["APCA_API_KEY_ID"] = alpaca_key
    if alpaca_secret:
        os.environ["APCA_API_SECRET_KEY"] = alpaca_secret
    
    # Verify Alpaca credentials
    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")
    
    if not api_key or not api_secret:
        logger.error("Alpaca API credentials not found")
        logger.error("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY environment variables")
        return 1
    
    logger.info("=" * 70)
    logger.info("AUTO-START: AI-Powered Trading Bot with Strategy Learning")
    logger.info("=" * 70)
    
    # Initialize strategy learning
    if auto_learn:
        logger.info("\n[LEARNING] Initializing strategy learning system...")
        learner = auto_initialize_learning()
        logger.info(f"[LEARNING] Ready to learn from trading results")
    else:
        learner = None
    
    # Select stocks
    if auto_select:
        logger.info("\n[SELECTION] Smart stock selection enabled")
        from trading_bot.cli import _get_smart_selected_symbols
        symbols = _get_smart_selected_symbols(
            top_n=500,
            select_top=50,
            min_score=60,
            use_cached=True,
        )
        logger.info(f"[SELECTION] Selected {len(symbols)} stocks for trading")
    elif symbols:
        logger.info(f"\n[SELECTION] Using manual symbols: {', '.join(symbols)}")
    else:
        logger.info("\n[SELECTION] Using default symbol: SPY")
        symbols = ["SPY"]
    
    # Prepare trading config
    logger.info("\n[CONFIG] Trading Configuration:")
    logger.info(f"  • Initial Cash: ${start_cash:,.2f}")
    logger.info(f"  • Symbols: {len(symbols)} stocks")
    logger.info(f"  • Period: {period}")
    logger.info(f"  • Interval: {interval}")
    logger.info(f"  • Database: {db_path}")
    logger.info(f"  • UI Enabled: {ui}")
    logger.info(f"  • Iterations: {'Infinite loop' if iterations == 0 else f'{iterations} iterations'}")
    
    if auto_learn:
        logger.info(f"  • Auto-Learning: YES")
    
    logger.info("\n" + "=" * 70)
    logger.info("Starting paper trading... Press Ctrl+C to stop")
    logger.info("=" * 70 + "\n")
    
    try:
        # Run paper trading
        result = run_paper_trading(
            config_path=config_path,
            symbols=symbols,
            period=period,
            interval=interval,
            start_cash=start_cash,
            db_path=db_path,
            sleep_seconds=sleep_seconds,
            iterations=iterations,
            ui=ui,
            commission_bps=0.0,
            slippage_bps=0.0,
            min_fee=0.0,
            ignore_market_hours=False,
            memory_mode=False,
        )
        
        # After trading completes, learn from results if enabled
        if auto_learn and learner:
            logger.info("\n" + "=" * 70)
            logger.info("[LEARNING] Learning from trading results...")
            logger.info("=" * 70)
            
            try:
                # Load trade history and learn from it
                from trading_bot.db.trade_log import TradeLog
                trade_log = TradeLog(db_path=db_path)
                trades = trade_log.get_recent_trades(limit=100)
                
                if trades:
                    logger.info(f"[LEARNING] Found {len(trades)} trades to learn from")
                    
                    # Learn from performance history
                    learner.learn_from_performance_history(
                        strategy_name="auto_trading_session",
                        trades=trades,
                        initial_params={
                            "stop_loss_pct": 2.0,
                            "take_profit_pct": 5.0,
                            "rsi_threshold": 30,
                        }
                    )
                    
                    # Build hybrid from top strategies if we have enough
                    learned_strats = learner.get_learned_strategies()
                    if len(learned_strats) >= 2:
                        top_strats = learner.get_top_strategies(top_n=2)
                        if len(top_strats) >= 2:
                            hybrid = learner.build_hybrid_strategy(
                                name=f"hybrid_auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                                base_strategies=[s.name for s in top_strats[:2]],
                                strategy_params=learner.learned_strategies,
                                weight_by="sharpe_ratio"
                            )
                            logger.info(f"[LEARNING] Built new hybrid strategy: {hybrid.name}")
                    
                    # Save learned strategies
                    learner.save()
                    logger.info("[LEARNING] ✓ Saved learned strategies to disk")
                    
                    # Show what was learned
                    logger.info("\n[LEARNING] Learned Strategies Summary:")
                    for strat_name, strat_params in learner.learned_strategies.items():
                        logger.info(f"  • {strat_name}")
                        logger.info(f"    - Sharpe: {strat_params.performance.get('sharpe_ratio', 0):.2f}")
                        logger.info(f"    - Win Rate: {strat_params.performance.get('win_rate', 0):.1%}")
                        logger.info(f"    - Samples: {strat_params.samples}")
                        logger.info(f"    - Confidence: {strat_params.confidence:.1%}")
                else:
                    logger.info("[LEARNING] No trades found to learn from")
            except Exception as e:
                logger.error(f"[LEARNING] Failed to learn from results: {e}")
        
        logger.info("\n" + "=" * 70)
        logger.info("Paper trading completed successfully")
        logger.info("=" * 70)
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("\n" + "!" * 70)
        logger.info("Paper trading stopped by user (Ctrl+C)")
        logger.info("!" * 70)
        
        # Still try to learn from partial results
        if auto_learn and learner:
            try:
                from trading_bot.db.trade_log import TradeLog
                trade_log = TradeLog(db_path=db_path)
                trades = trade_log.get_recent_trades(limit=50)
                
                if trades:
                    learner.learn_from_performance_history(
                        strategy_name=f"auto_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        trades=trades,
                        initial_params={}
                    )
                    learner.save()
                    logger.info("[LEARNING] Saved partial learning from interrupted session")
            except Exception as e:
                logger.debug(f"[LEARNING] Could not save partial learning: {e}")
        
        return 0
    except Exception as e:
        logger.error(f"\n[ERROR] Paper trading failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def auto_start_with_defaults() -> int:
    """
    Start auto paper trading with smart defaults.
    This is the easiest entry point for users.
    """
    return auto_start_paper_trading(
        symbols=None,
        iterations=0,  # Infinite loop
        auto_select=True,  # Smart stock selection
        auto_learn=True,  # Learn from results
        config_path="configs/default.yaml",
        start_cash=100_000.0,
        db_path="data/trades.sqlite",
        period="60d",
        interval="1d",
        sleep_seconds=30.0,
        ui=True,
    )


if __name__ == "__main__":
    import sys
    sys.exit(auto_start_with_defaults())
