"""
Neural Network-based Parameter Optimizer.
Uses ML to find optimal strategy parameters automatically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


@dataclass
class ParameterSet:
    """A set of strategy parameters with performance metrics"""
    params: dict[str, float]
    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    profit_factor: float
    total_return: float
    num_trades: int
    timestamp: datetime


class NeuralNetworkOptimizer:
    """ML-based parameter optimizer using neural networks"""
    
    def __init__(self, param_ranges: dict[str, tuple[float, float]]):
        """
        Initialize optimizer.
        
        Args:
            param_ranges: Dict of {param_name: (min, max)}
                Example: {"rsi_threshold": (20, 80), "ma_period": (5, 50)}
        """
        self.param_ranges = param_ranges
        self.model = MLPRegressor(
            hidden_layer_sizes=(128, 64, 32),
            activation='relu',
            solver='adam',
            max_iter=1000,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1,
        )
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        
        self.training_data: list[ParameterSet] = []
        self.is_trained = False
        self.best_params: Optional[dict] = None
        self.best_score: float = 0.0
    
    def add_result(self, params: dict[str, float], sharpe: float, win_rate: float,
                  max_dd: float, pf: float, ret: float, num_trades: int):
        """Add training data from a backtesting run"""
        result = ParameterSet(
            params=params,
            sharpe_ratio=sharpe,
            win_rate=win_rate,
            max_drawdown=max_dd,
            profit_factor=pf,
            total_return=ret,
            num_trades=num_trades,
            timestamp=datetime.now(),
        )
        self.training_data.append(result)
        
        # Track best
        score = self._calculate_fitness(result)
        if score > self.best_score:
            self.best_score = score
            self.best_params = params.copy()
    
    def train(self):
        """Train the neural network on collected results"""
        if len(self.training_data) < 10:
            logger.warning(f"Need at least 10 samples, got {len(self.training_data)}")
            return False
        
        try:
            # Prepare training data
            X = []
            y = []
            
            for result in self.training_data:
                # Normalize parameters to 0-1
                x_sample = self._params_to_features(result.params)
                X.append(x_sample)
                
                # Target: fitness score
                fitness = self._calculate_fitness(result)
                y.append(fitness)
            
            X = np.array(X)
            y = np.array(y).reshape(-1, 1)
            
            # Scale features
            X_scaled = self.scaler_X.fit_transform(X)
            y_scaled = self.scaler_y.fit_transform(y)
            
            # Train
            self.model.fit(X_scaled, y_scaled.ravel())
            self.is_trained = True
            
            logger.info(f"NN optimizer trained on {len(X)} samples, best score: {self.best_score:.3f}")
            return True
        
        except Exception as e:
            logger.error(f"Training error: {e}")
            return False
    
    def optimize(self, num_candidates: int = 100) -> list[dict[str, float]]:
        """
        Generate optimized parameter candidates using the trained network.
        
        Args:
            num_candidates: Number of parameter sets to generate
        
        Returns:
            List of parameter dicts, sorted by predicted fitness
        """
        if not self.is_trained:
            logger.warning("Model not trained, returning random candidates")
            return self._random_candidates(num_candidates)
        
        candidates = []
        scores = []
        
        # Generate random candidates
        for _ in range(num_candidates * 2):  # Generate more, then filter
            params = self._random_params()
            x_sample = self._params_to_features(params)
            x_scaled = self.scaler_X.transform([x_sample])[0]
            
            # Predict fitness
            fitness = self.model.predict([x_scaled])[0]
            fitness_unscaled = self.scaler_y.inverse_transform([[fitness]])[0][0]
            
            candidates.append(params)
            scores.append(float(fitness_unscaled))
        
        # Sort by predicted fitness and return top N
        sorted_idx = np.argsort(scores)[::-1]
        top_candidates = [candidates[i] for i in sorted_idx[:num_candidates]]
        
        return top_candidates
    
    def predict_fitness(self, params: dict[str, float]) -> float:
        """Predict fitness score for parameter set"""
        if not self.is_trained:
            return 0.5
        
        try:
            x_sample = self._params_to_features(params)
            x_scaled = self.scaler_X.transform([x_sample])[0]
            fitness = self.model.predict([x_scaled])[0]
            return float(self.scaler_y.inverse_transform([[fitness]])[0][0])
        except Exception as e:
            logger.debug(f"Prediction error: {e}")
            return 0.5
    
    def _params_to_features(self, params: dict[str, float]) -> list[float]:
        """Convert parameters to normalized features (0-1)"""
        features = []
        for param_name in sorted(self.param_ranges.keys()):
            if param_name in params:
                min_val, max_val = self.param_ranges[param_name]
                # Normalize to 0-1
                normalized = (params[param_name] - min_val) / (max_val - min_val)
                features.append(max(0, min(1, normalized)))
            else:
                features.append(0.5)  # Default to middle
        return features
    
    def _features_to_params(self, features: list[float]) -> dict[str, float]:
        """Convert normalized features back to parameters"""
        params = {}
        for i, param_name in enumerate(sorted(self.param_ranges.keys())):
            min_val, max_val = self.param_ranges[param_name]
            # Denormalize
            value = min_val + features[i] * (max_val - min_val)
            params[param_name] = float(value)
        return params
    
    def _random_params(self) -> dict[str, float]:
        """Generate random parameters within ranges"""
        params = {}
        for param_name, (min_val, max_val) in self.param_ranges.items():
            params[param_name] = np.random.uniform(min_val, max_val)
        return params
    
    def _random_candidates(self, num: int) -> list[dict[str, float]]:
        """Generate random candidates"""
        return [self._random_params() for _ in range(num)]
    
    def _calculate_fitness(self, result: ParameterSet) -> float:
        """Calculate overall fitness score (0-1)"""
        # Weighted combination of metrics
        # Higher Sharpe = better
        # Higher win rate = better
        # Lower max drawdown = better
        # Higher profit factor = better
        # More trades = better (more data)
        
        sharpe_score = max(0, min(1, (result.sharpe_ratio + 2) / 6))  # -2 to 4 maps to 0-1
        win_rate_score = result.win_rate  # Already 0-1
        dd_score = max(0, 1 - result.max_drawdown)  # Invert: lower is better
        pf_score = min(1, result.profit_factor / 3)  # 0-3 maps to 0-1
        trades_score = min(1, result.num_trades / 100)  # More trades is better
        
        # Weighted combination
        fitness = (
            sharpe_score * 0.3 +
            win_rate_score * 0.25 +
            dd_score * 0.2 +
            pf_score * 0.15 +
            trades_score * 0.1
        )
        
        return float(fitness)
    
    def get_best_params(self) -> Optional[dict[str, float]]:
        """Get best parameters found so far"""
        return self.best_params.copy() if self.best_params else None
    
    def get_top_results(self, top_n: int = 10) -> list[ParameterSet]:
        """Get top N results by fitness"""
        sorted_results = sorted(
            self.training_data,
            key=lambda r: self._calculate_fitness(r),
            reverse=True
        )
        return sorted_results[:top_n]
    
    def save_history(self, filepath: str):
        """Save optimization history to file"""
        import json
        
        history = {
            "timestamp": datetime.now().isoformat(),
            "num_results": len(self.training_data),
            "best_params": self.best_params,
            "best_score": self.best_score,
            "results": [
                {
                    "params": r.params,
                    "sharpe": r.sharpe_ratio,
                    "win_rate": r.win_rate,
                    "max_dd": r.max_drawdown,
                    "pf": r.profit_factor,
                    "return": r.total_return,
                    "trades": r.num_trades,
                }
                for r in self.training_data
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(history, f, indent=2, default=str)
        
        logger.info(f"Saved optimization history to {filepath}")
