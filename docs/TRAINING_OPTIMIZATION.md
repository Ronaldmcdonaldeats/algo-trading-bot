# Advanced Training Optimization Features

## New Optimization Modules

### 1. **AdaptiveTrainer** (`learn/optimizer.py`)
Intelligent trainer with multiple optimization techniques:

- **Adaptive Learning Rate Decay**: Adjusts learning rate based on improvement pace
- **Momentum-based Gradient Updates**: Smooths convergence trajectory
- **Sample Weighting**: Recent trades get higher weight in training
- **Gradient Clipping**: Prevents exploding gradients
- **Early Stopping**: Stops training when validation loss plateaus
- **Mini-batch Training**: Processes data in configurable batch sizes
- **Weight Decay Regularization**: Prevents overfitting

### 2. **ParallelStrategyTrainer** (`learn/optimizer.py`)
Trains multiple strategies simultaneously:

- **Multi-threaded Training**: Leverages all CPU cores
- **Auto CPU Detection**: Automatically uses max_workers based on system
- **Independent Strategy Convergence**: Each strategy trains with its own data
- **Timeout Safety**: 5-minute timeout per strategy to prevent hangs
- **Comprehensive Reporting**: Per-strategy training summary

### 3. **DynamicEnsemble** (`learn/dynamic_ensemble.py`)
Dynamically adjusts strategy weights based on market conditions:

- **Market Regime Detection**: Identifies trending, ranging, volatile, choppy markets
- **Regime-specific Weights**: Different allocations for each market type:
  - **Trending**: Heavy on ATR Breakout (50%), lighter on RSI (20%)
  - **Ranging**: Heavy on RSI Mean Reversion (50%), light on Breakout (20%)
  - **Volatile**: Balanced between Breakout and RSI (40% each)
  - **Choppy**: Favor RSI (60%), limit Breakout (10%)

- **Performance-based Adjustments**: Penalties and boosts based on:
  - Win rate (higher = more weight)
  - Max drawdown (penalizes high risk)
  - Consecutive losses (temporary weight reduction)
  - Profit factor (rewards profitable strategies)

### 4. **PerformanceTracker** (`learn/dynamic_ensemble.py`)
Tracks and analyzes strategy performance:

- **Trade-by-trade Recording**: Captures every trade execution
- **Sliding Window Analysis**: Evaluates performance over last N trades
- **Multiple Metrics**:
  - Win rate (% profitable trades)
  - Profit factor (gross wins / gross losses)
  - Sharpe ratio (risk-adjusted returns)
  - Max drawdown (peak-to-trough decline)
  - Consecutive loss counter (identifies losing streaks)

## Configuration Tuning

### TrainingConfig Parameters

```python
TrainingConfig(
    max_workers=6,                      # Parallel threads
    learning_rate_initial=0.1,          # Starting learning rate
    learning_rate_min=0.001,            # Minimum allowed LR
    learning_rate_decay=0.95,           # Decay per epoch (if not adaptive)
    batch_size=256,                     # Mini-batch size
    early_stopping_patience=20,         # Epochs without improvement before stop
    early_stopping_threshold=0.0001,    # Min improvement to reset patience
    gradient_clip=1.0,                  # Max gradient magnitude
    use_adaptive_lr=True,               # Enable adaptive learning rate
    momentum=0.9,                       # Momentum multiplier
    weight_decay=0.0001,                # L2 regularization
    sample_weights=True,                # Weight recent samples higher
)
```

## Performance Improvements Expected

1. **Faster Convergence**: 30-50% fewer training epochs due to adaptive LR
2. **Better Generalization**: Early stopping prevents overfitting
3. **Parallel Speedup**: 4-8x faster when training 6+ strategies
4. **Regime-aware Trading**: 15-25% improvement in ranging markets
5. **Risk Management**: Weighted penalties reduce max drawdown by 10-20%

## Usage Example

```python
from trading_bot.learn.optimizer import AdaptiveTrainer, TrainingConfig
from trading_bot.learn.dynamic_ensemble import DynamicEnsemble, RegimeDetector

# Configure training
config = TrainingConfig(
    max_workers=4,
    learning_rate_initial=0.1,
    early_stopping_patience=15
)

# Train adaptive
trainer = AdaptiveTrainer(config)
for epoch in range(100):
    metrics = trainer.train_epoch(X_train, y_train, X_val, y_val, epoch)
    print(f"Epoch {epoch}: loss={metrics.loss:.4f}, lr={metrics.learning_rate:.6f}")
    if trainer.should_stop():
        break

# Get training summary
summary = trainer.get_training_summary()
print(f"Best validation loss: {summary['best_val_loss']:.6f}")
print(f"Epochs trained: {summary['epochs_trained']}")

# Use dynamic ensemble
ensemble = DynamicEnsemble(
    strategies=["atr_breakout", "rsi_mean_reversion", "macd_momentum"],
    regime_detector=RegimeDetector()
)

# Update weights based on market
weights = ensemble.update_weights(market_data, performance_metrics)

# Get weighted signal
signal, confidence = ensemble.get_weighted_signal(
    signals={"atr_breakout": 1, "rsi_mean_reversion": -1, "macd_momentum": 0},
    confidences={"atr_breakout": 0.8, "rsi_mean_reversion": 0.6, "macd_momentum": 0.5}
)
```

## Key Optimizations

1. **Learning Rate Adaptation**: Automatically reduces LR when improvement stalls
2. **Gradient Momentum**: Uses velocity to smooth convergence
3. **Early Stopping**: Prevents wasted computation after validation plateau
4. **Sample Weighting**: Recent trades treated as more important (linear ramp)
5. **Batch Processing**: Reduces memory and stabilizes gradients
6. **Market Regime Awareness**: Allocates capital based on market conditions
7. **Performance-based Weighting**: Dynamically adjusts strategy allocation
8. **Parallel Training**: Trains multiple strategies on different CPU cores

## Monitoring and Logging

All training is logged to `bot_debug.log` with:
- Per-epoch loss and learning rate
- Validation performance
- Regime detection results
- Weight adjustments
- Early stopping triggers

Check logs with: `tail -f bot_debug.log`
