# 🚀 Complete Environment Setup Guide

This guide walks you through setting up your AI-powered trading bot from scratch.

## Step 1: Prerequisites

### Check Python Installation
```bash
python --version  # Should show 3.8 or higher
```

If Python is not installed, download from [python.org](https://www.python.org/downloads/)

### Check Git Installation (Optional)
```bash
git --version
```

## Step 2: Automatic Setup (Recommended)

The easiest way is to use the automatic setup script:

```bash
python setup.py
```

This will automatically:
1. ✅ Verify Python version
2. ✅ Create virtual environment
3. ✅ Install all dependencies
4. ✅ Create configuration directories
5. ✅ Download sample data
6. ✅ Run tests to verify everything works

**That's it!** The script handles everything.

---

## Step 3: Manual Setup (Alternative)

If you prefer to do it manually:

### 3a. Create Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\Activate.ps1

# Mac/Linux
python -m venv .venv
source .venv/bin/activate
```

### 3b. Install Dependencies
```bash
pip install --upgrade pip
pip install -e .
pip install pyarrow jupyter  # Optional but recommended
```

### 3c. Create Directories
```bash
mkdir -p configs data logs notebooks
mkdir -p .cache/.strategy_learning
```

---

## Step 4: Configure Alpaca API Credentials

### 4a. Get Your Credentials

1. Go to [app.alpaca.markets](https://app.alpaca.markets)
2. Log in or create account
3. Go to Settings → API Keys
4. Copy your **API Key ID** and **Secret Key**

### 4b. Add to Environment

**Option 1: Environment File (Recommended)**
```bash
# Create .env file in project root
APCA_API_KEY_ID=your_api_key_here
APCA_API_SECRET_KEY=your_secret_key_here
APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

**Option 2: Command Line**
```bash
# Windows
$env:APCA_API_KEY_ID="your_key"
$env:APCA_API_SECRET_KEY="your_secret"

# Mac/Linux
export APCA_API_KEY_ID="your_key"
export APCA_API_SECRET_KEY="your_secret"
```

**Option 3: Pass via CLI**
```bash
python -m trading_bot auto \
    --alpaca-key your_key \
    --alpaca-secret your_secret
```

---

## Step 5: Verify Installation

### Test 1: Import Core Modules
```bash
python -c "from trading_bot.learn.strategy_learner import StrategyLearner; print('✓ Learning system loaded')"
```

### Test 2: Run Pytest
```bash
python -m pytest tests/ -v
```

Should show: **32 passed, 1 skipped**

### Test 3: Check Auto Command
```bash
python -m trading_bot auto --help
```

Should show help text with all options.

---

## Step 6: First Run

### Easiest: Use Auto-Start
```bash
python -m trading_bot auto
```

This automatically:
- Loads learned strategies
- Scores NASDAQ stocks
- Selects top performers
- Starts paper trading
- Shows real-time dashboard

### Alternative: Use Quick-Start Script

**Windows PowerShell:**
```powershell
.\quick_start.ps1
```

**Windows Command Prompt:**
```cmd
quick_start.bat
```

**Mac/Linux:**
```bash
python quick_start.py
```

---

## Troubleshooting

### Issue: "Python not found"
**Solution:** Install Python 3.8+ from [python.org](https://www.python.org)

### Issue: "Module not found"
**Solution:** Make sure virtual environment is activated:
```bash
# Windows
.venv\Scripts\Activate.ps1

# Mac/Linux
source .venv/bin/activate
```

### Issue: "Alpaca credentials not found"
**Solution:** Make sure .env file exists with credentials:
```bash
# Edit .env with your keys
APCA_API_KEY_ID=your_key_here
APCA_API_SECRET_KEY=your_secret_here
```

### Issue: "Tests failing"
**Solution:** Try running tests individually:
```bash
python -m pytest tests/test_config.py -v
python -m pytest tests/test_strategy_learner.py -v
```

---

## Detailed Configuration

### Application Config (configs/default.yaml)

Edit this file to customize:

```yaml
risk:
  max_risk_per_trade: 0.10      # 10% risk per trade
  stop_loss_pct: 0.02           # 2% stop loss
  take_profit_pct: 0.05         # 5% take profit

portfolio:
  target_sector_count: 5        # Diversify across 5 sectors

strategy:
  mean_reversion:
    lookback_days: 20           # 20-day lookback
    zscore_entry: 2.0           # Entry at 2 std deviations
    
  momentum:
    rsi_period: 14              # RSI with 14-period
    rsi_overbought: 70
    rsi_oversold: 30
```

---

## Environment Variables

### Required
- `APCA_API_KEY_ID` - Your Alpaca API key
- `APCA_API_SECRET_KEY` - Your Alpaca secret
- `APCA_API_BASE_URL` - Paper trading URL (default: https://paper-api.alpaca.markets)

### Optional
- `FLASK_ENV` - "development" or "production"
- `LOG_LEVEL` - "DEBUG", "INFO", "WARNING", "ERROR"

---

## Docker Setup (Advanced)

If you prefer Docker:

```bash
docker-compose up --build
```

This starts:
- Trading bot service
- Database
- Dashboard (port 5000)

---

## Verification Checklist

After setup, verify:

- [ ] Python 3.8+ installed
- [ ] Virtual environment active
- [ ] All dependencies installed (`pip list | grep trading-bot`)
- [ ] .env file created with Alpaca credentials
- [ ] `python -m pytest tests/` shows 32 passed
- [ ] `python -m trading_bot auto --help` shows help text
- [ ] Quick-start script is executable

---

## Next Steps

1. **First test:** Run a short paper trading session
   ```bash
   python -m trading_bot paper --symbols SPY --iterations 5 --no-ui
   ```

2. **View dashboard:** Run with UI
   ```bash
   python -m trading_bot auto
   ```
   Dashboard appears in terminal with real-time updates

3. **Check learned strategies:**
   ```bash
   ls -la .cache/strategy_learning/
   ```

4. **Inspect trades:**
   ```bash
   python -m trading_bot learn history --db data/trades.sqlite
   ```

5. **Run backtest:**
   ```bash
   python -m trading_bot backtest --symbols SPY,QQQ,IWM --period 1y
   ```

---

## Support

**Questions?** Check these files:
- `START_HERE.md` - Quick start guide
- `AUTO_START_GUIDE.md` - Detailed auto-start
- `README.md` - Full documentation
- `FINAL_STATUS.md` - System capabilities

**Issues?** See the logs:
```bash
tail -f bot_debug.log
```

---

## Success!

Once setup is complete, you can:

✅ Trade 24/7 (market open or closed)
✅ Automatically learn from every trade
✅ Build hybrid strategies
✅ Monitor in real-time
✅ Scale to 500+ stocks
✅ Deploy to cloud/Docker

**Ready?**
```bash
python -m trading_bot auto
```

Happy trading! 🚀
