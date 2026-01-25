"""Dynamic stop-loss and take-profit calculation using ATR (Average True Range)."""

from __future__ import annotations

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


class DynamicStops:
    """Calculate dynamic stop-loss and take-profit levels based on volatility."""

    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Average True Range (ATR).
        
        Args:
            high: Series of high prices
            low: Series of low prices
            close: Series of close prices
            period: ATR period (default 14)
            
        Returns:
            Series of ATR values
        """
        # Calculate true range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR as moving average of true range
        atr = tr.rolling(window=period).mean()
        return atr

    @staticmethod
    def get_volatility_adjusted_stops(
        entry_price: float,
        atr: float,
        stop_loss_atr_multiplier: float = 2.0,
        take_profit_atr_multiplier: float = 3.0,
        min_stop_pct: float = 0.01,  # 1% minimum
        max_stop_pct: float = 0.05,  # 5% maximum
    ) -> tuple[float, float]:
        """Calculate stop-loss and take-profit using ATR.
        
        Args:
            entry_price: Entry price for position
            atr: Current ATR value
            stop_loss_atr_multiplier: ATR multiplier for stop (e.g., 2.0 = 2*ATR)
            take_profit_atr_multiplier: ATR multiplier for profit (e.g., 3.0 = 3*ATR)
            min_stop_pct: Minimum stop distance as % (default 1%)
            max_stop_pct: Maximum stop distance as % (default 5%)
            
        Returns:
            Tuple of (stop_loss_price, take_profit_price)
        """
        if entry_price <= 0 or atr <= 0:
            # Fallback to fixed stops
            stop_loss = entry_price * (1 - min_stop_pct)
            take_profit = entry_price * (1 + 0.05)  # 5% profit target
            return stop_loss, take_profit
        
        # Calculate ATR-based distances
        stop_distance = stop_loss_atr_multiplier * atr
        profit_distance = take_profit_atr_multiplier * atr
        
        # Convert to percentages
        stop_pct = stop_distance / entry_price
        profit_pct = profit_distance / entry_price
        
        # Apply limits
        stop_pct = max(min(stop_pct, max_stop_pct), min_stop_pct)
        profit_pct = max(min(profit_pct, 0.10), 0.02)  # Keep between 2-10%
        
        stop_loss = entry_price * (1 - stop_pct)
        take_profit = entry_price * (1 + profit_pct)
        
        return stop_loss, take_profit

    @staticmethod
    def get_volatility_regime(atr: float, entry_price: float) -> str:
        """Classify volatility regime based on ATR.
        
        Args:
            atr: Current ATR value
            entry_price: Current price (for context)
            
        Returns:
            'LOW', 'MEDIUM', or 'HIGH' volatility regime
        """
        if entry_price <= 0:
            return 'MEDIUM'
        
        atr_pct = (atr / entry_price) * 100
        
        # Regimes based on ATR as % of price
        if atr_pct < 0.5:  # Less than 0.5% ATR
            return 'LOW'
        elif atr_pct < 1.5:  # 0.5% - 1.5% ATR
            return 'MEDIUM'
        else:  # More than 1.5% ATR
            return 'HIGH'

    @staticmethod
    def get_position_size_adjustment(volatility_regime: str) -> float:
        """Get position size multiplier based on volatility regime.
        
        Args:
            volatility_regime: 'LOW', 'MEDIUM', or 'HIGH'
            
        Returns:
            Position size multiplier (0.5 - 1.5)
        """
        adjustments = {
            'LOW': 1.5,      # Increase size in low vol
            'MEDIUM': 1.0,   # Normal size in medium vol
            'HIGH': 0.5,     # Reduce size in high vol
        }
        return adjustments.get(volatility_regime, 1.0)
