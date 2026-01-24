# Quick Start - 5 Minutes

Get your trading bot running in 5 minutes.

## Choose Your Path

### 🐳 Docker (Easiest)
```bash
# Clone repo
git clone https://github.com/yourusername/algo-trading-bot
cd algo-trading-bot

# Start with Docker
docker-compose up

# Visit dashboard
open http://localhost:5000
```

That's it! You're running the bot.

### 💻 Local Installation
```bash
# Requirements: Python 3.8+
python --version

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac/Linux

# Install bot
pip install -e .

# Run paper trading
python -m trading_bot paper --symbols AAPL,MSFT
```

### 🔌 Live Trading (Alpaca)
```bash
# Get API keys from https://alpaca.markets

# Set environment variables
export ALPACA_API_KEY="your_key"
export ALPACA_API_SECRET="your_secret"

# Run with Docker
docker-compose up
```

## What's Running?

✅ **Trading Algorithms**
- 5 core strategies automatically running
- Concurrent execution (5-8+ parallel)
- Real-time performance tracking

✅ **Dashboard** 
- Live at `http://localhost:5000`
- Shows all positions, trades, metrics
- Real-time updates

✅ **Paper Trading**
- Risk-free testing
- Unlimited virtual capital
- Real market data

## Next Steps

1. **See your trades**: Visit [http://localhost:5000](http://localhost:5000)
2. **Customize**: Check [Configuration Guide](../deployment/CONFIG.md)
3. **Go live**: Read [Live Trading Guide](../features/LIVE_TRADING.md)
4. **Learn more**: See [Full Documentation](../index.md)

## Common Commands

```bash
# Help
python -m trading_bot --help

# Paper trading with different symbols
python -m trading_bot paper --symbols AAPL,MSFT,GOOGL

# Use mock data (no API needed)
python -m trading_bot paper --use-mock

# Dashboard only
python -m trading_bot web

# Backtest
python -m trading_bot backtest --symbols AAPL --period 6mo
```

## Troubleshooting

**Docker error?** → See [Docker Troubleshooting](../deployment/TROUBLESHOOTING.md)

**Port 5000 in use?** → Change in `.env` or `docker-compose.yml`

**Need API keys?** → Get from [Alpaca](https://alpaca.markets)

**More help?** → [Full Troubleshooting Guide](../deployment/TROUBLESHOOTING.md)

---

**Done!** Now read [Features Guide](../features/NINE_FEATURES.md) to learn what the bot can do.
