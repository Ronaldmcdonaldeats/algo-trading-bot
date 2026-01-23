"""Market regime detection for adaptive strategy selection.

Detects trending, ranging, and volatile regimes to inform strategy weighting.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd


class Regime(Enum):
    """Market regimes."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class RegimeState:
    """Current market regime with confidence and supporting metrics."""
    regime: Regime
    confidence: float  # 0.0-1.0
    volatility: float  # annualized
    trend_strength: float  # 0.0-1.0 (how strong the trend)
    support: Optional[float] = None
    resistance: Optional[float] = None
    explanation: dict[str, float | str] = None

    def __post_init__(self):
        if self.explanation is None:
            object.__setattr__(self, "explanation", {})


def _atr_volatility(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Estimate annualized volatility from ATR."""
    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]
    if atr <= 0 or close.iloc[-1] <= 0:
        return 0.0
    # Approximate annualized volatility from ATR
    return float((atr / close.iloc[-1]) * (252**0.5))


def _sma_crossover_trend(close: pd.Series, fast: int = 10, slow: int = 30) -> tuple[float, float]:
    """Trend strength via SMA crossover. Returns (trend_strength, trend_direction).
    
    trend_direction: -1.0 (down), 0 (neutral), +1.0 (up)
    trend_strength: 0.0-1.0
    """
    if len(close) < slow:
        return 0.0, 0.0
    
    sma_fast = close.rolling(window=fast).mean()
    sma_slow = close.rolling(window=slow).mean()
    
    last_fast = float(sma_fast.iloc[-1]) if pd.notna(sma_fast.iloc[-1]) else 0.0
    last_slow = float(sma_slow.iloc[-1]) if pd.notna(sma_slow.iloc[-1]) else 0.0
    last_close = float(close.iloc[-1])
    
    if last_slow <= 0:
        return 0.0, 0.0
    
    # Trend direction
    if last_fast > last_slow:
        direction = 1.0
    elif last_fast < last_slow:
        direction = -1.0
    else:
        direction = 0.0
    
    # Trend strength: how far apart the SMAs are (as % of price)
    strength = abs(last_fast - last_slow) / last_slow
    strength = min(1.0, strength / 0.05)  # normalize to 5% separation
    
    return float(strength), float(direction)


def _support_resistance(high: pd.Series, low: pd.Series, lookback: int = 20) -> tuple[Optional[float], Optional[float]]:
    """Find recent support and resistance levels."""
    if len(high) < lookback:
        return None, None
    
    recent_high = float(high.tail(lookback).max())
    recent_low = float(low.tail(lookback).min())
    
    return recent_low, recent_high


def detect_regime(df: pd.DataFrame) -> RegimeState:
    """Detect current market regime.
    
    Args:
        df: OHLCV DataFrame with High, Low, Close columns
    
    Returns:
        RegimeState with regime, confidence, and metrics
    """
    if df.empty or len(df) < 14:
        return RegimeState(
            regime=Regime.INSUFFICIENT_DATA,
            confidence=0.0,
            volatility=0.0,
            trend_strength=0.0,
            explanation={"reason": "insufficient_data", "rows": len(df)},
        )
    
    close = df["Close"].astype(float)
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    
    # Calculate metrics
    volatility = _atr_volatility(high, low, close, period=14)
    trend_strength, trend_direction = _sma_crossover_trend(close, fast=10, slow=30)
    support, resistance = _support_resistance(high, low, lookback=20)
    
    # Determine regime
    # High volatility takes precedence
    if volatility > 0.40:  # 40% annualized vol
        regime = Regime.VOLATILE
        confidence = min(1.0, volatility / 0.60)
    # Trend-based classification
    elif trend_strength > 0.5:
        if trend_direction > 0:
            regime = Regime.TRENDING_UP
        else:
            regime = Regime.TRENDING_DOWN
        confidence = trend_strength
    # Low volatility + weak trend = ranging
    else:
        regime = Regime.RANGING
        confidence = 1.0 - trend_strength
    
    return RegimeState(
        regime=regime,
        confidence=float(min(1.0, confidence)),
        volatility=float(volatility),
        trend_strength=float(trend_strength),
        support=support,
        resistance=resistance,
        explanation={
            "volatility_annualized": round(volatility, 4),
            "trend_strength": round(trend_strength, 4),
            "trend_direction": float(trend_direction),
            "support": round(support, 2) if support else None,
            "resistance": round(resistance, 2) if resistance else None,
        },
    )


# Regime-aware strategy weights: maps regime to ideal strategy focus
REGIME_STRATEGY_AFFINITY = {
    Regime.RANGING: {
        "mean_reversion_rsi": 0.60,  # RSI excels in ranges
        "momentum_macd_volume": 0.20,
        "breakout_atr": 0.20,
    },
    Regime.TRENDING_UP: {
        "mean_reversion_rsi": 0.10,
        "momentum_macd_volume": 0.70,  # MACD good for trends
        "breakout_atr": 0.20,
    },
    Regime.TRENDING_DOWN: {
        "mean_reversion_rsi": 0.10,
        "momentum_macd_volume": 0.70,
        "breakout_atr": 0.20,
    },
    Regime.VOLATILE: {
        "mean_reversion_rsi": 0.20,
        "momentum_macd_volume": 0.20,
        "breakout_atr": 0.60,  # ATR breakout handles volatility
    },
    Regime.INSUFFICIENT_DATA: {
        "mean_reversion_rsi": 0.33,
        "momentum_macd_volume": 0.33,
        "breakout_atr": 0.34,
    },
}


def regime_adjusted_weights(regime_state: RegimeState, learned_weights: dict[str, float]) -> dict[str, float]:
    """Blend regime affinity with learned weights.
    
    Args:
        regime_state: Current market regime
        learned_weights: Ensemble weights from learning
    
    Returns:
        Adjusted weights favoring strategies suited to current regime
    """
    regime_affinity = REGIME_STRATEGY_AFFINITY.get(regime_state.regime, {})
    if not regime_affinity:
        return learned_weights
    
    # Blend: high confidence in regime → lean toward affinity
    # Low confidence → stick with learned weights
    blend = float(regime_state.confidence)
    
    adjusted = {}
    for name in learned_weights.keys():
        affinity = float(regime_affinity.get(name, 1.0 / len(learned_weights)))
        learned = float(learned_weights[name])
        # High confidence in regime → more affinity, less learned weight
        adjusted[name] = (1.0 - blend) * learned + blend * affinity
    
    # Normalize
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {k: v / total for k, v in adjusted.items()}
    
    return adjusted
