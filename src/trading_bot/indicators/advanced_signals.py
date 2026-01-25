"""Advanced signal indicators for better trading signals."""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return series.rolling(window=period).mean()


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range."""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_stoch(high: pd.Series, low: pd.Series, close: pd.Series, 
                    period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> tuple:
    """Calculate Stochastic Oscillator.
    
    Returns:
        (K line, D line)
    """
    lowest_low = low.rolling(window=period).min()
    highest_high = high.rolling(window=period).max()
    
    k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
    k_line = k_percent.rolling(window=smooth_k).mean()
    d_line = k_line.rolling(window=smooth_d).mean()
    
    return k_line, d_line


def calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple:
    """Calculate MACD.
    
    Returns:
        (MACD line, Signal line, Histogram)
    """
    ema_fast = calculate_ema(close, fast)
    ema_slow = calculate_ema(close, slow)
    
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    
    return macd_line, signal_line, histogram


def calculate_bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> tuple:
    """Calculate Bollinger Bands.
    
    Returns:
        (Upper band, Middle band, Lower band)
    """
    sma = calculate_sma(close, period)
    std = close.rolling(window=period).std()
    
    upper = sma + (std_dev * std)
    lower = sma - (std_dev * std)
    
    return upper, sma, lower


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


class EnhancedSignalGenerator:
    """Generate trading signals using multiple indicators."""
    
    def __init__(
        self,
        rsi_period: int = 14,
        rsi_overbought: float = 70,
        rsi_oversold: float = 30,
        use_volume_filter: bool = True,
        use_ema_filter: bool = True,
        use_stoch: bool = True,
        use_bollinger: bool = False,
    ):
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.use_volume_filter = use_volume_filter
        self.use_ema_filter = use_ema_filter
        self.use_stoch = use_stoch
        self.use_bollinger = use_bollinger
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate signals based on multiple indicators.
        
        Args:
            df: OHLCV DataFrame
        
        Returns:
            DataFrame with signal column (1=BUY, 0=NEUTRAL, -1=SELL) and confidence
        """
        if df.empty or len(df) < 30:
            return None
        
        df = df.copy()
        
        # Calculate indicators
        rsi = calculate_rsi(df['Close'], self.rsi_period)
        ema_9 = calculate_ema(df['Close'], 9)
        ema_21 = calculate_ema(df['Close'], 21)
        ema_50 = calculate_ema(df['Close'], 50)
        
        # Base RSI signal (mean reversion)
        rsi_signal = np.where(rsi < self.rsi_oversold, 1, 0)  # BUY oversold
        rsi_signal = np.where(rsi > self.rsi_overbought, -1, rsi_signal)  # SELL overbought
        
        # Volume confirmation
        volume_signal = np.ones(len(df))
        if self.use_volume_filter and 'Volume' in df.columns:
            avg_volume = df['Volume'].rolling(20).mean()
            volume_filter = df['Volume'] > (avg_volume * 0.8)  # Above 80% of average
            volume_signal = np.where(volume_filter, 1, 0.5)
        
        # EMA trend filter
        ema_signal = np.ones(len(df))
        if self.use_ema_filter:
            # Uptrend: price above 9 EMA, 9 above 21, 21 above 50
            uptrend = (df['Close'] > ema_9) & (ema_9 > ema_21) & (ema_21 > ema_50)
            # Downtrend: price below 9 EMA, 9 below 21, 21 below 50
            downtrend = (df['Close'] < ema_9) & (ema_9 < ema_21) & (ema_21 < ema_50)
            ema_signal = np.where(uptrend, 1.0, np.where(downtrend, -1.0, 0.0))
        
        # Stochastic confirmation
        stoch_signal = np.ones(len(df))
        if self.use_stoch:
            k_line, d_line = calculate_stoch(df['High'], df['Low'], df['Close'])
            # Buy when K crosses above D in oversold
            stoch_buy = (k_line < 20) & (k_line > d_line)
            # Sell when K crosses below D in overbought
            stoch_sell = (k_line > 80) & (k_line < d_line)
            stoch_signal = np.where(stoch_buy, 1.0, np.where(stoch_sell, -1.0, 0.0))
        
        # Bollinger Bands confirmation
        bb_signal = np.ones(len(df))
        if self.use_bollinger:
            upper, middle, lower = calculate_bollinger_bands(df['Close'], period=20, std_dev=2.0)
            bb_signal = np.where(df['Close'] < lower, 1.0, np.where(df['Close'] > upper, -1.0, 0.0))
        
        # Combine signals (weighted voting)
        signals = (
            rsi_signal * 0.35 +  # 35% weight to RSI
            ema_signal * 0.25 +  # 25% weight to EMA trend
            stoch_signal * 0.20 +  # 20% weight to Stochastic
            bb_signal * 0.10 +  # 10% weight to Bollinger
            volume_signal * 0.10  # 10% weight to Volume
        )
        
        # Convert to -1, 0, 1
        final_signal = np.where(signals > 0.5, 1, np.where(signals < -0.5, -1, 0))
        confidence = np.abs(signals) / 1.0  # Normalize confidence
        
        df['signal'] = final_signal
        df['confidence'] = confidence
        
        return df
    
    def get_signal_breakdown(self, df: pd.DataFrame) -> dict:
        """Get breakdown of why signal was generated."""
        if df.empty or len(df) < 30:
            return {}
        
        df = df.copy()
        
        rsi = calculate_rsi(df['Close'], self.rsi_period)
        ema_9 = calculate_ema(df['Close'], 9)
        ema_21 = calculate_ema(df['Close'], 21)
        ema_50 = calculate_ema(df['Close'], 50)
        
        latest_rsi = rsi.iloc[-1]
        latest_price = df['Close'].iloc[-1]
        latest_ema_9 = ema_9.iloc[-1]
        latest_ema_21 = ema_21.iloc[-1]
        latest_ema_50 = ema_50.iloc[-1]
        
        return {
            "rsi": latest_rsi,
            "rsi_overbought": latest_rsi > self.rsi_overbought,
            "rsi_oversold": latest_rsi < self.rsi_oversold,
            "price": latest_price,
            "ema_9": latest_ema_9,
            "ema_21": latest_ema_21,
            "ema_50": latest_ema_50,
            "uptrend": (latest_price > latest_ema_9) and (latest_ema_9 > latest_ema_21) and (latest_ema_21 > latest_ema_50),
            "downtrend": (latest_price < latest_ema_9) and (latest_ema_9 < latest_ema_21) and (latest_ema_21 < latest_ema_50),
        }
