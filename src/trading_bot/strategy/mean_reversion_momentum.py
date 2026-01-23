from __future__ import annotations

import pandas as pd

from trading_bot.indicators import add_indicators


def zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window=window).mean()
    std = series.rolling(window=window).std(ddof=0)
    return (series - mean) / std


def generate_signals(
    df: pd.DataFrame,
    *,
    close_col: str = "Close",
    lookback_days: int = 20,
    zscore_entry: float = 2.0,
    zscore_exit: float = 0.5,
    rsi_period: int = 14,
    rsi_oversold: float = 30,
    rsi_overbought: float = 70,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
    sma_fast: int = 20,
    sma_slow: int = 50,
) -> pd.DataFrame:
    """Return df with a `signal` column.

    signal:
      +1 = long
       0 = flat
      -1 = short (reserved; currently unused)

    Entry idea (long): price is far below its mean (zscore <= -zscore_entry)
    plus momentum filter not bearish (RSI oversold and MACD diff >= 0, fast MA >= slow MA).

    Exit idea: zscore mean reverts (>= -zscore_exit) or RSI goes overbought.

    This is intentionally conservative and meant as a starting point.
    """
    out = add_indicators(
        df,
        close_col=close_col,
        rsi_period=rsi_period,
        macd_fast=macd_fast,
        macd_slow=macd_slow,
        macd_signal=macd_signal,
        sma_fast=sma_fast,
        sma_slow=sma_slow,
    )

    out["z"] = zscore(out[close_col], window=lookback_days)

    long_entry = (
        (out["z"] <= -abs(zscore_entry))
        & (out["rsi"] <= rsi_oversold)
        & (out["macd_diff"] >= 0)
        & (out["sma_fast"] >= out["sma_slow"])
    )

    long_exit = (out["z"] >= -abs(zscore_exit)) | (out["rsi"] >= rsi_overbought)

    signal = pd.Series(0, index=out.index, dtype="int64")
    in_long = False
    for idx in out.index:
        if not in_long and bool(long_entry.loc[idx]):
            in_long = True
            signal.loc[idx] = 1
        elif in_long and bool(long_exit.loc[idx]):
            in_long = False
            signal.loc[idx] = 0
        else:
            signal.loc[idx] = 1 if in_long else 0

    out["signal"] = signal
    return out
