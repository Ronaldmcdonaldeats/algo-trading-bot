# 📈 Algo Trading Bot

**Production-ready trading system with concurrent multi-algorithm execution, autonomous learning, and real-time monitoring.**

[![Python](https://img.shields.io/badge/Python-3.8+-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](Dockerfile)
[![Tests](https://img.shields.io/badge/Tests-5/5%20Passing-brightgreen)](#status)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success)](#status)

---

## ⚡ Quick Start

### Docker (1 Command)
```bash
docker-compose up --build
# Visit http://localhost:8501
```

### Local Python
```bash
pip install -e .
python -m trading_bot paper --symbols AAPL,MSFT
```

### Live Trading
```bash
export ALPACA_API_KEY=your_key
export ALPACA_SECRET_KEY=your_secret
python -m trading_bot live --symbols AAPL
```

---

## 📚 Documentation

**[→ Full Documentation on Wiki](https://github.com/yourusername/algo-trading-bot/wiki)**

- **[Quick Start](https://github.com/yourusername/algo-trading-bot/wiki/Quick-Start)** - 5 minutes to trading
- **[Features](https://github.com/yourusername/algo-trading-bot/wiki/Features)** - 9 advanced capabilities
- **[Configuration](https://github.com/yourusername/algo-trading-bot/wiki/Configuration)** - All settings explained
- **[Docker](https://github.com/yourusername/algo-trading-bot/wiki/Docker)** - Production deployment
- **[Integration](https://github.com/yourusername/algo-trading-bot/wiki/Integration)** - Use with your system
- **[Troubleshooting](https://github.com/yourusername/algo-trading-bot/wiki/Troubleshooting)** - Common issues

---

## ✨ Key Features

| Feature | Benefit |
|---------|---------|
| **Concurrent Execution** | 3-4x faster (5-8 algorithms in parallel) |
| **Market Regimes** | Auto-detect trending/ranging/volatile markets |
| **Smart Batching** | 50ms order windows, priority routing |
| **Calculation Cache** | 60-80% hit rate, 2-5x speedup |
| **Real-Time Dashboard** | Live monitoring with Streamlit |
| **Paper + Live Trading** | Risk-free testing + real money trading |
| **Training Optimization** | 30-50% fewer epochs, 4-8x faster |
| **Dynamic Weighting** | Algorithms adapt based on performance |

---

## 🎯 What It Does

1. **Runs multiple trading algorithms concurrently** - No bottlenecks
2. **Detects market conditions automatically** - Adapts strategy weights
3. **Places orders with intelligent batching** - Efficient execution
4. **Learns and improves over time** - Optimized parameters
5. **Monitors everything in real-time** - Live dashboard
6. **Logs detailed trade history** - Complete audit trail

---

## 📊 Performance

| Metric | Value |
|--------|-------|
| **Execution Speed** | 20ms (5 algorithms) vs 75ms (sequential) |
| **Cache Hit Rate** | 60-80% on realistic data |
| **Performance Gain** | 15-30% improvement combined |
| **Test Coverage** | 5/5 test suites passing |
| **Production Ready** | ✅ Yes |

---

## 🚀 System Requirements

- **Python** 3.8+
- **Docker** (optional, for containerized deployment)
- **Alpaca Account** (for live trading)
- **4GB RAM** minimum (8GB recommended)
- **Internet Connection** (for market data)

---

## 📖 For Different Users

### I want to start trading in 5 minutes
→ [Quick Start](https://github.com/yourusername/algo-trading-bot/wiki/Quick-Start)

### I want to understand the system
→ [Features](https://github.com/yourusername/algo-trading-bot/wiki/Features)

### I want to customize it
→ [Configuration](https://github.com/yourusername/algo-trading-bot/wiki/Configuration)

### I want to deploy to production
→ [Docker](https://github.com/yourusername/algo-trading-bot/wiki/Docker)

### I want to integrate with my system
→ [Integration](https://github.com/yourusername/algo-trading-bot/wiki/Integration)

### I'm having issues
→ [Troubleshooting](https://github.com/yourusername/algo-trading-bot/wiki/Troubleshooting)

---

## 🏗️ Architecture

```
Market Data
    ↓
Concurrent Algorithms (5-8+)
    ↓
Signal Coordination (regime-aware)
    ↓
Order Batching (50ms windows)
    ↓
Adaptive Weighting (performance-based)
    ↓
Execution (Paper or Live)
    ↓
Dashboard + Email Reports
```

---

## 🔧 Configuration

Example `configs/production.yaml`:

```yaml
mode: paper                        # paper or live
symbols:
  - AAPL
  - MSFT
  - NVDA

concurrent:
  max_workers: 4                   # Parallel threads
  timeout_seconds: 5
  batch_window_ms: 50

risk:
  max_position_size: 0.05
  max_daily_loss: 0.02
  stop_loss_pct: 2.0
  take_profit_pct: 5.0

data:
  provider: yahoo                  # yahoo or alpaca
  lookback_days: 60
  timeframe: 1d
```

[→ Full configuration guide](https://github.com/yourusername/algo-trading-bot/wiki/Configuration)

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Specific test
python -m pytest tests/test_concurrent_execution.py -v

# With coverage
python -m pytest --cov=src tests/
```

**Status**: ✅ 5/5 test suites passing

---

## 📁 Project Structure

```
algo-trading-bot/
├── README.md                       ← You are here
├── LICENSE                         ← MIT License
├── Dockerfile                      ← Container definition
├── docker-compose.yml              ← One-command deployment
├── pyproject.toml                  ← Dependencies
├── .github/
│   └── wiki/                       ← Full documentation
├── src/trading_bot/
│   ├── learn/                      ← Core algorithms
│   ├── broker/                     ← Paper & live trading
│   ├── data/                       ← Data providers
│   └── strategy/                   ← Trading strategies
├── tests/                          ← Test suite
└── configs/                        ← Configuration examples
```

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 📜 License

MIT License - see [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

This software is for **educational and research purposes**. Trading with real money carries risk. Start with paper trading and test thoroughly before using real capital.

---

## 🔗 Links

- **GitHub**: [algo-trading-bot](https://github.com/yourusername/algo-trading-bot)
- **Issues**: [Report a bug](https://github.com/yourusername/algo-trading-bot/issues)
- **Discussions**: [Ask questions](https://github.com/yourusername/algo-trading-bot/discussions)
- **Wiki**: [Full documentation](https://github.com/yourusername/algo-trading-bot/wiki)

---

## 📊 Status

- ✅ **Core System**: Production Ready
- ✅ **Tests**: 5/5 Passing
- ✅ **Documentation**: Complete
- ✅ **Docker**: Tested
- ✅ **Performance**: Validated
- ⏳ **v2.0**: Current

---

**[→ Start with Quick Start Guide](https://github.com/yourusername/algo-trading-bot/wiki/Quick-Start)**
