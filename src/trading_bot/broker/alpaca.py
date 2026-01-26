"""Alpaca broker integration for paper and live trading.

This module provides:
- AlpacaProvider: Real-time and historical market data
- AlpacaBroker: Order submission and portfolio management
- Support for paper and live trading modes
- Risk management and safety controls
"""

from __future__ import annotations

import ast
import gc
import logging
import os
import time
import hashlib
import json
import traceback
from pathlib import Path
from dataclasses import dataclass
import concurrent.futures
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd

from trading_bot.core.models import Fill, Order, OrderType, Portfolio, Side, Position
from trading_bot.broker.base import Broker, OrderRejection

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlpacaConfig:
    """Alpaca broker configuration.
    
    Reads from environment variables:
    - APCA_API_KEY_ID: API key
    - APCA_API_SECRET_KEY: API secret
    - APCA_API_BASE_URL: API endpoint (paper or live)
    """
    
    api_key: str
    api_secret: str
    base_url: str
    paper_mode: bool = True
    
    @classmethod
    def from_env(cls, paper_mode: bool = True) -> "AlpacaConfig":
        """Load Alpaca configuration from environment variables."""
        api_key = os.environ.get("APCA_API_KEY_ID")
        api_secret = os.environ.get("APCA_API_SECRET_KEY")
        
        if not api_key or not api_secret:
            raise ValueError(
                "Alpaca credentials not found. Set APCA_API_KEY_ID and APCA_API_SECRET_KEY"
            )
        
        # Paper: https://paper-api.alpaca.markets
        # Live: https://api.alpaca.markets
        if paper_mode:
            base_url = os.environ.get(
                "APCA_API_BASE_URL",
                "https://paper-api.alpaca.markets"
            )
        else:
            base_url = os.environ.get(
                "APCA_API_BASE_URL",
                "https://api.alpaca.markets"
            )
        
        return cls(
            api_key=api_key,
            api_secret=api_secret,
            base_url=base_url,
            paper_mode=paper_mode
        )


@dataclass(frozen=True)
class AlpacaProvider:
    """Real-time and historical market data from Alpaca.
    
    Supports:
    - Intraday bars (1m, 5m, 15m, 1h, 4h, 1d)
    - Historical data retrieval
    - Real-time updates (via websocket - optional)
    """
    
    config: AlpacaConfig
    
    def __post_init__(self) -> None:
        """Initialize Alpaca REST client."""
        try:
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            from alpaca.data.timeframe import TimeFrameUnit
            from alpaca.data.enums import DataFeed
        except ImportError:
            raise ImportError(
                "alpaca-py not installed. Install with: pip install alpaca-py"
            )
        
        object.__setattr__(self, "_client", StockHistoricalDataClient(
            self.config.api_key,
            self.config.api_secret
        ))
        object.__setattr__(self, "_StockBarsRequest", StockBarsRequest)
        object.__setattr__(self, "_TimeFrame", TimeFrame)
        object.__setattr__(self, "_TimeFrameUnit", TimeFrameUnit)
        object.__setattr__(self, "_DataFeed", DataFeed)
    
    def download_bars(
        self,
        *,
        symbols: list[str],
        period: str = "7d",
        interval: str = "1d",
        use_cache: bool = True,
        cache_ttl_minutes: int = 60
    ) -> pd.DataFrame:
        """Download bars for multiple symbols - optimized for speed.
        
        Args:
            symbols: List of tickers (e.g., ["AAPL", "MSFT"])
            period: Time period (e.g., "5d", "7d", "1d") - shorter = faster
            interval: Bar interval (e.g., "1m", "15m", "1h", "1d")
            use_cache: Whether to use cached data (default True)
            cache_ttl_minutes: Cache time-to-live in minutes (default 60 for stable historical data)
            
        Returns:
            DataFrame with tuple columns (Price, Symbol)
        """
        TimeFrame = self._TimeFrame
        TimeFrameUnit = self._TimeFrameUnit
        DataFeed = self._DataFeed
        
        # 1. Check Cache (JSON)
        cache_dir = Path(".cache")
        cache_dir.mkdir(exist_ok=True)
        
        # Create unique cache key based on request parameters
        sym_key = ",".join(sorted(symbols))
        req_hash = hashlib.md5(f"{sym_key}_{period}_{interval}".encode()).hexdigest()
        cache_file = cache_dir / f"alpaca_bars_{req_hash}.json"
        
        if use_cache and cache_file.exists():
            mtime = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
            # Cache valid for specified TTL
            if (datetime.now(timezone.utc) - mtime) < timedelta(minutes=cache_ttl_minutes):
                print(f"[CACHE] Using cached data from {cache_file}")
                logger.info(f"Loading cached data from {cache_file}")
                try:
                    df = pd.read_json(cache_file, orient="split")
                    df.index = pd.to_datetime(df.index)
                    
                    # Handle MultiIndex columns restoration
                    # Columns might be stored as string representations like "('Open', 'AAPL')"
                    if not df.empty and isinstance(df.columns, pd.Index):
                        # Try to convert string representations back to tuples
                        new_cols = []
                        is_multiindex = False
                        for col in df.columns:
                            if isinstance(col, str) and col.startswith("('") and col.endswith("')"):
                                # Parse string representation of tuple
                                try:
                                    # Extract the tuple content
                                    import ast
                                    parsed = ast.literal_eval(col)
                                    if isinstance(parsed, tuple):
                                        new_cols.append(parsed)
                                        is_multiindex = True
                                    else:
                                        new_cols.append(col)
                                except:
                                    new_cols.append(col)
                            elif isinstance(col, list):
                                new_cols.append(tuple(col))
                                is_multiindex = True
                            else:
                                new_cols.append(col)
                        
                        if is_multiindex:
                            df.columns = pd.MultiIndex.from_tuples(new_cols)
                        else:
                            df.columns = new_cols
                    
                    return df
                except Exception as e:
                    logger.warning(f"Failed to load cache: {e}")
            else:
                print(f"[CACHE] Cache expired, re-downloading data")

        print(f"[CACHE] No valid cache, downloading data from Alpaca")
        # Map interval to TimeFrame
        if interval == "1m":
            tf = TimeFrame.Minute
        elif interval == "5m":
            tf = TimeFrame(5, TimeFrameUnit.Minute)
        elif interval == "15m":
            tf = TimeFrame(15, TimeFrameUnit.Minute)
        elif interval == "1h":
            tf = TimeFrame.Hour
        elif interval == "1d":
            tf = TimeFrame.Day
        else:
            tf = TimeFrame.Day
            
        # Map period to start date
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=30)
        if period.endswith("d"):
            start = now - timedelta(days=int(period[:-1]))
        elif period.endswith("y"):
            start = now - timedelta(days=int(period[:-1]) * 365)
        # Chunk symbols to avoid URI Too Long errors - use larger chunks for better performance
        chunk_size = 100  # Increased from 50 - Alpaca can handle it
        chunks = [symbols[i:i + chunk_size] for i in range(0, len(symbols), chunk_size)]
        print(f"[DOWNLOAD] Fetching {len(symbols)} symbols in {len(chunks)} chunk(s) (timeout: 10s per chunk)")
        all_dfs = []
        
        def fetch_chunk(chunk_syms):
            try:
                req = self._StockBarsRequest(
                    symbol_or_symbols=chunk_syms,
                    timeframe=tf,
                    start=start,
                    end=now,
                    adjustment="all",
                    feed=DataFeed.IEX,
                )
                df = self._client.get_stock_bars(req).df
                df = df.reset_index()
                # Normalize columns
                # Check for various timestamp column names
                if "timestamp" in df.columns:
                    pass
                elif "index" in df.columns:
                    df = df.rename(columns={"index": "timestamp"})
                if "symbol" not in df.columns and len(chunk_syms) == 1:
                    df["symbol"] = chunk_syms[0]
                return df
            except Exception as e:
                logger.warning(f"Batch download failed (first: {chunk_syms[0]}): {e}. Retrying individually...")
                # Fallback: Try individually to salvage valid symbols
                dfs = []
                for sym in chunk_syms:
                    try:
                        logger.info(f"Retrying fetch for {sym}...")
                        req_single = self._StockBarsRequest(
                            symbol_or_symbols=[sym],
                            timeframe=tf,
                            start=start,
                            end=now,
                            adjustment="all",
                            feed=DataFeed.IEX,
                        )
                        res = self._client.get_stock_bars(req_single).df
                        if not res.empty:
                            res = res.reset_index()
                            if "timestamp" in res.columns:
                                pass
                            elif "index" in res.columns:
                                res = res.rename(columns={"index": "timestamp"})
                            # Force symbol to be correct for individual requests
                            res["symbol"] = sym
                            dfs.append(res)
                        time.sleep(0.01)  # Minimal pause - Alpaca rate limits are generous
                    except Exception as inner_e:
                        logger.error(f"Failed to download {sym}: {inner_e}")
                        logger.error(traceback.format_exc())
                
                if dfs:
                    try:
                        return pd.concat(dfs)
                    except Exception as e:
                        logger.error(f"Failed to concat retried chunk: {e}")
                        return None
                return None

        # Use threads to fetch chunks in parallel - increased workers for faster downloads
        max_workers = min(100, len(chunks) * 5)  # Aggressive parallelization
        print(f"[DOWNLOAD] Using {max_workers} parallel workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_chunk, chunk): chunk for chunk in chunks}
            completed = 0
            for future in concurrent.futures.as_completed(futures, timeout=15):
                chunk_start = futures[future][0]
                completed += 1
                try:
                    res = future.result(timeout=10)
                    if res is not None and not res.empty:
                        all_dfs.append(res)
                except concurrent.futures.TimeoutError:
                    logger.error(f"Timeout downloading chunk starting with {chunk_start}")
                except Exception as e:
                    logger.error(f"Unexpected error in download thread for chunk {chunk_start}: {e}")
                finally:
                    # Clean up future to free memory immediately
                    del futures[future]
                # Show progress every 10 chunks
                if completed % 10 == 0:
                    print(f"[DOWNLOAD] Progress: {completed}/{len(chunks)} chunks completed")
        
        if not all_dfs:
            return pd.DataFrame()
            
        try:
            df = pd.concat(all_dfs)
            logger.info(f"After concat: df shape {df.shape}, columns: {list(df.columns)}, sample data:\n{df.head()}")
            
            # Rename columns to match yfinance (Capitalized)
            df = df.rename(columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume"
            })
            logger.info(f"After rename: columns {list(df.columns)}")
            
            # Pivot table to get MultiIndex columns
            pivot_df = df.pivot(
                index="timestamp", 
                columns="symbol", 
                values=["Open", "High", "Low", "Close", "Volume"]
            )
            logger.info(f"After pivot: shape {pivot_df.shape}, columns: {pivot_df.columns.tolist()}")
            
            # Flatten if single symbol to match yfinance behavior
            if len(symbols) == 1 and not pivot_df.empty:
                pivot_df.columns = pivot_df.columns.droplevel(1)
                logger.info(f"After flatten: columns {list(pivot_df.columns)}")
            
            # Save to cache
            if not pivot_df.empty:
                try:
                    pivot_df.to_json(cache_file, orient="split", date_format="iso")
                    logger.info(f"Saved data to cache: {cache_file}")
                except Exception as e:
                    logger.warning(f"Failed to save cache: {e}")

            # Clean up temporary dataframes after download completes
            del all_dfs, df, chunks, futures
            gc.collect()  # Force garbage collection after large data processing
            
            return pivot_df
            
        except Exception as e:
            logger.error(f"Failed to process/merge data: {e}")
            return pd.DataFrame()
    
    def history(
        self,
        symbol: str,
        *,
        start: Optional[datetime | str] = None,
        end: Optional[datetime | str] = None,
        interval: str = "1d",
        auto_adjust: bool = False,
    ) -> dict:
        """Get historical OHLCV data for a single symbol.
        
        Args:
            symbol: Ticker symbol
            start: Start date/time
            end: End date/time
            interval: Bar interval (e.g., "1m", "15m", "1h", "1d")
            auto_adjust: Whether to auto-adjust for splits/dividends
            
        Returns:
            Dictionary with OHLCV data
        """
        raise NotImplementedError("AlpacaProvider.history() not yet implemented")


class AlpacaBroker(Broker):
    """Live order submission and portfolio management via Alpaca.
    
    Supports:
    - Paper trading mode (sandbox)
    - Live trading mode
    - Market and limit orders
    - Stop-loss and take-profit orders
    - Position tracking and PnL calculation
    - Risk management (max drawdown, max loss)
    """
    
    def __init__(self, config: AlpacaConfig):
        """Initialize Alpaca broker.
        
        Args:
            config: AlpacaConfig with API credentials
        """
        self.config = config
        self._prices: dict[str, float] = {}
        self._portfolio: Optional[Portfolio] = None
        
        try:
            from alpaca.trading.client import TradingClient
        except ImportError:
            raise ImportError(
                "alpaca-py not installed. Install with: pip install alpaca-py"
            )
        
        # Initialize trading client
        self._client = TradingClient(
            api_key=config.api_key,
            secret_key=config.api_secret,
            paper=config.paper_mode
        )
    
    def set_price(self, symbol: str, price: float) -> None:
        """Set mark-to-market price for a symbol.
        
        Args:
            symbol: Ticker symbol
            price: Current market price
        """
        self._prices[symbol] = price
    
    def prices(self) -> dict[str, float]:
        """Get current mark-to-market prices."""
        return self._prices
    
    def submit_order(self, order: Order) -> Fill | OrderRejection:
        """Submit order to Alpaca.
        
        Args:
            order: Order to submit
            
        Returns:
            Fill if successful, OrderRejection if failed
        """
        from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        
        try:
            # Map OrderType and Side to Alpaca enums
            # Handle both string and enum inputs
            if isinstance(order.side, str):
                side = OrderSide.BUY if order.side.upper() == "BUY" else OrderSide.SELL
            else:
                side = OrderSide.BUY if order.side == Side.BUY else OrderSide.SELL
            
            # Market order
            if getattr(order, 'type', 'MARKET') == "MARKET":
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
            # Limit order
            elif getattr(order, 'type', 'MARKET') == "LIMIT":
                request = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    limit_price=order.limit_price or 0.0,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                return OrderRejection(
                    order=order,
                    reason=f"Unsupported order type: {getattr(order, 'type', 'UNKNOWN')}"
                )
            
            # Submit to Alpaca
            alpaca_order = self._client.submit_order(request)
            
            # Convert Alpaca order to Fill
            fill = Fill(
                order_id=alpaca_order.id,
                ts=datetime.now(timezone.utc),
                symbol=alpaca_order.symbol,
                side=order.side,
                qty=alpaca_order.qty,
                price=alpaca_order.filled_avg_price or self._prices.get(order.symbol, 0.0),
            )
            
            return fill
            
        except Exception as e:
            return OrderRejection(
                order=order,
                reason=str(e)
            )
    
    def portfolio(self) -> Portfolio:
        """Get current portfolio from Alpaca.
        
        Returns:
            Portfolio with cash, positions, equity
        """
        try:
            # Get account info
            account = self._client.get_account()
            
            # Get positions
            positions = self._client.get_all_positions()
            
            # Build positions dict with Position objects
            pos_dict = {}
            for pos in positions:
                # Convert to proper types (Alpaca may return strings)
                qty = int(pos.qty) if pos.qty else 0
                avg_price = float(getattr(pos, 'avg_fill_price', None) or getattr(pos, 'avg_entry_price', None) or 0.0)
                
                # Create Position object
                position = Position(
                    symbol=pos.symbol,
                    qty=qty,
                    avg_price=avg_price,
                )
                pos_dict[pos.symbol] = position
            
            # Build portfolio
            portfolio = Portfolio(
                cash=float(account.cash),
                positions=pos_dict,
            )
            
            self._portfolio = portfolio
            return portfolio
            
        except Exception as e:
            raise RuntimeError(f"Failed to fetch portfolio: {e}")
    
    def get_account_info(self) -> dict:
        """Get account information from Alpaca.
        
        Returns:
            Account details (buying_power, cash, equity, drawdown)
        """
        try:
            account = self._client.get_account()
            
            return {
                "account_number": account.account_number,
                "buying_power": float(account.buying_power),
                "cash": float(account.cash),
                "equity": float(account.portfolio_value),
                "last_equity": float(account.last_equity),
                "multiplier": account.multiplier,
                "shorting_enabled": account.shorting_enabled,
                "trade_suspended_by_user": account.trade_suspended_by_user,
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked,
                "account_blocked": account.account_blocked,
                "created_at": account.created_at,
                "status": account.status,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to fetch account info: {e}")
    
    def get_positions(self) -> list[dict]:
        """Get open positions from Alpaca.
        
        Returns:
            List of position details
        """
        try:
            positions = self._client.get_all_positions()
            
            pos_list = []
            for pos in positions:
                pos_list.append({
                    "symbol": pos.symbol,
                    "qty": pos.qty,
                    "avg_fill_price": float(pos.avg_fill_price),
                    "current_price": float(pos.current_price or self._prices.get(pos.symbol, pos.avg_fill_price)),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc),
                    "asset_id": pos.asset_id,
                    "asset_class": pos.asset_class,
                    "side": pos.side,
                    "qty_available": pos.qty_available,
                })
            
            return pos_list
        except Exception as e:
            raise RuntimeError(f"Failed to fetch positions: {e}")


# Safety controls for live trading
@dataclass(frozen=True)
class SafetyControls:
    """Risk management and safety controls for live trading."""
    
    max_drawdown_pct: float = 5.0  # Kill switch if drawdown > 5%
    max_daily_loss_pct: float = 2.0  # Max loss per day
    max_position_size_pct: float = 10.0  # Max position as % of equity
    max_orders_per_day: int = 100  # Max orders per day
    require_explicit_enable: bool = True  # Require --enable-live flag
    
    def validate(self, state: dict) -> tuple[bool, str]:
        """Validate trading state against safety controls.
        
        Args:
            state: Current trading state with equity, cash, drawdown, etc.
            
        Returns:
            (is_valid, reason_if_invalid)
        """
        # Check max drawdown
        if state.get("drawdown_pct", 0) < -self.max_drawdown_pct:
            return False, f"Drawdown {state['drawdown_pct']:.1f}% exceeds limit {self.max_drawdown_pct}%"
        
        # Check daily loss
        if state.get("daily_loss_pct", 0) < -self.max_daily_loss_pct:
            return False, f"Daily loss {state['daily_loss_pct']:.1f}% exceeds limit {self.max_daily_loss_pct}%"
        
        # Check position size
        if state.get("max_position_pct", 0) > self.max_position_size_pct:
            return False, f"Position {state['max_position_pct']:.1f}% exceeds limit {self.max_position_size_pct}%"
        
        # Check orders per day
        if state.get("orders_today", 0) > self.max_orders_per_day:
            return False, f"Orders {state['orders_today']} exceeds daily limit {self.max_orders_per_day}"
        
        return True, ""
