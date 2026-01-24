#!/usr/bin/env python
"""Test Alpaca API connection and data fetching."""

import os
from datetime import datetime, timedelta
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Check credentials
api_key = os.getenv("APCA_API_KEY_ID")
api_secret = os.getenv("APCA_API_SECRET_KEY")
base_url = os.getenv("APCA_API_BASE_URL")

print(f"API Key: {api_key[:20] if api_key else 'NOT SET'}...")
print(f"API Secret: {api_secret[:20] if api_secret else 'NOT SET'}...")
print(f"Base URL: {base_url}")

# Try to fetch data
try:
    client = StockHistoricalDataClient(api_key, api_secret)
    print("✓ Connected to Alpaca API")
    
    # Request data for AAPL from last month
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    print(f"\nRequesting data for AAPL from {start_date} to {end_date}")
    
    request = StockBarsRequest(
        symbol_or_symbols="AAPL",
        timeframe=TimeFrame.Day,
        start=start_date,
        end=end_date,
    )
    
    bars = client.get_stock_bars(request)
    
    if bars and "AAPL" in bars:
        print(f"✓ Got {len(bars['AAPL'])} bars for AAPL")
        for i, bar in enumerate(list(bars['AAPL'])[:3]):
            print(f"  {bar.timestamp}: O={bar.open:.2f} H={bar.high:.2f} L={bar.low:.2f} C={bar.close:.2f} V={bar.volume}")
    else:
        print("✗ No data returned for AAPL")
        print(f"Bars content: {bars}")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
