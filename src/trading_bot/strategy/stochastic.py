"""Stochastic Oscillator strategy.

Entry: Stochastic crosses above 20 (oversold) in uptrend
Exit: Stochastic crosses below 80 (overbought)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pandas as pd
from ta.momentum import StochasticOscillator

from trading_bot.strategy.base import StrategyOutput


@dataclass
class StochasticStrategy:
    """Stochastic Oscillator mean reversion strategy."""
    
    name: str = "stochastic"
    k_period: int = 14
    d_period: int = 3
    smooth_k: int = 3
    oversold_threshold: float = 20.0
    overbought_threshold: float = 80.0
    
    def evaluate(self, df: pd.DataFrame) -> StrategyOutput:
        """
        Generate trading signal based on Stochastic Oscillator.
        
        Long signal: %K crosses above %D and Stochastic < 20 (oversold)
        Exit: %K crosses below %D or Stochastic > 80 (overbought)
        """
        if df.empty:
            return StrategyOutput(signal=0, confidence=0.0, explanation={"error": "empty_df"})
        
        required_cols = ["High", "Low", "Close"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing {col} column")
        
        if len(df) < self.k_period + self.d_period:
            return StrategyOutput(
                signal=0,
                confidence=0.0,
                explanation={
                    "error": "insufficient_data",
                    "rows": len(df),
                    "required": self.k_period + self.d_period,
                },
            )
        
        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        close = df["Close"].astype(float)
        
        # Calculate Stochastic
        stoch = StochasticOscillator(
            high=high,
            low=low,
            close=close,
            window=self.k_period,
            smooth_window=self.smooth_k
        )
        
        stoch_k = stoch.stoch()
        stoch_d = stoch.stoch_signal()
        
        current_k = stoch_k.iloc[-1]
        current_d = stoch_d.iloc[-1]
        prev_k = stoch_k.iloc[-2] if len(stoch_k) > 1 else current_k
        prev_d = stoch_d.iloc[-2] if len(stoch_d) > 1 else current_d
        
        confidence = 0.0
        signal = 0
        explanation: Dict[str, Any] = {
            "current_k": float(current_k),
            "current_d": float(current_d),
            "oversold_threshold": self.oversold_threshold,
            "overbought_threshold": self.overbought_threshold,
        }
        
        # Long signal: K crosses above D AND in oversold territory
        if prev_k <= prev_d and current_k > current_d and current_k < self.oversold_threshold:
            signal = 1
            # Confidence increases as K rises from oversold
            confidence = min(0.95, 0.5 + (current_k / self.oversold_threshold) * 0.4)
            explanation["signal_reason"] = "k_crosses_above_d_oversold"
        
        # Exit signal: K crosses below D OR enters overbought
        elif (prev_k > prev_d and current_k <= current_d) or current_k > self.overbought_threshold:
            signal = 0
            explanation["signal_reason"] = "k_crosses_below_d_or_overbought"
        
        return StrategyOutput(
            signal=signal,
            confidence=confidence,
            explanation=explanation
        )
