# Phase 4: Live Trading with Alpaca Integration

## Overview

Phase 4 adds real broker integration via Alpaca, enabling:
- **Paper Trading**: Test strategies on Alpaca's sandbox with fake money
- **Live Trading**: Trade with real money on Alpaca's platform
- **Safety Interlocks**: Kill switches for drawdown and daily losses
- **Real-Time Monitoring**: Track PnL, positions, and execution

## Architecture

```
Paper Trading (Phase 3)               Live Trading (Phase 4)
─────────────────────────            ──────────────────────
Local YFinance Data                  Alpaca Real-Time Data
↓                                    ↓
PaperBroker (Simulated)              AlpacaBroker (Real Orders)
↓                                    ↓
SQLite Logging                       SQLite + Alpaca Logging
↓                                    ↓
Learning System (Adaptive)           Learning System (Adaptive)
↓                                    ↓
Paper Port + CLI                     Live Account + Safety Controls
```

## Setup Instructions

### 1. Install Alpaca SDK
```powershell
pip install alpaca-py
```

### 2. Get Alpaca API Credentials

**Paper Trading (Recommended to start):**
1. Go to https://app.alpaca.markets/
2. Login or create account
3. Go to Account → Settings → API Keys
4. Copy API Key and Secret Key

**Live Trading:**
1. Upgrade to live account on Alpaca
2. Complete KYC verification
3. Fund your account with real money
4. Get live API keys (different from paper keys)

### 3. Configure Environment Variables

Create or update `.env`:
```powershell
# Paper Trading
APCA_API_KEY_ID=your_paper_api_key
APCA_API_SECRET_KEY=your_paper_secret
APCA_API_BASE_URL=https://paper-api.alpaca.markets

# Live Trading (different credentials)
# APCA_API_KEY_ID=your_live_api_key
# APCA_API_SECRET_KEY=your_live_secret
# APCA_API_BASE_URL=https://api.alpaca.markets
```

Or set environment variables:
```powershell
$env:APCA_API_KEY_ID="your_api_key"
$env:APCA_API_SECRET_KEY="your_secret"
```

## Usage

### Paper Trading on Alpaca

```powershell
python -m trading_bot live paper \
    --symbols SPY,QQQ,IWM \
    --period 60d \
    --interval 1d \
    --iterations 50
```

**Output:**
```
[LIVE] Paper Trading Mode on Alpaca
[LIVE] Symbols: SPY, QQQ, IWM
[LIVE] Starting cash: $100,000.00
[LIVE] Connected to: https://paper-api.alpaca.markets
[LIVE] Ready for paper trading!
iter=1 cash=100,000.00 equity=100,000.00 fills=0
iter=2 cash=99,950.00 equity=100,150.00 fills=1
...
```

### LIVE Trading on Alpaca (Real Money)

```powershell
python -m trading_bot live trading \
    --symbols SPY,QQQ,IWM \
    --interval 15m \
    --iterations 100 \
    --enable-live \
    --max-drawdown 5.0 \
    --max-daily-loss 2.0
```

⚠️  **IMPORTANT SAFETY FEATURES:**

1. **Explicit Enable Flag**: `--enable-live` required (prevents accidents)
2. **User Confirmation**: Must type "YES I UNDERSTAND" when prompted
3. **Kill Switch**: Auto-stops at 5% drawdown (customizable)
4. **Daily Loss Limit**: Auto-stops if daily loss > 2% (customizable)
5. **Audit Trail**: All trades logged with timestamps and reasoning

**Output:**
```
╔════════════════════════════════════════════════════════════════╗
║                    ⚠️  LIVE TRADING WARNING ⚠️                   ║
║                                                                ║
║  This will trade with REAL MONEY on your Alpaca account!      ║
║  Losses are real. Commissions apply.                          ║
║                                                                ║
║  Safety Controls Active:                                       ║
║  • Max Drawdown: 5.0% kill switch                             ║
║  • Max Daily Loss: 2.0%                                       ║
║  • All orders logged and auditable                            ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

Type 'YES I UNDERSTAND' to proceed with live trading: YES I UNDERSTAND

[LIVE] Starting REAL MONEY trading on Alpaca...
[LIVE] Connected to LIVE account: https://api.alpaca.markets
[LIVE] Safety controls initialized
[LIVE] Ready for LIVE trading with real money!
iter=1 cash=99,950.00 equity=100,150.00 fills=1
```

## CLI Commands

### Paper Mode
```powershell
python -m trading_bot live paper [OPTIONS]

Options:
  --symbols TICKERS           Comma-separated tickers (default: SPY)
  --period PERIOD             Historical period (default: 60d)
  --interval INTERVAL         Bar interval (default: 1d)
  --start-cash AMOUNT         Starting cash (default: 100000)
  --iterations N              Number of iterations (0=infinite)
  --db PATH                   SQLite database path
```

### Live Mode
```powershell
python -m trading_bot live trading [OPTIONS]

Options:
  --symbols TICKERS           Comma-separated tickers
  --interval INTERVAL         Bar interval (recommend: 15m for live)
  --iterations N              Number of iterations (0=infinite)
  --db PATH                   SQLite database path
  --enable-live               REQUIRED to enable real trading
  --max-drawdown PCT          Kill switch drawdown % (default: 5%)
  --max-daily-loss PCT        Daily loss limit % (default: 2%)
```

## Safety Controls

### Built-In Protections

1. **Explicit Enable Flag**
   - Live trading requires `--enable-live` flag
   - Prevents accidental real money trading

2. **User Confirmation**
   - Must type "YES I UNDERSTAND" when prompted
   - Shows all risk parameters before execution

3. **Drawdown Kill Switch**
   - Stops trading if equity drops X%
   - Default: 5% (customizable with `--max-drawdown`)
   - Prevents catastrophic losses

4. **Daily Loss Limit**
   - Stops trading if daily loss > X%
   - Default: 2% (customizable with `--max-daily-loss`)
   - Protects account during bad days

5. **Position Size Limits**
   - Max 10% of account in single position (default)
   - Prevents concentration risk

6. **Order Rate Limits**
   - Max 100 orders per day (default)
   - Prevents order spam

7. **Audit Trail**
   - Every trade logged with timestamp and rationale
   - Queryable via SQLite
   - Full compliance documentation

## Monitoring Live Trading

### Real-Time Dashboard (Coming Soon)
```powershell
# Monitor live positions and PnL
python -m trading_bot live monitor
```

### Check Account Status
```powershell
# View account information
python -m trading_bot live status
```

### Historical Analysis
```powershell
# View executed trades
python -m trading_bot live history --limit 20

# View daily PnL
python -m trading_bot live pnl --period 7d
```

## Learning System Integration

The autonomous learning system from Phase 3 works seamlessly with Phase 4:

1. **Real Market Adaptation**
   - Regime detector learns from live market data
   - Trades analyzed for real fill prices (with slippage)
   - Performance metrics include commissions

2. **Adaptive Weighting**
   - Strategies weighted based on live results
   - Weights adjust as market conditions change
   - Full audit trail in database

3. **Risk Management**
   - Learning respects safety controls
   - Won't recommend aggressive strategies during losses
   - Automatically scales back during drawdowns

## Database Schema

### New Tables (Phase 4)

**live_trades**
- id, symbol, side, quantity, entry_price, exit_price, timestamp
- commission, slippage, pnl, pnl_pct

**live_orders**
- id, symbol, side, quantity, order_type, limit_price, status, timestamp
- filled_qty, filled_price, error

**live_account_snapshots**
- timestamp, cash, equity, buying_power, drawdown_pct, daily_pnl

**live_risks_events**
- timestamp, event_type (drawdown_breach, daily_loss_breach, etc.)
- value, limit, action_taken

## Common Tasks

### Start Paper Trading
```powershell
python -m trading_bot live paper --iterations 10
```

### Migrate from Paper to Live
1. Test thoroughly with paper trading
2. Verify 10+ iterations with positive PnL
3. Check safety limits are appropriate
4. Use `--enable-live` flag when ready

### Halt Live Trading
```powershell
# Press Ctrl+C to stop trading gracefully
# Open positions can be manually closed on Alpaca dashboard
```

### Review Live Trades
```powershell
sqlite3 trades.sqlite

SELECT * FROM live_trades WHERE timestamp >= datetime('now', '-1 day');
SELECT SUM(pnl) as daily_pnl FROM live_trades WHERE date(timestamp) = date('now');
```

## Risk Management Checklist

- [ ] API credentials configured (not hardcoded!)
- [ ] Paper trading tested thoroughly
- [ ] Account has minimum funding (~$25k for day trading)
- [ ] Safety limits set appropriately
- [ ] Emergency stop procedure understood
- [ ] Database backups configured
- [ ] Monitoring dashboard active
- [ ] Alert system configured (email/SMS for drawdowns)

## Troubleshooting

### "Alpaca credentials not found"
- Check environment variables are set
- Verify `.env` file in project root
- Use `echo $env:APCA_API_KEY_ID` to verify

### "Connection refused"
- Check API endpoint (paper vs live)
- Verify internet connection
- Check Alpaca API status page

### "Insufficient buying power"
- Paper trading accounts get $100k
- Live trading needs real funding
- Check available cash in Alpaca dashboard

### Orders not executing
- Check market hours (9:30-16:00 ET)
- Verify symbols are tradeable
- Check position size limits
- Review error logs in database

## Next Steps

1. **Get API Credentials**: Sign up for Alpaca account
2. **Test Paper Trading**: Run 10+ iterations in paper mode
3. **Enable Live Trading**: Use `--enable-live` when ready
4. **Monitor Performance**: Track PnL and learning metrics
5. **Adjust Parameters**: Fine-tune risk limits based on results

## Support

For Alpaca-specific issues:
- Alpaca Documentation: https://docs.alpaca.markets
- API Reference: https://github.com/alpacahq/alpaca-py

For trading bot issues:
- Check database: `sqlite3 trades.sqlite`
- Review logs: `tail -100 trades.sqlite` or query error tables
- Check GitHub issues in project repository

