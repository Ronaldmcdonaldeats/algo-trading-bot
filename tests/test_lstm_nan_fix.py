"""
Tests for SimpleLSTM NaN handling fix
"""

import pytest
import numpy as np
from trading_bot.learn.deep_learning_models import SimpleLSTM, LSTMPrediction


class TestSimpleLSTMNaNHandling:
    """Test SimpleLSTM handles edge cases without NaN"""
    
    @pytest.fixture
    def lstm(self):
        return SimpleLSTM(input_size=10, hidden_size=32)
    
    def test_empty_features_returns_valid_prediction(self, lstm):
        """Test that empty features return valid (non-NaN) prediction"""
        features = {}
        prediction = lstm.forward(features)
        
        assert isinstance(prediction, LSTMPrediction)
        assert not np.isnan(prediction.next_return)
        assert not np.isnan(prediction.confidence)
        assert not np.isnan(prediction.probability_up)
        assert prediction.next_return == 0.0
        assert prediction.confidence == 0.0
        assert prediction.probability_up == 0.5
    
    def test_zero_variance_returns_valid_prediction(self, lstm):
        """Test that zero-variance features return valid prediction"""
        # All features are the same = zero variance
        features = {f'feat_{i}': 1.0 for i in range(10)}
        prediction = lstm.forward(features)
        
        assert isinstance(prediction, LSTMPrediction)
        assert not np.isnan(prediction.next_return)
        assert not np.isnan(prediction.confidence)
        assert not np.isnan(prediction.probability_up)
        
        # Should return reasonable values
        assert -0.05 <= prediction.next_return <= 0.05
        assert 0.0 <= prediction.confidence <= 1.0
        assert 0.0 <= prediction.probability_up <= 1.0
    
    def test_extreme_feature_values(self, lstm):
        """Test that extreme feature values don't cause NaN"""
        features = {
            'feat_0': 1e6,
            'feat_1': -1e6,
            'feat_2': 0.0,
            **{f'feat_{i}': np.random.randn() for i in range(3, 10)}
        }
        
        prediction = lstm.forward(features)
        
        assert isinstance(prediction, LSTMPrediction)
        assert not np.isnan(prediction.next_return)
        assert not np.isnan(prediction.confidence)
        assert not np.isnan(prediction.probability_up)
    
    def test_nan_in_features_is_handled(self, lstm):
        """Test that NaN in input features is handled gracefully"""
        features = {
            'feat_0': np.nan,
            'feat_1': 1.0,
            **{f'feat_{i}': 0.5 for i in range(2, 10)}
        }
        
        # Implementation should replace NaN or skip it
        prediction = lstm.forward(features)
        
        assert isinstance(prediction, LSTMPrediction)
        # Output should not be NaN (implementation dependent)
        assert not np.isnan(prediction.next_return)
        assert not np.isnan(prediction.confidence)
        assert not np.isnan(prediction.probability_up)
    
    def test_inf_values_handled(self, lstm):
        """Test that infinite values are handled"""
        features = {
            'feat_0': np.inf,
            'feat_1': -np.inf,
            **{f'feat_{i}': 1.0 for i in range(2, 10)}
        }
        
        prediction = lstm.forward(features)
        
        assert isinstance(prediction, LSTMPrediction)
        assert not np.isnan(prediction.next_return)
        assert not np.isnan(prediction.confidence)
        assert not np.isnan(prediction.probability_up)
    
    def test_few_features(self, lstm):
        """Test with fewer features than input size"""
        features = {
            'feat_0': 1.0,
            'feat_1': 2.0,
            'feat_2': 3.0
        }
        
        prediction = lstm.forward(features)
        
        assert isinstance(prediction, LSTMPrediction)
        assert not np.isnan(prediction.next_return)
        assert not np.isnan(prediction.confidence)
        assert not np.isnan(prediction.probability_up)
    
    def test_many_features(self, lstm):
        """Test with more features than input size"""
        features = {f'feat_{i}': float(i) for i in range(20)}
        
        prediction = lstm.forward(features)
        
        assert isinstance(prediction, LSTMPrediction)
        assert not np.isnan(prediction.next_return)
        assert not np.isnan(prediction.confidence)
        assert not np.isnan(prediction.probability_up)
    
    def test_prediction_bounds(self, lstm):
        """Test that predictions stay within expected bounds"""
        # Random but valid features
        np.random.seed(42)
        features = {f'feat_{i}': np.random.randn() * 0.1 for i in range(10)}
        
        prediction = lstm.forward(features)
        
        # Next return should be in [-5%, 5%]
        assert -0.05 <= prediction.next_return <= 0.05
        
        # Confidence should be [0, 1]
        assert 0.0 <= prediction.confidence <= 1.0
        
        # Probability should be [0, 1]
        assert 0.0 <= prediction.probability_up <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
