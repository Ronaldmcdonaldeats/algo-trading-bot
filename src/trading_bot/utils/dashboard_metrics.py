"""Enhanced dashboard metrics tracking and calculation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List
import numpy as np
import pandas as pd


@dataclass
class TradeRecord:
    """Single trade record for metrics calculation."""
    symbol: str
    entry_price: float
    exit_price: float
    quantity: int
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    strategy: str
    
    @property
    def duration(self) -> timedelta:
        return self.exit_time - self.entry_time
    
    @property
    def is_win(self) -> bool:
        return self.pnl > 0


@dataclass
class DashboardMetrics:
    """Real-time metrics for dashboard display."""
    portfolio_value: float
    cash: float
    invested: float
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    positions_count: int
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class EnhancedMetricsCalculator:
    """Calculate comprehensive trading metrics for dashboard."""
    
    def __init__(self, initial_capital: float = 100_000):
        """Initialize metrics calculator.
        
        Args:
            initial_capital: Starting portfolio value
        """
        self.initial_capital = initial_capital
        self.trades: List[TradeRecord] = []
        self.equity_history: List[float] = [initial_capital]
        self.timestamps: List[datetime] = [datetime.utcnow()]
    
    def add_trade(self, trade: TradeRecord) -> None:
        """Record a completed trade."""
        self.trades.append(trade)
    
    def update_equity(self, current_value: float, timestamp: Optional[datetime] = None) -> None:
        """Update equity history.
        
        Args:
            current_value: Current portfolio value
            timestamp: Time of update (default: now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        self.equity_history.append(current_value)
        self.timestamps.append(timestamp)
    
    def calculate_metrics(
        self,
        current_portfolio_value: float,
        cash: float,
        invested: float,
    ) -> DashboardMetrics:
        """Calculate all metrics for current state.
        
        Args:
            current_portfolio_value: Current total portfolio value
            cash: Available cash
            invested: Value of invested positions
            
        Returns:
            DashboardMetrics object with all calculations
        """
        # Basic metrics
        total_pnl = current_portfolio_value - self.initial_capital
        total_pnl_pct = (total_pnl / self.initial_capital) * 100 if self.initial_capital > 0 else 0
        
        # Daily metrics (from last day)
        yesterday_value = self.equity_history[-2] if len(self.equity_history) > 1 else self.initial_capital
        daily_pnl = current_portfolio_value - yesterday_value
        daily_pnl_pct = (daily_pnl / yesterday_value) * 100 if yesterday_value > 0 else 0
        
        # Trade statistics
        if self.trades:
            wins = sum(1 for t in self.trades if t.is_win)
            losses = len(self.trades) - wins
            win_rate = (wins / len(self.trades)) * 100
            
            win_trades = [t.pnl for t in self.trades if t.is_win]
            loss_trades = [abs(t.pnl) for t in self.trades if not t.is_win]
            
            avg_win = np.mean(win_trades) if win_trades else 0.0
            avg_loss = np.mean(loss_trades) if loss_trades else 0.0
            
            total_wins = sum(win_trades) if win_trades else 0.0
            total_losses = sum(loss_trades) if loss_trades else 0.0
            profit_factor = total_wins / total_losses if total_losses > 0 else 0.0
        else:
            wins = losses = 0
            win_rate = avg_win = avg_loss = profit_factor = 0.0
        
        # Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio()
        
        # Drawdown metrics
        max_dd, max_dd_pct, dd_curve = self._calculate_drawdown()
        
        return DashboardMetrics(
            portfolio_value=current_portfolio_value,
            cash=cash,
            invested=invested,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            positions_count=1 if invested > 0 else 0,  # Simplified
            trades_count=len(self.trades),
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            equity_curve=self.equity_history.copy(),
            drawdown_curve=dd_curve,
        )
    
    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio.
        
        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
            
        Returns:
            Annualized Sharpe ratio
        """
        if len(self.equity_history) < 2:
            return 0.0
        
        # Calculate daily returns
        equity_array = np.array(self.equity_history)
        returns = np.diff(equity_array) / equity_array[:-1]
        
        if len(returns) == 0:
            return 0.0
        
        # Annualize
        mean_return = np.mean(returns) * 252
        std_return = np.std(returns) * np.sqrt(252)
        
        if std_return == 0:
            return 0.0
        
        sharpe = (mean_return - risk_free_rate) / std_return
        return float(sharpe)
    
    def _calculate_drawdown(self) -> tuple[float, float, list[float]]:
        """Calculate maximum drawdown and drawdown curve.
        
        Returns:
            (max_drawdown, max_drawdown_pct, drawdown_curve)
        """
        if len(self.equity_history) < 1:
            return 0.0, 0.0, []
        
        equity_array = np.array(self.equity_history)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max * 100
        
        max_dd_pct = float(np.min(drawdown)) if len(drawdown) > 0 else 0.0
        max_dd = float(np.min(equity_array - running_max)) if len(equity_array) > 0 else 0.0
        
        return max_dd, max_dd_pct, drawdown.tolist()
    
    def get_trade_distribution(self) -> dict:
        """Get trade distribution statistics."""
        if not self.trades:
            return {
                "hourly": {},
                "daily": {},
                "by_symbol": {},
                "by_strategy": {},
            }
        
        hourly = {}
        daily = {}
        by_symbol = {}
        by_strategy = {}
        
        for trade in self.trades:
            # Hourly distribution
            hour = trade.entry_time.hour
            hourly[hour] = hourly.get(hour, 0) + 1
            
            # Daily distribution
            day = trade.entry_time.strftime("%Y-%m-%d")
            daily[day] = daily.get(day, 0) + 1
            
            # By symbol
            by_symbol[trade.symbol] = by_symbol.get(trade.symbol, 0) + 1
            
            # By strategy
            by_strategy[trade.strategy] = by_strategy.get(trade.strategy, 0) + 1
        
        return {
            "hourly": hourly,
            "daily": daily,
            "by_symbol": by_symbol,
            "by_strategy": by_strategy,
        }
    
    def get_monthly_performance(self) -> dict[str, float]:
        """Get performance by month."""
        if not self.trades:
            return {}
        
        monthly_pnl = {}
        for trade in self.trades:
            month = trade.exit_time.strftime("%Y-%m")
            monthly_pnl[month] = monthly_pnl.get(month, 0) + trade.pnl
        
        return monthly_pnl


def format_metrics_for_display(metrics: DashboardMetrics) -> dict:
    """Format metrics for JSON/display.
    
    Args:
        metrics: DashboardMetrics object
        
    Returns:
        Dict with formatted values
    """
    return {
        "portfolio": {
            "value": f"${metrics.portfolio_value:,.2f}",
            "cash": f"${metrics.cash:,.2f}",
            "invested": f"${metrics.invested:,.2f}",
        },
        "pnl": {
            "daily": f"${metrics.daily_pnl:,.2f} ({metrics.daily_pnl_pct:+.2f}%)",
            "total": f"${metrics.total_pnl:,.2f} ({metrics.total_pnl_pct:+.2f}%)",
        },
        "trading": {
            "trades": metrics.trades_count,
            "wins": metrics.wins,
            "losses": metrics.losses,
            "win_rate": f"{metrics.win_rate:.1f}%",
            "profit_factor": f"{metrics.profit_factor:.2f}",
        },
        "risk": {
            "max_drawdown": f"${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct:.2f}%)",
            "sharpe_ratio": f"{metrics.sharpe_ratio:.2f}",
        },
        "timestamp": metrics.timestamp.isoformat(),
    }
