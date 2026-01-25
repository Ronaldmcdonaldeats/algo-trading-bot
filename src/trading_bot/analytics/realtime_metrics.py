"""
Phase 23: Real-Time Metrics Monitor

Live performance tracking and metrics collection for trading engine.
Tracks P&L, Sharpe ratio, win rate, drawdown, execution stats in real-time.
Provides API-friendly snapshots for dashboard integration.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from collections import deque


@dataclass
class ExecutionMetrics:
    """Metrics for order execution"""
    total_orders: int = 0
    filled_orders: int = 0
    rejected_orders: int = 0
    avg_fill_time_ms: float = 0.0
    slippage_bps: float = 0.0  # Basis points
    last_fill_time: Optional[datetime] = None
    
    @property
    def fill_rate(self) -> float:
        """Percentage of orders filled"""
        if self.total_orders == 0:
            return 0.0
        return self.filled_orders / self.total_orders
    
    @property
    def rejection_rate(self) -> float:
        """Percentage of orders rejected"""
        if self.total_orders == 0:
            return 0.0
        return self.rejected_orders / self.total_orders


@dataclass
class SignalMetrics:
    """Metrics for signal quality"""
    total_signals: int = 0
    winning_signals: int = 0
    losing_signals: int = 0
    avg_signal_confidence: float = 0.0
    entry_filter_rate: float = 0.0  # % of signals that pass entry filter
    false_signal_rate: float = 0.0  # % of signals that result in losses
    
    @property
    def win_rate(self) -> float:
        """% of signals that result in winning trades"""
        if self.total_signals == 0:
            return 0.0
        return self.winning_signals / self.total_signals
    
    @property
    def hit_rate(self) -> float:
        """% of signals that result in any profit"""
        if self.total_signals == 0:
            return 0.0
        return (self.total_signals - self.losing_signals) / self.total_signals


@dataclass
class PositionMetrics:
    """Metrics for active positions"""
    symbol: str
    qty: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    momentum_multiplier: float = 1.0
    has_hedge: bool = False
    time_held_bars: int = 0
    
    @property
    def gain_loss_pct(self) -> float:
        """Percent gain/loss of position"""
        if self.entry_price <= 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price


@dataclass
class PerformanceSnapshot:
    """Snapshot of real-time performance metrics"""
    ts: datetime
    iteration: int
    
    # Portfolio metrics
    equity: float = 0.0
    cash: float = 0.0
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    current_pnl: float = 0.0
    current_pnl_pct: float = 0.0
    
    # Return metrics
    daily_return_pct: float = 0.0
    weekly_return_pct: float = 0.0
    monthly_return_pct: float = 0.0
    
    # Risk metrics
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    volatility_pct: float = 0.0
    
    # Trading metrics
    win_rate: float = 0.0
    num_trades: int = 0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    
    # Active position data
    num_open_positions: int = 0
    avg_position_size: float = 0.0
    largest_position: str = ""
    largest_position_pct: float = 0.0
    
    # Execution metrics
    execution: ExecutionMetrics = field(default_factory=ExecutionMetrics)
    
    # Signal metrics
    signals: SignalMetrics = field(default_factory=SignalMetrics)
    
    # Active positions detail
    positions: List[PositionMetrics] = field(default_factory=list)


class MetricsCollector:
    """Collects and aggregates real-time metrics from trading engine"""
    
    def __init__(self, window_size: int = 100):
        """
        Args:
            window_size: Number of iterations to keep in history
        """
        self.window_size = window_size
        self.snapshots: deque[PerformanceSnapshot] = deque(maxlen=window_size)
        
        # Running metrics
        self.execution = ExecutionMetrics()
        self.signals = SignalMetrics()
        
        # History tracking
        self.daily_returns: List[float] = []
        self.equity_history: List[float] = []
        self.position_history: Dict[str, List[PositionMetrics]] = {}
        
        # Current state
        self.prev_equity: float = 0.0
        self.session_start_time: Optional[datetime] = None
        self.last_snapshot: Optional[PerformanceSnapshot] = None
    
    def collect_metrics(
        self,
        ts: datetime,
        iteration: int,
        portfolio,
        prices: Dict[str, float],
        equity_history: List[float],
        trade_history: List[dict],
        fills: List,
        rejections: List,
    ) -> PerformanceSnapshot:
        """
        Collect all metrics for current iteration
        
        Args:
            ts: Current timestamp
            iteration: Current iteration number
            portfolio: Broker portfolio object
            prices: Current prices by symbol
            equity_history: Historical equity values
            trade_history: Historical trades
            fills: Orders filled this iteration
            rejections: Orders rejected this iteration
            
        Returns:
            PerformanceSnapshot with all current metrics
        """
        if self.session_start_time is None:
            self.session_start_time = ts
        
        # Calculate basic portfolio metrics
        equity = float(portfolio.equity(prices))
        cash = float(portfolio.cash)
        
        # Update execution metrics
        self.execution.total_orders += len(fills) + len(rejections)
        self.execution.filled_orders += len(fills)
        self.execution.rejected_orders += len(rejections)
        
        if len(fills) > 0:
            self.execution.last_fill_time = ts
        
        # Calculate position metrics
        positions_list: List[PositionMetrics] = []
        gross_exposure = 0.0
        largest_position_value = 0.0
        largest_position_sym = ""
        
        for sym, pos in portfolio.positions.items():
            if pos.qty == 0:
                continue
            
            current_price = prices.get(sym, pos.avg_price)
            unrealized_pnl = (current_price - pos.avg_price) * pos.qty
            unrealized_pnl_pct = unrealized_pnl / (pos.avg_price * pos.qty) if pos.avg_price > 0 else 0.0
            
            pos_metrics = PositionMetrics(
                symbol=sym,
                qty=pos.qty,
                entry_price=pos.avg_price,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
            )
            positions_list.append(pos_metrics)
            
            # Track for exposure calculation
            pos_value = abs(current_price * pos.qty)
            gross_exposure += pos_value
            if pos_value > largest_position_value:
                largest_position_value = pos_value
                largest_position_sym = sym
        
        # Calculate returns
        daily_return_pct = 0.0
        weekly_return_pct = 0.0
        monthly_return_pct = 0.0
        
        if len(equity_history) > 1:
            current_equity = equity_history[-1]
            
            # Daily return (last 252 bars ≈ 1 day)
            if len(equity_history) >= 252:
                daily_return_pct = (current_equity - equity_history[-252]) / equity_history[-252]
            
            # Weekly return (last 1260 bars ≈ 1 week, 252 bars/day)
            if len(equity_history) >= 1260:
                weekly_return_pct = (current_equity - equity_history[-1260]) / equity_history[-1260]
            
            # Monthly return (last 5040 bars ≈ 1 month)
            if len(equity_history) >= 5040:
                monthly_return_pct = (current_equity - equity_history[-5040]) / equity_history[-5040]
        
        # Calculate drawdown and Sharpe
        max_drawdown_pct = 0.0
        sharpe_ratio = 0.0
        volatility = 0.0
        
        if len(equity_history) > 1:
            eq_array = np.array(equity_history)
            cummax = np.maximum.accumulate(eq_array)
            drawdown = (eq_array - cummax) / cummax
            max_drawdown_pct = float(np.min(drawdown)) if len(drawdown) > 0 else 0.0
            
            # Sharpe ratio (assuming 252 trading days, 0% risk-free rate)
            returns = np.diff(eq_array) / eq_array[:-1] if len(eq_array) > 1 else np.array([])
            if len(returns) > 1:
                volatility = float(np.std(returns))
                sharpe_ratio = float(np.sqrt(252) * np.mean(returns) / (volatility + 1e-8)) if volatility > 0 else 0.0
        
        # Calculate win rate and trade metrics
        win_rate = 0.0
        num_trades = len(trade_history)
        consecutive_wins = 0
        consecutive_losses = 0
        
        if num_trades > 0:
            winning = len([t for t in trade_history if t.get("pnl", 0) > 0])
            win_rate = winning / num_trades
            
            # Consecutive win/loss streak
            for t in reversed(trade_history):
                if t.get("pnl", 0) > 0:
                    consecutive_wins += 1
                else:
                    break
            
            for t in reversed(trade_history):
                if t.get("pnl", 0) <= 0:
                    consecutive_losses += 1
                else:
                    break
        
        # Build snapshot
        snapshot = PerformanceSnapshot(
            ts=ts,
            iteration=iteration,
            equity=equity,
            cash=cash,
            gross_exposure=gross_exposure,
            net_exposure=gross_exposure,  # Simplified, assume net = gross for longs
            current_pnl=equity - (equity_history[0] if equity_history else equity),
            current_pnl_pct=(equity - (equity_history[0] if equity_history else equity)) / (equity_history[0] if equity_history else equity),
            daily_return_pct=daily_return_pct,
            weekly_return_pct=weekly_return_pct,
            monthly_return_pct=monthly_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown_pct=max_drawdown_pct,
            volatility_pct=volatility,
            win_rate=win_rate,
            num_trades=num_trades,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
            num_open_positions=len(positions_list),
            avg_position_size=gross_exposure / len(positions_list) if positions_list else 0.0,
            largest_position=largest_position_sym,
            largest_position_pct=largest_position_value / equity if equity > 0 else 0.0,
            execution=self.execution,
            signals=self.signals,
            positions=positions_list,
        )
        
        self.snapshots.append(snapshot)
        self.last_snapshot = snapshot
        self.equity_history.append(equity)
        
        return snapshot
    
    def update_signal_metrics(self, signal: int, confidence: float, entry_valid: bool, profit_pct: Optional[float] = None):
        """Update signal quality metrics"""
        self.signals.total_signals += 1
        self.signals.avg_signal_confidence = (
            (self.signals.avg_signal_confidence * (self.signals.total_signals - 1) + confidence)
            / self.signals.total_signals
        )
        
        if entry_valid:
            self.signals.entry_filter_rate = (
                (self.signals.entry_filter_rate * (self.signals.total_signals - 1) + 1.0)
                / self.signals.total_signals
            )
        
        # Track winning vs losing signals (if profit_pct provided)
        if profit_pct is not None:
            if profit_pct > 0:
                self.signals.winning_signals += 1
            else:
                self.signals.losing_signals += 1
            
            if profit_pct < 0:
                self.signals.false_signal_rate = (
                    self.signals.false_signal_rate * (self.signals.total_signals - 1) / self.signals.total_signals
                    + 1.0 / self.signals.total_signals
                )
    
    def get_latest_snapshot(self) -> Optional[PerformanceSnapshot]:
        """Get most recent metrics snapshot"""
        return self.last_snapshot
    
    def get_metrics_summary(self) -> Dict:
        """Get dictionary summary of current metrics (for API/dashboard)"""
        if not self.last_snapshot:
            return {}
        
        snap = self.last_snapshot
        return {
            "timestamp": snap.ts.isoformat(),
            "iteration": snap.iteration,
            "portfolio": {
                "equity": round(snap.equity, 2),
                "cash": round(snap.cash, 2),
                "pnl": round(snap.current_pnl, 2),
                "pnl_pct": round(snap.current_pnl_pct * 100, 2),
                "exposure": round(snap.gross_exposure, 2),
            },
            "performance": {
                "sharpe": round(snap.sharpe_ratio, 2),
                "max_drawdown": round(snap.max_drawdown_pct * 100, 2),
                "volatility": round(snap.volatility_pct * 100, 2),
                "daily_return": round(snap.daily_return_pct * 100, 2),
                "weekly_return": round(snap.weekly_return_pct * 100, 2),
            },
            "trading": {
                "win_rate": round(snap.win_rate * 100, 1),
                "num_trades": snap.num_trades,
                "consecutive_wins": snap.consecutive_wins,
                "consecutive_losses": snap.consecutive_losses,
            },
            "positions": {
                "count": snap.num_open_positions,
                "avg_size": round(snap.avg_position_size, 2),
                "largest": snap.largest_position,
                "largest_pct": round(snap.largest_position_pct * 100, 1),
            },
            "execution": {
                "total_orders": snap.execution.total_orders,
                "filled": snap.execution.filled_orders,
                "rejected": snap.execution.rejected_orders,
                "fill_rate": round(snap.execution.fill_rate * 100, 1),
            },
            "signals": {
                "total": snap.signals.total_signals,
                "winning": snap.signals.winning_signals,
                "win_rate": round(snap.signals.win_rate * 100, 1),
                "avg_confidence": round(snap.signals.avg_signal_confidence, 3),
                "entry_filter_rate": round(snap.signals.entry_filter_rate * 100, 1),
            },
        }
    
    def get_position_details(self) -> List[Dict]:
        """Get detailed info on all active positions"""
        if not self.last_snapshot:
            return []
        
        details = []
        for pos in self.last_snapshot.positions:
            details.append({
                "symbol": pos.symbol,
                "qty": pos.qty,
                "entry_price": round(pos.entry_price, 2),
                "current_price": round(pos.current_price, 2),
                "gain_loss_pct": round(pos.gain_loss_pct * 100, 2),
                "unrealized_pnl": round(pos.unrealized_pnl, 2),
                "momentum_mult": round(pos.momentum_multiplier, 2),
                "hedged": pos.has_hedge,
                "time_held": pos.time_held_bars,
            })
        return details
    
    def print_status(self):
        """Print real-time metrics status"""
        if not self.last_snapshot:
            return
        
        snap = self.last_snapshot
        print(
            f"   [METRICS] Equity: ${snap.equity:,.0f} | "
            f"PnL: ${snap.current_pnl:+,.0f} ({snap.current_pnl_pct:+.1%}) | "
            f"Sharpe: {snap.sharpe_ratio:.2f} | "
            f"DD: {snap.max_drawdown_pct:.1%} | "
            f"Win: {snap.win_rate:.1%} ({snap.num_trades} trades)",
            flush=True,
        )
        
        if snap.num_open_positions > 0:
            print(
                f"   [POSITIONS] Count: {snap.num_open_positions} | "
                f"Largest: {snap.largest_position} ({snap.largest_position_pct:.1%}) | "
                f"Exposure: ${snap.gross_exposure:,.0f}",
                flush=True,
            )
        
        if snap.signals.total_signals > 0:
            print(
                f"   [SIGNALS] Total: {snap.signals.total_signals} | "
                f"Win: {snap.signals.win_rate:.1%} | "
                f"Confidence: {snap.signals.avg_signal_confidence:.3f} | "
                f"Filter: {snap.signals.entry_filter_rate:.1%}",
                flush=True,
            )
        
        print(
            f"   [EXECUTION] Filled: {snap.execution.filled_orders}/{snap.execution.total_orders} "
            f"({snap.execution.fill_rate:.0%}) | "
            f"Rejected: {snap.execution.rejected_orders}",
            flush=True,
        )
