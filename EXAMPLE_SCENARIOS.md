# 📚 Example Trading Scenarios

This guide shows real-world examples of how to use the trading bot for different purposes.

## Scenario 1: Quick Test (5 minutes)

Test the system with minimal data and time:

```bash
python -m trading_bot paper \
    --symbols SPY \
    --period 30d \
    --iterations 3 \
    --start-cash 10000 \
    --no-ui
```

**What happens:**
- Downloads 1 month of data for SPY
- Runs 3 trading iterations
- Completes in ~30 seconds
- No learning (quick test)

**Good for:**
- Testing setup
- Verifying connectivity
- Quick validation

---

## Scenario 2: Backtest Single Strategy (10 minutes)

Test a specific strategy on historical data:

```bash
python -m trading_bot backtest \
    --symbols SPY,QQQ,IWM \
    --period 1y \
    --interval 1d \
    --strategy mean_reversion_rsi
```

**What happens:**
- Tests 1 year of data
- Uses only RSI mean reversion strategy
- Shows metrics (Sharpe, drawdown, win rate)
- Saves results to database

**Good for:**
- Optimizing parameters
- Testing strategy changes
- Historical analysis

---

## Scenario 3: Smart Stock Selection (15 minutes)

Auto-select best stocks and trade them:

```bash
python -m trading_bot auto \
    --iterations 5 \
    --start-cash 50000 \
    --period 60d \
    --interval 1d
```

**What happens:**
- Scores all 500 NASDAQ stocks
- Selects top 50 performers
- Trades them for 5 iterations
- Learns from results
- Saves strategies for next session

**Good for:**
- Daily/weekly automated trading
- Letting AI pick stocks
- Continuous learning

---

## Scenario 4: Specific Stocks (Hands-on Trading)

Trade your favorite stocks:

```bash
python -m trading_bot auto \
    --symbols AAPL,MSFT,GOOGL,AMZN,TSLA \
    --iterations 100 \
    --start-cash 100000 \
    --period 6mo
```

**What happens:**
- Trades only your selected stocks
- 100 trading iterations (daily for 100 days)
- 6 months of historical data
- Learns which strategies work best
- Builds hybrid strategies

**Good for:**
- Focused portfolios
- Testing specific ideas
- Long-term learning

---

## Scenario 5: Continuous 24/7 Learning

Run overnight for automatic learning:

**Cron job (Mac/Linux):**
```bash
# Edit crontab
crontab -e

# Add this line to run at 2 AM every day
0 2 * * * cd ~/projects/algo-trading-bot && python -m trading_bot auto --iterations 20 --no-ui
```

**Windows Task Scheduler:**
1. Open Task Scheduler
2. Create Basic Task
3. Set Trigger: "At 2:00 AM daily"
4. Set Action: Run `quick_start.bat`
5. Click OK

**What happens:**
- Runs every night while you sleep
- Learns from prior sessions
- Improves parameters
- Builds better strategies
- Wakes up smarter each day

**Good for:**
- Hands-off trading
- Continuous improvement
- 24/7 market coverage

---

## Scenario 6: Compare Multiple Strategies

Test different strategies against each other:

```bash
# Strategy 1: Mean Reversion
python -m trading_bot backtest --strategy mean_reversion_rsi --period 1y

# Strategy 2: Momentum
python -m trading_bot backtest --strategy momentum_macd_volume --period 1y

# Strategy 3: Breakout
python -m trading_bot backtest --strategy breakout_atr --period 1y

# Strategy 4: Ensemble (all combined)
python -m trading_bot backtest --strategy ensemble --period 1y
```

**What happens:**
- Tests each strategy independently
- Compares performance metrics
- Shows which works best
- Helps with strategy selection

**Good for:**
- Strategy research
- Performance benchmarking
- Decision making

---

## Scenario 7: Monitor Live Trading

Run with dashboard for real-time monitoring:

```bash
python -m trading_bot auto \
    --symbols SPY,QQQ,IWM,GLD,TLT \
    --period 60d \
    --no-ui  # No UI
```

In another terminal:
```bash
# Start web dashboard
python -m trading_bot.ui.web
# Visit http://localhost:5000
```

**What happens:**
- Trading runs in terminal
- Dashboard shows live updates
- See equity curve in real-time
- Monitor positions and P&L
- Watch learning progress

**Good for:**
- Active monitoring
- Tweaking parameters
- Learning observation

---

## Scenario 8: Aggressive Growth (High Risk)

Use larger leverage and more aggressive parameters:

```bash
python -m trading_bot auto \
    --symbols $(python -c "from trading_bot.data.nasdaq_symbols import get_nasdaq_symbols; print(','.join(get_nasdaq_symbols(100)))") \
    --start-cash 100000 \
    --period 90d \
    --iterations 200
```

**Configuration changes (edit configs/default.yaml):**
```yaml
risk:
  max_risk_per_trade: 0.15      # 15% risk (aggressive)
  stop_loss_pct: 0.03           # 3% stop loss (loose)
  take_profit_pct: 0.10         # 10% take profit (ambitious)
```

**What happens:**
- Takes larger positions
- More aggressive trading
- Higher potential returns
- Higher potential losses
- Faster learning

**Good for:**
- Testing aggressive strategies
- Small accounts (learning)
- Risk tolerance testing

**⚠️ Warning:** Only for testing! Use smaller positions in real trading.

---

## Scenario 9: Conservative Income (Low Risk)

Stable, predictable returns:

```bash
python -m trading_bot auto \
    --symbols SPY,QQQ,TLT,GLD,XLE \
    --start-cash 500000 \
    --period 60d \
    --iterations 50
```

**Configuration changes (edit configs/default.yaml):**
```yaml
risk:
  max_risk_per_trade: 0.02      # 2% risk (conservative)
  stop_loss_pct: 0.01           # 1% stop loss (tight)
  take_profit_pct: 0.03         # 3% take profit (modest)
```

**What happens:**
- Small positions
- Frequent winners
- Lower losses
- Steady growth
- Less volatility

**Good for:**
- Passive income
- Risk-averse traders
- Stable portfolios

---

## Scenario 10: Docker Deployment (Production)

Deploy everything with one command:

```bash
# Setup
git clone https://github.com/yourusername/algo-trading-bot
cd algo-trading-bot

# Configure
cp .env.example .env
# Edit .env with your Alpaca credentials

# Deploy
docker-compose up -d

# Monitor
docker-compose logs -f trading-bot
docker-compose logs -f dashboard

# Access dashboard
# Open http://localhost:5000 in browser

# Stop
docker-compose down
```

**What happens:**
- Builds Docker image
- Starts trading bot service
- Starts dashboard on port 5000
- Starts PostgreSQL database
- Runs with auto-restart
- Health checks every 30s

**Good for:**
- Production deployment
- Cloud hosting (AWS, GCP, etc.)
- Hands-off operation
- Team setups

---

## Quick Reference: Common Commands

```bash
# Auto-start (smartest way)
python -m trading_bot auto

# Paper trading with specific stocks
python -m trading_bot paper --symbols AAPL,MSFT --period 6mo

# Backtest historical data
python -m trading_bot backtest --period 1y --interval 1d

# Check learning progress
python -m trading_bot learn inspect

# View trading history
python -m trading_bot paper report

# View performance metrics
python -m trading_bot learn metrics

# Run tests
python -m pytest tests/

# View logs
tail -f bot_debug.log
```

---

## Choosing Your Scenario

| Goal | Scenario | Time | Risk |
|------|----------|------|------|
| Test setup | Scenario 1 | 5 min | None |
| Backtest strategy | Scenario 2 | 10 min | None |
| Auto-trade | Scenario 3 | 15 min | Paper |
| Specific stocks | Scenario 4 | Ongoing | Paper |
| Overnight learning | Scenario 5 | Auto | Paper |
| Compare strategies | Scenario 6 | 30 min | None |
| Monitor live | Scenario 7 | Ongoing | Paper |
| Aggressive | Scenario 8 | Ongoing | Paper |
| Conservative | Scenario 9 | Ongoing | Paper |
| Production | Scenario 10 | Ongoing | Production |

---

## Pro Tips

1. **Start with Scenario 1** - Verify everything works
2. **Then try Scenario 3** - Let AI pick stocks
3. **Run Scenario 5 overnight** - Build learning history
4. **Compare with Scenario 6** - See what works
5. **Switch to Scenario 9** - Conservative long-term

---

## Monitoring Your Trades

Always check:

```bash
# See recent trades
python -m trading_bot learn history --limit 20

# View performance metrics
python -m trading_bot learn metrics

# Check recent decisions
python -m trading_bot learn decisions

# Inspect learned strategies
python -c "from trading_bot.learn.strategy_learner import StrategyLearner; \
           learner = StrategyLearner(); \
           for name, strat in learner.learned_strategies.items(): \
               print(f'{name}: {strat.performance}')"
```

---

## Troubleshooting Scenarios

**Scenario isn't trading?**
- Check data downloaded: `ls data/`
- Check strategy signals: Add `--debug` flag
- Verify credentials: `echo $APCA_API_KEY_ID`

**Learning isn't working?**
- Need at least 5 trades
- Check: `ls -la .cache/strategy_learning/`
- View: `python -m trading_bot learn inspect`

**Dashboard not showing?**
- Check port 5000: `netstat -an | grep 5000`
- Restart: `docker-compose restart dashboard`

---

## Ready?

Pick a scenario and start trading!

```bash
python -m trading_bot auto
```

Happy trading! 🚀
