# QUICK REFERENCE - Learning CLI

## All Commands

### 1. Current State
```powershell
python -m trading_bot learn inspect
```
Shows: Current regime, confidence, latest decision, adjusted weights

### 2. Decision Timeline
```powershell
python -m trading_bot learn decisions [--limit 10]
```
Shows: History of adaptive decisions with weight changes

### 3. Regime History
```powershell
python -m trading_bot learn history [--limit 20]
```
Shows: Timeline of detected market regimes (trending, ranging, volatile, etc.)

### 4. Performance Metrics
```powershell
python -m trading_bot learn metrics [--limit 5]
```
Shows: Sharpe ratio, drawdown, win rate, profit factor over time

## Multi-Terminal Setup

**Terminal 1: Start Paper Trading**
```powershell
python -m trading_bot paper run --iterations 50 --no-ui --period 180d --interval 1d
```

**Terminal 2: Monitor Learning (while Terminal 1 runs)**
```powershell
python -m trading_bot learn inspect
python -m trading_bot learn decisions
python -m trading_bot learn history
python -m trading_bot learn metrics
```

## Interpreting Output

### Regimes
- `trending_up` - Uptrend with strong momentum
- `trending_down` - Downtrend with strong momentum  
- `ranging` - Sideways consolidation
- `volatile` - High volatility
- `insufficient_data` - Not enough bars

### Weights
- **Adjusted Weights**: Current strategy weights (result of learning)
- **Learned Weights**: From ensemble bandit algorithm
- **Blend**: 70% learned + 30% regime affinity

### Metrics
- **Sharpe Ratio**: Risk-adjusted return (higher = better)
- **Drawdown**: Max peak-to-trough loss
- **Win Rate**: % of profitable trades
- **Profit Factor**: Gross profit / Gross loss (>1.5 is good)

## Options
```powershell
--db <path>      # Use different database (default: trades.sqlite)
--limit <N>      # Number of records to show (default: varies)
```

**Examples:**
```powershell
python -m trading_bot learn decisions --db backup.sqlite --limit 50
python -m trading_bot learn history --limit 100
```

## What's Happening Behind the Scenes

Each paper trading iteration:
1. Fetches market data
2. Detects market regime (volatility, trend, support/resistance)
3. Analyzes recent trades for patterns
4. Calculates performance metrics
5. Blends strategy weights (70% learned + 30% regime)
6. Logs decision to database
7. Executes trades with adaptive weights

The Learning CLI queries the database to show you real-time results.

## Troubleshooting

**"No regime history yet"**
- Paper trading hasn't run long enough
- Run at least 2-3 iterations

**"No adaptive decisions yet"**
- Same as above, or database is empty
- Check: `ls -la trades.sqlite`

**Weights not changing**
- Normal! 70/30 blending is gradual
- Takes multiple iterations to see changes

## Files

- Database: `trades.sqlite` (SQLite)
- Learning modules: `src/trading_bot/learn/`
- CLI code: `src/trading_bot/learn/cli.py`
- Engine integration: `src/trading_bot/engine/paper.py`

