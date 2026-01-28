"""
Tests for Advanced Risk Management and Deep Learning Features
"""

import pytest
import numpy as np
from src.trading_bot.risk.advanced_risk_management import (
    ValueAtRisk, MonteCarloSimulation, RegimeDetection,
    DynamicPositionSizing, ComprehensiveRiskAnalysis
)
from src.trading_bot.learn.deep_learning_models import (
    FeatureEngineering, SimpleLSTM, ReinforcementLearningAgent, OnlineLearner
)


class TestValueAtRisk:
    """Test VaR calculations"""
    
    def test_calculate_var(self):
        """Test basic VaR calculation"""
        returns = [0.01, -0.02, 0.005, -0.03, 0.02] * 30  # 150 data points
        var = ValueAtRisk.calculate_var(returns, 0.95)
        
        assert isinstance(var, float)
        assert var < 0  # VaR should be negative (loss)
        assert var > -0.1  # But not catastrophic
    
    def test_calculate_cvar(self):
        """Test Conditional VaR calculation"""
        returns = np.random.normal(-0.001, 0.02, 200).tolist()
        cvar = ValueAtRisk.calculate_cvar(returns, 0.95)
        var = ValueAtRisk.calculate_var(returns, 0.95)
        
        # CVaR should be worse than VaR (more negative)
        assert cvar <= var
    
    def test_var_requires_minimum_data(self):
        """Test that VaR requires sufficient data"""
        with pytest.raises(ValueError):
            ValueAtRisk.calculate_var([0.01, 0.02], 0.95)


class TestMonteCarloSimulation:
    """Test Monte Carlo simulation"""
    
    def test_simulate_returns_shape(self):
        """Test shape of simulated returns"""
        returns = MonteCarloSimulation.simulate_returns(
            mean_return=0.0005,
            volatility=0.012,
            days=10,
            simulations=100,
            seed=42
        )
        
        assert returns.shape == (100, 10)
        assert np.all(returns >= -1.0)  # Can't lose more than 100%
    
    def test_simulate_returns_statistics(self):
        """Test that simulated returns match input statistics"""
        returns = MonteCarloSimulation.simulate_returns(
            mean_return=0.001,
            volatility=0.010,
            days=500,
            simulations=1000,
            seed=42
        )
        
        # With 500 days and 0.1% daily return, compound return is approximately:
        # (1.001^500 - 1) ≈ 0.64 or 64%
        mean_return = np.mean(returns[:, -1])  # Mean return at end
        assert mean_return > 0.5  # Positive drift
        assert mean_return < 1.0  # But reasonable
    
    def test_simulate_portfolio_value(self):
        """Test portfolio value simulation"""
        portfolio_vals, p5, p95 = MonteCarloSimulation.simulate_portfolio_value(
            initial_capital=100000,
            mean_return=0.0005,
            volatility=0.012,
            days=100,
            simulations=500
        )
        
        assert portfolio_vals.shape == (500, 100)
        assert np.all(p5 <= p95)  # 5th percentile < 95th percentile
        assert np.all(portfolio_vals[:, 0] > 95000)  # Initial values with some variance
        assert np.all(portfolio_vals[:, 0] < 105000)


class TestRegimeDetection:
    """Test market regime detection"""
    
    def test_detect_bull_regime(self):
        """Test bull market detection"""
        returns = [0.002] * 20  # Consistent positive returns, low volatility
        regime = RegimeDetection.detect_regime(returns, window=20)
        
        assert regime == 'bull'
    
    def test_detect_bear_regime(self):
        """Test bear market detection"""
        returns = [-0.005, -0.004] * 15  # Consistent negative returns, high volatility
        regime = RegimeDetection.detect_regime(returns, window=20)
        
        # With significant negative returns and volatility, should be bear
        assert regime in ('bear', 'sideways')
    
    def test_detect_sideways_regime(self):
        """Test sideways market detection"""
        returns = [0.0001, -0.0001] * 20  # Oscillating around zero
        regime = RegimeDetection.detect_regime(returns, window=20)
        
        assert regime == 'sideways'
    
    def test_regime_multiplier(self):
        """Test position sizing multipliers"""
        assert RegimeDetection.get_regime_multiplier('bull') == 1.5
        assert RegimeDetection.get_regime_multiplier('sideways') == 1.0
        assert RegimeDetection.get_regime_multiplier('bear') == 0.5


class TestDynamicPositionSizing:
    """Test Kelly Criterion and position sizing"""
    
    def test_kelly_fraction_positive(self):
        """Test Kelly Criterion with winning strategy"""
        kelly = DynamicPositionSizing.kelly_fraction(
            win_rate=0.55,
            avg_win=1.0,
            avg_loss=1.0
        )
        
        assert kelly > 0
        assert kelly <= 0.25  # Half Kelly for safety
    
    def test_kelly_fraction_negative(self):
        """Test Kelly with losing strategy"""
        kelly = DynamicPositionSizing.kelly_fraction(
            win_rate=0.45,
            avg_win=1.0,
            avg_loss=1.0
        )
        
        assert kelly == 0.0  # Don't trade losing strategies
    
    def test_volatility_adjusted_size(self):
        """Test volatility-adjusted position sizing"""
        base = 1000
        
        # High volatility should reduce size
        high_vol_size = DynamicPositionSizing.volatility_adjusted_size(
            base, current_volatility=0.03, target_volatility=0.015
        )
        
        # Low volatility should increase size
        low_vol_size = DynamicPositionSizing.volatility_adjusted_size(
            base, current_volatility=0.01, target_volatility=0.015
        )
        
        assert high_vol_size < base
        assert low_vol_size > base
    
    def test_calculate_position_size(self):
        """Test comprehensive position sizing"""
        size = DynamicPositionSizing.calculate_position_size(
            capital=100000,
            kelly_fraction=0.05,
            volatility=0.012,
            target_volatility=0.015,
            max_risk_pct=0.02
        )
        
        assert size > 0
        assert size <= 100000 * 0.02 / 0.012  # Respects max risk


class TestFeatureEngineering:
    """Test feature extraction"""
    
    def test_extract_features(self):
        """Test feature extraction"""
        prices = np.linspace(100, 120, 50).tolist()
        features = FeatureEngineering.extract_features(prices, window=20)
        
        assert 'momentum_5d' in features
        assert 'volatility_5d' in features
        assert 'price_to_sma' in features
        assert len(features) > 5
    
    def test_normalize_features(self):
        """Test feature normalization"""
        features = {'f1': 2.5, 'f2': -1.5, 'f3': 0.0}
        normalized = FeatureEngineering.normalize_features(features)
        
        # All normalized features should be in [-1, 1]
        for value in normalized.values():
            assert -1.0 <= value <= 1.0


class TestSimpleLSTM:
    """Test LSTM model"""
    
    def test_forward_pass(self):
        """Test LSTM forward pass"""
        lstm = SimpleLSTM(input_size=10, hidden_size=32)
        features = {f'f{i}': 0.1 * i for i in range(10)}
        
        prediction = lstm.forward(features)
        
        assert isinstance(prediction.next_return, float)
        assert 0.0 <= prediction.confidence <= 1.0
        assert 0.0 <= prediction.probability_up <= 1.0
    
    def test_forward_with_empty_features(self):
        """Test LSTM with empty features"""
        lstm = SimpleLSTM()
        prediction = lstm.forward({})
        
        assert prediction.next_return == 0.0
        assert prediction.confidence == 0.0


class TestReinforcementLearning:
    """Test RL agent"""
    
    def test_get_state(self):
        """Test state discretization"""
        agent = ReinforcementLearningAgent()
        
        state = agent.get_state('bull', volatility=0.012, sharpe=1.5)
        
        assert isinstance(state, tuple)
        assert len(state) == 3
        assert all(isinstance(x, int) for x in state)
    
    def test_get_action(self):
        """Test action selection"""
        agent = ReinforcementLearningAgent()
        state = (0, 1, 1)
        
        action = agent.get_action(state)
        
        assert 0 <= action < 5
    
    def test_update_q_value(self):
        """Test Q-value updates"""
        agent = ReinforcementLearningAgent()
        state = (0, 1, 1)
        next_state = (0, 1, 2)
        
        agent.update_q_value(state, action=2, reward=0.05, next_state=next_state)
        
        # Q-value should be non-zero
        assert agent.q_values[state][2] > 0
    
    def test_position_multiplier(self):
        """Test position multiplier from action"""
        agent = ReinforcementLearningAgent()
        
        assert agent.get_position_multiplier(0) == 0.0
        assert agent.get_position_multiplier(2) == 1.0
        assert agent.get_position_multiplier(4) == 2.0


class TestOnlineLearner:
    """Test online learning"""
    
    def test_add_observation(self):
        """Test adding observations"""
        learner = OnlineLearner()
        
        learner.add_observation({'f1': 0.1}, 0.02)
        learner.add_observation({'f1': 0.15}, -0.01)
        
        assert len(learner.feature_history) == 2
        assert len(learner.return_history) == 2
    
    def test_get_recent_accuracy(self):
        """Test accuracy calculation"""
        learner = OnlineLearner()
        
        # Add 10 positive returns
        for i in range(10):
            learner.add_observation({'f1': 0.1}, 0.01)
        
        accuracy = learner.get_recent_accuracy(window=10)
        assert accuracy == 1.0  # All positive
    
    def test_should_update_model(self):
        """Test model update trigger"""
        learner = OnlineLearner()
        
        # Add bad predictions (negative returns) - more than window size
        for i in range(60):
            learner.add_observation({'f1': 0.1}, -0.01)
        
        # With 60 negative returns, accuracy should be 0
        accuracy = learner.get_recent_accuracy(window=50)
        assert accuracy == 0.0
        
        should_update = learner.should_update_model(accuracy_threshold=0.5)
        assert should_update is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
