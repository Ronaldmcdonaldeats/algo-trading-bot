# Integration

Integrate the trading bot into your existing systems.

---

## Using the Orchestrator

The `MultiAlgorithmOrchestrator` is the main entry point.

```python
from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator

# Initialize
orchestrator = MultiAlgorithmOrchestrator(max_history=1000)

# Register algorithms
orchestrator.register_algorithm(
    "atr", 
    atr_algorithm_function,
    weight=1.2
)

# Run a trading cycle
signal, confidence, metrics = orchestrator.execute_cycle(
    market_data=df,
    symbols=["AAPL"],
    current_prices={"AAPL": 150.25},
    market_regime="trending"
)

print(f"Signal: {signal}")  # "BUY", "SELL", or "HOLD"
print(f"Confidence: {confidence:.2%}")
```

---

## Custom Algorithm

Create your own algorithm:

```python
def my_algorithm(data, symbol, current_price, **kwargs):
    """
    Args:
        data: DataFrame with OHLCV
        symbol: Stock symbol
        current_price: Current market price
    
    Returns:
        signal: "BUY", "SELL", or "HOLD"
        strength: 0.0-1.0 confidence
        indicators: dict of indicator values
    """
    if some_condition:
        return "BUY", 0.85, {"indicator": value}
    return "HOLD", 0.5, {}

# Register it
orchestrator.register_algorithm("my_algo", my_algorithm, weight=1.0)
```

---

## Integration Scenarios

### Existing Trading System

```python
class MyTradingSystem:
    def __init__(self):
        self.orchestrator = MultiAlgorithmOrchestrator()
    
    def run_strategy(self, market_data):
        signal, confidence, _ = self.orchestrator.execute_cycle(
            market_data=market_data,
            symbols=self.symbols
        )
        
        if signal == "BUY" and confidence > 0.7:
            self.place_buy_order()
```

### Multi-Account Management

```python
class MultiAccountManager:
    def __init__(self):
        self.accounts = {
            "paper": PaperBroker(capital=100000),
            "live": AlpacaBroker(api_key="...")
        }
        self.orchestrator = MultiAlgorithmOrchestrator()
    
    def execute_all(self, market_data):
        signal, _, _ = self.orchestrator.execute_cycle(...)
        
        for account_name, broker in self.accounts.items():
            broker.place_order(symbol, quantity, signal)
```

### REST API

```python
from fastapi import FastAPI
from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator

app = FastAPI()
orchestrator = MultiAlgorithmOrchestrator()

@app.get("/signal/{symbol}")
def get_signal(symbol: str):
    signal, confidence, _ = orchestrator.execute_cycle(...)
    return {
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence
    }
```

---

## Parallel Execution

```python
from trading_bot.learn.concurrent_executor import ConcurrentStrategyExecutor

executor = ConcurrentStrategyExecutor(max_workers=4)

# Run multiple strategies in parallel
results = executor.execute([
    ("atr", atr_func, df, "AAPL"),
    ("rsi", rsi_func, df, "AAPL"),
    ("macd", macd_func, df, "AAPL"),
])
```

---

## Performance Optimization

### Calculation Caching

```python
from trading_bot.learn.concurrent_executor import CalculationCache

cache = CalculationCache(max_size=256, ttl_seconds=60)

# Expensive calculation (cached)
key = f"{symbol}_{timestamp}"
if key not in cache:
    result = expensive_calculation(data)
    cache.set(key, result)
else:
    result = cache.get(key)
```

---

## Testing

```python
import pytest
from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator

def test_orchestrator():
    orchestrator = MultiAlgorithmOrchestrator()
    
    def dummy_algo(data, symbol, price, **kwargs):
        return "BUY", 0.8, {}
    
    orchestrator.register_algorithm("test", dummy_algo)
    
    signal, confidence, _ = orchestrator.execute_cycle(
        market_data=test_data,
        symbols=["TEST"]
    )
    
    assert signal == "BUY"
    assert confidence > 0.5
```

---

## API Reference

### Orchestrator

```python
orchestrator = MultiAlgorithmOrchestrator()

# Register algorithm
orchestrator.register_algorithm(
    name="atr",
    func=atr_func,
    weight=1.2
)

# Execute cycle
signal, confidence, metrics = orchestrator.execute_cycle(
    market_data=df,
    symbols=["AAPL"],
    current_prices={"AAPL": 150.25},
    market_regime="trending"
)

# Get metrics
print(orchestrator.win_rate)
print(orchestrator.avg_execution_time)
print(orchestrator.execution_count)
```

---

## Next

- **Quick Start**: [Get running](Quick-Start)
- **Configuration**: [Customize settings](Configuration)
- **Features**: [What can it do?](Features)
