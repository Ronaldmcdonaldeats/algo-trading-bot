# Phase 3: Comprehensive Self-Learning System

## Overview

Implemented a **fully autonomous, adaptive machine learning system** that continuously improves trading performance through:

1. **Market Regime Detection** - Real-time identification of market conditions
2. **Adaptive Strategy Selection** - Dynamic weighting based on regime suitability
3. **Performance Analytics** - Continuous calculation of Sharpe, drawdown, win rate, profit factor
4. **Trade Pattern Recognition** - Win/loss streak detection and anomaly alerts
5. **Autonomous Parameter Optimization** - Guided recommendations for parameter adjustments
6. **Complete Audit Trail** - Full persistence of learning decisions and regime history

---

## Architecture

### 1. Market Regime Detector (`src/trading_bot/learn/regime.py`)

**Detects 5 market conditions:**
- `TRENDING_UP` - Strong uptrend detected
- `TRENDING_DOWN` - Strong downtrend detected
- `RANGING` - Sideways/consolidation market
- `VOLATILE` - High volatility environment
- `INSUFFICIENT_DATA` - Not enough bars

**Metrics Used:**
- **Volatility** - Annualized ATR-based volatility
- **Trend Strength** - SMA crossover magnitude (10-period fast / 30-period slow)
- **Support/Resistance** - Recent high/low levels (20-bar lookback)

**Regime-Strategy Affinity:**
```
RANGING:    RSI (60%) > MACD (20%) > ATR (20%)
TRENDING:   MACD (70%) > ATR (20%) > RSI (10%)
VOLATILE:   ATR (60%) > RSI (20%) > MACD (20%)
```

**Output:** `RegimeState(regime, confidence, volatility, trend_strength, support, resistance, explanation)`

---

### 2. Performance Metrics Calculator (`src/trading_bot/learn/metrics.py`)

**Metrics Calculated:**
- `total_return` - Net P&L / starting capital
- `sharpe_ratio` - Risk-adjusted return (252 trading days)
- `max_drawdown` - Peak-to-trough decline
- `win_rate` - Winning trades / total trades
- `profit_factor` - Gross profit / gross loss
- `avg_win` / `avg_loss` - Average win/loss magnitude
- `avg_trade_duration_bars` - Average bars held in trade

**Scoring Functions:**
- `score_performance(objective='sharpe')` - Optimize for Sharpe, return, win_rate, or balanced

---

### 3. Trade Outcome Analyzer (`src/trading_bot/learn/trade_analyzer.py`)

**Analysis Types:**

**Strategy Performance Per Regime:**
```python
StrategyAnalysis(
    strategy_name, 
    trades, wins, losses, 
    total_pnl, avg_trade_return, 
    win_rate, regime_performance
)
```

**Pattern Recognition:**
- Win streaks (3+ consecutive wins)
- Loss streaks (2+ consecutive losses)
- Trade quality indicators

**Parameter Recommendations:**
- RSI Mean Reversion: Adjust `entry_oversold` based on win rate
- MACD Momentum: Tune `vol_mult` for volume filtering
- ATR Breakout: Calibrate `atr_mult` for volatility regime

---

### 4. Adaptive Learning Controller (`src/trading_bot/learn/adaptive_controller.py`)

**Main Orchestrator** that combines all learning components.

```python
AdaptiveDecision(
    regime,                          # Current market regime
    regime_confidence,               # 0.0-1.0
    adjusted_weights,                # Regime-aware strategy weights
    parameter_recommendations,       # Suggested param changes
    performance,                     # PerformanceMetrics
    anomalies,                       # List of pattern alerts
    explanation                      # Detailed breakdown
)
```

**Workflow:**
1. Detect regime across all symbols
2. Analyze recent trades (last 30)
3. Calculate performance metrics
4. Blend learned weights with regime affinity
5. Recommend parameter changes
6. Log everything for audit

---

### 5. Database Persistence

**New Tables:**

| Table | Purpose |
|-------|---------|
| `regime_history` | Market regime observations with metrics |
| `adaptive_decisions` | All adaptive learning decisions with explanations |
| `performance_metrics` | Periodic performance snapshots |

**Fields logged:**
- Timestamps
- Regime with confidence
- Volatility, trend strength
- Adjusted weights
- Parameter recommendations
- Anomalies detected
- Full explanation JSON

---

### 6. PaperEngine Integration

**In `step()` method:**

```
1) Weighted rewards update (existing)
   ↓
2) Weekly parameter tuning (existing)
   ↓
3) [NEW] Adaptive learning step
      - Regime detection
      - Trade analysis
      - Performance calculation
      - Weight adjustment (70% learned + 30% regime)
      - Log decision
   ↓
4) Strategy evaluation & execution
   ↓
5) Track equity & trades for next iteration
```

**Automatic Trade Tracking:**
- Captures entry/exit prices
- Associates with strategy
- Tracks bar numbers for duration
- Available for performance analysis

---

## Usage

### Run with Adaptive Learning

```powershell
# 3 iterations with learning enabled
python -m trading_bot paper run --iterations 3 --no-ui --period 90d --interval 1d

# With weekly tuning + adaptive learning
python -m trading_bot paper run \
  --iterations 10 \
  --no-ui \
  --period 1y \
  --interval 1d
```

### Check Learning State

```powershell
# View latest learning state
python -m trading_bot paper report --db trades.sqlite
```

### Query Database

```python
from trading_bot.db.repository import SqliteRepository
from sqlalchemy import select
from trading_bot.db.models import AdaptiveDecisionEvent

repo = SqliteRepository()
engine = repo._engine()

# Get latest adaptive decisions
with Session(engine) as session:
    decisions = session.query(AdaptiveDecisionEvent)\
        .order_by(AdaptiveDecisionEvent.ts.desc())\
        .limit(5)\
        .all()
    
    for d in decisions:
        print(d.ts, d.regime, d.regime_confidence)
```

---

## Learning Loop

### Each Iteration:

1. **Market Regime Detection**
   - Analyzes latest OHLCV data
   - Calculates volatility, trend, support/resistance
   - Determines if market is trending/ranging/volatile

2. **Strategy Performance Analysis**
   - Reviews last 30 trades
   - Calculates win rate per strategy
   - Detects win/loss streaks
   - Identifies anomalies

3. **Adaptive Weighting**
   - Takes ensemble's learned weights
   - Blends with regime affinity (30% adjustment)
   - Favors strategies suited to current regime
   - Prevents overfit to past conditions

4. **Parameter Recommendations**
   - If RSI win rate < 30%: Tighten entry (lower entry_oversold)
   - If RSI win rate > 70%: Relax entry slightly
   - If MACD win rate low: Increase volume filtering (vol_mult++)
   - If ATR win rate low: Increase breakout threshold (atr_mult++)

5. **Audit Logging**
   - All decisions persisted with full explanation
   - Regime history maintained
   - Performance snapshots recorded
   - Enables post-analysis and validation

---

## Key Features

### ✅ Autonomous Learning
- No manual intervention required
- Self-adjusting to market changes
- Learns from trade outcomes

### ✅ Explainability
- Every decision logged with reasoning
- Regime metrics detailed
- Weight adjustments transparent
- Parameter changes justified

### ✅ Risk-Aware
- Sharpe ratio, max drawdown tracked
- Profit factor calculated
- Win rates monitored
- Alerts on losing streaks

### ✅ Regime-Aware
- Trending strategies favored in trends
- Mean reversion favored in ranges
- ATR breakouts favored in volatility
- Automatically adapts to conditions

### ✅ Persistent State
- Full learning history in database
- Can resume from checkpoints
- Audit trail for compliance
- Enables backtesting improvements

---

## Performance Metrics Tracked

```
Total Return:         P&L / Starting Capital
Sharpe Ratio:         (Excess Return / Volatility) * √252
Max Drawdown:         Peak-to-trough decline
Win Rate:             Wins / Total Trades
Profit Factor:        Gross Profit / Gross Loss
Trade Count:          Number of closed trades
Avg Win/Loss:         Average profit/loss per trade
Trade Duration:       Average bars held
```

---

## Example: Learning in Action

**Scenario:** Market shifts from trending to ranging

```
Iteration 1:
  Regime: TRENDING_DOWN, confidence=0.85
  Weights: MACD=0.70, ATR=0.20, RSI=0.10
  
Iteration 2:
  Regime: RANGING, confidence=0.72
  Adjusted: RSI=0.60, MACD=0.20, ATR=0.20
  Blended: RSI=0.51, MACD=0.35, ATR=0.20
  → RSI gets 51% weight (up from 10%)
  
Iteration 3:
  RSI trades analyzed: Win rate = 65%
  Recommendation: "Relax entry_oversold from 30 to 32.5"
  Parameter updated automatically
```

---

## Files Added/Modified

### New Files
- `src/trading_bot/learn/regime.py` - Market regime detection
- `src/trading_bot/learn/metrics.py` - Performance calculation
- `src/trading_bot/learn/trade_analyzer.py` - Trade analysis & patterns
- `src/trading_bot/learn/adaptive_controller.py` - Main orchestrator

### Modified Files
- `src/trading_bot/db/models.py` - Added RegimeHistoryEvent, AdaptiveDecisionEvent, PerformanceMetricsEvent
- `src/trading_bot/db/repository.py` - Added log_adaptive_decision()
- `src/trading_bot/engine/paper.py` - Integrated adaptive controller in step()
- `src/trading_bot/strategy/atr_breakout.py` - Added data sufficiency check

---

## Next Steps (Phase 4+)

1. **CLI Learning Inspection**
   - `python -m trading_bot paper learn inspect` - View regime history
   - `python -m trading_bot paper learn report` - Learning summary

2. **Alpaca Integration** (Phase 4)
   - Live market data via Alpaca provider
   - Paper trading on real tick data
   - Live trading with safety interlocks

3. **Advanced Learning**
   - Genetic algorithm for parameter optimization
   - Multi-symbol correlation learning
   - Sentiment-based regime detection

4. **Risk Enhancements**
   - Position correlation tracking
   - Sector concentration limits
   - Dynamic leverage adjustment

---

## Testing

```powershell
# Run all tests
pytest

# Run learning-specific tests
pytest -k "regime or metrics or analyzer or controller"

# Quick integration test
python -m trading_bot paper run --iterations 5 --no-ui --period 180d --interval 1d
```

---

## Safety Notes

- ✅ All decisions logged for audit
- ✅ Parameter changes bounded and gradual
- ✅ Insufficient data detected and handled
- ✅ Learning only affects future trades
- ✅ Historical trades never modified

**System is fully explainable and auditablel** - every decision can be traced back to market conditions and trade outcomes.
