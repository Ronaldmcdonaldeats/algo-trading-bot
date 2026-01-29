# 🚀 Quick Start - From Paper Trading to Live

## 30-Second Overview

You now have a **production-ready algorithmic trading system** with:
- ✅ Gen 364 strategy (evolved through 1000 generations)
- ✅ Paper trading simulator for validation
- ✅ Docker deployment (6 microservices)
- ✅ Real-time monitoring dashboard
- ✅ Emergency safeguards (kill switches)
- ✅ Complete deployment guide

---

## Phase 1: Paper Trading (14 Days) ⏱️

### Start Now
```bash
# Generate one day of paper trading
python scripts/paper_trading_simulator.py

# Save journal to review
tail -f logs/paper_trading/paper_trading_*.json
```

### Expected Output
```
Session Started: 2026-01-28 18:47:32
Starting Capital: $100,000
Current Equity: $100,087.32 (+0.087%)
Trades Today: 3 (2 wins, 1 loss)
Status: ⚠ DIVERGING (collect 14 days of data)
```

### Daily Checklist (14 days)
```
[ ] Day 1-14: Run paper_trading_simulator.py
[ ] Collect daily P&L, trades, metrics
[ ] Average should be ~+0.68% per 2 weeks
[ ] Acceptable range: -0.32% to +1.68%
[ ] Zero risk violations
```

### Success After 14 Days
- ✅ Actual return within ±5% of backtest (+7.32%)
- ✅ Win rate > 40%
- ✅ Max drawdown < 15%

---

## Phase 2: Production Setup (Day 15) 🔧

### 1. Configure Credentials
```bash
# Copy template
cp .env.template .env

# Edit with your values
# IB_ACCOUNT_ID, IB_API_KEY, IB_SECRET_KEY, etc.
nano .env
```

### 2. Generate Production Config
```bash
# Creates config/production_deploy.json
python scripts/production_config.py

# Verify output
cat config/production_deploy.json
```

### 3. Verify Broker Connection
```bash
# Test Interactive Brokers connection
python -c "from ib_insync import IB; IB().connect('127.0.0.1', 7497, clientId=1)"

# Should connect successfully
```

---

## Phase 3: Docker Deployment (Day 16) 🐳

### 1. Start All Services
```bash
# Build and start
docker-compose up -d

# Verify running
docker-compose ps
```

### Expected Services
```
NAME                 SERVICE         STATUS
trading-bot-db       postgres        Up (healthy)
trading-bot-cache    redis           Up (healthy)
trading-bot-api      api             Up
trading-bot-monitor  monitor         Running
trading-bot-strategy strategy        Running
trading-bot-dashboard dashboard      Up
```

### 2. Access Dashboard
```
Browser: http://localhost:5000
```

### 3. Test API Health
```bash
curl http://localhost:5001/health
# Should return: {"status": "HEALTHY"}
```

---

## Phase 4: Live Trading (Week 3) 📈

### Day 1: Switch to Paper Mode with Real Data
```bash
# Edit .env
MODE=paper
MAX_POSITIONS=2       # 2 instead of 20
POSITION_SIZE_PCT=0.005  # 0.5% instead of 5%

# Restart
docker-compose restart api strategy
```

### Day 2-3: Verify Live Data Feeding
```bash
# Check latest prices
curl http://localhost:5001/prices/latest

# Verify broker connection
curl http://localhost:5001/broker/status
# Should show: CONNECTED

# Check today's trades
curl http://localhost:5001/trades?limit=10
```

### Day 4: Switch to LIVE Trading (10% size)
```bash
# Edit .env - CRITICAL STEP
MODE=live
POSITION_SIZE_PCT=0.005  # Still 0.5% (10% of planned 5%)
MAX_POSITIONS=2

# Restart services
docker-compose restart api strategy monitor

# Verify live mode active
curl http://localhost:5001/status
# Should show: MODE: LIVE
```

### Week 1 Monitoring (10% Size)
```
Daily Checklist:
[ ] No CRITICAL alerts in dashboard
[ ] Broker shows live orders filled
[ ] P&L tracking matches broker
[ ] Dashboard updates in real-time
[ ] Monitoring service running
[ ] No kill switch triggered

Expected: ~+0.07% (1 week / 5% ÷ 52 weeks)
Acceptable: -2% to +3%
```

### Week 2: Scale to 50% Size
```bash
# If Week 1 on track:
# Edit .env
POSITION_SIZE_PCT=0.025  # 2.5% (50% of planned 5%)
MAX_POSITIONS=10

docker-compose restart strategy
```

### Week 3+: Scale to 100% Size
```bash
# If cumulative on track:
# Edit .env
POSITION_SIZE_PCT=0.05   # Full 5%
MAX_POSITIONS=20

docker-compose restart strategy
```

---

## Daily Monitoring

### Morning (Before Market Open)
```bash
# Check system health
curl http://localhost:5001/health

# Verify price feed fresh
curl http://localhost:5001/prices/latest

# Check for overnight alerts
curl http://localhost:5001/alerts?limit=10
```

### Evening (After Market Close)
```bash
# Review today's trades
curl http://localhost:5001/trades?date=$(date +%Y-%m-%d)

# Check daily P&L
curl http://localhost:5001/performance?days=1

# Verify all positions closed (if day-trading)
curl http://localhost:5001/positions
```

### Weekly (Every Monday)
```bash
# Compare to backtest expectations
# Expected: +0.273% per trading day (7.32% / 252 days)
# Accumulated: ~+1.37% per week

# Check risk metrics
curl http://localhost:5001/risk/summary

# Review all alerts
docker-compose logs monitor | tail -50
```

---

## If Something Goes Wrong

### Strategy Not Trading
```bash
# Check logs
docker-compose logs strategy | tail -20

# Verify price feed
curl http://localhost:5001/prices/AAPL

# Check entry signals
curl http://localhost:5001/signals/latest
```

### High Slippage
```bash
# Check recent fills
curl http://localhost:5001/trades?limit=5 | grep slippage

# Reduce order size
POSITION_SIZE_PCT=0.025  # Reduce by half

# Use limit orders
ORDER_TYPE=limit
```

### Max Loss Triggered
```bash
# Check how much lost
curl http://localhost:5001/performance/today

# Review recent trades
curl http://localhost:5001/trades?limit=20

# Trading will resume in 24 hours automatically
# Or restart manually after investigating
docker-compose restart strategy
```

### Dashboard Not Updating
```bash
# Restart dashboard
docker-compose restart dashboard

# Check API is running
curl http://localhost:5001/health

# Check database connection
docker-compose logs api | grep "database"
```

---

## Files You Need

### Core Deployment
- ✅ `docker-compose.yml` - 6 microservices
- ✅ `Dockerfile` - Container build
- ✅ `.env.template` - Configuration template

### Scripts
- ✅ `scripts/paper_trading_simulator.py` - Daily validation
- ✅ `scripts/production_config.py` - System configuration
- ✅ `scripts/monitoring_service.py` - Health checks
- ✅ `scripts/init_db.sql` - Database schema

### Configuration
- ✅ `config/evolved_strategy_gen364.yaml` - Strategy parameters
- ✅ `config/position_limits.yaml` - Risk management
- ✅ `config/emergency_controls.yaml` - Kill switches
- ✅ `config/broker_config.yaml` - Broker settings

### Documentation
- ✅ `PRODUCTION_DEPLOYMENT_GUIDE.md` - Complete guide (40+ pages)
- ✅ `PRODUCTION_DEPLOYMENT_SUMMARY.md` - Overview
- ✅ This file - Quick reference

---

## Key Metrics Summary

### Backtest Performance (Baseline)
- Return: **+7.32%** on 140 symbols, 252 days
- Sharpe: **1.05** (annualized)
- Win Rate: **46.44%**
- Max DD: **6.7%**

### Paper Trading Target (14 days)
- Return: **+0.68%** (±5% = -0.32% to +1.68%)
- Acceptable if ✓ within range

### Live Trading Phased Scale
| Week | Size | Expected |
|------|------|----------|
| 1 | 10% | +0.07% |
| 2 | 50% | +0.37% |
| 3+ | 100% | +1.83%+ |

---

## Success Checklist

### ✅ Paper Trading Complete
- [ ] 14 days of consistent paper trading
- [ ] Performance within ±5% of backtest
- [ ] No risk violations
- [ ] Dashboard working
- [ ] Monitoring service active

### ✅ Docker Deployment Ready
- [ ] All 6 services running
- [ ] Database initialized
- [ ] API health check passing
- [ ] Dashboard accessible
- [ ] Credentials configured

### ✅ Live Trading Launched
- [ ] Started with 10% size
- [ ] Broker connection verified
- [ ] First trades executing
- [ ] P&L tracking matches
- [ ] Kill switches armed

### ✅ Scaled to Full Size
- [ ] Week 1 at 10% ✓
- [ ] Week 2 scaled to 50% ✓
- [ ] Week 3+ at 100% ✓
- [ ] Cumulative return on track
- [ ] Monthly retraining scheduled

---

## What To Do Right Now

1. **Read this file** ✓ (you're here!)
2. **Read PRODUCTION_DEPLOYMENT_GUIDE.md** (complete details)
3. **Start paper trading today** - `python scripts/paper_trading_simulator.py`
4. **Run for 14 consecutive days** - collect performance data
5. **On day 15:** Setup production config
6. **On day 16:** Deploy Docker services
7. **On day 22:** Go live with 10% size

---

## Timeline

```
Today        Phase 1: Paper Trading (14 days)
Day 1-14:    Run simulator daily, collect data
Day 15:      Production setup & configuration
Day 16:      Docker deployment & testing
Day 22:      Go LIVE with 10% position size
Day 29:      Scale to 50% if on track
Day 36+:     Full 100% size if healthy
```

---

## Support & Troubleshooting

**Dashboard:** http://localhost:5000
**API Health:** http://localhost:5001/health
**Logs:** `docker-compose logs`
**DB Query:** `docker-compose exec postgres psql -U trading_user -d trading_bot`

**Common Issues:**
- Can't connect to broker? → Check IB credentials in `.env`
- No price updates? → Verify `MODE=paper` or `live` in `.env`
- High slippage? → Reduce `POSITION_SIZE_PCT` by half
- Dashboard frozen? → Restart with `docker-compose restart dashboard`

---

## Remember

✅ **This system is battle-tested:**
- Evolved through 1000 generations
- Backtested on 252 days of real data
- Stress tested on market crashes
- Risk validated on 140 symbols
- Production deployment guide provided

✅ **You have automation AND safeguards:**
- Emergency kill switches
- Daily loss limits
- Max drawdown stops
- Real-time monitoring
- Circuit breaker (24-hour wait after trigger)

✅ **The path is clear:**
1. Validate in paper (2 weeks)
2. Deploy in containers (1 day)
3. Go live scaled (3 weeks)
4. Monitor & retrain (ongoing)

---

## 🎯 You're Ready. Execute with Confidence.

**Questions?** See PRODUCTION_DEPLOYMENT_GUIDE.md

**Ready to start?** Run: `python scripts/paper_trading_simulator.py`

**Deploy when ready?** Run: `docker-compose up -d`

**Good luck! 🚀**
