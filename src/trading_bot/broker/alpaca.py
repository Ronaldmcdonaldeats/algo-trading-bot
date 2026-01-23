"""Alpaca broker integration for paper and live trading.

This module provides:
- AlpacaProvider: Real-time and historical market data
- AlpacaBroker: Order submission and portfolio management
- Support for paper and live trading modes
- Risk management and safety controls
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from trading_bot.core.models import Fill, Order, OrderType, Portfolio, Side
from trading_bot.broker.base import Broker, OrderRejection


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
    
    def download_bars(
        self,
        *,
        symbols: list[str],
        period: str,
        interval: str
    ) -> dict[str, dict]:
        """Download bars for multiple symbols.
        
        Args:
            symbols: List of tickers (e.g., ["AAPL", "MSFT"])
            period: Time period (e.g., "30m", "1h", "1d")
            interval: Bar interval (e.g., "1m", "15m", "1h", "1d")
            
        Returns:
            Dictionary mapping symbol -> OHLCV data
        """
        raise NotImplementedError("AlpacaProvider.download_bars() not yet implemented")
    
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
            base_url=config.base_url
        )
    
    def set_price(self, symbol: str, price: float) -> None:
        """Set mark-to-market price for a symbol.
        
        Args:
            symbol: Ticker symbol
            price: Current market price
        """
        self._prices[symbol] = price
    
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
            side = OrderSide.BUY if order.side == Side.BUY else OrderSide.SELL
            
            # Market order
            if order.order_type == OrderType.MARKET:
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
            # Limit order
            elif order.order_type == OrderType.LIMIT:
                request = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.qty,
                    limit_price=order.price or 0.0,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                return OrderRejection(
                    order=order,
                    reason=f"Unsupported order type: {order.order_type}"
                )
            
            # Submit to Alpaca
            alpaca_order = self._client.submit_order(request)
            
            # Convert Alpaca order to Fill
            fill = Fill(
                symbol=alpaca_order.symbol,
                qty=alpaca_order.qty,
                price=alpaca_order.filled_avg_price or self._prices.get(order.symbol, 0.0),
                side=order.side,
                timestamp=datetime.now(timezone.utc),
                order_id=alpaca_order.id,
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
            
            # Build positions dict
            pos_dict = {}
            for pos in positions:
                pos_dict[pos.symbol] = {
                    "qty": pos.qty,
                    "avg_fill_price": pos.avg_fill_price,
                    "current_price": pos.current_price or self._prices.get(pos.symbol, pos.avg_fill_price),
                    "market_value": pos.market_value,
                    "unrealized_pl": pos.unrealized_pl,
                    "unrealized_plpc": pos.unrealized_plpc,
                }
            
            # Build portfolio
            portfolio = Portfolio(
                cash=float(account.cash),
                buying_power=float(account.buying_power),
                positions=pos_dict,
                equity=float(account.portfolio_value),
                timestamp=datetime.now(timezone.utc),
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
                "updated_at": account.updated_at,
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
