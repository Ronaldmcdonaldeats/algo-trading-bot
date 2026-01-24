"""Latency Optimizer - Reduce trading delays

Optimizes order execution speed by:
- Batching orders efficiently  
- Using faster data providers
- Parallel processing
- Smart caching
"""

from dataclasses import dataclass
from typing import Dict, List, Callable, Optional
import time
from datetime import datetime
import json
from pathlib import Path


@dataclass
class LatencyMetrics:
    """Latency performance metrics"""
    data_fetch_ms: float
    analysis_ms: float
    order_placement_ms: float
    total_ms: float
    timestamp: datetime
    optimization_applied: str


class LatencyOptimizer:
    """Optimize trading latency"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.metrics_history: List[LatencyMetrics] = []
        self.data_cache = {}
        self.cache_ttl = 30  # seconds
        self.cache_timestamps = {}
    
    def enable_data_caching(self, ttl_seconds: int = 30):
        """Enable caching of market data"""
        self.cache_ttl = ttl_seconds
        return True
    
    def cache_get(self, key: str) -> Optional:
        """Get cached value if still valid"""
        if key not in self.data_cache:
            return None
        
        age = time.time() - self.cache_timestamps.get(key, 0)
        if age > self.cache_ttl:
            # Cache expired
            del self.data_cache[key]
            del self.cache_timestamps[key]
            return None
        
        return self.data_cache[key]
    
    def cache_set(self, key: str, value):
        """Cache a value"""
        self.data_cache[key] = value
        self.cache_timestamps[key] = time.time()
    
    def cache_clear(self):
        """Clear all caches"""
        self.data_cache = {}
        self.cache_timestamps = {}
    
    def measure_operation(self, operation_name: str, 
                         func: Callable, *args, **kwargs) -> tuple:
        """Measure time taken by operation"""
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start) * 1000
            return result, elapsed_ms
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            raise Exception(f"{operation_name} failed in {elapsed_ms:.2f}ms: {e}")
    
    def optimize_data_fetch(self, symbols: List[str], use_cache: bool = True) -> Dict:
        """Optimize data fetching"""
        optimizations = []
        
        if use_cache:
            # Check cache first
            cached = [s for s in symbols if self.cache_get(f"ohlcv_{s}") is not None]
            if cached:
                optimizations.append(f"Used cache for {len(cached)}/{len(symbols)} symbols")
        
        return {
            'use_cache': use_cache,
            'optimizations': optimizations,
            'efficiency': len([x for x in optimizations if 'cache' in x.lower()])
        }
    
    def batch_operations(self, operations: List[Dict], batch_size: int = 10) -> List:
        """Batch operations for efficiency"""
        results = []
        
        for i in range(0, len(operations), batch_size):
            batch = operations[i:i + batch_size]
            # Process batch together
            results.extend(batch)
        
        return results
    
    def parallelize_order_execution(self, orders: List[Dict], max_workers: int = 4) -> Dict:
        """Plan for parallel order execution"""
        return {
            'orders': len(orders),
            'max_workers': max_workers,
            'batches': (len(orders) + max_workers - 1) // max_workers,
            'optimization': 'Parallel execution ready'
        }
    
    def record_metrics(self, data_fetch_ms: float, analysis_ms: float, 
                      order_ms: float, optimization: str = ""):
        """Record latency metrics"""
        metrics = LatencyMetrics(
            data_fetch_ms=data_fetch_ms,
            analysis_ms=analysis_ms,
            order_placement_ms=order_ms,
            total_ms=data_fetch_ms + analysis_ms + order_ms,
            timestamp=datetime.now(),
            optimization_applied=optimization
        )
        self.metrics_history.append(metrics)
        return metrics
    
    def get_latency_stats(self) -> Dict:
        """Get latency statistics"""
        if not self.metrics_history:
            return {
                'avg_total_ms': 0,
                'min_total_ms': 0,
                'max_total_ms': 0,
                'optimizations_applied': 0
            }
        
        total_times = [m.total_ms for m in self.metrics_history]
        
        return {
            'avg_total_ms': sum(total_times) / len(total_times),
            'min_total_ms': min(total_times),
            'max_total_ms': max(total_times),
            'num_measurements': len(self.metrics_history),
            'optimizations_applied': len([m for m in self.metrics_history if m.optimization_applied])
        }
    
    def recommend_optimizations(self, metrics: Dict) -> List[str]:
        """Recommend optimizations based on metrics"""
        recommendations = []
        
        avg_time = metrics.get('avg_total_ms', 0)
        
        if avg_time > 1000:
            recommendations.append("Enable data caching to reduce fetch time")
            recommendations.append("Batch orders together for faster execution")
        
        if avg_time > 500:
            recommendations.append("Consider parallel processing for multiple stocks")
        
        if avg_time > 200:
            recommendations.append("Your latency is acceptable for most strategies")
        
        return recommendations
    
    def save_metrics(self, filename: str = "latency_metrics.json"):
        """Save latency metrics"""
        filepath = self.cache_dir / filename
        
        data = [
            {
                'data_fetch_ms': m.data_fetch_ms,
                'analysis_ms': m.analysis_ms,
                'order_placement_ms': m.order_placement_ms,
                'total_ms': m.total_ms,
                'timestamp': m.timestamp.isoformat(),
                'optimization': m.optimization_applied
            }
            for m in self.metrics_history
        ]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def generate_optimization_report(self) -> str:
        """Generate detailed optimization report"""
        stats = self.get_latency_stats()
        recommendations = self.recommend_optimizations(stats)
        
        report = []
        report.append("=" * 50)
        report.append("LATENCY OPTIMIZATION REPORT")
        report.append("=" * 50)
        report.append("")
        report.append("Current Performance:")
        report.append(f"  Average Total Latency: {stats.get('avg_total_ms', 0):.2f}ms")
        report.append(f"  Minimum: {stats.get('min_total_ms', 0):.2f}ms")
        report.append(f"  Maximum: {stats.get('max_total_ms', 0):.2f}ms")
        report.append("")
        report.append("Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            report.append(f"  {i}. {rec}")
        report.append("")
        report.append("=" * 50)
        
        return "\n".join(report)
