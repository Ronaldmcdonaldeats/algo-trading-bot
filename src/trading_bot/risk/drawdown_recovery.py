"""Drawdown Recovery System - Auto-pause and gradual resume trading

Features:
- Automatic pause after daily loss threshold
- Gradual position size reduction during recovery
- Recovery tracking and metrics
- Drawdown history and analysis
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import json


@dataclass
class DrawdownEvent:
    """Record of a drawdown event"""
    event_id: str
    start_date: datetime
    end_date: Optional[datetime]
    peak_equity: float
    trough_equity: float
    drawdown_pct: float
    days_to_recover: Optional[int] = None
    recovery_strategy: str = "GRADUAL"  # GRADUAL, AGGRESSIVE, CONSERVATIVE
    status: str = "RECOVERING"  # ACTIVE, RECOVERING, RECOVERED
    
    def to_dict(self) -> dict:
        return {
            'event_id': self.event_id,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'peak_equity': self.peak_equity,
            'trough_equity': self.trough_equity,
            'drawdown_pct': self.drawdown_pct,
            'days_to_recover': self.days_to_recover,
            'recovery_strategy': self.recovery_strategy,
            'status': self.status,
        }


@dataclass
class RecoveryPhase:
    """Phase of drawdown recovery"""
    phase_num: int
    start_equity: float
    target_equity: float
    position_size_multiplier: float  # e.g., 0.5 = 50% normal position
    max_trades_per_day: int
    duration_days: int


class DrawdownRecoveryManager:
    """Manage drawdown recovery process"""
    
    def __init__(self,
                 daily_loss_threshold: float = 0.05,  # 5% daily loss triggers pause
                 portfolio_loss_threshold: float = 0.20,  # 20% portfolio loss stops trading
                 recovery_phases: Optional[List[RecoveryPhase]] = None):
        """
        Initialize recovery manager
        
        Args:
            daily_loss_threshold: Stop trading if daily P&L drops below this
            portfolio_loss_threshold: Stop all trading if portfolio drops below this
            recovery_phases: Custom recovery phases (None = use defaults)
        """
        self.daily_loss_threshold = daily_loss_threshold
        self.portfolio_loss_threshold = portfolio_loss_threshold
        
        # Default recovery phases
        if recovery_phases is None:
            recovery_phases = [
                RecoveryPhase(1, 0, 0.5, 0.3, 2, 3),      # Phase 1: 30% size, 2 trades/day, 3 days
                RecoveryPhase(2, 0.5, 0.75, 0.5, 5, 3),    # Phase 2: 50% size, 5 trades/day, 3 days
                RecoveryPhase(3, 0.75, 1.0, 0.8, 10, 3),   # Phase 3: 80% size, 10 trades/day, 3 days
            ]
        self.recovery_phases = recovery_phases
        
        # Tracking
        self.drawdown_events: Dict[str, DrawdownEvent] = {}
        self.current_event: Optional[DrawdownEvent] = None
        self.trading_paused = False
        self.pause_reason = ""
    
    def check_daily_loss(self, daily_pnl: float, total_equity: float) -> bool:
        """
        Check if daily loss exceeded threshold
        
        Returns:
            True if should pause trading
        """
        daily_pnl_pct = daily_pnl / total_equity if total_equity > 0 else 0
        
        if daily_pnl_pct <= -self.daily_loss_threshold:
            self.trading_paused = True
            self.pause_reason = f"Daily loss {daily_pnl_pct:.1%} exceeded threshold {-self.daily_loss_threshold:.1%}"
            return True
        
        return False
    
    def check_portfolio_loss(self, peak_equity: float, current_equity: float) -> bool:
        """
        Check if portfolio loss exceeded critical threshold
        
        Returns:
            True if portfolio loss critical
        """
        loss_pct = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
        
        if loss_pct >= self.portfolio_loss_threshold:
            self.trading_paused = True
            self.pause_reason = f"Portfolio loss {loss_pct:.1%} exceeded critical threshold"
            return True
        
        return False
    
    def detect_drawdown(self, peak_equity: float, current_equity: float, 
                        event_id: str = None) -> Optional[DrawdownEvent]:
        """
        Detect and record new drawdown
        
        Returns:
            DrawdownEvent if new drawdown detected, None otherwise
        """
        drawdown_pct = (peak_equity - current_equity) / peak_equity if peak_equity > 0 else 0
        
        # Only trigger on significant drawdowns
        if drawdown_pct >= 0.05:  # 5% minimum
            if event_id is None:
                event_id = f"DD_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            event = DrawdownEvent(
                event_id=event_id,
                start_date=datetime.now(),
                end_date=None,
                peak_equity=peak_equity,
                trough_equity=current_equity,
                drawdown_pct=drawdown_pct,
                status="ACTIVE"
            )
            
            self.current_event = event
            self.drawdown_events[event_id] = event
            self.trading_paused = True
            
            return event
        
        return None
    
    def get_recovery_phase(self, current_equity: float, 
                          start_equity: float) -> Optional[RecoveryPhase]:
        """
        Get current recovery phase based on equity recovery
        
        Returns:
            RecoveryPhase or None if not in recovery
        """
        if self.current_event is None:
            return None
        
        # Calculate recovery progress
        loss = self.current_event.peak_equity - self.current_event.trough_equity
        current_recovery = (current_equity - self.current_event.trough_equity) / loss if loss > 0 else 0
        
        for phase in self.recovery_phases:
            if phase.start_equity <= current_recovery < phase.target_equity:
                return phase
        
        # All phases complete
        return None
    
    def get_position_size_multiplier(self, current_equity: float,
                                    start_equity: float) -> float:
        """
        Get position size multiplier for current recovery phase
        
        Returns:
            Multiplier (e.g., 0.5 = use 50% of normal position size)
        """
        phase = self.get_recovery_phase(current_equity, start_equity)
        
        if phase is None:
            # Recovery complete
            self.trading_paused = False
            if self.current_event:
                self.current_event.status = "RECOVERED"
                self.current_event.end_date = datetime.now()
                days_to_recover = (self.current_event.end_date - self.current_event.start_date).days
                self.current_event.days_to_recover = days_to_recover
            return 1.0
        
        return phase.position_size_multiplier
    
    def get_max_trades_today(self, current_equity: float,
                            start_equity: float) -> int:
        """
        Get max trades allowed today during recovery
        
        Returns:
            Max number of trades
        """
        phase = self.get_recovery_phase(current_equity, start_equity)
        
        if phase is None:
            return 999  # Unlimited
        
        return phase.max_trades_per_day
    
    def should_trade(self, current_equity: float, peak_equity: float,
                    start_equity: float, trades_today: int = 0) -> Tuple[bool, str]:
        """
        Determine if trading should be allowed
        
        Returns:
            (allow_trade, reason)
        """
        # Check portfolio loss
        if self.check_portfolio_loss(peak_equity, current_equity):
            return False, "PORTFOLIO_LOSS_CRITICAL"
        
        # Check if in recovery phase
        phase = self.get_recovery_phase(current_equity, start_equity)
        
        if phase is None:
            # Recovery complete
            self.trading_paused = False
            return True, "RECOVERY_COMPLETE"
        
        # In recovery - check trade limit
        if trades_today >= phase.max_trades_per_day:
            return False, f"TRADE_LIMIT_REACHED ({trades_today}/{phase.max_trades_per_day})"
        
        return True, "IN_RECOVERY"
    
    def end_recovery(self, event_id: str) -> bool:
        """Mark recovery as complete"""
        if event_id not in self.drawdown_events:
            return False
        
        event = self.drawdown_events[event_id]
        event.status = "RECOVERED"
        event.end_date = datetime.now()
        event.days_to_recover = (event.end_date - event.start_date).days
        
        self.current_event = None
        self.trading_paused = False
        
        return True
    
    def get_recovery_metrics(self, event_id: str = None) -> Optional[Dict]:
        """Get metrics for recovery event"""
        if event_id is None:
            event = self.current_event
        else:
            event = self.drawdown_events.get(event_id)
        
        if event is None:
            return None
        
        return {
            'event_id': event.event_id,
            'drawdown_pct': event.drawdown_pct,
            'peak_equity': event.peak_equity,
            'trough_equity': event.trough_equity,
            'loss_amount': event.peak_equity - event.trough_equity,
            'start_date': event.start_date.isoformat(),
            'end_date': event.end_date.isoformat() if event.end_date else None,
            'days_to_recover': event.days_to_recover,
            'status': event.status,
        }
    
    def get_all_drawdowns(self) -> List[Dict]:
        """Get all recorded drawdown events"""
        return [event.to_dict() for event in self.drawdown_events.values()]
    
    def get_recovery_status(self) -> Dict:
        """Get current recovery status"""
        if self.current_event is None:
            return {
                'in_recovery': False,
                'current_event': None,
                'trading_paused': False,
            }
        
        event = self.current_event
        loss = event.peak_equity - event.trough_equity
        
        return {
            'in_recovery': True,
            'current_event': event.event_id,
            'event_start': event.start_date.isoformat(),
            'peak_equity': event.peak_equity,
            'trough_equity': event.trough_equity,
            'total_loss': loss,
            'loss_pct': event.drawdown_pct,
            'trading_paused': self.trading_paused,
            'pause_reason': self.pause_reason,
            'status': event.status,
        }
    
    def reset_pause(self):
        """Manually resume trading (e.g., after review)"""
        self.trading_paused = False
        self.pause_reason = ""


class DrawdownTracker:
    """Track drawdown statistics and history"""
    
    def __init__(self):
        self.peak_equity = 0
        self.drawdown_history: List[DrawdownEvent] = []
        self.current_drawdown = 0
        self.max_drawdown = 0
        self.days_since_peak = 0
    
    def update(self, current_equity: float):
        """Update tracking with new equity"""
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
            self.current_drawdown = 0
            self.days_since_peak = 0
        else:
            self.current_drawdown = (self.peak_equity - current_equity) / self.peak_equity
            self.max_drawdown = max(self.max_drawdown, self.current_drawdown)
            self.days_since_peak += 1
    
    def get_stats(self) -> Dict:
        """Get drawdown statistics"""
        return {
            'peak_equity': self.peak_equity,
            'current_drawdown_pct': self.current_drawdown,
            'max_drawdown_pct': self.max_drawdown,
            'days_since_peak': self.days_since_peak,
        }
