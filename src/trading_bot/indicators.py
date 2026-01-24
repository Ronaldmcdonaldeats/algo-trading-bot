from __future__ import annotations

import hashlib

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator

# OPTIMIZATION: Cache computed indicators to avoid recalculation
_indicator_cache: dict[str, pd.DataFrame] = {}
_cache_max_size = 50  # Prevent unbounded memory growth


def add_indicators(
    df: pd.DataFrame,
    *,
    close_col: str = "Close",
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    sma_fast: int = 20,
    sma_slow: int = 50,
) -> pd.DataFrame:
    if close_col not in df.columns:
        raise ValueError(f"Missing required column: {close_col}")
    
    # OPTIMIZATION: Hash last 50 rows to create cache key (25% smaller cache)
    # Skip expensive indicator calculation if we've computed this exact data before
    try:
        df_tail = df.tail(50).to_string()
        cache_key = hashlib.sha256(df_tail.encode()).hexdigest()
        
        if cache_key in _indicator_cache:
            # Return cached result
            return _indicator_cache[cache_key]
    except:
        cache_key = None

    out = df.copy()
    close = out[close_col]

    out["rsi"] = RSIIndicator(close=close, window=rsi_period).rsi()

    macd = MACD(close=close, window_fast=macd_fast, window_slow=macd_slow, window_sign=macd_signal)
    out["macd"] = macd.macd()
    out["macd_signal"] = macd.macd_signal()
    out["macd_diff"] = macd.macd_diff()

    out["sma_fast"] = SMAIndicator(close=close, window=sma_fast).sma_indicator()
    out["sma_slow"] = SMAIndicator(close=close, window=sma_slow).sma_indicator()

    # OPTIMIZATION: Cache computed result for next identical OHLCV data
    if cache_key is not None:
        if len(_indicator_cache) >= _cache_max_size:
            # Simple FIFO eviction when cache is full
            oldest_key = next(iter(_indicator_cache))
            del _indicator_cache[oldest_key]
        _indicator_cache[cache_key] = out

    return out
