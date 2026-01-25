"""
Phase 24: Position Monitor with Real-Time Alerts

Monitors active positions and generates alerts for:
- Positions reaching stop loss or take profit
- Excessive drawdown on positions
- Momentum changes in held positions
- Hedge status changes
- Position age/time-held tracking
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Callable
from enum import Enum


class AlertType(Enum):
    """Types of position alerts"""
    APPROACHING_TP = "approaching_take_profit"
    APPROACHING_SL = "approaching_stop_loss"
    DRAWDOWN_WARNING = "drawdown_warning"
    MOMENTUM_SHIFT = "momentum_shift"
    HEDGE_ACTIVATED = "hedge_activated"
    POSITION_AGED = "position_aged"
    LARGE_POSITION = "large_position"
    CORRELATION_SPIKE = "correlation_spike"


@dataclass
class PositionAlert:
    """Alert for position status"""
    ts: datetime
    symbol: str
    alert_type: AlertType
    severity: float  # 0.0-1.0, higher = more urgent
    message: str
    metric: float = 0.0  # Current metric value
    threshold: float = 0.0  # Alert threshold
    actions: List[str] = field(default_factory=list)  # Recommended actions
    
    def __str__(self) -> str:
        severity_str = "🔴" if self.severity > 0.8 else "🟠" if self.severity > 0.5 else "🟡"
        return f"{severity_str} [{self.symbol}] {self.alert_type.value}: {self.message}"


@dataclass
class PositionState:
    """Tracks state and history of a position"""
    symbol: str
    entry_price: float
    entry_bar: int
    qty: int
    
    # Current state
    current_price: float = 0.0
    current_pnl_pct: float = 0.0
    momentum_score: float = 0.0
    hedged: bool = False
    
    # History
    peak_price: float = 0.0
    lowest_price: float = 0.0
    max_favorable_excursion: float = 0.0  # Best profit reached
    max_adverse_excursion: float = 0.0  # Worst loss reached
    
    # Tracking
    alerts: List[PositionAlert] = field(default_factory=list)
    last_alert_bar: int = 0
    momentum_history: List[float] = field(default_factory=list)
    
    def update(self, current_price: float, momentum_score: float, iteration: int):
        """Update position state"""
        self.current_price = current_price
        self.current_pnl_pct = (current_price - self.entry_price) / self.entry_price if self.entry_price > 0 else 0.0
        self.momentum_score = momentum_score
        
        # Track extremes
        if current_price > self.peak_price:
            self.peak_price = current_price
        if current_price < self.lowest_price or self.lowest_price == 0.0:
            self.lowest_price = current_price
        
        # Track MFE (Max Favorable Excursion) and MAE (Max Adverse Excursion)
        unrealized_pnl_pct = self.current_pnl_pct
        if unrealized_pnl_pct > self.max_favorable_excursion:
            self.max_favorable_excursion = unrealized_pnl_pct
        if unrealized_pnl_pct < self.max_adverse_excursion or self.max_adverse_excursion == 0.0:
            self.max_adverse_excursion = unrealized_pnl_pct
        
        self.momentum_history.append(momentum_score)
    
    def bars_held(self, current_bar: int) -> int:
        """Get bars held"""
        return current_bar - self.entry_bar
    
    def drawdown_from_peak(self) -> float:
        """Get drawdown from peak price"""
        if self.peak_price <= 0:
            return 0.0
        return (self.peak_price - self.current_price) / self.peak_price
    
    def recent_momentum_trend(self, window: int = 5) -> float:
        """Get momentum trend (positive = improving)"""
        if len(self.momentum_history) < window:
            return 0.0
        recent = self.momentum_history[-window:]
        return (recent[-1] - recent[0]) / len(recent)


class PositionMonitor:
    """Monitors active positions and generates alerts"""
    
    def __init__(
        self,
        tp_threshold: float = 0.01,  # Alert if within 1% of take profit
        sl_threshold: float = 0.005,  # Alert if within 0.5% of stop loss
        drawdown_threshold: float = 0.03,  # Alert if down >3% from peak
        age_threshold: int = 200,  # Alert if held >200 bars
        momentum_shift_threshold: float = 0.2,  # Alert if momentum shifts >0.2
    ):
        self.tp_threshold = tp_threshold
        self.sl_threshold = sl_threshold
        self.drawdown_threshold = drawdown_threshold
        self.age_threshold = age_threshold
        self.momentum_shift_threshold = momentum_shift_threshold
        
        # Position tracking
        self.positions: Dict[str, PositionState] = {}
        self.alert_history: List[PositionAlert] = []
        self.position_history: List[PositionState] = []
        
        # Callbacks
        self.alert_callbacks: List[Callable[[PositionAlert], None]] = []
    
    def register_alert_callback(self, callback: Callable[[PositionAlert], None]):
        """Register callback for alerts"""
        self.alert_callbacks.append(callback)
    
    def add_position(
        self,
        symbol: str,
        entry_price: float,
        qty: int,
        entry_bar: int,
        ts: datetime,
    ):
        """Add a new position to monitor"""
        self.positions[symbol] = PositionState(
            symbol=symbol,
            entry_price=entry_price,
            entry_bar=entry_bar,
            qty=qty,
            current_price=entry_price,
            peak_price=entry_price,
            lowest_price=entry_price,
        )
    
    def remove_position(self, symbol: str):
        """Remove position from active monitoring"""
        if symbol in self.positions:
            pos = self.positions.pop(symbol)
            self.position_history.append(pos)
    
    def update_position(
        self,
        symbol: str,
        current_price: float,
        momentum_score: float,
        iteration: int,
        ts: datetime,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        hedged: bool = False,
    ) -> List[PositionAlert]:
        """
        Update position and check for alerts
        
        Returns:
            List of new alerts generated
        """
        if symbol not in self.positions:
            return []
        
        pos = self.positions[symbol]
        pos.update(current_price, momentum_score, iteration)
        pos.hedged = hedged
        
        new_alerts = []
        
        # Check for approaching take profit
        if take_profit and take_profit > pos.entry_price:
            distance_to_tp = (take_profit - current_price) / (take_profit - pos.entry_price)
            if 0 < distance_to_tp < self.tp_threshold:
                alert = PositionAlert(
                    ts=ts,
                    symbol=symbol,
                    alert_type=AlertType.APPROACHING_TP,
                    severity=1.0 - distance_to_tp,  # Closer = higher severity
                    message=f"Within {distance_to_tp*100:.1f}% of take profit (${take_profit:.2f})",
                    metric=current_price,
                    threshold=take_profit,
                    actions=["Consider taking some profit", "Tighten stop loss"],
                )
                new_alerts.append(alert)
        
        # Check for approaching stop loss
        if stop_loss and stop_loss < pos.entry_price:
            distance_to_sl = (current_price - stop_loss) / (pos.entry_price - stop_loss)
            if 0 < distance_to_sl < self.sl_threshold:
                alert = PositionAlert(
                    ts=ts,
                    symbol=symbol,
                    alert_type=AlertType.APPROACHING_SL,
                    severity=1.0 - distance_to_sl,  # Closer = higher severity
                    message=f"Within {distance_to_sl*100:.1f}% of stop loss (${stop_loss:.2f})",
                    metric=current_price,
                    threshold=stop_loss,
                    actions=["Reduce position", "Consider hedging"],
                )
                new_alerts.append(alert)
        
        # Check for large drawdown
        drawdown = pos.drawdown_from_peak()
        if drawdown > self.drawdown_threshold:
            alert = PositionAlert(
                ts=ts,
                symbol=symbol,
                alert_type=AlertType.DRAWDOWN_WARNING,
                severity=min(1.0, drawdown / 0.05),  # 5% drawdown = high severity
                message=f"Drawdown {drawdown*100:.1f}% from peak (${pos.peak_price:.2f})",
                metric=current_price,
                threshold=pos.peak_price * (1 - self.drawdown_threshold),
                actions=["Review thesis", "Consider stop loss order", "Evaluate hedge"],
            )
            new_alerts.append(alert)
        
        # Check for momentum shift
        if len(pos.momentum_history) > 5:
            momentum_trend = pos.recent_momentum_trend(window=5)
            if abs(momentum_trend) > self.momentum_shift_threshold:
                direction = "improving" if momentum_trend > 0 else "deteriorating"
                alert = PositionAlert(
                    ts=ts,
                    symbol=symbol,
                    alert_type=AlertType.MOMENTUM_SHIFT,
                    severity=abs(momentum_trend),
                    message=f"Momentum {direction} ({momentum_trend:+.3f})",
                    metric=pos.momentum_score,
                    threshold=self.momentum_shift_threshold,
                    actions=["Analyze momentum indicators", "Review entry thesis"],
                )
                new_alerts.append(alert)
        
        # Check for position age
        bars_held = pos.bars_held(iteration)
        if bars_held > self.age_threshold and iteration - pos.last_alert_bar > 50:
            alert = PositionAlert(
                ts=ts,
                symbol=symbol,
                alert_type=AlertType.POSITION_AGED,
                severity=0.5,
                message=f"Position held {bars_held} bars (>{self.age_threshold}) with {pos.current_pnl_pct:+.1%} PnL",
                metric=bars_held,
                threshold=self.age_threshold,
                actions=["Consider taking profit", "Reassess position thesis"],
            )
            new_alerts.append(alert)
        
        # Check for new hedge
        if hedged and not self._was_hedged(symbol):
            alert = PositionAlert(
                ts=ts,
                symbol=symbol,
                alert_type=AlertType.HEDGE_ACTIVATED,
                severity=0.3,  # Low severity, this is protective
                message=f"Hedge activated for profitable position ({pos.current_pnl_pct:+.1%})",
                metric=pos.current_pnl_pct,
                threshold=0.01,
                actions=["Monitor hedge costs", "Review hedge exit criteria"],
            )
            new_alerts.append(alert)
        
        # Store alerts and fire callbacks
        for alert in new_alerts:
            self.alert_history.append(alert)
            pos.alerts.append(alert)
            pos.last_alert_bar = iteration
            
            for callback in self.alert_callbacks:
                callback(alert)
        
        return new_alerts
    
    def _was_hedged(self, symbol: str) -> bool:
        """Check if position was previously hedged"""
        if symbol not in self.positions:
            return False
        pos = self.positions[symbol]
        return len([a for a in pos.alerts if a.alert_type == AlertType.HEDGE_ACTIVATED]) > 0
    
    def get_position_summary(self, symbol: str) -> Optional[Dict]:
        """Get summary of position state"""
        if symbol not in self.positions:
            return None
        
        pos = self.positions[symbol]
        return {
            "symbol": symbol,
            "qty": pos.qty,
            "entry_price": round(pos.entry_price, 2),
            "current_price": round(pos.current_price, 2),
            "pnl_pct": round(pos.current_pnl_pct * 100, 2),
            "peak_price": round(pos.peak_price, 2),
            "drawdown": round(pos.drawdown_from_peak() * 100, 2),
            "mfe": round(pos.max_favorable_excursion * 100, 2),
            "mae": round(pos.max_adverse_excursion * 100, 2),
            "momentum": round(pos.momentum_score, 3),
            "hedged": pos.hedged,
            "active_alerts": len([a for a in pos.alerts if a.ts.timestamp() > (datetime.now().timestamp() - 3600)])
        }
    
    def get_all_positions_summary(self) -> List[Dict]:
        """Get summary of all active positions"""
        summaries = []
        for symbol in self.positions:
            summary = self.get_position_summary(symbol)
            if summary:
                summaries.append(summary)
        return summaries
    
    def get_critical_alerts(self) -> List[PositionAlert]:
        """Get alerts with high severity (>0.7)"""
        return [a for a in self.alert_history if a.severity > 0.7]
    
    def get_recent_alerts(self, hours: int = 1) -> List[PositionAlert]:
        """Get recent alerts from last N hours"""
        cutoff_time = datetime.now().timestamp() - (hours * 3600)
        return [a for a in self.alert_history if a.ts.timestamp() > cutoff_time]
    
    def print_position_status(self):
        """Print status of all monitored positions"""
        if not self.positions:
            return
        
        print(f"   [MONITOR] Active positions: {len(self.positions)}", flush=True)
        
        # Show summary stats
        avg_pnl = sum(p.current_pnl_pct for p in self.positions.values()) / len(self.positions) if self.positions else 0
        max_dd = max((p.drawdown_from_peak() for p in self.positions.values()), default=0)
        
        print(
            f"   [MONITOR] Avg PnL: {avg_pnl:+.1%} | Max Drawdown: {max_dd:.1%} | "
            f"Hedged: {sum(1 for p in self.positions.values() if p.hedged)}/{len(self.positions)}",
            flush=True,
        )
        
        # Show alerts if any
        critical = self.get_critical_alerts()
        if critical:
            print(f"   [MONITOR] ⚠️  {len(critical)} critical alerts", flush=True)
            for alert in critical[-3:]:  # Show last 3 critical alerts
                print(f"            {alert}", flush=True)
