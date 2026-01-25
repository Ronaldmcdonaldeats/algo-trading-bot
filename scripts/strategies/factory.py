"""Strategy factory - load strategies dynamically by name"""

from typing import Dict, Type, Optional
from .base import BaseStrategy
from .implementations import (
    UltraEnsembleStrategy,
    TrendFollowingStrategy,
    MeanReversionStrategy,
    RSIStrategy,
    MomentumStrategy,
    VolatilityStrategy,
    HybridStrategy
)


class StrategyFactory:
    """Factory for creating strategy instances"""
    
    _STRATEGIES: Dict[str, Type[BaseStrategy]] = {
        'ultra_ensemble': UltraEnsembleStrategy,
        'trend_following': TrendFollowingStrategy,
        'mean_reversion': MeanReversionStrategy,
        'rsi': RSIStrategy,
        'momentum': MomentumStrategy,
        'volatility': VolatilityStrategy,
        'hybrid': HybridStrategy,
    }
    
    @classmethod
    def create(cls, strategy_name: str, config: Dict = None) -> Optional[BaseStrategy]:
        """
        Create a strategy instance by name
        
        Args:
            strategy_name: Name of strategy (key in _STRATEGIES)
            config: Configuration dict for the strategy
        
        Returns:
            Strategy instance or None if not found
        """
        strategy_class = cls._STRATEGIES.get(strategy_name.lower())
        if strategy_class is None:
            return None
        return strategy_class(name=strategy_name, config=config or {})
    
    @classmethod
    def list_strategies(cls) -> list:
        """Return list of available strategy names"""
        return sorted(list(cls._STRATEGIES.keys()))
    
    @classmethod
    def register(cls, name: str, strategy_class: Type[BaseStrategy]):
        """Register a new strategy"""
        cls._STRATEGIES[name.lower()] = strategy_class
    
    @classmethod
    def get_strategy_info(cls, strategy_name: str) -> Dict:
        """Get info about a strategy"""
        strategy = cls.create(strategy_name)
        if strategy is None:
            return None
        return {
            'name': strategy_name,
            'class': strategy.__class__.__name__,
            'description': strategy.__class__.__doc__ or 'No description'
        }
    
    @classmethod
    def list_all_info(cls) -> Dict:
        """Get info about all strategies"""
        return {
            name: cls.get_strategy_info(name)
            for name in cls.list_strategies()
        }
