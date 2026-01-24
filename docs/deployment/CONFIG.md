# Configuration Guide

## Environment Setup

Configuration files control how your trading bot behaves. This guide covers all configuration options.

---

## Quick Setup (3 options)

### Option 1: Docker (Recommended)
```bash
# Copy default config
cp configs/default.yaml configs/production.yaml

# Edit your settings
nano configs/production.yaml

# Run with Docker
docker-compose up -d
```

### Option 2: Local Python
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Configure and run
python -m trading_bot --config configs/production.yaml
```

### Option 3: Live Trading (Alpaca)
```bash
# Set API keys
export ALPACA_API_KEY=your_key
export ALPACA_SECRET_KEY=your_secret

# Run with live trading enabled
python -m trading_bot --mode live --config configs/production.yaml
```

---

## Configuration File Structure

### Main Config (configs/default.yaml)

```yaml
# Trading Mode
mode: paper                    # "paper" or "live"
symbols:                       # Symbols to trade
  - AAPL
  - MSFT
  - NVDA

# Algorithm Configuration
algorithms:
  - name: atr_breakout
    enabled: true
    weight: 1.2               # Relative strength (higher = more weight)
    params:
      period: 14
      multiplier: 2.0

  - name: rsi_mean_reversion
    enabled: true
    weight: 1.0
    params:
      period: 14
      threshold: 70           # Overbought

# Concurrent Execution
concurrent:
  max_workers: 4              # Number of parallel threads
  timeout_seconds: 5          # Per-algorithm timeout
  batch_window_ms: 50         # Order batching window
  cache_size: 256             # LRU cache entries
  cache_ttl_seconds: 60       # Cache expiration

# Market Regimes
market_detection:
  enabled: true               # Auto-detect trending/ranging/volatile
  lookback_periods: 50        # Analysis window
  regime_thresholds:
    trending_threshold: 0.65
    ranging_threshold: 0.35

# Risk Management
risk:
  max_position_size: 0.05     # % of portfolio per trade
  max_daily_loss: 0.02        # Stop trading if -2% loss
  max_drawdown: 0.10          # Maximum drawdown tolerance
  stop_loss_pct: 2.0          # % below entry price
  take_profit_pct: 5.0        # % above entry price

# Data & Indicators
data:
  provider: "yahoo"           # "yahoo" or "alpaca"
  lookback_days: 60
  timeframe: "1d"             # "1d", "1h", "15m", "5m"

indicators:
  cache_enabled: true         # Enable calculation caching
  atr_period: 14
  rsi_period: 14
  macd_fast: 12
  macd_slow: 26
  macd_signal: 9

# Backtest Configuration
backtest:
  enabled: false              # Set to true to backtest instead of live
  start_date: "2023-01-01"
  end_date: "2024-01-01"
  initial_capital: 100000

# Dashboard & Monitoring
dashboard:
  enabled: true               # Enable real-time dashboard
  port: 8501                  # Streamlit port
  update_frequency_seconds: 2 # Refresh rate

# Logging & Reporting
logging:
  level: "INFO"               # "DEBUG", "INFO", "WARNING", "ERROR"
  file: "trading_bot.log"
  
reporting:
  daily_email_enabled: false  # Send daily summary email
  email_to: "your@email.com"
  smtp_server: "smtp.gmail.com"
  smtp_port: 587

# Alpaca Integration (Live Trading)
alpaca:
  api_key: "${ALPACA_API_KEY}"          # Use environment variables
  secret_key: "${ALPACA_SECRET_KEY}"
  base_url: "https://paper-api.alpaca.markets"  # Use paper trading by default
  timeout_seconds: 30
```

---

## Environment Variables

Override config file settings with environment variables:

```bash
# Alpaca credentials (NEVER commit these!)
export ALPACA_API_KEY=your_actual_key
export ALPACA_SECRET_KEY=your_actual_secret

# Trading mode
export TRADING_MODE=live              # or "paper"

# Algorithm weights
export ATR_BREAKOUT_WEIGHT=1.2
export RSI_WEIGHT=1.0

# Risk limits
export MAX_POSITION_SIZE=0.05
export MAX_DAILY_LOSS=0.02

# Performance tuning
export MAX_WORKERS=4
export CACHE_SIZE=256
export BATCH_WINDOW_MS=50
```

---

## Configuration Profiles

### Development (Default)
```yaml
mode: paper
concurrent.max_workers: 2        # Fewer threads
concurrent.cache_size: 64        # Smaller cache
logging.level: DEBUG             # Verbose logs
dashboard.enabled: true          # Always show dashboard
```

### Production
```yaml
mode: paper                       # Start with paper trading
concurrent.max_workers: 8         # Full parallelization
concurrent.cache_size: 512        # Large cache
logging.level: WARNING            # Less verbose
dashboard.enabled: true           # Monitor live
risk.max_daily_loss: 0.02        # Strict limits
```

### Live Trading
```yaml
mode: live                        # REAL MONEY
concurrent.max_workers: 6
risk.max_position_size: 0.02      # Half of paper
risk.max_daily_loss: 0.01         # Stricter limits
risk.max_drawdown: 0.05           # More conservative
logging.level: INFO               # Good detail
alpaca.base_url: "https://api.alpaca.markets"  # REAL API
```

### Backtest
```yaml
backtest.enabled: true
backtest.start_date: "2023-01-01"
backtest.end_date: "2024-01-01"
mode: paper                       # Simulate paper trading
concurrent.max_workers: 1         # Sequential for debugging
logging.level: DEBUG              # Show all details
```

---

## Common Configuration Scenarios

### Scenario 1: Fast Day Trading
```yaml
timeframe: "5m"                   # 5-minute bars
lookback_days: 5                  # Recent data only
max_position_size: 0.05
take_profit_pct: 1.5
stop_loss_pct: 0.5
max_workers: 8                    # Maximum parallelization
```

### Scenario 2: Swing Trading (2-5 days)
```yaml
timeframe: "1d"                   # Daily bars
lookback_days: 60                 # 2-3 months history
max_position_size: 0.03
take_profit_pct: 5.0
stop_loss_pct: 2.0
max_workers: 4                    # Moderate parallelization
```

### Scenario 3: Conservative Long-Term
```yaml
timeframe: "1d"                   # Daily bars
lookback_days: 365                # Year of history
max_position_size: 0.02           # Smaller positions
take_profit_pct: 10.0             # Bigger targets
stop_loss_pct: 5.0                # Wider stops
max_drawdown: 0.05                # Strict drawdown
max_daily_loss: 0.01              # Stop daily loss
```

### Scenario 4: High-Frequency with Caching
```yaml
timeframe: "1m"                   # 1-minute bars
cache_ttl_seconds: 30             # Fresh data
cache_size: 1024                  # Large cache
batch_window_ms: 20               # Tight batching
max_workers: 8                    # Full CPU
concurrent.timeout_seconds: 2     # Tight timeout
```

---

## Validation & Testing

### Check Configuration Syntax
```bash
python -c "from trading_bot.config import load_config; load_config('configs/production.yaml')"
```

### Validate with Dry Run
```bash
python -m trading_bot --dry-run --config configs/production.yaml
```

### Test Individual Settings
```python
from trading_bot.config import load_config

config = load_config('configs/production.yaml')
print(f"Mode: {config.mode}")
print(f"Symbols: {config.symbols}")
print(f"Max workers: {config.concurrent.max_workers}")
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Config not loading** | Check YAML syntax with `python -m yaml path/to/config.yaml` |
| **Alpaca connection fails** | Verify API keys with `echo $ALPACA_API_KEY` |
| **Dashboard not starting** | Check port not in use: `netstat -ano \| findstr :8501` |
| **Too slow** | Increase `max_workers` and `cache_size` |
| **Too risky** | Decrease `max_position_size` and `take_profit_pct` |
| **Memory issues** | Reduce `cache_size` or `lookback_days` |

---

## Next Steps

1. **Copy default config**: `cp configs/default.yaml configs/production.yaml`
2. **Edit your settings**: Update symbols, risk limits, algorithm weights
3. **Validate**: Run `python -m trading_bot --dry-run --config configs/production.yaml`
4. **Test with paper trading**: `mode: paper` before `mode: live`
5. **Monitor**: Check dashboard at `http://localhost:8501`

See [Docker Deployment](DOCKER.md) for containerized setup, or [Quick Start](../getting-started/QUICK_START.md) for 5-minute setup.
