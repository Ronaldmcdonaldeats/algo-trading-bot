# Learning CLI - Real-Time Monitoring

The `learning` CLI allows you to inspect the autonomous learning system while paper trading is running. This enables real-time monitoring of market regime detection, adaptive decisions, and performance metrics.

## Quick Start

### Terminal 1: Start Paper Trading
```powershell
python -m trading_bot paper run --iterations 100 --no-ui --period 180d --interval 1d
```

### Terminal 2: Monitor Learning (while Terminal 1 is running)
```powershell
python -m trading_bot learn inspect     # Snapshot of current state
python -m trading_bot learn decisions   # All adaptive decisions
python -m trading_bot learn history     # Market regime history
python -m trading_bot learn metrics     # Performance metrics
```

## Commands

### 1. `learn inspect` - Current State Snapshot
Shows the latest market regime, adaptive weights, and recent decisions.

```powershell
python -m trading_bot learn inspect
```

**Output:**
```
================================================================================
LEARNING STATE INSPECTOR
================================================================================

📊 LATEST MARKET REGIME:
  Timestamp:    2026-01-23 16:57:41.744765
  Regime:       ranging
  Confidence:   90.3%
  Volatility:   0.141
  Trend Str:    0.097

🤖 LATEST ADAPTIVE DECISION:
  Timestamp:    2026-01-23 16:57:41.744765
  Regime:       ranging (confidence: 90.3%)
  Adjusted Weights:
    mean_reversion_rsi  : 0.5864
    breakout_atr        : 0.2068
    momentum_macd_volume: 0.2068
  Explanation:
    adjusted_weights    : {'mean_reversion_rsi': 0.5864, ...}
    learned_weights     : {'mean_reversion_rsi': 0.4602, ...}
    regime              : ranging
    strategy_analysis   : {}

📈 RECENT PERFORMANCE:
  [1] 2026-01-23 16:57:41 | Sharpe: -0.03 | DD: -0.1% | WR:  0.0%
```

### 2. `learn history` - Regime History
Shows the timeline of detected market regimes.

```powershell
python -m trading_bot learn history [--limit 20]
```

**Output:**
```
================================================================================
REGIME HISTORY
================================================================================

Timestamp            Regime          Confidence   Volatility   Trend
2026-01-23 12:30:45  trending_up     85.2%        0.102        0.654
2026-01-23 12:35:20  trending_up     87.1%        0.098        0.672
2026-01-23 12:40:15  ranging         88.5%        0.089        0.145
2026-01-23 12:45:30  ranging         90.3%        0.141        0.097
```

**Regimes Detected:**
- `trending_up` - Uptrend with strong momentum
- `trending_down` - Downtrend with strong momentum
- `ranging` - Sideways consolidation
- `volatile` - High volatility regardless of direction
- `insufficient_data` - Not enough bars for analysis

### 3. `learn decisions` - Adaptive Decisions Timeline
Shows the complete history of adaptive learning decisions with strategy weight adjustments.

```powershell
python -m trading_bot learn decisions [--limit 10]
```

**Output:**
```
================================================================================
ADAPTIVE DECISIONS
================================================================================

[1] 2026-01-23 16:57:40.197854
    Regime: ranging (confidence: 90.3%)
    Weights:
      mean_reversion_rsi  : 0.5742
      breakout_atr        : 0.2129
      momentum_macd_volume: 0.2129
    Parameter Recommendations:
      mean_reversion_rsi:
        entry_oversold: -2 (was 35)
        exit_rsi: no change

[2] 2026-01-23 16:57:40.951090
    Regime: ranging (confidence: 90.3%)
    Weights:
      mean_reversion_rsi  : 0.5771
      breakout_atr        : 0.2115
      momentum_macd_volume: 0.2115
```

### 4. `learn metrics` - Performance Metrics
Shows performance snapshots over time (Sharpe, drawdown, win rate, etc.).

```powershell
python -m trading_bot learn metrics [--limit 5]
```

**Output:**
```
================================================================================
PERFORMANCE METRICS
================================================================================

Timestamp            Return     Sharpe    Drawdown   Win Rate    PF       Trades
2026-01-23 12:30:00   0.5%      0.23      -1.2%       50.0%      1.2       4
2026-01-23 12:35:00   0.6%      0.45      -0.8%       55.0%      1.5       9
2026-01-23 12:40:00   0.8%      0.67      -0.5%       60.0%      1.8      15
2026-01-23 12:45:00   1.2%      1.02      -0.2%       65.0%      2.1      20

Latest (Most Recent):
  Total Return:      1.2%
  Sharpe Ratio:      1.02
  Max Drawdown:      -0.2%
  Win Rate:          65.0%
  Profit Factor:     2.10
  Total Trades:      20
  Winning Trades:    13
  Losing Trades:     7
```

## Options

All commands support these options:

```powershell
--db DBPATH       # Path to SQLite database (default: trades.sqlite)
--limit N         # Number of recent records to show (default: varies by command)
```

**Examples:**
```powershell
# Use custom database
python -m trading_bot learn inspect --db my_trades.sqlite

# Show more history
python -m trading_bot learn history --limit 50
python -m trading_bot learn decisions --limit 20

# Show all metrics
python -m trading_bot learn metrics --limit 100
```

## Workflow: Real-Time Monitoring

### Setup
1. Open Terminal 1 and start paper trading
2. Open Terminal 2 and use learning CLI commands

### Monitor
- **Every 10 seconds:** Check `learn inspect` for latest regime
- **Every 30 seconds:** Review `learn decisions` for weight changes
- **Every 5 minutes:** Analyze `learn metrics` for performance trends

### Interpret
- **Regime changes** indicate market condition shifts (trending → ranging, etc.)
- **Weight adjustments** show learning responding to performance
- **Metric trends** reveal whether learning is improving returns
- **Anomalies** flag unusual patterns (unusual win streaks, sudden drawdowns)

## Example: Multi-Terminal Setup

**Terminal 1:**
```powershell
$ python -m trading_bot paper run --iterations 100 --no-ui --period 180d --interval 1d
iter=1 cash=100,000.00 equity=100,000.00 fills=0 rejections=0
iter=2 cash=100,000.00 equity=100,000.00 fills=0 rejections=0
```

**Terminal 2 (while Terminal 1 is running):**
```powershell
$ python -m trading_bot learn inspect
[Shows current regime and decision]

$ python -m trading_bot learn history | tail -5
[Shows last 5 regime observations]

$ python -m trading_bot learn metrics
[Shows performance trends]
```

## Audit Trail

All learning decisions are persisted to SQLite with full explanations:

- **Regime Detection** - Market analysis results (volatility, trend, support/resistance)
- **Adaptive Decisions** - Weight adjustments with reasoning
- **Performance Metrics** - Sharpe, drawdown, win rate snapshots
- **Parameter Recommendations** - Suggested strategy tuning

Access this via:
```powershell
python -m trading_bot learn inspect      # Human-readable summary
sqlite3 trades.sqlite                    # Raw database queries
```

## Integration with Paper Trading

Learning is **enabled by default** in the PaperEngine:
- `enable_learning: True` - Adaptive learning active
- `tune_weekly: True` - Weekly parameter tuning active

Disable if needed:
```python
# In engine config (not yet exposed via CLI, but can modify in code)
enable_learning=False
tune_weekly=False
```

## Architecture

```
Paper Trading Engine (Terminal 1)
    ↓
Market Data → 3 Strategies → Ensemble
    ↓
Regime Detection → Adaptive Decision
    ↓
SQLite Database (trades.sqlite)
    ↓
Learning CLI (Terminal 2)
    ↓
Human Monitoring & Analysis
```

Each iteration of paper trading:
1. Fetches OHLCV data
2. Detects market regime (volatility, trend, support/resistance)
3. Analyzes recent trades for patterns
4. Computes performance metrics
5. Blends learned weights with regime affinity (70% + 30%)
6. Logs decision with full explanation
7. Executes strategies with adjusted weights

The Learning CLI queries this database to provide real-time insights.

## Performance Interpretation

### Sharpe Ratio
- < 0: Strategy losing money
- 0-0.5: Acceptable for algorithmic trading
- 0.5-1.0: Good risk-adjusted returns
- > 1.0: Excellent risk-adjusted returns

### Drawdown
- How much equity can drop from peak
- -5%: Moderate drawdown
- -10%: Large drawdown
- -20%+: Very risky strategy

### Win Rate
- % of profitable trades
- 40-50%: Typical for trending strategies
- 60%+: Strong strategy
- Requires enough trades for statistical significance

### Profit Factor
- Gross profit / Gross loss
- 1.0: Breaks even
- 1.5: Good (50% more win than loss)
- 2.0+: Excellent (2x more win than loss)

## Troubleshooting

### "No regime history yet"
- Paper trading hasn't run long enough (need at least 2-3 iterations)
- Check that `enable_learning=True` (default)

### "No adaptive decisions yet"
- Same as above, or database is empty
- Verify trades.sqlite exists with: `ls -la trades.sqlite`

### Weights not changing
- Normal if no trades have occurred yet
- Regime-aware blending (70/30) gradually adjusts weights
- Takes multiple iterations to see significant changes

### Different database
- Use `--db` flag: `python -m trading_bot learn inspect --db my_trades.sqlite`

## Next Steps

- **Phase 4**: Alpaca integration for live trading
- **Future**: Add `learn export` to save learning history as CSV/JSON
- **Future**: Add `learn compare` to benchmark learning improvements

