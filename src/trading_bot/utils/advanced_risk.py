"""Advanced risk controls: consecutive losses, position rotation, trade limits."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List


@dataclass
class TradeResult:
    """Single trade result for risk tracking."""
    symbol: str
    side: str  # "BUY" or "SELL"
    entry_price: float
    exit_price: float
    qty: int
    pnl: float
    pnl_pct: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_win(self) -> bool:
        return self.pnl > 0
    
    @property
    def is_loss(self) -> bool:
        return self.pnl < 0


class ConsecutiveLossTracker:
    """Track consecutive losses and enforce trading limits."""
    
    def __init__(self, max_consecutive_losses: int = 3, pause_duration_minutes: int = 60):
        """Initialize consecutive loss tracker.
        
        Args:
            max_consecutive_losses: Maximum consecutive losses before pausing
            pause_duration_minutes: How long to pause trading after max losses hit
        """
        self.max_consecutive_losses = max_consecutive_losses
        self.pause_duration_minutes = pause_duration_minutes
        self.consecutive_losses = 0
        self.last_loss_time: Optional[datetime] = None
        self.pause_until: Optional[datetime] = None
        self.trade_history: List[TradeResult] = []
    
    def record_trade(self, result: TradeResult) -> None:
        """Record a trade result.
        
        Args:
            result: TradeResult object
        """
        self.trade_history.append(result)
        
        if result.is_loss:
            self.consecutive_losses += 1
            self.last_loss_time = datetime.utcnow()
            
            # Trigger pause if max consecutive losses reached
            if self.consecutive_losses >= self.max_consecutive_losses:
                self.set_pause(self.pause_duration_minutes)
        else:
            # Reset counter on win
            self.consecutive_losses = 0
    
    def set_pause(self, duration_minutes: int) -> None:
        """Set trading pause.
        
        Args:
            duration_minutes: Pause duration in minutes
        """
        self.pause_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        print(f"[RISK] Trading paused after {self.consecutive_losses} consecutive losses")
        print(f"       Resume trading at: {self.pause_until.strftime('%H:%M:%S')}")
    
    def is_trading_paused(self) -> bool:
        """Check if trading is currently paused.
        
        Returns:
            True if trading is paused
        """
        if self.pause_until is None:
            return False
        
        if datetime.utcnow() >= self.pause_until:
            # Pause period expired
            self.pause_until = None
            self.consecutive_losses = 0  # Reset counter
            return False
        
        return True
    
    def get_pause_remaining_seconds(self) -> int:
        """Get remaining pause duration in seconds.
        
        Returns:
            Seconds remaining, or 0 if not paused
        """
        if self.pause_until is None:
            return 0
        
        remaining = (self.pause_until - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    def get_streak_stats(self) -> Dict:
        """Get current streak statistics.
        
        Returns:
            Dict with streak info
        """
        return {
            "consecutive_losses": self.consecutive_losses,
            "max_consecutive_losses": self.max_consecutive_losses,
            "consecutive_loss_limit_reached": self.consecutive_losses >= self.max_consecutive_losses,
            "is_paused": self.is_trading_paused(),
            "pause_remaining_seconds": self.get_pause_remaining_seconds(),
            "total_trades": len(self.trade_history),
        }


class DailyLossLimiter:
    """Enforce daily loss limits."""
    
    def __init__(self, max_daily_loss_amount: float, max_daily_loss_pct: float = 0.05):
        """Initialize daily loss limiter.
        
        Args:
            max_daily_loss_amount: Max loss in dollars per day
            max_daily_loss_pct: Max loss as % of bankroll per day
        """
        self.max_daily_loss_amount = max_daily_loss_amount
        self.max_daily_loss_pct = max_daily_loss_pct
        self.daily_start_time: Optional[datetime] = None
        self.daily_trades: List[TradeResult] = []
        self.daily_pnl = 0.0
    
    def reset_daily(self) -> None:
        """Reset daily counters (call at market open)."""
        self.daily_start_time = datetime.utcnow()
        self.daily_trades = []
        self.daily_pnl = 0.0
    
    def record_trade(self, result: TradeResult) -> None:
        """Record a trade to daily tracking.
        
        Args:
            result: TradeResult object
        """
        self.daily_trades.append(result)
        self.daily_pnl += result.pnl
    
    def has_reached_daily_limit(self) -> bool:
        """Check if daily loss limit reached.
        
        Returns:
            True if daily loss limit exceeded
        """
        return self.daily_pnl <= -self.max_daily_loss_amount
    
    def get_daily_stats(self) -> Dict:
        """Get daily trading statistics.
        
        Returns:
            Dict with daily PnL and trade count
        """
        winning_trades = sum(1 for t in self.daily_trades if t.is_win)
        losing_trades = sum(1 for t in self.daily_trades if t.is_loss)
        
        daily_loss_pct = 0
        if self.max_daily_loss_amount > 0:
            daily_loss_pct = abs(self.daily_pnl) / self.max_daily_loss_amount
        
        return {
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_pnl_vs_limit": round(self.daily_pnl / -self.max_daily_loss_amount, 1),
            "daily_loss_pct_of_limit": round(daily_loss_pct * 100, 1),
            "total_daily_trades": len(self.daily_trades),
            "daily_wins": winning_trades,
            "daily_losses": losing_trades,
            "daily_win_rate": round(winning_trades / len(self.daily_trades) * 100, 1) if self.daily_trades else 0,
        }


class PositionRotationManager:
    """Manage time-based position rotation."""
    
    def __init__(self, max_hold_time_hours: int = 24, rotation_check_interval_minutes: int = 60):
        """Initialize position rotation manager.
        
        Args:
            max_hold_time_hours: Maximum hours to hold a position
            rotation_check_interval_minutes: Check for rotation every N minutes
        """
        self.max_hold_time_hours = max_hold_time_hours
        self.rotation_check_interval_minutes = rotation_check_interval_minutes
        self.positions: Dict[str, datetime] = {}  # symbol -> entry_time
        self.last_rotation_check: Optional[datetime] = None
    
    def add_position(self, symbol: str, entry_time: Optional[datetime] = None) -> None:
        """Track a new position.
        
        Args:
            symbol: Trading symbol
            entry_time: Entry time (default: now)
        """
        self.positions[symbol] = entry_time or datetime.utcnow()
    
    def remove_position(self, symbol: str) -> None:
        """Remove closed position.
        
        Args:
            symbol: Trading symbol
        """
        if symbol in self.positions:
            del self.positions[symbol]
    
    def get_positions_to_rotate(self) -> List[Dict]:
        """Get positions that should be rotated (exited and re-entered).
        
        Returns:
            List of symbols that have exceeded hold time
        """
        now = datetime.utcnow()
        max_hold = timedelta(hours=self.max_hold_time_hours)
        
        positions_to_rotate = []
        for symbol, entry_time in self.positions.items():
            hold_duration = now - entry_time
            if hold_duration > max_hold:
                positions_to_rotate.append({
                    "symbol": symbol,
                    "entry_time": entry_time,
                    "hold_duration_hours": hold_duration.total_seconds() / 3600,
                })
        
        return positions_to_rotate
    
    def should_check_rotation(self) -> bool:
        """Check if it's time to check for position rotation.
        
        Returns:
            True if rotation check should run
        """
        if self.last_rotation_check is None:
            return True
        
        interval = timedelta(minutes=self.rotation_check_interval_minutes)
        return datetime.utcnow() - self.last_rotation_check > interval
    
    def get_rotation_stats(self) -> Dict:
        """Get position rotation statistics.
        
        Returns:
            Dict with rotation info
        """
        now = datetime.utcnow()
        max_hold = timedelta(hours=self.max_hold_time_hours)
        
        positions_due_for_rotation = 0
        avg_hold_hours = 0
        
        if self.positions:
            hold_times = [now - entry_time for entry_time in self.positions.values()]
            avg_hold_hours = sum(h.total_seconds() for h in hold_times) / len(hold_times) / 3600
            
            positions_due_for_rotation = sum(1 for h in hold_times if h > max_hold)
        
        return {
            "total_open_positions": len(self.positions),
            "positions_due_for_rotation": positions_due_for_rotation,
            "avg_hold_hours": round(avg_hold_hours, 1),
            "max_hold_hours": self.max_hold_time_hours,
        }


class AdvancedRiskManager:
    """Master risk manager combining all advanced risk controls."""
    
    def __init__(self, 
                 max_consecutive_losses: int = 3,
                 max_daily_loss: float = 5000,
                 max_hold_hours: int = 24):
        """Initialize advanced risk manager.
        
        Args:
            max_consecutive_losses: Max consecutive losses before pause
            max_daily_loss: Max daily loss in dollars
            max_hold_hours: Max hours to hold a position
        """
        self.consecutive_loss_tracker = ConsecutiveLossTracker(
            max_consecutive_losses=max_consecutive_losses
        )
        self.daily_loss_limiter = DailyLossLimiter(max_daily_loss_amount=max_daily_loss)
        self.position_rotator = PositionRotationManager(max_hold_time_hours=max_hold_hours)
    
    def record_trade(self, result: TradeResult) -> Dict:
        """Record trade and check all risk limits.
        
        Args:
            result: TradeResult object
            
        Returns:
            Dict with risk checks
        """
        self.consecutive_loss_tracker.record_trade(result)
        self.daily_loss_limiter.record_trade(result)
        
        risk_checks = {
            "is_trading_paused": self.consecutive_loss_tracker.is_trading_paused(),
            "consecutive_losses": self.consecutive_loss_tracker.consecutive_losses,
            "daily_loss_limit_reached": self.daily_loss_limiter.has_reached_daily_limit(),
            "daily_pnl": self.daily_loss_limiter.daily_pnl,
        }
        
        return risk_checks
    
    def check_position_rotation(self) -> List[Dict]:
        """Check if any positions need rotation.
        
        Returns:
            List of positions to rotate
        """
        if self.position_rotator.should_check_rotation():
            self.position_rotator.last_rotation_check = datetime.utcnow()
            return self.position_rotator.get_positions_to_rotate()
        
        return []
    
    def get_risk_status(self) -> Dict:
        """Get comprehensive risk status.
        
        Returns:
            Dict with all risk metrics
        """
        return {
            "consecutive_loss_tracker": self.consecutive_loss_tracker.get_streak_stats(),
            "daily_loss_limiter": self.daily_loss_limiter.get_daily_stats(),
            "position_rotator": self.position_rotator.get_rotation_stats(),
        }
    
    def print_risk_status(self) -> None:
        """Print formatted risk status."""
        status = self.get_risk_status()
        
        print("\n[ADVANCED RISK STATUS]")
        
        # Consecutive losses
        cls_status = status["consecutive_loss_tracker"]
        print(f"  Consecutive Losses: {cls_status['consecutive_losses']}/{cls_status['max_consecutive_losses']}", end="")
        if cls_status["is_paused"]:
            print(f" - PAUSED ({cls_status['pause_remaining_seconds']}s remaining)")
        else:
            print()
        
        # Daily loss limit
        dll_status = status["daily_loss_limiter"]
        daily_loss_pct = dll_status["daily_loss_pct_of_limit"]
        print(f"  Daily P&L: ${dll_status['daily_pnl']:+,.2f} ({daily_loss_pct:.0f}% of limit)")
        print(f"  Today's Trades: {dll_status['total_daily_trades']} ({dll_status['daily_win_rate']:.0f}% win rate)")
        
        # Position rotation
        pr_status = status["position_rotator"]
        print(f"  Open Positions: {pr_status['total_open_positions']} "
              f"(avg hold: {pr_status['avg_hold_hours']}h, "
              f"rotation due: {pr_status['positions_due_for_rotation']})")
        print()
