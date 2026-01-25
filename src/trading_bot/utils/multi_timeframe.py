"""Multiple timeframe analysis for trade confirmation."""

from __future__ import annotations

import pandas as pd
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class MultiTimeframeAnalysis:
    """Confirm trades across multiple timeframes."""

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI for a price series.
        
        Args:
            prices: Series of prices
            period: RSI period
            
        Returns:
            Series of RSI values
        """
        if len(prices) < period + 1:
            return pd.Series(50, index=prices.index)
        
        delta = prices.diff()
        gains = delta.where(delta > 0, 0).rolling(window=period).mean()
        losses = -delta.where(delta < 0, 0).rolling(window=period).mean()
        
        rs = gains / losses.replace(0, 1)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    @staticmethod
    def confirm_signal(
        signal_5m: int,  # 1 (buy), -1 (sell), 0 (no signal)
        signal_15m: int,
        require_agreement: bool = True,
    ) -> int:
        """Confirm signal across timeframes.
        
        Args:
            signal_5m: Signal from 5-minute timeframe (1, -1, or 0)
            signal_15m: Signal from 15-minute timeframe (1, -1, or 0)
            require_agreement: If True, both must agree; if False, either can trade
            
        Returns:
            Final signal: 1 (confirmed buy), -1 (confirmed sell), or 0 (no confirmation)
        """
        if require_agreement:
            # Both timeframes must agree
            if signal_5m == signal_15m and signal_5m != 0:
                return signal_5m
            return 0
        else:
            # Either timeframe can signal if not conflicting
            if signal_5m != 0 and signal_15m == 0:
                return signal_5m
            elif signal_15m != 0 and signal_5m == 0:
                return signal_15m
            elif signal_5m == signal_15m and signal_5m != 0:
                return signal_5m
            return 0

    @staticmethod
    def get_trend(prices: pd.Series, fast_period: int = 20, slow_period: int = 50) -> str:
        """Determine trend from moving averages.
        
        Args:
            prices: Series of prices
            fast_period: Fast moving average period
            slow_period: Slow moving average period
            
        Returns:
            'UPTREND', 'DOWNTREND', or 'SIDEWAYS'
        """
        if len(prices) < slow_period:
            return 'SIDEWAYS'
        
        ma_fast = prices.rolling(window=fast_period).mean()
        ma_slow = prices.rolling(window=slow_period).mean()
        
        latest_fast = ma_fast.iloc[-1]
        latest_slow = ma_slow.iloc[-1]
        
        if latest_fast > latest_slow * 1.01:  # 1% threshold
            return 'UPTREND'
        elif latest_fast < latest_slow * 0.99:  # 1% threshold
            return 'DOWNTREND'
        else:
            return 'SIDEWAYS'

    @staticmethod
    def apply_trend_filter(signal: int, trend: str) -> int:
        """Filter signal based on trend.
        
        Args:
            signal: Trading signal (1, -1, or 0)
            trend: Current trend ('UPTREND', 'DOWNTREND', 'SIDEWAYS')
            
        Returns:
            Filtered signal (may return 0 if conflicting with trend)
        """
        if signal == 0:
            return 0
        
        # Reduce risk by only taking signals aligned with trend
        if trend == 'UPTREND' and signal == -1:
            return 0  # Don't short in uptrend
        elif trend == 'DOWNTREND' and signal == 1:
            return 0  # Don't buy in downtrend
        
        return signal

    @staticmethod
    def get_signal_strength(
        agreement_count: int,
        timeframe_count: int = 2,
    ) -> str:
        """Get signal strength based on how many timeframes agree.
        
        Args:
            agreement_count: Number of agreeing timeframes
            timeframe_count: Total timeframes checked
            
        Returns:
            'WEAK', 'MEDIUM', or 'STRONG'
        """
        agreement_ratio = agreement_count / timeframe_count if timeframe_count > 0 else 0
        
        if agreement_ratio >= 0.75:
            return 'STRONG'
        elif agreement_ratio >= 0.5:
            return 'MEDIUM'
        else:
            return 'WEAK'
