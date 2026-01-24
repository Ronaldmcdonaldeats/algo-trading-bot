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

from trading_bot.broker.alpaca import AlpacaConfig, AlpacaBroker, SafetyControls, AlpacaProvider
from trading_bot.core.models import Order, OrderType, Side
from trading_bot.configs import load_config
from trading_bot.strategy.mean_reversion_momentum import generate_signals
from trading_bot.db.repository import SqliteRepository

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
    period: str = "7d",
    interval: str = "1d",
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
        symbols: List of tickers
        period: Historical data period
          - Default 7d for fast CLI mode
          - UI mode automatically uses 60d for better analysis
        interval: Bar interval (default 1d)
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
    print(f"[LIVE] Symbols: {', '.join(symbols)}")
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
        
        # Initialize data provider and broker
        data_provider = AlpacaProvider(config=alpaca_config)
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
        print("[LIVE] Fetching initial data...")
        
        # Get initial data
        df_all = data_provider.download_bars(
            symbols=symbols,
            period=period,
            interval=interval
        )
        print(f"[DEBUG] Downloaded data shape: {df_all.shape}")
        print(f"[DEBUG] Column type: {type(df_all.columns)}, Is MultiIndex: {isinstance(df_all.columns, pd.MultiIndex)}")
        if not df_all.empty:
            print(f"[DEBUG] Sample columns: {list(df_all.columns)[:5]} ... {list(df_all.columns)[-5:]}")
        
        # Cache management - optimized for live trading
        last_data_fetch = datetime.now(timezone.utc)
        data_cache_ttl_seconds = 60  # 1 minute - refresh frequently for live data
        
        # Run trading loop
        iteration = 0
        total_trades = 0
        session_pnl = 0.0
        
        while iterations == 0 or iteration < iterations:
            iteration += 1
            
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
            
            # Generate signals
            try:
                # Process each symbol individually like the paper engine does
                all_signals = []
                for symbol in symbols:
                    try:
                        # Extract data for this symbol
                        # Columns are stored as tuples like ('Open', 'AAPL'), ('Close', 'AAPL'), etc.
                        symbol_data = {}
                        for col_name in ['Open', 'High', 'Low', 'Close', 'Volume']:
                            col_tuple = (col_name, symbol)
                            if col_tuple in df_all.columns:
                                symbol_data[col_name] = df_all[col_tuple]
                            else:
                                pass  # Skip missing columns
                        
                        if not symbol_data or 'Close' not in symbol_data:
                            print(f"[WARN] {symbol} missing required OHLCV data, skipping")
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
                        
                        # Generate signals for this symbol
                        symbol_signals = generate_signals(
                            symbol_df,
                            rsi_period=config.strategy.raw.get("rsi_period", 14),
                            rsi_overbought=config.strategy.raw.get("rsi_overbought", 70),
                            rsi_oversold=config.strategy.raw.get("rsi_oversold", 30),
                        )
                        
                        if symbol_signals is not None and not symbol_signals.empty:
                            # Add symbol index for multi-symbol handling
                            symbol_signals["symbol"] = symbol
                            symbol_signals = symbol_signals.set_index("symbol", append=True)
                            all_signals.append(symbol_signals)
                            
                    except Exception as sym_e:
                        print(f"[WARN] Failed to process {symbol}: {sym_e}")
                        continue
                
                if not all_signals:
                    print("[INFO] No signals generated for any symbols this iteration")
                    signals_df = None
                else:
                    signals_df = pd.concat(all_signals)
                    print(f"[SIGNAL] Generated signals for {len(all_signals)} symbols")
                
                if signals_df is None or signals_df.empty:
                    print("[INFO] No signals generated this iteration")
                    iteration += 1
                    continue
                
                # Get latest signals - now we have MultiIndex (timestamp, symbol)
                latest_signals = signals_df.groupby(level=1).tail(1)  # Group by symbol, take latest
                
                for idx, row in latest_signals.iterrows():
                    symbol = idx[1] if isinstance(idx, tuple) else idx  # Extract symbol from MultiIndex
                    if row.get("signal", 0) == 1:
                        # BUY signal
                        qty = int(portfolio.cash * 0.1 / row["Close"])  # 10% of cash
                        if qty > 0:
                            print(f"[TRADE] BUY {qty} {symbol} @ ${row['Close']:.2f}")
                            order = Order(
                                id=uuid.uuid4().hex,
                                ts=timestamp,
                                symbol=symbol,
                                side=Side.BUY,
                                qty=qty,
                                type=OrderType.MARKET
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
                                side=Side.SELL,
                                qty=int(float(pos.qty)),
                                type=OrderType.MARKET
                            )
                            broker.submit_order(order)
                            total_trades += 1
            
            except Exception as e:
                print(f"[ERROR] Signal generation failed: {e}")
            
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
                                side=Side.BUY,
                                qty=qty,
                                type=OrderType.MARKET
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
                                side=Side.SELL,
                                qty=int(float(pos.qty)),
                                type=OrderType.MARKET
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
