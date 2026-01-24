"""Concurrent multi-strategy executor - runs multiple trading algorithms simultaneously with intelligent coordination."""

from __future__ import annotations

import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Callable, Any
from datetime import datetime
from enum import Enum
import numpy as np
import pandas as pd
from functools import lru_cache
import threading

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Strategy execution mode."""
    THREADED = "threaded"      # Thread pool (I/O bound)
    PROCESS = "process"        # Process pool (CPU bound)
    ASYNC = "async"            # Async/await (high concurrency)
    HYBRID = "hybrid"          # Mix of threads and processes


@dataclass
class StrategyResult:
    """Result from strategy execution."""
    strategy_name: str
    signal: int  # -1, 0, 1
    confidence: float  # 0-1
    execution_time_ms: float
    metrics: Dict[str, float] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConcurrentExecutionConfig:
    """Configuration for concurrent execution."""
    max_workers: int = 6
    max_workers_per_strategy: int = 2
    execution_mode: ExecutionMode = ExecutionMode.THREADED
    timeout_seconds: float = 5.0
    enable_caching: bool = True
    cache_ttl_seconds: float = 60.0
    batch_orders: bool = True
    batch_window_ms: int = 100  # Wait up to 100ms to batch signals
    use_process_pool: bool = False  # Use processes for CPU-intensive strategies


class CalculationCache:
    """LRU cache for expensive calculations (indicators, etc)."""
    
    def __init__(self, maxsize: int = 128):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self.lock = threading.Lock()
    
    def get(self, key: str, ttl_seconds: float = 60.0) -> Optional[Any]:
        """Get cached value if not expired."""
        with self.lock:
            if key in self.cache:
                value, timestamp = self.cache[key]
                if time.time() - timestamp < ttl_seconds:
                    self.hits += 1
                    return value
                else:
                    del self.cache[key]
            self.misses += 1
            return None
    
    def set(self, key: str, value: Any) -> None:
        """Set cache value."""
        with self.lock:
            if len(self.cache) >= self.maxsize:
                # Remove oldest entry
                oldest_key = min(self.cache.keys(), 
                               key=lambda k: self.cache[k][1])
                del self.cache[oldest_key]
            
            self.cache[key] = (value, time.time())
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "size": len(self.cache)
        }


class ConcurrentStrategyExecutor:
    """Execute multiple strategies concurrently with intelligent coordination."""
    
    def __init__(self, config: Optional[ConcurrentExecutionConfig] = None):
        self.config = config or ConcurrentExecutionConfig()
        self.thread_executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self.process_executor = None
        if self.config.use_process_pool:
            self.process_executor = ProcessPoolExecutor(max_workers=max(1, self.config.max_workers // 2))
        
        self.cache = CalculationCache(maxsize=256)
        self.signal_buffer: List[StrategyResult] = []
        self.buffer_lock = threading.Lock()
        self.last_signal_time = 0.0
        self.strategy_results: Dict[str, StrategyResult] = {}
    
    def execute_strategies(
        self,
        strategies: Dict[str, Callable],
        market_data: pd.DataFrame,
        symbols: List[str]
    ) -> Dict[str, StrategyResult]:
        """Execute multiple strategies concurrently."""
        
        futures = {}
        results = {}
        
        # Submit all strategies
        for strategy_name, strategy_func in strategies.items():
            future = self.thread_executor.submit(
                self._execute_single_strategy,
                strategy_name,
                strategy_func,
                market_data,
                symbols
            )
            futures[strategy_name] = future
        
        # Collect results
        for strategy_name, future in futures.items():
            try:
                result = future.result(timeout=self.config.timeout_seconds)
                results[strategy_name] = result
                self.strategy_results[strategy_name] = result
            except asyncio.TimeoutError:
                logger.warning(f"Strategy {strategy_name} timed out after {self.config.timeout_seconds}s")
                results[strategy_name] = StrategyResult(
                    strategy_name=strategy_name,
                    signal=0,
                    confidence=0.0,
                    execution_time_ms=self.config.timeout_seconds * 1000,
                    error="timeout"
                )
            except Exception as e:
                logger.error(f"Strategy {strategy_name} failed: {e}")
                results[strategy_name] = StrategyResult(
                    strategy_name=strategy_name,
                    signal=0,
                    confidence=0.0,
                    execution_time_ms=0.0,
                    error=str(e)
                )
        
        return results
    
    def _execute_single_strategy(
        self,
        strategy_name: str,
        strategy_func: Callable,
        market_data: pd.DataFrame,
        symbols: List[str]
    ) -> StrategyResult:
        """Execute a single strategy with caching."""
        start_time = time.time()
        
        # Check cache - use data shape and sum as key to avoid unhashable types
        data_hash = hash((market_data.shape, market_data['Close'].sum(), tuple(symbols)))
        cache_key = f"{strategy_name}_{data_hash}"
        
        if self.config.enable_caching:
            cached = self.cache.get(cache_key, self.config.cache_ttl_seconds)
            if cached is not None:
                logger.debug(f"{strategy_name}: Cache hit")
                return cached
        
        # Execute strategy
        try:
            signal, confidence, metrics = strategy_func(market_data, symbols)
            
            execution_time = (time.time() - start_time) * 1000
            
            result = StrategyResult(
                strategy_name=strategy_name,
                signal=int(signal),
                confidence=float(confidence),
                execution_time_ms=execution_time,
                metrics=metrics or {}
            )
            
            # Cache result
            if self.config.enable_caching:
                self.cache.set(cache_key, result)
            
            return result
        
        except Exception as e:
            logger.error(f"Strategy {strategy_name} execution failed: {e}")
            return StrategyResult(
                strategy_name=strategy_name,
                signal=0,
                confidence=0.0,
                execution_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    def aggregate_signals(
        self,
        results: Dict[str, StrategyResult],
        weights: Optional[Dict[str, float]] = None
    ) -> Tuple[int, float, Dict]:
        """Intelligently aggregate signals from multiple strategies."""
        
        if not results:
            return 0, 0.0, {}
        
        # Use provided weights or equal weight
        if weights is None:
            weights = {name: 1.0 / len(results) for name in results.keys()}
        
        # Weighted voting
        weighted_signal = 0.0
        weighted_confidence = 0.0
        total_weight = 0.0
        
        valid_results = []
        
        for strategy_name, result in results.items():
            if result.error is not None:
                continue  # Skip failed strategies
            
            weight = weights.get(strategy_name, 0.0)
            
            weighted_signal += weight * result.signal * result.confidence
            weighted_confidence += weight * result.confidence
            total_weight += weight
            
            valid_results.append(result)
        
        if total_weight > 0:
            weighted_confidence /= total_weight
        
        # Convert to final signal
        final_signal = 1 if weighted_signal >= 0.3 else (-1 if weighted_signal <= -0.3 else 0)
        
        # Build aggregation metrics
        metrics = {
            "consensus_strength": abs(weighted_signal),
            "valid_strategies": len(valid_results),
            "execution_times_ms": [r.execution_time_ms for r in valid_results],
            "avg_execution_time_ms": np.mean([r.execution_time_ms for r in valid_results]) if valid_results else 0,
            "max_execution_time_ms": np.max([r.execution_time_ms for r in valid_results]) if valid_results else 0,
        }
        
        return final_signal, weighted_confidence, metrics
    
    def buffer_and_batch_signals(
        self,
        results: Dict[str, StrategyResult],
        weights: Optional[Dict[str, float]] = None
    ) -> Optional[Tuple[int, float, Dict]]:
        """Buffer signals to batch them and reduce execution frequency."""
        
        if not self.config.batch_orders:
            return self.aggregate_signals(results, weights)
        
        with self.buffer_lock:
            self.signal_buffer.extend(results.values())
            current_time = time.time() * 1000
            
            # Check if we should flush buffer
            time_since_last = current_time - self.last_signal_time
            
            if time_since_last < self.config.batch_window_ms and len(self.signal_buffer) < len(results) * 2:
                logger.debug(f"Buffering signals: {len(self.signal_buffer)} buffered, {time_since_last:.0f}ms since last")
                return None  # Wait for more signals to batch
            
            # Flush buffer
            self.last_signal_time = current_time
            buffer_to_process = dict((r.strategy_name, r) for r in self.signal_buffer)
            self.signal_buffer.clear()
        
        return self.aggregate_signals(buffer_to_process, weights)
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get statistics on execution performance."""
        execution_times = [r.execution_time_ms for r in self.strategy_results.values() if r.error is None]
        
        stats = {
            "total_strategies": len(self.strategy_results),
            "successful_executions": sum(1 for r in self.strategy_results.values() if r.error is None),
            "failed_executions": sum(1 for r in self.strategy_results.values() if r.error is not None),
            "avg_execution_time_ms": np.mean(execution_times) if execution_times else 0,
            "min_execution_time_ms": np.min(execution_times) if execution_times else 0,
            "max_execution_time_ms": np.max(execution_times) if execution_times else 0,
            "cache_stats": self.cache.get_stats(),
        }
        
        return stats
    
    def shutdown(self) -> None:
        """Shutdown executor pools."""
        self.thread_executor.shutdown(wait=True)
        if self.process_executor:
            self.process_executor.shutdown(wait=True)


class IntelligentSignalCoordinator:
    """Coordinates multiple signal sources with intelligent routing and conflict resolution."""
    
    def __init__(self, executor: ConcurrentStrategyExecutor):
        self.executor = executor
        self.signal_history: List[Tuple[datetime, int, float]] = []
        self.max_history = 100
    
    def coordinate_signals(
        self,
        signals: Dict[str, int],
        confidences: Dict[str, float],
        market_regime: str = "neutral"
    ) -> Tuple[int, float, Dict]:
        """Intelligently coordinate multiple signals considering market regime."""
        
        if not signals:
            return 0, 0.0, {}
        
        # Regime-specific handling
        regime_adjustments = {
            "trending": {"multiplier": 1.2, "min_agreement": 0.4},
            "ranging": {"multiplier": 0.9, "min_agreement": 0.5},
            "volatile": {"multiplier": 0.8, "min_agreement": 0.6},
        }
        
        adjustment = regime_adjustments.get(market_regime, {"multiplier": 1.0, "min_agreement": 0.5})
        
        # Calculate agreement level
        bullish_signals = sum(1 for s in signals.values() if s > 0)
        bearish_signals = sum(1 for s in signals.values() if s < 0)
        neutral_signals = sum(1 for s in signals.values() if s == 0)
        
        total = len(signals)
        bull_agreement = bullish_signals / total if total > 0 else 0
        bear_agreement = bearish_signals / total if total > 0 else 0
        
        # Weighted signal
        weighted_signal = 0.0
        for name, signal in signals.items():
            conf = confidences.get(name, 0.5)
            weighted_signal += signal * conf
        
        weighted_signal *= adjustment["multiplier"]
        
        # Apply agreement threshold
        if bull_agreement >= adjustment["min_agreement"]:
            final_signal = 1
            confidence = bull_agreement
        elif bear_agreement >= adjustment["min_agreement"]:
            final_signal = -1
            confidence = bear_agreement
        else:
            final_signal = 0
            confidence = 0.0
        
        # Record in history
        self.signal_history.append((datetime.now(), final_signal, confidence))
        if len(self.signal_history) > self.max_history:
            self.signal_history.pop(0)
        
        return final_signal, confidence, {
            "bull_agreement": float(bull_agreement),
            "bear_agreement": float(bear_agreement),
            "regime": market_regime,
            "adjustment_multiplier": adjustment["multiplier"]
        }
    
    def detect_signal_conflicts(self, signals: Dict[str, int]) -> Dict[str, List[str]]:
        """Detect conflicting signals between strategies."""
        conflicts = {
            "bullish_vs_bearish": [],
            "agreement_rate": 0.0
        }
        
        if not signals:
            return conflicts
        
        bullish = [name for name, sig in signals.items() if sig > 0]
        bearish = [name for name, sig in signals.items() if sig < 0]
        
        if bullish and bearish:
            conflicts["bullish_vs_bearish"] = {
                "bullish": bullish,
                "bearish": bearish
            }
        
        total = len(signals)
        max_agreement = max(len(bullish), len(bearish), total - len(bullish) - len(bearish))
        conflicts["agreement_rate"] = max_agreement / total if total > 0 else 0
        
        return conflicts
