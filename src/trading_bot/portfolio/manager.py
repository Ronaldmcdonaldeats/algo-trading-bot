"""Portfolio Manager - Core position and portfolio tracking"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from collections import defaultdict


@dataclass
class Position:
    """Individual position in portfolio"""
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    target_weight: float = 0.0  # Target allocation %
    sector: str = ""
    asset_class: str = "equity"
    
    @property
    def entry_value(self) -> float:
        return self.quantity * self.entry_price
    
    @property
    def current_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def unrealized_pnl(self) -> float:
        return self.current_value - self.entry_value
    
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_value == 0:
            return 0.0
        return (self.unrealized_pnl / self.entry_value) * 100
    
    @property
    def holding_days(self) -> int:
        return (datetime.now() - self.entry_time).days


@dataclass
class PortfolioSnapshot:
    """Point-in-time portfolio state"""
    timestamp: datetime
    total_value: float
    cash: float
    positions: Dict[str, Position] = field(default_factory=dict)
    gross_exposure: float = 0.0  # Sum of absolute position values
    net_exposure: float = 0.0
    leverage: float = 0.0
    
    @property
    def invested_capital(self) -> float:
        return sum(p.current_value for p in self.positions.values())
    
    @property
    def utilization(self) -> float:
        """Percentage of capital deployed"""
        if self.total_value == 0:
            return 0.0
        return (self.invested_capital / self.total_value) * 100


class PortfolioManager:
    """Manage portfolio positions, tracking, and analysis"""
    
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.history: List[PortfolioSnapshot] = []
        self.trades: List[Dict] = []
        self.sector_allocation: Dict[str, float] = defaultdict(float)
        self.asset_class_allocation: Dict[str, float] = defaultdict(float)
        
    @property
    def total_value(self) -> float:
        """Total portfolio value (cash + positions)"""
        positions_value = sum(p.current_value for p in self.positions.values())
        return self.cash + positions_value
    
    @property
    def invested_value(self) -> float:
        """Value invested in positions"""
        return sum(p.current_value for p in self.positions.values())
    
    @property
    def return_pct(self) -> float:
        """Total return %"""
        if self.initial_capital == 0:
            return 0.0
        return ((self.total_value - self.initial_capital) / self.initial_capital) * 100
    
    @property
    def utilization(self) -> float:
        """Capital utilization %"""
        if self.total_value == 0:
            return 0.0
        return (self.invested_value / self.total_value) * 100
    
    @property
    def gross_exposure(self) -> float:
        """Sum of absolute position values"""
        return sum(abs(p.current_value) for p in self.positions.values())
    
    @property
    def net_exposure(self) -> float:
        """Sum of signed position values"""
        return sum(p.current_value for p in self.positions.values())
    
    @property
    def leverage(self) -> float:
        """Gross exposure / total capital"""
        if self.total_value == 0:
            return 0.0
        return self.gross_exposure / self.total_value
    
    @property
    def num_positions(self) -> int:
        """Number of open positions"""
        return len(self.positions)
    
    @property
    def avg_holding_days(self) -> float:
        """Average holding period across positions"""
        if not self.positions:
            return 0.0
        return np.mean([p.holding_days for p in self.positions.values()])
    
    def open_position(self, symbol: str, quantity: float, price: float,
                      sector: str = "", asset_class: str = "equity") -> None:
        """Open a new position"""
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        
        cost = quantity * price
        if cost > self.cash:
            raise ValueError(f"Insufficient cash. Need {cost}, have {self.cash}")
        
        self.cash -= cost
        self.positions[symbol] = Position(
            symbol=symbol,
            quantity=quantity,
            entry_price=price,
            entry_time=datetime.now(),
            current_price=price,
            sector=sector,
            asset_class=asset_class
        )
        
        self.trades.append({
            "symbol": symbol,
            "type": "BUY",
            "quantity": quantity,
            "price": price,
            "timestamp": datetime.now(),
            "cash_before": self.cash + cost
        })
        
        self._update_allocations()
    
    def close_position(self, symbol: str, quantity: Optional[float] = None,
                       price: Optional[float] = None) -> float:
        """Close a position (partial or full)
        
        Returns:
            Realized P&L
        """
        if symbol not in self.positions:
            raise ValueError(f"Position {symbol} not found")
        
        position = self.positions[symbol]
        if quantity is None:
            quantity = position.quantity
        if price is None:
            price = position.current_price
        
        if quantity > position.quantity:
            raise ValueError(f"Cannot close {quantity}, only have {position.quantity}")
        
        proceeds = quantity * price
        cost = quantity * position.entry_price
        realized_pnl = proceeds - cost
        
        self.cash += proceeds
        
        if quantity == position.quantity:
            del self.positions[symbol]
        else:
            position.quantity -= quantity
        
        self.trades.append({
            "symbol": symbol,
            "type": "SELL",
            "quantity": quantity,
            "price": price,
            "realized_pnl": realized_pnl,
            "timestamp": datetime.now()
        })
        
        self._update_allocations()
        return realized_pnl
    
    def update_prices(self, prices: Dict[str, float]) -> None:
        """Update current prices for all positions"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position by symbol"""
        return self.positions.get(symbol)
    
    def get_all_positions(self) -> List[Position]:
        """Get all open positions"""
        return list(self.positions.values())
    
    def get_position_by_sector(self, sector: str) -> List[Position]:
        """Get all positions in a sector"""
        return [p for p in self.positions.values() if p.sector == sector]
    
    def get_sector_exposure(self) -> Dict[str, float]:
        """Get sector exposure as % of portfolio"""
        total = self.total_value
        if total == 0:
            return {}
        
        exposure = defaultdict(float)
        for pos in self.positions.values():
            exposure[pos.sector] += pos.current_value / total
        
        return dict(exposure)
    
    def get_asset_class_exposure(self) -> Dict[str, float]:
        """Get asset class exposure as % of portfolio"""
        total = self.total_value
        if total == 0:
            return {}
        
        exposure = defaultdict(float)
        for pos in self.positions.values():
            exposure[pos.asset_class] += pos.current_value / total
        
        return dict(exposure)
    
    def get_concentration(self) -> Dict[str, float]:
        """Get concentration (position size as % of portfolio)"""
        total = self.total_value
        if total == 0:
            return {}
        
        return {
            p.symbol: (p.current_value / total) * 100 
            for p in self.positions.values()
        }
    
    def get_top_positions(self, n: int = 5) -> List[Tuple[str, float]]:
        """Get top N positions by value"""
        sorted_pos = sorted(
            self.positions.items(),
            key=lambda x: abs(x[1].current_value),
            reverse=True
        )
        return [(s, p.current_value) for s, p in sorted_pos[:n]]
    
    def get_total_unrealized_pnl(self) -> float:
        """Total unrealized P&L across all positions"""
        return sum(p.unrealized_pnl for p in self.positions.values())
    
    def get_total_realized_pnl(self) -> float:
        """Total realized P&L from closed trades"""
        realized = sum(
            t.get("realized_pnl", 0) 
            for t in self.trades 
            if t["type"] == "SELL"
        )
        return realized
    
    def get_realized_trades(self, limit: int = 50) -> List[Dict]:
        """Get realized trades"""
        sells = [t for t in self.trades if t["type"] == "SELL"]
        return sells[-limit:]
    
    def take_snapshot(self) -> PortfolioSnapshot:
        """Take a point-in-time portfolio snapshot"""
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(),
            total_value=self.total_value,
            cash=self.cash,
            positions={s: p for s, p in self.positions.items()},
            gross_exposure=self.gross_exposure,
            net_exposure=self.net_exposure,
            leverage=self.leverage
        )
        self.history.append(snapshot)
        return snapshot
    
    def get_history(self) -> List[PortfolioSnapshot]:
        """Get portfolio history"""
        return self.history
    
    def get_history_df(self) -> pd.DataFrame:
        """Get portfolio history as DataFrame"""
        if not self.history:
            return pd.DataFrame()
        
        data = {
            "timestamp": [s.timestamp for s in self.history],
            "total_value": [s.total_value for s in self.history],
            "cash": [s.cash for s in self.history],
            "invested": [s.invested_capital for s in self.history],
            "leverage": [s.leverage for s in self.history],
            "utilization": [s.utilization for s in self.history]
        }
        
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df
    
    def get_summary(self) -> Dict:
        """Get portfolio summary"""
        total_realized = self.get_total_realized_pnl()
        total_unrealized = self.get_total_unrealized_pnl()
        
        return {
            "total_value": self.total_value,
            "initial_capital": self.initial_capital,
            "return_pct": self.return_pct,
            "cash": self.cash,
            "invested_value": self.invested_value,
            "utilization_pct": self.utilization,
            "num_positions": self.num_positions,
            "gross_exposure": self.gross_exposure,
            "net_exposure": self.net_exposure,
            "leverage": self.leverage,
            "total_realized_pnl": total_realized,
            "total_unrealized_pnl": total_unrealized,
            "total_pnl": total_realized + total_unrealized,
            "avg_holding_days": self.avg_holding_days,
            "sector_exposure": self.get_sector_exposure(),
            "asset_class_exposure": self.get_asset_class_exposure(),
            "top_positions": dict(self.get_top_positions()),
            "concentration": self.get_concentration()
        }
    
    def _update_allocations(self) -> None:
        """Update sector and asset class allocations"""
        self.sector_allocation.clear()
        self.asset_class_allocation.clear()
        
        for pos in self.positions.values():
            self.sector_allocation[pos.sector] += pos.current_value
            self.asset_class_allocation[pos.asset_class] += pos.current_value
