"""Volume Profile breakout strategy.

Entry: Price breaks above volume-weighted resistance with increasing volume
Exit: Price returns below volume-weighted support
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pandas as pd
import numpy as np

from trading_bot.strategy.base import StrategyOutput


@dataclass
class VolumeProfileStrategy:
    """Volume Profile based breakout strategy."""
    
    name: str = "volume_profile"
    lookback: int = 20
    volume_sma_period: int = 14
    
    def evaluate(self, df: pd.DataFrame) -> StrategyOutput:
        """
        Generate trading signal based on Volume Profile.
        
        Long signal: Price breaks above POC (Point of Control) with volume spike
        Exit: Price falls below POC or volume dries up
        """
        if df.empty:
            return StrategyOutput(signal=0, confidence=0.0, explanation={"error": "empty_df"})
        
        required_cols = ["Close", "Volume", "High", "Low"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing {col} column")
        
        if len(df) < self.lookback:
            return StrategyOutput(
                signal=0,
                confidence=0.0,
                explanation={
                    "error": "insufficient_data",
                    "rows": len(df),
                    "lookback": self.lookback,
                },
            )
        
        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float)
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        
        # Calculate volume-weighted average price (VWAP)
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).rolling(self.lookback).sum() / volume.rolling(self.lookback).sum()
        
        # Volume profile: find price level with highest volume concentration
        lookback_data = df.tail(self.lookback)
        volume_weighted_high = (lookback_data["High"] * lookback_data["Volume"]).sum() / lookback_data["Volume"].sum()
        volume_weighted_low = (lookback_data["Low"] * lookback_data["Volume"]).sum() / lookback_data["Volume"].sum()
        poc = (volume_weighted_high + volume_weighted_low) / 2  # Point of Control
        
        # Calculate volume indicators
        volume_sma = volume.rolling(self.volume_sma_period).mean()
        current_volume = volume.iloc[-1]
        avg_volume = volume_sma.iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        current_close = close.iloc[-1]
        prev_close = close.iloc[-2] if len(close) > 1 else current_close
        
        confidence = 0.0
        signal = 0
        explanation: Dict[str, Any] = {
            "current_close": float(current_close),
            "poc": float(poc),
            "current_volume": float(current_volume),
            "avg_volume": float(avg_volume),
            "volume_ratio": float(volume_ratio),
        }
        
        # Long signal: Price breaks above POC with volume spike
        if current_close > poc and prev_close <= poc and volume_ratio > 1.2:
            signal = 1
            # Confidence increases with stronger volume
            confidence = min(0.95, 0.5 + (volume_ratio - 1.0) * 0.3)
            explanation["signal_reason"] = "poc_breakout_with_volume"
        
        # Exit signal: Price falls back below POC or volume dries up
        elif current_close < poc or volume_ratio < 0.8:
            signal = 0
            explanation["signal_reason"] = "poc_breakdown_or_low_volume"
        
        return StrategyOutput(
            signal=signal,
            confidence=confidence,
            explanation=explanation
        )
