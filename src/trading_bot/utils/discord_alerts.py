"""Discord alerts and live trading notifications with webhooks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging
import asyncio
import aiohttp
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SUCCESS = "success"


class AlertCategory(Enum):
    """Alert categories."""
    TRADE_ENTRY = "trade_entry"
    TRADE_EXIT = "trade_exit"
    RISK_ALERT = "risk_alert"
    CIRCUIT_BREAKER = "circuit_breaker"
    POSITION_ALERT = "position_alert"
    DAILY_SUMMARY = "daily_summary"
    ERROR = "error"
    PERFORMANCE = "performance"


@dataclass
class Alert:
    """Single alert message."""
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def emoji(self) -> str:
        """Get emoji for severity."""
        emojis = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.SUCCESS: "✅",
        }
        return emojis.get(self.severity, "📢")
    
    @property
    def color(self) -> int:
        """Get Discord embed color."""
        colors = {
            AlertSeverity.INFO: 0x3498db,      # Blue
            AlertSeverity.WARNING: 0xf39c12,   # Orange
            AlertSeverity.CRITICAL: 0xe74c3c,  # Red
            AlertSeverity.SUCCESS: 0x2ecc71,   # Green
        }
        return colors.get(self.severity, 0x95a5a6)


@dataclass
class TradeAlert:
    """Alert for trade execution."""
    symbol: str
    action: str  # BUY, SELL
    quantity: int
    price: float
    expected_value: float
    strategy: str
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def formatted_message(self) -> str:
        """Format as message."""
        return f"{self.action} {self.quantity} {self.symbol} @ ${self.price:.2f}"


@dataclass
class RiskAlert:
    """Alert for risk conditions."""
    alert_type: str  # drawdown, concentration, liquidity, volatility
    symbol: Optional[str] = None
    value: float = 0.0
    threshold: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DailySummary:
    """Daily trading summary."""
    date: datetime
    trades_executed: int
    winning_trades: int
    losing_trades: int
    gross_pnl: float
    net_pnl: float
    win_rate: float
    largest_win: float
    largest_loss: float
    total_return_pct: float


class DiscordWebhook:
    """Discord webhook client for sending alerts."""
    
    def __init__(self, webhook_url: str):
        """Initialize Discord webhook.
        
        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session.
        
        Returns:
            ClientSession
        """
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def send_message(self, content: str) -> bool:
        """Send simple text message.
        
        Args:
            content: Message content
            
        Returns:
            True if successful
        """
        try:
            session = await self._get_session()
            payload = {"content": content}
            
            async with session.post(self.webhook_url, json=payload) as resp:
                return resp.status == 204
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return False
    
    async def send_embed(
        self,
        title: str,
        description: str,
        color: int = 0x3498db,
        fields: Optional[Dict[str, str]] = None,
        footer: Optional[str] = None,
    ) -> bool:
        """Send embed message.
        
        Args:
            title: Embed title
            description: Embed description
            color: Embed color (hex)
            fields: Dict of field_name -> field_value
            footer: Footer text
            
        Returns:
            True if successful
        """
        try:
            session = await self._get_session()
            
            embed = {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            if fields:
                embed["fields"] = [
                    {"name": k, "value": v, "inline": True}
                    for k, v in fields.items()
                ]
            
            if footer:
                embed["footer"] = {"text": footer}
            
            payload = {"embeds": [embed]}
            
            async with session.post(self.webhook_url, json=payload) as resp:
                return resp.status == 204
        except Exception as e:
            logger.error(f"Failed to send Discord embed: {e}")
            return False
    
    async def close(self):
        """Close session."""
        if self.session:
            await self.session.close()


class AlertNotifier:
    """Manages alerts and notifications."""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """Initialize notifier.
        
        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook = DiscordWebhook(webhook_url) if webhook_url else None
        self.alert_history: List[Alert] = []
        self.muted_categories: List[AlertCategory] = []
    
    def mute_category(self, category: AlertCategory) -> None:
        """Mute alerts for category.
        
        Args:
            category: Alert category
        """
        if category not in self.muted_categories:
            self.muted_categories.append(category)
            logger.info(f"Muted {category.value} alerts")
    
    def unmute_category(self, category: AlertCategory) -> None:
        """Unmute alerts for category.
        
        Args:
            category: Alert category
        """
        if category in self.muted_categories:
            self.muted_categories.remove(category)
            logger.info(f"Unmuted {category.value} alerts")
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert.
        
        Args:
            alert: Alert to send
            
        Returns:
            True if successful
        """
        # Check if muted
        if alert.category in self.muted_categories:
            logger.debug(f"Alert muted: {alert.title}")
            return True
        
        self.alert_history.append(alert)
        
        if not self.webhook:
            logger.warning("No Discord webhook configured")
            return False
        
        # Format message
        emoji = alert.emoji
        title = f"{emoji} {alert.title}"
        
        # Build fields
        fields = {
            "Category": alert.category.value,
            "Severity": alert.severity.value,
        }
        fields.update(alert.details)
        
        # Send embed
        success = await self.webhook.send_embed(
            title=title,
            description=alert.message,
            color=alert.color,
            fields=fields,
            footer=f"Trading Bot • {alert.timestamp.strftime('%H:%M:%S')}",
        )
        
        if success:
            logger.info(f"Alert sent: {alert.title}")
        
        return success
    
    async def send_trade_alert(self, trade: TradeAlert) -> bool:
        """Send trade execution alert.
        
        Args:
            trade: Trade alert
            
        Returns:
            True if successful
        """
        alert = Alert(
            category=AlertCategory.TRADE_ENTRY if trade.action == "BUY" else AlertCategory.TRADE_EXIT,
            severity=AlertSeverity.SUCCESS,
            title=f"{trade.action} {trade.symbol}",
            message=trade.formatted_message,
            details={
                "Symbol": trade.symbol,
                "Action": trade.action,
                "Quantity": str(trade.quantity),
                "Price": f"${trade.price:.2f}",
                "Value": f"${trade.expected_value:,.0f}",
                "Strategy": trade.strategy,
                "Confidence": f"{trade.confidence:.1%}",
            },
        )
        
        return await self.send_alert(alert)
    
    async def send_risk_alert(self, risk: RiskAlert) -> bool:
        """Send risk alert.
        
        Args:
            risk: Risk alert
            
        Returns:
            True if successful
        """
        # Determine severity
        if risk.value > risk.threshold * 1.5:
            severity = AlertSeverity.CRITICAL
        elif risk.value > risk.threshold:
            severity = AlertSeverity.WARNING
        else:
            severity = AlertSeverity.INFO
        
        details = {
            "Type": risk.alert_type.replace("_", " ").title(),
            "Current": f"{risk.value:.2f}",
            "Threshold": f"{risk.threshold:.2f}",
        }
        
        if risk.symbol:
            details["Symbol"] = risk.symbol
        
        alert = Alert(
            category=AlertCategory.RISK_ALERT,
            severity=severity,
            title=f"Risk Alert: {risk.alert_type}",
            message=f"{risk.alert_type} threshold exceeded",
            details=details,
        )
        
        return await self.send_alert(alert)
    
    async def send_daily_summary(self, summary: DailySummary) -> bool:
        """Send daily summary.
        
        Args:
            summary: Daily summary
            
        Returns:
            True if successful
        """
        # Determine severity based on performance
        if summary.net_pnl > 0:
            severity = AlertSeverity.SUCCESS
            emoji_prefix = "📈"
        else:
            severity = AlertSeverity.WARNING
            emoji_prefix = "📉"
        
        fields = {
            "Date": summary.date.strftime("%Y-%m-%d"),
            "Trades": str(summary.trades_executed),
            "Wins": f"{summary.winning_trades}/{summary.trades_executed}",
            "Win Rate": f"{summary.win_rate:.1%}",
            "Net P&L": f"${summary.net_pnl:,.2f}",
            "Return": f"{summary.total_return_pct:+.2f}%",
            "Best Trade": f"${summary.largest_win:,.2f}",
            "Worst Trade": f"${summary.largest_loss:,.2f}",
        }
        
        alert = Alert(
            category=AlertCategory.DAILY_SUMMARY,
            severity=severity,
            title=f"{emoji_prefix} Daily Summary - {summary.date.strftime('%B %d')}",
            message=f"Trading day summary: {summary.trades_executed} trades executed",
            details=fields,
        )
        
        return await self.send_alert(alert)
    
    async def send_circuit_breaker_alert(
        self,
        trigger_type: str,
        current_value: float,
        threshold: float,
    ) -> bool:
        """Send circuit breaker alert.
        
        Args:
            trigger_type: Type of trigger (drawdown, loss, etc.)
            current_value: Current value
            threshold: Threshold value
            
        Returns:
            True if successful
        """
        alert = Alert(
            category=AlertCategory.CIRCUIT_BREAKER,
            severity=AlertSeverity.CRITICAL,
            title="🛑 CIRCUIT BREAKER TRIGGERED",
            message=f"Trading has been halted due to {trigger_type}",
            details={
                "Trigger": trigger_type,
                "Current": f"{current_value:.2f}",
                "Threshold": f"{threshold:.2f}",
                "Status": "TRADING PAUSED",
            },
        )
        
        return await self.send_alert(alert)


class NotificationQueue:
    """Queue for async notification sending."""
    
    def __init__(self, notifier: AlertNotifier, batch_size: int = 5):
        """Initialize queue.
        
        Args:
            notifier: AlertNotifier instance
            batch_size: Batch size for processing
        """
        self.notifier = notifier
        self.batch_size = batch_size
        self.queue: List[Alert] = []
        self.processing = False
    
    def queue_alert(self, alert: Alert) -> None:
        """Queue alert for sending.
        
        Args:
            alert: Alert to queue
        """
        self.queue.append(alert)
    
    async def process_queue(self) -> None:
        """Process queued alerts."""
        if self.processing:
            return
        
        self.processing = True
        
        try:
            while self.queue:
                batch = self.queue[:self.batch_size]
                self.queue = self.queue[self.batch_size:]
                
                # Send batch concurrently
                await asyncio.gather(
                    *[self.notifier.send_alert(alert) for alert in batch],
                    return_exceptions=True
                )
        finally:
            self.processing = False


class LiveTradingNotifier:
    """Real-time trading notifications."""
    
    def __init__(self, notifier: AlertNotifier):
        """Initialize notifier.
        
        Args:
            notifier: AlertNotifier instance
        """
        self.notifier = notifier
        self.last_notifications: Dict[str, datetime] = {}
        self.notification_cooldown = 60  # seconds
    
    async def notify_trade_execution(
        self,
        symbol: str,
        action: str,
        quantity: int,
        price: float,
        strategy: str,
        confidence: float = 0.0,
    ) -> bool:
        """Notify trade execution.
        
        Args:
            symbol: Stock symbol
            action: BUY or SELL
            quantity: Number of shares
            price: Execution price
            strategy: Strategy name
            confidence: Confidence score
            
        Returns:
            True if successful
        """
        trade = TradeAlert(
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            expected_value=quantity * price,
            strategy=strategy,
            confidence=confidence,
        )
        
        return await self.notifier.send_trade_alert(trade)
    
    async def notify_position_update(
        self,
        symbol: str,
        quantity: int,
        price: float,
        pnl: float,
        pnl_pct: float,
    ) -> bool:
        """Notify position update.
        
        Args:
            symbol: Stock symbol
            quantity: Current quantity
            price: Current price
            pnl: Unrealized P&L
            pnl_pct: P&L percentage
            
        Returns:
            True if successful
        """
        severity = AlertSeverity.SUCCESS if pnl > 0 else AlertSeverity.WARNING
        emoji = "📈" if pnl > 0 else "📉"
        
        alert = Alert(
            category=AlertCategory.POSITION_ALERT,
            severity=severity,
            title=f"{emoji} {symbol} Position Update",
            message=f"{quantity} shares @ ${price:.2f}",
            details={
                "Symbol": symbol,
                "Quantity": str(quantity),
                "Price": f"${price:.2f}",
                "P&L": f"${pnl:+,.2f}",
                "Return": f"{pnl_pct:+.2f}%",
            },
        )
        
        return await self.notifier.send_alert(alert)
    
    async def notify_error(
        self,
        error_title: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Notify error.
        
        Args:
            error_title: Error title
            error_message: Error message
            context: Additional context
            
        Returns:
            True if successful
        """
        details = context or {}
        
        alert = Alert(
            category=AlertCategory.ERROR,
            severity=AlertSeverity.CRITICAL,
            title=f"❌ {error_title}",
            message=error_message,
            details=details,
        )
        
        return await self.notifier.send_alert(alert)
