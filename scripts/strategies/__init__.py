"""Strategy module - pluggable trading strategies"""

from .base import BaseStrategy
from .factory import StrategyFactory
from .implementations import (
    UltraEnsembleStrategy,
    TrendFollowingStrategy,
    MeanReversionStrategy,
    RSIStrategy,
    MomentumStrategy,
    VolatilityStrategy,
    HybridStrategy
)

__all__ = [
    'BaseStrategy',
    'StrategyFactory',
    'UltraEnsembleStrategy',
    'TrendFollowingStrategy',
    'MeanReversionStrategy',
    'RSIStrategy',
    'MomentumStrategy',
    'VolatilityStrategy',
    'HybridStrategy',
]
