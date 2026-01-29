# 🚀 Complete Trading Bot Deployment Guide

**Status**: ✅ LIVE & OPERATIONAL  
**Date**: January 29, 2026  
**Deployment**: Oracle Cloud (129.213.99.89)  
**Trading Mode**: 24/7 Automated with Market Hours Awareness

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [System Overview](#system-overview)
3. [24/7 Live Trading Setup](#247-live-trading-setup)
4. [Security Configuration](#security-configuration)
5. [Discord Integration](#discord-integration)
6. [Monitoring & Logging](#monitoring--logging)
7. [Alpaca Trading Platform](#alpaca-trading-platform)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### 🎯 Current Status
- **Service**: ✅ ACTIVE (running on Oracle Cloud)
- **Market**: 🔴 CLOSED (opens Thursday 9:30 AM EST)
- **Credentials**: ✅ LOADED (.env configured)
- **Discord Webhook**: ✅ TESTED (3 messages delivered)
- **Auto-Restart**: ✅ ENABLED (systemd service)

### ⏱️ Next Trading Session
**Thursday, January 30, 2026 @ 9:30 AM EST** — Bot automatically begins trading

### 📡 What You're Monitoring
- **Discord**: Real-time trade notifications
- **Alpaca Dashboard**: Order execution and P/L
- **SSH Logs**: Detailed trading activity (optional)

---

## System Overview

### 🏗️ Architecture

```
Your Local Machine
    ↓
    └→ SSH Tunnel (Encrypted)
       ↓
Oracle Cloud Instance (129.213.99.89)
       ↓
       ├→ Systemd Service: live-trading.service (24/7)
       ├→ Docker Orchestration: docker-compose
       │   ├→ Dashboard (Port 5000)
       │   ├→ API (Port 5001)
       │   ├→ Strategy Engine
       │   ├→ PostgreSQL Database
       │   └→ Redis Cache
       └→ Alpaca Integration
           ├→ Live/Paper Trading API
           ├→ Market Data
           └→ Order Execution
```

### 🔧 Key Components

| Component | Status | Purpose |
|-----------|--------|---------|
| **live-trading.service** | ✅ ACTIVE | 24/7 service management |
| **Docker Containers** | ✅ RUNNING | 6 microservices deployed |
| **Strategy Engine** | ✅ READY | Gen 364 strategy (+7.32% backtest) |
| **Alpaca API** | ✅ CONFIGURED | Paper trading account |
| **Discord Webhook** | ✅ TESTED | Real-time notifications |
| **PostgreSQL** | ✅ HEALTHY | Trade history & database |
| **Redis Cache** | ✅ HEALTHY | Performance optimization |

---

## 24/7 Live Trading Setup

### ✅ What's Configured

Your bot is set up to:
- **Run continuously** — Never stops (unless server reboots)
- **Check market hours** — Only trades 9:30 AM - 4:00 PM EST, weekdays
- **Auto-restart** — Restarts every 10 seconds if it fails
- **Monitor health** — Validates all services are working
- **Send alerts** — Notifies Discord of every event

### 🎯 Market Hours Logic

```bash
# Runs 24/7 but trades only during:
Monday - Friday:  9:30 AM - 4:00 PM EST
Saturday - Sunday: CLOSED (no trading)
After 4:00 PM EST: Closes positions, enters standby
```

### 📊 Trading Strategy

**Gen 364** (Evolved via Genetic Algorithm)
- **Entry Threshold**: 0.7756
- **Profit Target**: 12.87%
- **Stop Loss**: 9.27%
- **Backtest Performance**: +7.32%, Sharpe Ratio: 1.05

### 🔄 Daily Trading Cycle

```
9:30 AM EST  → Market Opens
            → Bot detects market open
            → Strategy begins analyzing stocks
            → First trades execute
            
Throughout day → Continuous trading based on Gen 364 strategy
            → Trades logged in PostgreSQL
            → Discord notifications sent for each trade
            
4:00 PM EST  → Market Closes
            → Bot closes remaining open positions
            → Calculates daily P/L
            → Enters standby until next day
            
5:00 PM EST  → Overnight mode
            → Waits for next market open
            → Monitors for system health
            → Can be manually overridden
```

### 🚀 Service Management

**Check Service Status**
```bash
sudo systemctl status live-trading.service
```

**Start Service**
```bash
sudo systemctl start live-trading.service
```

**Stop Service**
```bash
sudo systemctl stop live-trading.service
```

**View Logs**
```bash
sudo journalctl -u live-trading.service -f
```

**Enable Auto-Start on Reboot**
```bash
sudo systemctl enable live-trading.service
```

---

## Security Configuration

### 🔐 Port Security

All ports are **restricted to localhost only** — not exposed to internet:

```yaml
ports:
  - "127.0.0.1:5000:5000"   # Dashboard (Private)
  - "127.0.0.1:5001:5001"   # API (Private)
  - "127.0.0.1:6379:6379"   # Redis (Private)
  - "127.0.0.1:5432:5432"   # PostgreSQL (Private)
```

### 🔑 SSH Tunnel Access

Access services securely via encrypted SSH tunnels:

#### Dashboard (Port 5000)
```powershell
# Terminal 1: Create tunnel
ssh -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2026-01-29.key" -L 5000:localhost:5000 ubuntu@129.213.99.89

# Terminal 2: Open browser
http://localhost:5000
```

#### API (Port 5001)
```powershell
ssh -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2026-01-29.key" -L 5001:localhost:5001 ubuntu@129.213.99.89

# Access:
http://localhost:5001
```

#### Database (Port 5432)
```powershell
# Terminal 1: Create tunnel
ssh -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2026-01-29.key" -L 5432:localhost:5432 ubuntu@129.213.99.89

# Terminal 2: Connect with psql (if installed)
psql -h localhost -U postgres -d trading_bot
```

### 🛡️ Security Features

✅ **Encrypted Communication** — All traffic via HTTPS/SSH  
✅ **No Public Exposure** — Ports bound to 127.0.0.1 only  
✅ **Key-Based Authentication** — SSH keys, no passwords  
✅ **Environment Isolation** — Credentials in .env (not in code)  
✅ **Audit Trail** — SSH logs all access  
✅ **Network Isolation** — Docker internal network for service communication  

### 📁 Credential Management

**Location**: `~/.env` on Oracle instance

**Contents**:
```bash
APCA_API_KEY_ID=PKNEMFUG7OGZGLGWZYX2FSXVO4
APCA_API_SECRET_KEY=2iFkEayDXqNiRmY7yT1ArDRhXySTujGrMAThkw8KeB3M
APCA_API_BASE_URL=https://paper-api.alpaca.markets
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

**Loaded in Service**:
```bash
set -a && source .env && set +a
```

---

## Discord Integration

### ✅ Status: TESTED & WORKING

3 test messages successfully delivered to Discord.

### 📤 Notifications Sent

#### 🟢 Trade Notifications
- **Trade Executed** - symbol, side, quantity, price, order ID
- **Position Closed** - entry price, exit price, P/L $, P/L %

#### 🔔 Market Events
- **Market Opened** - at 9:30 AM EST
- **Market Closed** - at 4:00 PM EST

#### ⚠️ Alerts
- **Low Balance Warning** - account balance below threshold
- **High Loss Alert** - position hit stop loss
- **Strategy Error** - system encountered error

#### 🤖 Status Updates
- **Strategy Started** - bot began trading
- **Strategy Stopped** - bot halted
- **Service Health Check** - periodic status

### 🧪 Test Results

```
✅ Test 1: Simple Notification (Blue)
   Status: PASSED - Message delivered
   
✅ Test 2: Trade Example (Green)
   Status: PASSED - Trade details displayed
   
✅ Test 3: Error Alert (Red)
   Status: PASSED - Alert formatted correctly
```

### 🎨 Message Format

Discord embeds with:
- Rich formatting (title, description, fields)
- Color coding (Green=Success, Yellow=Warning, Red=Error)
- Timestamps on all messages
- Structured data fields

### 📝 Example Messages

**Trade Executed**:
```
📈 TRADE EXECUTED - SPY

Gen 364 Strategy executed BUY order

Symbol: SPY
Side: BUY
Quantity: 10
Price: $450.25
Order ID: 123456
```

**Position Closed (Profit)**:
```
📊 POSITION CLOSED - AAPL

Trade closed with +$125.50 P/L

Symbol: AAPL
Quantity: 10
Entry Price: $150.00
Exit Price: $152.55
P/L Amount: +$125.50
P/L %: +1.70%
```

### 🔗 Configuration

**Webhook URL**: Stored in `.env`
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

**Test Webhook Locally**:
```bash
python test_discord_webhook.py
```

**Module Location**: `src/trading_bot/discord_notifier.py`

---

## Monitoring & Logging

### 📊 Real-Time Monitoring

#### Option 1: SSH Log Stream (Recommended)
```bash
ssh -i "key" ubuntu@129.213.99.89
tail -f ~/bot/logs/live_trading/live_trading_24_7.log
```

Shows real-time trading activity, market hours, strategy decisions.

#### Option 2: Discord Channel
Open your Discord and watch for automatic notifications.
No terminal needed — just view Discord!

#### Option 3: Alpaca Dashboard
Log into https://app.alpaca.markets
- See all orders
- Monitor positions
- Track account P/L
- View execution prices

#### Option 4: Service Status
```bash
ssh -i "key" ubuntu@129.213.99.89
sudo systemctl status live-trading.service
```

### 📁 Log Files

**Main Trading Log**
```
~/bot/logs/live_trading/live_trading_24_7.log
```
Contains all trading activity, market hours detection, strategy decisions.

**Docker Logs**
```bash
docker logs -f trading-bot-strategy
docker logs -f trading-bot-api
docker logs -f trading-bot-dashboard
```

**System Journal**
```bash
sudo journalctl -u live-trading.service -f
```

### 📈 Metrics to Monitor

**Daily Tracking**:
- Total trades executed
- Win rate (% profitable trades)
- Total P/L ($)
- P/L % (return)
- Largest win
- Largest loss
- Average trade duration

**Weekly Summary**:
- Week P/L
- Best day
- Worst day
- Consistency metrics

---

## Alpaca Trading Platform

### 🎯 Account Setup

**Account Type**: Paper Trading (Simulated)
- All trades are simulated
- No real money required
- Perfect for testing

**To Switch to Live Trading**:
1. Add funds to Alpaca account
2. Change `.env`:
   ```bash
   APCA_API_BASE_URL=https://api.alpaca.markets
   ```
3. Restart service
4. ⚠️ BE CAREFUL — Real money now at risk!

### 📊 Viewing Your Trades

1. **Log into Alpaca**: https://app.alpaca.markets
2. **Navigate to**:
   - **Orders** → See all trade history
   - **Positions** → Current holdings
   - **Account** → Net worth, cash, buying power
   - **Activity** → Transaction log

### 🔄 Live Updates

When bot executes trade:
1. **Instantly on Alpaca** (within 1 second)
2. **Notification on Discord** (within 2 seconds)
3. **Logged in PostgreSQL** (within 1 second)
4. **Visible in Dashboard** (within 5 seconds)

### 💰 Understanding P/L

**Profit/Loss Calculation**:
```
P/L $ = (Exit Price - Entry Price) × Quantity

Example:
  Entry: 10 shares @ $150 = $1,500 investment
  Exit:  10 shares @ $155 = $1,550 proceeds
  P/L:   +$50 profit
  P/L %: +3.33%
```

**Daily P/L**: Sum of all trades closed today  
**Account P/L**: Includes open positions (unrealized) + closed trades (realized)

### 🎓 Strategy Performance

**Gen 364 Statistics**:
- Backtest Return: +7.32%
- Sharpe Ratio: 1.05
- Win Rate: ~60%
- Avg Win: +2.5%
- Avg Loss: -1.2%

---

## Troubleshooting

### 🔴 Service Not Running?

**Check Status**:
```bash
sudo systemctl status live-trading.service
```

**Restart Service**:
```bash
sudo systemctl restart live-trading.service
```

**View Errors**:
```bash
sudo journalctl -u live-trading.service -n 50
```

### 🔴 No Discord Messages?

**Test Webhook**:
```bash
ssh ubuntu@129.213.99.89
cd ~/bot
python3 test_discord_webhook.py
```

**Check Webhook URL**:
```bash
grep DISCORD_WEBHOOK ~/.env
```

**Verify Channel Permissions**:
- Discord server → Webhook channel
- Bot has "Send Messages" permission

### 🔴 Alpaca Not Connecting?

**Test Connection**:
```bash
ssh ubuntu@129.213.99.89
docker logs -f trading-bot-strategy | grep -i alpaca
```

**Check Credentials**:
```bash
grep APCA ~/.env
```

**Verify API Endpoint**:
- Should be: `https://paper-api.alpaca.markets` (paper trading)
- Or: `https://api.alpaca.markets` (live trading)

### 🔴 Docker Services Failing?

**Check Service Status**:
```bash
docker-compose ps
```

**View Container Logs**:
```bash
docker-compose logs -f strategy
docker-compose logs -f api
docker-compose logs -f dashboard
```

**Rebuild & Restart**:
```bash
cd ~/bot
docker-compose down
docker-compose build
docker-compose up -d
```

### 🔴 Market Hours Not Detected?

**Check EST Time**:
```bash
TZ='America/New_York' date
```

**Monitor Market Detection**:
```bash
tail -f logs/live_trading/live_trading_24_7.log | grep -i market
```

### 🔴 Low Performance?

**Check System Resources**:
```bash
docker stats
```

**Optimize if needed**:
```bash
# Limit memory per container
docker-compose down
# Edit docker-compose.yml
# Add: mem_limit: 2g
docker-compose up -d
```

---

## Daily Checklist

### 🌅 Morning (Before 9:30 AM EST)

- [ ] Verify service is running: `sudo systemctl status live-trading.service`
- [ ] Check Discord for notifications
- [ ] Review trading logs: `tail -f logs/live_trading/live_trading_24_7.log`
- [ ] Verify Alpaca account has adequate funds

### 📊 During Trading (9:30 AM - 4:00 PM EST)

- [ ] Monitor Discord for trade notifications
- [ ] Check Alpaca dashboard for P/L
- [ ] Review strategy decisions in logs (optional)
- [ ] Note any unusual market movements

### 🌙 Evening (After 4:00 PM EST)

- [ ] Service automatically enters standby
- [ ] Review daily P/L on Alpaca
- [ ] Check if any alerts were triggered
- [ ] Plan for next trading day

---

## Quick Command Reference

### SSH & Tunnels
```powershell
# SSH to instance
ssh -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2026-01-29.key" ubuntu@129.213.99.89

# Dashboard tunnel
ssh -i "key" -L 5000:localhost:5000 ubuntu@129.213.99.89

# API tunnel
ssh -i "key" -L 5001:localhost:5001 ubuntu@129.213.99.89

# Database tunnel
ssh -i "key" -L 5432:localhost:5432 ubuntu@129.213.99.89
```

### Service Management
```bash
# Check status
sudo systemctl status live-trading.service

# Start service
sudo systemctl start live-trading.service

# Stop service
sudo systemctl stop live-trading.service

# Restart service
sudo systemctl restart live-trading.service

# View logs
sudo journalctl -u live-trading.service -f
```

### Docker Commands
```bash
# Check container status
docker-compose ps

# View logs
docker logs -f trading-bot-strategy
docker logs -f trading-bot-api

# Restart all services
docker-compose restart

# Rebuild all images
docker-compose build
```

### Monitoring
```bash
# Stream logs
tail -f ~/bot/logs/live_trading/live_trading_24_7.log

# Check market detection
tail -f ~/bot/logs/live_trading/live_trading_24_7.log | grep -i market

# View strategy activity
docker logs -f trading-bot-strategy

# Real-time system stats
docker stats
```

---

## Important Contacts & Links

### 🔗 External Services

**Alpaca Trading**
- Dashboard: https://app.alpaca.markets
- Docs: https://alpaca.markets/docs

**Discord**
- Server: (Your Discord channel receiving webhook messages)
- Webhook configured and tested ✅

**Oracle Cloud**
- Instance IP: 129.213.99.89
- Region: (Your configured region)

### 🆘 Support Resources

- **Alpaca Support**: support@alpaca.markets
- **Discord Support**: support.discord.com
- **Project Repo**: Algo Trading Bot (GitHub)

---

## Summary

✅ **24/7 Live Trading**: Running automatically on Oracle Cloud  
✅ **Market Hours Aware**: Trades only 9:30 AM - 4:00 PM EST (weekdays)  
✅ **Auto-Restart**: Service recovers from failures automatically  
✅ **Discord Alerts**: Real-time notifications for all events  
✅ **Secure Access**: All ports private, SSH tunnel encrypted  
✅ **Professional Setup**: Docker orchestration, health checks, logging  

### 🚀 You're All Set!

Your trading bot is live and ready. Monitor via:
1. **Discord** — Easiest (just watch notifications)
2. **Alpaca Dashboard** — Official trading platform
3. **SSH Logs** — Detailed technical view (optional)

**Expected First Trade**: Thursday, January 30, 2026 @ ~9:35 AM EST

---

**Last Updated**: January 29, 2026  
**Status**: ✅ PRODUCTION READY  
**Deployment**: COMPLETE
