"""
Deep Learning Models for Trading
LSTM Neural Networks, Feature Engineering, Online Learning
"""

import numpy as np
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass
import json


@dataclass
class LSTMPrediction:
    """LSTM model prediction"""
    next_return: float  # Predicted next return
    confidence: float   # Confidence score (0-1)
    probability_up: float  # Probability of upward move


class FeatureEngineering:
    """Advanced technical feature extraction"""
    
    @staticmethod
    def extract_features(prices: List[float], window: int = 20) -> Dict[str, float]:
        """
        Extract advanced technical features
        
        Args:
            prices: Price history
            window: Lookback window
            
        Returns:
            Dictionary of engineered features
        """
        if len(prices) < window:
            return {}
        
        recent_prices = prices[-window:]
        returns = np.diff(recent_prices) / recent_prices[:-1]
        
        features = {}
        
        # Momentum features
        features['momentum_5d'] = (recent_prices[-1] - recent_prices[-5]) / recent_prices[-5]
        features['momentum_10d'] = (recent_prices[-1] - recent_prices[-10]) / recent_prices[-10]
        
        # Volatility features
        features['volatility_5d'] = np.std(returns[-5:])
        features['volatility_20d'] = np.std(returns)
        
        # Skewness and Kurtosis
        features['skewness'] = float(np.mean((returns - np.mean(returns))**3)) / (np.std(returns)**3 + 1e-10)
        features['kurtosis'] = float(np.mean((returns - np.mean(returns))**4)) / (np.std(returns)**4 + 1e-10)
        
        # Mean reversion features
        sma_20 = np.mean(recent_prices)
        features['price_to_sma'] = recent_prices[-1] / sma_20
        
        # Volume-like feature (proxy using price action)
        features['avg_change'] = np.mean(np.abs(returns))
        
        # Trend strength
        recent_trend = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
        features['trend_strength'] = recent_trend / np.mean(np.abs(returns))
        
        return features
    
    @staticmethod
    def normalize_features(features: Dict[str, float]) -> Dict[str, float]:
        """Normalize features to [-1, 1] range for neural network"""
        normalized = {}
        
        for key, value in features.items():
            # Clip extreme values
            clipped = max(-3.0, min(3.0, value))
            # Normalize to [-1, 1]
            normalized[key] = clipped / 3.0
        
        return normalized


class SimpleLSTM:
    """Simplified LSTM-inspired model for returns prediction"""
    
    def __init__(self, input_size: int = 10, hidden_size: int = 32):
        """
        Initialize LSTM model
        
        Args:
            input_size: Number of input features
            hidden_size: Hidden layer size
        """
        self.input_size = input_size
        self.hidden_size = hidden_size
        
        # Simple weights (in production, use TensorFlow/PyTorch)
        self.W_input = np.random.randn(input_size, hidden_size) * 0.01
        self.W_hidden = np.random.randn(hidden_size, hidden_size) * 0.01
        self.W_output = np.random.randn(hidden_size, 1) * 0.01
        
        self.hidden_state = np.zeros(hidden_size)
        self.learning_rate = 0.01
    
    def forward(self, features: Dict[str, float]) -> LSTMPrediction:
        """
        Forward pass through LSTM
        
        Args:
            features: Input features dict
            
        Returns:
            LSTMPrediction with next return prediction
        """
        # Convert dict to array
        if not features:
            return LSTMPrediction(next_return=0.0, confidence=0.0, probability_up=0.5)
        
        feature_array = np.array([v for v in features.values()])
        
        # Handle NaN and infinite values by replacing with 0
        feature_array = np.nan_to_num(feature_array, nan=0.0, posinf=3.0, neginf=-3.0)
        
        if len(feature_array) != self.input_size:
            # Pad or trim to input size
            feature_array = feature_array[:self.input_size]
            if len(feature_array) < self.input_size:
                feature_array = np.pad(feature_array, (0, self.input_size - len(feature_array)))
        
        # LSTM-like computation
        input_signal = np.tanh(feature_array @ self.W_input)
        self.hidden_state = np.tanh(
            input_signal + self.hidden_state @ self.W_hidden
        )
        
        # Output
        output = self.hidden_state @ self.W_output
        next_return = float(np.tanh(output[0]) * 0.05)  # Scale to [-5%, +5%]
        
        # Ensure output is not NaN
        if np.isnan(next_return):
            next_return = 0.0
        
        # Confidence based on feature magnitude
        confidence = float(np.mean(np.abs(feature_array)))
        confidence = min(1.0, max(0.0, confidence))  # Clamp to [0, 1]
        
        # Probability of up move
        probability_up = 0.5 + next_return / 0.10
        probability_up = max(0.0, min(1.0, probability_up))
        
        # Ensure probability is not NaN
        if np.isnan(probability_up):
            probability_up = 0.5
        
        return LSTMPrediction(
            next_return=next_return,
            confidence=confidence,
            probability_up=probability_up
        )
    
    def update_weights(self, gradient: np.ndarray, loss: float):
        """
        Simple weight update via gradient descent
        
        Args:
            gradient: Gradient for backprop
            loss: Loss value
        """
        self.W_output -= self.learning_rate * gradient


class ReinforcementLearningAgent:
    """Simple Q-Learning agent for position sizing"""
    
    def __init__(self, num_actions: int = 5):
        """
        Initialize RL agent
        
        Args:
            num_actions: Number of possible actions (position sizes)
                0: No position
                1: 0.5x position
                2: 1.0x position (normal)
                3: 1.5x position
                4: 2.0x position
        """
        self.num_actions = num_actions
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        self.exploration_rate = 0.1
        
        # Q-values: state -> action values
        self.q_values = {}
    
    def get_state(self, market_regime: str, volatility: float, sharpe: float) -> Tuple:
        """
        Discretize continuous state space
        
        Args:
            market_regime: 'bull', 'bear', 'sideways'
            volatility: Current volatility
            sharpe: Current Sharpe ratio
            
        Returns:
            Discrete state tuple
        """
        regime_code = {'bull': 0, 'sideways': 1, 'bear': 2}.get(market_regime, 1)
        vol_code = 0 if volatility < 0.01 else (1 if volatility < 0.015 else 2)
        sharpe_code = 0 if sharpe < 0.5 else (1 if sharpe < 1.0 else 2)
        
        return (regime_code, vol_code, sharpe_code)
    
    def get_action(self, state: Tuple, epsilon: bool = False) -> int:
        """
        Select action using epsilon-greedy policy
        
        Args:
            state: Current state tuple
            epsilon: Use epsilon-greedy exploration
            
        Returns:
            Action index (0-4)
        """
        if epsilon and np.random.random() < self.exploration_rate:
            return np.random.randint(0, self.num_actions)
        
        if state not in self.q_values:
            self.q_values[state] = np.zeros(self.num_actions)
        
        return int(np.argmax(self.q_values[state]))
    
    def update_q_value(
        self,
        state: Tuple,
        action: int,
        reward: float,
        next_state: Tuple
    ):
        """
        Update Q-values via Q-learning
        
        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
        """
        if state not in self.q_values:
            self.q_values[state] = np.zeros(self.num_actions)
        if next_state not in self.q_values:
            self.q_values[next_state] = np.zeros(self.num_actions)
        
        current_q = self.q_values[state][action]
        max_next_q = np.max(self.q_values[next_state])
        
        # Q-learning update
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )
        
        self.q_values[state][action] = new_q
    
    def get_position_multiplier(self, action: int) -> float:
        """Convert action to position size multiplier"""
        multipliers = [0.0, 0.5, 1.0, 1.5, 2.0]
        return multipliers[min(action, len(multipliers) - 1)]


class OnlineLearner:
    """Continuous learning and model updating"""
    
    def __init__(self):
        """Initialize online learner"""
        self.feature_history: List[Dict] = []
        self.return_history: List[float] = []
        self.model_updates = 0
    
    def add_observation(self, features: Dict[str, float], actual_return: float):
        """
        Add new observation for online learning
        
        Args:
            features: Market features
            actual_return: Actual return that occurred
        """
        self.feature_history.append(features)
        self.return_history.append(actual_return)
        
        # Keep only recent history (rolling window)
        max_history = 1000
        if len(self.feature_history) > max_history:
            self.feature_history = self.feature_history[-max_history:]
            self.return_history = self.return_history[-max_history:]
    
    def get_recent_accuracy(self, window: int = 50) -> float:
        """
        Calculate model accuracy on recent predictions
        
        Args:
            window: Recent window size
            
        Returns:
            Accuracy percentage (0-1)
        """
        if len(self.return_history) < window:
            return 0.5
        
        recent_returns = self.return_history[-window:]
        
        # Count correct predictions (sign matches)
        correct = sum(1 for r in recent_returns if r > 0)
        
        return correct / len(recent_returns)
    
    def should_update_model(self, accuracy_threshold: float = 0.45) -> bool:
        """
        Determine if model should be updated
        
        Args:
            accuracy_threshold: Minimum accuracy to keep current model
            
        Returns:
            True if accuracy dropped below threshold
        """
        recent_accuracy = self.get_recent_accuracy(window=50)
        return recent_accuracy < accuracy_threshold
    
    def save_state(self, filepath: str):
        """Save learner state to file"""
        state = {
            'feature_history': self.feature_history[-100:],  # Keep last 100
            'return_history': self.return_history[-100:],
            'model_updates': self.model_updates
        }
        with open(filepath, 'w') as f:
            json.dump(state, f)
    
    def load_state(self, filepath: str):
        """Load learner state from file"""
        try:
            with open(filepath, 'r') as f:
                state = json.load(f)
                self.feature_history = state.get('feature_history', [])
                self.return_history = state.get('return_history', [])
                self.model_updates = state.get('model_updates', 0)
        except FileNotFoundError:
            pass
