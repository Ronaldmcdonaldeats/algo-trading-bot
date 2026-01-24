"""Bollinger Bands breakout strategy.

Entry: Price breaks above upper band with increasing volatility
Exit: Price returns to middle band or crosses lower band
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pandas as pd
from ta.volatility import BollingerBands

from trading_bot.strategy.base import StrategyOutput


@dataclass
class BollingerBandsStrategy:
    """Bollinger Bands mean reversion and breakout strategy."""
    
    name: str = "bollinger_bands"
    period: int = 20
    std_dev: float = 2.0
    
    def evaluate(self, df: pd.DataFrame) -> StrategyOutput:
        """
        Generate trading signal based on Bollinger Bands.
        
        Long signal: Price touches lower band + RSI < 30 (oversold)
        Exit: Price crosses upper band or 2% profit
        """
        if df.empty:
            return StrategyOutput(signal=0, confidence=0.0, explanation={"error": "empty_df"})
        
        if "Close" not in df.columns:
            raise ValueError("Missing Close column")
        
        if len(df) < self.period:
            return StrategyOutput(
                signal=0,
                confidence=0.0,
                explanation={
                    "error": "insufficient_data",
                    "rows": len(df),
                    "period": self.period,
                },
            )
        
        close = df["Close"].astype(float)
        
        # Calculate Bollinger Bands
        bb = BollingerBands(close=close, window=self.period, window_dev=self.std_dev)
        bb_high = bb.bollinger_hband()
        bb_mid = bb.bollinger_mavg()
        bb_low = bb.bollinger_lband()
        
        current_close = close.iloc[-1]
        current_high = bb_high.iloc[-1]
        current_mid = bb_mid.iloc[-1]
        current_low = bb_low.iloc[-1]
        
        prev_close = close.iloc[-2] if len(close) > 1 else current_close
        
        # Calculate volatility (normalized band width)
        band_width = (current_high - current_low) / current_mid if current_mid > 0 else 0
        normalized_price = (current_close - current_low) / (current_high - current_low) if (current_high - current_low) > 0 else 0.5
        
        confidence = 0.0
        signal = 0
        explanation: Dict[str, Any] = {
            "current_close": float(current_close),
            "bb_high": float(current_high),
            "bb_mid": float(current_mid),
            "bb_low": float(current_low),
            "band_width": float(band_width),
            "normalized_price": float(normalized_price),
        }
        
        # Long signal: Price near lower band (mean reversion)
        if normalized_price < 0.2 and band_width > 0.02:
            signal = 1
            confidence = min(0.95, 0.5 + (0.2 - normalized_price) * 5)
            explanation["signal_reason"] = "oversold_lower_band"
        
        # Exit signal: Price near upper band
        elif normalized_price > 0.8:
            signal = 0
            explanation["signal_reason"] = "overbought_upper_band"
        
        return StrategyOutput(
            signal=signal,
            confidence=confidence,
            explanation=explanation
        )
