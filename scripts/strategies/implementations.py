"""Strategy implementations"""

from typing import Dict, Tuple
import numpy as np
from .base import BaseStrategy


class UltraEnsembleStrategy(BaseStrategy):
    """Phase 12 Ultra Ensemble - 6 expert classifiers with weighted voting"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        trend = (ma50 - ma200) / ma200
        
        deltas = np.diff(prices[-14:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains) if len(gains) > 0 else 0
        al = np.mean(losses) if len(losses) > 0 else 0
        rsi = 100 - (100 / (1 + ag/al)) if al > 0 else 50
        
        momentum = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        
        ma20 = np.mean(prices[-20:])
        std20 = np.std(prices[-20:])
        bb_upper = ma20 + 2 * std20
        bb_lower = ma20 - 2 * std20
        bb_position = (prices[-1] - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        
        accel_5 = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
        accel_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        acceleration = accel_5 - accel_20
        
        atr_fast = np.mean(np.abs(np.diff(prices[-10:])))
        atr_slow = np.mean(np.abs(np.diff(prices[-50:])))
        vol_ratio = atr_fast / (atr_slow + 1e-6)
        
        return {
            'trend': trend, 'rsi': rsi, 'momentum': momentum,
            'mean_reversion': bb_position, 'acceleration': acceleration, 'vol_ratio': vol_ratio
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        trend_signal = 1.0 if features['trend'] > 0.01 else (-1.0 if features['trend'] < -0.01 else 0.0)
        rsi_signal = 0.9 if features['rsi'] < 20 else (-0.9 if features['rsi'] > 80 else 0.0)
        momentum_signal = 1.0 if features['momentum'] > 0.01 else (-1.0 if features['momentum'] < -0.01 else 0.0)
        mr_signal = -0.8 if features['mean_reversion'] > 0.95 else (0.8 if features['mean_reversion'] < 0.05 else 0.0)
        accel_signal = 0.7 if features['acceleration'] > 0.005 else (-0.7 if features['acceleration'] < -0.005 else 0.0)
        vol_signal = 0.4 if features['vol_ratio'] > 1.2 else (-0.3 if features['vol_ratio'] < 0.8 else 0.0)
        
        vote = (trend_signal * 0.40 + rsi_signal * 0.25 + momentum_signal * 0.20 + 
                mr_signal * 0.10 + accel_signal * 0.03 + vol_signal * 0.02)
        
        position_size = self._size_position(vote, features['vol_ratio'])
        
        if prev_signal == 1 and vote > -0.03:
            return 1, position_size
        elif prev_signal == -1 and vote < 0.03:
            return -1, position_size
        
        if vote > self.entry_threshold:
            return 1, position_size
        elif vote < self.exit_threshold:
            return -1, position_size
        return 0, position_size
    
    def _size_position(self, vote: float, vol_ratio: float) -> float:
        if abs(vote) > 0.4:
            size = 1.5
        elif abs(vote) > 0.25:
            size = 1.3
        elif abs(vote) > 0.15:
            size = 1.1
        else:
            size = 0.7
        
        if vol_ratio < 0.8:
            size *= 1.2
        
        return min(size, self.max_position_size)


class TrendFollowingStrategy(BaseStrategy):
    """Simple moving average crossover strategy"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        ma10 = np.mean(prices[-10:])
        
        return {
            'ma10': ma10, 'ma50': ma50, 'ma200': ma200,
            'price': prices[-1], 'trend': (ma50 - ma200) / ma200
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        trend = features['trend']
        ma10 = features['ma10']
        ma50 = features['ma50']
        
        if ma10 > ma50 and trend > 0:
            signal = 1
            position_size = 1.2 if trend > 0.02 else 1.0
        elif ma10 < ma50 and trend < 0:
            signal = -1
            position_size = 1.0
        else:
            signal = 0
            position_size = 0.8
        
        return signal, min(position_size, self.max_position_size)


class MeanReversionStrategy(BaseStrategy):
    """Bollinger Bands mean reversion strategy"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 20:
            return {}
        
        ma20 = np.mean(prices[-20:])
        std20 = np.std(prices[-20:])
        
        return {
            'ma20': ma20,
            'bb_upper': ma20 + 2 * std20,
            'bb_lower': ma20 - 2 * std20,
            'price': prices[-1],
            'position': (prices[-1] - (ma20 - 2*std20)) / (4 * std20) if std20 > 0 else 0.5
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        pos = features['position']
        price = features['price']
        
        if pos < 0.1:  # Oversold, buy
            signal = 1
            position_size = 1.3
        elif pos > 0.9:  # Overbought, sell
            signal = -1
            position_size = 1.0
        else:
            signal = 0
            position_size = 0.8
        
        return signal, min(position_size, self.max_position_size)


class RSIStrategy(BaseStrategy):
    """RSI overbought/oversold strategy"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 14:
            return {}
        
        deltas = np.diff(prices[-14:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains) if len(gains) > 0 else 0
        al = np.mean(losses) if len(losses) > 0 else 0
        rsi = 100 - (100 / (1 + ag/al)) if al > 0 else 50
        
        return {'rsi': rsi, 'price': prices[-1]}
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        rsi = features['rsi']
        
        if rsi < 30:  # Oversold
            signal = 1
            position_size = 1.3
        elif rsi > 70:  # Overbought
            signal = -1
            position_size = 1.0
        else:
            signal = 0
            position_size = 0.7
        
        return signal, min(position_size, self.max_position_size)


class MomentumStrategy(BaseStrategy):
    """Price momentum strategy"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 20:
            return {}
        
        momentum_5 = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
        momentum_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        momentum_50 = (prices[-1] - prices[-50]) / prices[-50] if prices[-50] != 0 else 0
        
        return {
            'momentum_5': momentum_5,
            'momentum_20': momentum_20,
            'momentum_50': momentum_50,
            'price': prices[-1]
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        m5 = features['momentum_5']
        m20 = features['momentum_20']
        
        if m5 > 0.01 and m20 > 0.005:
            signal = 1
            position_size = 1.2 + (m5 * 5)  # More leverage in strong momentum
        elif m5 < -0.01 and m20 < -0.005:
            signal = -1
            position_size = 1.0
        else:
            signal = 0
            position_size = 0.7
        
        return signal, min(position_size, self.max_position_size)


class VolatilityStrategy(BaseStrategy):
    """ATR-based volatility breakout strategy"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 50:
            return {}
        
        atr_10 = np.mean(np.abs(np.diff(prices[-10:])))
        atr_50 = np.mean(np.abs(np.diff(prices[-50:])))
        recent_return = (prices[-1] - prices[-10]) / prices[-10] if prices[-10] != 0 else 0
        
        return {
            'atr_10': atr_10,
            'atr_50': atr_50,
            'vol_ratio': atr_10 / (atr_50 + 1e-6),
            'recent_return': recent_return,
            'price': prices[-1]
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        vol_ratio = features['vol_ratio']
        ret = features['recent_return']
        
        # High volatility + positive return = breakout
        if vol_ratio > 1.3 and ret > 0.005:
            signal = 1
            position_size = 1.4
        elif vol_ratio > 1.3 and ret < -0.005:
            signal = -1
            position_size = 1.0
        else:
            signal = 0
            position_size = 0.6
        
        return signal, min(position_size, self.max_position_size)


class HybridStrategy(BaseStrategy):
    """Hybrid combining trend, RSI, and momentum"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        # Trend
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        trend = (ma50 - ma200) / ma200
        
        # RSI
        deltas = np.diff(prices[-14:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains) if len(gains) > 0 else 0
        al = np.mean(losses) if len(losses) > 0 else 0
        rsi = 100 - (100 / (1 + ag/al)) if al > 0 else 50
        
        # Momentum
        momentum = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        
        return {'trend': trend, 'rsi': rsi, 'momentum': momentum, 'price': prices[-1]}
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        trend_vote = 1.0 if features['trend'] > 0.01 else (-1.0 if features['trend'] < -0.01 else 0.0)
        rsi_vote = 0.8 if features['rsi'] < 35 else (-0.8 if features['rsi'] > 65 else 0.0)
        mom_vote = 1.0 if features['momentum'] > 0.01 else (-1.0 if features['momentum'] < -0.01 else 0.0)
        
        vote = trend_vote * 0.5 + rsi_vote * 0.3 + mom_vote * 0.2
        position_size = 0.8 + abs(vote)
        
        if vote > 0.15:
            return 1, min(position_size, self.max_position_size)
        elif vote < -0.15:
            return -1, min(position_size, self.max_position_size)
        return 0, min(position_size, self.max_position_size)


class RiskAdjustedTrendStrategy(BaseStrategy):
    """Conservative trend-following with volatility adjustment for consistent outperformance"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        # Long-term trend
        ma100 = np.mean(prices[-100:])
        ma200 = np.mean(prices[-200:])
        long_trend = (ma100 - ma200) / ma200
        
        # Short-term momentum
        ma20 = np.mean(prices[-20:])
        short_trend = (ma20 - ma100) / ma100
        
        # Volatility
        returns = np.diff(prices[-60:]) / prices[-59:]
        volatility = np.std(returns)
        
        # Average True Range
        atr = np.mean(np.abs(np.diff(prices[-30:])))
        atr_pct = atr / prices[-1]
        
        return {
            'long_trend': long_trend,
            'short_trend': short_trend,
            'volatility': volatility,
            'atr_pct': atr_pct
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        # Only trade when both trends align and volatility is reasonable
        long_ok = features['long_trend'] > 0.002
        short_ok = features['short_trend'] > 0.001
        vol_ok = features['volatility'] < 0.03
        
        # Risk-adjusted position sizing
        base_size = 1.0
        if features['volatility'] > 0.025:
            base_size *= 0.8  # Reduce in high volatility
        
        if long_ok and short_ok and vol_ok:
            size = base_size + 0.3
            return 1, min(size, self.max_position_size)
        elif not long_ok and features['long_trend'] < -0.002:
            size = base_size * 0.9
            return -1, min(size, self.max_position_size)
        else:
            return 0, base_size


class AdaptiveMovingAverageStrategy(BaseStrategy):
    """Adaptive MA lengths based on market conditions for consistent returns"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        # Calculate volatility regime
        returns = np.diff(prices[-60:]) / prices[-59:]
        volatility = np.std(returns)
        
        # Adaptive lookback: shorter MAs in low vol, longer in high vol
        if volatility < 0.015:
            short_period, long_period = 20, 50
        elif volatility < 0.025:
            short_period, long_period = 30, 100
        else:
            short_period, long_period = 50, 150
        
        ma_short = np.mean(prices[-short_period:])
        ma_long = np.mean(prices[-long_period:])
        
        trend_strength = (ma_short - ma_long) / ma_long
        
        # Slope of MAs
        ma_short_slope = (np.mean(prices[-short_period:-short_period//2]) - np.mean(prices[-short_period//2:])) / ma_short
        
        return {
            'trend_strength': trend_strength,
            'ma_slope': ma_short_slope,
            'volatility': volatility
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        trend = features['trend_strength']
        slope = features['ma_slope']
        vol = features['volatility']
        
        # Position size based on trend strength AND slope
        if trend > 0.01 and slope < 0.001:  # Uptrend with increasing strength
            size = 1.1 - (vol * 20)  # Reduce if volatile
            return 1, min(max(0.7, size), self.max_position_size)
        elif trend < -0.01 and slope > -0.001:  # Downtrend
            size = 0.9
            return -1, min(size, self.max_position_size)
        else:
            return 0, 0.8


class CompositeQualityStrategy(BaseStrategy):
    """Quality signals combining multiple uncorrelated indicators"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        # 1. Trend strength (normalized)
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        trend = (ma50 - ma200) / ma200
        
        # 2. Price position in range (0-1)
        high_50 = np.max(prices[-50:])
        low_50 = np.min(prices[-50:])
        range_position = (prices[-1] - low_50) / (high_50 - low_50) if high_50 != low_50 else 0.5
        
        # 3. Volume-weighted momentum
        returns = np.diff(prices[-20:]) / prices[-19:]
        momentum = np.mean(returns[returns > 0]) - np.mean(np.abs(returns[returns < 0]))
        
        # 4. Mean reversion signal
        ma20 = np.mean(prices[-20:])
        deviation = (prices[-1] - ma20) / ma20
        
        return {
            'trend': trend,
            'range_pos': range_position,
            'momentum': momentum,
            'deviation': deviation
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        # Scoring system: higher score = stronger buy
        score = 0
        
        # Trend (0-2 points)
        if features['trend'] > 0.02:
            score += 2
        elif features['trend'] > 0.005:
            score += 1
        elif features['trend'] < -0.005:
            score -= 1
        
        # Position in range (0-1.5 points)
        if 0.6 < features['range_pos'] < 0.9:
            score += 1.5  # In upper part, trending up
        elif features['range_pos'] < 0.4:
            score += 0.5  # Oversold, potential bounce
        
        # Momentum (0-1.5 points)
        if features['momentum'] > 0.005:
            score += 1.5
        elif features['momentum'] < -0.005:
            score -= 1
        
        # Mean reversion (0-1 point)
        if -0.03 < features['deviation'] < 0.03:
            score += 1
        elif features['deviation'] > 0.05:
            score -= 0.5
        
        # Convert score to signal
        size = 0.7 + (score * 0.15)
        
        if score > 2.5:
            return 1, min(1.5, size)
        elif score < -1.5:
            return -1, min(1.0, size)
        else:
            return 0, size


class VolatilityAdaptiveStrategy(BaseStrategy):
    """Strategy that adapts position size and thresholds based on market volatility"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 100:
            return {}
        
        # Calculate realized volatility
        returns = np.diff(prices[-60:]) / prices[-59:]
        volatility = np.std(returns)
        volatility_ma = np.std(np.diff(prices[-100:]) / prices[-99:])
        
        # Trend
        ma50 = np.mean(prices[-50:])
        ma100 = np.mean(prices[-100:])
        trend = (ma50 - ma100) / ma100
        
        # Momentum with decay
        momentum_fast = (prices[-1] - prices[-10]) / prices[-10] if prices[-10] != 0 else 0
        momentum_slow = (prices[-1] - prices[-30]) / prices[-30] if prices[-30] != 0 else 0
        
        # RSI
        deltas = np.diff(prices[-14:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains)
        al = np.mean(losses)
        rsi = 100 - (100 / (1 + ag/al)) if al > 0 else 50
        
        return {
            'volatility': volatility,
            'volatility_ma': volatility_ma,
            'trend': trend,
            'momentum_fast': momentum_fast,
            'momentum_slow': momentum_slow,
            'rsi': rsi
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        vol = features['volatility']
        vol_hist = features['volatility_ma']
        
        # Adapt thresholds based on volatility regime
        if vol < 0.015:  # Low volatility - can be more aggressive
            trend_threshold = 0.005
            base_size = 1.3
        elif vol < 0.025:  # Normal volatility
            trend_threshold = 0.01
            base_size = 1.0
        else:  # High volatility - be conservative
            trend_threshold = 0.02
            base_size = 0.7
        
        trend = features['trend']
        rsi = features['rsi']
        mom = features['momentum_fast']
        
        # Multi-signal confirmation
        trend_ok = trend > trend_threshold
        rsi_ok = rsi < 65
        mom_ok = mom > 0.005
        
        if trend_ok and rsi_ok and mom_ok:
            size = base_size + 0.2
            return 1, min(1.4, size)
        elif trend < -trend_threshold:
            size = base_size * 0.8
            return -1, min(1.0, size)
        else:
            return 0, base_size * 0.75


class EnhancedEnsembleStrategy(BaseStrategy):
    """Improved ensemble with better signal validation and position sizing"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        # 6 independent signals
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        trend_signal = (ma50 - ma200) / ma200
        
        # RSI with better thresholds
        deltas = np.diff(prices[-14:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        ag = np.mean(gains)
        al = np.mean(losses)
        rsi = 100 - (100 / (1 + ag/al)) if al > 0 else 50
        
        # Momentum
        momentum = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        
        # Mean reversion
        ma20 = np.mean(prices[-20:])
        std20 = np.std(prices[-20:])
        bb_position = (prices[-1] - (ma20 - 2*std20)) / (4*std20) if std20 > 0 else 0.5
        
        # MACD-like signal
        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        macd = ema12 - ema26
        
        # Volatility
        atr = np.mean(np.abs(np.diff(prices[-20:])))
        vol_signal = atr / prices[-1]
        
        return {
            'trend': trend_signal,
            'rsi': rsi,
            'momentum': momentum,
            'bb_pos': bb_position,
            'macd': macd,
            'atr': vol_signal
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        # Score each signal (0 = neutral, 1 = bullish, -1 = bearish)
        signals = 0
        
        # Trend (40% weight) - most important
        if features['trend'] > 0.015:
            signals += 1
        elif features['trend'] < -0.015:
            signals -= 1
        
        # RSI (25% weight)
        if features['rsi'] < 25:
            signals += 0.8
        elif features['rsi'] > 75:
            signals -= 0.8
        elif 40 < features['rsi'] < 60:
            signals += 0  # Neutral
        
        # Momentum (20% weight)
        if features['momentum'] > 0.015:
            signals += 0.8
        elif features['momentum'] < -0.015:
            signals -= 0.8
        
        # Mean Reversion (10% weight)
        if features['bb_pos'] < 0.1:
            signals += 0.5
        elif features['bb_pos'] > 0.9:
            signals -= 0.5
        
        # MACD (3% weight)
        if features['macd'] > 0:
            signals += 0.2
        
        # Volatility adaptation (2% weight)
        if features['atr'] > 0.03:  # High volatility
            signals *= 0.9  # Be cautious
        
        # Position sizing
        size = 0.7 + (abs(signals) * 0.3)
        
        if signals > 1.2:
            return 1, min(1.5, size)
        elif signals < -1.2:
            return -1, min(1.0, size)
        else:
            return 0, min(1.0, size)
    
    def _ema(self, prices: np.ndarray, period: int) -> float:
        """Calculate EMA for the last price"""
        if len(prices) < period:
            return prices[-1]
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = price * multiplier + ema * (1 - multiplier)
        
        return ema
