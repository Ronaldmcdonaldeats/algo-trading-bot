# Installation Guide

Get the Algo Trading Bot running on your system.

## Prerequisites

- **Python 3.11+** - [Download here](https://www.python.org/downloads/)
- **Git** - For cloning the repository
- **Docker** (optional) - For containerized setup
- **Alpaca API Key** - [Get free paper trading account](https://alpaca.markets)

---

## Option 1: Local Installation (Recommended for Development)

### Step 1: Clone the Repository
```bash
git clone https://github.com/Ronaldmcdonaldeats/algo-trading-bot.git
cd algo-trading-bot
```

### Step 2: Create Virtual Environment
=== "Windows"
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

=== "macOS/Linux"
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    ```

### Step 3: Install Dependencies
```bash
pip install -U pip
pip install -e ".[dev]"
pip install flask flask-cors
```

### Step 4: Configure API Keys
Create `.env` file in project root:
```bash
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
```

Get your keys from: [Alpaca Dashboard](https://app.alpaca.markets)

### Step 5: Verify Installation
```bash
python -m trading_bot --help
```

Should show available commands.

---

## Option 2: Docker Installation (Recommended for Production)

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running

### Quick Start
```bash
git clone https://github.com/Ronaldmcdonaldeats/algo-trading-bot.git
cd algo-trading-bot
docker-compose up --build
```

Visit: `http://localhost:5000`

---

## Verification

### Test Installation
```bash
# Show version
python -m trading_bot --version

# Run help
python -m trading_bot --help

# List available strategies
python -m trading_bot paper --help
```

### First Run
=== "Local"
    ```bash
    python -m trading_bot paper \
        --symbols AAPL,GOOGL,MSFT \
        --period 6mo \
        --iterations 5
    ```

=== "Docker"
    ```bash
    docker-compose up
    # Visit http://localhost:5000
    ```

---

## Environment Variables

Create `.env` file with:

```bash
# Alpaca API credentials
ALPACA_API_KEY=PKC...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Database (optional)
DATABASE_URL=sqlite:///data/trades.sqlite

# Logging (optional)
LOG_LEVEL=INFO
```

---

## Troubleshooting

### ModuleNotFoundError
```bash
# Reinstall in editable mode
pip install -e ".[dev]"
```

### Port Already in Use
```bash
# Change port in docker-compose.yml or use:
docker-compose up --no-build -p mybot
```

### Alpaca Connection Error
- ✅ Verify API keys in `.env`
- ✅ Check internet connection
- ✅ Ensure using correct URL (paper vs live)
- ✅ Test with: `python -m trading_bot paper --symbols AAPL`

### Database Issues
```bash
# Reset database
rm data/trades.sqlite
# Restart bot
```

---

## Next Steps

1. **[Quick Start](QUICK_START.md)** - Run your first trade
2. **[Web Dashboard](WEB_DASHBOARD.md)** - Monitor live metrics
3. **[Paper Trading](PAPER_TRADING.md)** - Test strategies risk-free
4. **[Live Trading](LIVE_TRADING.md)** - Trade with real money (advanced)

---

## Getting Help

- 📖 [Read Documentation](../README.md)
- 🐛 [Report Issues](https://github.com/Ronaldmcdonaldeats/algo-trading-bot/issues)
- 💬 [Start Discussion](https://github.com/Ronaldmcdonaldeats/algo-trading-bot/discussions)
