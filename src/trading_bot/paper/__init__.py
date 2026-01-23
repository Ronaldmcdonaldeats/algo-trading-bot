"""Paper trading loop.

This module intentionally keeps things simple:
- fetches candles via yfinance
- generates signals using the built-in strategy scaffold
- executes immediate market fills via `PaperBroker`

It is designed to be a starting point, not a production-ready trading system.
"""
