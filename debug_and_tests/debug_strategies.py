#!/usr/bin/env python
"""Debug strategy outputs directly."""

import sys
sys.path.insert(0, 'src')

from trading_bot.data.providers import AlpacaProvider
from trading_bot.strategy.atr_breakout import AtrBreakoutStrategy
from trading_bot.strategy.rsi_mean_reversion import RsiMeanReversionStrategy
from trading_bot.strategy.macd_volume_momentum import MacdVolumeMomentumStrategy
from datetime import datetime, timedelta, timezone
import pandas as pd

# Fetch data
provider = AlpacaProvider()

symbols = ["AAPL", "MSFT"]

for sym in symbols:
    print(f"\n{'='*80}")
    print(f"ANALYZING: {sym}")
    print(f"{'='*80}")
    
    try:
        # Use download_bars with period instead
        df = provider.download_bars(symbols=[sym], period="2mo", interval="1d")
        
        # Restructure if needed (download_bars returns multi-level columns for multi-symbol)
        if isinstance(df.columns, pd.MultiIndex):
            ohlcv = df[sym].reset_index()
        else:
            ohlcv = df.reset_index()
        
        if ohlcv is None or len(ohlcv) < 30:
            print(f"  Not enough data: {len(ohlcv) if ohlcv is not None else 0} bars")
            continue
        
        print(f"  Data fetched: {len(ohlcv)} bars")
        print(f"  Price range: ${ohlcv['Close'].min():.2f} - ${ohlcv['Close'].max():.2f}")
        print(f"  Last price: ${ohlcv['Close'].iloc[-1]:.2f}")
        
        # Test ATR Breakout
        print(f"\n  [ATR BREAKOUT STRATEGY]")
        atr_strategy = AtrBreakoutStrategy()
        atr_output = atr_strategy.compute(ohlcv)
        print(f"    Signal: {atr_output.signal}")
        print(f"    Confidence: {atr_output.confidence:.2f}")
        print(f"    Explanation: {atr_output.explanation}")
        
        # Test RSI Mean Reversion
        print(f"\n  [RSI MEAN REVERSION STRATEGY]")
        rsi_strategy = RsiMeanReversionStrategy()
        rsi_output = rsi_strategy.compute(ohlcv)
        print(f"    Signal: {rsi_output.signal}")
        print(f"    Confidence: {rsi_output.confidence:.2f}")
        print(f"    Explanation: {rsi_output.explanation}")
        
        # Test MACD Volume Momentum
        print(f"\n  [MACD VOLUME MOMENTUM STRATEGY]")
        macd_strategy = MacdVolumeMomentumStrategy()
        macd_output = macd_strategy.compute(ohlcv)
        print(f"    Signal: {macd_output.signal}")
        print(f"    Confidence: {macd_output.confidence:.2f}")
        print(f"    Explanation: {macd_output.explanation}")
        
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
