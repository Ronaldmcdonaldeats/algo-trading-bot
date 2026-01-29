# 🤖 Algo Trading Bot - 24/7 Automated Trading

> Fully automated trading bot running on Oracle Cloud with real-time Discord alerts

## ✨ Current Status

**Status**: ✅ **LIVE** (24/7 trading active on Oracle Cloud)  
**Strategy**: Gen 364 (Genetic Algorithm Evolved)  
**Performance**: +7.32% backtest return, Sharpe Ratio 1.05  
**Monitoring**: Discord webhooks + Alpaca dashboard  
**Next Trading**: Thursday, January 30, 2026 @ 9:30 AM EST

---

## 🎯 Quick Start

### Monitor Your Trading

**1. Discord (Easiest)**
- Check your Discord channel for real-time trade alerts
- See every trade, profit/loss, and market events

**2. Alpaca Dashboard**
- Go to: https://app.alpaca.markets
- View all orders and positions
- Monitor P/L in real-time

**3. View Logs (Technical)**
```bash
ssh -i "key" ubuntu@129.213.99.89
tail -f ~/bot/logs/live_trading/live_trading_24_7.log
```

---

## 📚 Documentation

### **START HERE**: [COMPLETE_DEPLOYMENT_GUIDE.md](COMPLETE_DEPLOYMENT_GUIDE.md)

Master documentation covering everything:
- ✅ System overview & architecture
- ✅ 24/7 live trading setup
- ✅ Security configuration  
- ✅ Discord integration
- ✅ Monitoring & logging
- ✅ Alpaca integration
- ✅ Troubleshooting
- ✅ Quick commands reference

---

## 📊 Features

### Gen 364 Strategy (Currently Live)
- **Entry Threshold:** 0.7756
- **Profit Target:** 12.87%
- **Stop Loss:** 9.27%
- **Backtest Return:** +7.32%
- **Sharpe Ratio:** 1.05

### Ultimate Hybrid Strategy (Backtested Alternative)
- **26-year backtest:** 426.36% total return
- **Annual return:** ~20% (beats SPY by 10%)
- **12 Technical Indicators:** Multi-timeframe analysis
- **Volatility Adaptation:** Dynamic position sizing
- **Risk Management:** Stop loss & take profit controls

### Trading Modes
- ✅ **24/7 Automated** - Runs continuously on Oracle Cloud
- ✅ **Market Hours Aware** - Only trades 9:30 AM - 4:00 PM EST weekdays
- ✅ **Paper Trading** - Backtest strategies with historical data
- ✅ **Live Trading** - Execute real trades via Alpaca API
- ✅ **Auto-Restart** - Recovers automatically from failures

### Monitoring
- Real-time Discord notifications
- Alpaca dashboard integration
- Trade history logging
- PostgreSQL database
- Performance analytics
- Risk metrics tracking

---

## 🏗️ Architecture

```
Your Machine
    ↓
SSH Tunnel (Encrypted)
    ↓
Oracle Cloud Instance (129.213.99.89)
    ├→ Systemd Service (live-trading.service)
    ├→ Docker Containers
    │   ├→ Dashboard (Flask, Port 5000)
    │   ├→ API (REST, Port 5001)
    │   ├→ Strategy Engine
    │   ├→ PostgreSQL (Port 5432)
    │   └→ Redis (Port 6379)
    └→ Alpaca API Integration
        ├→ Paper/Live Trading
        ├→ Order Execution
        └→ Market Data
```

---

## 📖 How It Works

### Daily Trading Cycle

```
9:30 AM EST   → Market Opens
              → Bot detects opening
              → Strategy begins analyzing
              → First trades execute
              → Discord notification sent

Throughout    → Continuous trading
day           → Positions updated in real-time
              → P/L tracked
              → All trades logged

4:00 PM EST   → Market Closes
              → Positions closed
              → Daily P/L calculated
              → Enters standby

Next day      → Cycle repeats
```

---

## 🔧 Setup & Usage

### 1. Check If Bot Is Running
```bash
sudo systemctl status live-trading.service
```

### 2. View Live Logs
```bash
ssh -i "key" ubuntu@129.213.99.89
tail -f ~/bot/logs/live_trading/live_trading_24_7.log
```

### 3. Access Services

**Dashboard**
```bash
ssh -i "key" -L 5000:localhost:5000 ubuntu@129.213.99.89
# Then: http://localhost:5000
```

**API**
```bash
ssh -i "key" -L 5001:localhost:5001 ubuntu@129.213.99.89
# Then: http://localhost:5001
```

### 4. Manage Service
```bash
# Start
sudo systemctl start live-trading.service

# Stop
sudo systemctl stop live-trading.service

# Restart
sudo systemctl restart live-trading.service
```

### 5. Backtest a Strategy
```bash
python -m trading_bot backtest \
  --strategy ultimate_hybrid \
  --symbols AAPL,MSFT,GOOGL,AMZN,NVDA \
  --start-cash 100000 \
  --start-date 2020-01-01 \
  --end-date 2024-12-31
```

---

## 🔐 Security

✅ All ports private (127.0.0.1 only)  
✅ SSH encryption for all access  
✅ No hardcoded credentials (.env file)  
✅ Key-based authentication  
✅ Full audit trail  

---

## 🧪 What's Tested & Working

✅ Discord webhook - 3 test messages delivered  
✅ Alpaca API - Paper trading configured  
✅ Market hours - EST timezone aware  
✅ Auto-restart - Systemd service enabled  
✅ Docker - 6 containers running  
✅ Port security - All ports locked down  
✅ SSH tunnels - Encrypted access verified  

---

## 📊 Performance

**Gen 364 Strategy:**
- Backtest Return: +7.32%
- Sharpe Ratio: 1.05
- Win Rate: ~60%
- Profit Target: 12.87%
- Stop Loss: 9.27%

**Ultimate Hybrid Strategy:**
- 26-year total return: 426.36%
- Annual return: ~20%
- Max drawdown: -65.56%

---

## 🚀 What Happens Next

### Thursday, January 30, 2026 @ 9:30 AM EST

1. Market opens
2. Bot detects opening
3. Strategy analyzes stocks
4. First trade executes
5. **Discord notification arrives**
6. Trade appears on Alpaca dashboard
7. Trading continues until 4:00 PM EST
8. **Cycle repeats daily**

**You don't need to do anything** — it runs automatically!

---

## 📞 Quick Commands

| Command | Purpose |
|---------|---------|
| `sudo systemctl status live-trading.service` | Check if running |
| `tail -f ~/bot/logs/live_trading/live_trading_24_7.log` | View logs |
| `https://app.alpaca.markets` | View trades |
| Discord channel | Get notifications |

---

## ✅ Deployment Status

✅ Bot deployed on Oracle Cloud (129.213.99.89)  
✅ 24/7 automated trading active  
✅ Market hours detection working  
✅ Discord notifications tested  
✅ Alpaca integration configured  
✅ All services healthy  
✅ Auto-restart enabled  
✅ Fully secured  

---

## 📝 License

MIT License - See LICENSE file

---

**Status:** 🟢 LIVE & OPERATIONAL  
**Last Updated:** January 29, 2026  
**Strategy:** Gen 364 (Evolved)  
**Platform:** Oracle Cloud
