# Docker Compose Web Dashboard - Setup Complete ✅

Your trading bot now has a web dashboard accessible at **http://localhost:5000**

## What's New

### 1. **Web Dashboard** (`src/trading_bot/ui/web.py`)
- Modern Flask web application with real-time metrics
- Beautiful dark-theme dashboard with gradient styling
- Live charts (Chart.js) for equity curves and holdings
- Position table showing all open trades
- Auto-refreshes every 2 seconds from backend

### 2. **Updated Docker Compose** (`docker-compose.yml`)
Three services now run:
- **web** (Port 5000) - Flask dashboard server
- **app** - Trading bot running paper trading
- **postgres** (Port 5432) - Database for trade history

### 3. **Updated Dockerfile**
- Added Flask and flask-cors dependencies
- Added curl for health checks
- Optimized for both web and trading bot modes

## Quick Start

```bash
# Build and start all services
docker-compose up --build

# View logs
docker-compose logs -f web

# Stop services
docker-compose down
```

Then open: **http://localhost:5000**

## Dashboard Features

### Metrics Display
- **Current Equity** - Total account value
- **Current P&L** - Profit/loss from starting balance
- **Sharpe Ratio** - Risk-adjusted returns
- **Max Drawdown** - Largest peak-to-trough decline
- **Win Rate** - % of winning trades
- **Total Trades** - Number of completed trades

### Charts
- **Equity Curve** - Real-time account value over time
- **Holdings Breakdown** - Pie chart of positions

### Positions Table
- Symbol, quantity, entry/current price
- Unrealized P&L and return %
- Updates every 2 seconds

## Customization

### Change trading symbols
Edit `docker-compose.yml`:
```yaml
command: ["python", "-m", "trading_bot", "paper", 
          "--symbols", "SPY,QQQ,IWM", "--period", "1y"]
```

### Change port
```yaml
ports:
  - "8080:5000"  # Now at http://localhost:8080
```

### Run backtest instead
```yaml
command: ["python", "-m", "trading_bot", "backtest",
          "--symbols", "AAPL,GOOGL,MSFT"]
```

## Files Modified/Created

✅ `src/trading_bot/ui/web.py` - New Flask web app
✅ `src/trading_bot/ui/__main__.py` - Module entry point
✅ `docker-compose.yml` - Updated with web service
✅ `Dockerfile` - Added Flask dependencies
✅ `docs/DOCKER_COMPOSE_GUIDE.md` - Detailed setup guide

## Architecture

```
┌──────────────────────┐
│  Browser (localhost) │
└──────────┬───────────┘
           │ HTTP
           ▼
┌──────────────────────┐
│   Flask Web Server   │  Port 5000
│  (ui/web.py)         │
└──────────┬───────────┘
           │ Shared Volume & Network
           ▼
┌──────────────────────────────┐
│   Trading Bot (paper.py)     │
│   - Runs strategies          │
│   - Updates metrics          │
│   - Persists trades          │
└──────────┬────────────────────┘
           │ TCP
           ▼
┌──────────────────────┐
│   PostgreSQL         │  Port 5432
│   Trade History      │
└──────────────────────┘
```

## API Endpoint

The web dashboard queries: `GET /api/data`

Returns JSON with:
```json
{
  "portfolio": {
    "equity": 102500.00,
    "cash": 50000.00,
    "holdings": {"AAPL": {...}, "GOOGL": {...}}
  },
  "prices": {"AAPL": 150.25, "GOOGL": 140.50},
  "sharpe_ratio": 1.23,
  "max_drawdown_pct": 0.05,
  "win_rate": 0.65,
  "num_trades": 12,
  "equity_history": [100000, 101000, 102500, ...]
}
```

## Troubleshooting

**Dashboard shows "Loading data..."**
- Wait 10-15 seconds for web server startup
- Check: `docker-compose logs web`

**Port 5000 already in use**
- Change port in docker-compose.yml
- Or stop other services: `lsof -i :5000`

**Data not updating**
- Ensure app service is running: `docker-compose ps`
- Check app logs: `docker-compose logs app`

**Browser refresh shows blank page**
- Clear cache or use Ctrl+Shift+Delete
- Try incognito/private browsing mode

Enjoy your real-time trading dashboard! 🚀
