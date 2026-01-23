# Phase 4: Quick Start Guide

## Setup (One-Time)

### 1. Get Alpaca API Credentials
- Sign up at https://app.alpaca.markets
- Go to Settings → API Keys
- Copy your **API Key ID** and **Secret Key**

### 2. Configure Environment
Edit `.env` or set environment variables:
```bash
set APCA_API_KEY_ID=your_key_here
set APCA_API_SECRET_KEY=your_secret_here
set APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

### 3. Verify Setup
```bash
python -m trading_bot live paper --help
```

---

## Paper Trading (Sandbox - No Real Money)

### Run Paper Trading
```bash
python -m trading_bot live paper \
    --config configs/default.yaml \
    --symbols AAPL MSFT GOOGL \
    --period 30d \
    --interval 1d \
    --iterations 5
```

### Parameters
- `--symbols`: Stock symbols to trade (space-separated)
- `--period`: Data lookback period (1d, 5d, 1mo, 3mo, 6mo, 1y)
- `--interval`: Bar interval (1m, 5m, 15m, 1h, 1d)
- `--iterations`: Number of trading cycles (0 = infinite)

### Expected Output
```
[LIVE] Paper Trading Mode on Alpaca
[LIVE] Connected to: https://paper-api.alpaca.markets
[PORTFOLIO] Cash: $99,500.00 | Equity: $100,245.32
[ITERATION 1] Trading...
```

---

## Live Trading (Real Money - WARNING!)

### Enable Live Mode
First, set live API endpoint:
```bash
set APCA_API_BASE_URL=https://api.alpaca.markets
```

### Run Live Trading
```bash
python -m trading_bot live trading \
    --config configs/default.yaml \
    --symbols AAPL \
    --enable-live \
    --max-drawdown 5.0 \
    --max-daily-loss 2.0 \
    --iterations 10
```

### Parameters
- `--enable-live`: **REQUIRED** - explicit safety flag
- `--symbols`: Symbols to trade
- `--max-drawdown`: Kill switch % (stops if exceeded)
- `--max-daily-loss`: Daily loss limit %
- `--iterations`: Number of trading cycles

### Safety Confirmation
You'll see a warning banner and must type:
```
Type 'YES I UNDERSTAND' to proceed with live trading:
```

---

## Monitoring

### Check Paper Account Status
```bash
# During paper trading, Alpaca dashboard shows:
# https://app.alpaca.markets/paper/dashboard
```

### Check Live Account Status
```bash
# Live trading:
# https://app.alpaca.markets/dashboard
```

### Database Logs
All trades logged to SQLite:
```bash
sqlite3 trades.sqlite
> SELECT * FROM order_filled ORDER BY timestamp DESC LIMIT 5;
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Credentials not found" | Set APCA_API_KEY_ID, APCA_API_SECRET_KEY, APCA_API_BASE_URL |
| "No data returned" | Verify symbols exist and period is valid |
| "No signals generated" | Check strategy parameters in config file |
| Can't connect to live | Confirm APCA_API_BASE_URL is https://api.alpaca.markets |
| Order rejected | Check market hours and buying power |

---

## Configuration (configs/default.yaml)

```yaml
portfolio:
  starting_cash: 100000

risk:
  max_position_pct: 10
  stop_loss_pct: 5
  take_profit_pct: 10

strategy:
  raw:
    rsi_period: 14
    rsi_overbought: 70
    rsi_oversold: 30
```

---

## Stopping Trading

Press `Ctrl+C` to stop at any time. The system will:
1. Log final portfolio status
2. Report session PnL
3. Exit gracefully

---

## Safety Features

✅ **User Confirmation**: Must type "YES I UNDERSTAND" for live trading  
✅ **Drawdown Kill Switch**: Stops trading if drawdown exceeds limit  
✅ **Daily Loss Limit**: Prevents trading once daily loss reached  
✅ **Position Sizing**: Limits position size to % of equity  
✅ **Audit Trail**: All trades logged to database  

---

## Common Commands

### Paper Trading 1-Hour Test
```bash
python -m trading_bot live paper --config configs/default.yaml --symbols AAPL --iterations 1
```

### Live Trading with Conservative Limits
```bash
python -m trading_bot live trading --config configs/default.yaml --symbols AAPL --enable-live --max-drawdown 3.0 --max-daily-loss 1.0
```

### Multi-Symbol Paper Trading
```bash
python -m trading_bot live paper --config configs/default.yaml --symbols AAPL MSFT GOOGL TSLA --period 60d
```

---

## API Reference

### Paper Trading Function
```python
from trading_bot.live.runner import run_live_paper_trading

result = run_live_paper_trading(
    config_path="configs/default.yaml",
    symbols=["AAPL", "MSFT"],
    period="60d",
    interval="1d",
    start_cash=100000.0,
    iterations=10
)

print(f"Trades: {result.total_trades}, PnL: ${result.total_pnl:.2f}")
```

### Live Trading Function
```python
from trading_bot.live.runner import run_live_real_trading

result = run_live_real_trading(
    config_path="configs/default.yaml",
    symbols=["AAPL"],
    max_drawdown_pct=5.0,
    max_daily_loss_pct=2.0,
    iterations=10
)
```

---

## Next Steps

1. **Test paper trading** with 1-2 iterations
2. **Monitor orders** in Alpaca dashboard
3. **Review logs** to verify signal generation
4. **Adjust parameters** if needed
5. **Enable live trading** when confident

---

## Support

- Alpaca API Docs: https://alpaca.markets/docs/api-references/
- Trading Config: See `configs/default.yaml`
- Strategy Docs: See `src/trading_bot/strategy/`
- Learning Docs: See `PHASE_3_AND_CLI_COMPLETE.md`

Phase 4 is ready for production use!
