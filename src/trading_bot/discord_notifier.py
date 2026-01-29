#!/usr/bin/env python3
"""
Discord Webhook Integration for Trading Bot
Sends notifications for trades, alerts, and system events
"""

import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DiscordNotifier:
    """Send trading notifications to Discord via webhook"""
    
    def __init__(self):
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)
    
    def _send_embed(self, embed_data):
        """Send an embed message to Discord"""
        if not self.enabled:
            return False
        
        payload = {"embeds": [embed_data]}
        
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            return response.status_code == 204
        except Exception as e:
            print(f"Discord notification error: {e}")
            return False
    
    def _create_embed(self, title, description, color=3447003, fields=None):
        """Create a Discord embed"""
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "footer": {"text": "Trading Bot"}
        }
        
        if fields:
            embed["fields"] = fields
        
        return embed
    
    def trade_executed(self, symbol, side, quantity, price, order_id=None):
        """Notify when a trade is executed"""
        fields = [
            {"name": "Symbol", "value": symbol, "inline": True},
            {"name": "Side", "value": side.upper(), "inline": True},
            {"name": "Quantity", "value": str(quantity), "inline": True},
            {"name": "Price", "value": f"${price:.2f}", "inline": True},
        ]
        if order_id:
            fields.append({"name": "Order ID", "value": str(order_id), "inline": False})
        
        embed = self._create_embed(
            f"📈 TRADE EXECUTED - {symbol}",
            f"Gen 364 Strategy executed {side.upper()} order",
            color=65280,  # Green
            fields=fields
        )
        return self._send_embed(embed)
    
    def market_open(self):
        """Notify when market opens"""
        embed = self._create_embed(
            "🔔 MARKET OPENED",
            "Stock market opened - trading bot is now active",
            color=65280,  # Green
        )
        return self._send_embed(embed)
    
    def market_close(self):
        """Notify when market closes"""
        embed = self._create_embed(
            "🔔 MARKET CLOSED",
            "Stock market closed - trading bot is now in standby",
            color=16776960,  # Yellow
        )
        return self._send_embed(embed)
    
    def profit_loss(self, symbol, entry_price, exit_price, quantity, pl_amount, pl_percent):
        """Notify when a position is closed with profit/loss"""
        color = 65280 if pl_amount >= 0 else 16711680  # Green if profit, red if loss
        emoji = "📊" if pl_amount >= 0 else "📉"
        
        fields = [
            {"name": "Symbol", "value": symbol, "inline": True},
            {"name": "Quantity", "value": str(quantity), "inline": True},
            {"name": "Entry Price", "value": f"${entry_price:.2f}", "inline": True},
            {"name": "Exit Price", "value": f"${exit_price:.2f}", "inline": True},
            {"name": "P/L Amount", "value": f"${pl_amount:.2f}", "inline": True},
            {"name": "P/L %", "value": f"{pl_percent:.2f}%", "inline": True},
        ]
        
        embed = self._create_embed(
            f"{emoji} POSITION CLOSED - {symbol}",
            f"Trade closed with {'+' if pl_amount >= 0 else ''}{pl_amount:.2f} P/L",
            color=color,
            fields=fields
        )
        return self._send_embed(embed)
    
    def error_alert(self, error_type, error_message):
        """Notify on error or warning"""
        embed = self._create_embed(
            f"⚠️ ERROR: {error_type}",
            error_message,
            color=16711680,  # Red
        )
        return self._send_embed(embed)
    
    def strategy_status(self, status, details=None):
        """Notify strategy status changes"""
        colors = {
            "started": 65280,      # Green
            "stopped": 16711680,   # Red
            "paused": 16776960,    # Yellow
            "error": 16711680,     # Red
        }
        color = colors.get(status, 3447003)
        
        fields = []
        if details:
            for key, value in details.items():
                fields.append({"name": key, "value": str(value), "inline": True})
        
        embed = self._create_embed(
            f"🤖 Strategy {status.upper()}",
            f"Gen 364 Strategy has {status}",
            color=color,
            fields=fields
        )
        return self._send_embed(embed)

# Export for use in other modules
notifier = DiscordNotifier()

if __name__ == "__main__":
    # Quick test
    if notifier.enabled:
        print("Testing Discord integration...")
        notifier.trade_executed("AAPL", "BUY", 10, 150.25, "12345")
        notifier.market_open()
        print("Test message sent!")
    else:
        print("Discord webhook not configured")
