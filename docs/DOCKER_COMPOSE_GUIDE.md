# Docker Compose Setup Guide

## Quick Start

### Start all services:
```bash
docker-compose up --build
```

### Access the services:

**Web Dashboard:** http://localhost:5000
- Real-time trading metrics
- Equity curve chart
- Holdings breakdown
- Open positions table
- Auto-refreshes every 2 seconds

**PostgreSQL:** localhost:5432
- User: `trading`
- Password: `trading`
- Database: `trading`

## Services

### 1. Web Service (Port 5000)
Runs the Flask web dashboard showing:
- Current equity and P&L
- Sharpe ratio, max drawdown, win rate
- Equity curve visualization
- Holdings breakdown chart
- Live positions table

The dashboard auto-updates every 2 seconds.

### 2. App Service
Runs the trading bot in paper trading mode:
- Trades AAPL, GOOGL, MSFT
- 6-month historical period
- Logs trades to the database
- Connects with the web service to share data

### 3. PostgreSQL Service (Port 5432)
Persistent database for trade history.

## Configuration

Edit `docker-compose.yml` to customize:

```yaml
# Change symbols (comma-separated)
command: ["python", "-m", "trading_bot", "paper", "--symbols", "AAPL,GOOGL,MSFT", "--period", "6mo"]

# Or run backtest instead
command: ["python", "-m", "trading_bot", "backtest", "--symbols", "SPY", "--period", "1y"]
```

## Volumes

- `.` → Entire project mounted at `/app`
- `./data` → SQLite database and logs stored locally
- `pgdata` → PostgreSQL data (persisted between runs)

## Health Checks

Both web and database services include health checks:
- Web: `curl http://localhost:5000/` every 10 seconds
- PostgreSQL: `pg_isready` check every 10 seconds

## Troubleshooting

### Access http://localhost:5000 and see "Cannot GET /"
- Wait 10-15 seconds for the web service to fully start
- Check logs: `docker-compose logs web`

### Database connection errors
- Ensure PostgreSQL service is healthy: `docker-compose ps`
- Check database credentials match your config

### Live data not updating in dashboard
- The web service needs data from the app service
- Both are connected through shared volumes and network
- Check app logs: `docker-compose logs app`

### Port already in use
- Change in `docker-compose.yml`:
  ```yaml
  ports:
    - "8000:5000"  # Use http://localhost:8000 instead
    - "5433:5432"  # PostgreSQL on 5433
  ```

## Stop services:
```bash
docker-compose down
```

## Restart services:
```bash
docker-compose restart
```

## View logs:
```bash
docker-compose logs -f web    # Follow web service logs
docker-compose logs -f app    # Follow trading app logs
```
