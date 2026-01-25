"""
Phase 14: Real-Time Notifications

Send email/Slack/Discord alerts for trades, risk events, and system status.
"""

from __future__ import annotations

import json
import smtplib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from urllib.request import Request, urlopen


class NotificationType(Enum):
    """Types of notifications"""
    TRADE_ENTRY = "TRADE_ENTRY"
    TRADE_EXIT = "TRADE_EXIT"
    RISK_EVENT = "RISK_EVENT"
    SYSTEM_ERROR = "SYSTEM_ERROR"
    DAILY_SUMMARY = "DAILY_SUMMARY"
    CONSECUTIVE_LOSS = "CONSECUTIVE_LOSS"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    POSITION_ROTATION = "POSITION_ROTATION"


@dataclass
class Notification:
    """A notification message"""
    type: NotificationType
    title: str
    message: str
    timestamp: datetime
    data: dict = None  # Additional context data


class EmailNotifier:
    """Send email notifications via SMTP"""

    def __init__(
        self,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: str = "",
        sender_password: str = "",
        recipient_email: str = ""
    ):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.recipient_email = recipient_email
        self.enabled = bool(sender_email and sender_password and recipient_email)

    def send(self, notification: Notification) -> bool:
        """Send email notification"""
        if not self.enabled:
            return False

        try:
            subject = f"[{notification.type.value}] {notification.title}"
            body = f"{notification.message}\n\nTime: {notification.timestamp.isoformat()}"

            message = f"Subject: {subject}\n\n{body}"

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, self.recipient_email, message)

            return True
        except Exception as e:
            print(f"[ERROR] Failed to send email: {e}")
            return False


class SlackNotifier:
    """Send Slack notifications via webhook"""

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)

    def send(self, notification: Notification) -> bool:
        """Send Slack notification"""
        if not self.enabled or not self.webhook_url:
            return False

        try:
            # Determine color based on type
            color_map = {
                NotificationType.TRADE_ENTRY: "#4CAF50",  # Green
                NotificationType.TRADE_EXIT: "#2196F3",   # Blue
                NotificationType.RISK_EVENT: "#FF9800",   # Orange
                NotificationType.SYSTEM_ERROR: "#F44336",  # Red
                NotificationType.DAILY_SUMMARY: "#9C27B0",  # Purple
                NotificationType.CONSECUTIVE_LOSS: "#FF5722",  # Deep Orange
                NotificationType.DAILY_LOSS_LIMIT: "#E91E63",  # Pink
                NotificationType.POSITION_ROTATION: "#00BCD4",  # Cyan
            }
            color = color_map.get(notification.type, "#000000")

            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": notification.title,
                        "text": notification.message,
                        "footer": notification.type.value,
                        "ts": int(notification.timestamp.timestamp()),
                    }
                ]
            }

            if notification.data:
                # Add fields for extra data
                fields = [
                    {"title": k, "value": str(v), "short": True}
                    for k, v in notification.data.items()
                ]
                payload["attachments"][0]["fields"] = fields

            req = Request(
                self.webhook_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"},
            )

            with urlopen(req) as response:
                return response.status == 200

        except Exception as e:
            print(f"[ERROR] Failed to send Slack notification: {e}")
            return False


class DiscordNotifier:
    """Send Discord notifications via webhook"""

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url
        self.enabled = bool(webhook_url)

    def send(self, notification: Notification) -> bool:
        """Send Discord notification"""
        if not self.enabled or not self.webhook_url:
            return False

        try:
            # Determine color based on type (Discord uses decimal color values)
            color_map = {
                NotificationType.TRADE_ENTRY: 0x4CAF50,    # Green
                NotificationType.TRADE_EXIT: 0x2196F3,     # Blue
                NotificationType.RISK_EVENT: 0xFF9800,     # Orange
                NotificationType.SYSTEM_ERROR: 0xF44336,   # Red
                NotificationType.DAILY_SUMMARY: 0x9C27B0,  # Purple
                NotificationType.CONSECUTIVE_LOSS: 0xFF5722,  # Deep Orange
                NotificationType.DAILY_LOSS_LIMIT: 0xE91E63,  # Pink
                NotificationType.POSITION_ROTATION: 0x00BCD4,  # Cyan
            }
            color = color_map.get(notification.type, 0x000000)

            embed = {
                "title": notification.title,
                "description": notification.message,
                "color": color,
                "footer": {"text": notification.type.value},
                "timestamp": notification.timestamp.isoformat(),
            }

            if notification.data:
                embed["fields"] = [
                    {"name": k, "value": str(v), "inline": True}
                    for k, v in notification.data.items()
                ]

            payload = {"embeds": [embed]}

            req = Request(
                self.webhook_url,
                data=json.dumps(payload).encode('utf-8'),
                headers={"Content-Type": "application/json"},
            )

            with urlopen(req) as response:
                return response.status == 200

        except Exception as e:
            print(f"[ERROR] Failed to send Discord notification: {e}")
            return False


class NotificationManager:
    """Unified notification manager"""

    def __init__(
        self,
        email_config: dict = None,
        slack_webhook: str = "",
        discord_webhook: str = "",
        enabled_types: Optional[list[NotificationType]] = None
    ):
        self.email_notifier = EmailNotifier(**(email_config or {}))
        self.slack_notifier = SlackNotifier(slack_webhook)
        self.discord_notifier = DiscordNotifier(discord_webhook)

        # Enable all notification types by default
        self.enabled_types = enabled_types or list(NotificationType)
        self.notification_history: list[Notification] = []

    def send_notification(
        self,
        notification_type: NotificationType,
        title: str,
        message: str,
        data: dict = None,
        send_email: bool = True,
        send_slack: bool = True,
        send_discord: bool = True
    ) -> bool:
        """Send notification through enabled channels"""
        if notification_type not in self.enabled_types:
            return False

        notification = Notification(
            type=notification_type,
            title=title,
            message=message,
            timestamp=datetime.now(),
            data=data
        )

        self.notification_history.append(notification)

        # Send through configured channels
        success = False
        if send_email:
            success |= self.email_notifier.send(notification)
        if send_slack:
            success |= self.slack_notifier.send(notification)
        if send_discord:
            success |= self.discord_notifier.send(notification)

        return success

    def notify_trade_entry(
        self,
        symbol: str,
        side: str,
        qty: int,
        price: float,
        strategy: str = "consensus"
    ) -> bool:
        """Notify of trade entry"""
        return self.send_notification(
            NotificationType.TRADE_ENTRY,
            f"{side} {qty} {symbol}",
            f"Entered {side} position of {qty} shares of {symbol} at ${price:.2f} using {strategy}",
            data={
                "Symbol": symbol,
                "Side": side,
                "Quantity": qty,
                "Price": f"${price:.2f}",
                "Strategy": strategy
            }
        )

    def notify_trade_exit(
        self,
        symbol: str,
        qty: int,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float
    ) -> bool:
        """Notify of trade exit"""
        status = "WIN ✓" if pnl > 0 else "LOSS ✗"
        return self.send_notification(
            NotificationType.TRADE_EXIT,
            f"{status} {symbol}",
            f"Exited {qty} shares at ${exit_price:.2f} (entry: ${entry_price:.2f})",
            data={
                "Symbol": symbol,
                "P&L": f"${pnl:,.2f}",
                "P&L %": f"{pnl_pct*100:.2f}%",
                "Quantity": qty
            }
        )

    def notify_consecutive_loss(self, count: int, max_count: int) -> bool:
        """Notify of consecutive losses"""
        return self.send_notification(
            NotificationType.CONSECUTIVE_LOSS,
            f"Consecutive Loss Alert ({count}/{max_count})",
            f"Experienced {count} consecutive losses. Trading will pause after {max_count}.",
            data={"Current": count, "Threshold": max_count}
        )

    def notify_daily_loss_limit(self, daily_pnl: float, limit: float) -> bool:
        """Notify of daily loss limit"""
        return self.send_notification(
            NotificationType.DAILY_LOSS_LIMIT,
            "Daily Loss Limit Reached",
            f"Daily P&L of ${daily_pnl:,.2f} has reached/exceeded limit of ${limit:,.2f}",
            data={"Daily P&L": f"${daily_pnl:,.2f}", "Limit": f"${limit:,.2f}"}
        )

    def notify_position_rotation(self, symbol: str, hold_hours: float) -> bool:
        """Notify of position rotation due"""
        return self.send_notification(
            NotificationType.POSITION_ROTATION,
            f"Position Rotation Due: {symbol}",
            f"{symbol} has been held for {hold_hours:.1f} hours (max: 24h)",
            data={"Symbol": symbol, "Hold Time": f"{hold_hours:.1f}h"}
        )

    def notify_system_error(self, error_title: str, error_message: str) -> bool:
        """Notify of system error"""
        return self.send_notification(
            NotificationType.SYSTEM_ERROR,
            error_title,
            error_message,
            send_email=True,
            send_slack=True,
            send_discord=True
        )

    def notify_daily_summary(self, summary_data: dict) -> bool:
        """Notify with daily summary"""
        message = f"""
Daily Trading Summary
Total Trades: {summary_data.get('total_trades', 0)}
Win Rate: {summary_data.get('win_rate', 0)*100:.1f}%
Daily P&L: ${summary_data.get('daily_pnl', 0):,.2f}
Sharpe Ratio: {summary_data.get('sharpe_ratio', 0):.2f}
        """
        return self.send_notification(
            NotificationType.DAILY_SUMMARY,
            "Daily Summary",
            message,
            data=summary_data
        )

    def get_notification_count(self, notification_type: NotificationType = None) -> int:
        """Get count of notifications by type"""
        if notification_type is None:
            return len(self.notification_history)
        return sum(1 for n in self.notification_history if n.type == notification_type)

    def get_recent_notifications(self, count: int = 10) -> list[Notification]:
        """Get recent notifications"""
        return self.notification_history[-count:]

    def print_notification_summary(self):
        """Print notification summary"""
        print("\n[NOTIFICATION SUMMARY]")
        for notif_type in NotificationType:
            count = self.get_notification_count(notif_type)
            if count > 0:
                print(f"  {notif_type.value}: {count}")
        print()

    def clear_history(self):
        """Clear notification history"""
        self.notification_history.clear()
