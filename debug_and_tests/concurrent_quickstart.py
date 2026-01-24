"""Quick start example - Concurrent multi-algorithm trading system."""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator, OrchestratorConfig


# Define your trading algorithms (can be from your existing strategy modules)

def strategy_atr_breakout(data: pd.DataFrame, symbols: list):
    """ATR-based breakout detection."""
    if len(data) < 14:
        return 0, 0.3, {}
    
    atr = (data['High'] - data['Low']).rolling(14).mean()
    current_atr = atr.iloc[-1]
    avg_atr = atr.mean()
    
    # Signal: breakout when ATR expands
    if current_atr > avg_atr * 1.2:
        # Check direction
        signal = 1 if data['Close'].iloc[-1] > data['Open'].iloc[-1] else -1
        confidence = min(current_atr / (avg_atr * 2), 1.0)
    else:
        signal = 0
        confidence = 0.2
    
    return signal, confidence, {"atr": float(current_atr), "avg_atr": float(avg_atr)}


def strategy_rsi_mean_reversion(data: pd.DataFrame, symbols: list):
    """RSI-based mean reversion strategy."""
    if len(data) < 14:
        return 0, 0.3, {}
    
    # Calculate RSI
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    current_rsi = rsi.iloc[-1]
    
    if current_rsi > 70:
        return -1, 0.85, {"rsi": float(current_rsi), "signal": "overbought"}
    elif current_rsi < 30:
        return 1, 0.85, {"rsi": float(current_rsi), "signal": "oversold"}
    else:
        return 0, 0.3, {"rsi": float(current_rsi), "signal": "neutral"}


def strategy_macd_momentum(data: pd.DataFrame, symbols: list):
    """MACD momentum strategy."""
    if len(data) < 26:
        return 0, 0.3, {}
    
    ema12 = data['Close'].ewm(span=12).mean()
    ema26 = data['Close'].ewm(span=26).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()
    
    histogram = macd - signal_line
    
    if histogram.iloc[-1] > 0:
        confidence = min(abs(histogram.iloc[-1]) / 5, 1.0)
        signal = 1
    else:
        confidence = min(abs(histogram.iloc[-1]) / 5, 1.0)
        signal = -1
    
    return signal, confidence, {
        "macd": float(macd.iloc[-1]),
        "histogram": float(histogram.iloc[-1])
    }


def strategy_bollinger_bands(data: pd.DataFrame, symbols: list):
    """Bollinger Bands mean reversion."""
    if len(data) < 20:
        return 0, 0.3, {}
    
    middle = data['Close'].rolling(20).mean()
    std = data['Close'].rolling(20).std()
    upper = middle + (std * 2)
    lower = middle - (std * 2)
    
    price = data['Close'].iloc[-1]
    bb_width = (upper - lower).iloc[-1]
    
    if price > upper.iloc[-1]:
        return -1, 0.75, {"position": "above_upper", "bb_width": float(bb_width)}
    elif price < lower.iloc[-1]:
        return 1, 0.75, {"position": "below_lower", "bb_width": float(bb_width)}
    else:
        return 0, 0.3, {"position": "inside_bands", "bb_width": float(bb_width)}


def create_sample_market_data():
    """Generate realistic sample market data."""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')
    
    # Generate realistic price movement
    base_price = 150
    returns = np.random.normal(0.0005, 0.015, 100)
    prices = base_price * np.exp(np.cumsum(returns))
    
    data = {
        'Open': prices + np.random.normal(0, 1, 100),
        'High': prices + abs(np.random.normal(1, 1, 100)),
        'Low': prices - abs(np.random.normal(1, 1, 100)),
        'Close': prices,
        'Volume': np.random.randint(1000000, 5000000, 100)
    }
    
    df = pd.DataFrame(data, index=dates)
    df['High'] = df[['Open', 'Close', 'High']].max(axis=1)
    df['Low'] = df[['Open', 'Close', 'Low']].min(axis=1)
    
    return df


def main():
    """Run concurrent multi-algorithm trading system."""
    
    print("\n" + "="*70)
    print("CONCURRENT MULTI-ALGORITHM TRADING SYSTEM - QUICK START")
    print("="*70)
    
    # Create orchestrator with optimal configuration
    config = OrchestratorConfig(
        max_concurrent_algorithms=8,
        execution_batch_window_ms=50,  # Ultra-fast 50ms batching
        enable_adaptive_weighting=True,  # Automatic weight adjustment
        enable_signal_batching=True,
        enable_conflict_resolution=True
    )
    
    orchestrator = MultiAlgorithmOrchestrator(config)
    
    # Register your trading algorithms
    print("\n📋 Registering trading algorithms:")
    
    algorithms = {
        "atr_breakout": (strategy_atr_breakout, 1.2),
        "rsi_mean_reversion": (strategy_rsi_mean_reversion, 1.0),
        "macd_momentum": (strategy_macd_momentum, 0.9),
        "bollinger_bands": (strategy_bollinger_bands, 1.1),
    }
    
    for name, (func, weight) in algorithms.items():
        orchestrator.register_algorithm(name, func, weight=weight)
        print(f"  ✓ {name:25s} (weight={weight})")
    
    # Load or create market data
    print("\n📊 Generating market data...")
    market_data = create_sample_market_data()
    print(f"  ✓ {len(market_data)} candles loaded")
    
    # Run trading cycles
    print("\n🚀 Running trading cycles (all algorithms execute concurrently):\n")
    
    symbols = ["AAPL"]
    current_prices = {"AAPL": market_data['Close'].iloc[-1]}
    
    for cycle in range(3):
        print(f"Cycle {cycle + 1}:")
        print(f"  Price: ${current_prices['AAPL']:.2f}")
        
        # Execute full cycle - all algorithms run in parallel
        signal, confidence, metrics = orchestrator.execute_cycle(
            market_data[-50:],  # Use last 50 candles
            symbols,
            current_prices,
            market_regime="trending"  # Could be: trending, ranging, volatile
        )
        
        print(f"  Signal: {signal:2d} | Confidence: {confidence:.2f}")
        print(f"  Execution: {metrics.get('execution_time_ms', 0):.1f}ms | "
              f"Orders: {metrics.get('total_orders', 0)}")
        
        # Simulate price movement
        current_prices['AAPL'] *= np.random.normal(1.001, 0.01)
        print()
    
    # Print orchestrator status
    print("📈 Orchestrator Status:")
    status = orchestrator.get_status()
    
    print(f"\n  Algorithms: {status['enabled_algorithms']}/{status['total_algorithms']} enabled")
    print(f"  Execution Cycles: {status['execution_cycles']}")
    print(f"  Avg Cycle Time: {status['performance']['avg_cycle_time_ms']:.1f}ms")
    print(f"  Min Cycle Time: {status['performance']['fastest_cycle_ms']:.1f}ms")
    print(f"  Max Cycle Time: {status['performance']['slowest_cycle_ms']:.1f}ms")
    
    # Print execution history
    print(f"\n📊 Execution History:")
    history = orchestrator.get_execution_history(limit=5)
    
    for i, h in enumerate(history, 1):
        signal_str = "BUY " if h['signal'] > 0 else "SELL" if h['signal'] < 0 else "HOLD"
        print(f"  {i}. {signal_str} (conf={h['confidence']:.2f}) | "
              f"Time={h['execution_time_ms']:.1f}ms | Orders={h['orders']}")
    
    # Demonstrate algorithm management
    print("\n⚙️ Algorithm Management:")
    
    # Disable an algorithm
    orchestrator.disable_algorithm("atr_breakout")
    print("  ✓ Disabled atr_breakout")
    
    # Change weights
    orchestrator.set_algorithm_weight("rsi_mean_reversion", 1.5)
    print("  ✓ Updated rsi_mean_reversion weight to 1.5")
    
    # Run another cycle with changes
    signal, confidence, metrics = orchestrator.execute_cycle(
        market_data[-50:],
        symbols,
        current_prices,
        market_regime="ranging"  # Different regime
    )
    
    print(f"\n  Result with changes: Signal={signal} | Confidence={confidence:.2f}")
    
    # Shutdown
    orchestrator.shutdown()
    print("\n✓ Orchestrator shutdown complete\n")


if __name__ == "__main__":
    main()
