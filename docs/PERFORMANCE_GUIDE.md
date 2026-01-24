# Performance Guide

## Fast Trading with NASDAQ Stocks

### ⚡ TL;DR - Quick Commands

**Fastest possible backtest (2-5 min):**
```bash
python -m trading_bot backtest --nasdaq-top-100 --period 6mo --interval 1h
```

**Fast paper trading (real-time):**
```bash
python -m trading_bot paper --nasdaq-top-500 --max-symbols 100 --period 6mo
```

**Full optimization:**
```bash
python -m trading_bot backtest --nasdaq-top-500 --max-symbols 100 --period 1y --interval 1h
```

---

## Performance Tips

### 1. Choose Smaller Symbol Sets
```bash
# FAST - 100 symbols
--nasdaq-top-100

# MEDIUM - 500 symbols with limit
--nasdaq-top-500 --max-symbols 100

# SLOWER - 500 symbols
--nasdaq-top-500
```

### 2. Use Longer Intervals
```bash
# FAST - Hourly (fewer data points)
--interval 1h

# MEDIUM - 30-minute
--interval 30m

# SLOWER - 1-minute (more data points)
--interval 1m
```

### 3. Use Shorter Periods
```bash
# FAST - 3 months
--period 3mo

# MEDIUM - 6 months
--period 6mo

# SLOWER - 1 year
--period 1y
```

### 4. Enable Memory Mode
```bash
# Reduces memory usage but slightly slower
--memory-mode
```

### 5. Limit Data Downloads
```bash
# Only fetch data for top 50 symbols
--nasdaq-top-500 --max-symbols 50
```

---

## Real-World Timing Examples

### Example 1: Quick Proof of Concept
```bash
docker-compose exec app python -m trading_bot backtest \
  --nasdaq-top-100 \
  --period 3mo \
  --interval 1h
# Expected: ~1-2 minutes
```

### Example 2: Medium Optimization Testing
```bash
docker-compose exec app python -m trading_bot backtest \
  --nasdaq-top-500 \
  --max-symbols 100 \
  --period 6mo \
  --interval 1h
# Expected: ~10-15 minutes
```

### Example 3: Full Research (overnight run)
```bash
docker-compose exec app python -m trading_bot backtest \
  --nasdaq-top-500 \
  --period 1y \
  --interval 1h \
  --memory-mode
# Expected: ~25-40 minutes
```

### Example 4: Live Paper Trading (real-time)
```bash
docker-compose exec app python -m trading_bot paper \
  --nasdaq-top-500 \
  --max-symbols 200 \
  --period 6mo \
  --interval 1h
# No wait - trades in real-time
```

---

## System Requirements by Configuration

| Config | CPU | RAM | Time |
|--------|-----|-----|------|
| top-100, 3mo | 2 cores | 500MB | 1-2 min |
| top-100, 1y | 2 cores | 600MB | 3-5 min |
| top-500 (50 symbols), 1y | 4 cores | 1GB | 8-15 min |
| top-500, 1y | 8+ cores | 2GB+ | 20-40 min |
| top-500 + memory-mode | 4 cores | 1.2GB | 25-45 min |

---

## Optimization Checklist

- [ ] Use `--nasdaq-top-100` for quick tests
- [ ] Use `--max-symbols` to limit large universes
- [ ] Use `--interval 1h` instead of `1m`
- [ ] Use `--period 3mo` or `6mo` for faster runs
- [ ] Enable `--memory-mode` for very large runs
- [ ] Close other applications to free RAM
- [ ] Use Docker for consistent performance
- [ ] Run overnight for full 1-year backtests

---

## Expected Performance

### Backtest Speed
- **100 symbols, 3 months, hourly**: 1-2 minutes ⚡
- **100 symbols, 1 year, hourly**: 3-5 minutes ⚡
- **500 symbols (50 limit), 1 year**: 8-15 minutes ⚡⚡
- **500 symbols, 1 year**: 20-40 minutes ⚡⚡⚡

### Paper Trading
- Real-time execution regardless of symbol count
- No additional latency from data processing

### Live Trading
- Same as paper trading
- Ready for production with safety controls

---

## Docker Performance Tips

**Check available resources:**
```bash
docker stats
```

**Allocate more resources in docker-compose.yml:**
```yaml
services:
  app:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G
        reservations:
          cpus: '2'
          memory: 2G
```

**Run in background:**
```bash
docker-compose up -d
docker-compose logs -f app
```

---

## Troubleshooting Performance

**If backtest is slow:**
1. Reduce symbols: Use `--nasdaq-top-100` instead of `--nasdaq-top-500`
2. Reduce data: Use `--period 3mo --interval 1h`
3. Limit symbols: Add `--max-symbols 50`
4. Enable memory mode: Add `--memory-mode`

**If running out of memory:**
1. Enable memory mode: `--memory-mode`
2. Limit symbols: `--max-symbols 50`
3. Reduce period: `--period 3mo`
4. Use longer interval: `--interval 1h`

**If Docker container crashes:**
1. Check available disk space: `docker system df`
2. Clean up: `docker system prune`
3. Increase Docker memory in settings (Docker Desktop)
4. Run on host machine instead of Docker

---

## Production Deployment

For **live trading with 500 symbols:**
```bash
# Recommended settings
python -m trading_bot paper --nasdaq-top-500 --max-symbols 200 --period 6mo --interval 1h

# Or limit to mega-cap
python -m trading_bot paper --nasdaq-top-100 --period 6mo --interval 30m
```

For **24/7 backtesting pipeline:**
```bash
# Schedule overnight
0 20 * * * /usr/bin/python -m trading_bot backtest --nasdaq-top-500 --period 1y --interval 1h
```

---

## Optimization Results

With these settings, you can:
- ✅ Run quick backtests in 1-5 minutes
- ✅ Test 500 NASDAQ stocks in 20-40 minutes
- ✅ Trade in real-time with any symbol count
- ✅ Optimize parameters within a single session
- ✅ Deploy to production safely

**Questions?** See [NASDAQ_TRADING.md](NASDAQ_TRADING.md) for more examples.
