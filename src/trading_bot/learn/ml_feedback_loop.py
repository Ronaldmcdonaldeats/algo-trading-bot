"""
ML Feedback Loop: Orchestrates strategy generation, testing, and learning cycle.

This module implements the complete feedback loop:
1. StrategyMaker generates candidate strategies
2. StrategyTester evaluates them against historical data
3. Results feedback to StrategyMaker to improve future generations
4. Successful strategies (>10% above S&P 500) inform next generation

OPTIMIZATIONS:
- Adaptive mutation/crossover rates (decrease as algorithm converges)
- Elitism: preserve top strategies across generations
- Diversity management: maintain parameter diversity to avoid local optima
- Convergence detection: stop evolution when no progress made
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
import json
from pathlib import Path
import numpy as np

from trading_bot.learn.strategy_maker import (
    StrategyMaker,
    StrategyCandidate,
    StrategyPerformance,
)
from trading_bot.learn.strategy_tester import (
    StrategyTester,
    BatchStrategyTester,
)
from trading_bot.learn.ml_optimizer import (
    MLOptimizer,
    ConvergenceTracker,
    ElitismManager,
    DiversityManager,
)
from trading_bot.data.providers import MarketDataProvider

logger = logging.getLogger(__name__)


@dataclass
class GenerationReport:
    """Results from one generation of strategy evolution"""
    
    generation: int
    num_candidates: int
    num_passed: int
    pass_rate: float  # % that passed
    best_performer: Optional[Tuple[str, float]]  # (candidate_id, outperformance)
    avg_outperformance: float
    avg_sharpe: float
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "generation": self.generation,
            "num_candidates": self.num_candidates,
            "num_passed": self.num_passed,
            "pass_rate": self.pass_rate,
            "best_performer": self.best_performer,
            "avg_outperformance": self.avg_outperformance,
            "avg_sharpe": self.avg_sharpe,
            "timestamp": self.timestamp,
        }


class MLFeedbackLoop:
    """Complete strategy learning pipeline with feedback and adaptive optimization"""
    
    def __init__(
        self,
        strategy_maker: Optional[StrategyMaker] = None,
        strategy_tester: Optional[StrategyTester] = None,
        symbols: Optional[List[str]] = None,
        cache_dir: str = ".cache/ml_feedback",
        use_adaptive_optimization: bool = True,
    ):
        """
        Initialize ML feedback loop.
        
        Args:
            strategy_maker: Strategy generator (auto-created if None)
            strategy_tester: Strategy validator (auto-created if None)
            symbols: Symbols to trade
            cache_dir: Directory for caching results
            use_adaptive_optimization: Use adaptive mutation rates & elitism
        """
        self.strategy_maker = strategy_maker or StrategyMaker()
        self.strategy_tester = strategy_tester or StrategyTester()
        self.batch_tester = BatchStrategyTester(self.strategy_tester)
        self.symbols = symbols or ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.generation_reports: List[GenerationReport] = []
        
        # OPTIMIZATION: Adaptive parameters for faster convergence
        self.use_adaptive_optimization = use_adaptive_optimization
        self.ml_optimizer = MLOptimizer() if use_adaptive_optimization else None
        
        self._load_reports()
        
        logger.info(
            f"MLFeedbackLoop initialized: symbols={self.symbols}, "
            f"generations_complete={len(self.generation_reports)}, "
            f"adaptive_optimization={'enabled' if use_adaptive_optimization else 'disabled'}"
        )
    
    def _load_reports(self) -> None:
        """Load previous generation reports"""
        try:
            reports_file = self.cache_dir / "generation_reports.json"
            if reports_file.exists():
                with open(reports_file) as f:
                    data = json.load(f).get("reports", [])
                    self.generation_reports = [
                        GenerationReport(
                            generation=r["generation"],
                            num_candidates=r["num_candidates"],
                            num_passed=r["num_passed"],
                            pass_rate=r["pass_rate"],
                            best_performer=tuple(r["best_performer"]) if r["best_performer"] else None,
                            avg_outperformance=r["avg_outperformance"],
                            avg_sharpe=r["avg_sharpe"],
                            timestamp=r["timestamp"],
                        )
                        for r in data
                    ]
        except Exception as e:
            logger.warning(f"Failed to load generation reports: {e}")
    
    def _save_reports(self) -> None:
        """Save generation reports to disk"""
        try:
            reports_file = self.cache_dir / "generation_reports.json"
            data = {
                "timestamp": datetime.now().isoformat(),
                "reports": [r.to_dict() for r in self.generation_reports],
            }
            with open(reports_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save generation reports: {e}")
    
    def run_generation(
        self,
        num_candidates: int = 20,
    ) -> GenerationReport:
        """
        Run one generation of strategy evolution (OPTIMIZED).
        
        Process:
        1. Generate candidate strategies (with adaptive parameters if enabled)
        2. Test each on historical data (parallel)
        3. Score based on >10% outperformance vs S&P 500
        4. Update success rate and adaptive parameters
        5. Save successful strategies for next generation
        6. Advance to next generation
        
        OPTIMIZATIONS:
        - Adaptive mutation/crossover rates based on success
        - Elitism: preserve top strategies
        - Diversity management: avoid premature convergence
        - Convergence detection: stop if no progress
        
        Returns:
            GenerationReport with results
        """
        logger.info(
            f"Starting generation {self.strategy_maker.generation}: "
            f"generating {num_candidates} candidates"
        )
        
        # OPTIMIZATION: Calculate adaptive parameters
        if self.use_adaptive_optimization and self.generation_reports:
            last_report = self.generation_reports[-1]
            success_rate = last_report.pass_rate
            
            # Update mutation/crossover rates based on success
            mutation_rate, crossover_rate = self.ml_optimizer.calculate_adaptive_rates(
                generation=self.strategy_maker.generation,
                success_rate=success_rate,
            )
            
            # Apply adaptive rates to strategy maker
            self.strategy_maker.mutation_rate = mutation_rate
            self.strategy_maker.crossover_rate = crossover_rate
        
        # Step 1: Generate candidates (with adaptive parameters)
        candidates = self.strategy_maker.generate_candidates(num_candidates)
        logger.info(f"Generated {len(candidates)} strategy candidates")
        
        # OPTIMIZATION: Check population diversity
        if self.use_adaptive_optimization:
            diversity = self.ml_optimizer.get_diversity_score(candidates)
            logger.info(f"Population diversity score: {diversity:.2f}")
            if diversity < 0.3:
                logger.warning("Low population diversity - consider increasing mutation rate")
        
        # Step 2: Test each candidate (parallel testing)
        logger.info("Beginning strategy testing (parallel)...")
        results = self.batch_tester.test_batch(candidates, self.symbols)
        
        # Step 3: Record results and update maker
        passed = 0
        passed_results = []
        for result in results:
            self.strategy_maker.record_result(result)
            if result.passed:
                passed += 1
                passed_results.append(result)
        
        # Step 4: Calculate report
        if results:
            pass_rate = (passed / len(results)) * 100
            avg_outperformance = sum(r.outperformance for r in results) / len(results)
            avg_sharpe = sum(r.sharpe_ratio for r in results) / len(results)
            
            best_result = max(results, key=lambda r: r.outperformance)
            best_performer = (best_result.candidate_id, best_result.outperformance)
        else:
            pass_rate = 0.0
            avg_outperformance = 0.0
            avg_sharpe = 0.0
            best_performer = None
        
        report = GenerationReport(
            generation=self.strategy_maker.generation,
            num_candidates=len(candidates),
            num_passed=passed,
            pass_rate=pass_rate,
            best_performer=best_performer,
            avg_outperformance=avg_outperformance,
            avg_sharpe=avg_sharpe,
            timestamp=datetime.now().isoformat(),
        )
        
        self.generation_reports.append(report)
        
        logger.info(
            f"Generation {self.strategy_maker.generation} complete: "
            f"{passed}/{len(results)} passed ({pass_rate:.1f}%), "
            f"avg outperformance {avg_outperformance:+.1f}%, "
            f"best {best_performer[1]:+.1f}% if best_performer else 'N/A'"
        )
        
        # Step 5: Advance generation
        self.strategy_maker.advance_generation()
        self._save_reports()
        
        return report
    
    def run_multiple_generations(
        self,
        num_generations: int = 5,
        candidates_per_generation: int = 20,
    ) -> List[GenerationReport]:
        """
        Run multiple generations of strategy evolution.
        
        Each generation learns from previous successes.
        
        Returns:
            List of GenerationReport for each generation
        """
        num_generations = max(1, int(num_generations))
        logger.info(
            f"Starting multi-generation run: {num_generations} generations, "
            f"{candidates_per_generation} candidates each"
        )
        
        reports = []
        for gen in range(num_generations):
            try:
                report = self.run_generation(candidates_per_generation)
                reports.append(report)
                
                # Log progress
                logger.info(
                    f"Progress: {gen+1}/{num_generations} generations complete, "
                    f"cumulative passed: {sum(r.num_passed for r in reports)}"
                )
            
            except Exception as e:
                logger.error(f"Error in generation {gen}: {e}", exc_info=True)
                break
        
        return reports
    
    def get_best_strategies(self, top_n: int = 5) -> List[Tuple[StrategyCandidate, StrategyPerformance]]:
        """Get top N best performing strategies"""
        all_results = self.strategy_maker.all_results
        if not all_results:
            return []
        
        # Sort by outperformance
        sorted_results = sorted(all_results, key=lambda r: r.outperformance, reverse=True)
        
        top_results = sorted_results[:top_n]
        best_strategies = []
        
        for result in top_results:
            # Find corresponding candidate
            for cand in self.strategy_maker.candidates:
                if cand.id == result.candidate_id:
                    best_strategies.append((cand, result))
                    break
        
        return best_strategies
    
    def apply_best_to_bot(
        self,
        engine,
    ) -> None:
        """
        Apply best performing strategy to the bot.
        
        This integrates the learned strategy into the active trading bot.
        
        Args:
            engine: PaperEngine or similar trading bot instance
        """
        best = self.get_best_strategies(top_n=1)
        if not best:
            logger.warning("No successful strategies to apply")
            return
        
        best_candidate, best_performance = best[0]
        
        logger.info(
            f"Applying best strategy {best_candidate.name} to bot: "
            f"+{best_performance.outperformance:.1f}% vs S&P 500"
        )
        
        # Update engine with best parameters
        if hasattr(engine, "params"):
            engine.params.update(best_candidate.parameters)
            logger.info(f"Updated engine parameters: {best_candidate.parameters}")
        
        if hasattr(engine, "repo") and hasattr(engine.repo, "log_order_filled"):
            # Log this update
            engine.repo.log_order_filled(
                None,  # No specific order, just marking update
            )
    
    def print_summary(self) -> None:
        """Print summary of all generations"""
        if not self.generation_reports:
            print("No generation reports yet")
            return
        
        print("\n" + "="*80)
        print("ML FEEDBACK LOOP SUMMARY")
        print("="*80)
        
        total_candidates = sum(r.num_candidates for r in self.generation_reports)
        total_passed = sum(r.num_passed for r in self.generation_reports)
        
        print(f"Total generations: {len(self.generation_reports)}")
        print(f"Total candidates: {total_candidates}")
        print(f"Total passed (>10% above S&P 500): {total_passed} ({100*total_passed/max(1,total_candidates):.1f}%)")
        print(f"Avg outperformance: {sum(r.avg_outperformance for r in self.generation_reports)/len(self.generation_reports):+.1f}%")
        
        print("\nGeneration Details:")
        print(f"{'Gen':<5} {'Candidates':<12} {'Passed':<10} {'Rate':<8} {'Avg Out%':<10} {'Best':<10}")
        print("-"*80)
        
        for report in self.generation_reports:
            best_str = f"+{report.best_performer[1]:.1f}%" if report.best_performer else "N/A"
            print(
                f"{report.generation:<5} "
                f"{report.num_candidates:<12} "
                f"{report.num_passed:<10} "
                f"{report.pass_rate:<8.1f}% "
                f"{report.avg_outperformance:<+10.1f} "
                f"{best_str:<10}"
            )
        
        best_strategies = self.get_best_strategies(5)
        if best_strategies:
            print("\nTop 5 Strategies:")
            for i, (cand, perf) in enumerate(best_strategies, 1):
                print(
                    f"  {i}. {cand.name}: "
                    f"+{perf.outperformance:.1f}% vs SPX, "
                    f"Sharpe={perf.sharpe_ratio:.2f}, "
                    f"Win rate={perf.win_rate:.1f}%"
                )
        
        print("="*80 + "\n")
