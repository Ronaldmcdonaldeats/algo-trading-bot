# 📈 Algo Trading Bot

Welcome to the **Algo Trading Bot** documentation! This is an intelligent Python-based trading bot with real-time web dashboard, autonomous learning system, and live trading capabilities.

## 🚀 Quick Links

- **[Quick Start](docs/QUICK_START.md)** - Get started in 5 minutes
- **[Docker Setup](docs/DOCKER_COMPOSE_GUIDE.md)** - Run with Docker Compose
- **[Web Dashboard](docs/WEB_DASHBOARD.md)** - Real-time metrics at localhost:5000
- **[GitHub Repository](https://github.com/Ronaldmcdonaldeats/algo-trading-bot)** - View source code

## 🎯 What Can You Do?

### 📊 **Real-Time Web Dashboard**
Monitor your trading activity live:
- Equity curve and performance metrics
- Holdings breakdown
- Open positions with P&L
- Sharpe ratio, drawdown, win rate
- Auto-refreshing every 2 seconds

**Access at:** `http://localhost:5000`

### 🤖 **Intelligent Trading**
- **RSI Mean Reversion** - Oversold/overbought signals
- **MACD Volume Momentum** - Trend confirmation
- **ATR Breakout** - Volatility-based sizing

### 🧠 **Autonomous Learning**
- Detects market regimes (trending, ranging, volatile)
- Adapts strategy weights based on performance
- Optimizes parameters weekly
- Complete audit trail

### 💰 **Paper & Live Trading**
- **Paper Trading** - Risk-free sandbox testing
- **Live Trading** - Real money with safety controls
- **Backtesting** - Historical analysis

---

## ⚡ Get Started Now

### Option 1: Docker (1 command)
```bash
docker-compose up --build
# Visit: http://localhost:5000
```

### Option 2: Local Installation
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m trading_bot paper --symbols AAPL,GOOGL,MSFT
```

---

## 📚 Documentation Structure

| Section | Purpose |
|---------|---------|
| **Getting Started** | Installation and first steps |
| **Features** | Core capabilities and examples |
| **Guides** | How-to tutorials for each mode |
| **Documentation** | Technical reference and architecture |

---

## 🛡️ Important Safety Notice

**Trading involves real financial risk.**

Before using with real money:
- ✅ Paper trade thoroughly first
- ✅ Understand all trading logic
- ✅ Set appropriate risk limits
- ✅ Comply with regulations (SEC/FINRA)
- ✅ Review safety controls

For details, see [Live Trading Guide](docs/LIVE_TRADING.md).

---

## 🤝 Community

- **Issues & Bugs**: [Report on GitHub](https://github.com/Ronaldmcdonaldeats/algo-trading-bot/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Ronaldmcdonaldeats/algo-trading-bot/discussions)
- **Contribute**: Pull requests welcome!

---

## 📄 License

MIT License - See LICENSE file for details

---

**Ready to get started?** → [Quick Start Guide](docs/QUICK_START.md)
