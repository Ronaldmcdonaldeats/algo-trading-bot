"""Multi-Algorithm Orchestrator - Coordinates multiple strategies for speed and intelligence."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
import threading
from functools import wraps

from .concurrent_executor import (
    ConcurrentStrategyExecutor,
    ConcurrentExecutionConfig,
    IntelligentSignalCoordinator,
    StrategyResult
)
from .fast_execution import (
    FastExecutionPipeline,
    SmartOrderBatcher,
    Order,
    OrderType,
    OrderPriority
)

logger = logging.getLogger(__name__)


def performance_tracked(func):
    """Decorator to track function performance."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        start_time = time.time()
        result = func(self, *args, **kwargs)
        elapsed_ms = (time.time() - start_time) * 1000
        
        func_name = func.__name__
        if func_name not in self.performance_metrics:
            self.performance_metrics[func_name] = []
        self.performance_metrics[func_name].append(elapsed_ms)
        
        return result
    
    return wrapper


@dataclass
class AlgorithmConfig:
    """Configuration for a single algorithm/strategy."""
    name: str
    func: Callable
    enabled: bool = True
    weight: float = 1.0  # Default weight (0-1)
    timeout_seconds: float = 5.0
    cache_results: bool = True
    min_confidence: float = 0.3  # Minimum confidence to generate signal
    use_for_learning: bool = True  # Include in adaptive weighting


@dataclass
class OrchestratorConfig:
    """Configuration for multi-algorithm orchestrator."""
    max_concurrent_algorithms: int = 8
    execution_batch_window_ms: int = 50  # Ultra-fast batching
    enable_signal_batching: bool = True
    enable_adaptive_weighting: bool = True
    enable_conflict_resolution: bool = True
    cache_ttl_seconds: float = 60.0
    performance_history_size: int = 1000


@dataclass
class ExecutionSummary:
    """Summary of single execution cycle."""
    timestamp: datetime
    num_algorithms: int
    num_signals_generated: int
    final_signal: int
    final_confidence: float
    execution_time_ms: float
    batches_created: int
    total_orders: int
    avg_algorithm_time_ms: float
    metrics: Dict[str, Any] = field(default_factory=dict)


class MultiAlgorithmOrchestrator:
    """Orchestrates multiple trading algorithms for concurrent execution and intelligent coordination."""
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        self.config = config or OrchestratorConfig()
        
        # Core components
        self.executor_config = ConcurrentExecutionConfig(
            max_workers=self.config.max_concurrent_algorithms,
            batch_window_ms=self.config.execution_batch_window_ms
        )
        self.executor = ConcurrentStrategyExecutor(self.executor_config)
        self.coordinator = IntelligentSignalCoordinator(self.executor)
        self.execution_pipeline = FastExecutionPipeline(
            batch_window_ms=self.config.execution_batch_window_ms
        )
        
        # Algorithm management
        self.algorithms: Dict[str, AlgorithmConfig] = {}
        self.adaptive_weights: Dict[str, float] = {}
        
        # Metrics and monitoring
        self.execution_history: List[ExecutionSummary] = []
        self.performance_metrics: Dict[str, List[float]] = {}
        self.algorithm_success_rates: Dict[str, float] = {}
        self.algorithm_win_rates: Dict[str, float] = {}
        
        self.lock = threading.Lock()
    
    def register_algorithm(
        self,
        name: str,
        func: Callable,
        weight: float = 1.0,
        enabled: bool = True,
        timeout_seconds: float = 5.0
    ) -> None:
        """Register a trading algorithm."""
        
        config = AlgorithmConfig(
            name=name,
            func=func,
            enabled=enabled,
            weight=weight,
            timeout_seconds=timeout_seconds
        )
        
        with self.lock:
            self.algorithms[name] = config
            self.adaptive_weights[name] = weight
            self.algorithm_success_rates[name] = 0.5
            self.algorithm_win_rates[name] = 0.5
        
        logger.info(f"Registered algorithm: {name} (weight={weight})")
    
    def register_algorithms(self, algorithms: Dict[str, AlgorithmConfig]) -> None:
        """Register multiple algorithms at once."""
        for name, config in algorithms.items():
            with self.lock:
                self.algorithms[name] = config
                self.adaptive_weights[name] = config.weight
                self.algorithm_success_rates[name] = 0.5
                self.algorithm_win_rates[name] = 0.5
            logger.info(f"Registered: {name}")
    
    @performance_tracked
    def execute_cycle(
        self,
        market_data: pd.DataFrame,
        symbols: List[str],
        current_prices: Dict[str, float],
        market_regime: str = "neutral",
        position_sizes: Optional[Dict[str, float]] = None
    ) -> Tuple[int, float, Dict]:
        """Execute full cycle: run all algorithms, coordinate signals, execute orders."""
        
        cycle_start = time.time()
        
        # Get enabled algorithms
        enabled_algos = {
            name: config.func
            for name, config in self.algorithms.items()
            if config.enabled
        }
        
        if not enabled_algos:
            logger.warning("No algorithms enabled")
            return 0, 0.0, {}
        
        logger.debug(f"Executing {len(enabled_algos)} algorithms")
        
        # Step 1: Execute all algorithms concurrently
        algorithm_results = self.executor.execute_strategies(
            enabled_algos,
            market_data,
            symbols
        )
        
        # Step 2: Filter by minimum confidence
        filtered_results = {
            name: result
            for name, result in algorithm_results.items()
            if result.confidence >= self.algorithms[name].min_confidence
        }
        
        num_signals = len(filtered_results)
        
        # Step 3: Get aggregation weights (adaptive or static)
        if self.config.enable_adaptive_weighting:
            weights = self.adaptive_weights.copy()
        else:
            weights = {
                name: config.weight
                for name, config in self.algorithms.items()
            }
        
        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {name: w / total_weight for name, w in weights.items()}
        
        # Step 4: Coordinate signals
        if self.config.enable_conflict_resolution:
            signals = {name: result.signal for name, result in filtered_results.items()}
            confidences = {name: result.confidence for name, result in filtered_results.items()}
            
            final_signal, final_confidence, coordination_metrics = self.coordinator.coordinate_signals(
                signals,
                confidences,
                market_regime=market_regime
            )
        else:
            final_signal, final_confidence, coordination_metrics = self.executor.aggregate_signals(
                filtered_results,
                weights
            )
        
        # Step 5: Create orders from signals
        algo_signals = {
            name: (result.signal, result.confidence)
            for name, result in filtered_results.items()
        }
        
        if algo_signals:
            self.execution_pipeline.add_signal_as_orders(
                algo_signals,
                current_prices,
                position_sizes
            )
        
        # Step 6: Create and execute batches
        batches = self.execution_pipeline.batcher.create_batch()
        
        if batches:
            execution_results = self.execution_pipeline.execute_batches_smart(batches)
        else:
            execution_results = {}
        
        # Step 7: Update adaptive weights based on recent performance
        if self.config.enable_adaptive_weighting:
            self._update_adaptive_weights(algorithm_results)
        
        # Build summary
        cycle_time = (time.time() - cycle_start) * 1000
        
        algorithm_times = [
            r.execution_time_ms for r in algorithm_results.values()
            if r.error is None
        ]
        
        summary = ExecutionSummary(
            timestamp=datetime.now(),
            num_algorithms=len(enabled_algos),
            num_signals_generated=num_signals,
            final_signal=final_signal,
            final_confidence=final_confidence,
            execution_time_ms=cycle_time,
            batches_created=len(batches),
            total_orders=sum(len(b.orders) for b in batches),
            avg_algorithm_time_ms=np.mean(algorithm_times) if algorithm_times else 0,
            metrics={
                "executor_stats": self.executor.get_execution_stats(),
                "pipeline_stats": self.execution_pipeline.get_pipeline_stats(),
                "coordination_metrics": coordination_metrics,
                "execution_results": execution_results
            }
        )
        
        with self.lock:
            self.execution_history.append(summary)
            if len(self.execution_history) > self.config.performance_history_size:
                self.execution_history.pop(0)
        
        logger.info(
            f"Cycle complete: {len(enabled_algos)} algos, {num_signals} signals, "
            f"signal={final_signal}, confidence={final_confidence:.2f}, "
            f"time={cycle_time:.1f}ms, batches={len(batches)}"
        )
        
        return final_signal, final_confidence, summary.metrics
    
    def _update_adaptive_weights(self, algorithm_results: Dict[str, StrategyResult]) -> None:
        """Update algorithm weights based on recent performance."""
        
        if not self.config.enable_adaptive_weighting:
            return
        
        # Look at recent execution history
        recent_cycles = self.execution_history[-100:] if self.execution_history else []
        
        if not recent_cycles:
            return
        
        # For each algorithm, track success (if signal + actual trade was profitable)
        for algo_name in algorithm_results.keys():
            # This is simplified - in production, track actual trade results
            result = algorithm_results[algo_name]
            
            if result.error is None:
                # Successful execution - increase weight
                success_boost = 0.01 * (result.confidence ** 2)  # Quadratic boost for confidence
            else:
                # Failed execution - decrease weight
                success_boost = -0.02
            
            # Update weight with momentum
            old_weight = self.adaptive_weights[algo_name]
            new_weight = old_weight * 0.95 + (old_weight + success_boost) * 0.05  # Exponential moving average
            
            # Keep weight between 0.5 and 2.0
            new_weight = max(0.5, min(2.0, new_weight))
            
            self.adaptive_weights[algo_name] = new_weight
    
    def enable_algorithm(self, name: str) -> None:
        """Enable an algorithm."""
        if name in self.algorithms:
            self.algorithms[name].enabled = True
            logger.info(f"Enabled algorithm: {name}")
    
    def disable_algorithm(self, name: str) -> None:
        """Disable an algorithm."""
        if name in self.algorithms:
            self.algorithms[name].enabled = False
            logger.info(f"Disabled algorithm: {name}")
    
    def set_algorithm_weight(self, name: str, weight: float) -> None:
        """Set algorithm weight."""
        if name in self.algorithms:
            with self.lock:
                self.adaptive_weights[name] = max(0, weight)
            logger.info(f"Set {name} weight to {weight}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get orchestrator status."""
        
        with self.lock:
            enabled = sum(1 for c in self.algorithms.values() if c.enabled)
            
            status = {
                "total_algorithms": len(self.algorithms),
                "enabled_algorithms": enabled,
                "algorithms": {
                    name: {
                        "enabled": config.enabled,
                        "weight": self.adaptive_weights[name],
                        "timeout_seconds": config.timeout_seconds,
                    }
                    for name, config in self.algorithms.items()
                },
                "execution_cycles": len(self.execution_history),
                "performance": {
                    "total_execution_time_ms": sum(
                        s.execution_time_ms for s in self.execution_history
                    ),
                    "avg_cycle_time_ms": np.mean(
                        [s.execution_time_ms for s in self.execution_history]
                    ) if self.execution_history else 0,
                    "fastest_cycle_ms": min(
                        [s.execution_time_ms for s in self.execution_history],
                        default=0
                    ),
                    "slowest_cycle_ms": max(
                        [s.execution_time_ms for s in self.execution_history],
                        default=0
                    ),
                }
            }
        
        return status
    
    def get_execution_history(self, limit: int = 50) -> List[Dict]:
        """Get execution history."""
        with self.lock:
            history = self.execution_history[-limit:] if self.execution_history else []
        
        return [
            {
                "timestamp": h.timestamp.isoformat(),
                "num_algorithms": h.num_algorithms,
                "num_signals": h.num_signals_generated,
                "signal": h.final_signal,
                "confidence": h.final_confidence,
                "execution_time_ms": h.execution_time_ms,
                "batches": h.batches_created,
                "orders": h.total_orders,
            }
            for h in history
        ]
    
    def shutdown(self) -> None:
        """Shutdown orchestrator."""
        self.executor.shutdown()
        logger.info("Orchestrator shutdown complete")


class FastAlgorithmExecutor:
    """Drop-in replacement for single algorithm - executes with orchestrator speed."""
    
    def __init__(self):
        self.orchestrator = MultiAlgorithmOrchestrator()
    
    def add_algorithm(self, name: str, func: Callable, weight: float = 1.0) -> None:
        """Add algorithm to executor."""
        self.orchestrator.register_algorithm(name, func, weight)
    
    def execute(
        self,
        market_data: pd.DataFrame,
        symbols: List[str],
        current_prices: Dict[str, float],
        market_regime: str = "neutral"
    ) -> Tuple[int, float, Dict]:
        """Execute all algorithms and return aggregated signal."""
        
        return self.orchestrator.execute_cycle(
            market_data,
            symbols,
            current_prices,
            market_regime
        )
