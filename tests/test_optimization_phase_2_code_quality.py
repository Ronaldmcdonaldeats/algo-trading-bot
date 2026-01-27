"""
Phase 2 Code Quality Optimization Tests (4 tests)

Coverage:
- Centralized parameter definitions
- Parameter bounds validation
- Random parameter generation
- Parameter mutation and crossover
"""

import pytest
from unittest.mock import Mock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trading_bot.learn.parameter_utils import ParameterBound, ParameterSpace, ParameterOps


class TestParameterBound:
    """Test parameter bound definition and validation"""
    
    def test_parameter_bound_creation(self):
        """Test creating parameter bounds"""
        bound = ParameterBound(
            name="rsi_period",
            min_value=7,
            max_value=21,
            param_type="int",
            default=14,
            choices=None
        )
        
        assert bound.name == "rsi_period"
        assert bound.min_value == 7
        assert bound.max_value == 21
        assert bound.default == 14
    
    def test_parameter_bound_with_choices(self):
        """Test parameter bounds with discrete choices"""
        bound = ParameterBound(
            name="signal_type",
            min_value=None,
            max_value=None,
            param_type="choice",
            default="RSI",
            choices=["RSI", "MACD", "BB"]
        )
        
        assert bound.choices == ["RSI", "MACD", "BB"]
        assert bound.default == "RSI"


class TestParameterSpace:
    """Test 1: Centralized parameter space definition"""
    
    def test_parameter_space_contains_all_parameters(self):
        """Verify ParameterSpace has all required strategy parameters"""
        # Check RSI parameters
        assert hasattr(ParameterSpace, 'RSI_PERIOD')
        assert hasattr(ParameterSpace, 'RSI_OVERBOUGHT')
        assert hasattr(ParameterSpace, 'RSI_OVERSOLD')
        
        # Check MACD parameters
        assert hasattr(ParameterSpace, 'MACD_FAST')
        assert hasattr(ParameterSpace, 'MACD_SLOW')
        assert hasattr(ParameterSpace, 'MACD_SIGNAL')
        
        # Check ATR parameters
        assert hasattr(ParameterSpace, 'ATR_PERIOD')
        
        # Check risk parameters
        assert hasattr(ParameterSpace, 'MAX_LOSS_PERCENT')
        assert hasattr(ParameterSpace, 'POSITION_SIZE')
    
    def test_parameter_space_bounds_are_valid(self):
        """Verify all parameter bounds are properly defined"""
        for attr_name in dir(ParameterSpace):
            if attr_name.isupper():
                param = getattr(ParameterSpace, attr_name)
                if isinstance(param, ParameterBound):
                    # Check bounds are logical
                    if param.param_type == "int" or param.param_type == "float":
                        assert param.min_value < param.max_value
                        assert param.default is not None
    
    def test_parameter_space_type_consistency(self):
        """Verify parameter types match their definitions"""
        rsi_period = ParameterSpace.RSI_PERIOD
        assert rsi_period.param_type == "int"
        
        max_loss = ParameterSpace.MAX_LOSS_PERCENT
        assert max_loss.param_type == "float"


class TestParameterOps:
    """Test 2: Unified parameter operations"""
    
    def test_generate_random_parameters(self):
        """Test random parameter generation"""
        params = ParameterOps.generate_random()
        
        # Verify all expected parameters present
        assert 'rsi_period' in params
        assert 'macd_fast' in params
        assert 'atr_period' in params
        
        # Verify values are within bounds
        rsi_bound = ParameterSpace.RSI_PERIOD
        assert rsi_bound.min_value <= params['rsi_period'] <= rsi_bound.max_value
    
    def test_mutate_parameters(self):
        """Test parameter mutation"""
        original_params = {
            'rsi_period': 14,
            'macd_fast': 12,
            'atr_period': 14,
            'max_loss_percent': 0.02,
        }
        
        # Mutate with 50% mutation rate
        mutated = ParameterOps.mutate(original_params, mutation_rate=0.5)
        
        # Verify result is dict
        assert isinstance(mutated, dict)
        
        # Verify keys preserved
        assert set(mutated.keys()) == set(original_params.keys())
        
        # Verify values are within bounds
        rsi_bound = ParameterSpace.RSI_PERIOD
        assert rsi_bound.min_value <= mutated['rsi_period'] <= rsi_bound.max_value
    
    def test_crossover_parameters(self):
        """Test parameter crossover (recombination)"""
        parent1 = {
            'rsi_period': 14,
            'macd_fast': 12,
            'atr_period': 14,
            'max_loss_percent': 0.02,
        }
        
        parent2 = {
            'rsi_period': 18,
            'macd_fast': 10,
            'atr_period': 20,
            'max_loss_percent': 0.03,
        }
        
        # Crossover
        child = ParameterOps.crossover(parent1, parent2)
        
        # Verify result is dict
        assert isinstance(child, dict)
        
        # Verify keys preserved
        assert set(child.keys()) == set(parent1.keys())
        
        # Verify child has values from either parent
        assert child['rsi_period'] in [parent1['rsi_period'], parent2['rsi_period']]
        
        # Verify values are within bounds
        rsi_bound = ParameterSpace.RSI_PERIOD
        assert rsi_bound.min_value <= child['rsi_period'] <= rsi_bound.max_value


class TestParameterValidation:
    """Test 3: Parameter validation and clamping"""
    
    def test_validate_all_clamps_out_of_bounds(self):
        """Test that validate_all clamps out-of-bounds values"""
        invalid_params = {
            'rsi_period': 100,  # Out of bounds (max 21)
            'macd_fast': 1,     # Out of bounds (min 5)
            'atr_period': 14,   # In bounds
        }
        
        validated = ParameterOps.validate_all(invalid_params)
        
        # Verify clamping occurred
        rsi_bound = ParameterSpace.RSI_PERIOD
        assert validated['rsi_period'] <= rsi_bound.max_value
        
        macd_bound = ParameterSpace.MACD_FAST
        assert validated['macd_fast'] >= macd_bound.min_value
    
    def test_validate_all_preserves_valid_values(self):
        """Test that validate_all preserves valid values"""
        valid_params = {
            'rsi_period': 14,
            'macd_fast': 12,
            'atr_period': 14,
        }
        
        validated = ParameterOps.validate_all(valid_params)
        
        assert validated['rsi_period'] == 14
        assert validated['macd_fast'] == 12
        assert validated['atr_period'] == 14


class TestParameterConsistency:
    """Test 4: Cross-method consistency"""
    
    def test_generated_params_are_valid(self):
        """Test that generated parameters pass validation"""
        generated = ParameterOps.generate_random()
        validated = ParameterOps.validate_all(generated)
        
        # Should be identical since generated should already be valid
        assert generated == validated
    
    def test_mutated_params_are_valid(self):
        """Test that mutated parameters pass validation"""
        original = ParameterOps.generate_random()
        mutated = ParameterOps.mutate(original, mutation_rate=0.8)
        validated = ParameterOps.validate_all(mutated)
        
        # Mutated should already be valid
        assert mutated == validated
    
    def test_crossover_params_are_valid(self):
        """Test that crossover parameters pass validation"""
        parent1 = ParameterOps.generate_random()
        parent2 = ParameterOps.generate_random()
        child = ParameterOps.crossover(parent1, parent2)
        validated = ParameterOps.validate_all(child)
        
        # Crossover should already be valid
        assert child == validated


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
