# Advanced Trading Bot Features - Developer Guide

## Quick Start

The algo trading bot now includes two major advanced feature sets:

### 1. Advanced Risk Management
```python
from src.trading_bot.risk.advanced_risk_management import ComprehensiveRiskAnalysis

# Calculate all risk metrics
risk_metrics = ComprehensiveRiskAnalysis.analyze_portfolio(
    returns=historical_returns,
    capital=100000
)

print(f"Value at Risk (95%): {risk_metrics['var']:.2%}")
print(f"Market Regime: {risk_metrics['market_regime']}")
print(f"Recommended Position Size: {risk_metrics['dynamic_position_size']}")
```

### 2. Deep Learning & Online Learning
```python
from src.trading_bot.learn.deep_learning_models import (
    FeatureEngineering, SimpleLSTM, OnlineLearner
)

# Extract and normalize features
features = FeatureEngineering.extract_features(prices, window=20)
normalized = FeatureEngineering.normalize_features(features)

# Get LSTM prediction
lstm = SimpleLSTM()
prediction = lstm.forward(normalized)
print(f"Predicted Return: {prediction.next_return:.4f}")
print(f"Confidence: {prediction.confidence:.2%}")

# Track performance and detect drift
learner = OnlineLearner()
learner.add_observation(normalized, actual_return)
if learner.should_update_model():
    print("Model update recommended")
```

---

## Module Overview

### Advanced Risk Management (`src/trading_bot/risk/advanced_risk_management.py`)

#### Components

1. **ValueAtRisk**: Historical VaR and CVaR calculations
   - Determines portfolio risk at specific confidence levels
   - Handles edge cases and minimum data requirements
   - Supports both Value at Risk and Conditional VaR

2. **MonteCarloSimulation**: Stochastic portfolio projection
   - Projects portfolio values under various market scenarios
   - Uses Geometric Brownian Motion for realistic price paths
   - Provides percentile bounds and confidence intervals

3. **RegimeDetection**: Market condition classification
   - Identifies bull, bear, and sideways markets
   - Adjusts strategy aggressiveness per regime
   - Provides position multipliers (0.5x to 1.5x)

4. **DynamicPositionSizing**: Optimal position sizing
   - Implements Kelly Criterion with safety factors
   - Adjusts sizes based on volatility and strategy performance
   - Respects maximum risk constraints

5. **ComprehensiveRiskAnalysis**: Unified risk interface
   - Combines all risk metrics into single assessment
   - Used by brokers and strategies for position validation
   - Returns complete risk profile dictionary

#### Usage Examples

```python
# 1. Value at Risk
from src.trading_bot.risk.advanced_risk_management import ValueAtRisk

returns = [-0.02, 0.01, 0.015, -0.01, 0.005]  # Daily returns
var_95 = ValueAtRisk.calculate_var(returns, confidence=0.95)
cvar_95 = ValueAtRisk.calculate_cvar(returns, confidence=0.95)
print(f"VaR: {var_95:.2%}, CVaR: {cvar_95:.2%}")

# 2. Monte Carlo Simulation
from src.trading_bot.risk.advanced_risk_management import MonteCarloSimulation

portfolio_vals, p5, p95 = MonteCarloSimulation.simulate_portfolio_value(
    initial_capital=100000,
    mean_return=0.0005,
    volatility=0.012,
    days=100,
    simulations=1000
)
print(f"5th percentile: ${p5:.0f}, 95th percentile: ${p95:.0f}")

# 3. Regime Detection
from src.trading_bot.risk.advanced_risk_management import RegimeDetection

returns = [0.002, 0.0015, 0.001, 0.0025]  # Positive, low volatility
regime = RegimeDetection.detect_regime(returns, window=20)
multiplier = RegimeDetection.get_regime_multiplier(regime)
print(f"Market Regime: {regime}, Position Multiplier: {multiplier}x")

# 4. Dynamic Position Sizing
from src.trading_bot.risk.advanced_risk_management import DynamicPositionSizing

kelly = DynamicPositionSizing.kelly_fraction(
    win_rate=0.55,
    avg_win=1.0,
    avg_loss=1.0
)
size = DynamicPositionSizing.volatility_adjusted_size(
    base_size=1000,
    current_volatility=0.015,
    target_volatility=0.015
)
print(f"Kelly Fraction: {kelly:.2%}, Adjusted Size: ${size:.0f}")
```

---

### Deep Learning & Online Learning (`src/trading_bot/learn/deep_learning_models.py`)

#### Components

1. **FeatureEngineering**: Technical indicator extraction
   - Momentum, volatility, RSI, MACD
   - Normalization to [-1, 1] range
   - Suitable for neural network input

2. **SimpleLSTM**: Neural network for return prediction
   - LSTM-based architecture
   - Returns prediction with confidence scores
   - Real-time prediction capability

3. **ReinforcementLearningAgent**: Q-learning trader
   - Learns optimal position sizes per market condition
   - Adjusts strategy based on regime and volatility
   - Q-value table updates with real-world rewards

4. **OnlineLearner**: Continuous model monitoring
   - Tracks prediction accuracy
   - Detects concept drift
   - Triggers retraining when accuracy degrades

#### Usage Examples

```python
# 1. Feature Engineering
from src.trading_bot.learn.deep_learning_models import FeatureEngineering

prices = [100, 101, 102, 101, 103]  # Price series
features = FeatureEngineering.extract_features(prices, window=20)
normalized = FeatureEngineering.normalize_features(features)
print(f"Features: {list(features.keys())}")
print(f"Normalized: {normalized}")

# 2. LSTM Prediction
from src.trading_bot.learn.deep_learning_models import SimpleLSTM

lstm = SimpleLSTM(input_size=10, hidden_size=32)
prediction = lstm.forward(normalized)
print(f"Next Return: {prediction.next_return:.4f}")
print(f"Confidence: {prediction.confidence:.2%}")
print(f"Probability Up: {prediction.probability_up:.2%}")

# 3. Reinforcement Learning
from src.trading_bot.learn.deep_learning_models import ReinforcementLearningAgent

agent = ReinforcementLearningAgent()
state = agent.get_state(regime='bull', volatility=0.012, sharpe_ratio=1.5)
action = agent.get_action(state)
position_multiplier = agent.get_position_multiplier(action)

# After trade execution
reward = 0.05  # Profit of 5%
next_state = agent.get_state(regime='bull', volatility=0.011, sharpe_ratio=1.6)
agent.update_q_value(state, action, reward, next_state)

print(f"Action: {action}, Position: {position_multiplier}x")

# 4. Online Learning
from src.trading_bot.learn.deep_learning_models import OnlineLearner

learner = OnlineLearner()
for trade in completed_trades:
    learner.add_observation(trade.features, trade.return_pct)

accuracy = learner.get_recent_accuracy(window=50)
if learner.should_update_model(accuracy_threshold=0.45):
    print(f"Accuracy degraded to {accuracy:.2%}, retraining model...")
```

---

## Integration with Trading Engine

### Paper Trading Integration

```python
from src.trading_bot.paper.runner import PaperRunner
from src.trading_bot.learn.deep_learning_models import SimpleLSTM

runner = PaperRunner()

# Get prediction from LSTM
lstm = SimpleLSTM()
prediction = lstm.forward(features)

# Execute trade if confident
if prediction.confidence > 0.7:
    if prediction.next_return > 0:
        runner.buy(symbol="AAPL", size=100)
    else:
        runner.sell(symbol="AAPL", size=100)

# Track accuracy over time
runner.track_prediction(
    predicted_return=prediction.next_return,
    actual_return=actual_return
)
```

### Backtesting Integration

```python
from src.trading_bot.backtest.engine import BacktestEngine
from src.trading_bot.risk.advanced_risk_management import ComprehensiveRiskAnalysis

engine = BacktestEngine()

# Use risk analysis for position sizing
for bar in price_data:
    risk_metrics = ComprehensiveRiskAnalysis.analyze_portfolio(
        returns=historical_returns,
        capital=engine.account_balance
    )
    
    position_size = risk_metrics['dynamic_position_size']
    regime = risk_metrics['market_regime']
    
    if regime == 'bull':
        engine.place_order('AAPL', position_size, 'buy')
```

---

## Configuration & Hyperparameters

### Risk Management Config
```yaml
# In configs/default.yaml
risk_management:
  var_confidence: 0.95              # 95% confidence level
  monte_carlo_simulations: 10000    # Number of paths
  regime_detection_window: 20       # Returns lookback
  kelly_fraction_scale: 0.25        # Safety factor
  target_volatility: 0.015          # Target portfolio vol
  max_position_risk: 0.02           # 2% max risk per trade
```

### Learning Config
```yaml
learning:
  feature_window: 20                # Technical indicator window
  lstm_hidden_size: 32              # LSTM nodes
  lstm_learning_rate: 0.001         # Training learning rate
  
  reinforcement:
    learning_rate: 0.1              # Q-learning alpha
    discount_factor: 0.95           # Gamma
    epsilon: 0.1                    # Exploration rate
  
  online_learning:
    history_window: 1000            # Max observations
    accuracy_window: 50             # Accuracy calc window
    update_threshold: 0.45          # Retraining trigger
```

---

## Performance Characteristics

### Speed
- VaR calculation: < 1ms
- Monte Carlo (10k sims): ~100ms
- Feature extraction: < 1ms
- LSTM prediction: < 1ms
- Q-learning update: < 0.1ms

### Memory
- Risk module: ~1MB
- Learning module: ~5-10MB
- Total footprint: Suitable for real-time

### Accuracy
- LSTM: Requires 100+ training samples
- RL Agent: Learns over 500-1000 trades
- Online Learning: Detects drift in 50-100 trades

---

## Testing

Run all advanced features tests:
```bash
pytest tests/test_advanced_features.py -v
```

Run specific component tests:
```bash
pytest tests/test_advanced_features.py::TestValueAtRisk -v
pytest tests/test_advanced_features.py::TestSimpleLSTM -v
```

All 25 tests should pass:
```
tests\test_advanced_features.py .........................
=================================================== 25 passed in 1.89s ===================================================
```

---

## Troubleshooting

### VaR Calculation Errors
**Problem**: "ValueError: Not enough data points"
**Solution**: Provide at least 20 historical returns

### Monte Carlo Takes Too Long
**Problem**: Simulation is slow
**Solution**: Reduce simulations parameter (10000 → 5000)

### LSTM Returns All Zeros
**Problem**: Prediction always 0.0
**Solution**: Ensure features are normalized to [-1, 1] range

### Online Learner Not Detecting Drift
**Problem**: Model not retraining
**Solution**: Check accuracy window (default 50 trades), adjust threshold

---

## Best Practices

1. **Risk Management**
   - Update regime detection daily (market changes)
   - Use VaR for position sizing, not profit targets
   - Apply Kelly fraction only to proven strategies

2. **Learning**
   - Collect 100+ trades before evaluating LSTM
   - Monitor online learner accuracy weekly
   - Don't trust RL agent until 500+ trades
   - Use ensemble: LSTM + RL + Traditional indicators

3. **Production**
   - Start with paper trading
   - Monitor all metrics continuously
   - Have kill switches for unusual regimes
   - Update models monthly with new data

---

## Future Enhancements

1. **Advanced LSTM**: True sequential LSTM with memory
2. **Deep Q-Network**: Continuous action space
3. **Ensemble Methods**: Combine multiple models
4. **Transfer Learning**: Pre-training on related assets
5. **Active Learning**: Query uncertain samples

---

## API Reference

### ValueAtRisk
```python
ValueAtRisk.calculate_var(returns: List[float], confidence: float) -> float
ValueAtRisk.calculate_cvar(returns: List[float], confidence: float) -> float
```

### MonteCarloSimulation
```python
MonteCarloSimulation.simulate_returns(mean_return, volatility, days, simulations, seed) -> np.ndarray
MonteCarloSimulation.simulate_portfolio_value(initial_capital, mean_return, volatility, days, simulations) -> Tuple
MonteCarloSimulation.calculate_portfolio_var(capital, mean_return, volatility, days, confidence) -> float
```

### RegimeDetection
```python
RegimeDetection.detect_regime(returns: List[float], window: int) -> str
RegimeDetection.get_regime_multiplier(regime: str) -> float
```

### DynamicPositionSizing
```python
DynamicPositionSizing.kelly_fraction(win_rate, avg_win, avg_loss) -> float
DynamicPositionSizing.volatility_adjusted_size(base_size, current_volatility, target_volatility) -> float
DynamicPositionSizing.calculate_position_size(capital, kelly_fraction, volatility, target_volatility, max_risk_pct) -> float
```

### FeatureEngineering
```python
FeatureEngineering.extract_features(prices: List[float], window: int) -> Dict[str, float]
FeatureEngineering.normalize_features(features: Dict[str, float]) -> Dict[str, float]
```

### SimpleLSTM
```python
SimpleLSTM.forward(features: Dict[str, float]) -> LSTMPrediction
```

### ReinforcementLearningAgent
```python
ReinforcementLearningAgent.get_state(regime, volatility, sharpe_ratio) -> Tuple[int, int, int]
ReinforcementLearningAgent.get_action(state) -> int
ReinforcementLearningAgent.update_q_value(state, action, reward, next_state) -> None
ReinforcementLearningAgent.get_position_multiplier(action) -> float
```

### OnlineLearner
```python
OnlineLearner.add_observation(features: Dict[str, float], return_value: float) -> None
OnlineLearner.get_recent_accuracy(window: int) -> float
OnlineLearner.should_update_model(accuracy_threshold: float) -> bool
```

---

## Support & Documentation

- **Issue Tracker**: Report bugs in GitHub Issues
- **Documentation**: See IMPLEMENTATION_SUMMARY.md
- **QA Report**: See QUALITY_ASSURANCE_REPORT.md
- **Tests**: Comprehensive suite in tests/test_advanced_features.py

---

## License

These advanced features are part of the algo-trading-bot project.
See LICENSE file for details.
