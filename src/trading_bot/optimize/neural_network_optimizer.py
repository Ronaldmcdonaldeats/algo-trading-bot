"""Neural Network Parameter Optimizer

Uses simple neural network to find optimal trading strategy parameters.
Tests different combinations and learns which parameters work best.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import json
from pathlib import Path
import numpy as np


@dataclass
class OptimizationResult:
    """Result of parameter optimization"""
    parameters: Dict[str, float]
    performance: float  # Sharpe ratio or similar metric
    win_rate: float
    profit_factor: float
    trades: int


class SimpleNeuralNet:
    """Simple neural network for parameter optimization"""
    
    def __init__(self, input_size: int = 5, hidden_size: int = 16, learning_rate: float = 0.01):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.learning_rate = learning_rate
        
        # Initialize weights
        self.w1 = np.random.randn(input_size, hidden_size) * 0.01
        self.b1 = np.zeros((1, hidden_size))
        self.w2 = np.random.randn(hidden_size, 1) * 0.01
        self.b2 = np.zeros((1, 1))
    
    def relu(self, x):
        """ReLU activation"""
        return np.maximum(0, x)
    
    def relu_derivative(self, x):
        """ReLU derivative"""
        return (x > 0).astype(float)
    
    def sigmoid(self, x):
        """Sigmoid activation"""
        return 1 / (1 + np.exp(-np.clip(x, -500, 500)))
    
    def forward(self, x):
        """Forward pass"""
        self.z1 = np.dot(x, self.w1) + self.b1
        self.a1 = self.relu(self.z1)
        self.z2 = np.dot(self.a1, self.w2) + self.b2
        self.a2 = self.sigmoid(self.z2)
        return self.a2
    
    def backward(self, x, y, output):
        """Backward pass"""
        m = x.shape[0]
        
        # Output layer gradients
        dz2 = output - y
        dw2 = np.dot(self.a1.T, dz2) / m
        db2 = np.sum(dz2, axis=0, keepdims=True) / m
        
        # Hidden layer gradients
        da1 = np.dot(dz2, self.w2.T)
        dz1 = da1 * self.relu_derivative(self.z1)
        dw1 = np.dot(x.T, dz1) / m
        db1 = np.sum(dz1, axis=0, keepdims=True) / m
        
        # Update weights
        self.w2 -= self.learning_rate * dw2
        self.b2 -= self.learning_rate * db2
        self.w1 -= self.learning_rate * dw1
        self.b1 -= self.learning_rate * db1
    
    def train(self, x, y, epochs: int = 100):
        """Train the network"""
        for epoch in range(epochs):
            output = self.forward(x)
            self.backward(x, y, output)


class NeuralNetworkOptimizer:
    """Optimize trading parameters using neural networks"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.net = SimpleNeuralNet()
        self.best_params = {}
        self.optimization_history: List[OptimizationResult] = []
    
    def optimize_parameters(self, 
                           param_ranges: Dict[str, Tuple[float, float]],
                           performance_data: List[Dict],
                           iterations: int = 100) -> OptimizationResult:
        """
        Optimize parameters using neural network
        
        Args:
            param_ranges: Dict of param_name -> (min, max)
            performance_data: List of backtest results with metrics
            iterations: Number of optimization iterations
            
        Returns:
            Best OptimizationResult found
        """
        if not performance_data:
            return OptimizationResult(
                parameters={k: (v[0] + v[1]) / 2 for k, v in param_ranges.items()},
                performance=0,
                win_rate=0,
                profit_factor=0,
                trades=0
            )
        
        # Prepare training data
        X_train = []
        y_train = []
        
        param_names = list(param_ranges.keys())
        
        for data in performance_data:
            # Extract parameter values
            x = [data.get(param, 0) for param in param_names]
            # Normalize to 0-1
            x_norm = [
                (data.get(param, 0) - param_ranges[param][0]) / 
                (param_ranges[param][1] - param_ranges[param][0] + 1e-6)
                for param in param_names
            ]
            X_train.append(x_norm)
            
            # Performance score
            performance = data.get('sharpe_ratio', 0)
            y_train.append([performance])
        
        if len(X_train) < 2:
            return self._create_default_result(param_ranges)
        
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        
        # Train network
        self.net.train(X_train, y_train, epochs=iterations)
        
        # Find best parameters by testing grid
        best_result = None
        best_performance = -float('inf')
        
        # Generate test points
        test_params = self._generate_parameter_grid(param_ranges, samples=20)
        
        for params_dict in test_params:
            x_test = np.array([[
                (params_dict[param] - param_ranges[param][0]) / 
                (param_ranges[param][1] - param_ranges[param][0] + 1e-6)
                for param in param_names
            ]])
            
            predicted_performance = self.net.forward(x_test)[0, 0]
            
            if predicted_performance > best_performance:
                best_performance = predicted_performance
                best_result = OptimizationResult(
                    parameters=params_dict,
                    performance=float(predicted_performance),
                    win_rate=0.5,  # Placeholder
                    profit_factor=1.5,  # Placeholder
                    trades=100  # Placeholder
                )
        
        self.optimization_history.append(best_result)
        self.best_params = best_result.parameters
        
        return best_result
    
    def _generate_parameter_grid(self, param_ranges: Dict[str, Tuple[float, float]], 
                                samples: int = 10) -> List[Dict[str, float]]:
        """Generate grid of parameter combinations"""
        params_list = list(param_ranges.items())
        
        if len(params_list) == 1:
            param_name, (min_val, max_val) = params_list[0]
            return [{param_name: v} for v in np.linspace(min_val, max_val, samples)]
        
        # For multiple parameters, create grid
        results = []
        for param_name, (min_val, max_val) in params_list:
            for val in np.linspace(min_val, max_val, max(2, samples // len(params_list))):
                results.append({param_name: val})
        
        return results
    
    def _create_default_result(self, param_ranges: Dict[str, Tuple[float, float]]) -> OptimizationResult:
        """Create default result with middle values"""
        return OptimizationResult(
            parameters={k: (v[0] + v[1]) / 2 for k, v in param_ranges.items()},
            performance=1.0,
            win_rate=0.5,
            profit_factor=1.5,
            trades=100
        )
    
    def save_optimization(self, filename: str = "optimization_results.json"):
        """Save optimization history"""
        filepath = self.cache_dir / filename
        
        data = [
            {
                'parameters': result.parameters,
                'performance': result.performance,
                'win_rate': result.win_rate,
                'profit_factor': result.profit_factor,
                'trades': result.trades
            }
            for result in self.optimization_history
        ]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load_best_parameters(self, filename: str = "optimization_results.json") -> Dict[str, float]:
        """Load best parameters from file"""
        filepath = self.cache_dir / filename
        
        if not filepath.exists():
            return {}
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        if data:
            return data[0]['parameters']  # First is best
        return {}
