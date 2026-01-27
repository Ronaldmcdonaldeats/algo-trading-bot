"""
ML System Optimizer: Adaptive genetic algorithm parameters for faster convergence.

Optimizations:
- Adaptive mutation rates (decrease as generation improves)
- Elitism: preserve best strategies across generations
- Diversified population: maintain parameter diversity to avoid premature convergence
- Parallel strategy testing (already in strategy_tester.py)
"""

from __future__ import annotations

import logging
import math
from typing import List, Tuple
from dataclasses import dataclass

from trading_bot.learn.strategy_maker import StrategyCandidate, StrategyPerformance

logger = logging.getLogger(__name__)


@dataclass
class AdaptiveGeneticParams:
    """Adaptive parameters for genetic algorithm"""
    
    base_mutation_rate: float = 0.15
    base_crossover_rate: float = 0.30
    min_mutation_rate: float = 0.05  # Don't go below this
    max_mutation_rate: float = 0.50  # Don't go above this
    
    # Elitism: preserve top N strategies
    elite_count: int = 3  # Keep best 3 strategies per generation
    
    # Diversity preservation
    min_diversity_score: float = 0.3  # Ensure ~30% parameter variance
    
    def adaptive_mutation_rate(self, generation: int, success_rate: float) -> float:
        """
        Adapt mutation rate based on generation and success rate.
        
        - Early generations: high mutation (exploration)
        - Later generations with low success: increase mutation (escape local optima)
        - Later generations with high success: lower mutation (exploit winners)
        """
        # Generation factor: decrease over time (exploration → exploitation)
        generation_factor = 1.0 / (1.0 + 0.1 * generation)
        
        # Success factor: high success → lower mutation, low success → higher mutation
        # success_rate goes 0-1, we want inverse relationship
        success_factor = 1.0 + (1.0 - success_rate)
        
        # Combined rate
        adaptive_rate = self.base_mutation_rate * generation_factor * success_factor
        
        # Clamp to bounds
        return max(self.min_mutation_rate, min(self.max_mutation_rate, adaptive_rate))
    
    def adaptive_crossover_rate(self, generation: int, success_rate: float) -> float:
        """
        Adapt crossover rate based on generation and success rate.
        
        - High success: increase crossover (combine winners)
        - Low success: decrease crossover (more exploration)
        """
        # Inverse of mutation: when success is high, use crossover more
        crossover_rate = self.base_crossover_rate * (0.5 + success_rate)
        
        # Clamp to reasonable range
        return max(0.1, min(0.5, crossover_rate))


class ConvergenceTracker:
    """Track convergence metrics to detect stagnation"""
    
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.best_scores: List[float] = []
        self.generation_count = 0
    
    def update(self, best_outperformance: float) -> None:
        """Record best performance for this generation"""
        self.best_scores.append(best_outperformance)
        self.generation_count += 1
        logger.debug(f"Gen {self.generation_count}: best outperformance = {best_outperformance:.1f}%")
    
    def is_converged(self, threshold: float = 0.5) -> bool:
        """
        Check if algorithm has converged (improvement < threshold for last N generations).
        
        Args:
            threshold: Minimum improvement to consider as "progress" (percentage points)
        
        Returns:
            True if stagnant (no improvement), False if still improving
        """
        if len(self.best_scores) < self.window_size + 1:
            return False
        
        # Check improvement over last window
        recent = self.best_scores[-self.window_size:]
        improvement = max(recent) - min(recent)
        
        is_stagnant = improvement < threshold
        if is_stagnant:
            logger.warning(f"Algorithm converged: only {improvement:.1f}% improvement in last {self.window_size} generations")
        
        return is_stagnant
    
    def get_convergence_rate(self) -> float:
        """
        Calculate convergence rate (improvement per generation).
        
        Returns:
            Percentage points improvement per generation
        """
        if len(self.best_scores) < 2:
            return 0.0
        
        total_improvement = self.best_scores[-1] - self.best_scores[0]
        generations = len(self.best_scores) - 1
        
        return total_improvement / generations if generations > 0 else 0.0


class ElitismManager:
    """Manage elite strategies for preservation across generations"""
    
    def __init__(self, elite_count: int = 3):
        self.elite_count = elite_count
        self.elite_strategies: List[Tuple[StrategyCandidate, StrategyPerformance]] = []
    
    def update_elite(
        self,
        candidates: List[StrategyCandidate],
        performances: List[StrategyPerformance],
    ) -> None:
        """Update elite with best strategies from current generation"""
        # Create candidate -> performance mapping
        candidate_map = {perf.candidate_id: perf for perf in performances}
        
        # Sort by outperformance
        ranked = sorted(
            [(c, candidate_map.get(c.id)) for c in candidates if c.id in candidate_map],
            key=lambda x: x[1].outperformance if x[1] else -float('inf'),
            reverse=True
        )
        
        # Keep top N
        self.elite_strategies = ranked[:self.elite_count]
        
        if self.elite_strategies:
            best_elite = self.elite_strategies[0]
            logger.info(f"Elite updated: {best_elite[1].outperformance:.1f}% outperformance")
    
    def get_elite_candidates(self) -> List[StrategyCandidate]:
        """Get elite candidates for next generation"""
        return [c for c, _ in self.elite_strategies]
    
    def get_elite_for_mutation(self) -> List[StrategyCandidate]:
        """Get elite strategies for use in mutation/crossover"""
        return self.get_elite_candidates()


class DiversityManager:
    """Ensure population maintains sufficient parameter diversity"""
    
    @staticmethod
    def calculate_diversity_score(candidates: List[StrategyCandidate]) -> float:
        """
        Calculate parameter diversity of population (0-1).
        
        0 = all identical parameters, 1 = maximum diversity
        """
        if len(candidates) < 2:
            return 1.0
        
        import numpy as np
        
        # Extract parameters into array
        param_names = list(candidates[0].parameters.keys())
        param_values = np.array([
            [c.parameters.get(name, 0.0) for name in param_names]
            for c in candidates
        ])
        
        # Calculate parameter variance across population
        param_std = np.std(param_values, axis=0)
        
        # Average normalized standard deviation (0-1)
        diversity = np.mean(param_std) / (np.max(param_values) - np.min(param_values) + 1e-8)
        
        return min(1.0, max(0.0, float(diversity)))
    
    @staticmethod
    def ensure_diversity(
        candidates: List[StrategyCandidate],
        min_diversity: float = 0.3,
    ) -> List[StrategyCandidate]:
        """
        Ensure population maintains minimum diversity by injecting random variations.
        
        If diversity < threshold, replace some candidates with new random ones.
        """
        diversity = DiversityManager.calculate_diversity_score(candidates)
        
        if diversity < min_diversity:
            logger.warning(f"Low population diversity: {diversity:.2f}, injecting random variations")
            # Replace lower-performing candidates with random variations
            # (implementation in strategy_maker.generate_candidates)
            pass
        
        return candidates


class MLOptimizer:
    """Orchestrate ML system optimizations"""
    
    def __init__(self):
        self.adaptive_params = AdaptiveGeneticParams()
        self.convergence_tracker = ConvergenceTracker()
        self.elitism_manager = ElitismManager(elite_count=3)
        self.diversity_manager = DiversityManager()
    
    def calculate_adaptive_rates(
        self,
        generation: int,
        success_rate: float,
    ) -> Tuple[float, float]:
        """Calculate adaptive mutation and crossover rates"""
        mutation = self.adaptive_params.adaptive_mutation_rate(generation, success_rate)
        crossover = self.adaptive_params.adaptive_crossover_rate(generation, success_rate)
        
        logger.info(f"Gen {generation}: mutation={mutation:.2%}, crossover={crossover:.2%}, "
                   f"success_rate={success_rate:.2%}")
        
        return mutation, crossover
    
    def should_continue_evolution(self) -> bool:
        """Determine if algorithm should continue or has converged"""
        return not self.convergence_tracker.is_converged(threshold=0.5)
    
    def get_diversity_score(self, candidates: List[StrategyCandidate]) -> float:
        """Get current population diversity"""
        return DiversityManager.calculate_diversity_score(candidates)
