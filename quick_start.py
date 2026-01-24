#!/usr/bin/env python
"""
Quick-start script: Run this to automatically start trading with learning.
No configuration needed - just run it!

Usage:
    python quick_start.py

This will:
    1. Select top 50 NASDAQ stocks automatically
    2. Start paper trading
    3. Learn from trading results
    4. Show real-time dashboard

Press Ctrl+C to stop.
"""

import sys
import os

# Set up environment
os.environ.setdefault("APCA_API_BASE_URL", "https://paper-api.alpaca.markets")

# Import after environment is set
from trading_bot.auto_start import auto_start_with_defaults

if __name__ == "__main__":
    print("🤖 AI-Powered Trading Bot with Strategy Learning")
    print("=" * 70)
    print("Starting auto-trading session...")
    print("=" * 70)
    
    exit_code = auto_start_with_defaults()
    sys.exit(exit_code)
