"""
Discord Integration for Real-time Trading Alerts
Posts trades, alerts, and daily summaries to Discord channels.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class DiscordConfig:
    """Discord configuration"""
    webhook_url: str  # Discord webhook URL
    enabled: bool = True
    post_trades: bool = True
    post_alerts: bool = True
    post_summaries: bool = True
    username: str = "Trading Bot"
    avatar_url: Optional[str] = None


class DiscordNotifier:
    """Send notifications to Discord"""
    
    def __init__(self, config: DiscordConfig):
        self.config = config
        self.session = requests.Session()
    
    def post_trade(self, symbol: str, side: str, qty: int, price: float,
                  reason: str = "", pnl: Optional[float] = None):
        """Post a trade execution to Discord"""
        if not self.config.enabled or not self.config.post_trades:
            return
        
        if side.upper() == "BUY":
            emoji = "🟢"
            action = "BOUGHT"
            color = 0x00ff00  # Green
        else:
            emoji = "🔴"
            action = "SOLD"
            color = 0xff0000  # Red
        
        embed = {
            "title": f"{emoji} {action} {symbol}",
            "color": color,
            "fields": [
                {"name": "Symbol", "value": symbol, "inline": True},
                {"name": "Shares", "value": str(qty), "inline": True},
                {"name": "Price", "value": f"${price:,.2f}", "inline": True},
                {"name": "Total", "value": f"${price * qty:,.2f}", "inline": True},
            ],
            "timestamp": datetime.now().isoformat(),
        }
        
        if reason:
            embed["fields"].append({"name": "Reason", "value": reason, "inline": False})
        
        if pnl is not None:
            pnl_emoji = "📈" if pnl >= 0 else "📉"
            embed["fields"].append({
                "name": f"{pnl_emoji} P&L",
                "value": f"${pnl:,.2f}",
                "inline": True
            })
        
        self._send_embed(embed)
    
    def post_alert(self, title: str, description: str, level: str = "info"):
        """Post an alert to Discord"""
        if not self.config.enabled or not self.config.post_alerts:
            return
        
        color_map = {
            "info": 0x0099ff,     # Blue
            "warning": 0xffaa00,  # Orange
            "error": 0xff0000,    # Red
            "success": 0x00ff00,  # Green
        }
        color = color_map.get(level.lower(), 0x0099ff)
        
        emoji_map = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }
        emoji = emoji_map.get(level.lower(), "ℹ️")
        
        embed = {
            "title": f"{emoji} {title}",
            "description": description,
            "color": color,
            "timestamp": datetime.now().isoformat(),
        }
        
        self._send_embed(embed)
    
    def post_daily_summary(self, stats: dict):
        """Post daily trading summary"""
        if not self.config.enabled or not self.config.post_summaries:
            return
        
        pnl = stats.get("pnl", 0)
        pnl_emoji = "📈" if pnl >= 0 else "📉"
        
        embed = {
            "title": f"{pnl_emoji} Daily Trading Summary",
            "color": 0x0099ff,
            "fields": [
                {"name": "Date", "value": datetime.now().strftime("%Y-%m-%d"), "inline": True},
                {"name": "P&L", "value": f"${pnl:,.2f}", "inline": True},
                {"name": "Trades", "value": str(stats.get("num_trades", 0)), "inline": True},
                {"name": "Win Rate", "value": f"{stats.get('win_rate', 0):.1%}", "inline": True},
                {"name": "Sharpe Ratio", "value": f"{stats.get('sharpe_ratio', 0):.2f}", "inline": True},
                {"name": "Max Drawdown", "value": f"{stats.get('max_dd', 0):.1%}", "inline": True},
            ],
            "timestamp": datetime.now().isoformat(),
        }
        
        if "best_trade" in stats:
            embed["fields"].append({
                "name": "Best Trade",
                "value": f"{stats['best_trade']['symbol']}: +${stats['best_trade']['pnl']:,.2f}",
                "inline": True
            })
        
        if "worst_trade" in stats:
            embed["fields"].append({
                "name": "Worst Trade",
                "value": f"{stats['worst_trade']['symbol']}: ${stats['worst_trade']['pnl']:,.2f}",
                "inline": True
            })
        
        self._send_embed(embed)
    
    def post_positions(self, positions: dict[str, dict]):
        """Post current positions"""
        if not self.config.enabled:
            return
        
        if not positions:
            self.post_alert("Portfolio", "No open positions", "info")
            return
        
        description = ""
        for symbol, pos in sorted(positions.items()):
            qty = pos.get("qty", 0)
            price = pos.get("price", 0)
            pnl = pos.get("pnl", 0)
            pnl_emoji = "📈" if pnl >= 0 else "📉"
            description += f"{pnl_emoji} **{symbol}**: {qty} @ ${price:,.2f} | P&L: ${pnl:,.2f}\n"
        
        embed = {
            "title": "📊 Current Positions",
            "description": description,
            "color": 0x0099ff,
            "timestamp": datetime.now().isoformat(),
        }
        
        self._send_embed(embed)
    
    def _send_embed(self, embed: dict):
        """Send embed message to Discord"""
        try:
            data = {
                "username": self.config.username,
                "embeds": [embed],
            }
            
            if self.config.avatar_url:
                data["avatar_url"] = self.config.avatar_url
            
            response = requests.post(
                self.config.webhook_url,
                json=data,
                timeout=10,
            )
            
            if response.status_code != 204:
                logger.warning(f"Discord post failed: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Discord notification error: {e}")
    
    def test_connection(self) -> bool:
        """Test Discord webhook connection"""
        try:
            self.post_alert(
                "Test Message",
                "Trading bot Discord integration is working!",
                "success"
            )
            return True
        except Exception as e:
            logger.error(f"Discord test failed: {e}")
            return False


class DiscordAlertManager:
    """Manage multiple Discord alerts with rate limiting"""
    
    def __init__(self, notifier: DiscordNotifier):
        self.notifier = notifier
        self.last_alert_time = {}
        self.min_interval = 60  # Minimum seconds between alerts of same type
    
    def alert_big_trade(self, symbol: str, side: str, qty: int, price: float):
        """Alert on significant trade"""
        self.notifier.post_trade(
            symbol, side, qty, price,
            reason="Significant trade execution"
        )
    
    def alert_stop_loss_hit(self, symbol: str, price: float, pnl: float):
        """Alert when stop loss is triggered"""
        self.notifier.post_alert(
            f"Stop Loss Hit: {symbol}",
            f"Position closed at ${price:,.2f}\nP&L: ${pnl:,.2f}",
            "warning"
        )
    
    def alert_take_profit_hit(self, symbol: str, price: float, pnl: float):
        """Alert when take profit is triggered"""
        self.notifier.post_alert(
            f"Take Profit Hit: {symbol}",
            f"Position closed at ${price:,.2f}\nP&L: ${pnl:,.2f}",
            "success"
        )
    
    def alert_drawdown(self, current_dd: float, limit_dd: float):
        """Alert when drawdown exceeds limit"""
        self.notifier.post_alert(
            "⚠️ Drawdown Alert",
            f"Current drawdown: {current_dd:.1%}\nLimit: {limit_dd:.1%}",
            "error"
        )
    
    def alert_error(self, title: str, error_msg: str):
        """Alert on error"""
        self.notifier.post_alert(title, error_msg, "error")
