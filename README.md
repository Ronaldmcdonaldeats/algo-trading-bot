# 📈 Algo Trading Bot - Master System

A **production-ready** algorithmic trading bot with **all 9 advanced features fully integrated**, real-time dashboard, automated learning, and live trading via Alpaca.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-blue)](docker-compose.yml)
[![Tests: 55/55](https://img.shields.io/badge/Tests-55%2F55%20✓-green)](tests/)

## 🎯 9 Integrated Features

## 🎯 9 Integrated Features

| # | Feature | What It Does |
|---|---------|-------------|
| 1️⃣ | **Sentiment Analysis** | Analyzes news → Bullish/Bearish signals |
| 2️⃣ | **Equity Curve Analyzer** | Detects market regime → Uptrend/Downtrend |
| 3️⃣ | **Portfolio Analytics** | Checks diversification → Health score |
| 4️⃣ | **Kelly Criterion** | Optimal position sizing → Max profit |
| 5️⃣ | **Advanced Orders** | Bracket orders → Entry + TP + SL |
| 6️⃣ | **Email Reports** | Daily summaries → HTML inbox |
| 7️⃣ | **Tax Harvesting** | Finds losses → Automatic optimization |
| 8️⃣ | **WebSocket Data** | Real-time prices → 100ms updates |
| 9️⃣ | **Tearsheet Analysis** | Performance review → Sharpe, drawdown |

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended)

```bash
docker-compose up --build
```

Visit: **http://localhost:5000**

### Option 2: Local Installation

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1     # Windows
source .venv/bin/activate      # Mac/Linux

pip install -e ".[dev]"
python -m trading_bot
```

---

## 📊 What's Inside

### 📈 Real-Time Web Dashboard
- Live equity curve and performance metrics
- Holdings breakdown visualization
- Open positions with P&L tracking
- Sharpe ratio, max drawdown, win rate
- **Access at:** `http://localhost:5000`

### 🤖 Intelligent Trading
- **3 Core Strategies** - RSI, MACD, ATR
- **Multi-source Signals** - All 9 features analyze together
- **Professional Orders** - Bracket orders with risk management
- **Kelly Sizing** - Optimal position sizing
- **Tax Optimization** - Automatic loss harvesting

### 🧠 Autonomous Learning
- Market regime detection (trending, ranging, volatile)
- Adaptive strategy weighting based on performance
- Real-time metrics tracking
- Weekly parameter optimization
- Complete audit trail for compliance

---

## 📋 Common Commands

### Auto-Start (Recommended)
```bash
# Intelligent trading with all 9 features
python -m trading_bot auto

# Optional: customize settings
python -m trading_bot auto --iterations 100 --period 6mo
```

### Paper Trading
```bash
python -m trading_bot paper \
    --symbols AAPL,MSFT,GOOGL \
    --period 6mo
```

### Backtesting
```bash
python -m trading_bot backtest \
    --symbols SPY \
    --period 1y
```

### Live Trading (Real Money)
```bash
python -m trading_bot live \
    --symbols AAPL \
    --max-drawdown 5.0
```

---

## 📁 Documentation

| Guide | Purpose |
|-------|---------|
| [MASTER_SYSTEM_STATUS.md](docs/MASTER_SYSTEM_STATUS.md) | Complete system overview |
| [MASTER_INTEGRATION_GUIDE.md](docs/MASTER_INTEGRATION_GUIDE.md) | How all 9 features work together |
| [MASTER_QUICK_REF.md](docs/MASTER_QUICK_REF.md) | Copy-paste code examples |
| [FEATURES_9_ADVANCED.md](docs/FEATURES_9_ADVANCED.md) | Detailed feature documentation |
| [SMART_SELECTION.md](docs/SMART_SELECTION.md) | Automatic stock selection |
| [FINAL_STATUS.md](docs/FINAL_STATUS.md) | Learning system details |

**More in [docs/](docs/) folder →**

---

## 🏗️ Project Structure

```
algo-trading-bot/
├── src/trading_bot/
│   ├── strategy/
│   │   └── integrated_strategy.py     (450 lines) Master orchestrator
│   ├── ui/
│   │   ├── master_dashboard.py        (287 lines) Real-time display
│   │   └── web.py                     Web dashboard
│   ├── monitoring/
│   │   └── production_monitoring.py   (368 lines) Logging & alerts
│   ├── engine/                        Trading engine & strategies
│   ├── learn/                         Learning system
│   ├── broker/                        Alpaca integration
│   ├── db/                            SQLite layer
│   └── cli.py                         Command-line interface
├── tests/                             Unit & integration tests
├── docs/                              📖 All documentation
├── configs/                           Configuration files
├── data/                              Runtime data (trades, logs)
└── docker-compose.yml                 Docker setup
```

---

## ✨ Status

| Metric | Status |
|--------|--------|
| **Production Code** | 5,500+ lines ✅ |
| **Tests Passing** | 55/55 ✅ |
| **Features Integrated** | 9/9 ✅ |
| **Documentation** | 4,000+ lines ✅ |
| **Ready for Trading** | Yes ✅ |

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
pytest tests/ -v
```

### Lint Code
```bash
ruff check .
```

### Build Docker
```bash
docker build -t algo-trading-bot .
```

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
