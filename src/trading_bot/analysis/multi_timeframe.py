"""Multi-timeframe analysis - combine signals from 1m, 5m, 15m, 1h, 1d."""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum


class Signal(Enum):
    """Trade signal strength."""
    STRONG_BUY = 1.0
    BUY = 0.5
    NEUTRAL = 0.0
    SELL = -0.5
    STRONG_SELL = -1.0


class TimeFrames(Enum):
    """Available timeframes."""
    ONE_MINUTE = "1m"
    FIVE_MINUTE = "5m"
    FIFTEEN_MINUTE = "15m"
    ONE_HOUR = "1h"
    FOUR_HOUR = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


class MultiTimeframeAnalyzer:
    """Analyze signals across multiple timeframes for stronger entries/exits."""
    
    # Timeframe hierarchy (for weighting)
    TIMEFRAME_WEIGHTS = {
        "1m": 0.1,
        "5m": 0.15,
        "15m": 0.2,
        "1h": 0.25,
        "4h": 0.15,
        "1d": 0.15
    }
    
    def __init__(self):
        self.signals = {}  # {symbol: {timeframe: signal}}
        self.confluences = {}  # {symbol: confluence_score}
    
    def analyze_timeframe(
        self,
        symbol: str,
        timeframe: str,
        price: float,
        sma_20: float,
        sma_50: float,
        sma_200: float,
        rsi: float,
        macd: float,
        volume: float,
        avg_volume: float
    ) -> Signal:
        """
        Analyze single timeframe and generate signal.
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe (1m, 5m, 15m, 1h, 1d)
            price: Current price
            sma_20: 20-period SMA
            sma_50: 50-period SMA
            sma_200: 200-period SMA
            rsi: RSI (0-100)
            macd: MACD value
            volume: Current volume
            avg_volume: Average volume
        
        Returns:
            Signal strength
        """
        signals_list = []
        
        # Trend signal (SMAs)
        if price > sma_20 > sma_50 > sma_200:
            signals_list.append(1.0)  # Strong uptrend
        elif price > sma_50 > sma_200:
            signals_list.append(0.5)  # Uptrend
        elif price < sma_20 < sma_50 < sma_200:
            signals_list.append(-1.0)  # Strong downtrend
        elif price < sma_50 < sma_200:
            signals_list.append(-0.5)  # Downtrend
        else:
            signals_list.append(0.0)  # Neutral
        
        # Momentum signal (RSI)
        if rsi < 30:
            signals_list.append(-0.5)  # Oversold
        elif rsi < 40:
            signals_list.append(-0.2)
        elif rsi > 70:
            signals_list.append(0.5)  # Overbought
        elif rsi > 60:
            signals_list.append(0.2)
        else:
            signals_list.append(0.0)
        
        # MACD signal
        if macd > 0:
            signals_list.append(0.5 if macd > 0.1 else 0.25)
        elif macd < 0:
            signals_list.append(-0.5 if macd < -0.1 else -0.25)
        else:
            signals_list.append(0.0)
        
        # Volume signal
        if volume > avg_volume * 1.5:
            signals_list.append(0.3)  # High volume on move
        elif volume < avg_volume * 0.7:
            signals_list.append(-0.1)  # Low volume (weak)
        else:
            signals_list.append(0.0)
        
        # Average signal across indicators
        avg_signal = np.mean(signals_list)
        
        # Map to signal strength
        if avg_signal >= 0.7:
            return Signal.STRONG_BUY
        elif avg_signal >= 0.3:
            return Signal.BUY
        elif avg_signal <= -0.7:
            return Signal.STRONG_SELL
        elif avg_signal <= -0.3:
            return Signal.SELL
        else:
            return Signal.NEUTRAL
    
    def calculate_confluence(
        self,
        symbol: str,
        signals_by_timeframe: Dict[str, Signal]
    ) -> Dict[str, Any]:
        """
        Calculate signal confluence across timeframes.
        
        Strong signal = multiple timeframes aligned
        
        Args:
            symbol: Stock symbol
            signals_by_timeframe: {timeframe: Signal}
        
        Returns:
            {
                'confluence_score': 0-1,
                'aligned_count': number of timeframes aligned,
                'dominant_direction': 'up', 'down', 'neutral',
                'signal_strength': 'strong', 'moderate', 'weak'
            }
        """
        self.signals[symbol] = signals_by_timeframe
        
        # Convert signals to numeric
        numeric_signals = {tf: s.value for tf, s in signals_by_timeframe.items()}
        
        # Calculate weighted average
        weights_sum = 0
        weighted_signal = 0
        aligned_count = 0
        
        for tf, signal_val in numeric_signals.items():
            weight = self.TIMEFRAME_WEIGHTS.get(tf, 0.1)
            weighted_signal += signal_val * weight
            weights_sum += weight
            
            if signal_val > 0.3:  # Consider as aligned if positive
                aligned_count += 1
            elif signal_val < -0.3:
                aligned_count += 1
        
        confluence_score = weighted_signal / weights_sum if weights_sum > 0 else 0
        
        # Determine direction
        if confluence_score > 0.3:
            direction = 'up'
        elif confluence_score < -0.3:
            direction = 'down'
        else:
            direction = 'neutral'
        
        # Determine strength
        if abs(confluence_score) > 0.7:
            strength = 'strong'
        elif abs(confluence_score) > 0.4:
            strength = 'moderate'
        else:
            strength = 'weak'
        
        result = {
            'confluence_score': confluence_score,
            'aligned_count': aligned_count,
            'total_timeframes': len(signals_by_timeframe),
            'dominant_direction': direction,
            'signal_strength': strength,
            'signals_by_timeframe': {tf: s.name for tf, s in signals_by_timeframe.items()},
            'timestamp': datetime.now().isoformat()
        }
        
        self.confluences[symbol] = result
        return result
    
    def find_buy_setup(
        self,
        symbol: str,
        signals_by_timeframe: Dict[str, Signal],
        min_confluence: float = 0.4
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Find high-probability buy setup using confluence.
        
        Requirements:
        1. At least 3 timeframes show buy signal
        2. Confluence score > threshold
        3. Larger timeframe (1d) is favorable
        
        Returns:
            (is_valid_setup, details)
        """
        confluence = self.calculate_confluence(symbol, signals_by_timeframe)
        
        # Check daily timeframe
        daily_signal = signals_by_timeframe.get('1d', Signal.NEUTRAL)
        daily_favorable = daily_signal.value > 0
        
        # Check minimum confluence
        confluence_ok = confluence['confluence_score'] > min_confluence
        
        # Check minimum aligned timeframes
        min_aligned = 3
        aligned_ok = confluence['aligned_count'] >= min_aligned
        
        is_valid = confluence_ok and aligned_ok and daily_favorable
        
        details = {
            'setup_valid': is_valid,
            'reason': self._get_setup_reason(confluence, daily_favorable, confluence_ok, aligned_ok),
            'confluence': confluence,
            'entry_bias': 'strong' if confluence['confluence_score'] > 0.6 else 'moderate'
        }
        
        return is_valid, details
    
    def find_sell_setup(
        self,
        symbol: str,
        signals_by_timeframe: Dict[str, Signal],
        min_confluence: float = -0.4
    ) -> Tuple[bool, Dict[str, Any]]:
        """Find high-probability sell setup using confluence."""
        
        confluence = self.calculate_confluence(symbol, signals_by_timeframe)
        
        # Check daily timeframe
        daily_signal = signals_by_timeframe.get('1d', Signal.NEUTRAL)
        daily_favorable = daily_signal.value < 0
        
        # Check minimum confluence
        confluence_ok = confluence['confluence_score'] < min_confluence
        
        # Check minimum aligned timeframes
        min_aligned = 3
        aligned_ok = confluence['aligned_count'] >= min_aligned
        
        is_valid = confluence_ok and aligned_ok and daily_favorable
        
        details = {
            'setup_valid': is_valid,
            'reason': self._get_setup_reason(confluence, daily_favorable, confluence_ok, aligned_ok),
            'confluence': confluence,
            'entry_bias': 'strong' if confluence['confluence_score'] < -0.6 else 'moderate'
        }
        
        return is_valid, details
    
    def _get_setup_reason(self, confluence, daily_fav, conf_ok, aligned_ok) -> str:
        """Generate human-readable reason for setup validity."""
        if not daily_fav:
            return "Daily timeframe not favorable"
        if not conf_ok:
            return "Confluence score insufficient"
        if not aligned_ok:
            return "Not enough timeframes aligned"
        return "Setup valid - high probability entry"
    
    def get_multi_timeframe_report(self, symbol: str) -> Dict[str, Any]:
        """Generate comprehensive multi-timeframe analysis report."""
        
        if symbol not in self.confluences:
            return {'error': 'No analysis for symbol'}
        
        confluence = self.confluences[symbol]
        signals = self.signals.get(symbol, {})
        
        return {
            'symbol': symbol,
            'confluence': confluence,
            'signals_by_timeframe': {tf: s.name for tf, s in signals.items()},
            'timestamp': datetime.now().isoformat(),
            'recommendation': self._get_recommendation(confluence)
        }
    
    def _get_recommendation(self, confluence: Dict[str, Any]) -> str:
        """Generate trading recommendation."""
        score = confluence['confluence_score']
        strength = confluence['signal_strength']
        direction = confluence['dominant_direction']
        
        if direction == 'up' and strength == 'strong':
            return "STRONG BUY - Multiple timeframes aligned bullish"
        elif direction == 'up' and strength == 'moderate':
            return "BUY - Timeframes showing bullish bias"
        elif direction == 'down' and strength == 'strong':
            return "STRONG SELL - Multiple timeframes aligned bearish"
        elif direction == 'down' and strength == 'moderate':
            return "SELL - Timeframes showing bearish bias"
        else:
            return "HOLD - Insufficient confluence for directional trade"
    
    def get_optimal_entry_timeframe(self, symbol: str) -> str:
        """
        Suggest which timeframe to enter on (highest confluence).
        
        Returns:
            Timeframe with strongest aligned signal
        """
        if symbol not in self.signals:
            return "1h"
        
        signals = self.signals[symbol]
        
        # Find strongest signal
        best_tf = max(
            signals.items(),
            key=lambda x: abs(x[1].value)
        )[0]
        
        return best_tf
    
    def get_optimal_exit_timeframe(self, symbol: str) -> str:
        """
        Suggest which timeframe to watch for exit (fastest reversals).
        
        Returns:
            Fastest timeframe showing reversal
        """
        if symbol not in self.signals:
            return "5m"
        
        signals = self.signals[symbol]
        
        # Watch faster timeframes for exit (1m, 5m, 15m)
        fast_frames = {tf: sig for tf, sig in signals.items() if tf in ['1m', '5m', '15m']}
        
        if not fast_frames:
            return "5m"
        
        # Return fastest frame
        return min(fast_frames.keys(), key=lambda x: ['1m', '5m', '15m'].index(x))
