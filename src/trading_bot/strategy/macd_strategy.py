"""MACD (Moving Average Convergence Divergence) trading strategy."""

import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

import logging
logger = logging.getLogger(__name__)


def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """Calculate MACD, signal line, and histogram.
    
    Args:
        prices: Series of closing prices
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal EMA period (default 9)
        
    Returns:
        Tuple of (macd, signal_line, histogram) Series
    """
    ema_fast = prices.ewm(span=fast, adjust=False).mean()
    ema_slow = prices.ewm(span=slow, adjust=False).mean()
    
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    
    return macd, signal_line, histogram


def generate_signals(
    df: pd.DataFrame,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    **kwargs
) -> Optional[pd.DataFrame]:
    """Generate MACD trading signals.
    
    Buy Signal: 
    - MACD line crosses above signal line
    - Histogram turns positive from negative
    
    Sell Signal:
    - MACD line crosses below signal line
    - Histogram turns negative from positive
    
    Args:
        df: OHLCV DataFrame with 'Close' column
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal line period
        
    Returns:
        DataFrame with signal column (-1, 0, 1) and metadata
    """
    if df.empty or 'Close' not in df.columns:
        return None
    
    try:
        close = df['Close'].astype(float)
        
        # Need minimum bars for calculation
        if len(close) < slow_period + signal_period:
            return None
        
        # Calculate MACD
        macd_line, signal_line, histogram = calculate_macd(
            close,
            fast=fast_period,
            slow=slow_period,
            signal=signal_period
        )
        
        # Detect crossovers
        signal_series = pd.Series(0, index=df.index)
        
        # Buy signal: MACD crosses above signal line
        buy_cross = (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))
        signal_series[buy_cross] = 1
        
        # Sell signal: MACD crosses below signal line
        sell_cross = (macd_line < signal_line) & (macd_line.shift(1) >= signal_line.shift(1))
        signal_series[sell_cross] = -1
        
        # Return only most recent signal
        result_df = df.copy()
        result_df['signal'] = signal_series
        result_df['macd'] = macd_line
        result_df['macd_signal'] = signal_line
        result_df['macd_histogram'] = histogram
        
        # Return last non-zero signal or 0
        last_signal = signal_series[signal_series != 0]
        if not last_signal.empty:
            latest_signal = last_signal.iloc[-1]
            if latest_signal != 0:
                return pd.DataFrame({
                    'signal': [latest_signal],
                    'strategy': ['MACD'],
                    'strength': [abs(histogram.iloc[-1])],
                    'macd': [macd_line.iloc[-1]],
                    'signal_line': [signal_line.iloc[-1]]
                })
        
        return None
        
    except Exception as e:
        logger.debug(f"MACD signal generation failed: {e}")
        return None
