# 🚀 Auto-Start Guide

Your AI-powered trading bot can now start automatically with strategy learning enabled!

## Simplest Way: One Command

```bash
python -m trading_bot auto
```

That's it! The system will:
1. ✅ Load cached learned strategies (if available)
2. ✅ Score all NASDAQ stocks automatically
3. ✅ Select top 50 performers
4. ✅ Start paper trading
5. ✅ Learn from trading results
6. ✅ Show real-time dashboard

## Windows Users: Click-to-Run Files

### Option 1: PowerShell (Recommended)
```powershell
.\quick_start.ps1
```
Double-click `quick_start.ps1` and it will:
- Activate your Python environment
- Install dependencies if needed
- Start trading automatically
- Show colorful progress messages

### Option 2: Batch File
```batch
quick_start.bat
```
Double-click `quick_start.bat` - works even if you don't have PowerShell installed.

### Option 3: Python Script
```bash
python quick_start.py
```

## Customization Examples

### Auto-start with different options

```bash
# Trade for 100 iterations instead of infinite
python -m trading_bot auto --iterations 100

# Use specific stocks instead of auto-selection
python -m trading_bot auto --symbols AAPL,MSFT,GOOGL

# Disable learning (just trade)
python -m trading_bot auto --no-learn

# Headless mode (no dashboard)
python -m trading_bot auto --no-ui

# Change starting capital
python -m trading_bot auto --start-cash 50000

# Combine options
python -m trading_bot auto \
    --symbols AAPL,MSFT \
    --iterations 50 \
    --start-cash 25000
```

## What Happens When You Start

### Initial Load (1-2 minutes)
```
[INFO] AUTO-START: AI-Powered Trading Bot with Strategy Learning
[INFO] Initializing strategy learning system...
[LEARNING] Ready to learn from trading results
[SELECTION] Smart stock selection enabled
[SELECTION] Selected 50 stocks for trading
[CONFIG] Trading Configuration:
  • Initial Cash: $100,000.00
  • Symbols: 50 stocks
  • Auto-Learning: YES
```

### Trading Loop
The system continuously:
1. **Scores stocks** by trend, momentum, volatility, liquidity
2. **Selects winners** (top performers from NASDAQ)
3. **Executes trades** based on learned strategies
4. **Monitors positions** with real-time P&L
5. **Learns** from outcomes to improve future trades

### Dashboard
While trading, you see:
- Real-time equity curve
- Holdings breakdown
- Open positions with P&L
- Sharpe ratio and drawdown metrics
- Current win rate

Press **Ctrl+C** anytime to stop gracefully.

## What Gets Learned

The system automatically learns:

### 1. Strategy Performance
```
Learned Strategies:
  • mean_reversion_rsi_learned
    - Sharpe: 1.5
    - Win Rate: 55%
    - Confidence: 100%
    
  • macd_volume_momentum_learned
    - Sharpe: 1.2
    - Win Rate: 60%
    - Confidence: 100%
```

### 2. Hybrid Strategies
Combines top strategies:
```
Hybrid Strategy: hybrid_auto_20260124_120000
  Base strategies: [mean_reversion_rsi_learned, macd_volume_momentum_learned]
  Expected Sharpe: 1.4
  Expected Win Rate: 57.5%
```

### 3. Parameter Adjustments
Auto-adjusts based on outcomes:
- Win rate < 40%? → Be more selective (10% tighter thresholds)
- Profit factor < 1.0? → Tighten stops (20% smaller)
- Too few trades? → Loosen thresholds (10% more lenient)

## Where Data is Stored

Everything is saved automatically:

```
.cache/strategy_learning/
  ├── learned_strategies.json      # Learned strategy parameters
  └── hybrid_strategies.json        # Hybrid combinations

data/
  └── trades.sqlite                # All trades and events
```

## Keyboard Shortcuts

**While the dashboard is running:**
- **Ctrl+C** - Stop trading gracefully (still learns from results)
- **Q** - Quit (if using terminal UI)

## Environment Variables

Optional: Set Alpaca API credentials:

```bash
export APCA_API_KEY_ID=your_key_id
export APCA_API_SECRET_KEY=your_secret_key
export APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

Or pass via command line:
```bash
python -m trading_bot auto \
    --alpaca-key YOUR_KEY \
    --alpaca-secret YOUR_SECRET
```

## Troubleshooting

### "Alpaca API credentials not found"
**Solution:** Set environment variables or pass via command line:
```bash
python -m trading_bot auto --alpaca-key KEY --alpaca-secret SECRET
```

### No stocks selected
**Solution:** Check NASDAQ symbol loading - try a specific symbol:
```bash
python -m trading_bot auto --symbols SPY,QQQ,IWM
```

### Dashboard not showing
**Solution:** Use headless mode:
```bash
python -m trading_bot auto --no-ui
```

### Learning not working
**Solution:** Check database has trades:
```bash
python -m trading_bot learn history --db data/trades.sqlite
```

## Advanced: Automation on System Startup

### Windows Task Scheduler

1. Open **Task Scheduler**
2. Click "Create Basic Task"
3. Name: "Trading Bot Auto-Start"
4. Trigger: "At log on" (or custom time)
5. Action: Start a program
6. Program: `C:\Users\YourName\projects\algo-trading-bot\quick_start.bat`
7. Click OK

### macOS/Linux: Cron Job

```bash
# Run at 8 AM every weekday
0 8 * * 1-5 cd ~/projects/algo-trading-bot && python -m trading_bot auto
```

Edit with: `crontab -e`

### Linux: Systemd Service

Create `/etc/systemd/system/trading-bot.service`:
```ini
[Unit]
Description=AI Trading Bot with Learning
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/projects/algo-trading-bot
ExecStart=/home/your_username/projects/algo-trading-bot/.venv/bin/python -m trading_bot auto
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable trading-bot
sudo systemctl start trading-bot
sudo systemctl status trading-bot
```

## Next Steps

1. **First run:** `python -m trading_bot auto`
2. **Watch the dashboard** - See it learn and trade
3. **Check learned strategies** - Inspect `.cache/strategy_learning/`
4. **Paper trade for a few days** - Build confidence
5. **Deploy to paper trading** - Trade real (but not real money)

## FAQ

**Q: Is this real money?**
A: No, paper trading uses a sandbox. No real money changes hands.

**Q: Can I stop and restart?**
A: Yes! The system saves everything. Just run the command again.

**Q: How often does it learn?**
A: Automatically after each trading session. Learning is instant.

**Q: Can I combine with my own strategies?**
A: Yes! See `FINAL_STATUS.md` for integration examples.

**Q: How much history does it need to learn?**
A: Starts learning after 5-10 trades. High confidence after 30+ trades.

---

**Ready?** Run `python -m trading_bot auto` and let it go! 🚀
