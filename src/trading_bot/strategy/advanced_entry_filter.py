"""
Advanced entry filtering.
Validates entry conditions before executing trades.
Prevents entries on poor price action, low volume, gaps, etc.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List


@dataclass
class EntryValidation:
    """Entry validation result"""
    symbol: str
    timestamp: datetime
    
    # Individual checks
    price_action_valid: bool
    volume_valid: bool
    volatility_valid: bool
    gap_valid: bool
    trend_alignment: bool
    momentum_valid: bool
    
    # Overall assessment
    is_valid: bool
    confidence: float  # 0-1, higher = more confident in entry
    reasons: List[str] = None  # Why entry is invalid (if not valid)
    
    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []


class AdvancedEntryFilter:
    """
    Advanced entry filter to validate trade entries.
    Checks price action, volume, gaps, trend, momentum before allowing entry.
    """
    
    def __init__(
        self,
        min_volume_ratio: float = 1.2,  # Volume must be 20% above average
        min_volume_bars: int = 20,
        max_gap_pct: float = 3.0,  # Reject if gap >3%
        volatility_bands: Tuple[float, float] = (0.01, 0.05),  # Reject if vol too low/high
        price_action_lookback: int = 5,
        trend_confirmation_bars: int = 2,
    ):
        self.min_volume_ratio = min_volume_ratio
        self.min_volume_bars = min_volume_bars
        self.max_gap_pct = max_gap_pct
        self.volatility_bands = volatility_bands
        self.price_action_lookback = price_action_lookback
        self.trend_confirmation_bars = trend_confirmation_bars
        
        self.validation_history: Dict[str, EntryValidation] = {}
        self.stats = {
            "total_validations": 0,
            "valid_entries": 0,
            "rejected_volume": 0,
            "rejected_gap": 0,
            "rejected_price_action": 0,
            "rejected_volatility": 0,
        }
    
    def validate_entry(
        self,
        symbol: str,
        ohlcv: pd.DataFrame,
        signal: int,  # 1=buy, -1=sell, 0=neutral
    ) -> EntryValidation:
        """
        Validate if entry signal is valid
        
        Args:
            symbol: Stock symbol
            ohlcv: Historical OHLCV data (at least 20 bars)
            signal: Buy (1) or sell (-1) signal
            
        Returns:
            EntryValidation with detailed checks
        """
        self.stats["total_validations"] += 1
        reasons = []
        
        if len(ohlcv) < 20:
            return EntryValidation(
                symbol=symbol,
                timestamp=pd.Timestamp.now(),
                price_action_valid=False,
                volume_valid=False,
                volatility_valid=False,
                gap_valid=False,
                trend_alignment=False,
                momentum_valid=False,
                is_valid=False,
                confidence=0.0,
                reasons=["Insufficient data"],
            )
        
        # Check 1: Price Action
        price_action_valid, pa_reason = self._check_price_action(ohlcv, signal)
        if not price_action_valid:
            reasons.append(pa_reason)
            self.stats["rejected_price_action"] += 1
        
        # Check 2: Volume
        volume_valid, vol_reason = self._check_volume(ohlcv)
        if not volume_valid:
            reasons.append(vol_reason)
            self.stats["rejected_volume"] += 1
        
        # Check 3: Volatility
        volatility_valid, vol_reason = self._check_volatility(ohlcv)
        if not volatility_valid:
            reasons.append(vol_reason)
            self.stats["rejected_volatility"] += 1
        
        # Check 4: Gap
        gap_valid, gap_reason = self._check_gap(ohlcv)
        if not gap_valid:
            reasons.append(gap_reason)
            self.stats["rejected_gap"] += 1
        
        # Check 5: Trend Alignment
        trend_aligned, trend_reason = self._check_trend_alignment(ohlcv, signal)
        
        # Check 6: Momentum
        momentum_valid, mom_reason = self._check_momentum(ohlcv, signal)
        
        # Overall assessment
        critical_passed = price_action_valid and volume_valid and gap_valid
        overall_valid = critical_passed and volatility_valid
        
        # Confidence score
        checks_passed = sum([price_action_valid, volume_valid, volatility_valid, gap_valid, trend_aligned, momentum_valid])
        confidence = checks_passed / 6.0
        
        validation = EntryValidation(
            symbol=symbol,
            timestamp=pd.Timestamp.now(),
            price_action_valid=price_action_valid,
            volume_valid=volume_valid,
            volatility_valid=volatility_valid,
            gap_valid=gap_valid,
            trend_alignment=trend_aligned,
            momentum_valid=momentum_valid,
            is_valid=overall_valid,
            confidence=confidence,
            reasons=reasons,
        )
        
        self.validation_history[symbol] = validation
        
        if overall_valid:
            self.stats["valid_entries"] += 1
        
        return validation
    
    def _check_price_action(self, ohlcv: pd.DataFrame, signal: int) -> tuple[bool, str]:
        """Check if price action looks healthy (not choppy)"""
        close = ohlcv['close'].values
        high = ohlcv['high'].values
        low = ohlcv['low'].values
        
        lookback = min(self.price_action_lookback, len(close) - 1)
        
        if signal == 1:  # Buy signal
            # For buys: price should be making higher lows
            lows = low[-lookback:]
            if len(lows) > 1:
                higher_lows = np.sum(np.diff(lows) > 0)
                if higher_lows < 2:
                    return False, "Buy: Price action not confirming uptrend"
        
        elif signal == -1:  # Sell signal
            # For sells: price should be making lower highs
            highs = high[-lookback:]
            if len(highs) > 1:
                lower_highs = np.sum(np.diff(highs) < 0)
                if lower_highs < 2:
                    return False, "Sell: Price action not confirming downtrend"
        
        return True, ""
    
    def _check_volume(self, ohlcv: pd.DataFrame) -> tuple[bool, str]:
        """Check if volume is sufficient"""
        if 'volume' not in ohlcv.columns:
            return True, ""  # Skip if no volume data
        
        volume = ohlcv['volume'].values
        
        # Current volume should be above average
        recent_volume = volume[-1]
        avg_volume = np.mean(volume[-self.min_volume_bars:])
        
        if avg_volume == 0:
            return True, ""
        
        volume_ratio = recent_volume / avg_volume
        
        if volume_ratio < self.min_volume_ratio:
            return False, f"Volume ratio {volume_ratio:.2f}x below minimum {self.min_volume_ratio}x"
        
        return True, ""
    
    def _check_volatility(self, ohlcv: pd.DataFrame) -> tuple[bool, str]:
        """Check if volatility is in acceptable range"""
        close = ohlcv['close'].values
        
        # Calculate recent volatility
        returns = np.diff(close) / close[:-1]
        recent_vol = np.std(returns[-20:])
        
        vol_min, vol_max = self.volatility_bands
        
        if recent_vol < vol_min:
            return False, f"Volatility {recent_vol:.4f} too low (min {vol_min})"
        
        if recent_vol > vol_max:
            return False, f"Volatility {recent_vol:.4f} too high (max {vol_max})"
        
        return True, ""
    
    def _check_gap(self, ohlcv: pd.DataFrame) -> tuple[bool, str]:
        """Check if there's a suspicious gap"""
        close = ohlcv['close'].values
        open_prices = ohlcv['open'].values
        
        if len(close) < 2:
            return True, ""
        
        # Gap between previous close and current open
        prev_close = close[-2]
        current_open = open_prices[-1]
        
        if prev_close == 0:
            return True, ""
        
        gap_pct = abs(current_open - prev_close) / prev_close * 100
        
        if gap_pct > self.max_gap_pct:
            return False, f"Gap {gap_pct:.2f}% exceeds maximum {self.max_gap_pct}%"
        
        return True, ""
    
    def _check_trend_alignment(self, ohlcv: pd.DataFrame, signal: int) -> tuple[bool, str]:
        """Check if signal aligns with overall trend"""
        close = ohlcv['close'].values
        
        # Calculate short and long term trends
        sma_5 = np.mean(close[-5:])
        sma_20 = np.mean(close[-20:])
        
        current_price = close[-1]
        
        if signal == 1:  # Buy signal
            if current_price < sma_20:
                return False, "Price below 20-day SMA"
            return True, ""
        
        elif signal == -1:  # Sell signal
            if current_price > sma_20:
                return False, "Price above 20-day SMA"
            return True, ""
        
        return True, ""
    
    def _check_momentum(self, ohlcv: pd.DataFrame, signal: int) -> tuple[bool, str]:
        """Check if momentum supports the signal"""
        close = ohlcv['close'].values
        
        # Simple momentum: rate of change
        if len(close) < 10:
            return True, ""
        
        recent_returns = (close[-1] - close[-10]) / close[-10]
        
        if signal == 1 and recent_returns < 0:
            return False, "Negative momentum for buy signal"
        
        if signal == -1 and recent_returns > 0:
            return False, "Positive momentum for sell signal"
        
        return True, ""
    
    def get_validation_rate(self) -> float:
        """Get percentage of validations that passed"""
        if self.stats["total_validations"] == 0:
            return 0.0
        
        return self.stats["valid_entries"] / self.stats["total_validations"]
    
    def print_summary(self):
        """Print entry filter summary"""
        total = self.stats["total_validations"]
        
        if total == 0:
            print("[ENTRY FILTER] No validations yet")
            return
        
        print("\n[ENTRY FILTER REPORT]")
        print(f"  Total validations: {total}")
        print(f"  Valid entries: {self.stats['valid_entries']} ({self.get_validation_rate()*100:.1f}%)")
        print(f"  Rejections:")
        print(f"    - Price action: {self.stats['rejected_price_action']}")
        print(f"    - Volume: {self.stats['rejected_volume']}")
        print(f"    - Volatility: {self.stats['rejected_volatility']}")
        print(f"    - Gap: {self.stats['rejected_gap']}")
