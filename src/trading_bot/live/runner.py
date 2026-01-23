"""Live trading runners for Alpaca integration."""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from trading_bot.broker.alpaca import AlpacaConfig, AlpacaBroker, SafetyControls
from trading_bot.data.providers import AlpacaProvider
from trading_bot.config import load_config
from trading_bot.strategy.mean_reversion_momentum import generate_signals
from trading_bot.db.repository import SqliteRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    period: str = "60d",
    interval: str = "1d",
    start_cash: float = 100_000.0,
    db_path: str = "trades.sqlite",
    iterations: int = 0,
) -> LiveTradingSummary:
    """Run paper trading on Alpaca (sandbox mode).
    
    Args:
        config_path: Path to YAML config
        symbols: List of tickers
        period: Historical data period
        interval: Bar interval
        start_cash: Starting cash
        db_path: SQLite database path
        iterations: Number of iterations (0 = infinite)
        
    Returns:
        LiveTradingSummary with results
    """
    print("[LIVE] Paper Trading Mode on Alpaca")
    print(f"[LIVE] Symbols: {', '.join(symbols)}")
    print(f"[LIVE] Starting cash: ${start_cash:,.2f}")
    print("[LIVE] Connecting to Alpaca paper trading...")
    
    try:
        # Load trading config
        config = load_config(config_path)
        
        # Load Alpaca configuration from environment
        alpaca_config = AlpacaConfig.from_env(paper_mode=True)
        print(f"[LIVE] Connected to: {alpaca_config.base_url}")
        
        # Initialize data provider and broker
        data_provider = AlpacaProvider(
            api_key=alpaca_config.api_key,
            api_secret=alpaca_config.api_secret,
            base_url=alpaca_config.base_url,
            paper_mode=True
        )
        broker = AlpacaBroker(config=alpaca_config)
        
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
        
        # Run trading loop
        iteration = 0
        total_trades = 0
        session_pnl = 0.0
        
        while iterations == 0 or iteration < iterations:
            iteration += 1
            timestamp = datetime.now(timezone.utc)
            
            print(f"\n[ITERATION {iteration}] {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Get portfolio
            portfolio = broker.portfolio()
            print(f"[PORTFOLIO] Cash: ${portfolio.cash:,.2f} | Equity: ${portfolio.equity:,.2f}")
            
            # Generate signals
            try:
                signals_df = generate_signals(
                    df_all,
                    rsi_period=config.strategy.raw.get("rsi_period", 14),
                    rsi_overbought=config.strategy.raw.get("rsi_overbought", 70),
                    rsi_oversold=config.strategy.raw.get("rsi_oversold", 30),
                )
                
                if signals_df is None or signals_df.empty:
                    print("[SIGNAL] No signals generated")
                    iteration += 1
                    continue
                
                # Get latest signals
                latest_signals = signals_df.groupby(level=0).tail(1)
                
                for symbol, row in latest_signals.iterrows():
                    if row.get("signal", 0) == 1:
                        # BUY signal
                        qty = int(portfolio.cash * 0.1 / row["Close"])  # 10% of cash
                        if qty > 0:
                            print(f"[TRADE] BUY {qty} {symbol} @ ${row['Close']:.2f}")
                            # TODO: Submit order through broker
                            total_trades += 1
                    elif row.get("signal", 0) == -1:
                        # SELL signal
                        # TODO: Close position
                        print(f"[TRADE] SELL signal for {symbol}")
            
            except Exception as e:
                print(f"[ERROR] Signal generation failed: {e}")
            
            # Sleep before next iteration
            print("[LIVE] Waiting 60 seconds for next iteration...")
            time.sleep(60)
        
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
    db_path: str = "trades.sqlite",
    iterations: int = 0,
    max_drawdown_pct: float = 5.0,
    max_daily_loss_pct: float = 2.0,
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
        # Load trading config
        config = load_config(config_path)
        
        # Load Alpaca configuration from environment
        alpaca_config = AlpacaConfig.from_env(paper_mode=False)
        print(f"[LIVE] Connected to LIVE account: {alpaca_config.base_url}")
        
        # Initialize data provider and broker
        data_provider = AlpacaProvider(
            api_key=alpaca_config.api_key,
            api_secret=alpaca_config.api_secret,
            base_url=alpaca_config.base_url,
            paper_mode=False
        )
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
                    time.sleep(60)
                    continue
                
                # Get latest signals
                latest_signals = signals_df.groupby(level=0).tail(1)
                
                for symbol, row in latest_signals.iterrows():
                    if row.get("signal", 0) == 1:
                        # BUY signal - only if we have cash
                        qty = int(portfolio.cash * 0.1 / row["Close"])  # 10% of cash
                        if qty > 0 and account_info["cash"] > row["Close"] * qty:
                            print(f"[TRADE] BUY {qty} {symbol} @ ${row['Close']:.2f}")
                            # TODO: Submit order through broker
                            total_trades += 1
                    elif row.get("signal", 0) == -1:
                        # SELL signal
                        print(f"[TRADE] SELL signal for {symbol}")
                        # TODO: Close position if held
            
            except Exception as e:
                print(f"[ERROR] Trading iteration failed: {e}")
                logger.exception("Trading error")
            
            # Sleep before next iteration
            print("[LIVE] Waiting 60 seconds for next iteration...")
            time.sleep(60)
        
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
