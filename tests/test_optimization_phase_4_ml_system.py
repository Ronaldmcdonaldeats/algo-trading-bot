"""
Phase 4 ML System Optimization Tests (5 tests)

Coverage:
- Adaptive genetic algorithm parameters
- Convergence detection and tracking
- Elitism management (preserving best strategies)
- Population diversity management
- ML optimizer orchestration
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from trading_bot.learn.ml_optimizer import (
    AdaptiveGeneticParams,
    ConvergenceTracker,
    ElitismManager,
    DiversityManager,
    MLOptimizer
)


class TestAdaptiveGeneticParams:
    """Test 1: Adaptive genetic algorithm parameters"""
    
    def test_adaptive_mutation_rate_decreases_over_time(self):
        """Test that mutation rate decreases with generation"""
        params = AdaptiveGeneticParams()
        
        # Early generation: high exploration
        rate_gen_0 = params.adaptive_mutation_rate(generation=0, success_rate=0.5)
        
        # Late generation: low exploration
        rate_gen_10 = params.adaptive_mutation_rate(generation=10, success_rate=0.5)
        
        # Rate should decrease
        assert rate_gen_10 < rate_gen_0
    
    def test_adaptive_mutation_rate_increases_on_low_success(self):
        """Test that mutation rate increases when success is low"""
        params = AdaptiveGeneticParams()
        
        # High success rate
        rate_high_success = params.adaptive_mutation_rate(generation=5, success_rate=0.8)
        
        # Low success rate
        rate_low_success = params.adaptive_mutation_rate(generation=5, success_rate=0.1)
        
        # Low success should increase mutation (escape local optima)
        assert rate_low_success > rate_high_success
    
    def test_adaptive_mutation_rate_bounded(self):
        """Test that mutation rate stays within bounds"""
        params = AdaptiveGeneticParams()
        
        for gen in range(20):
            for success in [0.0, 0.25, 0.5, 0.75, 1.0]:
                rate = params.adaptive_mutation_rate(generation=gen, success_rate=success)
                assert 0.0 <= rate <= 1.0
    
    def test_adaptive_crossover_rate_increases_on_success(self):
        """Test that crossover rate increases with success"""
        params = AdaptiveGeneticParams()
        
        # Low success rate
        rate_low_success = params.adaptive_crossover_rate(generation=5, success_rate=0.2)
        
        # High success rate
        rate_high_success = params.adaptive_crossover_rate(generation=5, success_rate=0.8)
        
        # High success should increase crossover (combine winners)
        assert rate_high_success > rate_low_success
    
    def test_adaptive_crossover_rate_bounded(self):
        """Test that crossover rate stays within bounds"""
        params = AdaptiveGeneticParams()
        
        for gen in range(20):
            for success in [0.0, 0.25, 0.5, 0.75, 1.0]:
                rate = params.adaptive_crossover_rate(generation=gen, success_rate=success)
                assert 0.0 <= rate <= 1.0


class TestConvergenceTracker:
    """Test 2: Convergence detection and tracking"""
    
    def test_convergence_tracker_initialization(self):
        """Test ConvergenceTracker initializes correctly"""
        tracker = ConvergenceTracker(window_size=5)
        assert tracker.window_size == 5
    
    def test_convergence_tracker_records_performance(self):
        """Test that tracker records performance over generations"""
        tracker = ConvergenceTracker(window_size=3)
        
        # Simulate improving performance
        tracker.update(0.05)  # Gen 0
        tracker.update(0.08)  # Gen 1
        tracker.update(0.10)  # Gen 2
        
        # Should have 3 recordings
        assert len(tracker.performance_history) == 3
    
    def test_convergence_tracker_detects_plateau(self):
        """Test that tracker detects when improvement plateaus"""
        tracker = ConvergenceTracker(window_size=3)
        
        # Improvements
        tracker.update(0.05)
        tracker.update(0.06)
        tracker.update(0.07)
        
        # No improvement (plateau)
        tracker.update(0.07)
        tracker.update(0.07)
        
        # Should detect convergence
        is_converged = tracker.is_converged(threshold=0.01)
        assert is_converged is True
    
    def test_convergence_tracker_allows_continued_search(self):
        """Test that tracker allows search to continue during improvement"""
        tracker = ConvergenceTracker(window_size=3)
        
        # Steady improvements
        tracker.update(0.05)
        tracker.update(0.08)
        tracker.update(0.12)
        tracker.update(0.15)
        tracker.update(0.18)
        
        # Should not be converged (still improving)
        is_converged = tracker.is_converged(threshold=0.01)
        assert is_converged is False
    
    def test_convergence_rate_calculation(self):
        """Test convergence rate calculation"""
        tracker = ConvergenceTracker(window_size=2)
        
        tracker.update(0.05)
        tracker.update(0.10)  # +0.05
        tracker.update(0.14)  # +0.04
        
        rate = tracker.get_convergence_rate()
        
        # Should show recent improvement
        assert rate > 0


class TestElitismManager:
    """Test 3: Elitism management (preserve best strategies)"""
    
    def test_elitism_manager_initialization(self):
        """Test ElitismManager initializes correctly"""
        manager = ElitismManager(elite_count=3)
        assert manager.elite_count == 3
    
    def test_elitism_manager_selects_top_candidates(self):
        """Test that ElitismManager selects best candidates"""
        manager = ElitismManager(elite_count=2)
        
        # Create mock candidates with different performances
        candidates = [
            Mock(name="strategy_1", parameters={'rsi': 14}),
            Mock(name="strategy_2", parameters={'rsi': 15}),
            Mock(name="strategy_3", parameters={'rsi': 16}),
        ]
        
        performances = [0.10, 0.25, 0.15]  # strategy_2 is best
        
        manager.update_elite(candidates, performances)
        
        elite = manager.get_elite_candidates()
        
        # Should contain top 2 (strategy_2 and strategy_3)
        assert len(elite) <= 2
        assert elite[0].name == "strategy_2"  # Best is first
    
    def test_elitism_manager_preserves_elite_across_generations(self):
        """Test that elite candidates are preserved"""
        manager = ElitismManager(elite_count=2)
        
        # Generation 1
        candidates_1 = [
            Mock(name="gen1_strat1", parameters={'rsi': 14}),
            Mock(name="gen1_strat2", parameters={'rsi': 15}),
            Mock(name="gen1_strat3", parameters={'rsi': 16}),
        ]
        manager.update_elite(candidates_1, [0.10, 0.25, 0.15])
        elite_1 = manager.get_elite_candidates()
        
        # Generation 2: all worse than best from gen 1
        candidates_2 = [
            Mock(name="gen2_strat1", parameters={'rsi': 14}),
            Mock(name="gen2_strat2", parameters={'rsi': 15}),
            Mock(name="gen2_strat3", parameters={'rsi': 16}),
        ]
        manager.update_elite(candidates_2, [0.12, 0.20, 0.18])
        elite_2 = manager.get_elite_candidates()
        
        # Best from gen 1 should still be in elite
        best_names = [e.name for e in elite_2]
        assert "gen1_strat2" in best_names
    
    def test_elitism_manager_never_loses_best(self):
        """Test that best strategy is never lost"""
        manager = ElitismManager(elite_count=3)
        
        best_candidate = Mock(name="best", parameters={'rsi': 14})
        
        # Gen 1: establish best
        candidates_1 = [
            Mock(name="ok", parameters={'rsi': 15}),
            best_candidate,
            Mock(name="poor", parameters={'rsi': 16}),
        ]
        manager.update_elite(candidates_1, [0.15, 0.50, 0.05])  # best = 0.50
        
        # Gen 2: even worse performers
        candidates_2 = [
            Mock(name="bad1", parameters={'rsi': 14}),
            Mock(name="bad2", parameters={'rsi': 15}),
        ]
        manager.update_elite(candidates_2, [0.08, 0.12])
        
        elite = manager.get_elite_candidates()
        
        # Best should still be in elite
        best_names = [e.name for e in elite]
        assert "best" in best_names


class TestDiversityManager:
    """Test 4: Population diversity management"""
    
    def test_diversity_manager_initialization(self):
        """Test DiversityManager initializes correctly"""
        manager = DiversityManager(min_diversity_threshold=0.5)
        assert manager.min_diversity_threshold == 0.5
    
    def test_diversity_score_identical_candidates(self):
        """Test diversity with identical candidates"""
        manager = DiversityManager()
        
        # All identical
        candidates = [
            Mock(parameters={'rsi': 14, 'macd': 12}),
            Mock(parameters={'rsi': 14, 'macd': 12}),
            Mock(parameters={'rsi': 14, 'macd': 12}),
        ]
        
        diversity = manager.calculate_diversity_score(candidates)
        
        # Should be 0 (no diversity)
        assert diversity == pytest.approx(0.0, abs=0.01)
    
    def test_diversity_score_different_candidates(self):
        """Test diversity with different candidates"""
        manager = DiversityManager()
        
        # All different
        candidates = [
            Mock(parameters={'rsi': 10, 'macd': 10}),
            Mock(parameters={'rsi': 15, 'macd': 15}),
            Mock(parameters={'rsi': 20, 'macd': 20}),
        ]
        
        diversity = manager.calculate_diversity_score(candidates)
        
        # Should be high (good diversity)
        assert diversity > 0.7
    
    def test_diversity_warnings(self):
        """Test diversity manager warnings"""
        manager = DiversityManager(min_diversity_threshold=0.5)
        
        # Low diversity candidates
        candidates = [
            Mock(parameters={'rsi': 14, 'macd': 12}),
            Mock(parameters={'rsi': 14, 'macd': 12}),
            Mock(parameters={'rsi': 14, 'macd': 12}),
        ]
        
        # Should warn if diversity too low
        diversity = manager.calculate_diversity_score(candidates)
        manager.ensure_diversity(candidates, 0.5)
        
        assert diversity < 0.5


class TestMLOptimizer:
    """Test 5: ML optimizer orchestration"""
    
    def test_ml_optimizer_initialization(self):
        """Test MLOptimizer initializes correctly"""
        optimizer = MLOptimizer()
        
        assert hasattr(optimizer, 'adaptive_params')
        assert hasattr(optimizer, 'convergence_tracker')
        assert hasattr(optimizer, 'elitism_manager')
        assert hasattr(optimizer, 'diversity_manager')
    
    def test_ml_optimizer_calculates_adaptive_rates(self):
        """Test optimizer calculates adaptive rates"""
        optimizer = MLOptimizer()
        
        mutation_rate, crossover_rate = optimizer.calculate_adaptive_rates(
            generation=5,
            success_rate=0.6
        )
        
        # Both should be valid rates
        assert 0.0 <= mutation_rate <= 1.0
        assert 0.0 <= crossover_rate <= 1.0
    
    def test_ml_optimizer_detects_convergence(self):
        """Test optimizer detects convergence"""
        optimizer = MLOptimizer()
        
        # Simulate convergence
        for gen in range(5):
            optimizer.convergence_tracker.update(0.10)  # No improvement
        
        is_converged = optimizer.should_continue_evolution()
        
        # Should recommend stopping if converged
        assert is_converged is False
    
    def test_ml_optimizer_allows_continued_evolution(self):
        """Test optimizer allows continued evolution during improvement"""
        optimizer = MLOptimizer()
        
        # Simulate improvement
        optimizer.convergence_tracker.update(0.05)
        optimizer.convergence_tracker.update(0.08)
        optimizer.convergence_tracker.update(0.12)
        optimizer.convergence_tracker.update(0.15)
        
        is_converged = optimizer.should_continue_evolution()
        
        # Should recommend continuing if improving
        assert is_converged is True
    
    def test_ml_optimizer_assesses_diversity(self):
        """Test optimizer can assess population diversity"""
        optimizer = MLOptimizer()
        
        # Diverse candidates
        candidates = [
            Mock(parameters={'rsi': 10, 'macd': 10}),
            Mock(parameters={'rsi': 15, 'macd': 15}),
            Mock(parameters={'rsi': 20, 'macd': 20}),
        ]
        
        diversity = optimizer.get_diversity_score(candidates)
        
        # Should be high
        assert diversity > 0.5
    
    def test_ml_optimizer_integration(self):
        """Test complete ML optimizer workflow"""
        optimizer = MLOptimizer()
        
        # Simulate multiple generations
        for gen in range(5):
            # Calculate rates
            mutation_rate, crossover_rate = optimizer.calculate_adaptive_rates(
                generation=gen,
                success_rate=0.5 + gen * 0.1  # Improving success
            )
            
            # Update convergence
            optimizer.convergence_tracker.update(0.10 + gen * 0.05)
            
            # Check if should continue
            should_continue = optimizer.should_continue_evolution()
            
            assert mutation_rate >= 0
            assert crossover_rate >= 0
            assert isinstance(should_continue, bool)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
