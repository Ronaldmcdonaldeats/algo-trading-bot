"""Test and example usage of concurrent multi-algorithm execution system."""

import sys
import time
from pathlib import Path
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_bot.learn.concurrent_executor import (
    ConcurrentStrategyExecutor,
    ConcurrentExecutionConfig,
    IntelligentSignalCoordinator
)
from trading_bot.learn.fast_execution import SmartOrderBatcher, Order, OrderType, OrderPriority
from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator, OrchestratorConfig


def create_sample_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    data = {
        'Open': 100 + np.cumsum(np.random.randn(100) * 2),
        'High': 102 + np.cumsum(np.random.randn(100) * 2),
        'Low': 98 + np.cumsum(np.random.randn(100) * 2),
        'Close': 100 + np.cumsum(np.random.randn(100) * 2),
        'Volume': np.random.randint(1000000, 5000000, 100)
    }
    df = pd.DataFrame(data, index=dates)
    return df


def strategy_atr_breakout(data, symbols):
    """ATR breakout strategy."""
    atr = (data['High'] - data['Low']).rolling(14).mean()
    price_change = abs(data['Close'].iloc[-1] - data['Close'].iloc[-2])
    
    signal = 1 if price_change > atr.iloc[-1] else 0
    confidence = 0.85
    
    return signal, confidence, {"atr": float(atr.iloc[-1]), "price_change": float(price_change)}


def strategy_rsi_mean_reversion(data, symbols):
    """RSI mean reversion strategy."""
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    current_rsi = rsi.iloc[-1]
    
    if current_rsi > 70:
        signal = -1
        confidence = 0.80
    elif current_rsi < 30:
        signal = 1
        confidence = 0.80
    else:
        signal = 0
        confidence = 0.3
    
    return signal, confidence, {"rsi": float(current_rsi)}


def strategy_macd_momentum(data, symbols):
    """MACD momentum strategy."""
    ema12 = data['Close'].ewm(span=12).mean()
    ema26 = data['Close'].ewm(span=26).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()
    
    histogram = macd - signal_line
    
    signal = 1 if histogram.iloc[-1] > 0 else -1
    confidence = min(abs(float(histogram.iloc[-1])) / 2, 1.0)
    
    return signal, confidence, {"macd": float(macd.iloc[-1]), "histogram": float(histogram.iloc[-1])}


def strategy_bollinger_bands(data, symbols):
    """Bollinger bands mean reversion strategy."""
    middle = data['Close'].rolling(20).mean()
    std = data['Close'].rolling(20).std()
    upper = middle + (std * 2)
    lower = middle - (std * 2)
    
    price = data['Close'].iloc[-1]
    
    if price > upper.iloc[-1]:
        signal = -1
        confidence = 0.75
    elif price < lower.iloc[-1]:
        signal = 1
        confidence = 0.75
    else:
        signal = 0
        confidence = 0.2
    
    return signal, confidence, {"bb_width": float((upper - lower).iloc[-1])}


def strategy_volume_momentum(data, symbols):
    """Volume-weighted momentum strategy."""
    vol_ma = data['Volume'].rolling(20).mean()
    vol_ratio = data['Volume'].iloc[-1] / vol_ma.iloc[-1]
    
    if vol_ratio > 1.5:
        signal = 1 if data['Close'].iloc[-1] > data['Open'].iloc[-1] else -1
        confidence = 0.75
    else:
        signal = 0
        confidence = 0.3
    
    return signal, confidence, {"volume_ratio": float(vol_ratio)}


def test_concurrent_executor():
    """Test 1: Concurrent Strategy Executor."""
    print("\n" + "="*70)
    print("TEST 1: CONCURRENT STRATEGY EXECUTOR")
    print("="*70)
    
    data = create_sample_data()
    symbols = ["AAPL"]
    
    config = ConcurrentExecutionConfig(
        max_workers=4,
        timeout_seconds=5.0,
        enable_caching=True
    )
    
    executor = ConcurrentStrategyExecutor(config)
    
    strategies = {
        "atr_breakout": strategy_atr_breakout,
        "rsi_mean_reversion": strategy_rsi_mean_reversion,
        "macd_momentum": strategy_macd_momentum,
        "bollinger_bands": strategy_bollinger_bands,
    }
    
    start = time.time()
    results = executor.execute_strategies(strategies, data, symbols)
    elapsed_ms = (time.time() - start) * 1000
    
    print(f"\n✓ Executed {len(results)} strategies concurrently in {elapsed_ms:.1f}ms")
    
    for name, result in results.items():
        status = "✓" if result.error is None else "✗"
        print(f"  {status} {name:25s} | Signal: {result.signal:2d} | Confidence: {result.confidence:.2f} | Time: {result.execution_time_ms:.1f}ms")
    
    # Test caching
    print(f"\nCache Stats:")
    cache_stats = executor.cache.get_stats()
    print(f"  Hits: {cache_stats['hits']}, Misses: {cache_stats['misses']}, Hit Rate: {cache_stats['hit_rate']:.1%}")
    
    # Test execution again (should use cache)
    start = time.time()
    results2 = executor.execute_strategies(strategies, data, symbols)
    elapsed_ms2 = (time.time() - start) * 1000
    
    print(f"\nSecond execution (with caching) in {elapsed_ms2:.1f}ms")
    
    executor.shutdown()
    return True


def test_signal_coordination():
    """Test 2: Intelligent Signal Coordination."""
    print("\n" + "="*70)
    print("TEST 2: INTELLIGENT SIGNAL COORDINATION")
    print("="*70)
    
    data = create_sample_data()
    symbols = ["AAPL"]
    
    executor = ConcurrentStrategyExecutor()
    coordinator = IntelligentSignalCoordinator(executor)
    
    # Simulate different signal scenarios
    scenarios = [
        {
            "name": "Strong Bullish Consensus",
            "signals": {"algo1": 1, "algo2": 1, "algo3": 1, "algo4": -1},
            "confidences": {"algo1": 0.9, "algo2": 0.85, "algo3": 0.8, "algo4": 0.3},
            "regime": "trending"
        },
        {
            "name": "Weak Mixed Signals",
            "signals": {"algo1": 1, "algo2": -1, "algo3": 0, "algo4": 1},
            "confidences": {"algo1": 0.6, "algo2": 0.5, "algo3": 0.2, "algo4": 0.4},
            "regime": "ranging"
        },
        {
            "name": "Bearish with High Confidence",
            "signals": {"algo1": -1, "algo2": -1, "algo3": -1},
            "confidences": {"algo1": 0.95, "algo2": 0.9, "algo3": 0.88},
            "regime": "volatile"
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{scenario['name']} ({scenario['regime']}):")
        print(f"  Signals: {scenario['signals']}")
        print(f"  Confidences: {scenario['confidences']}")
        
        signal, confidence, metrics = coordinator.coordinate_signals(
            scenario['signals'],
            scenario['confidences'],
            market_regime=scenario['regime']
        )
        
        print(f"  → Final Signal: {signal:2d} | Confidence: {confidence:.2f}")
        print(f"  → Bull Agreement: {metrics['bull_agreement']:.2f} | Bear Agreement: {metrics['bear_agreement']:.2f}")
    
    executor.shutdown()
    return True


def test_smart_batching():
    """Test 3: Smart Order Batching."""
    print("\n" + "="*70)
    print("TEST 3: SMART ORDER BATCHING")
    print("="*70)
    
    batcher = SmartOrderBatcher(batch_window_ms=100, max_batch_size=10)
    
    # Add orders
    print(f"\nAdding 15 orders...")
    
    for i in range(15):
        order = Order(
            symbol="AAPL" if i % 2 == 0 else "MSFT",
            type=OrderType.BUY if i % 3 == 0 else OrderType.SELL,
            quantity=100 + i*10,
            signal_confidence=0.5 + (i % 10) * 0.05,
            priority=OrderPriority.CRITICAL if i == 0 else OrderPriority.NORMAL,
            strategy_source=f"strategy_{i % 3}"
        )
        batcher.add_order(order)
    
    print(f"  Pending orders: {len(batcher.pending_orders)}")
    print(f"  Should batch: {batcher.should_batch()}")
    
    # Create batches
    batches = batcher.create_batch()
    print(f"\n✓ Created {len(batches)} batches")
    
    for batch in batches:
        print(f"\n  Symbol: {batch.symbol}")
        print(f"    Orders: {len(batch.orders)}")
        print(f"    Total Quantity: {batch.total_quantity:.0f}")
        print(f"    Avg Confidence: {batch.avg_confidence:.2f}")
        direction, qty = batch.get_net_position()
        print(f"    Net Position: {direction} {qty:.0f}")
    
    stats = batcher.get_batch_stats()
    print(f"\nBatcher Stats:")
    print(f"  Total Batches: {stats['total_batches_created']}")
    print(f"  Pending Orders: {stats['pending_orders']}")
    
    return True


def test_orchestrator():
    """Test 4: Multi-Algorithm Orchestrator."""
    print("\n" + "="*70)
    print("TEST 4: MULTI-ALGORITHM ORCHESTRATOR")
    print("="*70)
    
    data = create_sample_data()
    symbols = ["AAPL"]
    current_prices = {"AAPL": 150.25}
    
    # Create orchestrator
    config = OrchestratorConfig(
        max_concurrent_algorithms=5,
        execution_batch_window_ms=50,
        enable_adaptive_weighting=True
    )
    
    orchestrator = MultiAlgorithmOrchestrator(config)
    
    # Register algorithms
    print(f"\nRegistering algorithms:")
    orchestrator.register_algorithm("atr_breakout", strategy_atr_breakout, weight=1.2)
    print(f"  ✓ atr_breakout (weight=1.2)")
    
    orchestrator.register_algorithm("rsi_mean_reversion", strategy_rsi_mean_reversion, weight=1.0)
    print(f"  ✓ rsi_mean_reversion (weight=1.0)")
    
    orchestrator.register_algorithm("macd_momentum", strategy_macd_momentum, weight=0.9)
    print(f"  ✓ macd_momentum (weight=0.9)")
    
    orchestrator.register_algorithm("bollinger_bands", strategy_bollinger_bands, weight=1.1)
    print(f"  ✓ bollinger_bands (weight=1.1)")
    
    orchestrator.register_algorithm("volume_momentum", strategy_volume_momentum, weight=0.8)
    print(f"  ✓ volume_momentum (weight=0.8)")
    
    # Execute multiple cycles to test performance
    print(f"\nExecuting 5 trading cycles:")
    cycle_times = []
    
    for cycle in range(5):
        start = time.time()
        
        signal, confidence, metrics = orchestrator.execute_cycle(
            data,
            symbols,
            current_prices,
            market_regime="trending"
        )
        
        elapsed_ms = (time.time() - start) * 1000
        cycle_times.append(elapsed_ms)
        
        print(f"  Cycle {cycle+1}: Signal={signal:2d} | Confidence={confidence:.2f} | Time={elapsed_ms:.1f}ms | Orders={metrics.get('total_orders', 0)}")
    
    # Print summary
    avg_time = np.mean(cycle_times)
    min_time = np.min(cycle_times)
    max_time = np.max(cycle_times)
    
    print(f"\nExecution Summary:")
    print(f"  Average Cycle Time: {avg_time:.1f}ms")
    print(f"  Min Cycle Time: {min_time:.1f}ms")
    print(f"  Max Cycle Time: {max_time:.1f}ms")
    
    # Get status
    status = orchestrator.get_status()
    print(f"\nOrchestrator Status:")
    print(f"  Total Algorithms: {status['total_algorithms']}")
    print(f"  Enabled: {status['enabled_algorithms']}")
    print(f"  Total Execution Cycles: {status['execution_cycles']}")
    print(f"  Overall Avg Cycle Time: {status['performance']['avg_cycle_time_ms']:.1f}ms")
    
    # Get execution history
    history = orchestrator.get_execution_history(limit=3)
    print(f"\nRecent Execution History:")
    for h in history:
        print(f"  {h['timestamp']} | Signal={h['signal']:2d} | Confidence={h['confidence']:.2f} | Time={h['execution_time_ms']:.1f}ms")
    
    orchestrator.shutdown()
    return True


def test_concurrent_vs_sequential():
    """Test 5: Speed comparison (concurrent vs sequential)."""
    print("\n" + "="*70)
    print("TEST 5: CONCURRENT VS SEQUENTIAL COMPARISON")
    print("="*70)
    
    data = create_sample_data()
    symbols = ["AAPL"]
    
    strategies = {
        "atr_breakout": strategy_atr_breakout,
        "rsi_mean_reversion": strategy_rsi_mean_reversion,
        "macd_momentum": strategy_macd_momentum,
        "bollinger_bands": strategy_bollinger_bands,
        "volume_momentum": strategy_volume_momentum,
    }
    
    # Sequential execution
    print("\nSequential Execution:")
    start = time.time()
    for name, func in strategies.items():
        func(data, symbols)
    sequential_time = (time.time() - start) * 1000
    print(f"  Time: {sequential_time:.1f}ms")
    
    # Concurrent execution
    print("\nConcurrent Execution:")
    config = ConcurrentExecutionConfig(max_workers=5)
    executor = ConcurrentStrategyExecutor(config)
    
    start = time.time()
    executor.execute_strategies(strategies, data, symbols)
    concurrent_time = (time.time() - start) * 1000
    print(f"  Time: {concurrent_time:.1f}ms")
    
    speedup = sequential_time / concurrent_time
    print(f"\nSpeedup: {speedup:.2f}x faster")
    print(f"Time Saved: {sequential_time - concurrent_time:.1f}ms ({(1 - concurrent_time/sequential_time)*100:.1f}%)")
    
    executor.shutdown()
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "█"*70)
    print("█  CONCURRENT MULTI-ALGORITHM EXECUTION SYSTEM - TEST SUITE")
    print("█"*70)
    
    tests = [
        ("Concurrent Executor", test_concurrent_executor),
        ("Signal Coordination", test_signal_coordination),
        ("Smart Batching", test_smart_batching),
        ("Multi-Algorithm Orchestrator", test_orchestrator),
        ("Concurrent vs Sequential", test_concurrent_vs_sequential),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "PASS" if result else "FAIL"))
        except Exception as e:
            print(f"\n✗ TEST FAILED: {e}")
            results.append((name, "FAIL"))
    
    # Print summary
    print("\n" + "█"*70)
    print("█  TEST SUMMARY")
    print("█"*70)
    
    for name, status in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name:40s} | {status}")
    
    passed = sum(1 for _, status in results if status == "PASS")
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    print("\n" + "█"*70)
    
    return all(status == "PASS" for _, status in results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
