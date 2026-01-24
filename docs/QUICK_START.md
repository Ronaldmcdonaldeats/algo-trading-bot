# Quick Start Guide

## Fastest Startup (Recommended for Testing)

```powershell
python -m trading_bot start --no-ui --iterations 1 --ignore-market-hours --memory-mode
```

**What this does:**
- `--no-ui`: Disable Textual dashboard (text output only)
- `--iterations 1`: Run 1 iteration and exit (for testing)
- `--ignore-market-hours`: Skip market hours check
- `--memory-mode`: Use aggressive memory optimization (smaller batches)

**Defaults:**
- `--period`: 6mo (down from 1y) = 25% faster data loading
- `--launch-monitor`: Disabled (skips log viewer) = 5-10 seconds faster

**Startup time: 5-10 seconds**

---

## For Production/Monitoring

```powershell
# Paper trading with metrics display
python -m trading_bot start --no-ui --iterations 0 --max-symbols 50

# Output shows:
# [ITERATION 1] 2026-01-24 14:54:01 | Equity: $100,000.00 | P&L: +0.00 (+0.00%) | Sharpe: N/A | DD: 0.0% | Win Rate: N/A | Trades: 0 | Fills: 0
```

---

## Command Flags Reference

| Flag | Effect | Default | Use Case |
|------|--------|---------|----------|
| `--launch-monitor` | Launch log viewer window | Disabled | Monitor learning |
| `--memory-mode` | Smaller batches (10 vs 20) | Off | Low-memory systems |
| `--max-symbols N` | Limit to N stocks | All 76 | Fast testing |
| `--ignore-market-hours` | Run anytime | Off | Testing outside hours |
| `--iterations N` | Run N times (0=forever) | 0 | Testing vs continuous |
| `--no-ui` | Text output only | Off | Faster than Textual TUI |
| `--period PERIOD` | Historical period | 6mo | Change data window |

---

## Real-Time Metrics Now Available

Each iteration shows:
- **Sharpe Ratio**: Risk-adjusted return
- **Max Drawdown %**: Worst portfolio decline
- **Win Rate %**: Profitable trade percentage
- **Trades**: Number of trades executed
- **P&L**: Current profit/loss

Example output:
```
[ITERATION 5] 2026-01-24 15:02:34 | Equity: $102,450.50 | P&L: +2,450.50 (+2.45%) | Sharpe: +0.85 | DD: 1.2% | Win Rate: 62% | Trades: 8 | Fills: 2
```

---

## Configuration Validation

Config is validated on startup. If you get an error like:
```
[CONFIG ERROR] Configuration validation failed:
  • risk.max_risk_per_trade must be 0 < x <= 1.0, got 1.5
```

Check `configs/default.yaml`:
- `risk.max_risk_per_trade`: 0-1.0 (max 100% per trade)
- `risk.stop_loss_pct`: 0-0.5 (max 50% stop loss)
- `risk.take_profit_pct`: > stop_loss_pct

---

## Performance Tips

**Faster startup (already defaults):**
- Default period is now 6mo (vs 1y) = 25% less data
- Log viewer disabled by default = 5-10 seconds saved
- Use `--launch-monitor` if you want to see the learning monitor

**Faster processing:**
- Use `--memory-mode` (smaller batches)
- Use `--max-symbols 50` instead of all 76
- Use `--interval 4h` instead of `1d` (fewer bars to process)

**Lower memory:**
- `--memory-mode` (10-symbol batches)
- `--max-symbols 100` (for 200+ stocks)
- Default `--period 6mo` (125 bars vs 250)
