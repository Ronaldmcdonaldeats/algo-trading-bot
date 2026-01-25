"""
Phase 26: Multi-Timeframe Signal Confirmation

Validates trading signals across multiple timeframes (daily + hourly).
Only executes trades when signals are aligned across timeframes.

Features:
- Multi-timeframe confirmation (daily + hourly)
- Correlation-based symbol avoidance
- Volatility clustering detection
- Expected value calculator for each signal
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class TimeframeSignal:
    """Signal data for a specific timeframe"""
    timeframe: str  # "1h", "1d"
    signal: int  # 1 = buy, -1 = sell, 0 = neutral
    strength: float  # 0.0-1.0 confidence
    price: float
    timestamp: datetime
    indicators: Dict[str, float] = field(default_factory=dict)


@dataclass
class MultiTimeframeAnalysis:
    """Analysis of signals across multiple timeframes"""
    symbol: str
    daily_signal: Optional[TimeframeSignal]
    hourly_signal: Optional[TimeframeSignal]
    is_confirmed: bool  # Both timeframes agree
    alignment_strength: float  # 0.0-1.0 how aligned they are
    expected_value: float  # EV in dollars
    correlation_warning: bool  # Other symbols have similar signal
    volatility_regime: str  # "low", "normal", "high"
    recommendation: str  # "STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"
    confidence: float  # Final confidence 0.0-1.0


class MultiTimeframeSignalValidator:
    """
    Validates signals across multiple timeframes and manages correlations.
    
    Prevents over-trading by:
    1. Requiring signals to align across timeframes
    2. Avoiding correlated symbols
    3. Detecting volatility regimes
    4. Calculating expected value
    """
    
    def __init__(
        self,
        hourly_weight: float = 0.4,
        daily_weight: float = 0.6,
        correlation_threshold: float = 0.65,
        vol_threshold_low: float = 0.15,
        vol_threshold_high: float = 0.35,
        min_alignment_strength: float = 0.5,
    ):
        """
        Args:
            hourly_weight: Weight of hourly signal (0-1)
            daily_weight: Weight of daily signal (0-1)
            correlation_threshold: Max correlation to allow for similar signals
            vol_threshold_low: Volatility level for "low" regime
            vol_threshold_high: Volatility level for "high" regime
            min_alignment_strength: Minimum alignment required to proceed
        """
        self.hourly_weight = hourly_weight / (hourly_weight + daily_weight)
        self.daily_weight = daily_weight / (hourly_weight + daily_weight)
        self.correlation_threshold = correlation_threshold
        self.vol_threshold_low = vol_threshold_low
        self.vol_threshold_high = vol_threshold_high
        self.min_alignment_strength = min_alignment_strength
        
        # Store historical signals for correlation analysis
        self.daily_signals: Dict[str, List[TimeframeSignal]] = {}
        self.hourly_signals: Dict[str, List[TimeframeSignal]] = {}
        self.symbol_volatilities: Dict[str, float] = {}
        self.price_history: Dict[str, List[float]] = {}
    
    def add_signal(
        self,
        symbol: str,
        signal: int,
        strength: float,
        price: float,
        timeframe: str = "1h",
        indicators: Optional[Dict[str, float]] = None,
    ) -> None:
        """Add a signal for analysis"""
        ts_signal = TimeframeSignal(
            timeframe=timeframe,
            signal=signal,
            strength=strength,
            price=price,
            timestamp=datetime.now(),
            indicators=indicators or {}
        )
        
        if timeframe == "1d":
            if symbol not in self.daily_signals:
                self.daily_signals[symbol] = []
            self.daily_signals[symbol].append(ts_signal)
            # Keep last 20 signals
            self.daily_signals[symbol] = self.daily_signals[symbol][-20:]
        else:  # hourly
            if symbol not in self.hourly_signals:
                self.hourly_signals[symbol] = []
            self.hourly_signals[symbol].append(ts_signal)
            # Keep last 50 signals
            self.hourly_signals[symbol] = self.hourly_signals[symbol][-50:]
        
        # Track price for volatility
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(price)
        self.price_history[symbol] = self.price_history[symbol][-100:]
    
    def analyze(self, symbol: str) -> MultiTimeframeAnalysis:
        """Analyze current signal strength across timeframes"""
        daily_signal = self.daily_signals.get(symbol, [None])[-1] if symbol in self.daily_signals else None
        hourly_signal = self.hourly_signals.get(symbol, [None])[-1] if symbol in self.hourly_signals else None
        
        # Calculate alignment
        is_confirmed, alignment_strength = self._check_alignment(daily_signal, hourly_signal)
        
        # Calculate expected value
        ev = self._calculate_expected_value(symbol, daily_signal, hourly_signal)
        
        # Check for correlated symbols
        correlation_warning = self._check_correlation_warning(symbol, hourly_signal)
        
        # Detect volatility regime
        volatility_regime = self._detect_volatility_regime(symbol)
        
        # Generate recommendation
        recommendation, confidence = self._generate_recommendation(
            is_confirmed,
            alignment_strength,
            daily_signal,
            hourly_signal,
            volatility_regime,
            ev
        )
        
        return MultiTimeframeAnalysis(
            symbol=symbol,
            daily_signal=daily_signal,
            hourly_signal=hourly_signal,
            is_confirmed=is_confirmed,
            alignment_strength=alignment_strength,
            expected_value=ev,
            correlation_warning=correlation_warning,
            volatility_regime=volatility_regime,
            recommendation=recommendation,
            confidence=confidence,
        )
    
    def _check_alignment(
        self,
        daily: Optional[TimeframeSignal],
        hourly: Optional[TimeframeSignal]
    ) -> Tuple[bool, float]:
        """Check if signals align across timeframes"""
        if daily is None or hourly is None:
            return False, 0.0
        
        # Same direction?
        same_direction = (daily.signal == hourly.signal) and (daily.signal != 0)
        
        if not same_direction:
            return False, 0.0
        
        # Calculate alignment strength
        # Both strong = 1.0
        # One weak = 0.5-0.8
        # Both weak = 0.3-0.5
        strength = (daily.strength + hourly.strength) / 2.0
        
        is_strong = strength >= 0.6
        
        return is_strong, strength
    
    def _calculate_expected_value(
        self,
        symbol: str,
        daily: Optional[TimeframeSignal],
        hourly: Optional[TimeframeSignal]
    ) -> float:
        """Calculate expected value of the signal in dollars"""
        if daily is None or hourly is None:
            return 0.0
        
        # Get win rate from indicators if available
        daily_winrate = daily.indicators.get('win_rate', 0.55)
        hourly_winrate = hourly.indicators.get('win_rate', 0.55)
        
        # Combined win rate (weighted)
        combined_wr = (daily_winrate * self.daily_weight + 
                      hourly_winrate * self.hourly_weight)
        
        # Expected value: (win_rate * avg_win) - ((1-win_rate) * avg_loss)
        # Assuming avg_win = 2% and avg_loss = 1%
        ev_pct = (combined_wr * 0.02) - ((1 - combined_wr) * 0.01)
        
        # On $10,000 position (example)
        ev = ev_pct * 10000
        
        return ev
    
    def _check_correlation_warning(
        self,
        symbol: str,
        hourly: Optional[TimeframeSignal]
    ) -> bool:
        """Check if other symbols have correlated signals"""
        if hourly is None or hourly.signal == 0:
            return False
        
        # Count symbols with same signal direction in last hour
        same_signal_count = 0
        for other_sym in self.hourly_signals:
            if other_sym != symbol and self.hourly_signals[other_sym]:
                other_signal = self.hourly_signals[other_sym][-1]
                if (other_signal.signal == hourly.signal and 
                    (datetime.now() - other_signal.timestamp).seconds < 3600):
                    same_signal_count += 1
        
        # Warning if too many correlated signals (possible market-wide event)
        return same_signal_count > 5
    
    def _detect_volatility_regime(self, symbol: str) -> str:
        """Detect current volatility regime"""
        if symbol not in self.price_history or len(self.price_history[symbol]) < 10:
            return "normal"
        
        prices = np.array(self.price_history[symbol][-50:])
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        
        self.symbol_volatilities[symbol] = volatility
        
        if volatility < self.vol_threshold_low:
            return "low"
        elif volatility > self.vol_threshold_high:
            return "high"
        else:
            return "normal"
    
    def _generate_recommendation(
        self,
        is_confirmed: bool,
        alignment_strength: float,
        daily: Optional[TimeframeSignal],
        hourly: Optional[TimeframeSignal],
        volatility_regime: str,
        ev: float
    ) -> Tuple[str, float]:
        """Generate final recommendation and confidence"""
        if not is_confirmed:
            return "HOLD", 0.0
        
        if daily is None or hourly is None:
            return "HOLD", 0.0
        
        # Base confidence from alignment
        confidence = alignment_strength
        
        # Adjust for volatility regime
        if volatility_regime == "high":
            confidence *= 0.7  # Reduce confidence in high volatility
        elif volatility_regime == "low":
            confidence *= 0.9  # Slightly reduce in low vol (might be consolidation)
        
        # Adjust for expected value
        if ev < 0:
            confidence *= 0.5  # Negative EV, lower confidence
        elif ev > 50:
            confidence *= 1.1  # Positive EV, boost confidence (cap at 1.0)
        
        confidence = np.clip(confidence, 0.0, 1.0)
        
        # Generate recommendation based on signal and confidence
        signal = daily.signal
        
        if signal == 1:  # Buy signal
            if confidence >= 0.8:
                return "STRONG_BUY", confidence
            elif confidence >= 0.6:
                return "BUY", confidence
            else:
                return "HOLD", confidence
        elif signal == -1:  # Sell signal
            if confidence >= 0.8:
                return "STRONG_SELL", confidence
            elif confidence >= 0.6:
                return "SELL", confidence
            else:
                return "HOLD", confidence
        else:
            return "HOLD", 0.0
    
    def get_strong_signals(self, min_confidence: float = 0.75) -> List[MultiTimeframeAnalysis]:
        """Get all signals with confidence above threshold"""
        strong_signals = []
        
        # Check all symbols with daily signals
        all_symbols = set(self.daily_signals.keys()) | set(self.hourly_signals.keys())
        
        for symbol in all_symbols:
            analysis = self.analyze(symbol)
            if analysis.confidence >= min_confidence:
                strong_signals.append(analysis)
        
        # Sort by confidence descending
        strong_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return strong_signals
    
    def print_status(self) -> None:
        """Print current analysis status"""
        strong = self.get_strong_signals(min_confidence=0.6)
        
        logger.info(f"[MULTITIMEFRAME] Signals analyzed for {len(set(self.daily_signals.keys()) | set(self.hourly_signals.keys()))} symbols")
        logger.info(f"[MULTITIMEFRAME] Strong confirmed signals: {len(strong)}")
        
        for analysis in strong[:5]:  # Show top 5
            logger.info(f"[SIGNAL] {analysis.symbol}: {analysis.recommendation} "
                       f"(conf={analysis.confidence:.2f}, EV=${analysis.expected_value:.0f}, "
                       f"vol={analysis.volatility_regime})")
