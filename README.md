# 📈 Algo Trading Bot

An intelligent Python-based algorithmic trading bot with real-time web dashboard, automated learning system, and live trading capabilities via Alpaca.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue)](docker-compose.yml)

## 🎯 Features

### 📊 Real-Time Web Dashboard
- Live equity curve and performance metrics
- Holdings breakdown visualization
- Open positions with P&L tracking
- Sharpe ratio, max drawdown, win rate
- Auto-refreshing every 2 seconds
- **Access at:** `http://localhost:5000`

### 🤖 Intelligent Trading Strategies
- **RSI Mean Reversion** - Oversold/overbought entry signals
- **MACD Volume Momentum** - Trend confirmation with volume
- **ATR Breakout** - Volatility-based position sizing

### 🧠 Autonomous Learning System
- Market regime detection (trending, ranging, volatile)
- Adaptive strategy weighting based on performance
- Real-time metrics: Sharpe, drawdown, win rate
- Weekly parameter optimization
- Complete audit trail for compliance

### 📱 Paper & Live Trading
- **Paper Trading** - Risk-free testing on Alpaca sandbox
- **Live Trading** - Real money with built-in safety controls
- **Backtesting** - Historical performance analysis
- **Portfolio Management** - Cash, positions, equity tracking

### 🛡️ Risk Management
- Automatic drawdown kill switch
- Daily loss limits
- Position sizing based on volatility
- Multi-level profit taking
- Time-based exits

### ⚡ NASDAQ Large-Scale Trading
- **Top 500 stocks** - Trade entire index segment
- **Top 100 stocks** - Diversified mega-cap portfolio
- **Optimized loading** - Fast symbol initialization
- **Memory efficient** - Handles large universes

**Quick example:**
```bash
python -m trading_bot paper --nasdaq-top-500 --period 6mo --interval 1h
python -m trading_bot backtest --nasdaq-top-100 --period 1y
```

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
docker-compose up --build
```

Visit: **http://localhost:5000**

All services start automatically:
- Web dashboard on port 5000
- PostgreSQL database on port 5432
- Trading bot running in background

### ⚡ Smart Automatic Stock Selection (FASTEST)

Auto-scores all 500 NASDAQ stocks and trades only the best performers:

```bash
# Select top 50 best stocks (1-2 min backtest)
docker-compose exec app python -m trading_bot backtest --auto-select --period 3mo --interval 1h

# Score and trade all 500 stocks (2-5 min)
docker-compose exec app python -m trading_bot paper --smart-rank --period 6mo --interval 1h

# Use past winners - gets faster each run
docker-compose exec app python -m trading_bot backtest --use-performance-history --select-top 50
```

**Features:** Parallel batch downloading • Intelligent scoring (4 metrics) • Auto-selection • Learning from past performance • 3-10x faster

📖 Details: [SMART_SELECTION.md](SMART_SELECTION.md)

### ⚡ Trading with Top 500 NASDAQ Stocks

```bash
# Backtest top 100 NASDAQ stocks (fast - ~2-5 min)
docker-compose exec app python -m trading_bot backtest --nasdaq-top-100 --period 1y

# Paper trade top 500 with symbol limit (optimized - ~10-20 min)
docker-compose exec app python -m trading_bot paper --nasdaq-top-500 --max-symbols 100 --period 6mo

# Full top 500 backtest (15-30 min)
docker-compose exec app python -m trading_bot backtest --nasdaq-top-500 --period 1y --interval 1h
```

### Option 2: Local Installation

```bash
# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows
source .venv/bin/activate   # Mac/Linux

# Install
pip install -U pip
pip install -e ".[dev]"

# Run paper trading
python -m trading_bot paper --symbols AAPL,GOOGL,MSFT --period 6mo

# Or start web dashboard
python -m trading_bot.ui.web
```

---

## 📋 Common Commands

### Paper Trading (No Real Money)
```bash
python -m trading_bot paper \
    --symbols AAPL,MSFT,GOOGL \
    --period 6mo \
    --iterations 50
```

### Backtesting
```bash
python -m trading_bot backtest \
    --symbols SPY \
    --period 1y
```

### Live Trading (Real Money)
```bash
python -m trading_bot live trading \
    --symbols AAPL \
    --max-drawdown 5.0 \
    --max-daily-loss 2.0
```

### Monitor Learning System
```bash
# In another terminal while trading runs:
python -m trading_bot learn inspect      # Current state
python -m trading_bot learn history      # Regime history
python -m trading_bot learn decisions    # Decision log
python -m trading_bot learn metrics      # Performance
```

---

## 🏗️ Project Structure

```
algo-trading-bot/
├── src/trading_bot/
│   ├── engine/          # Trading engine & strategies
│   ├── learn/           # Learning system & tuning
│   ├── broker/          # Alpaca integration
│   ├── ui/              # Web dashboard (Flask)
│   ├── db/              # SQLite database layer
│   ├── strategy/        # Trading strategies (RSI, MACD, ATR)
│   └── cli.py           # Command-line interface
├── docs/                # Documentation & guides
├── data/                # Runtime data (trades.sqlite, logs)
├── configs/             # YAML configuration
├── tests/               # Unit tests
└── docker-compose.yml   # Docker services
```

---

## 🔧 Configuration

Edit `configs/default.yaml`:

```yaml
strategies:
  - name: mean_reversion_rsi
    enabled: true
    rsi_threshold: 30
    
  - name: macd_volume_momentum
    enabled: true
    
  - name: atr_breakout
    enabled: true

risk:
  max_position_size: 0.05
  stop_loss_pct: 2.0
  take_profit_pct: 3.0
```

---

## 📊 Performance Metrics

The system tracks:
- **Sharpe Ratio** - Risk-adjusted returns
- **Max Drawdown %** - Largest peak-to-trough decline
- **Win Rate %** - Percentage of winning trades
- **Total Trades** - Number of completed trades
- **Current P&L** - Profit/loss from starting balance

---

## 🔐 Safety & Compliance

This is a software template for educational and testing purposes.

**Trading involves real financial risk.** Before using with real money:
- ✅ Understand all trading logic and risks
- ✅ Paper trade thoroughly first
- ✅ Review all broker terms and regulations
- ✅ Comply with SEC/FINRA regulations in your jurisdiction
- ✅ Set appropriate risk limits and drawdown controls
- ✅ Audit all trades post-execution

---

## 🛠️ Development

### Run Tests
```bash
pytest
```

### Lint Code
```bash
ruff check .
```

### Build Docker Image
```bash
docker build -t algo-trading-bot .
```

---

## 📚 Documentation

- [Docker Setup Guide](docs/DOCKER_COMPOSE_GUIDE.md)
- [Quick Start](docs/QUICK_START.md)
- [Optimization Summary](docs/OPTIMIZATION_SUMMARY.md)
- [Folder Structure](docs/FOLDER_STRUCTURE.md)

---

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push and create a pull request

---

## 📝 License

MIT License - See LICENSE file

---

## ⚠️ Disclaimer

This software is provided as-is for educational purposes. The author is not liable for trading losses or financial consequences. Always paper trade first and understand all risks before using real money.
