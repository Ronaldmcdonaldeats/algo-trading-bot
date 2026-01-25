"""Machine learning strategy enhancement with ensemble models and RL-based position sizing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Tuple, Any
import logging
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class ModelType(Enum):
    """Supported ML model types."""
    LINEAR_REGRESSION = "linear_regression"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    NEURAL_NETWORK = "neural_network"
    SVM = "svm"
    LSTM = "lstm"
    TRANSFORMER = "transformer"


class FeatureType(Enum):
    """Feature types for ML models."""
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    PRICE_ACTION = "price_action"
    CORRELATION = "correlation"
    MACRO = "macro"
    SENTIMENT = "sentiment"
    TECHNICAL = "technical"


@dataclass
class Feature:
    """Single feature for ML model."""
    name: str
    feature_type: FeatureType
    value: float
    importance: float = 0.0  # Feature importance score 0-1
    lag: int = 0  # Bars to look back
    normalized: bool = False
    
    def normalize(self, mean: float = 0.0, std: float = 1.0) -> float:
        """Normalize feature value.
        
        Args:
            mean: Mean for standardization
            std: Std dev for standardization
            
        Returns:
            Normalized value
        """
        if std == 0:
            return 0.0
        normalized = (self.value - mean) / std
        self.normalized = True
        return normalized


@dataclass
class ModelPrediction:
    """ML model prediction."""
    symbol: str
    predicted_return: float  # Expected return %
    confidence: float  # 0-1
    model_name: str
    features_used: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def buy_signal_strength(self) -> float:
        """Buy signal strength (0-1)."""
        if self.predicted_return > 0:
            return min(1.0, self.predicted_return / 5.0 * self.confidence)
        return 0.0
    
    @property
    def sell_signal_strength(self) -> float:
        """Sell signal strength (0-1)."""
        if self.predicted_return < 0:
            return min(1.0, abs(self.predicted_return) / 5.0 * self.confidence)
        return 0.0


@dataclass
class EnsemblePrediction:
    """Ensemble model prediction combining multiple models."""
    symbol: str
    consensus_return: float
    consensus_confidence: float
    predictions: List[ModelPrediction] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)
    disagreement_level: float = 0.0  # 0-1, higher = more disagreement
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_high_confidence(self) -> bool:
        """High confidence signal (agreement + positive confidence)."""
        return self.disagreement_level < 0.3 and self.consensus_confidence > 0.7
    
    @property
    def is_conflicting(self) -> bool:
        """Conflicting signals (high disagreement)."""
        return self.disagreement_level > 0.6


class FeatureEngineer:
    """Generates features for ML models."""
    
    def __init__(self):
        """Initialize feature engineer."""
        self.feature_cache: Dict[str, Dict] = {}
        self.feature_stats: Dict[str, Dict] = {}
    
    def calculate_momentum_features(self, prices: List[float]) -> Dict[str, float]:
        """Calculate momentum-based features.
        
        Args:
            prices: List of prices
            
        Returns:
            Dict of feature -> value
        """
        features = {}
        
        if len(prices) < 20:
            return features
        
        # Rate of change
        roc_5 = (prices[-1] - prices[-5]) / prices[-5] * 100
        roc_10 = (prices[-1] - prices[-10]) / prices[-10] * 100
        roc_20 = (prices[-1] - prices[-20]) / prices[-20] * 100
        
        features['roc_5'] = roc_5
        features['roc_10'] = roc_10
        features['roc_20'] = roc_20
        features['roc_avg'] = (roc_5 + roc_10 + roc_20) / 3
        
        # Momentum acceleration
        features['momentum_accel'] = roc_5 - roc_10
        
        return features
    
    def calculate_volatility_features(self, prices: List[float]) -> Dict[str, float]:
        """Calculate volatility-based features.
        
        Args:
            prices: List of prices
            
        Returns:
            Dict of feature -> value
        """
        features = {}
        
        if len(prices) < 20:
            return features
        
        returns = np.diff(prices) / prices[:-1]
        
        # Volatility measures
        vol_5 = np.std(returns[-5:]) * np.sqrt(252) * 100
        vol_10 = np.std(returns[-10:]) * np.sqrt(252) * 100
        vol_20 = np.std(returns[-20:]) * np.sqrt(252) * 100
        
        features['vol_5'] = vol_5
        features['vol_10'] = vol_10
        features['vol_20'] = vol_20
        features['vol_ratio'] = vol_5 / (vol_20 + 1e-8)
        
        # Volatility of volatility (vol clustering)
        vol_series = np.abs(returns[-20:]) * 100
        features['vol_clustering'] = np.std(vol_series)
        
        return features
    
    def calculate_volume_features(self, volumes: List[int], prices: List[float]) -> Dict[str, float]:
        """Calculate volume-based features.
        
        Args:
            volumes: List of volumes
            prices: List of prices
            
        Returns:
            Dict of feature -> value
        """
        features = {}
        
        if len(volumes) < 10:
            return features
        
        vol_array = np.array(volumes)
        
        # Volume measures
        avg_vol_10 = np.mean(vol_array[-10:])
        avg_vol_20 = np.mean(vol_array[-20:])
        current_vol = vol_array[-1]
        
        features['vol_above_avg'] = (current_vol - avg_vol_20) / avg_vol_20 * 100
        features['vol_trend'] = avg_vol_10 / (avg_vol_20 + 1e-8) - 1
        
        # On-balance volume (simple)
        close_prices = np.array(prices[-10:])
        vol_changes = (close_prices[-1] - close_prices[0]) / close_prices[0]
        features['vol_price_correlation'] = vol_changes
        
        return features
    
    def calculate_technical_features(self, prices: List[float]) -> Dict[str, float]:
        """Calculate technical analysis features.
        
        Args:
            prices: List of prices
            
        Returns:
            Dict of feature -> value
        """
        features = {}
        
        if len(prices) < 20:
            return features
        
        prices_array = np.array(prices)
        
        # Moving averages
        ma_5 = np.mean(prices_array[-5:])
        ma_10 = np.mean(prices_array[-10:])
        ma_20 = np.mean(prices_array[-20:])
        
        features['price_to_ma5'] = (prices_array[-1] - ma_5) / ma_5 * 100
        features['price_to_ma20'] = (prices_array[-1] - ma_20) / ma_20 * 100
        features['ma_slope_5'] = (ma_5 - ma_10) / ma_10 * 100
        features['ma_slope_20'] = (ma_10 - ma_20) / ma_20 * 100
        
        # Support/Resistance
        high = np.max(prices_array[-20:])
        low = np.min(prices_array[-20:])
        price_range = high - low
        
        features['price_to_high'] = (prices_array[-1] - low) / price_range * 100
        features['support_distance'] = (prices_array[-1] - low) / prices_array[-1] * 100
        
        return features
    
    def get_all_features(self, symbol: str, prices: List[float], 
                        volumes: List[int]) -> Dict[str, float]:
        """Get all features for symbol.
        
        Args:
            symbol: Stock symbol
            prices: Price history
            volumes: Volume history
            
        Returns:
            Dict of all features
        """
        features = {}
        
        features.update(self.calculate_momentum_features(prices))
        features.update(self.calculate_volatility_features(prices))
        features.update(self.calculate_volume_features(volumes, prices))
        features.update(self.calculate_technical_features(prices))
        
        # Cache features
        self.feature_cache[symbol] = features
        
        return features


class EnsembleModel:
    """Ensemble of multiple ML models."""
    
    def __init__(self, models: Optional[List[str]] = None):
        """Initialize ensemble.
        
        Args:
            models: List of model names to include
        """
        self.models: Dict[str, Any] = {}
        self.weights: Dict[str, float] = {}
        self.feature_engineer = FeatureEngineer()
        
        if models is None:
            models = [
                'random_forest',
                'gradient_boosting',
                'neural_network',
                'linear_regression'
            ]
        
        # Initialize each model type
        for model_name in models:
            self.models[model_name] = self._create_model(model_name)
            self.weights[model_name] = 1.0 / len(models)  # Equal weighting
    
    def _create_model(self, model_type: str) -> Any:
        """Create ML model instance.
        
        Args:
            model_type: Type of model
            
        Returns:
            Model instance
        """
        # In production, would use actual ML libraries (sklearn, tf, etc.)
        return {
            'type': model_type,
            'trained': False,
            'predictions': {},
        }
    
    def train(self, features: List[Dict[str, float]], 
             targets: List[float]) -> None:
        """Train ensemble models.
        
        Args:
            features: List of feature dicts
            targets: List of target values (returns)
        """
        logger.info(f"Training ensemble with {len(features)} samples")
        
        # In production, would train actual models
        for model_name in self.models:
            self.models[model_name]['trained'] = True
            self.models[model_name]['mean_target'] = np.mean(targets)
            self.models[model_name]['std_target'] = np.std(targets)
    
    def predict_symbol(self, symbol: str, prices: List[float],
                      volumes: List[int]) -> EnsemblePrediction:
        """Generate ensemble prediction for symbol.
        
        Args:
            symbol: Stock symbol
            prices: Price history
            volumes: Volume history
            
        Returns:
            EnsemblePrediction
        """
        # Get features
        features = self.feature_engineer.get_all_features(symbol, prices, volumes)
        
        # Get predictions from each model
        predictions = []
        pred_values = []
        
        for model_name, model in self.models.items():
            weight = self.weights[model_name]
            
            if model['trained']:
                # Simulate prediction (in production, actual ML prediction)
                predicted_return = model.get('mean_target', 0.0) * np.random.uniform(0.8, 1.2)
                confidence = 0.5 + np.random.uniform(-0.2, 0.2)
            else:
                predicted_return = 0.0
                confidence = 0.0
            
            pred = ModelPrediction(
                symbol=symbol,
                predicted_return=predicted_return,
                confidence=max(0, min(1, confidence)),
                model_name=model_name,
                features_used=len(features),
            )
            
            predictions.append(pred)
            pred_values.append(predicted_return * weight)
        
        # Calculate ensemble prediction
        consensus_return = sum(pred_values)
        consensus_confidence = np.mean([p.confidence for p in predictions])
        
        # Calculate disagreement level
        returns = np.array([p.predicted_return for p in predictions])
        disagreement = np.std(returns) / (np.max(np.abs(returns)) + 1e-8) if returns.any() else 0
        
        return EnsemblePrediction(
            symbol=symbol,
            consensus_return=consensus_return,
            consensus_confidence=consensus_confidence,
            predictions=predictions,
            weights=self.weights.copy(),
            disagreement_level=min(1.0, disagreement),
        )
    
    def update_weights(self, performance: Dict[str, float]) -> None:
        """Update model weights based on performance.
        
        Args:
            performance: Dict of model_name -> performance_score
        """
        total_perf = sum(performance.values())
        
        if total_perf > 0:
            for model_name, perf in performance.items():
                self.weights[model_name] = perf / total_perf
        
        logger.info(f"Updated ensemble weights: {self.weights}")


class RLPositionSizer:
    """Reinforcement learning-based position sizing."""
    
    def __init__(self, initial_epsilon: float = 0.1):
        """Initialize RL position sizer.
        
        Args:
            initial_epsilon: Initial exploration rate
        """
        self.epsilon = initial_epsilon
        self.min_epsilon = 0.01
        self.epsilon_decay = 0.995
        self.q_table: Dict[str, Dict[str, float]] = {}
    
    def get_state(self, prediction: EnsemblePrediction) -> str:
        """Convert prediction to state.
        
        Args:
            prediction: Ensemble prediction
            
        Returns:
            State string
        """
        return_level = 'high' if prediction.consensus_return > 2 else 'medium' if prediction.consensus_return > 0.5 else 'low'
        conf_level = 'high' if prediction.consensus_confidence > 0.7 else 'medium' if prediction.consensus_confidence > 0.5 else 'low'
        agree_level = 'high' if prediction.disagreement_level < 0.3 else 'medium' if prediction.disagreement_level < 0.6 else 'low'
        
        return f"{return_level}_{conf_level}_{agree_level}"
    
    def get_position_size(self, prediction: EnsemblePrediction,
                         portfolio_value: float,
                         max_position_pct: float = 5.0) -> float:
        """Get position size using RL.
        
        Args:
            prediction: Ensemble prediction
            portfolio_value: Total portfolio value
            max_position_pct: Max position as % of portfolio
            
        Returns:
            Position size as % of portfolio
        """
        state = self.get_state(prediction)
        
        # Initialize Q-table for state if needed
        if state not in self.q_table:
            self.q_table[state] = {
                'small': 0.0,      # 1% position
                'medium': 0.0,     # 3% position
                'large': 0.0,      # 5% position
            }
        
        # Epsilon-greedy selection
        if np.random.random() < self.epsilon:
            # Explore: random action
            action = np.random.choice(['small', 'medium', 'large'])
        else:
            # Exploit: best known action
            action = max(self.q_table[state], key=self.q_table[state].get)
        
        # Map action to position size
        action_to_size = {
            'small': 1.0,
            'medium': 3.0,
            'large': 5.0,
        }
        
        position_pct = action_to_size[action]
        
        # Adjust based on prediction confidence
        position_pct *= prediction.consensus_confidence
        
        # Respect max position limit
        position_pct = min(position_pct, max_position_pct)
        
        return position_pct
    
    def update_q_values(self, state: str, action: str, reward: float) -> None:
        """Update Q-table values.
        
        Args:
            state: Current state
            action: Action taken
            reward: Reward received
        """
        if state in self.q_table and action in self.q_table[state]:
            learning_rate = 0.1
            self.q_table[state][action] += learning_rate * reward
    
    def decay_epsilon(self) -> None:
        """Decay exploration rate."""
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)


class MLStrategyEnhancer:
    """Main ML strategy enhancement class."""
    
    def __init__(self):
        """Initialize ML enhancer."""
        self.ensemble = EnsembleModel()
        self.position_sizer = RLPositionSizer()
        self.feature_engineer = FeatureEngineer()
        self.prediction_history: List[EnsemblePrediction] = []
    
    def train_models(self, training_data: Dict[str, Dict[str, Any]]) -> None:
        """Train ensemble models.
        
        Args:
            training_data: Training data dict
        """
        # Extract features and targets
        all_features = []
        all_targets = []
        
        for symbol, data in training_data.items():
            features = self.feature_engineer.get_all_features(
                symbol, data['prices'], data['volumes']
            )
            all_features.append(features)
            all_targets.append(data.get('return', 0.0))
        
        self.ensemble.train(all_features, all_targets)
        logger.info(f"Trained ensemble on {len(training_data)} symbols")
    
    def get_signals(self, symbols: List[str], price_data: Dict[str, List[float]],
                   volume_data: Dict[str, List[int]],
                   portfolio_value: float) -> Dict[str, Dict[str, Any]]:
        """Get trading signals for symbols.
        
        Args:
            symbols: List of symbols
            price_data: Dict of symbol -> prices
            volume_data: Dict of symbol -> volumes
            portfolio_value: Current portfolio value
            
        Returns:
            Dict of symbol -> signal
        """
        signals = {}
        
        for symbol in symbols:
            if symbol not in price_data or len(price_data[symbol]) < 20:
                continue
            
            # Get ensemble prediction
            prediction = self.ensemble.predict_symbol(
                symbol,
                price_data[symbol],
                volume_data.get(symbol, [0] * len(price_data[symbol]))
            )
            
            self.prediction_history.append(prediction)
            
            # Get position size from RL
            position_pct = self.position_sizer.get_position_size(
                prediction, portfolio_value
            )
            
            # Generate signal
            if prediction.is_high_confidence and prediction.consensus_return > 0.5:
                action = 'BUY'
            elif prediction.is_high_confidence and prediction.consensus_return < -0.5:
                action = 'SELL'
            elif prediction.is_conflicting:
                action = 'HOLD'
            else:
                action = 'HOLD'
            
            signals[symbol] = {
                'action': action,
                'position_pct': position_pct,
                'confidence': prediction.consensus_confidence,
                'expected_return': prediction.consensus_return,
                'disagreement': prediction.disagreement_level,
            }
        
        return signals
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary.
        
        Returns:
            Performance summary dict
        """
        if not self.prediction_history:
            return {}
        
        predictions = self.prediction_history[-100:]  # Last 100 predictions
        buy_signals = len([p for p in predictions if p.consensus_return > 0])
        sell_signals = len([p for p in predictions if p.consensus_return < 0])
        
        avg_confidence = np.mean([p.consensus_confidence for p in predictions])
        avg_disagreement = np.mean([p.disagreement_level for p in predictions])
        
        return {
            'total_predictions': len(predictions),
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'neutral_signals': len(predictions) - buy_signals - sell_signals,
            'avg_confidence': avg_confidence,
            'avg_disagreement': avg_disagreement,
            'epsilon': self.position_sizer.epsilon,
        }
