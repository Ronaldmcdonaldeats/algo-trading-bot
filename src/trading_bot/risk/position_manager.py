"""Position management with stop-loss, take-profit, and trailing stops."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class ManagedPosition:
    """Tracks an open position with exits."""
    symbol: str
    qty: int
    entry_price: float
    entry_time: datetime
    stop_loss_price: float
    take_profit_price: float
    trailing_stop_pct: Optional[float] = None  # e.g., 0.02 for 2%
    highest_price: float = None  # For trailing stops
    
    def __post_init__(self):
        if self.highest_price is None:
            self.highest_price = self.entry_price
    
    def current_pnl(self, current_price: float) -> float:
        """Calculate current P&L."""
        return (current_price - self.entry_price) * self.qty
    
    def current_pnl_pct(self, current_price: float) -> float:
        """Calculate current P&L %."""
        if self.entry_price == 0:
            return 0.0
        return (current_price - self.entry_price) / self.entry_price
    
    def should_exit(self, current_price: float) -> Optional[str]:
        """Check if position should be exited. Returns reason or None."""
        # Check stop-loss
        if current_price <= self.stop_loss_price:
            return f"stop_loss (target: ${self.stop_loss_price:.2f}, current: ${current_price:.2f})"
        
        # Check take-profit
        if current_price >= self.take_profit_price:
            return f"take_profit (target: ${self.take_profit_price:.2f}, current: ${current_price:.2f})"
        
        # Check trailing stop
        if self.trailing_stop_pct is not None:
            # Update highest price
            if current_price > self.highest_price:
                self.highest_price = current_price
            
            # Calculate trailing stop level
            trailing_stop_level = self.highest_price * (1.0 - self.trailing_stop_pct)
            if current_price <= trailing_stop_level:
                return f"trailing_stop (highest: ${self.highest_price:.2f}, stop: ${trailing_stop_level:.2f})"
        
        return None
    
    def days_held(self) -> float:
        """Return number of days position has been held."""
        return (datetime.utcnow() - self.entry_time).total_seconds() / (24 * 3600)


class PositionManager:
    """Manages all open positions with risk controls."""
    
    def __init__(
        self,
        default_stop_loss_pct: float = 0.02,  # 2%
        default_take_profit_pct: float = 0.05,  # 5%
        max_position_size_pct: float = 0.1,  # 10% of portfolio per position
        max_daily_loss_pct: float = 0.05,  # 5% daily loss limit
        max_positions: int = 10,
        max_portfolio_drawdown_pct: float = 0.1,  # 10% portfolio drawdown limit
        volatility_adjustment: bool = True,  # Reduce position size for volatile stocks
    ):
        self.default_stop_loss_pct = default_stop_loss_pct
        self.default_take_profit_pct = default_take_profit_pct
        self.max_position_size_pct = max_position_size_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_positions = max_positions
        self.max_portfolio_drawdown_pct = max_portfolio_drawdown_pct
        self.volatility_adjustment = volatility_adjustment
        
        self.positions: Dict[str, ManagedPosition] = {}
        self.daily_pnl = 0.0
        self.peak_equity = 100000.0  # Track peak for drawdown calculation
        self.closed_positions = []  # Track closed positions for analytics
    
    def open_position(
        self,
        symbol: str,
        qty: int,
        entry_price: float,
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        trailing_stop_pct: Optional[float] = None,
    ) -> ManagedPosition:
        """Open a new managed position."""
        if symbol in self.positions:
            logger.warning(f"Position {symbol} already open, closing old one")
            self.close_position(symbol, entry_price)
        
        if len(self.positions) >= self.max_positions:
            logger.warning(f"Max positions ({self.max_positions}) reached, cannot open {symbol}")
            return None
        
        # Use defaults if not specified
        sl_pct = stop_loss_pct or self.default_stop_loss_pct
        tp_pct = take_profit_pct or self.default_take_profit_pct
        
        sl_price = entry_price * (1.0 - sl_pct)
        tp_price = entry_price * (1.0 + tp_pct)
        
        position = ManagedPosition(
            symbol=symbol,
            qty=qty,
            entry_price=entry_price,
            entry_time=datetime.utcnow(),
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
            trailing_stop_pct=trailing_stop_pct,
        )
        
        self.positions[symbol] = position
        logger.info(
            f"[POSITION] OPEN {symbol}: {qty} @ ${entry_price:.2f} | "
            f"SL: ${sl_price:.2f} | TP: ${tp_price:.2f}"
        )
        return position
    
    def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str = "manual",
    ) -> Optional[Dict]:
        """Close a position and record P&L."""
        if symbol not in self.positions:
            logger.warning(f"No position found for {symbol}")
            return None
        
        pos = self.positions.pop(symbol)
        pnl = (exit_price - pos.entry_price) * pos.qty
        pnl_pct = (exit_price - pos.entry_price) / pos.entry_price * 100
        
        self.daily_pnl += pnl
        
        close_record = {
            "symbol": symbol,
            "qty": pos.qty,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "days_held": pos.days_held(),
            "reason": reason,
            "entry_time": pos.entry_time,
            "exit_time": datetime.utcnow(),
        }
        
        self.closed_positions.append(close_record)
        
        logger.info(
            f"[POSITION] CLOSE {symbol} @ ${exit_price:.2f} | "
            f"P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%) | Reason: {reason}"
        )
        
        return close_record
    
    def check_exits(self, symbol_prices: Dict[str, float]) -> list:
        """Check all positions for exits. Returns list of (symbol, reason, exit_price) tuples."""
        exits = []
        
        for symbol, position in list(self.positions.items()):
            if symbol not in symbol_prices:
                continue
            
            current_price = symbol_prices[symbol]
            exit_reason = position.should_exit(current_price)
            
            if exit_reason:
                exits.append((symbol, exit_reason, current_price))
        
        return exits
    
    def execute_exits(self, symbol_prices: Dict[str, float]) -> list:
        """Execute all necessary exits and return list of closed positions."""
        exits = self.check_exits(symbol_prices)
        closed = []
        
        for symbol, reason, exit_price in exits:
            result = self.close_position(symbol, exit_price, reason=reason)
            closed.append(result)
        
        return closed
    
    def get_position(self, symbol: str) -> Optional[ManagedPosition]:
        """Get position details."""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> Dict[str, ManagedPosition]:
        """Get all open positions."""
        return self.positions.copy()
    
    def get_portfolio_pnl(self, symbol_prices: Dict[str, float]) -> Dict:
        """Get total portfolio P&L."""
        unrealized_pnl = 0.0
        for symbol, position in self.positions.items():
            if symbol in symbol_prices:
                unrealized_pnl += position.current_pnl(symbol_prices[symbol])
        
        total_pnl = self.daily_pnl + unrealized_pnl
        
        return {
            "realized_pnl": self.daily_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "num_open_positions": len(self.positions),
            "num_closed_positions": len(self.closed_positions),
        }
    
    def can_trade(self) -> bool:
        """Check if we can still trade (daily loss limit)."""
        if self.daily_pnl < 0 and abs(self.daily_pnl) > 100000 * self.max_daily_loss_pct:
            logger.warning(f"Daily loss limit exceeded: {self.daily_pnl:.2f}")
            return False
        return True
    
    def can_trade_volatility(self, symbol: str, volatility: float, current_equity: float) -> bool:
        """Check if symbol volatility allows trading.
        
        Args:
            symbol: Trading symbol
            volatility: Annualized volatility (e.g., 0.35 for 35%)
            current_equity: Current portfolio equity
            
        Returns:
            True if OK to trade, False if too volatile
        """
        if not self.volatility_adjustment:
            return True
        
        # Skip trades on extremely volatile stocks (>100% annualized)
        if volatility > 1.0:
            logger.warning(f"{symbol} volatility {volatility:.1%} too high, skipping")
            return False
        
        return True
    
    def check_portfolio_drawdown(self, current_equity: float) -> Dict:
        """Check portfolio drawdown status.
        
        Args:
            current_equity: Current portfolio equity
            
        Returns:
            Dict with drawdown info and whether we should halt trading
        """
        # Update peak
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        drawdown = (self.peak_equity - current_equity) / self.peak_equity if self.peak_equity > 0 else 0.0
        halt_trading = drawdown > self.max_portfolio_drawdown_pct
        
        return {
            "drawdown": drawdown,
            "drawdown_pct": drawdown * 100,
            "peak_equity": self.peak_equity,
            "current_equity": current_equity,
            "halt_trading": halt_trading,
        }
    
    def reset_daily(self):
        """Reset daily metrics (call at start of each trading day)."""
        self.daily_pnl = 0.0
    
    def get_analytics(self) -> Dict:
        """Get trading analytics from closed positions."""
        if not self.closed_positions:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "total_pnl": 0.0,
            }
        
        winning = [p for p in self.closed_positions if p["pnl"] > 0]
        losing = [p for p in self.closed_positions if p["pnl"] < 0]
        
        total_wins = sum(p["pnl"] for p in winning)
        total_losses = sum(abs(p["pnl"]) for p in losing)
        
        return {
            "total_trades": len(self.closed_positions),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(self.closed_positions) if self.closed_positions else 0.0,
            "avg_win": total_wins / len(winning) if winning else 0.0,
            "avg_loss": total_losses / len(losing) if losing else 0.0,
            "profit_factor": total_wins / total_losses if total_losses > 0 else 0.0,
            "total_pnl": sum(p["pnl"] for p in self.closed_positions),
            "avg_days_held": sum(p["days_held"] for p in self.closed_positions) / len(self.closed_positions) if self.closed_positions else 0.0,
        }
