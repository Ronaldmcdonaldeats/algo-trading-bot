"""
Strategy Maker: Generates candidate trading strategies based on successful patterns.

This module creates new trading strategies by:
1. Learning from historically successful strategy parameters
2. Combining winning indicators and thresholds
3. Applying mutations and crossovers to create variations
4. Feeding results back to the bot for continuous improvement
"""

from __future__ import annotations

import logging
import json
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrategyCandidate:
    """A candidate strategy configuration for testing"""
    
    id: str
    name: str
    parameters: Dict[str, float]  # e.g., {'rsi_threshold': 30, 'macd_period': 12}
    generator_method: str  # 'random', 'mutation', 'crossover', 'learned'
    parent_ids: List[str] = field(default_factory=list)  # Which strategies this came from
    generation: int = 0  # Which generation of strategies this is
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return asdict(self)


@dataclass
class StrategyPerformance:
    """Results from testing a strategy candidate"""
    
    candidate_id: str
    total_return: float  # Cumulative return %
    sharpe_ratio: float  # Risk-adjusted return
    max_drawdown: float  # Worst peak-to-trough decline
    win_rate: float  # % of winning trades
    num_trades: int  # Total trades executed
    spx_return: float  # S&P 500 benchmark return over same period
    outperformance: float  # (total_return - spx_return) in percentage points
    passed: bool  # True if outperformance >= 10%
    tested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class StrategyMaker:
    """Generate candidate trading strategies based on learned patterns"""
    
    def __init__(
        self,
        cache_dir: str = ".cache/strategy_maker",
        population_size: int = 20,
        mutation_rate: float = 0.15,
        crossover_rate: float = 0.30,
    ):
        """
        Initialize StrategyMaker.
        
        Args:
            cache_dir: Directory to store strategy history and results
            population_size: Number of candidates to maintain
            mutation_rate: Probability of parameter mutation (0-1)
            crossover_rate: Probability of combining two strategies (0-1)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.population_size = max(5, int(population_size))
        self.mutation_rate = max(0.01, min(0.5, float(mutation_rate)))
        self.crossover_rate = max(0.01, min(0.5, float(crossover_rate)))
        
        self.generation = 0
        self.candidates: List[StrategyCandidate] = []
        self.successful_candidates: List[Tuple[StrategyCandidate, StrategyPerformance]] = []
        self.all_results: List[StrategyPerformance] = []
        
        self._load_history()
        logger.info(f"StrategyMaker initialized: gen={self.generation}, "
                   f"successful={len(self.successful_candidates)}, "
                   f"population={len(self.candidates)}")
    
    def _load_history(self) -> None:
        """Load strategy history and results from cache"""
        try:
            candidates_file = self.cache_dir / "candidates.json"
            results_file = self.cache_dir / "results.json"
            
            if candidates_file.exists():
                with open(candidates_file) as f:
                    data = json.load(f)
                    self.generation = data.get("generation", 0)
                    candidates_list = data.get("candidates", [])
                    self.candidates = [
                        StrategyCandidate(
                            id=c["id"],
                            name=c["name"],
                            parameters=c["parameters"],
                            generator_method=c["generator_method"],
                            parent_ids=c.get("parent_ids", []),
                            generation=c.get("generation", 0),
                            created_at=c.get("created_at", ""),
                        )
                        for c in candidates_list
                    ]
            
            if results_file.exists():
                with open(results_file) as f:
                    results_list = json.load(f).get("results", [])
                    self.all_results = [
                        StrategyPerformance(
                            candidate_id=r["candidate_id"],
                            total_return=float(r["total_return"]),
                            sharpe_ratio=float(r["sharpe_ratio"]),
                            max_drawdown=float(r["max_drawdown"]),
                            win_rate=float(r["win_rate"]),
                            num_trades=int(r["num_trades"]),
                            spx_return=float(r["spx_return"]),
                            outperformance=float(r["outperformance"]),
                            passed=bool(r["passed"]),
                            tested_at=r.get("tested_at", ""),
                        )
                        for r in results_list
                    ]
                    
                    # Separate successful candidates
                    for result in self.all_results:
                        if result.passed:
                            for cand in self.candidates:
                                if cand.id == result.candidate_id:
                                    self.successful_candidates.append((cand, result))
                                    break
        except Exception as e:
            logger.warning(f"Failed to load strategy history: {e}")
    
    def save_history(self) -> None:
        """Save strategy history and results to cache"""
        try:
            candidates_file = self.cache_dir / "candidates.json"
            results_file = self.cache_dir / "results.json"
            
            # Save candidates
            candidates_data = {
                "generation": self.generation,
                "timestamp": datetime.now().isoformat(),
                "candidates": [c.to_dict() for c in self.candidates],
            }
            with open(candidates_file, "w") as f:
                json.dump(candidates_data, f, indent=2)
            
            # Save results
            results_data = {
                "timestamp": datetime.now().isoformat(),
                "results": [r.to_dict() for r in self.all_results],
            }
            with open(results_file, "w") as f:
                json.dump(results_data, f, indent=2)
            
            logger.debug(f"Saved {len(self.candidates)} candidates and {len(self.all_results)} results")
        except Exception as e:
            logger.error(f"Failed to save strategy history: {e}")
    
    def _generate_random_parameters(self) -> Dict[str, float]:
        """Generate random strategy parameters"""
        return {
            "rsi_period": random.choice([7, 14, 21]),
            "rsi_buy": float(random.randint(20, 40)),
            "rsi_sell": float(random.randint(60, 80)),
            "macd_fast": float(random.choice([8, 12, 13])),
            "macd_slow": float(random.choice([17, 26, 27])),
            "macd_signal": float(random.choice([5, 9, 11])),
            "atr_period": float(random.choice([10, 14, 20])),
            "atr_multiplier": float(random.uniform(1.5, 3.0)),
            "momentum_period": float(random.choice([10, 20, 30])),
            "volatility_threshold": float(random.uniform(0.01, 0.05)),
            "position_size_pct": float(random.uniform(0.02, 0.10)),
        }
    
    def _mutate_parameters(self, params: Dict[str, float]) -> Dict[str, float]:
        """Mutate strategy parameters randomly"""
        mutated = params.copy()
        
        for key in mutated:
            if random.random() < 0.3:  # 30% chance to mutate each param
                if "period" in key or "fast" in key or "slow" in key:
                    # Discrete period values
                    mutated[key] = float(random.choice(
                        [int(mutated[key]) - 1, int(mutated[key]), int(mutated[key]) + 1]
                    ))
                elif "threshold" in key or "multiplier" in key or "size" in key:
                    # Continuous values - add small random change
                    change = mutated[key] * random.uniform(-0.2, 0.2)
                    mutated[key] = max(0.001, mutated[key] + change)
                elif "buy" in key:
                    # RSI buy threshold (20-40)
                    mutated[key] = max(20.0, min(40.0, mutated[key] + random.uniform(-5, 5)))
                elif "sell" in key:
                    # RSI sell threshold (60-80)
                    mutated[key] = max(60.0, min(80.0, mutated[key] + random.uniform(-5, 5)))
        
        return mutated
    
    def _crossover_parameters(self, params1: Dict[str, float], params2: Dict[str, float]) -> Dict[str, float]:
        """Combine parameters from two strategies"""
        offspring = {}
        
        for key in params1:
            if random.random() < 0.5:
                offspring[key] = params1[key]
            else:
                offspring[key] = params2.get(key, params1[key])
        
        return offspring
    
    def generate_candidates(self, num_candidates: int = 10) -> List[StrategyCandidate]:
        """
        Generate new strategy candidates.
        
        Strategy:
        1. 30% random (exploration)
        2. 40% mutations of successful strategies (exploitation)
        3. 30% crossovers of successful pairs (combination)
        
        Returns:
            List of new candidate strategies
        """
        num_candidates = max(1, int(num_candidates))
        new_candidates = []
        
        # 30% random
        num_random = max(1, int(num_candidates * 0.30))
        for i in range(num_random):
            candidate_id = f"random_{self.generation}_{i}"
            params = self._generate_random_parameters()
            candidate = StrategyCandidate(
                id=candidate_id,
                name=f"Random_{self.generation}_{i}",
                parameters=params,
                generator_method="random",
                generation=self.generation,
            )
            new_candidates.append(candidate)
        
        # 40% mutations of successful strategies
        num_mutations = max(1, int(num_candidates * 0.40))
        if self.successful_candidates:
            for i in range(num_mutations):
                successful_cand, _ = random.choice(self.successful_candidates)
                candidate_id = f"mutation_{self.generation}_{i}"
                params = self._mutate_parameters(successful_cand.parameters)
                candidate = StrategyCandidate(
                    id=candidate_id,
                    name=f"Mutation_{self.generation}_{i}",
                    parameters=params,
                    generator_method="mutation",
                    parent_ids=[successful_cand.id],
                    generation=self.generation,
                )
                new_candidates.append(candidate)
        
        # 30% crossovers
        num_crossovers = max(1, int(num_candidates * 0.30))
        if len(self.successful_candidates) >= 2:
            for i in range(num_crossovers):
                cand1, _ = random.choice(self.successful_candidates)
                cand2, _ = random.choice(self.successful_candidates)
                candidate_id = f"crossover_{self.generation}_{i}"
                params = self._crossover_parameters(cand1.parameters, cand2.parameters)
                candidate = StrategyCandidate(
                    id=candidate_id,
                    name=f"Crossover_{self.generation}_{i}",
                    parameters=params,
                    generator_method="crossover",
                    parent_ids=[cand1.id, cand2.id],
                    generation=self.generation,
                )
                new_candidates.append(candidate)
        
        # Fill remaining with mutations/crossovers if not enough successful strategies
        while len(new_candidates) < num_candidates:
            if self.successful_candidates:
                cand, _ = random.choice(self.successful_candidates)
                params = self._mutate_parameters(cand.parameters)
            else:
                params = self._generate_random_parameters()
            
            candidate_id = f"filler_{self.generation}_{len(new_candidates)}"
            candidate = StrategyCandidate(
                id=candidate_id,
                name=f"Filler_{self.generation}_{len(new_candidates)}",
                parameters=params,
                generator_method="mutation" if self.successful_candidates else "random",
                generation=self.generation,
            )
            new_candidates.append(candidate)
        
        # Keep only the requested number
        new_candidates = new_candidates[:num_candidates]
        self.candidates = new_candidates
        
        logger.info(f"Generated {len(new_candidates)} candidates for generation {self.generation}")
        return new_candidates
    
    def record_result(self, performance: StrategyPerformance) -> None:
        """
        Record test result for a strategy candidate.
        
        If passed, add to successful strategies for future learning.
        """
        self.all_results.append(performance)
        
        if performance.passed:
            for cand in self.candidates:
                if cand.id == performance.candidate_id:
                    self.successful_candidates.append((cand, performance))
                    logger.info(
                        f"✅ Strategy {cand.name} PASSED: "
                        f"+{performance.outperformance:.1f}% vs S&P 500 "
                        f"(Sharpe: {performance.sharpe_ratio:.2f})"
                    )
                    break
        else:
            logger.debug(
                f"❌ Strategy {performance.candidate_id} failed: "
                f"{performance.outperformance:+.1f}% vs S&P 500"
            )
    
    def advance_generation(self) -> None:
        """Move to next generation of strategy evolution"""
        self.generation += 1
        self.save_history()
        logger.info(f"Advanced to generation {self.generation}, "
                   f"{len(self.successful_candidates)} strategies passed")


class StrategyRepository:
    """Persistent storage for strategies and results"""
    
    def __init__(self, db_path: str = ".cache/strategies.db"):
        """Initialize repository"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def save_candidate(self, candidate: StrategyCandidate) -> None:
        """Save strategy candidate"""
        # For now, use JSON. Could upgrade to SQLite
        cache_file = self.db_path.parent / f"candidate_{candidate.id}.json"
        with open(cache_file, "w") as f:
            json.dump(candidate.to_dict(), f, indent=2)
    
    def load_candidate(self, candidate_id: str) -> Optional[StrategyCandidate]:
        """Load strategy candidate by ID"""
        cache_file = self.db_path.parent / f"candidate_{candidate_id}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                data = json.load(f)
                return StrategyCandidate(
                    id=data["id"],
                    name=data["name"],
                    parameters=data["parameters"],
                    generator_method=data["generator_method"],
                    parent_ids=data.get("parent_ids", []),
                    generation=data.get("generation", 0),
                    created_at=data.get("created_at", ""),
                )
        return None
