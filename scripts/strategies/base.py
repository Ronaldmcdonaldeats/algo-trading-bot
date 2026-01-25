"""
Strategy base class - all strategies inherit from this
"""

from abc import ABC, abstractmethod
from typing import Dict, Tuple, List
import numpy as np


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(self, name: str, config: Dict = None):
        self.name = name
        self.config = config or {}
        self.entry_threshold = self.config.get('entry_threshold', 0.12)
        self.exit_threshold = self.config.get('exit_threshold', -0.12)
        self.max_position_size = self.config.get('max_position_size', 1.5)
        self.transaction_cost = self.config.get('transaction_cost', 0.001)
        self.lookback_period = self.config.get('lookback_period', 200)
    
    @abstractmethod
    def calculate_features(self, prices: np.ndarray) -> Dict[str, float]:
        """Calculate technical indicators/features from price data"""
        pass
    
    @abstractmethod
    def generate_signal(self, features: Dict[str, float], prev_signal: int = 0) -> Tuple[int, float]:
        """
        Generate trading signal based on features
        
        Returns:
            (signal, position_size)
            signal: 1 (buy), -1 (sell), 0 (neutral)
            position_size: leverage multiplier (0.5 to 2.0)
        """
        pass
    
    def backtest(self, prices: np.ndarray) -> float:
        """Run backtest and return annual return"""
        if len(prices) < self.lookback_period:
            return 0.0
        
        capital = 100000.0
        position = 0.0
        prev_signal = 0
        
        for i in range(self.lookback_period, len(prices)):
            price = prices[i]
            features = self.calculate_features(prices[:i+1])
            signal, pos_size = self.generate_signal(features, prev_signal)
            
            if signal == 1 and position == 0:
                position = (capital / price) * pos_size * (1 - self.transaction_cost)
                capital = 0
                prev_signal = 1
            elif signal == -1 and position > 0:
                capital = position * price * (1 - self.transaction_cost)
                position = 0
                prev_signal = -1
        
        if position > 0:
            capital = position * prices[-1] * (1 - self.transaction_cost)
        
        years = len(prices) / 252
        annual = (capital / 100000.0) ** (1 / years) - 1 if years > 0 else 0
        return annual
    
    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name})"
