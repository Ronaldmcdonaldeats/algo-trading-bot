# 📈 Algo Trading Bot - Documentation

Welcome to the **Algo Trading Bot** - a production-ready, intelligent trading system with concurrent multi-algorithm execution, autonomous learning, and real-time monitoring.

## 🚀 Getting Started

**New here?** Start with these:
- [Quick Start (5 min)](getting-started/QUICK_START.md) - Get running immediately
- [Installation Guide](getting-started/INSTALLATION.md) - Detailed setup
- [First Trade](getting-started/FIRST_TRADE.md) - Your first trading session

## 📚 Documentation by Topic

### Core Features
- [9 Advanced Features Overview](features/NINE_FEATURES.md) - All 9 features explained
- [Trading Strategies (ATR, RSI, MACD)](features/STRATEGIES.md)
- [Paper Trading](features/PAPER_TRADING.md) - Risk-free testing
- [Live Trading with Alpaca](features/LIVE_TRADING.md)
- [Real-Time Dashboard](features/DASHBOARD.md)

### Advanced Features
- [Concurrent Multi-Algorithm Execution](advanced/CONCURRENT_EXECUTION.md) - 3-4x faster
- [Training Optimization](advanced/TRAINING_OPTIMIZATION.md) - Adaptive learning
- [Market Regime Detection](advanced/MARKET_REGIMES.md) - Auto-adapt to market
- [Dynamic Ensemble Weighting](advanced/DYNAMIC_ENSEMBLE.md) - Intelligent allocation
- [Integration Guide](advanced/INTEGRATION.md) - Integrate into existing systems

### Deployment & Operations
- [Docker Deployment](deployment/DOCKER.md) - Production ready
- [Configuration Guide](deployment/CONFIG.md) - Environment setup
- [Monitoring & Health Checks](deployment/MONITORING.md)
- [Troubleshooting Guide](deployment/TROUBLESHOOTING.md)

### Developer Resources
- [API Reference](api-reference/ORCHESTRATOR.md)
- [Performance Tuning](advanced/PERFORMANCE.md)
- [Custom Strategies](examples/CUSTOM_STRATEGY.md)

## 🎯 Feature Matrix

| Feature | Status | Docs |
|---------|--------|------|
| Paper Trading | ✅ | [Guide](features/PAPER_TRADING.md) |
| Live Trading (Alpaca) | ✅ | [Guide](features/LIVE_TRADING.md) |
| Concurrent Execution (5-8 algos) | ✅ | [Guide](advanced/CONCURRENT_EXECUTION.md) |
| Training Optimization | ✅ | [Guide](advanced/TRAINING_OPTIMIZATION.md) |
| Dashboard | ✅ | [Guide](features/DASHBOARD.md) |
| Market Regimes | ✅ | [Guide](advanced/MARKET_REGIMES.md) |
| Docker | ✅ | [Guide](deployment/DOCKER.md) |
| Email Reports | ✅ | [Guide](features/ADVANCED_FEATURES.md) |

## 💡 Quick Reference

**Command Line:**
```bash
# Paper trading
python -m trading_bot paper --symbols AAPL,MSFT

# Start training
python -m trading_bot train --period 6mo

# Run dashboard
python -m trading_bot web

# Docker
docker-compose up
```

## 🔍 Need Help?

| Question | Answer |
|----------|--------|
| **Getting started?** | → [Quick Start](getting-started/QUICK_START.md) |
| **Deployment issue?** | → [Troubleshooting](deployment/TROUBLESHOOTING.md) |
| **API question?** | → [API Docs](api-reference/ORCHESTRATOR.md) |
| **Performance optimization?** | → [Performance Guide](advanced/PERFORMANCE.md) |

## 📊 System Status

- **Version**: 2.0 (Production Ready)
- **Python**: 3.8+
- **Tests**: 55+ passing
- **Performance**: 3-4x faster with concurrent execution
- **Updated**: January 2026

---

**GitHub**: [algo-trading-bot](https://github.com/yourusername/algo-trading-bot) | **Issues**: [Report a bug](https://github.com/yourusername/algo-trading-bot/issues)

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
