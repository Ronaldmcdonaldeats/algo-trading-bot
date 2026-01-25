"""Monitoring and Alerts System - Real-time portfolio monitoring and notifications"""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import numpy as np


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of alerts"""
    PRICE_ALERT = "price"
    DRAWDOWN_ALERT = "drawdown"
    POSITION_SIZE = "position_size"
    CORRELATION = "correlation"
    VOLATILITY = "volatility"
    CIRCUIT_BREAKER = "circuit_breaker"
    STALE_DATA = "stale_data"
    BROKER_HEALTH = "broker_health"
    EXECUTION = "execution"
    REBALANCE = "rebalance"


@dataclass
class Alert:
    """Alert message"""
    alert_id: str
    alert_type: AlertType
    level: AlertLevel
    symbol: str
    message: str
    timestamp: datetime
    value: Optional[float] = None
    threshold: Optional[float] = None
    metadata: Dict = None
    is_acknowledged: bool = False
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AlertSystem:
    """Manage and route alerts"""
    
    def __init__(self):
        self.alerts: List[Alert] = []
        self.handlers: Dict[AlertLevel, List[Callable]] = {
            AlertLevel.INFO: [],
            AlertLevel.WARNING: [],
            AlertLevel.CRITICAL: []
        }
        self.active_alerts: Dict[str, Alert] = {}  # By alert_id
        self.alert_history: List[Alert] = []
    
    def register_handler(self, level: AlertLevel, handler: Callable) -> None:
        """Register an alert handler
        
        Args:
            level: Alert level to handle
            handler: Callable taking Alert as argument
        """
        self.handlers[level].append(handler)
    
    def create_alert(self, alert_type: AlertType, level: AlertLevel,
                    symbol: str, message: str, value: Optional[float] = None,
                    threshold: Optional[float] = None) -> Alert:
        """Create and dispatch alert"""
        alert = Alert(
            alert_id=f"{alert_type.value}_{symbol}_{datetime.now().timestamp()}",
            alert_type=alert_type,
            level=level,
            symbol=symbol,
            message=message,
            timestamp=datetime.now(),
            value=value,
            threshold=threshold
        )
        
        self.alerts.append(alert)
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert.copy() if hasattr(alert, 'copy') else alert)
        
        # Dispatch to handlers
        self._dispatch_alert(alert)
        
        return alert
    
    def _dispatch_alert(self, alert: Alert) -> None:
        """Send alert to registered handlers"""
        for handler in self.handlers[alert.level]:
            try:
                handler(alert)
            except Exception as e:
                print(f"Error dispatching alert: {e}")
    
    def acknowledge_alert(self, alert_id: str) -> None:
        """Mark alert as acknowledged"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].is_acknowledged = True
    
    def clear_alert(self, alert_id: str) -> None:
        """Clear alert"""
        if alert_id in self.active_alerts:
            del self.active_alerts[alert_id]
    
    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """Get active alerts, optionally filtered by level"""
        alerts = list(self.active_alerts.values())
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts
    
    def get_critical_alerts(self) -> List[Alert]:
        """Get all critical alerts"""
        return self.get_active_alerts(AlertLevel.CRITICAL)
    
    def has_critical_alerts(self) -> bool:
        """Check if any critical alerts exist"""
        return len(self.get_critical_alerts()) > 0


class CircuitBreaker:
    """Trading circuit breaker - halt trading on extreme events"""
    
    def __init__(self, alert_system: AlertSystem, 
                 max_loss_pct: float = 0.05,
                 max_intraday_loss_pct: float = 0.02,
                 max_position_loss_pct: float = 0.10):
        """
        Args:
            alert_system: Alert system for notifications
            max_loss_pct: Stop at cumulative loss %
            max_intraday_loss_pct: Stop at intraday loss %
            max_position_loss_pct: Stop if single position loses >X%
        """
        self.alert_system = alert_system
        self.max_loss_pct = max_loss_pct
        self.max_intraday_loss_pct = max_intraday_loss_pct
        self.max_position_loss_pct = max_position_loss_pct
        
        self.is_triggered = False
        self.trigger_time: Optional[datetime] = None
        self.trigger_reason = ""
        self.daily_high = 0.0
        self.session_start_value = 0.0
    
    def check_circuit_breaker(self, portfolio_value: float, 
                             current_loss_pct: float,
                             position_losses: Dict[str, float]) -> bool:
        """Check if circuit breaker should trigger
        
        Args:
            portfolio_value: Current portfolio value
            current_loss_pct: Current cumulative loss %
            position_losses: Dict of {symbol: loss_pct}
            
        Returns:
            True if circuit breaker triggered
        """
        if self.session_start_value == 0:
            self.session_start_value = portfolio_value
        
        # Update daily high
        self.daily_high = max(self.daily_high, portfolio_value)
        
        # Check cumulative loss
        if current_loss_pct < -self.max_loss_pct:
            self.is_triggered = True
            self.trigger_reason = f"Cumulative loss {current_loss_pct*100:.2f}%"
            self.trigger_time = datetime.now()
            
            self.alert_system.create_alert(
                AlertType.CIRCUIT_BREAKER,
                AlertLevel.CRITICAL,
                "PORTFOLIO",
                f"Circuit breaker triggered: {self.trigger_reason}",
                value=current_loss_pct * 100,
                threshold=self.max_loss_pct * 100
            )
            return True
        
        # Check intraday loss
        intraday_loss = (portfolio_value - self.daily_high) / self.daily_high
        if intraday_loss < -self.max_intraday_loss_pct:
            self.is_triggered = True
            self.trigger_reason = f"Intraday loss {intraday_loss*100:.2f}%"
            self.trigger_time = datetime.now()
            
            self.alert_system.create_alert(
                AlertType.CIRCUIT_BREAKER,
                AlertLevel.CRITICAL,
                "PORTFOLIO",
                f"Circuit breaker triggered: {self.trigger_reason}",
                value=intraday_loss * 100,
                threshold=self.max_intraday_loss_pct * 100
            )
            return True
        
        # Check position losses
        for symbol, loss_pct in position_losses.items():
            if loss_pct < -self.max_position_loss_pct:
                self.is_triggered = True
                self.trigger_reason = f"Position {symbol} loss {loss_pct*100:.2f}%"
                self.trigger_time = datetime.now()
                
                self.alert_system.create_alert(
                    AlertType.CIRCUIT_BREAKER,
                    AlertLevel.WARNING,
                    symbol,
                    f"Large position loss: {loss_pct*100:.2f}%",
                    value=loss_pct * 100,
                    threshold=self.max_position_loss_pct * 100
                )
                break
        
        return self.is_triggered
    
    def reset(self) -> None:
        """Reset circuit breaker"""
        self.is_triggered = False
        self.trigger_time = None
        self.trigger_reason = ""
        self.daily_high = 0.0
        self.session_start_value = 0.0


class HealthMonitor:
    """Monitor system health"""
    
    def __init__(self, alert_system: AlertSystem):
        self.alert_system = alert_system
        self.checks: Dict[str, Callable] = {}
        self.last_check_time: Dict[str, datetime] = {}
        self.health_status: Dict[str, bool] = {}
    
    def register_health_check(self, name: str, check_func: Callable) -> None:
        """Register a health check
        
        Args:
            name: Check name
            check_func: Callable returning (is_healthy: bool, message: str)
        """
        self.checks[name] = check_func
        self.health_status[name] = True
    
    def run_health_checks(self) -> Dict[str, Dict]:
        """Run all health checks
        
        Returns:
            Dict of {check_name: {healthy, message, timestamp}}
        """
        results = {}
        
        for name, check_func in self.checks.items():
            try:
                is_healthy, message = check_func()
                results[name] = {
                    "healthy": is_healthy,
                    "message": message,
                    "timestamp": datetime.now()
                }
                
                # Create alert if status changed
                if is_healthy != self.health_status[name]:
                    level = AlertLevel.INFO if is_healthy else AlertLevel.CRITICAL
                    self.alert_system.create_alert(
                        AlertType.BROKER_HEALTH,
                        level,
                        "SYSTEM",
                        f"Health check '{name}': {message}"
                    )
                
                self.health_status[name] = is_healthy
                self.last_check_time[name] = datetime.now()
                
            except Exception as e:
                results[name] = {
                    "healthy": False,
                    "message": str(e),
                    "timestamp": datetime.now()
                }
                
                self.alert_system.create_alert(
                    AlertType.BROKER_HEALTH,
                    AlertLevel.WARNING,
                    "SYSTEM",
                    f"Health check '{name}' failed: {str(e)}"
                )
        
        return results
    
    def is_system_healthy(self) -> bool:
        """Check overall system health"""
        return all(self.health_status.values())


class VolatilityMonitor:
    """Monitor and alert on volatility changes"""
    
    def __init__(self, alert_system: AlertSystem,
                 vol_spike_threshold: float = 1.5,
                 vol_window: int = 20):
        """
        Args:
            alert_system: Alert system
            vol_spike_threshold: Flag if vol > X * average (e.g., 1.5x)
            vol_window: Window for calculating average volatility
        """
        self.alert_system = alert_system
        self.vol_spike_threshold = vol_spike_threshold
        self.vol_window = vol_window
        self.volatility_history: Dict[str, List[float]] = {}
    
    def check_volatility(self, symbol: str, returns: List[float]) -> bool:
        """Check for volatility spikes
        
        Args:
            symbol: Asset symbol
            returns: Recent returns
            
        Returns:
            True if spike detected
        """
        if len(returns) < 2:
            return False
        
        current_vol = np.std(returns) * np.sqrt(252)  # Annualized
        
        # Keep history
        if symbol not in self.volatility_history:
            self.volatility_history[symbol] = []
        
        self.volatility_history[symbol].append(current_vol)
        
        # Keep only recent history
        if len(self.volatility_history[symbol]) > self.vol_window * 5:
            self.volatility_history[symbol] = self.volatility_history[symbol][-self.vol_window * 5:]
        
        # Compare to average
        if len(self.volatility_history[symbol]) > self.vol_window:
            recent_vol = self.volatility_history[symbol][-self.vol_window:]
            avg_vol = np.mean(recent_vol)
            
            if current_vol > avg_vol * self.vol_spike_threshold:
                self.alert_system.create_alert(
                    AlertType.VOLATILITY,
                    AlertLevel.WARNING,
                    symbol,
                    f"Volatility spike detected: {current_vol*100:.1f}%",
                    value=current_vol * 100,
                    threshold=avg_vol * self.vol_spike_threshold * 100
                )
                return True
        
        return False
