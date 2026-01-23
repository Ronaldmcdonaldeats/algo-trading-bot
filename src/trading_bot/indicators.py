from __future__ import annotations

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator


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

    out = df.copy()
    close = out[close_col]

    out["rsi"] = RSIIndicator(close=close, window=rsi_period).rsi()

    macd = MACD(close=close, window_fast=macd_fast, window_slow=macd_slow, window_sign=macd_signal)
    out["macd"] = macd.macd()
    out["macd_signal"] = macd.macd_signal()
    out["macd_diff"] = macd.macd_diff()

    out["sma_fast"] = SMAIndicator(close=close, window=sma_fast).sma_indicator()
    out["sma_slow"] = SMAIndicator(close=close, window=sma_slow).sma_indicator()

    return out
