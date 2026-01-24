# Integration Guide

## Overview

This guide shows how to integrate the trading bot into your existing systems or extend it with custom components.

---

## Core Integration Points

### 1. Using the Orchestrator

The `MultiAlgorithmOrchestrator` is the main entry point:

```python
from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator, AlgorithmConfig

# Initialize
orchestrator = MultiAlgorithmOrchestrator(max_history=1000)

# Register algorithms
atr_config = AlgorithmConfig(
    name="atr_breakout",
    weight=1.2,
    timeout_seconds=5
)
orchestrator.register_algorithm(
    "atr", 
    atr_algorithm_function,
    config=atr_config
)

# Run a trading cycle
signal, confidence, metrics = orchestrator.execute_cycle(
    market_data=df,
    symbols=["AAPL", "MSFT"],
    current_prices={"AAPL": 150.25, "MSFT": 310.50},
    market_regime="trending"
)

# Get results
print(f"Signal: {signal}")  # "BUY", "SELL", or "HOLD"
print(f"Confidence: {confidence:.2%}")  # 0.0-1.0
print(f"Metrics: {metrics}")  # Execution details
```

### 2. Custom Algorithm Integration

```python
def my_custom_algorithm(data, symbol, current_price, **kwargs):
    """
    Your algorithm must follow this signature.
    
    Args:
        data: DataFrame with OHLCV data
        symbol: Stock symbol (e.g., "AAPL")
        current_price: Current market price
        **kwargs: Additional parameters
    
    Returns:
        signal: "BUY", "SELL", or "HOLD"
        strength: 0.0-1.0 confidence
        indicators: dict of indicator values
    """
    # Your logic here
    if some_condition:
        return "BUY", 0.85, {"indicator1": value1}
    else:
        return "HOLD", 0.5, {}

# Register it
orchestrator.register_algorithm(
    "my_algorithm",
    my_custom_algorithm,
    weight=1.0
)
```

### 3. Data Provider Integration

```python
from trading_bot.data.providers import YahooDataProvider, AlpacaDataProvider

# Use different data sources
yahoo_data = YahooDataProvider()
df = yahoo_data.get_data("AAPL", days=60)

alpaca_data = AlpacaDataProvider(api_key="...", secret="...")
live_df = alpaca_data.get_data("AAPL", timeframe="1min")

# Custom provider
class MyDataProvider:
    def get_data(self, symbol, days=60):
        # Fetch from your data source
        return df

provider = MyDataProvider()
df = provider.get_data("AAPL")
```

### 4. Broker Integration

```python
from trading_bot.broker.paper import PaperBroker
from trading_bot.broker.alpaca import AlpacaBroker

# Paper trading (backtesting)
paper_broker = PaperBroker(initial_capital=100000)
order = paper_broker.place_order(
    symbol="AAPL",
    quantity=100,
    side="BUY",
    order_type="MARKET"
)

# Live trading
live_broker = AlpacaBroker(
    api_key="...",
    secret_key="..."
)
order = live_broker.place_order(
    symbol="AAPL",
    quantity=100,
    side="BUY",
    order_type="MARKET",
    take_profit=5.0,      # % above entry
    stop_loss=2.0         # % below entry
)
```

---

## Common Integration Scenarios

### Scenario 1: Existing Trading System

Integrate the orchestrator into your existing system:

```python
# Your existing system
class MyTradingSystem:
    def __init__(self):
        self.orchestrator = MultiAlgorithmOrchestrator()
        
    def run_strategy(self, market_data):
        # Get signal from orchestrator
        signal, confidence, _ = self.orchestrator.execute_cycle(
            market_data=market_data,
            symbols=self.symbols,
            current_prices=self.current_prices,
            market_regime=self.detect_regime()
        )
        
        # Use signal in your system
        if signal == "BUY" and confidence > 0.7:
            self.place_buy_order()
        elif signal == "SELL" and confidence > 0.7:
            self.place_sell_order()
```

### Scenario 2: Risk Management Wrapper

Add risk management on top:

```python
class RiskManagedSystem:
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.max_position_size = 0.05
        self.max_daily_loss = 0.02
        self.daily_pnl = 0.0
    
    def execute_with_risk_control(self, signal, quantity):
        # Check position size
        if quantity * self.current_price > self.portfolio_value * self.max_position_size:
            quantity = int(self.portfolio_value * self.max_position_size / self.current_price)
        
        # Check daily loss
        if self.daily_pnl < -self.portfolio_value * self.max_daily_loss:
            print("Daily loss limit reached, stopping trades")
            return None
        
        # Execute
        return self.broker.place_order(symbol, quantity, signal)
```

### Scenario 3: Multi-Account Management

Manage multiple trading accounts:

```python
class MultiAccountManager:
    def __init__(self):
        self.accounts = {
            "paper": PaperBroker(initial_capital=100000),
            "live": AlpacaBroker(api_key="...", secret="..."),
            "swing": PaperBroker(initial_capital=50000)
        }
        self.orchestrator = MultiAlgorithmOrchestrator()
    
    def execute_all_accounts(self, market_data, symbol):
        signal, confidence, _ = self.orchestrator.execute_cycle(
            market_data=market_data,
            symbols=[symbol]
        )
        
        # Execute in all accounts
        for account_name, broker in self.accounts.items():
            quantity = self._calculate_quantity(account_name, symbol)
            broker.place_order(symbol, quantity, signal)
```

### Scenario 4: Live Dashboard Integration

Connect to a live monitoring dashboard:

```python
import streamlit as st
from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator

# Initialize
orchestrator = MultiAlgorithmOrchestrator()

# Dashboard
st.title("Trading Bot Dashboard")

# Metrics columns
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Win Rate", f"{orchestrator.win_rate:.1%}")
with col2:
    st.metric("Sharpe Ratio", f"{orchestrator.sharpe_ratio:.2f}")
with col3:
    st.metric("Max Drawdown", f"{orchestrator.max_drawdown:.1%}")
with col4:
    st.metric("P&L", f"${orchestrator.total_pnl:,.2f}")

# Current regime
regime = orchestrator.detect_regime(market_data)
st.metric("Market Regime", regime)

# Algorithm weights
weights = orchestrator.get_adjusted_weights(regime)
st.bar_chart(weights)
```

---

## Custom Indicators

### Add to Existing Algorithms

```python
def enhanced_atr_breakout(data, symbol, current_price, custom_threshold=2.0):
    """Enhanced ATR with custom indicators"""
    
    from trading_bot.indicators import calculate_atr, calculate_rsi
    
    # Standard indicators
    atr = calculate_atr(data, period=14)
    rsi = calculate_rsi(data, period=14)
    
    # Custom indicator
    recent_volatility = data['High'].pct_change().std() * 100
    
    # Your logic
    if current_price > data['Close'].mean() + (atr.iloc[-1] * custom_threshold):
        if rsi.iloc[-1] < 70:  # Not overbought
            return "BUY", 0.8 + (recent_volatility / 100), {
                "atr": atr.iloc[-1],
                "rsi": rsi.iloc[-1],
                "volatility": recent_volatility
            }
    
    return "HOLD", 0.5, {}
```

### Create New Indicator Library

```python
# src/trading_bot/indicators/custom.py

def calculate_machine_learning_signal(data):
    """Use ML model for signals"""
    import joblib
    
    model = joblib.load("ml_model.pkl")
    features = extract_features(data)
    signal = model.predict(features)
    
    return "BUY" if signal > 0.5 else "SELL"

def calculate_sentiment_adjusted_signal(data, sentiment_score):
    """Incorporate sentiment analysis"""
    
    if sentiment_score > 0.7:
        # Bullish sentiment
        return "BUY", 0.85
    elif sentiment_score < 0.3:
        # Bearish sentiment
        return "SELL", 0.85
    else:
        return "HOLD", 0.5
```

---

## Performance Optimization

### Caching Results

```python
from trading_bot.learn.concurrent_executor import CalculationCache

cache = CalculationCache(max_size=256, ttl_seconds=60)

# Expensive calculation
def expensive_calculation(data, symbol):
    # This will be cached
    key = f"{symbol}_{data.index[-1]}"
    
    if key in cache:
        return cache.get(key)
    
    result = complex_analysis(data)
    cache.set(key, result)
    return result
```

### Parallel Execution

```python
from trading_bot.learn.concurrent_executor import ConcurrentStrategyExecutor

executor = ConcurrentStrategyExecutor(
    max_workers=4,
    timeout_seconds=5
)

# Run multiple strategies in parallel
results = executor.execute([
    ("atr", atr_func, df, "AAPL"),
    ("rsi", rsi_func, df, "AAPL"),
    ("macd", macd_func, df, "AAPL"),
])
```

---

## Database Integration

### Trade History

```python
from trading_bot.db.models import Trade
from sqlalchemy import create_engine

engine = create_engine("sqlite:///trades.db")

# Log a trade
trade = Trade(
    symbol="AAPL",
    entry_price=150.25,
    exit_price=152.50,
    quantity=100,
    side="BUY",
    pnl=225.00,
    algorithm="atr_breakout"
)
session.add(trade)
session.commit()

# Query history
recent_trades = session.query(Trade)\
    .filter(Trade.symbol == "AAPL")\
    .order_by(Trade.created_at.desc())\
    .limit(100)\
    .all()
```

### Analytics

```python
from trading_bot.analytics.duckdb_pipeline import AnalyticsPipeline

pipeline = AnalyticsPipeline()

# Aggregate statistics
stats = pipeline.get_performance_stats(symbol="AAPL", days=30)
print(f"Win Rate: {stats['win_rate']:.1%}")
print(f"Avg Win: ${stats['avg_win']:.2f}")
print(f"Avg Loss: ${stats['avg_loss']:.2f}")
```

---

## API Integration

### REST API for External Access

```python
from fastapi import FastAPI
from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator

app = FastAPI()
orchestrator = MultiAlgorithmOrchestrator()

@app.get("/signal/{symbol}")
def get_signal(symbol: str):
    """Get current trading signal for symbol"""
    signal, confidence, metrics = orchestrator.execute_cycle(
        market_data=get_market_data(symbol),
        symbols=[symbol]
    )
    return {
        "symbol": symbol,
        "signal": signal,
        "confidence": confidence,
        "metrics": metrics
    }

@app.get("/status")
def get_status():
    """Get orchestrator status"""
    return {
        "algorithms": len(orchestrator.algorithms),
        "execution_count": orchestrator.execution_count,
        "win_rate": orchestrator.win_rate,
        "avg_execution_time_ms": orchestrator.avg_execution_time * 1000
    }
```

### Webhook Integration

```python
@app.post("/webhook/market_signal")
async def receive_market_signal(payload: dict):
    """Receive signals from external source"""
    
    # Process external signal
    external_signal = payload.get("signal")
    
    # Combine with internal signals
    internal_signal, confidence, _ = orchestrator.execute_cycle(...)
    
    # Make final decision
    if external_signal == internal_signal:
        confidence *= 1.2  # Increase confidence
    
    return {"decision": internal_signal, "confidence": confidence}
```

---

## Testing Integration

### Unit Tests

```python
import pytest
from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator

def test_orchestrator_integration():
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

### Integration Tests

```python
def test_end_to_end_trading():
    """Test complete trading flow"""
    
    # Setup
    broker = PaperBroker(initial_capital=100000)
    orchestrator = MultiAlgorithmOrchestrator()
    
    # Register algorithms
    orchestrator.register_algorithm("atr", atr_func)
    
    # Execute cycle
    signal, _, _ = orchestrator.execute_cycle(market_data, symbols)
    
    # Place order
    order = broker.place_order("AAPL", 100, signal)
    
    # Verify
    assert order.status == "filled"
    assert broker.get_position("AAPL") == 100
```

---

## Troubleshooting Integration

| Issue | Solution |
|-------|----------|
| **Import errors** | Install package: `pip install -e .` |
| **Data format mismatch** | Ensure DataFrame has OHLCV columns |
| **Signal conflicts** | Use orchestrator weighting system |
| **Performance issues** | Enable caching and parallel execution |
| **Database errors** | Check connection string and tables exist |

---

## Best Practices

1. **Use the orchestrator** as your main entry point
2. **Register custom algorithms** with meaningful names
3. **Handle errors gracefully** with try/except blocks
4. **Cache expensive calculations** to improve speed
5. **Monitor performance** with metrics and logging
6. **Test thoroughly** with paper trading first
7. **Keep data clean** and normalized
8. **Document your integrations** for future reference

---

## Next Steps

1. **Choose your integration point**: Standalone, existing system, or API
2. **Register your algorithms** with the orchestrator
3. **Test in paper trading**: Verify signals and performance
4. **Add risk management**: Position sizing, stop losses
5. **Deploy**: Docker or cloud platform
6. **Monitor**: Dashboard and logging

See [Configuration Guide](../deployment/CONFIG.md) for settings, [Concurrent Execution](CONCURRENT_EXECUTION.md) for architecture details, or [Quick Start](../getting-started/QUICK_START.md) for setup.
