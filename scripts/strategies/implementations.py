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
        returns = np.diff(prices[-60:]) / prices[-60:-1]
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
        # Simple adaptive strategy that works with limited data
        if len(prices) < 20:
            return {}
        
        # Use available data smartly
        lookback = min(60, len(prices))
        
        # Volatility
        if lookback >= 20:
            recent_prices = prices[-lookback:]
            returns = np.diff(recent_prices) / recent_prices[:-1]
            volatility = np.std(returns) if len(returns) > 0 else 0.02
        else:
            volatility = 0.02
        
        # Simple moving averages
        ma_short = np.mean(prices[-min(20, len(prices)):])
        ma_long = np.mean(prices[-min(50, len(prices)):])
        
        trend = (ma_short - ma_long) / ma_long if ma_long != 0 else 0
        
        return {
            'trend': trend,
            'volatility': volatility,
            'price': prices[-1],
            'ma_short': ma_short,
            'ma_long': ma_long
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        trend = features['trend']
        vol = features['volatility']
        
        # Simple trend-following with volatility adjustment
        if trend > 0.005:  # Uptrend
            size = 1.0 - (vol * 10)
            return 1, min(max(0.7, size), 1.5)
        elif trend < -0.005:  # Downtrend
            return -1, 0.9
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
        returns = np.diff(prices[-60:]) / prices[-60:-1]
        volatility = np.std(returns)
        volatility_ma = np.std(np.diff(prices[-100:]) / prices[-100:-1])
        
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


class BreakoutStrategy(BaseStrategy):
    """Breakout strategy - trade when price breaks key levels with volume confirmation"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        min_lookback = 20
        if len(prices) < min_lookback:
            return {}
        
        # Use available lookback
        lookback = min(50, len(prices))
        
        # Breakout levels
        high = np.max(prices[-lookback:])
        low = np.min(prices[-lookback:])
        current = prices[-1]
        
        # Distance from level
        above_high = (current - high) / high if high > 0 else 0
        below_low = (low - current) / low if low > 0 else 0
        
        # Volume proxy: volatility
        if len(prices) >= 20:
            recent_prices = prices[-20:]
            returns = np.diff(recent_prices) / recent_prices[:-1]
            vol_20 = np.std(returns) if len(returns) > 0 else 0.01
        else:
            vol_20 = 0.01
        
        # Trend confirmation
        ma_short = np.mean(prices[-min(20, len(prices)):])
        ma_long = np.mean(prices[-min(50, len(prices)):])
        trend = (ma_short - ma_long) / ma_long if ma_long != 0 else 0
        
        return {
            'above_high': above_high,
            'below_low': below_low,
            'vol_20': vol_20,
            'trend': trend,
            'price': current
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        # Breakout with trend confirmation
        above = features['above_high'] > 0.005
        below = features['below_low'] > 0.005
        trending_up = features['trend'] > 0.01
        trending_down = features['trend'] < -0.01
        
        if above and trending_up and features['vol_20'] > 0.008:
            return 1, 1.2
        elif below and trending_down and features['vol_20'] > 0.008:
            return -1, 1.0
        else:
            return 0, 0.7


class MacdStrategy(BaseStrategy):
    """MACD crossover strategy - moving average convergence divergence"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 26:
            return {}
        
        # Use available data
        lookback = min(60, len(prices))
        recent_prices = prices[-lookback:]
        
        # Fast and slow EMAs
        ema_12 = self._ema(recent_prices, min(12, len(recent_prices)))
        ema_26 = self._ema(recent_prices, min(26, len(recent_prices)))
        macd = ema_12 - ema_26
        
        # Signal line - simplified
        signal_line = ema_12 * 0.8 + ema_26 * 0.2
        
        # MACD histogram
        histogram = macd - signal_line
        
        # Trend
        ma_50 = np.mean(prices[-min(50, len(prices)):]) if len(prices) >= 50 else prices[-1]
        trend = (prices[-1] - ma_50) / ma_50 if ma_50 > 0 else 0
        
        return {
            'macd': macd,
            'signal': signal_line,
            'histogram': histogram,
            'trend': trend
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        # MACD crossover
        macd_above_signal = features['macd'] > features['signal']
        histogram_positive = features['histogram'] > 0
        trending = features['trend'] > 0
        
        if macd_above_signal and histogram_positive and trending:
            size = 1.1 + (abs(features['histogram']) * 2)
            return 1, min(1.5, size)
        elif not macd_above_signal and not histogram_positive and features['trend'] < 0:
            return -1, 1.0
        else:
            return 0, 0.8
    
    def _ema(self, prices: np.ndarray, period: int) -> float:
        if len(prices) < period:
            return prices[-1] if len(prices) > 0 else 0
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        for price in prices[period:]:
            ema = price * multiplier + ema * (1 - multiplier)
        return ema


class StochasticStrategy(BaseStrategy):
    """Stochastic oscillator - momentum indicator with overbought/oversold levels"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 14:
            return {}
        
        # Use available lookback
        lookback = min(14, len(prices))
        recent_prices = prices[-lookback:]
        
        # Stochastic K
        high = np.max(recent_prices)
        low = np.min(recent_prices)
        current = prices[-1]
        k_raw = (current - low) / (high - low) * 100 if high != low else 50
        
        # Simplified K (just use raw for speed)
        k = k_raw
        d = k_raw  # D = K when we have limited data
        
        # Momentum
        if len(prices) >= 5:
            momentum = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
        else:
            momentum = 0
        
        return {
            'k': k,
            'd': d,
            'momentum': momentum
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        k = features['k']
        
        # Oversold (< 20): buy signal
        if k < 20 and features['momentum'] > 0:
            return 1, 1.1
        # Overbought (> 80): sell signal
        elif k > 80 and features['momentum'] < 0:
            return -1, 1.0
        # Middle bands
        elif k > 50 and features['momentum'] > 0:
            return 1, 0.9
        elif k < 50 and features['momentum'] < 0:
            return -1, 0.9
        else:
            return 0, 0.8


class SupportResistanceStrategy(BaseStrategy):
    """Support & Resistance strategy - bounce off key levels"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 20:
            return {}
        
        # Use available lookback
        lookback = min(100, len(prices))
        recent_prices = prices[-lookback:]
        
        # Find levels
        high = np.max(recent_prices)
        low = np.min(recent_prices)
        mid = (high + low) / 2
        
        current = prices[-1]
        
        # Distance from key levels
        dist_to_resistance = (high - current) / high if high > 0 else 0
        dist_to_support = (current - low) / low if low > 0 else 0
        dist_to_middle = abs(current - mid) / mid if mid > 0 else 0
        
        # Price momentum
        if len(prices) >= 5:
            momentum_5 = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
        else:
            momentum_5 = 0
        
        if len(prices) >= 20:
            momentum_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        else:
            momentum_20 = 0
        
        # Mean reversion score
        ma_20 = np.mean(prices[-min(20, len(prices)):])
        deviation = (current - ma_20) / ma_20 if ma_20 != 0 else 0
        
        return {
            'dist_resistance': dist_to_resistance,
            'dist_support': dist_to_support,
            'dist_middle': dist_to_middle,
            'momentum_5': momentum_5,
            'momentum_20': momentum_20,
            'deviation': deviation
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        # Near support with upward momentum = bounce expected
        near_support = features['dist_support'] < 0.03
        bouncing = features['momentum_5'] > 0.005
        mean_revert = features['deviation'] < -0.02
        
        if near_support and bouncing and mean_revert:
            return 1, 1.1
        
        # Near resistance with downward momentum = breakdown expected
        near_resistance = features['dist_resistance'] < 0.03
        falling = features['momentum_5'] < -0.005
        over_extended = features['deviation'] > 0.02
        
        if near_resistance and falling and over_extended:
            return -1, 1.0
        
        # Range-bound trading
        in_middle = 0.02 < features['dist_middle'] < 0.04
        if in_middle and abs(features['momentum_20']) > 0.01:
            return 1 if features['momentum_20'] > 0 else -1, 0.9
        
        return 0, 0.8


class IchimokuStrategy(BaseStrategy):
    """Ichimoku Cloud strategy - Japanese multi-timeframe analysis"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 9:
            return {}
        
        # Tenkan-sen (9-period)
        lookback_9 = min(9, len(prices))
        high_9 = np.max(prices[-lookback_9:])
        low_9 = np.min(prices[-lookback_9:])
        tenkan = (high_9 + low_9) / 2
        
        # Kijun-sen (26-period)
        lookback_26 = min(26, len(prices))
        high_26 = np.max(prices[-lookback_26:])
        low_26 = np.min(prices[-lookback_26:])
        kijun = (high_26 + low_26) / 2
        
        # Senkou Span A (average of above)
        chikou = (tenkan + kijun) / 2
        
        # Senkou Span B (52-period)
        lookback_52 = min(52, len(prices))
        high_52 = np.max(prices[-lookback_52:])
        low_52 = np.min(prices[-lookback_52:])
        senkou_b = (high_52 + low_52) / 2
        
        # Cloud thickness
        cloud_thick = abs(chikou - senkou_b) / senkou_b if senkou_b > 0 else 0
        
        # Price position relative to cloud
        price_above_cloud = prices[-1] > max(chikou, senkou_b)
        price_below_cloud = prices[-1] < min(chikou, senkou_b)
        
        # Trend
        ma_20 = np.mean(prices[-min(20, len(prices)):])
        trend = (prices[-1] - ma_20) / ma_20 if ma_20 > 0 else 0
        
        return {
            'tenkan': tenkan,
            'kijun': kijun,
            'chikou': chikou,
            'senkou_b': senkou_b,
            'cloud_thick': cloud_thick,
            'above_cloud': price_above_cloud,
            'below_cloud': price_below_cloud,
            'trend': trend
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        # Strong bullish: price above cloud, tenkan > kijun, uptrend
        bullish = (features['above_cloud'] and 
                  features['tenkan'] > features['kijun'] and 
                  features['trend'] > 0.01)
        
        if bullish and features['cloud_thick'] > 0.01:
            return 1, 1.15
        
        # Strong bearish: price below cloud, tenkan < kijun, downtrend
        bearish = (features['below_cloud'] and 
                  features['tenkan'] < features['kijun'] and 
                  features['trend'] < -0.01)
        
        if bearish and features['cloud_thick'] > 0.01:
            return -1, 1.0
        
        # Weak signals
        if features['tenkan'] > features['kijun'] and features['trend'] > 0:
            return 1, 0.85
        elif features['tenkan'] < features['kijun'] and features['trend'] < 0:
            return -1, 0.85
        
        return 0, 0.75


class PremiumHybridStrategy(BaseStrategy):
    """PremiumHybrid #1: Combines top 3 realistic strategies (volatility_adaptive, risk_adjusted_trend, enhanced_ensemble)"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 20:
            return {}
        
        # Volatility regime (from volatility_adaptive)
        if len(prices) >= 60:
            returns = np.diff(prices[-60:]) / prices[-60:-1]
            volatility = np.std(returns) if len(returns) > 0 else 0.02
        else:
            volatility = 0.02
        
        # MAs for trend (from risk_adjusted_trend)
        ma20 = np.mean(prices[-min(20, len(prices)):])
        ma50 = np.mean(prices[-min(50, len(prices)):])
        ma200 = np.mean(prices[-min(200, len(prices)):])
        
        # Trend strength
        long_trend = (ma50 - ma200) / ma200 if ma200 != 0 else 0
        short_trend = (ma20 - ma50) / ma50 if ma50 != 0 else 0
        
        # RSI (from enhanced_ensemble concept)
        if len(prices) >= 14:
            delta = np.diff(prices[-14:])
            gain = np.mean([d for d in delta if d > 0]) if any(d > 0 for d in delta) else 0.001
            loss = abs(np.mean([d for d in delta if d < 0])) if any(d < 0 for d in delta) else 0.001
            rs = gain / loss if loss > 0 else 1
            rsi = 100 - (100 / (1 + rs))
        else:
            rsi = 50
        
        # Momentum
        momentum = (prices[-1] - prices[-min(10, len(prices))]) / prices[-min(10, len(prices))] if len(prices) >= 10 else 0
        
        return {
            'volatility': volatility,
            'long_trend': long_trend,
            'short_trend': short_trend,
            'rsi': rsi,
            'momentum': momentum,
            'ma20': ma20,
            'ma50': ma50,
            'ma200': ma200,
            'price': prices[-1]
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        vol = features['volatility']
        long_trend = features['long_trend']
        short_trend = features['short_trend']
        rsi = features['rsi']
        momentum = features['momentum']
        
        # Signal strength combines multiple factors
        bullish_score = 0
        
        # Long-term trend (strong uptrend = +1)
        if long_trend > 0.01:
            bullish_score += 1
        elif long_trend > 0:
            bullish_score += 0.5
        elif long_trend < -0.01:
            bullish_score -= 1
        
        # Short-term trend (uptrend = +1)
        if short_trend > 0.01:
            bullish_score += 1
        elif short_trend < -0.01:
            bullish_score -= 1
        
        # RSI (not overbought/oversold = healthy, neutral = 0)
        if rsi < 30:
            bullish_score += 1  # Oversold = bounce opportunity
        elif rsi > 70:
            bullish_score -= 1  # Overbought = pullback likely
        
        # Momentum confirmation
        if momentum > 0.005:
            bullish_score += 0.5
        elif momentum < -0.005:
            bullish_score -= 0.5
        
        # Determine signal and position size
        if bullish_score > 1.5:
            # Strong buy
            size = 1.3 / (1 + vol * 5)  # Volatility adjustment
            return 1, min(1.5, max(0.8, size))
        elif bullish_score > 0.5:
            # Weak buy
            size = 1.0 / (1 + vol * 5)
            return 1, min(1.2, max(0.7, size))
        elif bullish_score < -1.5:
            # Strong sell
            return -1, 1.0
        elif bullish_score < -0.5:
            # Weak sell
            return -1, 0.85
        else:
            # Neutral
            return 0, 0.8


class SmartHybridStrategy(BaseStrategy):
    """SmartHybrid #2: Conservative strategy with volatility adaptation and quality filters"""
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 20:
            return {}
        
        # Volatility analysis
        if len(prices) >= 60:
            returns = np.diff(prices[-60:]) / prices[-60:-1]
            volatility = np.std(returns) if len(returns) > 0 else 0.02
            volatility_ma = np.std(returns[-20:]) if len(returns) >= 20 else volatility
        else:
            volatility = 0.02
            volatility_ma = 0.02
        
        # Moving averages
        ma10 = np.mean(prices[-10:])
        ma30 = np.mean(prices[-min(30, len(prices)):])
        ma90 = np.mean(prices[-min(90, len(prices)):])
        
        # Trend identification
        uptrend = ma10 > ma30 > ma90
        downtrend = ma10 < ma30 < ma90
        
        # Price position in range
        high_20 = np.max(prices[-20:])
        low_20 = np.min(prices[-20:])
        range_20 = high_20 - low_20
        price_in_range = (prices[-1] - low_20) / range_20 if range_20 > 0 else 0.5
        
        # Momentum (5-day change)
        if len(prices) >= 5:
            momentum = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] > 0 else 0
        else:
            momentum = 0
        
        # Quality: Price consistency (lower = better quality)
        intra_volatility = np.std([prices[i] - prices[i-1] for i in range(-10, -1)]) if len(prices) >= 10 else 0.01
        
        return {
            'volatility': volatility,
            'volatility_ma': volatility_ma,
            'uptrend': uptrend,
            'downtrend': downtrend,
            'ma10': ma10,
            'ma30': ma30,
            'ma90': ma90,
            'price_in_range': price_in_range,
            'momentum': momentum,
            'intra_volatility': intra_volatility,
            'price': prices[-1]
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        vol = features['volatility']
        vol_ma = features['volatility_ma']
        uptrend = features['uptrend']
        downtrend = features['downtrend']
        momentum = features['momentum']
        price_in_range = features['price_in_range']
        quality = features['intra_volatility']
        
        # Conservative positioning
        if uptrend and 0.3 < price_in_range < 0.8 and momentum > 0.002 and vol < 0.03:
            # Good quality uptrend, price not at extremes
            size = 1.0 / (1 + vol * 8)
            return 1, min(1.3, max(0.8, size))
        
        elif downtrend and momentum < -0.002 and vol < 0.03:
            # Clear downtrend
            return -1, 0.9
        
        elif not uptrend and not downtrend:
            # Range-bound: trade range bounces
            if price_in_range < 0.2 and momentum > 0:
                # Near bottom, starting to bounce
                return 1, 0.8
            elif price_in_range > 0.8 and momentum < 0:
                # Near top, starting to decline
                return -1, 0.8
            else:
                return 0, 0.7
        
        else:
            return 0, 0.75


class UltimateHybridStrategy(BaseStrategy):
    """
    ULTIMATE HYBRID: Combines best of all strategies
    - Volatility-adaptive sizing (normal + crash markets)
    - Multi-timeframe momentum (trend confirmation)
    - Mean reversion (exploit panic dips)
    - News/volatility spike detection (handle uncertainty)
    - Risk-adjusted allocation
    
    Target: Beat SPY by 10%+ (20.1% annual return)
    Works in: Normal markets AND uncertain/volatile markets
    """
    
    def __init__(self, name: str = "ultimate_hybrid", config: Dict = None):
        super().__init__(name=name, config=config)
        self.min_position_size = 0.5
        self.max_position_size = 1.6
    
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        if len(prices) < 200:
            return {}
        
        # TIMEFRAME 1: Short-term momentum (5-20 days)
        ma5 = np.mean(prices[-5:])
        ma20 = np.mean(prices[-20:])
        short_momentum = (ma5 - ma20) / ma20 if ma20 != 0 else 0
        short_trend = 1.0 if short_momentum > 0.02 else (-1.0 if short_momentum < -0.02 else 0.0)
        
        # TIMEFRAME 2: Medium-term trend (50 days)
        ma50 = np.mean(prices[-50:])
        ma200 = np.mean(prices[-200:])
        long_momentum = (ma50 - ma200) / ma200 if ma200 != 0 else 0
        long_trend = 1.0 if long_momentum > 0.01 else (-1.0 if long_momentum < -0.01 else 0.0)
        
        # RSI: Overbought/Oversold detection
        deltas = np.diff(prices[-14:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains) if len(gains) > 0 else 0
        avg_loss = np.mean(losses) if len(losses) > 0 else 0
        rsi = 100 - (100 / (1 + avg_gain / (avg_loss + 1e-6))) if avg_loss > 0 else 50
        
        # Bollinger Bands: Mean reversion signal + volatility
        ma20_bb = np.mean(prices[-20:])
        std20 = np.std(prices[-20:])
        bb_upper = ma20_bb + 2 * std20
        bb_lower = ma20_bb - 2 * std20
        bb_position = (prices[-1] - bb_lower) / (bb_upper - bb_lower + 1e-6)
        
        # Volatility Detection (news/uncertainty indicator)
        recent_vol = np.std(np.diff(prices[-20:]) / prices[-20:-1])
        historical_vol = np.std(np.diff(prices[-100:-20]) / prices[-100:-21])
        vol_spike = recent_vol / (historical_vol + 1e-6)
        
        # ATR: Volatility-based position sizing
        atr_fast = np.mean(np.abs(np.diff(prices[-10:])))
        atr_slow = np.mean(np.abs(np.diff(prices[-50:])))
        volatility_ratio = atr_fast / (atr_slow + 1e-6)
        
        # Multi-period momentum confirmation
        momentum_5 = (prices[-1] - prices[-5]) / prices[-5] if prices[-5] != 0 else 0
        momentum_10 = (prices[-1] - prices[-10]) / prices[-10] if prices[-10] != 0 else 0
        momentum_20 = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
        momentum_confirm = 1.0 if momentum_5 > 0 and momentum_10 > 0 and momentum_20 > 0 else -1.0
        
        # Acceleration: Rate of change
        accel = (prices[-1] - prices[-5]) / prices[-5] - (prices[-5] - prices[-10]) / prices[-10] if prices[-10] != 0 and prices[-5] != 0 else 0
        
        # Gap detection (sudden news-driven moves)
        recent_gap = abs(prices[-1] - prices[-2]) / prices[-2] if prices[-2] != 0 else 0
        historical_gap = np.mean(np.abs(np.diff(prices[-50:]) / prices[-50:-1]))
        gap_anomaly = recent_gap / (historical_gap + 1e-6)
        
        return {
            'short_trend': short_trend,
            'long_trend': long_trend,
            'momentum_confirm': momentum_confirm,
            'rsi': rsi,
            'bb_position': bb_position,
            'volatility_ratio': volatility_ratio,
            'vol_spike': vol_spike,
            'momentum_5': momentum_5,
            'momentum_10': momentum_10,
            'momentum_20': momentum_20,
            'acceleration': accel,
            'gap_anomaly': gap_anomaly
        }
    
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        if not features:
            return 0, 1.0
        
        # SCORE SIGNAL COMPONENTS (each -1 to +1)
        
        # 1. Trend Score (40% weight) - NORMAL + CRASH MARKET
        trend_score = (features['short_trend'] * 0.4 + 
                      features['long_trend'] * 0.6)  # Favor long-term
        
        # 2. Momentum Confirmation (20% weight) - HANDLES UNCERTAINTY
        momentum_score = features['momentum_confirm'] * (
            min(abs(features['momentum_5']), abs(features['momentum_10']), 
                abs(features['momentum_20'])) / 0.02 if features['momentum_5'] != 0 else 0
        )
        momentum_score = max(-1.0, min(1.0, momentum_score))
        
        # 3. Mean Reversion Score (20% weight) - BUY DIPS, SELL PEAKS
        if features['bb_position'] < 0.2:
            mr_score = 0.9  # Strong oversold
        elif features['bb_position'] < 0.4:
            mr_score = 0.5  # Mild oversold
        elif features['bb_position'] > 0.8:
            mr_score = -0.9  # Strong overbought
        elif features['bb_position'] > 0.6:
            mr_score = -0.5  # Mild overbought
        else:
            mr_score = 0.0
        
        # 4. Volatility/News Sensitivity (15% weight) - HANDLES UNCERTAIN MARKETS
        vol_signal = 0.0
        if features['vol_spike'] > 1.5:
            # High volatility - reduce position (protect in crashes)
            vol_signal = -0.4
        elif features['vol_spike'] < 0.7:
            # Low volatility - increase confidence
            vol_signal = 0.3
        
        # Gap anomaly in high volatility = news event
        if features['gap_anomaly'] > 2.0 and features['vol_spike'] > 1.3:
            # Major news move + high volatility = uncertainty flag
            vol_signal -= 0.3  # Be more cautious
        
        # 5. RSI Confirmation (5% weight) - CONFIRMATION SIGNAL
        rsi_signal = 0.0
        if features['rsi'] > 80:
            rsi_signal = -0.6  # Overbought
        elif features['rsi'] < 20:
            rsi_signal = 0.6  # Oversold
        elif features['rsi'] > 70:
            rsi_signal = -0.3
        elif features['rsi'] < 30:
            rsi_signal = 0.3
        
        # AGGREGATE SIGNAL (weighted combination)
        vote = (trend_score * 0.40 +      # Trend is most important
               momentum_score * 0.20 +     # Confirmation is critical
               mr_score * 0.20 +           # Exploit opportunities
               vol_signal * 0.15 +         # Risk management
               rsi_signal * 0.05)          # Confirmation
        
        # POSITION SIZING: Adaptive based on confidence + volatility
        position_size = self._calculate_position_size(vote, features)
        
        # ENTRY/EXIT LOGIC WITH HYSTERESIS (prevent whipsaws)
        entry_threshold = 0.15
        exit_threshold = -0.15
        
        if prev_signal == 1:
            # In long position, be sticky (require stronger signal to exit)
            if vote < exit_threshold:
                return -1, position_size
            else:
                return 1, position_size
        elif prev_signal == -1:
            # In short position, require re-confirmation
            if vote > entry_threshold:
                return 1, position_size
            else:
                return -1, position_size
        else:
            # Neutral: wait for stronger signals
            if vote > entry_threshold:
                return 1, position_size
            elif vote < exit_threshold:
                return -1, position_size
            else:
                return 0, position_size
    
    def _calculate_position_size(self, vote: float, features: Dict[str, float]) -> float:
        """
        Dynamic position sizing:
        - High conviction + low volatility = max size
        - High conviction + high volatility = reduce (risk management)
        - Low conviction = reduce
        """
        base_size = 1.0
        
        # Conviction-based sizing
        conviction = abs(vote)
        if conviction > 0.50:
            size = 1.6  # High conviction
        elif conviction > 0.30:
            size = 1.4  # Good conviction
        elif conviction > 0.15:
            size = 1.2  # Moderate conviction
        else:
            size = 0.8  # Low conviction
        
        # Volatility adjustment (handle uncertain markets)
        vol_ratio = features['volatility_ratio']
        if vol_ratio > 1.5:
            # High volatility - reduce size for risk
            size *= 0.7
        elif vol_ratio > 1.2:
            size *= 0.85
        elif vol_ratio < 0.7:
            # Low volatility - can be more aggressive
            size *= 1.15
        
        # News/gap adjustment
        if features['gap_anomaly'] > 2.5:
            # Extreme gap - reduce until we understand the move
            size *= 0.6
        elif features['gap_anomaly'] > 1.8:
            size *= 0.8
        
        # Volatility spike protection
        if features['vol_spike'] > 2.0:
            # Extreme volatility (panic) - retreat to 50% size
            size *= 0.5
        elif features['vol_spike'] > 1.5:
            size *= 0.75
        
        # Never go below minimum or above maximum
        return min(max(size, self.min_position_size), self.max_position_size)
    
    def evaluate(self, df):
        """
        Evaluate strategy on DataFrame with OHLCV and indicators.
        Compatible with backtest engine interface.
        
        Returns:
            StrategyOutput(signal, confidence, explanation)
        """
        import pandas as pd
        from trading_bot.strategy.base import StrategyOutput
        
        if len(df) < 200:
            return StrategyOutput(
                signal=0,
                confidence=0.0,
                explanation={'error': 'Insufficient data'}
            )
        
        # Extract closing prices - handle both 'close' and 'Close' column names
        close_col = 'close' if 'close' in df.columns else 'Close'
        if close_col not in df.columns:
            return StrategyOutput(
                signal=0,
                confidence=0.0,
                explanation={'error': f'No closing price column found. Available: {list(df.columns)[:5]}'}
            )
        
        prices = df[close_col].values
        
        # Calculate features and generate signal
        features = self.calculate_features(prices)
        if not features:
            return StrategyOutput(signal=0, confidence=0.0, explanation={'error': 'Feature calculation failed'})
        
        signal, pos_size = self.generate_signal(features)
        
        # Calculate confidence from features
        confidence = min(abs(features.get('momentum_signal', 0.0)), 1.0)
        
        return StrategyOutput(
            signal=signal,
            confidence=confidence,
            explanation={
                'signal': signal,
                'position_size': pos_size,
                'short_trend': features.get('short_trend', 0),
                'long_trend': features.get('long_trend', 0),
                'volatility_ratio': features.get('volatility_ratio', 1.0),
            }
        )

