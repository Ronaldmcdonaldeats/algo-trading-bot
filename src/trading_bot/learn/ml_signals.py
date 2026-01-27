"""
ML-based signal generation using XGBoost.
Predicts price movements for enhanced trading signals.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, List
from dataclasses import dataclass, field

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    xgb = None

try:
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    StandardScaler = None


@dataclass
class MLSignal:
    """ML prediction result for a symbol"""
    symbol: str
    prediction: float  # 1.0 = strong buy, 0.5 = neutral, 0.0 = strong sell
    confidence: float  # 0.0-1.0
    probability_up: float  # P(price goes up)
    timestamp: datetime = field(default_factory=datetime.now)
    features_used: int = 0
    model_version: str = "1.0"

    def is_buy_signal(self, min_confidence: float = 0.6) -> bool:
        """Check if ML signal recommends buying"""
        return self.prediction > 0.65 and self.confidence >= min_confidence

    def is_sell_signal(self, min_confidence: float = 0.6) -> bool:
        """Check if ML signal recommends selling"""
        return self.prediction < 0.35 and self.confidence >= min_confidence

    def signal_strength(self) -> float:
        """Return signal strength 0-1"""
        if self.prediction >= 0.5:
            return (self.prediction - 0.5) * 2 * self.confidence
        else:
            return (0.5 - self.prediction) * 2 * self.confidence


class MLFeatureEngine:
    """Generate features for ML model from OHLCV data"""

    @staticmethod
    def calculate_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all ML features from OHLCV data
        
        Args:
            df: DataFrame with lowercase ohlcv columns (open, high, low, close, volume)
            
        Returns:
            DataFrame with original OHLC + calculated features
        """
        df = df.copy()
        
        if len(df) < 20:
            return df  # Not enough data
        
        # Price features
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Momentum features
        df['rsi_14'] = MLFeatureEngine._calculate_rsi(df['close'], 14)
        df['rsi_7'] = MLFeatureEngine._calculate_rsi(df['close'], 7)
        df['momentum_10'] = df['close'] - df['close'].shift(10)
        df['momentum_20'] = df['close'] - df['close'].shift(20)
        
        # Trend features
        df['sma_5'] = df['close'].rolling(5).mean()
        df['sma_10'] = df['close'].rolling(10).mean()
        df['sma_20'] = df['close'].rolling(20).mean()
        df['ema_12'] = df['close'].ewm(span=12).mean()
        df['ema_26'] = df['close'].ewm(span=26).mean()
        
        # MACD
        df['macd'] = df['ema_12'] - df['ema_26']
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_diff'] = df['macd'] - df['macd_signal']
        
        # Volatility features
        df['volatility_10'] = df['returns'].rolling(10).std()
        df['volatility_20'] = df['returns'].rolling(20).std()
        df['atr_14'] = MLFeatureEngine._calculate_atr(df, 14)
        
        # Volume features
        if 'volume' in df.columns:
            df['volume_sma_20'] = df['volume'].rolling(20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_sma_20'].replace(0, 1)
            df['volume_change'] = df['volume'].pct_change()
        
        # Price action features
        df['high_low_ratio'] = df['high'] / df['low']
        df['close_range'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-6)
        df['body_size'] = abs(df['close'] - df['open'])
        df['upper_shadow'] = df['high'] - np.maximum(df['open'], df['close'])
        df['lower_shadow'] = np.minimum(df['open'], df['close']) - df['low']
        
        # Volatility regime
        df['volatility_regime'] = (df['volatility_20'] > df['volatility_20'].rolling(50).mean()).astype(int)
        
        # Price position
        df['highest_20'] = df['close'].rolling(20).max()
        df['lowest_20'] = df['close'].rolling(20).min()
        df['position_in_range'] = (df['close'] - df['lowest_20']) / (df['highest_20'] - df['lowest_20'] + 1e-6)
        
        # Multi-timeframe features
        df['returns_std_10'] = df['returns'].rolling(10).std()
        df['returns_skew_20'] = df['returns'].rolling(20).skew()
        
        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        df['bb_std'] = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + (df['bb_std'] * 2)
        df['bb_lower'] = df['bb_middle'] - (df['bb_std'] * 2)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'] + 1e-6)
        
        return df

    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 1e-6)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate ATR"""
        df = df.copy()
        df['tr'] = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        atr = df['tr'].rolling(period).mean()
        return atr


class MLModelTrainer:
    """Train and manage XGBoost model for signal generation"""

    def __init__(self, model_name: str = "price_movement"):
        self.model_name = model_name
        self.model: Optional[xgb.XGBClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: List[str] = []
        self.trained = False
        
        if not XGBOOST_AVAILABLE:
            print("[ML] XGBoost not installed, using fallback signals")
        if not SKLEARN_AVAILABLE:
            print("[ML] scikit-learn not installed, using fallback scaler")

    def prepare_training_data(
        self,
        df: pd.DataFrame,
        lookback: int = 20,
        target_forward: int = 5
    ) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
        """
        Prepare training data with forward-looking target
        
        Args:
            df: DataFrame with calculated features
            lookback: min bars needed before a sample
            target_forward: bars to look ahead for target
            
        Returns:
            X, y, feature_names
        """
        df = df.copy()
        
        # Create target: 1 if price goes up, 0 if down
        df['target'] = (df['close'].shift(-target_forward) > df['close']).astype(int)
        
        # Drop rows without enough data
        df = df.dropna()
        
        # Select feature columns (exclude OHLCV, target, etc)
        exclude_cols = ['open', 'high', 'low', 'close', 'volume', 'target']
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        
        X = df[feature_cols].fillna(0)
        y = df['target']
        
        return X, y, feature_cols

    def train(self, df: pd.DataFrame, test_size: float = 0.2):
        """
        Train XGBoost model
        
        Args:
            df: DataFrame with OHLCV data
            test_size: test set fraction
        """
        if not XGBOOST_AVAILABLE:
            print("[ML] Cannot train: XGBoost not available")
            return
        
        # Calculate features
        df_featured = MLFeatureEngine.calculate_features(df)
        
        # Prepare data
        X, y, feature_names = self.prepare_training_data(df_featured)
        self.feature_names = feature_names
        
        if len(X) < 50:
            print(f"[ML] Not enough training data: {len(X)} samples")
            return
        
        # Split
        split_idx = int(len(X) * (1 - test_size))
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # Scale
        if SKLEARN_AVAILABLE:
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
        else:
            X_train_scaled = X_train.values
            X_test_scaled = X_test.values
        
        # Train model
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )
        
        self.model.fit(
            X_train_scaled, y_train,
            eval_set=[(X_test_scaled, y_test)],
            verbose=False
        )
        
        # Evaluate
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        self.trained = True
        print(f"[ML] Model trained: train_acc={train_score:.3f}, test_acc={test_score:.3f}")

    def predict(self, df: pd.DataFrame) -> MLSignal:
        """
        Generate ML signal for latest bar
        
        Args:
            df: DataFrame with recent OHLCV data (needs at least 20 bars)
            
        Returns:
            MLSignal with prediction and confidence
        """
        symbol = df.index.name or "UNKNOWN"
        
        # Default fallback signal
        fallback = MLSignal(
            symbol=symbol,
            prediction=0.5,
            confidence=0.3,
            probability_up=0.5,
            model_version="fallback"
        )
        
        if len(df) < 20:
            return fallback
        
        # Calculate features
        df_featured = MLFeatureEngine.calculate_features(df)
        latest = df_featured.iloc[-1]
        
        # If no model, use heuristics
        if not self.trained or self.model is None:
            return self._heuristic_signal(symbol, latest)
        
        # Prepare features
        X = latest[self.feature_names].fillna(0).values.reshape(1, -1)
        
        # Scale
        if self.scaler is not None:
            try:
                X = self.scaler.transform(X)
            except Exception:
                pass
        
        # Predict
        try:
            prob_class_0 = self.model.predict_proba(X)[0][0]
            prob_class_1 = 1 - prob_class_0
            
            # Map to 0-1 scale (0=sell, 1=buy)
            prediction = prob_class_1
            
            # Confidence based on how far from 0.5
            confidence = abs(prediction - 0.5) * 2
            
            return MLSignal(
                symbol=symbol,
                prediction=prediction,
                confidence=min(confidence, 1.0),
                probability_up=prob_class_1,
                features_used=len(self.feature_names),
                model_version="xgboost_1.0"
            )
        except Exception as e:
            print(f"[ML] Prediction error: {e}")
            return fallback

    def _heuristic_signal(self, symbol: str, latest: pd.Series) -> MLSignal:
        """
        Fallback heuristic signal when model unavailable
        Combines technical indicators
        """
        # RSI signal
        rsi_signal = 0.5
        if 'rsi_14' in latest.index:
            rsi = latest['rsi_14']
            if rsi < 30:
                rsi_signal = 0.8
            elif rsi > 70:
                rsi_signal = 0.2
            else:
                rsi_signal = rsi / 100
        
        # MACD signal
        macd_signal = 0.5
        if 'macd_diff' in latest.index:
            if latest['macd_diff'] > 0:
                macd_signal = 0.7
            else:
                macd_signal = 0.3
        
        # Trend signal
        trend_signal = 0.5
        if 'close' in latest.index and 'sma_20' in latest.index:
            if latest['close'] > latest['sma_20']:
                trend_signal = 0.65
            else:
                trend_signal = 0.35
        
        # Average
        combined = (rsi_signal + macd_signal + trend_signal) / 3
        confidence = 0.5  # Lower confidence for heuristic
        
        return MLSignal(
            symbol=symbol,
            prediction=combined,
            confidence=confidence,
            probability_up=combined,
            model_version="heuristic_fallback"
        )


class MLSignalManager:
    """Manage ML signals for multiple symbols"""

    def __init__(self):
        self.models: Dict[str, MLModelTrainer] = {}
        self.signals: Dict[str, MLSignal] = {}
        self.last_training: Dict[str, datetime] = {}
        self.training_interval = timedelta(hours=4)  # Retrain every 4 hours

    def train_symbol(self, symbol: str, df: pd.DataFrame) -> bool:
        """
        Train or update model for a symbol
        
        Args:
            symbol: Trading symbol
            df: Historical OHLCV data
            
        Returns:
            True if training successful
        """
        if symbol not in self.models:
            self.models[symbol] = MLModelTrainer(f"model_{symbol}")
        
        # Check if retraining needed
        now = datetime.now()
        last_train = self.last_training.get(symbol, datetime.min)
        
        if (now - last_train) < self.training_interval and symbol in self.last_training:
            return True  # Skip retraining, still valid
        
        try:
            self.models[symbol].train(df)
            self.last_training[symbol] = now
            return True
        except Exception as e:
            print(f"[ML] Training failed for {symbol}: {e}")
            return False

    def predict_signal(self, symbol: str, df: pd.DataFrame) -> MLSignal:
        """
        Get ML signal for a symbol
        
        Args:
            symbol: Trading symbol
            df: Recent OHLCV data
            
        Returns:
            MLSignal prediction
        """
        if symbol not in self.models:
            self.models[symbol] = MLModelTrainer(f"model_{symbol}")
        
        df.index.name = symbol
        signal = self.models[symbol].predict(df)
        self.signals[symbol] = signal
        return signal

    def get_top_signals(self, n: int = 5, threshold: float = 0.6) -> List[Tuple[str, MLSignal]]:
        """
        Get strongest buy signals
        
        Args:
            n: Number of signals to return
            threshold: Minimum confidence threshold
            
        Returns:
            List of (symbol, signal) tuples sorted by strength
        """
        buy_signals = [
            (sym, sig) for sym, sig in self.signals.items()
            if sig.is_buy_signal(threshold)
        ]
        
        # Sort by signal strength
        buy_signals.sort(key=lambda x: x[1].signal_strength(), reverse=True)
        return buy_signals[:n]

    def print_summary(self):
        """Print signal summary for monitoring"""
        if not self.signals:
            return
        
        buy_count = sum(1 for s in self.signals.values() if s.prediction > 0.6)
        sell_count = sum(1 for s in self.signals.values() if s.prediction < 0.4)
        
        print("\n[ML SIGNALS SUMMARY]")
        print(f"  Symbols analyzed: {len(self.signals)}")
        print(f"  Buy signals (p>0.6): {buy_count}")
        print(f"  Sell signals (p<0.4): {sell_count}")
        
        if self.signals:
            avg_conf = np.mean([s.confidence for s in self.signals.values()])
            print(f"  Average confidence: {avg_conf:.3f}")
