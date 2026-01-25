"""
Real-time performance dashboard data aggregation.
Streams performance metrics, trades, signals for web UI.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from collections import deque


@dataclass
class PortfolioSnapshot:
    """Real-time portfolio state"""
    timestamp: datetime
    cash: float
    equity: float
    buying_power: float
    total_return_pct: float
    realized_pnl: float
    unrealized_pnl: float
    num_open_positions: int
    num_trades_today: int
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['timestamp'] = d['timestamp'].isoformat()
        return d


@dataclass
class TradeEvent:
    """Trade execution event for streaming"""
    timestamp: datetime
    symbol: str
    side: str  # BUY/SELL
    qty: int
    price: float
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    strategy: str = "unknown"
    tag: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['timestamp'] = d['timestamp'].isoformat()
        return d


@dataclass
class SignalEvent:
    """Signal generation event"""
    timestamp: datetime
    symbol: str
    signal: int  # 1=buy, 0=neutral, -1=sell
    confidence: float
    strategy: str
    ml_prediction: Optional[float] = None
    ml_confidence: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['timestamp'] = d['timestamp'].isoformat()
        return d


@dataclass
class PerformanceMetrics:
    """Current performance metrics"""
    timestamp: datetime
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    total_return_pct: float
    num_trades: int
    num_wins: int
    num_losses: int
    avg_win: float
    avg_loss: float
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['timestamp'] = d['timestamp'].isoformat()
        return d


@dataclass
class StrategyMetrics:
    """Per-strategy performance"""
    name: str
    num_trades: int
    win_rate_pct: float
    total_pnl: float
    avg_trade_pnl: float
    largest_win: float
    largest_loss: float
    current_weight: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskStatus:
    """Current risk status"""
    timestamp: datetime
    consecutive_losses: int
    max_consecutive_losses: int
    daily_pnl: float
    daily_pnl_limit: float
    daily_loss_pct: float
    is_paused: bool
    pause_reason: Optional[str] = None
    positions_at_risk: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['timestamp'] = d['timestamp'].isoformat()
        return d


class RealtimeDashboard:
    """
    Real-time dashboard data aggregator.
    Maintains rolling history for web UI streaming.
    """
    
    def __init__(self, max_history: int = 500):
        self.max_history = max_history
        
        # Latest snapshots
        self.current_portfolio: Optional[PortfolioSnapshot] = None
        self.current_metrics: Optional[PerformanceMetrics] = None
        self.current_risk: Optional[RiskStatus] = None
        
        # Streaming history (for charts/logs)
        self.portfolio_history: deque = deque(maxlen=max_history)
        self.trade_history: deque = deque(maxlen=max_history)
        self.signal_history: deque = deque(maxlen=max_history)
        self.metrics_history: deque = deque(maxlen=100)  # Fewer metrics snapshots
        
        # Per-strategy performance
        self.strategy_metrics: Dict[str, StrategyMetrics] = {}
        
        # Summary stats
        self.iteration_count = 0
        self.start_time: Optional[datetime] = None
        self.last_update: Optional[datetime] = None
    
    def initialize(self, start_cash: float):
        """Initialize dashboard at start"""
        self.start_time = datetime.now()
        self.current_portfolio = PortfolioSnapshot(
            timestamp=self.start_time,
            cash=start_cash,
            equity=start_cash,
            buying_power=start_cash,
            total_return_pct=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            num_open_positions=0,
            num_trades_today=0,
        )
        self.portfolio_history.append(self.current_portfolio)
        
        self.current_metrics = PerformanceMetrics(
            timestamp=self.start_time,
            sharpe_ratio=0.0,
            sortino_ratio=0.0,
            max_drawdown_pct=0.0,
            win_rate_pct=0.0,
            profit_factor=1.0,
            total_return_pct=0.0,
            num_trades=0,
            num_wins=0,
            num_losses=0,
            avg_win=0.0,
            avg_loss=0.0,
        )
        
        self.current_risk = RiskStatus(
            timestamp=self.start_time,
            consecutive_losses=0,
            max_consecutive_losses=0,
            daily_pnl=0.0,
            daily_pnl_limit=0.0,
            daily_loss_pct=0.0,
            is_paused=False,
        )
    
    def update_portfolio(
        self,
        cash: float,
        equity: float,
        buying_power: float,
        total_return_pct: float,
        realized_pnl: float,
        unrealized_pnl: float,
        num_open_positions: int,
        num_trades_today: int,
    ):
        """Update portfolio snapshot"""
        self.current_portfolio = PortfolioSnapshot(
            timestamp=datetime.now(),
            cash=cash,
            equity=equity,
            buying_power=buying_power,
            total_return_pct=total_return_pct,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            num_open_positions=num_open_positions,
            num_trades_today=num_trades_today,
        )
        self.portfolio_history.append(self.current_portfolio)
        self.last_update = datetime.now()
        self.iteration_count += 1
    
    def update_metrics(
        self,
        sharpe_ratio: float,
        sortino_ratio: float,
        max_drawdown_pct: float,
        win_rate_pct: float,
        profit_factor: float,
        total_return_pct: float,
        num_trades: int,
        num_wins: int,
        num_losses: int,
        avg_win: float,
        avg_loss: float,
    ):
        """Update performance metrics"""
        self.current_metrics = PerformanceMetrics(
            timestamp=datetime.now(),
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            max_drawdown_pct=max_drawdown_pct,
            win_rate_pct=win_rate_pct,
            profit_factor=profit_factor,
            total_return_pct=total_return_pct,
            num_trades=num_trades,
            num_wins=num_wins,
            num_losses=num_losses,
            avg_win=avg_win,
            avg_loss=avg_loss,
        )
        self.metrics_history.append(self.current_metrics)
    
    def update_risk(
        self,
        consecutive_losses: int,
        max_consecutive_losses: int,
        daily_pnl: float,
        daily_pnl_limit: float,
        daily_loss_pct: float,
        is_paused: bool = False,
        pause_reason: Optional[str] = None,
        positions_at_risk: Optional[List[str]] = None,
    ):
        """Update risk status"""
        self.current_risk = RiskStatus(
            timestamp=datetime.now(),
            consecutive_losses=consecutive_losses,
            max_consecutive_losses=max_consecutive_losses,
            daily_pnl=daily_pnl,
            daily_pnl_limit=daily_pnl_limit,
            daily_loss_pct=daily_loss_pct,
            is_paused=is_paused,
            pause_reason=pause_reason,
            positions_at_risk=positions_at_risk or [],
        )
    
    def record_trade(self, trade: TradeEvent):
        """Record a trade execution"""
        self.trade_history.append(trade)
        if self.current_portfolio:
            self.current_portfolio.num_trades_today += 1
    
    def record_signal(self, signal: SignalEvent):
        """Record a signal generation"""
        self.signal_history.append(signal)
    
    def update_strategy_metric(
        self,
        name: str,
        num_trades: int,
        win_rate_pct: float,
        total_pnl: float,
        avg_trade_pnl: float,
        largest_win: float,
        largest_loss: float,
        current_weight: float,
    ):
        """Update per-strategy metrics"""
        self.strategy_metrics[name] = StrategyMetrics(
            name=name,
            num_trades=num_trades,
            win_rate_pct=win_rate_pct,
            total_pnl=total_pnl,
            avg_trade_pnl=avg_trade_pnl,
            largest_win=largest_win,
            largest_loss=largest_loss,
            current_weight=current_weight,
        )
    
    def get_state(self) -> Dict[str, Any]:
        """Get complete dashboard state for web UI"""
        return {
            "timestamp": datetime.now().isoformat(),
            "iteration": self.iteration_count,
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
            "portfolio": self.current_portfolio.to_dict() if self.current_portfolio else None,
            "metrics": self.current_metrics.to_dict() if self.current_metrics else None,
            "risk": self.current_risk.to_dict() if self.current_risk else None,
            "strategies": {name: metric.to_dict() for name, metric in self.strategy_metrics.items()},
        }
    
    def get_recent_trades(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent trades for display"""
        trades = list(self.trade_history)[-limit:]
        return [t.to_dict() for t in trades]
    
    def get_recent_signals(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent signals for display"""
        signals = list(self.signal_history)[-limit:]
        return [s.to_dict() for s in signals]
    
    def get_portfolio_chart_data(self) -> Dict[str, List[Any]]:
        """Get portfolio history for charting"""
        portfolios = list(self.portfolio_history)
        return {
            "timestamps": [p.timestamp.isoformat() for p in portfolios],
            "equity": [p.equity for p in portfolios],
            "cash": [p.cash for p in portfolios],
            "total_return": [p.total_return_pct for p in portfolios],
        }
    
    def get_metrics_chart_data(self) -> Dict[str, List[Any]]:
        """Get metrics history for charting"""
        metrics = list(self.metrics_history)
        return {
            "timestamps": [m.timestamp.isoformat() for m in metrics],
            "sharpe": [m.sharpe_ratio for m in metrics],
            "max_dd": [m.max_drawdown_pct for m in metrics],
            "win_rate": [m.win_rate_pct for m in metrics],
        }
    
    def get_summary(self) -> str:
        """Get text summary for logging"""
        if not self.current_portfolio or not self.current_metrics:
            return "[DASHBOARD] Not initialized"
        
        p = self.current_portfolio
        m = self.current_metrics
        r = self.current_risk
        
        summary = (
            f"[DASHBOARD]\n"
            f"  Portfolio: Cash ${p.cash:,.0f} | Equity ${p.equity:,.0f} | Return {p.total_return_pct:+.2f}%\n"
            f"  Performance: Sharpe {m.sharpe_ratio:.2f} | Win Rate {m.win_rate_pct:.1f}% | Trades {m.num_trades}\n"
            f"  Risk: Losses {r.consecutive_losses}/{r.max_consecutive_losses} | Daily P&L ${r.daily_pnl:+,.0f}"
        )
        if r.is_paused:
            summary += f" | [PAUSED: {r.pause_reason}]"
        
        return summary
