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
