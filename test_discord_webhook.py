#!/usr/bin/env python3
"""
Test Discord webhook integration for trading bot
"""

import requests
import json
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not DISCORD_WEBHOOK_URL:
    print("❌ ERROR: DISCORD_WEBHOOK_URL not found in .env file")
    exit(1)

def send_discord_message(title, message, color=3447003, fields=None):
    """
    Send a message to Discord via webhook
    
    Args:
        title: Embed title
        message: Embed description
        color: Embed color (default: blue)
        fields: List of dicts with 'name' and 'value' keys
    """
    
    embed = {
        "title": title,
        "description": message,
        "color": color,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "footer": {
            "text": "Trading Bot"
        }
    }
    
    if fields:
        embed["fields"] = fields
    
    payload = {
        "embeds": [embed]
    }
    
    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 204:
            return True
        else:
            print(f"❌ Discord error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending to Discord: {e}")
        return False

# Test 1: Simple notification
print("📤 Sending Test 1: Simple notification...")
success = send_discord_message(
    "🤖 Trading Bot Test",
    "This is a test message from your trading bot!",
    color=3447003  # Blue
)
if success:
    print("✅ Test 1 PASSED - Check Discord!\n")
else:
    print("❌ Test 1 FAILED\n")

# Test 2: Trade notification example
print("📤 Sending Test 2: Trade example...")
success = send_discord_message(
    "📈 TRADE EXECUTED",
    "Gen 364 Strategy placed a trade",
    color=65280,  # Green
    fields=[
        {"name": "Symbol", "value": "SPY", "inline": True},
        {"name": "Side", "value": "BUY", "inline": True},
        {"name": "Quantity", "value": "10", "inline": True},
        {"name": "Price", "value": "$450.25", "inline": True},
        {"name": "Status", "value": "Filled", "inline": False}
    ]
)
if success:
    print("✅ Test 2 PASSED - Check Discord!\n")
else:
    print("❌ Test 2 FAILED\n")

# Test 3: Error notification example
print("📤 Sending Test 3: Error alert example...")
success = send_discord_message(
    "⚠️ ALERT: Low Balance",
    "Account balance is below minimum threshold",
    color=16711680,  # Red
    fields=[
        {"name": "Current Balance", "value": "$500", "inline": True},
        {"name": "Minimum Required", "value": "$1000", "inline": True},
    ]
)
if success:
    print("✅ Test 3 PASSED - Check Discord!\n")
else:
    print("❌ Test 3 FAILED\n")

print("=" * 60)
print("✅ All tests completed! Check your Discord channel for messages.")
print("=" * 60)
