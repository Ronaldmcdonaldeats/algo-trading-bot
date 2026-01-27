"""
Parameter Utilities: Centralized parameter definitions and operations.

Reduces code duplication across strategy generation, mutation, and crossover.
Single source of truth for parameter bounds and types.
"""

from __future__ import annotations

from typing import Dict, Any, List, Tuple
from dataclasses import dataclass
import random
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParameterBound:
    """Definition of a single parameter with bounds and validation"""
    
    name: str
    min_value: float
    max_value: float
    param_type: str  # 'int', 'float', 'choice'
    default: float = None
    choices: List[float] = None  # For 'choice' type
    
    def validate(self, value: float) -> float:
        """Validate and clamp value to bounds"""
        return max(self.min_value, min(self.max_value, float(value)))
    
    def random_value(self) -> float:
        """Generate random value within bounds"""
        if self.param_type == 'choice' and self.choices:
            return float(random.choice(self.choices))
        elif self.param_type == 'int':
            return float(random.randint(int(self.min_value), int(self.max_value)))
        else:  # float
            return float(random.uniform(self.min_value, self.max_value))


class ParameterSpace:
    """Centralized definition of all strategy parameters (single source of truth)"""
    
    # RSI parameters
    RSI_PERIOD = ParameterBound("rsi_period", 7, 21, "choice", 14, [7, 14, 21])
    RSI_BUY = ParameterBound("rsi_buy", 20, 40, "int", 30)
    RSI_SELL = ParameterBound("rsi_sell", 60, 80, "int", 70)
    
    # MACD parameters
    MACD_FAST = ParameterBound("macd_fast", 8, 14, "choice", 12, [8, 12, 13])
    MACD_SLOW = ParameterBound("macd_slow", 17, 27, "choice", 26, [17, 26, 27])
    MACD_SIGNAL = ParameterBound("macd_signal", 5, 11, "choice", 9, [5, 9, 11])
    
    # ATR parameters
    ATR_PERIOD = ParameterBound("atr_period", 10, 20, "choice", 14, [10, 14, 20])
    ATR_MULTIPLIER = ParameterBound("atr_multiplier", 1.5, 3.0, "float", 2.0)
    
    # Momentum parameters
    MOMENTUM_PERIOD = ParameterBound("momentum_period", 10, 30, "choice", 20, [10, 20, 30])
    
    # Risk parameters
    VOLATILITY_THRESHOLD = ParameterBound("volatility_threshold", 0.01, 0.05, "float", 0.02)
    POSITION_SIZE_PCT = ParameterBound("position_size_pct", 0.02, 0.10, "float", 0.05)
    
    # All parameters as list for iteration
    ALL_PARAMS = [
        RSI_PERIOD, RSI_BUY, RSI_SELL,
        MACD_FAST, MACD_SLOW, MACD_SIGNAL,
        ATR_PERIOD, ATR_MULTIPLIER,
        MOMENTUM_PERIOD,
        VOLATILITY_THRESHOLD, POSITION_SIZE_PCT,
    ]
    
    # Parameter name to bound mapping
    PARAM_MAP: Dict[str, ParameterBound] = {p.name: p for p in ALL_PARAMS}


class ParameterOps:
    """OPTIMIZED: Common operations on parameters (replaces duplicated code)"""
    
    @staticmethod
    def generate_random() -> Dict[str, float]:
        """Generate random parameters within bounds"""
        return {
            p.name: p.random_value()
            for p in ParameterSpace.ALL_PARAMS
        }
    
    @staticmethod
    def mutate(params: Dict[str, float], mutation_rate: float = 0.15) -> Dict[str, float]:
        """
        Mutate parameters with given mutation_rate.
        
        OPTIMIZED: Centralized mutation logic (eliminates duplication from _mutate_parameters)
        - Faster: Uses lookup table instead of string matching
        - More consistent: All params mutated same way
        - More maintainable: One place to change mutation logic
        """
        mutated = params.copy()
        
        for param_name, value in params.items():
            if random.random() < mutation_rate:
                bound = ParameterSpace.PARAM_MAP.get(param_name)
                if bound:
                    if bound.param_type == 'choice':
                        # For choice params, pick a random choice (includes current value)
                        mutated[param_name] = float(random.choice(bound.choices))
                    elif bound.param_type == 'int':
                        # For int params, mutate by ±1 with small % chance of larger jump
                        if random.random() < 0.1:  # 10% chance of bigger jump
                            mutated[param_name] = float(random.randint(int(bound.min_value), int(bound.max_value)))
                        else:
                            change = random.choice([-1, 1])
                            new_val = value + change
                            mutated[param_name] = bound.validate(new_val)
                    else:  # float
                        # For float params, mutate by ±5% of range
                        range_size = bound.max_value - bound.min_value
                        change = random.uniform(-0.05 * range_size, 0.05 * range_size)
                        new_val = value + change
                        mutated[param_name] = bound.validate(new_val)
        
        return mutated
    
    @staticmethod
    def crossover(params1: Dict[str, float], params2: Dict[str, float]) -> Dict[str, float]:
        """
        Crossover: Create new parameters by mixing two parents.
        
        OPTIMIZED: Centralized crossover logic (eliminates duplication)
        """
        child = {}
        for param_name in ParameterSpace.PARAM_MAP.keys():
            # Randomly select from parent 1 or parent 2
            parent = params1 if random.random() < 0.5 else params2
            child[param_name] = parent.get(param_name, ParameterSpace.PARAM_MAP[param_name].default)
        return child
    
    @staticmethod
    def validate_all(params: Dict[str, float]) -> Dict[str, float]:
        """Validate all parameters against bounds (clamp to valid range)"""
        validated = {}
        for param_name, value in params.items():
            bound = ParameterSpace.PARAM_MAP.get(param_name)
            if bound:
                validated[param_name] = bound.validate(value)
        return validated


# Helper function for backward compatibility
def generate_random_parameters() -> Dict[str, float]:
    """Backward-compatible function (can deprecate after refactoring strategy_maker)"""
    return ParameterOps.generate_random()
