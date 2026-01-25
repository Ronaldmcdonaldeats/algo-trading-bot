# ⚡ Quick Start Guide for Monday Live Trading

## 🚀 Start Bot on Monday Morning (Before 9:30 AM)

### Fastest Way (Recommended)
```bash
cd c:\Users\Ronald\ mcdonald\projects\algo-trading-bot
docker-compose up -d
```
**That's it!** Bot starts automatically with 500 NASDAQ symbols.

### Watch Dashboard
```
Open browser: http://localhost:5000
Click "Logs" tab to see live trading activity
```

---

## 📊 What Bot Does on Monday

1. **8:00 AM** - Download 500 symbol data (~1.5-2 min)
2. **8:05 AM** - Score and select top 50 symbols (~40 sec)
3. **8:10 AM** - Dashboard ready, waiting for market open
4. **9:30 AM** - Market opens, bot starts trading
5. **4:00 PM** - Market closes, bot sleeps

---

## 🔑 Essential Commands

### Check if Running
```bash
docker-compose ps
# Should show 3 containers: trading-bot, dashboard, postgres
```

### View Live Logs
```bash
docker logs algo-trading-bot -f
# -f means follow (live updates)
```

### Stop Bot
```bash
docker-compose down
```

### Restart Bot
```bash
docker-compose restart trading-bot
```

---

## ⚠️ Critical Settings in `.env`

**Must have for live trading:**
```
APCA_API_KEY_ID=your_alpaca_key
APCA_API_SECRET_KEY=your_alpaca_secret
DB_USER=trading
DB_PASSWORD=trading
```

**Check before starting:**
```bash
cat .env | grep APCA
# Should show your API credentials
```

---

## 📈 Key Metrics to Monitor

### From Dashboard (http://localhost:5000)
- **Portfolio Value**: Starting $100,000 → current value
- **P&L**: Profit/loss since start
- **Win Rate**: % of winning trades
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest decline

### From Logs
```
[LIVE] Active symbols for trading: ...
[LIVE] Entering trade on XYZ at $123.45
[LIVE] Exiting trade on XYZ at $125.00 (+1.25%)
```

---

## 🛑 Safety Features Active

✅ **Circuit Breaker**: Stops if daily loss > 2%  
✅ **Position Limits**: Max 5% per symbol  
✅ **Risk Sizing**: Uses Kelly Criterion  
✅ **Gap Protection**: Avoids gap-up risk  
✅ **Liquidity Check**: Only trades liquid stocks  

---

## ❌ Common Issues & Fixes

### "containers already exists"
```bash
docker-compose down
docker-compose up -d
```

### "API credentials not found"
```bash
# Add to .env file:
APCA_API_KEY_ID=your_key
APCA_API_SECRET_KEY=your_secret

# Then restart:
docker-compose restart trading-bot
```

### "Market is closed"
- Bot only trades 9:30 AM - 4:00 PM EST
- Outside hours, it sleeps (normal behavior)

### Dashboard shows "connection failed"
```bash
docker-compose restart dashboard
# Wait 30 seconds
# Refresh browser
```

---

## 💰 Paper vs Live Trading

### Paper Trading (SAFE - Recommended)
```bash
# Default mode (no real money)
docker-compose up -d
# Bot uses paper account at paper-api.alpaca.markets
```

### Live Trading (REAL MONEY)
```bash
# Requires special flag
python -m trading_bot live trading \
  --nasdaq-top-500 \
  --enable-live-trading \
  --alpaca-key YOUR_KEY
```
**⚠️ Use only after testing with paper trading first!**

---

## 📊 Expected Results Monday

### Conservative Estimate (Per Trading Day)
- **Trades**: 3-8 per day
- **Win Rate**: 55-65%
- **Daily Return**: 0.5-1.5%
- **Risk**: Daily max -2% (protected by circuit breaker)

### Sharpe Ratio (Risk-Adjusted)
- **Good**: > 1.0
- **Excellent**: > 1.5
- **Outstanding**: > 2.0

*Real results depend on market conditions*

---

## 🎯 First Week Plan

**Monday (Day 1)**: Paper trading only
- Verify everything works
- Check for errors/bugs
- Confirm signals make sense

**Tuesday-Wednesday (Days 2-3)**: Paper trading continues
- Build confidence
- Review performance stats
- Check risk management

**Thursday+**: Consider small live positions
- Start with 10% of capital
- Scale up gradually
- Monitor daily

---

## 📞 Important Links

**Dashboard**: http://localhost:5000  
**Logs File**: `./logs/trading_bot.log`  
**Config**: `./configs/default.yaml`  
**Database**: `./data/trades.sqlite`  

**GitHub**: https://github.com/Ronaldmcdonaldeats/algo-trading-bot  
**Alpaca**: https://app.alpaca.markets  

---

## ✅ Pre-Market Checklist (Sunday Night)

- [ ] .env file has valid Alpaca credentials
- [ ] Docker installed and running
- [ ] All containers built: `docker-compose build`
- [ ] Test containers: `docker-compose up -d` then `docker-compose down`
- [ ] Check latest logs for errors
- [ ] Review `MONDAY_LIVE_TRADING_READINESS.md` for details

---

## 🎉 You're Ready!

Just type:
```bash
docker-compose up -d
```

And the bot does the rest! 🚀

**Check dashboard at:** http://localhost:5000

Good luck Monday! 📈
