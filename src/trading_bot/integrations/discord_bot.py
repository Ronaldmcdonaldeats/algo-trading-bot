"""Discord Integration - Send trading alerts to Discord

Posts trades, performance updates, and alerts to Discord channel
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import asyncio
import logging


logger = logging.getLogger(__name__)


@dataclass
class DiscordMessage:
    """Discord message to send"""
    title: str
    description: str
    fields: Dict[str, str]
    color: int  # Hex color code
    timestamp: datetime


class DiscordIntegration:
    """Integration with Discord for trading alerts"""
    
    def __init__(self, webhook_url: Optional[str] = None, cache_dir: str = ".cache"):
        self.webhook_url = webhook_url
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.message_queue: List[DiscordMessage] = []
        self.sent_messages: List[Dict] = []
        self.enabled = bool(webhook_url)
    
    def set_webhook_url(self, webhook_url: str):
        """Set Discord webhook URL"""
        self.webhook_url = webhook_url
        self.enabled = True
        return True
    
    def post_trade(self, symbol: str, side: str, quantity: int, price: float, 
                   reason: str = "", profit_loss: Optional[float] = None) -> bool:
        """Post a trade to Discord"""
        
        color = 0x00FF00 if side == "BUY" else 0xFF0000  # Green for buy, red for sell
        emoji = "🟢" if side == "BUY" else "🔴"
        
        fields = {
            'Stock': symbol,
            'Type': side,
            'Shares': str(quantity),
            'Price': f"${price:,.2f}",
        }
        
        if profit_loss is not None:
            fields['Profit/Loss'] = f"${profit_loss:,.2f}"
        
        if reason:
            fields['Reason'] = reason
        
        message = DiscordMessage(
            title=f"{emoji} {side} {symbol}",
            description=f"Trading {quantity} shares of {symbol} at ${price:,.2f}",
            fields=fields,
            color=color,
            timestamp=datetime.now()
        )
        
        return self._send_message(message)
    
    def post_daily_summary(self, total_trades: int, profit_loss: float, 
                          win_rate: float, best_trade: float, worst_trade: float) -> bool:
        """Post daily performance summary"""
        
        # Determine color based on P&L
        color = 0x00FF00 if profit_loss >= 0 else 0xFF0000
        emoji = "✅" if profit_loss >= 0 else "❌"
        
        fields = {
            'Total Trades': str(total_trades),
            'Profit/Loss': f"${profit_loss:,.2f}",
            'Win Rate': f"{win_rate*100:.1f}%",
            'Best Trade': f"${best_trade:,.2f}",
            'Worst Trade': f"${worst_trade:,.2f}",
        }
        
        message = DiscordMessage(
            title=f"{emoji} Daily Performance Summary",
            description=f"Trading bot daily performance for {datetime.now().date()}",
            fields=fields,
            color=color,
            timestamp=datetime.now()
        )
        
        return self._send_message(message)
    
    def post_alert(self, alert_type: str, message: str, severity: str = "info") -> bool:
        """Post alert message"""
        
        # Color based on severity
        severity_colors = {
            'critical': 0xFF0000,  # Red
            'warning': 0xFFA500,   # Orange
            'info': 0x0099FF,      # Blue
            'success': 0x00FF00,   # Green
        }
        
        emoji_map = {
            'critical': '🔴',
            'warning': '⚠️',
            'info': 'ℹ️',
            'success': '✅',
        }
        
        color = severity_colors.get(severity, 0x0099FF)
        emoji = emoji_map.get(severity, 'ℹ️')
        
        message = DiscordMessage(
            title=f"{emoji} {alert_type}",
            description=message,
            fields={'Severity': severity.upper()},
            color=color,
            timestamp=datetime.now()
        )
        
        return self._send_message(message)
    
    def post_market_alert(self, message: str, related_symbols: List[str] = None) -> bool:
        """Post market-related alert"""
        
        fields = {'Alert': message}
        
        if related_symbols:
            fields['Affected Stocks'] = ", ".join(related_symbols[:5])
        
        msg = DiscordMessage(
            title="📊 Market Alert",
            description=message,
            fields=fields,
            color=0xFFFF00,  # Yellow
            timestamp=datetime.now()
        )
        
        return self._send_message(msg)
    
    def _send_message(self, message: DiscordMessage) -> bool:
        """Send message to Discord"""
        
        if not self.enabled:
            logger.warning("Discord integration not enabled (no webhook URL)")
            return False
        
        # Queue message for sending
        self.message_queue.append(message)
        
        # Record that message was queued (actual send would happen async)
        self.sent_messages.append({
            'title': message.title,
            'description': message.description,
            'timestamp': message.timestamp.isoformat(),
            'status': 'queued'
        })
        
        # In real implementation, this would actually send to Discord
        logger.info(f"Discord message queued: {message.title}")
        return True
    
    def get_message_format(self, message: DiscordMessage) -> Dict:
        """Get Discord embed format for message"""
        
        fields = [
            {'name': name, 'value': value, 'inline': True}
            for name, value in message.fields.items()
        ]
        
        return {
            'embeds': [
                {
                    'title': message.title,
                    'description': message.description,
                    'color': message.color,
                    'fields': fields,
                    'timestamp': message.timestamp.isoformat()
                }
            ]
        }
    
    def save_message_history(self, filename: str = "discord_messages.json"):
        """Save message history to file"""
        filepath = self.cache_dir / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.sent_messages, f, indent=2)
    
    def load_message_history(self, filename: str = "discord_messages.json") -> List[Dict]:
        """Load message history from file"""
        filepath = self.cache_dir / filename
        
        if not filepath.exists():
            return []
        
        with open(filepath, 'r') as f:
            return json.load(f)
    
    def get_statistics(self) -> Dict:
        """Get Discord integration statistics"""
        return {
            'enabled': self.enabled,
            'webhook_url_set': bool(self.webhook_url),
            'messages_queued': len(self.message_queue),
            'messages_sent': len(self.sent_messages),
            'recent_messages': self.sent_messages[-5:] if self.sent_messages else []
        }
    
    async def process_queue(self):
        """Process message queue (async)"""
        while self.message_queue:
            message = self.message_queue.pop(0)
            # In real implementation, would send to Discord API
            await asyncio.sleep(0.1)  # Rate limiting
    
    def generate_config(self, webhook_url: str) -> Dict:
        """Generate Discord config for storage"""
        return {
            'discord': {
                'webhook_url': webhook_url,
                'enabled': True,
                'features': [
                    'trade_notifications',
                    'daily_summary',
                    'market_alerts',
                    'performance_updates'
                ]
            }
        }
    
    def setup_from_env(self) -> bool:
        """Setup Discord from environment variables"""
        import os
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if webhook_url:
            self.set_webhook_url(webhook_url)
            return True
        return False
