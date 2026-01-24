"""Tests for strategy learning system."""

import pytest
import tempfile
import shutil
from src.trading_bot.learn.strategy_learner import StrategyLearner, StrategyParams, HybridStrategy


class TestStrategyLearner:
    """Tests for strategy learning."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.learner = StrategyLearner(cache_dir=self.temp_dir)
    
    def teardown_method(self):
        """Cleanup."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_learn_from_backtest(self):
        """Test learning from backtest results."""
        backtest_results = {
            'sharpe_ratio': 1.5,
            'max_drawdown': -0.08,
            'win_rate': 0.55,
            'profit_factor': 1.8,
            'total_return': 0.25,
            'num_trades': 50,
        }
        
        params = self.learner.learn_from_backtest(
            'mean_reversion_rsi',
            {'rsi_threshold': 30, 'lookback': 14},
            backtest_results
        )
        
        assert params is not None
        assert params.name == 'mean_reversion_rsi_learned'
        assert params.performance['sharpe_ratio'] == 1.5
        assert params.performance['win_rate'] == 0.55
        assert params.confidence > 0.5  # 50 trades = high confidence
    
    def test_learn_from_performance_history(self):
        """Test learning from actual trading history."""
        trades = [
            {'entry_price': 100, 'exit_price': 105},  # +5%
            {'entry_price': 100, 'exit_price': 98},   # -2%
            {'entry_price': 100, 'exit_price': 102},  # +2%
            {'entry_price': 100, 'exit_price': 97},   # -3%
            {'entry_price': 100, 'exit_price': 104},  # +4%
        ]
        
        params = self.learner.learn_from_performance_history(
            'test_strategy',
            trades,
            {'threshold': 30, 'period': 14}
        )
        
        assert params is not None
        assert params.performance['win_rate'] == 0.6  # 3 wins out of 5
        assert params.performance['num_trades'] == 5
        assert params.confidence > 0.1
    
    def test_build_hybrid_strategy(self):
        """Test building hybrid strategies from multiple learned ones."""
        # First learn two strategies
        results1 = {
            'sharpe_ratio': 1.5,
            'win_rate': 0.55,
            'profit_factor': 1.8,
            'total_return': 0.25,
            'num_trades': 30,
        }
        
        results2 = {
            'sharpe_ratio': 1.2,
            'win_rate': 0.60,
            'profit_factor': 1.5,
            'total_return': 0.20,
            'num_trades': 40,
        }
        
        params1 = self.learner.learn_from_backtest(
            'strategy1',
            {'param1': 10},
            results1
        )
        
        params2 = self.learner.learn_from_backtest(
            'strategy2',
            {'param2': 20},
            results2
        )
        
        # Now build hybrid
        hybrid = self.learner.build_hybrid_strategy(
            'hybrid_1_2',
            ['strategy1_learned', 'strategy2_learned'],
            self.learner.learned_strategies,
            weight_by='sharpe_ratio'
        )
        
        assert hybrid is not None
        assert hybrid.name == 'hybrid_1_2'
        assert len(hybrid.base_strategies) == 2
        assert len(hybrid.weights) == 2
        assert abs(sum(hybrid.weights.values()) - 1.0) < 0.01  # Weights sum to 1
        assert 'sharpe_ratio' in hybrid.expected_metrics
    
    def test_get_top_strategies(self):
        """Test getting top performing strategies."""
        # Learn multiple strategies with different metrics
        for i in range(5):
            results = {
                'sharpe_ratio': 1.0 + i * 0.2,
                'win_rate': 0.50 + i * 0.02,
                'profit_factor': 1.5 + i * 0.1,
                'total_return': 0.15 + i * 0.05,
                'num_trades': 20 + i * 5,
            }
            
            self.learner.learn_from_backtest(
                f'strategy_{i}',
                {'param': 10 + i},
                results
            )
        
        top = self.learner.get_top_strategies(top_n=3, metric='sharpe_ratio')
        
        assert len(top) == 3
        # Should be sorted by sharpe_ratio descending
        for i in range(len(top) - 1):
            assert top[i].performance['sharpe_ratio'] >= top[i+1].performance['sharpe_ratio']
    
    def test_strategy_persistence(self):
        """Test saving and loading learned strategies."""
        # Learn a strategy
        results = {
            'sharpe_ratio': 1.5,
            'win_rate': 0.55,
            'profit_factor': 1.8,
            'total_return': 0.25,
            'num_trades': 50,
        }
        
        params = self.learner.learn_from_backtest(
            'test_strategy',
            {'threshold': 30},
            results
        )
        
        # Save
        self.learner.save()
        
        # Create new learner with same cache dir
        learner2 = StrategyLearner(cache_dir=self.temp_dir)
        
        # Should have loaded the strategy
        assert 'test_strategy_learned' in learner2.learned_strategies
        loaded_params = learner2.learned_strategies['test_strategy_learned']
        assert loaded_params.performance['sharpe_ratio'] == 1.5
        assert loaded_params.parameters['threshold'] == 30
    
    def test_parameter_adjustment(self):
        """Test that parameters are adjusted based on performance."""
        trades = [
            {'entry_price': 100, 'exit_price': 95},   # -5%
            {'entry_price': 100, 'exit_price': 94},   # -6%
            {'entry_price': 100, 'exit_price': 96},   # -4%
            {'entry_price': 100, 'exit_price': 93},   # -7%
            {'entry_price': 100, 'exit_price': 92},   # -8%
        ]
        
        initial_params = {
            'threshold': 30,
            'stop_loss_pct': 2.0,
        }
        
        params = self.learner.learn_from_performance_history(
            'losing_strategy',
            trades,
            initial_params
        )
        
        assert params is not None
        # With all losses, should have tighter stops
        assert params.parameters.get('stop_loss_pct', 2.0) > 2.0


class TestHybridStrategyExecution:
    """Test hybrid strategy execution."""
    
    def test_hybrid_get_combined_parameters(self):
        """Test getting combined parameters from hybrid strategy."""
        params1 = StrategyParams(
            name='strat1',
            parameters={'threshold': 30, 'lookback': 14},
            performance={'sharpe_ratio': 1.5, 'win_rate': 0.55, 'profit_factor': 1.8},
            confidence=0.9,
            samples=50,
        )
        
        params2 = StrategyParams(
            name='strat2',
            parameters={'rsi_period': 14, 'overbought': 70},
            performance={'sharpe_ratio': 1.2, 'win_rate': 0.60, 'profit_factor': 1.5},
            confidence=0.8,
            samples=40,
        )
        
        hybrid = HybridStrategy(
            name='test_hybrid',
            base_strategies=['strat1', 'strat2'],
            weights={'strat1': 0.6, 'strat2': 0.4},
            meta_parameters={'rebalance_frequency': 5.0},
            expected_metrics={'sharpe_ratio': 1.4, 'win_rate': 0.565},
        )
        
        combined = hybrid.get_combined_parameters({
            'strat1': params1,
            'strat2': params2,
        })
        
        assert 'strat1_threshold' in combined
        assert combined['strat1_threshold'] == 30
        assert 'strat2_rsi_period' in combined
        assert combined['rebalance_frequency'] == 5.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
