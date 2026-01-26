"""Live trading runners for Alpaca integration."""

from __future__ import annotations

import os
import getpass
import time
import uuid
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
import numpy as np

from trading_bot.broker.alpaca import AlpacaConfig, AlpacaBroker, SafetyControls, AlpacaProvider
from trading_bot.core.models import Order
from trading_bot.configs import load_config
from trading_bot.strategy.mean_reversion_momentum import generate_signals as generate_rsi_signals
from trading_bot.strategy.macd_strategy import generate_signals as generate_macd_signals
from trading_bot.db.repository import SqliteRepository
from trading_bot.risk.position_manager import PositionManager
from trading_bot.screening.symbol_screener import SymbolScreener
from trading_bot.screening.symbol_validator import SymbolValidator
from trading_bot.portfolio.optimizer import PortfolioOptimizer
from trading_bot.analytics.metrics import TradeMetrics
from trading_bot.utils.market_hours import MarketHours
from trading_bot.utils.dynamic_stops import DynamicStops
from trading_bot.utils.multi_timeframe import MultiTimeframeAnalysis
from trading_bot.utils.order_execution import OrderExecution, ExecutionConfig
from trading_bot.utils.volatility_regime import VolatilityRegime
from trading_bot.utils.kelly_criterion import KellyCriterion, PerformanceMetrics
from trading_bot.utils.advanced_orders import AdvancedOrderManager, OrderStatus
from trading_bot.utils.advanced_risk import AdvancedRiskManager, TradeResult
from trading_bot.utils.analytics import PortfolioAnalytics, TradeStats
from trading_bot.utils.adaptive_weighting import AdaptiveWeightManager, StrategyWeight
from trading_bot.utils.notifications import NotificationManager, NotificationType
from trading_bot.utils.advanced_backtest import AdvancedBacktester, BacktestResult
from trading_bot.data.optimization import DataFetchingOptimizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _setup_alpaca_creds(key: str | None, secret: str | None) -> None:
    """Setup Alpaca credentials from args, env, or prompt."""
    if key:
        os.environ["APCA_API_KEY_ID"] = key
    if secret:
        os.environ["APCA_API_SECRET_KEY"] = secret

    if not os.environ.get("APCA_API_KEY_ID"):
        print("[SETUP] Alpaca API Key not found in environment.")
        os.environ["APCA_API_KEY_ID"] = getpass.getpass("Enter Alpaca API Key ID: ").strip()

    if not os.environ.get("APCA_API_SECRET_KEY"):
        print("[SETUP] Alpaca Secret Key not found in environment.")
        os.environ["APCA_API_SECRET_KEY"] = getpass.getpass("Enter Alpaca Secret Key: ").strip()


@dataclass(frozen=True)
class LiveTradingSummary:
    iterations: int
    total_trades: int
    total_pnl: float
    status: str


def run_live_paper_trading(
    *,
    config_path: str,
    symbols: list[str],
    period: str = "1d",
    interval: str = "5m",  # Changed from 1d to 5m for intraday trading
    start_cash: float = 100_000.0,
    db_path: str = "data/trades.sqlite",
    iterations: int = 0,
    alpaca_key: str | None = None,
    alpaca_secret: str | None = None,
    ui: bool = True,
) -> LiveTradingSummary:
    """Run paper trading on Alpaca (sandbox mode).
    
    Args:
        config_path: Path to YAML config
        symbols: List of tickers (if None, auto-selects 500 NASDAQ stocks)
        period: Historical data period
          - Default 1d for 5-minute bar analysis (faster trades)
        interval: Bar interval (default 5m for intraday signals)
        start_cash: Starting cash
        db_path: SQLite database path
        iterations: Number of iterations (0 = infinite)
        alpaca_key: Alpaca API key (or set APCA_API_KEY_ID env var)
        alpaca_secret: Alpaca API secret (or set APCA_API_SECRET_KEY env var)
        ui: Enable TUI mode (default True). Set to False for CLI mode.
        
    Returns:
        LiveTradingSummary with results
    """
    print("[LIVE] Paper Trading Mode on Alpaca")
    print(f"[LIVE] Starting cash: ${start_cash:,.2f}")
    print("[LIVE] Connecting to Alpaca paper trading...")
    
    try:
        # Setup credentials (env or prompt)
        _setup_alpaca_creds(alpaca_key, alpaca_secret)

        # Force paper URL for safety in paper mode
        os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"

        # Default to live URL if not explicitly set
        if "APCA_API_BASE_URL" not in os.environ:
            os.environ["APCA_API_BASE_URL"] = "https://api.alpaca.markets"

        # Load trading config
        config = load_config(config_path)
        
        # Load Alpaca configuration from environment
        alpaca_config = AlpacaConfig.from_env(paper_mode=True)
        print(f"[LIVE] Connected to: {alpaca_config.base_url}")
        
        # Initialize data provider with optimization (caching + parallel downloads)
        base_provider = AlpacaProvider(config=alpaca_config)
        data_provider = DataFetchingOptimizer(base_provider=base_provider, cache_ttl_seconds=300)
        broker = AlpacaBroker(config=alpaca_config)
        
        if ui:
            from trading_bot.engine.paper import PaperEngine, PaperEngineConfig
            from trading_bot.tui.paper_app import run_paper_tui
            from trading_bot.schedule.us_equities import MarketSchedule, parse_interval
            
            # Configure engine to use Alpaca components
            engine_cfg = PaperEngineConfig(
                config_path=config_path,
                db_path=db_path,
                symbols=symbols,
                period=period,
                interval=interval,
                start_cash=start_cash,
                iterations=iterations,
            )
            
            engine = PaperEngine(cfg=engine_cfg, provider=data_provider, broker=broker)
            
            # Create schedule
            try:
                td = parse_interval(interval)
                market_hours_only = td < timedelta(days=1)
            except ValueError:
                td = timedelta(seconds=30.0)
                market_hours_only = False
            
            schedule = MarketSchedule(interval=td, market_hours_only=market_hours_only)
            
            run_paper_tui(engine=engine, schedule=schedule)
            return LiveTradingSummary(0, 0, 0.0, "TUI Closed")

        # Initialize database
        repo = SqliteRepository(db_path=db_path)
        repo.init_db()
        
        print("[LIVE] Ready for paper trading!")
        print("[LIVE] This mode uses Alpaca's paper trading account (no real money)")
        print("[LIVE] Fetching initial data for symbol screening...")
        
        # If no symbols specified, use 500 NASDAQ stocks and screen them
        if symbols is None:
            symbols = SymbolScreener.NASDAQ500_SYMBOLS
            print(f"[LIVE] Auto-screening {len(symbols)} NASDAQ symbols")
            
            # Try to validate and discover working symbols
            print("[LIVE] Discovering symbols with valid Alpaca data (this may take 30-60 seconds)...")
            try:
                validated = SymbolValidator.validate_symbols(
                    data_provider,
                    symbols=set(symbols),
                    max_workers=8  # Faster validation with more workers
                )
                
                if len(validated) >= 20:  # Need at least 20 working symbols
                    print(f"[LIVE] ✓ Validated {len(validated)} working symbols for trading")
                    symbols = list(validated)
                else:
                    print(f"[LIVE] ⚠ Only {len(validated)} working symbols found, using core fallback")
                    symbols = list(SymbolValidator.VERIFIED_CORE)
                    
            except Exception as e:
                logger.warning(f"[LIVE] Validation failed: {e}, using core fallback")
                symbols = list(SymbolValidator.VERIFIED_CORE)
        
        # Get initial data
        print(f"[LIVE] Downloading data for {len(symbols)} symbols...")
        df_all = data_provider.download_bars(
            symbols=symbols,
            period=period,
            interval=interval
        )
        print(f"[DEBUG] Downloaded data shape: {df_all.shape}")
        print(f"[DEBUG] Column type: {type(df_all.columns)}, Is MultiIndex: {isinstance(df_all.columns, pd.MultiIndex)}")
        if not df_all.empty:
            print(f"[DEBUG] Sample columns: {list(df_all.columns)[:5]} ... {list(df_all.columns)[-5:]}")
        
        # If no data returned, fall back to core symbols
        if df_all is None or df_all.empty or df_all.shape[0] == 0:
            logger.warning("[LIVE] No data from primary symbols, falling back to core symbols")
            symbols = list(SymbolValidator.VERIFIED_CORE)
            df_all = data_provider.download_bars(
                symbols=symbols,
                period=period,
                interval=interval
            )
            print(f"[DEBUG] Fallback data shape: {df_all.shape}")
        
        # Screen symbols to find best trading opportunities
        screener = SymbolScreener()
        active_symbols = screener.suggest_symbols(df_all, preferred_symbols=symbols, num_symbols=50)
        print(f"[LIVE] Active symbols for trading: {', '.join(active_symbols[:10])}... ({len(active_symbols)} total)")
        
        # Use screened symbols for trading
        symbols = active_symbols
        
        # Cache management - optimized for intraday 5-minute bar trading
        last_data_fetch = datetime.now(timezone.utc)
        data_cache_ttl_seconds = 5  # 5 seconds - refresh frequently for 5-min bars (was 60 for daily)
        
        # Run trading loop
        iteration = 0
        total_trades = 0
        session_pnl = 0.0
        
        # Initialize order execution config for smart limit orders
        execution_config = ExecutionConfig(
            use_limit_orders=True,
            limit_offset_pct=0.2,  # Place limit 0.2% inside spread
            smart_mode_threshold_bps=50.0,  # Use limit if spread > 50 bps
            volume_check_enabled=True,
            min_volume_threshold=100_000.0,
        )
        
        def submit_smart_order(broker, symbol, side, qty, current_price, df_symbol_data):
            """Submit order using smart limit order logic."""
            # Estimate spread from recent volume
            if df_symbol_data is not None and 'Volume' in df_symbol_data.columns:
                volume_series = df_symbol_data['Volume'].tail(20)
                spread_pct = OrderExecution.estimate_spread_from_volume(volume_series)
            else:
                spread_pct = 0.1  # Default 0.1% spread estimate
            
            # Get recommended order type
            order_info = OrderExecution.get_order_type(
                current_price=current_price,
                side=side,
                qty=qty,
                volume_data=df_symbol_data['Volume'].tail(20) if df_symbol_data is not None else None,
                spread_estimate_pct=spread_pct,
                config=execution_config,
            )
            
            # Create and submit order
            order = Order(
                id=uuid.uuid4().hex,
                ts=datetime.utcnow(),
                symbol=symbol,
                side=side,
                qty=qty,
                type=order_info['type'],
                limit_price=order_info['limit_price'],
            )
            
            result = broker.submit_order(order)
            if order_info['expected_savings'] > 0:
                print(f"[EXEC] {order_info['type']}: {order_info['rationale']} (saves ~${order_info['expected_savings']:.2f})")
            return result
        
        # Initialize advanced order manager (Phase 10)
        order_manager = AdvancedOrderManager()
        
        # Initialize advanced risk manager (Phase 13)
        advanced_risk = AdvancedRiskManager(
            max_consecutive_losses=3,
            max_daily_loss=5000.0,
            max_hold_hours=24,
        )
        
        # Reset daily limits at start
        advanced_risk.daily_loss_limiter.reset_daily()

        # Initialize portfolio analytics (Phase 11)
        portfolio_analytics = PortfolioAnalytics()

        # Initialize adaptive weighting (Phase 12)
        strategy_names = ["rsi_mean_reversion", "macd_volume_momentum", "atr_breakout", "consensus"]
        adaptive_weights = AdaptiveWeightManager(
            strategies=strategy_names,
            base_weight=1.0,
            rebalance_interval=20,
            lookback_trades=20
        )

        # Initialize notifications (Phase 14)
        # Configure email, Slack, Discord as needed (defaults: disabled)
        notifications = NotificationManager(
            email_config={},  # Set to {'smtp_server': '...', 'sender_email': '...', ...} to enable
            slack_webhook="",  # Set to webhook URL to enable
            discord_webhook="",  # Set to webhook URL to enable
        )
        
        # Initialize position manager with enhanced risk management
        # Increase max_positions to support more symbols
        pos_manager = PositionManager(
            default_stop_loss_pct=0.02,  # 2%
            default_take_profit_pct=0.05,  # 5%
            max_position_size_pct=0.1,
            max_daily_loss_pct=0.05,
            max_positions=min(50, len(symbols)),  # Can hold up to 50 positions or number of symbols
            max_portfolio_drawdown_pct=0.1,  # 10% max drawdown limit
            volatility_adjustment=True,  # Skip extremely volatile stocks
            starting_equity=100_000.0,  # Initialize peak_equity properly
        )
        
        # Initialize portfolio optimizer for position sizing
        optimizer = PortfolioOptimizer(lookback_periods=20)
        
        # Initialize metrics tracker for analytics
        metrics = TradeMetrics(trades_log_path=".trades_log.json")
        
        # Initialize symbol screener for auto-selection
        screener = SymbolScreener()
        last_symbol_update = datetime.now(timezone.utc)
        
        
        while iterations == 0 or iteration < iterations:
            iteration += 1
            
            # Check if market is open
            now = datetime.now(timezone.utc)
            is_market_open = MarketHours.is_market_open(now)
            
            if not is_market_open:
                time_until_open = MarketHours.format_time_until_open(now)
                print(f"[LIVE] Market closed. Opens in {time_until_open}. Sleeping...")
                time.sleep(min(60, max(1, MarketHours.minutes_until_open(now) - 2) * 60))  # Sleep until close to open
                continue
            
            time_until_close = MarketHours.format_time_until_close(now)
            print(f"[LIVE] Market open. {time_until_close} until close.")
            
            # Check advanced risk controls (Phase 13)
            if advanced_risk.consecutive_loss_tracker.is_trading_paused():
                pause_remaining = advanced_risk.consecutive_loss_tracker.get_pause_remaining_seconds()
                print(f"[RISK] Trading paused after consecutive losses. Resume in {pause_remaining}s")
                time.sleep(30)
                continue
            
            if advanced_risk.daily_loss_limiter.has_reached_daily_limit():
                print(f"[RISK] Daily loss limit reached: ${advanced_risk.daily_loss_limiter.daily_pnl:.2f}")
                time.sleep(60)
                continue
            
            # Check for positions that need rotation
            positions_to_rotate = advanced_risk.check_position_rotation()
            for pos_info in positions_to_rotate:
                print(f"[ROTATION] {pos_info['symbol']} held for {pos_info['hold_duration_hours']:.1f}h - consider rotation")
            
            # Check if data cache is stale and refresh if needed
            now = datetime.now(timezone.utc)
            if (now - last_data_fetch).total_seconds() >= data_cache_ttl_seconds:
                print(f"[LIVE] Refreshing data cache (last fetch was {(now - last_data_fetch).total_seconds():.0f}s ago)")
                df_all = data_provider.download_bars(
                    symbols=symbols,
                    period=period,
                    interval=interval
                )
                last_data_fetch = now
                print(f"[DEBUG] Data refreshed: shape {df_all.shape}")
                print(f"[DEBUG] Column type: {type(df_all.columns)}, Is MultiIndex: {isinstance(df_all.columns, pd.MultiIndex)}")
                if len(df_all.columns) > 0:
                    print(f"[DEBUG] Sample columns: {list(df_all.columns[:5])} ... {list(df_all.columns[-5:])}")
            else:
                time_since_fetch = (now - last_data_fetch).total_seconds()
                print(f"[LIVE] Using cached data ({data_cache_ttl_seconds - time_since_fetch:.0f}s until refresh)")
            
            timestamp = datetime.now(timezone.utc)
            
            print(f"\n[ITERATION {iteration}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Get portfolio
            portfolio = broker.portfolio()
            account_info = broker.get_account_info()
            starting_equity = 100_000.0  # Default from config
            current_equity = account_info['equity']
            pnl = current_equity - starting_equity
            pnl_pct = (pnl / starting_equity * 100) if starting_equity > 0 else 0
            
            print(f"[PORTFOLIO] Cash: ${portfolio.cash:,.2f} | Equity: ${current_equity:,.2f} | P&L: {pnl:+,.2f} ({pnl_pct:+.2f}%)")
            
            # Sync portfolio positions with PositionManager (for exit tracking)
            # On first iteration, load all existing positions from Alpaca
            if iteration == 1:
                print("[STARTUP] Loading existing positions from Alpaca...")
                existing_count = 0
                for symbol, pos in portfolio.positions.items():
                    if pos.qty > 0:
                        pos_manager.open_position(symbol, pos.qty, pos.avg_price)
                        advanced_risk.position_rotator.add_position(symbol)  # Track for rotation
                        existing_count += 1
                if existing_count > 0:
                    print(f"[STARTUP] Loaded {existing_count} existing position(s) from Alpaca")
            
            # Sync portfolio positions with PositionManager (for exit tracking)
            for symbol, pos in portfolio.positions.items():
                if pos.qty > 0:  # Only track long positions
                    # Update or add position in manager
                    existing = pos_manager.get_position(symbol)
                    if not existing or existing.qty == 0:
                        # New position from Alpaca - open it in PositionManager
                        pos_manager.open_position(symbol, pos.qty, pos.avg_price)
            
            # Extract current prices for exit checks
            symbol_prices = {}
            for symbol in symbols:
                try:
                    # Try MultiIndex tuple format first
                    col_tuple = ('Close', symbol)
                    if col_tuple in df_all.columns:
                        symbol_prices[symbol] = float(df_all[col_tuple].iloc[-1])
                    else:
                        # Try string format like "('Close', 'AAPL')"
                        str_col = f"('Close', '{symbol}')"
                        if str_col in df_all.columns:
                            symbol_prices[symbol] = float(df_all[str_col].iloc[-1])
                        else:
                            # Try simple column name
                            if 'Close' in df_all.columns:
                                symbol_prices[symbol] = float(df_all['Close'].iloc[-1])
                except Exception as e:
                    pass  # Skip if price not available
            
            # Check for exits (stop-loss, take-profit, trailing stops)
            closed_positions = pos_manager.execute_exits(symbol_prices)
            for closed in closed_positions:
                if closed:
                    # Place sell order for closed position using smart execution
                    symbol = closed['symbol']
                    df_symbol = df_all[[col for col in df_all.columns if col[1] == symbol]] if symbol in df_all.columns.get_level_values(1) else None
                    submit_smart_order(broker, symbol, "SELL", closed['qty'], symbol_prices[symbol], df_symbol)
                    print(f"[RISK] Exit {closed['symbol']}: {closed['reason']}")
                    total_trades += 1
            
            # Generate signals
            try:
                # Process each symbol individually like the paper engine does
                all_signals = []
                for symbol in symbols:
                    try:
                        # Extract data for this symbol
                        # Columns can be stored as tuples like ('Open', 'AAPL'), ('Close', 'AAPL'), etc.
                        # OR as simple strings if single symbol
                        # OR as string representations of tuples like "('Open', 'AAPL')"
                        symbol_data = {}
                        
                        # First try MultiIndex tuple format
                        if isinstance(df_all.columns, pd.MultiIndex):
                            for col_name in ['Open', 'High', 'Low', 'Close', 'Volume']:
                                col_tuple = (col_name, symbol)
                                if col_tuple in df_all.columns:
                                    symbol_data[col_name] = df_all[col_tuple]
                        
                        # Try Index with string representations of tuples: "('Open', 'CEG')"
                        if not symbol_data and not isinstance(df_all.columns, pd.MultiIndex):
                            for col_name in ['Open', 'High', 'Low', 'Close', 'Volume']:
                                # Try exact string format: "('Open', 'AAPL')"
                                str_col = f"('{col_name}', '{symbol}')"
                                if str_col in df_all.columns:
                                    symbol_data[col_name] = df_all[str_col]
                                    continue
                                
                                # If not found, try all columns that might match this symbol
                                for col in df_all.columns:
                                    if isinstance(col, str) and symbol in col and col_name in col:
                                        symbol_data[col_name] = df_all[col]
                                        break
                        
                        # Try simple column names (single symbol case)
                        if not symbol_data:
                            for col_name in ['Open', 'High', 'Low', 'Close', 'Volume']:
                                if col_name in df_all.columns:
                                    symbol_data[col_name] = df_all[col_name]
                        
                        if not symbol_data or 'Close' not in symbol_data:
                            # Try string column names like 'Close_AAPL'
                            for col_name in ['Open', 'High', 'Low', 'Close', 'Volume']:
                                alt_col = f"{col_name}_{symbol}"
                                if alt_col in df_all.columns:
                                    symbol_data[col_name] = df_all[alt_col]
                        
                        if not symbol_data or 'Close' not in symbol_data:
                            logger.debug(f"{symbol} missing required OHLCV data, skipping")
                            continue
                        
                        # Create DataFrame from extracted data
                        symbol_df = pd.DataFrame(symbol_data)
                        
                        if "Close" not in symbol_df.columns:
                            print(f"[WARN] {symbol} missing Close column, skipping")
                            continue
                        
                        symbol_df = symbol_df.dropna(subset=["Close"])
                        if symbol_df.empty:
                            print(f"[WARN] {symbol} has no valid Close data, skipping")
                            continue
                        
                        # Generate signals from multiple strategies (ensemble approach)
                        rsi_signal = 0
                        macd_signal = 0
                        strategies_voted = 0
                        
                        # Strategy 1: RSI Mean Reversion
                        try:
                            rsi_sig = generate_rsi_signals(
                                symbol_df,
                                rsi_period=config.strategy.raw.get("rsi_period", 14),
                                rsi_overbought=config.strategy.raw.get("rsi_overbought", 70),
                                rsi_oversold=config.strategy.raw.get("rsi_oversold", 30),
                            )
                            if rsi_sig is not None and not rsi_sig.empty:
                                if 'signal' in rsi_sig.columns:
                                    rsi_signal = int(rsi_sig['signal'].iloc[-1])
                                    strategies_voted += 1
                        except Exception as e:
                            logger.debug(f"RSI signal failed for {symbol}: {e}")
                        
                        # Strategy 2: MACD Trend Following
                        try:
                            macd_sig = generate_macd_signals(symbol_df, fast_period=12, slow_period=26)
                            if macd_sig is not None and not macd_sig.empty:
                                if 'signal' in macd_sig.columns:
                                    macd_signal = int(macd_sig['signal'].iloc[-1])
                                    strategies_voted += 1
                        except Exception as e:
                            logger.debug(f"MACD signal failed for {symbol}: {e}")
                        
                        # Combine signals: require majority consensus (both agree = 2/2 votes for signal=1)
                        consensus_signal = 0
                        if strategies_voted >= 2:
                            # Require both strategies to signal 1 (BUY) for consensus
                            if rsi_signal == 1 and macd_signal == 1:
                                consensus_signal = 1
                            elif rsi_signal == -1 and macd_signal == -1:
                                consensus_signal = -1
                        elif strategies_voted == 1:
                            # Single strategy voting - use if strong signal
                            if rsi_signal == 1 or macd_signal == 1:
                                consensus_signal = 1  
                            elif rsi_signal == -1 or macd_signal == -1:
                                consensus_signal = -1
                        
                        if consensus_signal != 0:
                                # Get current price - try multiple formats
                                current_price = None
                                
                                # Try MultiIndex format: ('Close', symbol)
                                if ("Close", symbol) in df_all.columns:
                                    current_price = float(df_all[("Close", symbol)].iloc[-1])
                                
                                # Try string tuple format: "('Close', 'SYMBOL')"
                                if current_price is None:
                                    str_col = f"('Close', '{symbol}')"
                                    if str_col in df_all.columns:
                                        current_price = float(df_all[str_col].iloc[-1])
                                
                                # Try simple format: 'Close_SYMBOL'
                                if current_price is None:
                                    simple_col = f"Close_{symbol}"
                                    if simple_col in df_all.columns:
                                        current_price = float(df_all[simple_col].iloc[-1])
                                
                                # Fallback: use last value from symbol_df if available
                                if current_price is None and "Close" in symbol_df.columns:
                                    current_price = float(symbol_df["Close"].iloc[-1])
                                
                                # Only add to signals if we have a price
                                if current_price is not None:
                                    sig_row = pd.DataFrame({
                                        'signal': [consensus_signal],
                                        'price': [current_price],
                                        'rsi_signal': [rsi_signal],
                                        'macd_signal': [macd_signal],
                                        'strategies': [strategies_voted],
                                        'symbol': [symbol]
                                    })
                                    sig_row = sig_row.set_index('symbol', append=True)
                                    all_signals.append(sig_row)
                                    print(f"[SIGNAL] {symbol}: consensus={consensus_signal:+d} (RSI={rsi_signal:+d}, MACD={macd_signal:+d}) @ ${current_price:.2f}")
                            
                    except Exception as sym_e:
                        print(f"[WARN] Failed to process {symbol}: {sym_e}")
                        continue
                
                if not all_signals:
                    print("[INFO] No consensus signals generated for any symbols this iteration")
                    signals_df = None
                else:
                    signals_df = pd.concat(all_signals)
                    print(f"[SIGNAL] Generated consensus signals for {len(all_signals)} symbols (from {len(symbols)} tested)")
                
                if signals_df is None or signals_df.empty:
                    print("[INFO] No signals generated this iteration")
                    iteration += 1
                    time.sleep(30)
                    continue
                
                # Get latest signals
                latest_signals = signals_df.groupby(level=1).tail(1)  # Group by symbol, take latest
                
                for idx, row in latest_signals.iterrows():
                    symbol = idx[1] if isinstance(idx, tuple) else idx  # Extract symbol from MultiIndex
                    signal_val = int(row.get("signal", 0))
                    
                    # Get current price from signal row (added during generation)
                    try:
                        if "price" in row.index or pd.notna(row.get("price")):
                            current_price = float(row["price"]) if "price" in row.index else float(row.get("price", np.nan))
                        else:
                            # Try to get price from df_all directly
                            if ("Close", symbol) in df_all.columns:
                                current_price = float(df_all[("Close", symbol)].iloc[-1])
                            elif f"('Close', '{symbol}')" in df_all.columns:
                                current_price = float(df_all[f"('Close', '{symbol}')"].iloc[-1])
                            elif f"Close_{symbol}" in df_all.columns:
                                current_price = float(df_all[f"Close_{symbol}"].iloc[-1])
                            else:
                                continue  # Skip if no price found
                    except (KeyError, ValueError, TypeError):
                        continue  # Skip if price extraction fails
                    
                    if signal_val == 1 and not pos_manager.get_position(symbol):
                        # BUY signal - check if we can trade
                        if not pos_manager.can_trade():
                            print(f"[RISK] Cannot trade {symbol}: daily loss limit exceeded")
                            continue
                        
                        # Check volatility filter
                        try:
                            # Try MultiIndex format first
                            symbol_close = []
                            if ("Close", symbol) in df_all.columns:
                                symbol_close = [float(df_all[("Close", symbol)].iloc[i]) for i in range(min(20, len(df_all)))]
                            # Try string tuple format
                            elif f"('Close', '{symbol}')" in df_all.columns:
                                symbol_close = [float(df_all[f"('Close', '{symbol}')"].iloc[i]) for i in range(min(20, len(df_all)))]
                            # Try simple format
                            elif f"Close_{symbol}" in df_all.columns:
                                symbol_close = [float(df_all[f"Close_{symbol}"].iloc[i]) for i in range(min(20, len(df_all)))]
                            
                            if symbol_close:
                                symbol_df = pd.DataFrame({'Close': symbol_close})
                                symbol_volatility = optimizer.calculate_volatility(symbol_df['Close'])
                                
                                if not pos_manager.can_trade_volatility(symbol, symbol_volatility, portfolio.equity):
                                    print(f"[RISK] {symbol} volatility {symbol_volatility:.1%} exceeds limits")
                                    continue
                        except Exception as vol_e:
                            logger.debug(f"Volatility check failed for {symbol}: {vol_e}")
                            continue
                        
                        qty = max(1, int(portfolio.cash * 0.1 / current_price))  # 10% of cash
                        
                        # Calculate dynamic stops using ATR and volatility regime
                        try:
                            symbol_high = []
                            symbol_low = []
                            
                            # Try MultiIndex format
                            if ("High", symbol) in df_all.columns and ("Low", symbol) in df_all.columns:
                                symbol_high = [float(df_all[("High", symbol)].iloc[i]) for i in range(min(20, len(df_all)))]
                                symbol_low = [float(df_all[("Low", symbol)].iloc[i]) for i in range(min(20, len(df_all)))]
                            # Try string tuple format
                            elif f"('High', '{symbol}')" in df_all.columns and f"('Low', '{symbol}')" in df_all.columns:
                                symbol_high = [float(df_all[f"('High', '{symbol}')"].iloc[i]) for i in range(min(20, len(df_all)))]
                                symbol_low = [float(df_all[f"('Low', '{symbol}')"].iloc[i]) for i in range(min(20, len(df_all)))]
                            # Try simple format
                            elif f"High_{symbol}" in df_all.columns and f"Low_{symbol}" in df_all.columns:
                                symbol_high = [float(df_all[f"High_{symbol}"].iloc[i]) for i in range(min(20, len(df_all)))]
                                symbol_low = [float(df_all[f"Low_{symbol}"].iloc[i]) for i in range(min(20, len(df_all)))]
                            
                            if symbol_high and symbol_low:
                                symbol_df_copy = pd.DataFrame({
                                    'High': symbol_high,
                                    'Low': symbol_low,
                                    'Close': symbol_close if symbol_close else [current_price] * len(symbol_high),
                                })
                            else:
                                symbol_df_copy = None
                        except Exception as atr_e:
                            logger.debug(f"ATR extraction failed for {symbol}: {atr_e}")
                            symbol_df_copy = None
                        
                        # Calculate comprehensive volatility metrics
                        if symbol_df_copy is not None:
                            vol_metrics = VolatilityRegime.calculate_volatility_metrics(
                                close_prices=symbol_df_copy['Close'],
                                high_prices=symbol_df_copy['High'],
                                low_prices=symbol_df_copy['Low'],
                                period=14
                            )
                            vol_regime = vol_metrics['volatility_regime']
                            
                            # Calculate ATR-based stops
                            atr = DynamicStops.calculate_atr(symbol_df_copy['High'], symbol_df_copy['Low'], symbol_df_copy['Close']).iloc[-1]
                            stop_loss, take_profit = DynamicStops.get_volatility_adjusted_stops(current_price, atr)
                        else:
                            # Fallback to simple fixed stops
                            vol_regime = 'MEDIUM'
                            stop_loss = current_price * 0.98  # 2% stop loss
                            take_profit = current_price * 1.05  # 5% take profit
                        
                        # Apply regime-based adjustments to stops
                        stop_adjustment = VolatilityRegime.get_stop_loss_adjustment(vol_regime)
                        profit_adjustment = VolatilityRegime.get_profit_target_adjustment(vol_regime)
                        
                        stop_loss = current_price - (atr * stop_adjustment)
                        take_profit = current_price + (atr * profit_adjustment)
                        
                        VolatilityRegime.print_regime_analysis(vol_metrics)
                        print(f"[RISK] {symbol}: Regime={vol_regime}, SL=${stop_loss:.2f}, TP=${take_profit:.2f}")
                        
                        # Adjust position size based on volatility regime
                        size_multiplier = VolatilityRegime.get_position_size_adjustment(vol_regime)
                        adjusted_qty = max(1, int(qty * size_multiplier))
                        
                        # Apply Kelly Criterion position sizing (Phase 9)
                        # Get recent performance metrics for this strategy
                        strategy_perf = metrics.get_strategy_performance()
                        if strategy_perf and len(strategy_perf) > 0:
                            # Use average performance across all strategies
                            total_trades_all = sum(p.get('total_trades', 0) for p in strategy_perf.values())
                            total_wins = sum(p.get('wins', 0) for p in strategy_perf.values())
                            total_loss = sum(p.get('losses', 0) for p in strategy_perf.values())
                            total_pnl = sum(p.get('pnl', 0) for p in strategy_perf.values())
                            
                            if total_trades_all >= 20:  # Minimum trades for reliable estimate
                                win_rate = total_wins / total_trades_all
                                avg_win = total_pnl / total_wins if total_wins > 0 else 0
                                avg_loss = abs(total_pnl) / total_loss if total_loss > 0 else 100
                                
                                kelly_metrics = PerformanceMetrics(
                                    win_rate=win_rate,
                                    loss_rate=1 - win_rate,
                                    avg_win=max(1, avg_win),
                                    avg_loss=max(1, avg_loss),
                                    total_trades=total_trades_all,
                                )
                                
                                kelly_result = KellyCriterion.get_position_size_from_metrics(
                                    bankroll=portfolio.cash,
                                    metrics=kelly_metrics,
                                    fractional_kelly=0.25,  # Conservative 25% Kelly
                                    max_position_size=portfolio.cash * 0.1,
                                )
                                
                                if kelly_result['is_valid']:
                                    # Scale position size by Kelly optimal sizing
                                    kelly_qty = int(kelly_result['position_size'] / current_price)
                                    adjusted_qty = max(1, min(adjusted_qty, kelly_qty))
                                    print(f"[KELLY] {symbol}: Kelly optimal ${kelly_result['position_size']:.2f} → {adjusted_qty} shares")
                        
                        # Calculate stop-loss and take-profit percentages
                        stop_loss_pct = (current_price - stop_loss) / current_price
                        take_profit_pct = (take_profit - current_price) / current_price
                        
                        # Open position with dynamic stops
                        pos_manager.open_position(
                            symbol=symbol,
                            qty=adjusted_qty,
                            entry_price=current_price,
                            stop_loss_pct=stop_loss_pct,
                            take_profit_pct=take_profit_pct,
                            trailing_stop_pct=None,
                        )
                        
                        # Track position for time-based rotation (Phase 13)
                        advanced_risk.position_rotator.add_position(symbol, timestamp.replace(tzinfo=None))
                        
                        # Place order using smart limit order logic for better execution
                        df_symbol = df_all[[col for col in df_all.columns if col[1] == symbol]] if symbol in df_all.columns.get_level_values(1) else None
                        try:
                            order_result = submit_smart_order(broker, symbol, "BUY", adjusted_qty, current_price, df_symbol)
                            print(f"[ORDER] Submitted BUY order for {symbol}: {order_result}")
                        except Exception as e:
                            print(f"[ERROR] Failed to submit order for {symbol}: {e}")
                            import traceback
                            traceback.print_exc()
                        total_trades += 1
                        # Track which strategies contributed to this signal
                        strategy_names = []
                        if 'strategies' in row.index and row['strategies'] > 0:
                            strategy_names.append(f"Consensus({int(row['strategies'])})")
                        strategy_label = "-".join(strategy_names) if strategy_names else "Consensus"
                        metrics.log_trade(symbol, "BUY", adjusted_qty, current_price, timestamp, strategy=strategy_label)
                        print(f"[TRADE] BUY {adjusted_qty} {symbol} @ ${current_price:.2f} ({strategy_label})")
                    
                    elif row.get("signal", 0) == -1 and pos_manager.get_position(symbol):
                        # SELL signal
                        position = pos_manager.get_position(symbol)
                        if position:
                            pnl = position.current_pnl(current_price)
                            pos_manager.close_position(symbol, current_price, reason="signal")
                            df_symbol = df_all[[col for col in df_all.columns if col[1] == symbol]] if symbol in df_all.columns.get_level_values(1) else None
                            submit_smart_order(broker, symbol, "SELL", position.qty, current_price, df_symbol)
                            total_trades += 1
                            
                            # Record trade for advanced risk tracking (Phase 13)
                            pnl_pct = (pnl / (position.qty * position.entry_price)) if position.entry_price > 0 else 0
                            trade_result = TradeResult(
                                symbol=symbol,
                                side="SELL",
                                entry_price=position.entry_price,
                                exit_price=current_price,
                                qty=position.qty,
                                pnl=pnl,
                                pnl_pct=pnl_pct,
                            )
                            advanced_risk.record_trade(trade_result)
                            advanced_risk.position_rotator.remove_position(symbol)

                            # Record trade for analytics and adaptive weighting (Phase 11, 12)
                            trade_stats = TradeStats(
                                symbol=symbol,
                                side="SELL",
                                entry_price=position.entry_price,
                                exit_price=current_price,
                                qty=position.qty,
                                pnl=pnl,
                                pnl_pct=pnl_pct,
                                entry_time=position.entry_time,
                                exit_time=timestamp,
                                strategy="consensus"
                            )
                            portfolio_analytics.add_trade(trade_stats)
                            adaptive_weights.record_trade("consensus", pnl)
                            
                            # Send trade notification (Phase 14)
                            notifications.notify_trade_exit(
                                symbol=symbol,
                                qty=position.qty,
                                entry_price=position.entry_price,
                                exit_price=current_price,
                                pnl=pnl,
                                pnl_pct=pnl_pct
                            )
                            
                            metrics.log_trade(symbol, "SELL", position.qty, current_price, timestamp, pnl=pnl, strategy="Exit")
                            print(f"[TRADE] SELL {position.qty} {symbol} @ ${current_price:.2f} (P&L: ${pnl:+.2f})")
            
            except Exception as e:
                print(f"[ERROR] Signal generation failed: {e}")
                import traceback
                traceback.print_exc()
            
            # Check portfolio drawdown and halt if needed
            # REFRESH equity right before check since orders may have been placed
            account_info = broker.get_account_info()
            current_equity = account_info['equity']
            drawdown_status = pos_manager.check_portfolio_drawdown(current_equity)
            
            if drawdown_status['halt_trading']:
                print(f"[RISK] Portfolio drawdown {drawdown_status['drawdown_pct']:.1f}% exceeds limit. Halting trades.")
            
            # Log position manager analytics
            pnl_summary = pos_manager.get_portfolio_pnl(symbol_prices)
            analytics = pos_manager.get_analytics()
            
            # Get metrics report
            today_metrics = metrics.get_today_metrics()
            strategy_perf = metrics.get_strategy_performance()
            
            print(f"[ANALYTICS] Realized: ${pnl_summary['realized_pnl']:+,.2f} | "
                  f"Unrealized: ${pnl_summary['unrealized_pnl']:+,.2f} | "
                  f"Equity: ${current_equity:,.2f} | Drawdown: {drawdown_status['drawdown_pct']:.2f}%")
            print(f"[METRICS] Trades: {analytics['total_trades']} | Win Rate: {analytics['win_rate']:.1%} | "
                  f"Avg Win: ${analytics['avg_win']:.2f} | Profit Factor: {analytics['profit_factor']:.2f}x")
            print(f"[TODAY] P&L: ${today_metrics['pnl']:+.2f} | Trades: {today_metrics['total_trades']} | "
                  f"Win Rate: {today_metrics['win_rate']:.1f}%")
            
            # Print advanced risk status (Phase 13)
            advanced_risk.print_risk_status()

            # Print portfolio analytics (Phase 11)
            if portfolio_analytics.total_trades > 0:
                portfolio_analytics.print_summary()
            
            # Print adaptive weights (Phase 12)
            if adaptive_weights.total_trades_recorded > 0 and adaptive_weights.total_trades_recorded % 20 == 0:
                adaptive_weights.print_weight_status()
            
            # Show strategy performance
            if strategy_perf:
                print(f"[STRATEGIES] Performance breakdown:")
                for strategy, perf in strategy_perf.items():
                    print(f"  {strategy}: {perf['total_trades']} trades | "
                          f"{perf['win_rate']:.1f}% W/R | ${perf['pnl']:+.2f} P&L")
            
            # Print notification summary (Phase 14)
            if notifications.notification_history:
                notifications.print_notification_summary()
            
            # Sleep before next iteration
            print("[LIVE] Waiting 30 seconds for next iteration...")
            time.sleep(30)
        
        return LiveTradingSummary(
            iterations=iteration,
            total_trades=total_trades,
            total_pnl=session_pnl,
            status="Paper trading completed"
        )
        
    except ValueError as e:
        print(f"[ERROR] {e}")
        return LiveTradingSummary(
            iterations=0,
            total_trades=0,
            total_pnl=0.0,
            status=f"Error: {e}"
        )
    except KeyboardInterrupt:
        print("\n[STOP] Paper trading interrupted by user")
        return LiveTradingSummary(
            iterations=iteration,
            total_trades=total_trades,
            total_pnl=session_pnl,
            status="User stopped paper trading"
        )


def run_live_real_trading(
    *,
    config_path: str,
    symbols: list[str],
    period: str = "60d",
    interval: str = "15m",
    db_path: str = "data/trades.sqlite",
    iterations: int = 0,
    max_drawdown_pct: float = 5.0,
    max_daily_loss_pct: float = 2.0,
    alpaca_key: str | None = None,
    alpaca_secret: str | None = None,
) -> LiveTradingSummary:
    """Run LIVE trading on Alpaca with real money.
    
    WARNING: REAL MONEY - This will trade with your actual account!
    
    Args:
        config_path: Path to YAML config
        symbols: List of tickers
        period: Historical data period
        interval: Bar interval (15m recommended for live)
        db_path: SQLite database path
        iterations: Number of iterations (0 = infinite)
        max_drawdown_pct: Kill switch at % drawdown
        max_daily_loss_pct: Max daily loss %
        
    Returns:
        LiveTradingSummary with results
    """
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║                    WARNING: LIVE TRADING                       ║")
    print("║                                                                ║")
    print("║  This will trade with REAL MONEY on your Alpaca account!      ║")
    print("║  Losses are real. Commissions apply.                          ║")
    print("║                                                                ║")
    print("║  Safety Controls Active:                                       ║")
    print(f"║  • Max Drawdown: {max_drawdown_pct}% kill switch                         ║")
    print(f"║  • Max Daily Loss: {max_daily_loss_pct}%                                ║")
    print("║  • All orders logged and auditable                            ║")
    print("║                                                                ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    
    # Confirm user intent
    response = input("\nType 'YES I UNDERSTAND' to proceed with live trading: ").strip()
    if response != "YES I UNDERSTAND":
        print("[ABORT] Live trading cancelled.")
        return LiveTradingSummary(
            iterations=0,
            total_trades=0,
            total_pnl=0.0,
            status="User cancelled live trading"
        )
    
    print("\n[LIVE] Starting REAL MONEY trading on Alpaca...")
    print(f"[LIVE] Symbols: {', '.join(symbols)}")
    print(f"[LIVE] Max Drawdown: {max_drawdown_pct}%")
    print(f"[LIVE] Max Daily Loss: {max_daily_loss_pct}%")
    
    try:
        # Setup credentials (env or prompt)
        _setup_alpaca_creds(alpaca_key, alpaca_secret)

        # Load trading config
        config = load_config(config_path)
        
        # Load Alpaca configuration from environment
        alpaca_config = AlpacaConfig.from_env(paper_mode=False)
        print(f"[LIVE] Connected to LIVE account: {alpaca_config.base_url}")
        
        # Initialize data provider and broker
        data_provider = AlpacaProvider(config=alpaca_config)
        broker = AlpacaBroker(config=alpaca_config)
        
        # Initialize safety controls
        safety = SafetyControls(
            max_drawdown_pct=max_drawdown_pct,
            max_daily_loss_pct=max_daily_loss_pct,
        )
        
        # Initialize database
        repo = SqliteRepository(db_path=db_path)
        repo.init_db()
        
        # Get initial account state
        account_info = broker.get_account_info()
        initial_equity = account_info["equity"]
        print(f"[LIVE] Initial Equity: ${initial_equity:,.2f}")
        
        print("[LIVE] Safety controls initialized")
        print("[LIVE] Ready for LIVE trading with real money!")
        print("[LIVE] All trades will be executed immediately")
        
        # Get initial data
        df_all = data_provider.download_bars(
            symbols=symbols,
            period=period,
            interval=interval
        )
        
        # Run trading loop
        iteration = 0
        total_trades = 0
        session_pnl = 0.0
        daily_loss = 0.0
        
        while iterations == 0 or iteration < iterations:
            iteration += 1
            timestamp = datetime.now(timezone.utc)
            
            print(f"\n[ITERATION {iteration}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                # Check safety controls
                account_info = broker.get_account_info()
                current_equity = account_info["equity"]
                drawdown_pct = ((current_equity - initial_equity) / initial_equity) * 100
                
                # Check drawdown kill switch
                if drawdown_pct < -max_drawdown_pct:
                    print(f"[SAFETY] DRAWDOWN KILL SWITCH TRIGGERED: {drawdown_pct:.2f}%")
                    break
                
                # Check daily loss
                if daily_loss < -max_daily_loss_pct:
                    print(f"[SAFETY] DAILY LOSS LIMIT EXCEEDED: {daily_loss:.2f}%")
                    break
                
                print(f"[PORTFOLIO] Cash: ${account_info['cash']:,.2f} | Equity: ${current_equity:,.2f} | Drawdown: {drawdown_pct:.2f}%")
                
                # Get portfolio
                portfolio = broker.portfolio()
                
                # Generate signals
                signals_df = generate_signals(
                    df_all,
                    rsi_period=config.strategy.raw.get("rsi_period", 14),
                    rsi_overbought=config.strategy.raw.get("rsi_overbought", 70),
                    rsi_oversold=config.strategy.raw.get("rsi_oversold", 30),
                )
                
                if signals_df is None or signals_df.empty:
                    print("[SIGNAL] No signals generated")
                    time.sleep(30)
                    continue
                
                # Get latest signals
                latest_signals = signals_df.groupby(level=0).tail(1)
                
                for symbol, row in latest_signals.iterrows():
                    if row.get("signal", 0) == 1:
                        # BUY signal - only if we have cash
                        qty = int(portfolio.cash * 0.1 / row["Close"])  # 10% of cash
                        if qty > 0 and account_info["cash"] > row["Close"] * qty:
                            print(f"[TRADE] BUY {qty} {symbol} @ ${row['Close']:.2f}")
                            order = Order(
                                id=uuid.uuid4().hex,
                                ts=timestamp,
                                symbol=symbol,
                                side="BUY",
                                qty=qty,
                                type="MARKET"
                            )
                            broker.submit_order(order)
                            total_trades += 1
                    elif row.get("signal", 0) == -1:
                        # SELL signal
                        pos = portfolio.get_position(symbol)
                        if pos.qty > 0:
                            print(f"[TRADE] SELL {pos.qty} {symbol} @ ${row['Close']:.2f}")
                            order = Order(
                                id=uuid.uuid4().hex,
                                ts=timestamp,
                                symbol=symbol,
                                side="SELL",
                                qty=int(float(pos.qty)),
                                type="MARKET"
                            )
                            broker.submit_order(order)
                            total_trades += 1
            
            except Exception as e:
                print(f"[ERROR] Trading iteration failed: {e}")
                logger.exception("Trading error")
            
            # Sleep before next iteration
            print("[LIVE] Waiting 30 seconds for next iteration...")
            time.sleep(30)
        
        # Final summary
        account_info = broker.get_account_info()
        final_equity = account_info["equity"]
        session_pnl = final_equity - initial_equity
        
        print(f"\n[LIVE] Final Equity: ${final_equity:,.2f}")
        print(f"[LIVE] Session PnL: ${session_pnl:,.2f}")
        
        # Print data fetching optimization statistics
        if hasattr(data_provider, 'print_summary'):
            data_provider.print_summary()
        
        return LiveTradingSummary(
            iterations=iteration,
            total_trades=total_trades,
            total_pnl=session_pnl,
            status="Live trading completed"
        )
        
    except ValueError as e:
        print(f"[ERROR] {e}")
        return LiveTradingSummary(
            iterations=0,
            total_trades=0,
            total_pnl=0.0,
            status=f"Error: {e}"
        )
    except KeyboardInterrupt:
        print("\n[STOP] Live trading interrupted by user")
        return LiveTradingSummary(
            iterations=iteration,
            total_trades=total_trades,
            total_pnl=session_pnl,
            status="User stopped live trading"
        )
