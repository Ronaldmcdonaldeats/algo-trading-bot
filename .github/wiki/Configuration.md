# Configuration

Complete guide to configuring your trading bot.

---

## Configuration File

Main config file: `configs/production.yaml`

```yaml
# Trading Mode
mode: paper                    # "paper" or "live"
symbols:
  - AAPL
  - MSFT
  - NVDA

# Algorithm Configuration
algorithms:
  - name: atr_breakout
    enabled: true
    weight: 1.2
    params:
      period: 14
      multiplier: 2.0

  - name: rsi_mean_reversion
    enabled: true
    weight: 1.0
    params:
      period: 14
      threshold: 70

# Concurrent Execution
concurrent:
  max_workers: 4              # Parallel threads
  timeout_seconds: 5
  batch_window_ms: 50
  cache_size: 256

# Market Regimes
market_detection:
  enabled: true
  lookback_periods: 50

# Risk Management
risk:
  max_position_size: 0.05
  max_daily_loss: 0.02
  max_drawdown: 0.10
  stop_loss_pct: 2.0
  take_profit_pct: 5.0

# Data
data:
  provider: "yahoo"
  lookback_days: 60
  timeframe: "1d"
```

---

## Environment Variables

Override config with environment variables:

```bash
# Alpaca credentials (NEVER commit!)
export ALPACA_API_KEY=your_key
export ALPACA_SECRET_KEY=your_secret

# Trading mode
export TRADING_MODE=live

# Algorithm weights
export ATR_BREAKOUT_WEIGHT=1.2
```

---

## Configuration Profiles

### Development
```yaml
mode: paper
max_workers: 2
cache_size: 64
logging.level: DEBUG
```

### Production
```yaml
mode: paper
max_workers: 8
cache_size: 512
logging.level: WARNING
risk.max_daily_loss: 0.02
```

### Live Trading
```yaml
mode: live
max_workers: 6
risk.max_position_size: 0.02
risk.max_daily_loss: 0.01
```

---

## Common Scenarios

### Day Trading (5-minute bars)
```yaml
timeframe: "5m"
lookback_days: 5
max_position_size: 0.05
take_profit_pct: 1.5
stop_loss_pct: 0.5
max_workers: 8
```

### Swing Trading (1-day bars)
```yaml
timeframe: "1d"
lookback_days: 60
max_position_size: 0.03
take_profit_pct: 5.0
stop_loss_pct: 2.0
max_workers: 4
```

### Conservative Long-Term
```yaml
timeframe: "1d"
lookback_days: 365
max_position_size: 0.02
take_profit_pct: 10.0
stop_loss_pct: 5.0
max_drawdown: 0.05
```

---

## All Settings Reference

| Setting | Values | Default | Notes |
|---------|--------|---------|-------|
| `mode` | paper, live | paper | paper=safe, live=real money |
| `max_workers` | 1-8 | 4 | Parallel threads |
| `timeout_seconds` | 1-30 | 5 | Per-algorithm timeout |
| `max_position_size` | 0.01-0.20 | 0.05 | % of portfolio |
| `max_daily_loss` | 0.01-0.10 | 0.02 | Stop trading at -2% |
| `max_drawdown` | 0.05-0.50 | 0.10 | Max loss before stopping |
| `stop_loss_pct` | 0.5-5.0 | 2.0 | % below entry |
| `take_profit_pct` | 2.0-20.0 | 5.0 | % above entry |
| `cache_size` | 64-1024 | 256 | Calculation cache entries |
| `cache_ttl_seconds` | 10-120 | 60 | Cache expiration time |

---

## Validation

Check your configuration:

```bash
python -c "from trading_bot.config import load_config; load_config('configs/production.yaml')"
```

---

## Next

- **Quick Start**: [Get running](Quick-Start)
- **Features**: [What can it do?](Features)
- **Docker**: [Deploy to production](Docker)
