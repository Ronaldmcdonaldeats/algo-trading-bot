# algo-trading-bot
Python-based algorithmic trading bot scaffold with backtesting + paper trading foundations.

## Safety / compliance
This repository is a software template. Trading involves risk. Ensure you comply with all broker rules and applicable regulations (SEC/FINRA/etc.).

## Quickstart (Windows PowerShell)
1) Create a venv
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
2) Install
```powershell
python -m pip install -U pip
python -m pip install -e ".[dev]"
```
3) Lint
```powershell
ruff check .
```
4) Run tests
```powershell
pytest
```
5) Run CLI help
```powershell
python -m trading_bot --help
```

## Project layout
- `src/trading_bot/` - library + CLI
- `configs/` - YAML configuration
- `tests/` - unit tests
- `notebooks/` - research notebooks

## Features (Phase 4 Complete ✅)

### Live Trading with Alpaca
- **Paper Trading Mode** - Test strategies on Alpaca sandbox (no real money)
- **Live Trading Mode** - Real money trading with safety controls
- **Market Data Integration** - Historical and real-time data from Alpaca
- **Order Management** - Market and limit orders with execution tracking
- **Portfolio Management** - Real-time cash, positions, and equity tracking
- **Safety Controls** - Drawdown kill switch, daily loss limits, position sizing
- **Risk Management** - Automated controls prevent catastrophic losses
- **CLI Integration** - Simple commands for paper and live trading

### Trading Strategies
- **RSI Mean Reversion** - Oversold entry (configurable RSI threshold), fixed exit
- **MACD+Volume Momentum** - Crossover signals with volume confirmation
- **ATR Breakout** - Resistance breaks with ATR multiplier sizing

### Autonomous Learning System
- **Market Regime Detection** - Detects trending/ranging/volatile conditions with confidence scoring
- **Adaptive Strategy Selection** - Blends learned weights (70%) with regime affinity (30%)
- **Performance Analytics** - Sharpe ratio, max drawdown, win rate, profit factor tracking
- **Trade Pattern Recognition** - Win/loss streak detection, anomaly alerts
- **Autonomous Parameter Optimization** - Bounded adjustments for RSI, MACD, ATR parameters
- **Complete Audit Trail** - Full decision logging with explanations for compliance

### Ensemble Learning
- **Bandit Algorithm** - ExponentialWeightsEnsemble with reward-driven weight updates
- **Weekly Tuning** - Grid search on strategy parameters with bounded ranges
- **State Persistence** - All decisions, regime history, metrics logged to SQLite

## Running with Learning System

### Default (Learning Enabled)
```powershell
python -m trading_bot paper run --iterations 10 --no-ui --period 1y --interval 1d
```

### Concurrent Monitoring (New!)
While paper trading is running, inspect learning state in another terminal:

```powershell
# Terminal 1: Start paper trading
python -m trading_bot paper run --iterations 100 --no-ui --period 180d --interval 1d

# Terminal 2 (while Terminal 1 is running): Monitor learning
python -m trading_bot learn inspect        # Current regime + weights + recent decisions
python -m trading_bot learn history        # Market regime history
python -m trading_bot learn decisions      # Adaptive decision timeline
python -m trading_bot learn metrics        # Performance snapshots
```

### Demo Script
```powershell
# Run complete demo with learning monitoring
.\demo_learning_monitoring.ps1
```

### Output Example
```
iter=1 cash=100,000.00 equity=100,000.00 fills=0 rejections=0
iter=2 cash=100,000.00 equity=100,000.00 fills=0 rejections=0
iter=3 cash=100,000.00 equity=100,000.00 fills=0 rejections=0

# Learning CLI Output:
╭─ LATEST MARKET REGIME
│  Regime:       ranging (90.3% confidence)
│  Volatility:   0.141
│  Trend Str:    0.097
│
├─ LATEST ADAPTIVE DECISION
│  Adjusted Weights:
│    mean_reversion_rsi  : 0.5864
│    breakout_atr        : 0.2068
│    momentum_macd_volume: 0.2068
│
└─ EXPLANATION
   Blended 70% learned weights + 30% regime affinity
```

### Learning Data (SQLite)
- `regime_history` - Market regime observations
- `adaptive_decisions` - Learning decisions + explanations
- `performance_metrics` - Performance snapshots

## Architecture

```
Market Data (OHLCV)
         ↓
  [3 Strategies]
         ↓
  [Ensemble Learning] → Weighted signal
         ↓
  [Regime Detector] → Market condition
         ↓
  [Trade Analyzer] → Patterns + performance
         ↓
  [Adaptive Controller] → Blended weights + recommendations
         ↓
  [PaperEngine] → Execution + logging
  [AlpacaBroker] → Live order execution (Phase 4)
  [SafetyControls] → Risk management (Phase 4)
```

## Documentation

- **Phase 3 - Learning System**: See [PHASE_3_AND_CLI_COMPLETE.md](PHASE_3_AND_CLI_COMPLETE.md)
- **Phase 4 - Alpaca Live Trading**: See [PHASE_4_IMPLEMENTATION_COMPLETE.md](PHASE_4_IMPLEMENTATION_COMPLETE.md)
- **Phase 4 Quick Start Guide**: See [PHASE_4_QUICK_START.md](PHASE_4_QUICK_START.md)

## Phase 4: Live Trading with Alpaca

### Paper Trading (Sandbox - No Real Money)
```bash
python -m trading_bot live paper \
    --config configs/default.yaml \
    --symbols AAPL MSFT \
    --period 30d \
    --interval 1d \
    --iterations 5
```

### Live Trading (Real Money - Requires Safety Confirmation)
```bash
python -m trading_bot live trading \
    --config configs/default.yaml \
    --symbols AAPL \
    --enable-live \
    --max-drawdown 5.0 \
    --max-daily-loss 2.0 \
    --iterations 10
```

**Safety Features**:
- ✅ Explicit user confirmation required (`--enable-live` flag)
- ✅ Warning banner displayed before trading
- ✅ Drawdown kill switch (stops if drawdown exceeds limit)
- ✅ Daily loss limit enforcement
- ✅ All trades audited in database

For detailed setup instructions, see [PHASE_4_QUICK_START.md](PHASE_4_QUICK_START.md).

## Roadmap (Phase 5+)

- **Phase 5 - Backtesting**: Walk-forward optimization, Monte Carlo robustness
- **Phase 6 - Monitoring**: Streamlit dashboard, performance alerts, drawdown warnings
- **Phase 7 - Risk Controls**: Max 2% risk/trade, 1.5% stop loss, 3% take profit, sector diversification
