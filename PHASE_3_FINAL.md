# Phase 3 Complete: Autonomous Learning System ✅

## Overview
The algo-trading-bot now features a comprehensive autonomous learning system that continuously improves trading performance through:
- Market regime detection (trending, ranging, volatile)
- Adaptive strategy selection (70% learned weights + 30% regime affinity)
- Performance analytics (Sharpe, drawdown, win rate, profit factor)
- Trade pattern recognition (win/loss streaks, anomalies)
- Real-time monitoring via CLI while paper trading

## What's Implemented

### 1. Paper Trading Engine
- **3 Strategies**: Mean Reversion RSI, MACD+Volume Momentum, ATR Breakout
- **Ensemble Learning**: Bandit algorithm with exponential weight updates
- **Weekly Tuning**: Bounded parameter grid search
- **Full State Persistence**: All decisions logged to SQLite

### 2. Adaptive Learning System (4 New Modules)

#### regime.py - Market Regime Detection
Detects market conditions in real-time:
- `TRENDING_UP` - Strong uptrend with momentum
- `TRENDING_DOWN` - Strong downtrend with momentum
- `RANGING` - Sideways consolidation
- `VOLATILE` - High volatility regardless of direction
- `INSUFFICIENT_DATA` - Not enough bars for analysis

**Features:**
- Volatility calculation (ATR-based)
- Trend strength via SMA crossovers
- Support/resistance detection
- Confidence scoring (0.0-1.0)

#### metrics.py - Performance Calculator
Computes key trading metrics:
- Total return
- Sharpe ratio (risk-adjusted)
- Maximum drawdown
- Win rate
- Profit factor
- Trade duration tracking
- Objective scoring functions

#### trade_analyzer.py - Pattern Recognition
Analyzes completed trades:
- Per-strategy performance breakdown
- Win/loss streak detection (3+ consecutive)
- Anomaly identification
- Autonomous parameter recommendations
- Bounded adjustments (e.g., RSI ±5, MACD ±0.25)

#### adaptive_controller.py - Learning Orchestrator
Main learning engine:
- Regime detection across all symbols
- Recent trade analysis (last 30 trades)
- Performance metric calculation
- Weight blending: 70% learned + 30% regime affinity
- Decision logging with full explanations

### 3. Learning CLI (4 Commands)

```powershell
python -m trading_bot learn inspect       # Current regime + weights + decisions
python -m trading_bot learn history       # Regime observation timeline
python -m trading_bot learn decisions     # Adaptive decision history
python -m trading_bot learn metrics       # Performance metrics over time
```

#### Features
- Real-time monitoring while paper trading runs
- Clean, readable output (no brackets/JSON clutter)
- Customizable limits (--limit N)
- Custom database support (--db path)

### 4. Database Persistence
3 new tables for learning audit trail:
- `RegimeHistoryEvent` - Market observations
- `AdaptiveDecisionEvent` - Learning decisions with explanations
- `PerformanceMetricsEvent` - Performance snapshots

## Running the System

### Quickstart
```powershell
# Terminal 1: Start paper trading with learning
python -m trading_bot paper run --iterations 100 --no-ui --period 180d --interval 1d

# Terminal 2 (while Terminal 1 runs): Monitor learning
python -m trading_bot learn inspect
python -m trading_bot learn decisions
python -m trading_bot learn metrics
```

### With Custom Settings
```powershell
python -m trading_bot paper run \
    --iterations 50 \
    --no-ui \
    --period 2y \
    --interval 1d \
    --symbols SPY,QQQ,IWM \
    --start-cash 250000
```

### Demo Script
```powershell
.\demo_learning_monitoring.ps1
```

## Output Example

### Learning Inspect
```
[MARKET REGIME]
  Regime:       ranging
  Confidence:   90.4%
  Volatility:   0.1442
  Trend Str:    0.0964

[ADAPTIVE DECISION]
  Adjusted Weights:
    mean_reversion_rsi  : 0.5865
    breakout_atr        : 0.2068
    momentum_macd_volume: 0.2067
  
  Regime Metrics:
    support             : 676.57
    resistance          : 696.09
    trend_direction     : 1.0000
    volatility_annualized: 0.1442
```

### Paper Trading
```
iter=1 cash=100,000.00 equity=100,000.00 fills=0 rejections=0
iter=2 cash=100,000.00 equity=100,000.00 fills=0 rejections=0
iter=3 cash=100,000.00 equity=100,000.00 fills=0 rejections=0
...
```

## Key Metrics Tracked

### Market Regime
- Volatility (annualized ATR)
- Trend strength (SMA crossover)
- Support/resistance levels
- Trend direction (+1/-1)

### Strategy Performance
- Return per trade
- Win/loss count
- Trade duration
- Strategy-specific anomalies

### Portfolio Metrics
- Total return
- Sharpe ratio (annualized, 252 days)
- Maximum drawdown
- Win rate
- Profit factor
- Trade count

## Workflow: Real-Time Monitoring

While paper trading runs:

1. **Every 10 sec**: Check regime changes
   ```powershell
   python -m trading_bot learn inspect
   ```

2. **Every 30 sec**: Review weight adjustments
   ```powershell
   python -m trading_bot learn decisions --limit 5
   ```

3. **Every 5 min**: Analyze performance trends
   ```powershell
   python -m trading_bot learn metrics
   ```

## Architecture

```
Paper Trading Loop (Every Iteration)
    ↓
Data Fetch (OHLCV)
    ↓
Market Regime Detection (volatility, trend, support/resistance)
    ↓
Trade Analysis (win/loss patterns, per-strategy performance)
    ↓
Performance Metrics Calc (Sharpe, drawdown, win rate)
    ↓
Ensemble Learning (exponential weight updates)
    ↓
Adaptive Decision (blend 70% learned + 30% regime affinity)
    ↓
Weight Adjustment (gentle blending into ensemble)
    ↓
Strategy Execution (RSI, MACD, ATR with adjusted weights)
    ↓
Decision Logging (SQLite with full explanation)
    ↓
Paper Trading Output (cash, equity, fills, rejections)
    ↓
Learning CLI can inspect at any point
```

## Safety & Robustness

✅ **Data Validation**
- Checks for sufficient bars before indicators
- Graceful handling of incomplete data

✅ **Bounded Learning**
- Parameter changes limited (e.g., RSI ±5)
- Gradual weight adjustments (70/30 blend)
- Historical trades never modified

✅ **Explainability**
- Full decision logging with reasoning
- Regime metrics captured
- Strategy analysis documented
- Anomalies flagged

✅ **Error Handling**
- Missing data fallback
- Incomplete state recovery
- Safe indicator calculation

## Files Created/Modified

### New Files (1050+ lines)
- `src/trading_bot/learn/regime.py` (400 lines)
- `src/trading_bot/learn/metrics.py` (150 lines)
- `src/trading_bot/learn/trade_analyzer.py` (200 lines)
- `src/trading_bot/learn/adaptive_controller.py` (300 lines)
- `src/trading_bot/learn/cli.py` (300 lines)

### Modified Files
- `src/trading_bot/engine/paper.py` - Integrated learning
- `src/trading_bot/db/models.py` - 3 new tables
- `src/trading_bot/db/repository.py` - Logging methods
- `src/trading_bot/cli.py` - Learning CLI commands

### Documentation
- `LEARNING_CLI_GUIDE.md` - Complete CLI guide
- `PHASE_3_LEARNING.md` - Architecture details
- `LEARNING_SYSTEM_SUMMARY.md` - Executive summary
- `PHASE_3_COMPLETION.md` - Feature checklist
- `demo_learning_monitoring.ps1` - Demo script

## Next Phase: Phase 4 - Alpaca Integration

The learning system is ready for real broker integration:
- Live market data (intraday bars)
- Paper + live trading modes
- Safety interlocks and circuit breakers
- Risk management on real positions

Learning will automatically adapt to:
- Real broker fill slippage
- Commission costs
- Execution delays
- Market microstructure effects

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python -m trading_bot paper run --iterations N` | Start paper trading |
| `python -m trading_bot learn inspect` | Current regime + weights |
| `python -m trading_bot learn history` | Regime history |
| `python -m trading_bot learn decisions` | Decision timeline |
| `python -m trading_bot learn metrics` | Performance metrics |
| `python -m trading_bot --help` | Show all commands |

## Performance Interpretation

**Sharpe Ratio:**
- 0-0.5: Acceptable
- 0.5-1.0: Good
- 1.0+: Excellent

**Drawdown:**
- -5%: Moderate
- -10%: Large
- -20%+: Very risky

**Win Rate:**
- 40-50%: Typical
- 60%+: Strong
- Requires 20+ trades for significance

**Profit Factor:**
- 1.0: Breaks even
- 1.5: Good (50% more wins)
- 2.0+: Excellent (2x more wins)

## System Status

✅ **Production Ready**
- All 7 components implemented and tested
- Database persistence functional
- CLI monitoring active
- Paper trading with learning enabled by default
- Full audit trail for compliance

## Getting Started

1. **Install** (if not already done):
   ```powershell
   python -m pip install -e ".[dev]"
   ```

2. **Run paper trading**:
   ```powershell
   python -m trading_bot paper run --iterations 20 --no-ui --period 180d
   ```

3. **Monitor learning** (in another terminal):
   ```powershell
   python -m trading_bot learn inspect
   ```

4. **Analyze results**:
   ```powershell
   python -m trading_bot learn decisions
   python -m trading_bot learn metrics
   ```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No adaptive decisions yet" | Paper trading needs 2-3 iterations to log decisions |
| "No regime history yet" | Same as above |
| Different database | Use `--db mydb.sqlite` flag |
| Weights not changing | Normal - regime blending (70/30) gradually adjusts |

---

**Phase 3 Status:** ✅ COMPLETE
**Next:** Phase 4 - Alpaca Integration
**Last Updated:** January 23, 2026
