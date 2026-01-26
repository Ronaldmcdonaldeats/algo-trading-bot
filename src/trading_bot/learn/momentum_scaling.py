"""
Momentum-based position scaling.
Scale position sizes up/down based on momentum indicator strength.
Higher momentum = larger positions, lower momentum = smaller.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List


@dataclass
class MomentumMetrics:
    """Momentum analysis for a symbol"""
    symbol: str
    timestamp: datetime
    momentum_score: float  # -1.0 (strong down) to +1.0 (strong up)
    momentum_strength: float  # 0.0 (weak) to 1.0 (very strong)
    rsi_momentum: float  # From RSI (0-1, 0.5=neutral)
    macd_momentum: float  # From MACD (0-1, 0.5=neutral)
    price_momentum: float  # From price change (0-1, 0.5=neutral)
    volume_momentum: float  # From volume surge (0-1, 0.5=neutral)
    
    def scaling_multiplier(self) -> float:
        """
        Get position size multiplier based on momentum
        Returns 0.5 to 1.5x multiplier
        """
        # Use momentum strength to scale, centered at 1.0
        base_multiplier = 1.0
        
        # Scale by strength: at 0.8+ strength, go up to 1.3x
        if self.momentum_strength > 0.7:
            base_multiplier = 1.0 + (self.momentum_strength - 0.7) * 1.0  # +0.3x at full strength
        elif self.momentum_strength < 0.3:
            base_multiplier = 0.7 + self.momentum_strength  # Down to 0.7x at 0% strength
        
        # Adjust by momentum direction
        if self.momentum_score > 0.3:
            # Strong buy momentum: boost to 1.3-1.5x
            base_multiplier = min(1.5, base_multiplier * (1.0 + self.momentum_score * 0.3))
        elif self.momentum_score < -0.3:
            # Strong sell momentum: reduce to 0.5-0.7x
            base_multiplier = max(0.5, base_multiplier * (0.8 + self.momentum_score * 0.3))
        
        return np.clip(base_multiplier, 0.5, 1.5)
    
    def should_take_trade(self, min_strength: float = 0.4) -> bool:
        """Check if momentum is strong enough for a trade"""
        return self.momentum_strength >= min_strength


class MomentumScaler:
    """
    Calculate momentum metrics and position scaling multipliers.
    Uses multiple indicators to gauge true momentum.
    """
    
    def __init__(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        momentum_lookback: int = 20,
    ):
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.momentum_lookback = momentum_lookback
        
        self.metrics: Dict[str, MomentumMetrics] = {}
    
    def calculate_momentum(self, ohlcv: pd.DataFrame) -> Optional[MomentumMetrics]:
        """
        Calculate momentum metrics from OHLCV data
        
        Args:
            ohlcv: DataFrame with OHLC data
            
        Returns:
            MomentumMetrics or None if insufficient data
        """
        if len(ohlcv) < max(self.momentum_lookback, self.macd_slow):
            return None
        
        symbol = ohlcv.index.name or "UNKNOWN"
        close = ohlcv['Close'].values
        volume = ohlcv['Volume'].values if 'Volume' in ohlcv.columns else None
        
        # 1. RSI Momentum
        rsi_momentum = self._calculate_rsi_momentum(close)
        
        # 2. MACD Momentum
        macd_momentum = self._calculate_macd_momentum(close)
        
        # 3. Price Momentum (rate of change)
        price_momentum = self._calculate_price_momentum(close)
        
        # 4. Volume Momentum
        volume_momentum = self._calculate_volume_momentum(volume) if volume is not None else 0.5
        
        # Combine into composite momentum score (-1 to +1)
        raw_momentum = (
            (rsi_momentum - 0.5) * 2 +
            (macd_momentum - 0.5) * 2 +
            (price_momentum - 0.5) * 2 +
            (volume_momentum - 0.5) * 1  # Volume less weight
        ) / 7.0
        momentum_score = np.clip(raw_momentum, -1.0, 1.0)
        
        # Momentum strength = how confident we are in the direction
        momentum_strength = abs(momentum_score)
        
        return MomentumMetrics(
            symbol=symbol,
            timestamp=pd.Timestamp.now(),
            momentum_score=float(momentum_score),
            momentum_strength=float(momentum_strength),
            rsi_momentum=float(rsi_momentum),
            macd_momentum=float(macd_momentum),
            price_momentum=float(price_momentum),
            volume_momentum=float(volume_momentum),
        )
    
    def _calculate_rsi_momentum(self, close: np.ndarray) -> float:
        """
        RSI-based momentum: 0=oversold, 0.5=neutral, 1=overbought
        """
        if len(close) < self.rsi_period:
            return 0.5
        
        # Calculate RSI
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.mean(gain[-self.rsi_period:])
        avg_loss = np.mean(loss[-self.rsi_period:])
        
        if avg_loss == 0:
            rsi = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100.0 - (100.0 / (1.0 + rs))
        
        # Convert to 0-1 scale
        return np.clip(rsi / 100.0, 0.0, 1.0)
    
    def _calculate_macd_momentum(self, close: np.ndarray) -> float:
        """
        MACD-based momentum: 0=bearish, 0.5=neutral, 1=bullish
        """
        if len(close) < self.macd_slow:
            return 0.5
        
        # Calculate exponential moving averages
        ema_fast = self._ewma(close, self.macd_fast)
        ema_slow = self._ewma(close, self.macd_slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = self._ewma(macd_line, self.macd_signal)
        
        # MACD momentum: positive when above signal
        if signal_line[-1] == 0:
            return 0.5
        
        macd_diff = macd_line[-1] - signal_line[-1]
        momentum = 0.5 + np.tanh(macd_diff / (abs(signal_line[-1]) + 1e-6)) * 0.5
        
        return np.clip(momentum, 0.0, 1.0)
    
    def _calculate_price_momentum(self, close: np.ndarray) -> float:
        """
        Price momentum: % change over lookback period
        0=down, 0.5=flat, 1=up
        """
        if len(close) < self.momentum_lookback:
            return 0.5
        
        # Calculate ROC (Rate of Change)
        current_price = close[-1]
        past_price = close[-self.momentum_lookback]
        
        if past_price == 0:
            return 0.5
        
        roc = (current_price - past_price) / past_price
        
        # Convert to 0-1 scale with saturation at ±10%
        momentum = 0.5 + np.tanh(roc / 0.1) * 0.5
        
        return np.clip(momentum, 0.0, 1.0)
    
    def _calculate_volume_momentum(self, volume: np.ndarray) -> float:
        """
        Volume momentum: is volume increasing?
        0=low vol, 0.5=avg vol, 1=surge
        """
        if len(volume) < 10:
            return 0.5
        
        # Current volume vs moving average
        current_vol = volume[-1]
        avg_vol = np.mean(volume[-20:])
        
        if avg_vol == 0:
            return 0.5
        
        vol_ratio = current_vol / avg_vol
        
        # 0.5x = 0, 1x = 0.5, 2x = 1.0
        momentum = np.tanh((vol_ratio - 1.0) * 1.5) * 0.5 + 0.5
        
        return np.clip(momentum, 0.0, 1.0)
    
    def _ewma(self, data: np.ndarray, span: int) -> np.ndarray:
        """Calculate exponential weighted moving average"""
        return pd.Series(data).ewm(span=span, adjust=False).mean().values
    
    def update_metrics(self, symbol: str, ohlcv: pd.DataFrame) -> Optional[MomentumMetrics]:
        """Update momentum metrics for a symbol"""
        ohlcv.index.name = symbol
        metrics = self.calculate_momentum(ohlcv)
        if metrics:
            self.metrics[symbol] = metrics
        return metrics
    
    def get_scaling_multiplier(self, symbol: str) -> float:
        """Get position size multiplier for a symbol (0.5-1.5)"""
        if symbol not in self.metrics:
            return 1.0
        return self.metrics[symbol].scaling_multiplier()
    
    def get_momentum_score(self, symbol: str) -> Optional[float]:
        """Get momentum score for a symbol (-1 to +1)"""
        if symbol not in self.metrics:
            return None
        return self.metrics[symbol].momentum_score
    
    def get_strong_momentum_symbols(self, min_strength: float = 0.6) -> List[str]:
        """Get symbols with strong momentum"""
        return [
            sym for sym, metrics in self.metrics.items()
            if metrics.momentum_strength >= min_strength
        ]
    
    def print_summary(self):
        """Print momentum summary for all symbols"""
        if not self.metrics:
            print("[MOMENTUM] No metrics calculated")
            return
        
        print("\n[MOMENTUM SCALING REPORT]")
        
        # Sort by momentum strength
        sorted_metrics = sorted(
            self.metrics.items(),
            key=lambda x: x[1].momentum_strength,
            reverse=True
        )
        
        for symbol, metrics in sorted_metrics[:10]:  # Top 10
            direction = "↑" if metrics.momentum_score > 0.3 else "↓" if metrics.momentum_score < -0.3 else "→"
            multiplier = metrics.scaling_multiplier()
            print(f"  {symbol}: {direction} score={metrics.momentum_score:+.2f} " +
                  f"strength={metrics.momentum_strength:.2f} multiplier={multiplier:.2f}x")
