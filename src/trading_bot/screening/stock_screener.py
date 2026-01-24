"""
Advanced Stock Screener using ML-based multi-factor analysis.
Identifies trading opportunities automatically using technical + ML scoring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


@dataclass
class StockScore:
    """Score for a single stock"""
    symbol: str
    momentum_score: float  # 0-100, trend strength
    volatility_score: float  # 0-100, opportunity size
    liquidity_score: float  # 0-100, tradability
    technical_score: float  # 0-100, signal strength
    ml_score: float  # 0-100, ML prediction
    combined_score: float  # 0-100, overall
    reason: str  # Why this stock is good
    timestamp: datetime


class StockScreener:
    """Intelligent stock screener using multiple technical and ML factors"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = cache_dir
        self.scaler = StandardScaler()
        self.ml_model = None
        self._load_ml_model()
    
    def _load_ml_model(self):
        """Load or create ML model for scoring"""
        try:
            from sklearn.ensemble import RandomForestRegressor
            # Create simple model (trains with real data over time)
            self.ml_model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
            self.model_trained = False
        except ImportError:
            logger.warning("sklearn not available, ML scoring disabled")
            self.ml_model = None
    
    def score_stocks(self, data: dict[str, pd.DataFrame]) -> list[StockScore]:
        """
        Score all stocks using multi-factor analysis.
        
        Args:
            data: Dict of {symbol: OHLCV dataframe}
        
        Returns:
            List of StockScore objects, sorted by combined score
        """
        scores = []
        
        for symbol, df in data.items():
            if df.empty or len(df) < 20:  # Need minimum data
                continue
            
            try:
                score = self._score_stock(symbol, df)
                if score:
                    scores.append(score)
            except Exception as e:
                logger.debug(f"Error scoring {symbol}: {e}")
                continue
        
        # Sort by combined score (highest first)
        scores.sort(key=lambda x: x.combined_score, reverse=True)
        return scores
    
    def _score_stock(self, symbol: str, df: pd.DataFrame) -> Optional[StockScore]:
        """Score a single stock across all factors"""
        close = df['Close'].values
        volume = df['Volume'].values
        
        if len(close) < 20:
            return None
        
        # Calculate individual scores
        momentum = self._momentum_score(close)
        volatility = self._volatility_score(close)
        liquidity = self._liquidity_score(volume)
        technical = self._technical_score(close)
        ml = self._ml_score(close, volume) if self.ml_model else technical
        
        # Weighted combination (can be tuned)
        combined = (
            momentum * 0.25 +
            volatility * 0.15 +
            liquidity * 0.10 +
            technical * 0.30 +
            ml * 0.20
        )
        
        reason = self._generate_reason(symbol, momentum, volatility, technical, ml)
        
        return StockScore(
            symbol=symbol,
            momentum_score=momentum,
            volatility_score=volatility,
            liquidity_score=liquidity,
            technical_score=technical,
            ml_score=ml,
            combined_score=combined,
            reason=reason,
            timestamp=datetime.now(),
        )
    
    def _momentum_score(self, close: np.ndarray) -> float:
        """Score based on recent momentum (0-100)"""
        # 20-day momentum
        momentum = (close[-1] - close[-20]) / close[-20] * 100
        
        # Score: positive momentum is good, -20 to +20 maps to 0-100
        score = max(0, min(100, (momentum + 20) * 2.5))
        return float(score)
    
    def _volatility_score(self, close: np.ndarray) -> float:
        """Score based on volatility/opportunity (0-100)"""
        # Higher volatility = bigger moves = more opportunity
        returns = np.diff(close) / close[:-1]
        volatility = np.std(returns) * 100  # Convert to percentage
        
        # Score: 5% daily vol is ideal (20), scale accordingly
        score = min(100, (volatility / 0.05) * 20)
        return float(score)
    
    def _liquidity_score(self, volume: np.ndarray) -> float:
        """Score based on liquidity/tradability (0-100)"""
        # Higher volume = easier to trade = better
        avg_vol = np.mean(volume[-20:])
        recent_vol = np.mean(volume[-5:])
        
        # Score: increasing volume is good
        if avg_vol == 0:
            return 0.0
        
        vol_ratio = recent_vol / avg_vol
        score = min(100, vol_ratio * 50)  # Max 100
        return float(score)
    
    def _technical_score(self, close: np.ndarray) -> float:
        """Score based on technical signals (0-100)"""
        # Simple technical scoring
        ma_20 = np.mean(close[-20:])
        ma_50 = np.mean(close[-50:]) if len(close) >= 50 else ma_20
        
        current = close[-1]
        
        # Score components
        above_ma20 = 1 if current > ma_20 else 0
        above_ma50 = 1 if current > ma_50 else 0
        
        # Check RSI-like signal
        recent_high = np.max(close[-14:])
        recent_low = np.min(close[-14:])
        if recent_high == recent_low:
            rsi_signal = 0
        else:
            rsi_level = (current - recent_low) / (recent_high - recent_low)
            # Prefer 40-60 RSI (not overbought/oversold)
            rsi_signal = 1 - abs(rsi_level - 0.5) * 2
        
        # Combine signals (0-100)
        score = (above_ma20 * 30 + above_ma50 * 25 + rsi_signal * 45)
        return float(score)
    
    def _ml_score(self, close: np.ndarray, volume: np.ndarray) -> float:
        """Score using ML model (0-100)"""
        if self.ml_model is None or len(close) < 20:
            return 50.0  # Neutral
        
        try:
            # Extract features
            features = self._extract_features(close, volume)
            
            # Predict (if model is trained)
            if hasattr(self.ml_model, 'n_estimators_'):
                prediction = self.ml_model.predict([features])[0]
                # Scale to 0-100
                score = max(0, min(100, prediction * 100))
                return float(score)
            else:
                return 50.0  # Neutral if not trained
        except Exception as e:
            logger.debug(f"ML scoring error: {e}")
            return 50.0
    
    def _extract_features(self, close: np.ndarray, volume: np.ndarray) -> list:
        """Extract features for ML model"""
        features = []
        
        # Momentum features
        features.append((close[-1] - close[-20]) / close[-20])  # 20d return
        features.append((close[-1] - close[-5]) / close[-5])    # 5d return
        
        # Volatility features
        returns = np.diff(close[-20:]) / close[-20:-1]
        features.append(np.std(returns))  # Volatility
        
        # Volume features
        features.append(volume[-1] / np.mean(volume[-20:]))  # Vol surge
        
        # Technical features
        ma_20 = np.mean(close[-20:])
        features.append(close[-1] / ma_20)  # Price to MA ratio
        
        return features
    
    def _generate_reason(self, symbol: str, momentum: float, volatility: float, 
                        technical: float, ml: float) -> str:
        """Generate human-readable reason for score"""
        reasons = []
        
        if momentum > 70:
            reasons.append("Strong uptrend")
        elif momentum > 50:
            reasons.append("Positive momentum")
        
        if volatility > 70:
            reasons.append("High volatility opportunity")
        elif volatility > 50:
            reasons.append("Good volatility")
        
        if technical > 70:
            reasons.append("Strong technical setup")
        elif technical > 50:
            reasons.append("Decent technical levels")
        
        if ml > 70:
            reasons.append("ML predicts upside")
        
        if not reasons:
            reasons.append("Balanced opportunity")
        
        return " | ".join(reasons)
    
    def train_model(self, historical_data: dict[str, pd.DataFrame], 
                   labels: dict[str, float]):
        """
        Train ML model on historical data and outcomes.
        
        Args:
            historical_data: Dict of {symbol: OHLCV data}
            labels: Dict of {symbol: outcome (0-1 for win rate)}
        """
        if self.ml_model is None:
            return
        
        X = []
        y = []
        
        for symbol, df in historical_data.items():
            if symbol not in labels or df.empty or len(df) < 20:
                continue
            
            close = df['Close'].values
            volume = df['Volume'].values
            
            try:
                features = self._extract_features(close, volume)
                X.append(features)
                y.append(labels[symbol])
            except Exception as e:
                logger.debug(f"Error training on {symbol}: {e}")
                continue
        
        if len(X) >= 5:  # Need minimum samples
            try:
                self.ml_model.fit(X, y)
                self.model_trained = True
                logger.info(f"ML model trained on {len(X)} stocks")
            except Exception as e:
                logger.error(f"Model training error: {e}")
    
    def filter_stocks(self, scores: list[StockScore], min_score: float = 50.0,
                     max_stocks: int = 50) -> list[StockScore]:
        """
        Filter stocks by criteria.
        
        Args:
            scores: List of StockScore objects
            min_score: Minimum combined score (0-100)
            max_stocks: Maximum number to return
        
        Returns:
            Filtered and limited list
        """
        filtered = [s for s in scores if s.combined_score >= min_score]
        return filtered[:max_stocks]
    
    def get_top_stocks(self, data: dict[str, pd.DataFrame], top_n: int = 50) -> list[StockScore]:
        """
        Get top N stocks by score.
        
        Args:
            data: Dict of {symbol: OHLCV data}
            top_n: Number of top stocks to return
        
        Returns:
            List of top StockScore objects
        """
        scores = self.score_stocks(data)
        return scores[:top_n]
