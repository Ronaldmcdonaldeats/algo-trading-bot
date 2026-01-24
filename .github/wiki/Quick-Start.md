# Quick Start

Get the trading bot running in 5 minutes.

---

## Option 1: Docker (1 Command)

### Prerequisites
- Docker Desktop installed ([get it here](https://www.docker.com/products/docker-desktop))

### Setup
```bash
git clone https://github.com/yourusername/algo-trading-bot.git
cd algo-trading-bot

# Start
docker-compose up --build

# Access dashboard
open http://localhost:8501
```

### What's Running
- Trading bot (paper trading mode)
- Real-time dashboard
- 4 concurrent algorithms
- Market data provider

**Time**: 2 minutes

---

## Option 2: Local Python

### Prerequisites
- Python 3.8+ installed

### Setup
```bash
git clone https://github.com/yourusername/algo-trading-bot.git
cd algo-trading-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Start trading (paper mode)
python -m trading_bot paper --symbols AAPL,MSFT,NVDA
```

**Time**: 3 minutes

---

## Option 3: Live Trading (Real Money)

### Prerequisites
- Alpaca account ([create free](https://alpaca.markets))
- API keys from Alpaca dashboard

### Setup
```bash
# Set API keys
export ALPACA_API_KEY=your_actual_key
export ALPACA_SECRET_KEY=your_actual_secret

# Start live trading (⚠️ real money!)
python -m trading_bot live --symbols AAPL,MSFT
```

**⚠️ Warning**: This trades with real money. Start with paper trading first!

**Time**: 2 minutes (after setup)

---

## What Happens Next

### Paper Trading Mode
1. Bot connects to market data
2. Loads 4 trading algorithms
3. Runs in 50ms cycles
4. Dashboard updates every 2 seconds
5. All trades are simulated (no real money)

### Dashboard
- Access at: `http://localhost:8501` (Docker) or `http://localhost:8000` (Local)
- Shows: Real-time P&L, algorithm signals, market regime
- Updates: Every 2 seconds
- Features: Performance metrics, trade history, risk metrics

### Next Steps
1. **Monitor for 5-10 minutes** - Watch the system trade
2. **Review [Configuration](Configuration)** - Customize symbols and risk
3. **Run for 1-2 weeks** in paper mode before going live
4. **Read [Features](Features)** - Understand what it can do

---

## Common Commands

```bash
# Paper trading with specific symbols
python -m trading_bot paper --symbols AAPL,TSLA,AMZN

# Live trading (real money!)
python -m trading_bot live --symbols AAPL

# Backtest historical data
python -m trading_bot backtest --start 2023-01-01 --end 2024-01-01

# Stop the bot
Ctrl+C

# View logs
docker-compose logs -f  # Docker
tail -f trading_bot.log  # Local
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **Port 8501 in use** | Stop other containers or change port in docker-compose.yml |
| **Can't connect to market data** | Check internet connection and data provider |
| **Dashboard won't load** | Wait 10 seconds for app to start, refresh browser |
| **API key errors** | Check environment variables: `echo $ALPACA_API_KEY` |

---

## Next

- **Configuration**: [Customize settings](Configuration)
- **Features**: [What can it do?](Features)
- **Deployment**: [Production setup](Docker)
- **Integration**: [Use with your system](Integration)
