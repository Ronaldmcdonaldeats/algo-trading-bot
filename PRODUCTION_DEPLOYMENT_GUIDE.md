# Production Deployment Guide

## Overview
This guide walks through deploying Gen 364 strategy from paper trading → live trading with full monitoring.

**Timeline: 2-3 weeks minimum**
- Weeks 1-2: Paper trading validation
- Week 3: Live trading with small positions
- Ongoing: Monitoring and retraining

---

## Phase 1: Paper Trading (Weeks 1-2)

### 1.1 Start Paper Trading Simulator
```bash
python scripts/paper_trading_simulator.py
```

**What it does:**
- Generates daily entry/exit signals
- Tracks P&L without real capital
- Compares actual vs backtest returns
- Monitors risk metrics

**Success Criteria:**
- ✓ Actual return within ±5% of backtest (+7.32%)
- ✓ Win rate > 40%
- ✓ Max drawdown < 15%
- ✓ Zero position violations
- ✓ Zero emergency alerts for 14+ consecutive days

### 1.2 Monitor Daily Performance
```bash
python scripts/monitoring_service.py
```

**Daily checklist:**
- [ ] Check P&L vs backtest target
- [ ] Review all executed trades
- [ ] Verify position limits respected
- [ ] Check for any alert emails
- [ ] Confirm price feed is fresh

**Expected output:**
```
Overall Status: HEALTHY
Broker: HEALTHY
Price Feed: HEALTHY
Strategy: HEALTHY (0 alerts)
```

### 1.3 Collect 2 Weeks of Data

Create a trading journal with:
- Entry signals (symbol, ML score, price)
- Exit signals (profit/loss reason)
- Daily P&L %
- Number of trades
- Risk metrics

**Example:**
```
Day 1: +0.32%, 3 trades (2W/1L), DD: -1.2%
Day 2: -0.15%, 2 trades (1W/1L), DD: -0.8%
...
Day 14: TOTAL: +4.8%, 42 trades (22W/20L), DD: -4.2%
```

### 1.4 Validate Against Backtest

Compare 2-week results:
- Backtest (14 days): +0.68% (7.32% annualized ÷ 52 weeks × 2)
- Paper Trading: Must be within ±5% → **-0.32% to +1.68% acceptable**

**Decision:**
- ✓ If within range → Proceed to Phase 2
- ✗ If outside range → Investigate, adjust parameters, restart Phase 1

---

## Phase 2: Production Configuration

### 2.1 Set Up .env File
```bash
cp .env.template .env
# Edit .env with your values
```

**Critical settings:**
```
MODE=paper              # DON'T set to live yet!
IB_ACCOUNT_ID=your_id
IB_API_KEY=your_key
IB_SECRET_KEY=your_secret
MAX_DAILY_LOSS_USD=5000
KILL_SWITCH_ENABLED=true
```

### 2.2 Generate Production Config
```bash
python scripts/production_config.py
```

**Output:** `config/production_deploy.json`

**Verify:**
- Broker settings correct
- Position limits reasonable
- Emergency controls active
- Monitoring enabled

### 2.3 Initialize Database

Docker will auto-initialize, but verify:
```bash
docker-compose exec postgres psql -U trading_user -d trading_bot -c "\dt"
```

Expected tables:
- trades (store executed trades)
- backtest_results
- trading_journal
- daily_performance
- risk_metrics
- strategy_parameters
- alerts

---

## Phase 3: Deploy with Docker

### 3.1 Build and Start Services
```bash
# Build images
docker-compose build

# Start all services
docker-compose up -d

# Verify all running
docker-compose ps
```

**Expected services:**
- ✓ postgres (port 5432)
- ✓ redis (port 6379)
- ✓ api (port 5001)
- ✓ dashboard (port 5000)
- ✓ strategy (background)
- ✓ monitor (background)

### 3.2 Access Dashboard
```
Browser: http://localhost:5000
```

**Dashboard sections:**
- Real-time P&L chart
- Trade log
- Risk metrics
- Alert summary
- Performance vs backtest

### 3.3 Monitor Health Check
```bash
curl http://localhost:5001/health
```

Expected response:
```json
{
  "status": "HEALTHY",
  "broker": "CONNECTED",
  "price_feed": "ACTIVE",
  "strategy": "RUNNING",
  "alerts": 0
}
```

---

## Phase 4: Live Trading (Week 3)

### 4.1 Start in Paper Mode (Days 1-3)
- Keep MODE=paper
- Full docker-compose running
- Monitor for 3 days without issues

**Success criteria:**
- Zero connection errors
- Consistent price updates
- Strategy generating signals
- Dashboard updates in real-time

### 4.2 Reduce Position Size
For first week of live trading, use **10% of planned size**:
```yaml
# config/evolved_strategy_gen364.yaml
position_size_pct: 0.005  # 0.5% instead of 5%
max_positions: 2          # 2 instead of 20
```

### 4.3 Switch to Live Mode
```bash
# Edit .env
MODE=live

# Restart services
docker-compose restart api strategy monitor
```

**Verification:**
- [ ] Mode shows as "LIVE" in dashboard
- [ ] Trades show in broker account
- [ ] No emergency alerts for 24 hours
- [ ] P&L tracking matches broker statement

### 4.4 Scale Up Gradually

**Week 1:** 10% of full size ✓ (monitor closely)
- Expected: ~+0.73% return (10% of backtest)
- Alert threshold: < -5% (kill switch)

**Week 2:** 50% of full size (if Week 1 on track)
- Expected: ~+3.66% return
- Cumulative: ~+4.4% expected

**Week 3+:** 100% of full size (if all weeks on track)
- Expected: ~+7.32% full backtest return

### 4.5 Daily Monitoring Checklist

**Every morning:**
```
[ ] Dashboard loads without errors
[ ] Price feed is current (< 1 hour old)
[ ] Broker connection shows CONNECTED
[ ] No CRITICAL alerts
[ ] P&L is within expected range
```

**Every evening:**
```
[ ] Close all open positions? NO (let strategy manage)
[ ] Review today's trades
[ ] Check any warning alerts
[ ] Verify cash available > minimum
[ ] No max loss/drawdown breaches
```

**Weekly:**
```
[ ] Compare P&L vs backtest expectations
[ ] Check risk metrics (concentration, exposure)
[ ] Review any failed orders
[ ] Backup trading journal
```

---

## Emergency Procedures

### Kill Switch Activation
Automatically triggered by:
- Max daily loss reached (-$5,000 or -5%)
- Max drawdown exceeded (-15%)
- 5 consecutive losing trades
- Broker connection lost > 5 minutes

**Manual activation:**
```bash
# Stop trading engine
docker-compose stop strategy

# Check alerts for reason
tail -f logs/alerts.json

# Review dashboard for details
# http://localhost:5000/alerts
```

### Circuit Breaker (24-hour wait)
After kill switch, trading resumes automatically after 24 hours.

**To resume earlier:**
```bash
# Manually restart
docker-compose start strategy

# ONLY after confirming why it stopped!
```

### Manual Position Closure
If immediate closure needed:
```bash
curl -X POST http://localhost:5001/positions/close_all \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Monitoring & Analytics

### Real-Time Dashboard
```
http://localhost:5000
```
Displays:
- Live equity curve
- Daily returns
- Current positions
- Risk metrics
- Recent trades

### API Endpoints
```bash
# Get account summary
curl http://localhost:5001/account

# Get daily performance
curl http://localhost:5001/performance?days=30

# Get risk metrics
curl http://localhost:5001/risk

# Get trade history
curl http://localhost:5001/trades?limit=100
```

### Database Queries
```bash
# Connect to postgres
docker-compose exec postgres psql -U trading_user -d trading_bot

# Sample queries:
SELECT DATE(trade_date), SUM(return_pct) 
FROM trades 
GROUP BY DATE(trade_date) 
ORDER BY DATE DESC;

SELECT * FROM alerts WHERE resolved = FALSE;

SELECT * FROM daily_performance 
WHERE ending_equity < starting_equity;
```

---

## Monthly Retraining

### First Monday of Each Month
```bash
# 1. Backup existing strategy
cp config/evolved_strategy_gen364.yaml \
   backups/evolved_strategy_gen364_$(date +%Y%m%d).yaml

# 2. Download new market data
python scripts/fetch_market_data.py

# 3. Run evolution on new data
python scripts/strategy_evolution_fast.py --generations 500

# 4. Validate new strategy
python scripts/validate_evolved_strategy.py

# 5. If improvement > 1%:
#    - Save new parameters
#    - Update config
#    - Restart strategy service
# 6. If no improvement:
#    - Keep existing strategy
#    - Document findings
```

---

## Troubleshooting

### Dashboard Not Updating
```bash
# Check API connection
curl http://localhost:5001/health

# Restart dashboard
docker-compose restart dashboard
```

### Strategy Not Trading
```bash
# Check logs
docker-compose logs strategy | tail -50

# Verify price feed
curl http://localhost:5001/price/AAPL

# Check broker connection status
curl http://localhost:5001/broker/status
```

### High Slippage
```bash
# Reduce order size
position_size_pct: 0.025  # From 0.05

# Use limit orders
order_type: limit
limit_offset_bps: 5  # 5 bps limit order

# Restart strategy
docker-compose restart strategy
```

### Risk Limit Violations
```bash
# Check current exposures
curl http://localhost:5001/risk/exposures

# Review recent trades
curl http://localhost:5001/trades?limit=20

# Adjust limits if needed
# Edit config/position_limits.yaml
# Restart services
```

---

## Rollback Procedure

If something goes wrong:

### Step 1: Stop All Trading
```bash
docker-compose stop strategy
```

### Step 2: Restore Previous Config
```bash
cp backups/evolved_strategy_gen364_YYYYMMDD.yaml \
   config/evolved_strategy_gen364.yaml
```

### Step 3: Close Positions (if needed)
```bash
curl -X POST http://localhost:5001/positions/close_all
```

### Step 4: Review Logs
```bash
docker-compose logs --tail=100
```

### Step 5: Restart Carefully
```bash
# In MODE=paper first
docker-compose restart strategy
```

---

## Success Metrics

### 4-Week Targets

| Metric | Target | Acceptable |
|--------|--------|-----------|
| Monthly Return | +2.4% | +0.2% to +4.6% |
| Sharpe Ratio | 1.05+ | 0.8+ |
| Win Rate | 46%+ | 40%+ |
| Max Drawdown | -6.7% | -15% max |
| Slippage Cost | <0.1% | <0.3% |

### Go/No-Go Decision Points

**After Paper Trading (Week 2):**
- ✓ Go Live if: Within ±5% of backtest, no violations
- ✗ No Go if: >5% variance or any risk violations

**After Week 1 Live (10% size):**
- ✓ Scale to 50% if: On track, no major issues
- ✗ Scale Back if: >5% divergence from backtest

**After Week 3 Live (50% size):**
- ✓ Full Size if: Cumulative in range, healthy system
- ✗ Hold at 50% if: Any concerns remain

---

## Contact & Support

For issues:
1. Check dashboard alerts
2. Review logs: `docker-compose logs`
3. Run health check: `curl http://localhost:5001/health`
4. Consult troubleshooting section above

---

**Remember:** The strategy has been validated through 1000 generations of evolution and extensive backtesting. Trust the process but monitor closely during transition to live trading.

**Good luck! 🚀**
