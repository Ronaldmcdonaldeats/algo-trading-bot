# Troubleshooting

Common issues and solutions.

---

## Docker Issues

### Port Already in Use

**Error**: `Address already in use`

**Solution**:
```bash
# Change port in docker-compose.yml
ports:
  - "8502:8501"  # Use different port

# Or stop other containers
docker-compose down
```

### Container Crashes

**Error**: Container exits immediately

**Solution**:
```bash
# Check logs
docker-compose logs trading_bot

# Check configuration
cat configs/production.yaml

# Verify environment variables
echo $ALPACA_API_KEY
```

### Config File Not Found

**Error**: `FileNotFoundError: configs/production.yaml`

**Solution**:
```bash
# Check volume mount in docker-compose.yml
volumes:
  - ./configs:/app/configs

# Copy default config
cp configs/default.yaml configs/production.yaml
```

---

## Configuration Issues

### Invalid Configuration

**Error**: `YAML parsing error` or `missing required field`

**Solution**:
```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('configs/production.yaml'))"

# Check for required fields
# mode: paper|live
# symbols: list
# algorithms: list
```

### Algorithm Weight Issues

**Error**: Algorithms not triggering or weird behavior

**Solution**:
```yaml
algorithms:
  - name: atr_breakout
    weight: 1.2  # Must be > 0
    enabled: true  # Make sure enabled
```

---

## Data & Market Issues

### No Market Data

**Error**: `No data available` or `connection timeout`

**Solution**:
```bash
# Check data provider
# In config:
data:
  provider: "yahoo"  # or "alpaca"

# Check internet connection
ping yahoo.com

# Verify symbols are valid
# AAPL, MSFT, NVDA (valid)
# XYZ123 (invalid)
```

### Historical Data Not Available

**Error**: `Not enough historical data`

**Solution**:
```yaml
data:
  lookback_days: 60  # Need at least 60 days
  # For weekend/holiday, add extra days
```

---

## API & Trading Issues

### Alpaca API Key Errors

**Error**: `Authentication failed` or `401 Unauthorized`

**Solution**:
```bash
# Verify API keys are set
echo $ALPACA_API_KEY
echo $ALPACA_SECRET_KEY

# Check they're actually your keys (not placeholder)
# Keys should be long alphanumeric strings

# For paper trading, make sure you're using paper API:
# https://paper-api.alpaca.markets
```

### Orders Not Executing

**Error**: Orders submitted but not filled

**Solution**:
```bash
# Check trading mode
# mode: paper (test)
# mode: live (real money)

# Check market hours (9:30 AM - 4:00 PM ET)
# Orders won't execute outside market hours

# Check position size
risk:
  max_position_size: 0.05  # % of portfolio
```

### Insufficient Funds

**Error**: `InsufficientBuyingPower` or similar

**Solution**:
```yaml
# Reduce position size
risk:
  max_position_size: 0.02  # Was 0.05

# Or check account balance
# Paper: Set initial_capital in config
# Live: Check Alpaca dashboard
```

---

## Performance Issues

### Bot Running Slow

**Error**: Execution time > 100ms per cycle

**Solution**:
```yaml
# Increase parallelization
concurrent:
  max_workers: 8  # Was 4
  cache_size: 512  # Was 256

# Reduce lookback
data:
  lookback_days: 30  # Was 60
```

### High Memory Usage

**Error**: Bot consuming lots of RAM

**Solution**:
```yaml
# Reduce cache
concurrent:
  cache_size: 128  # Was 256

# Reduce lookback
data:
  lookback_days: 30  # Was 60

# Docker: Increase memory limit
# Docker Desktop → Preferences → Resources
```

### Dashboard Not Updating

**Error**: Dashboard frozen or not refreshing

**Solution**:
```bash
# Restart dashboard
docker-compose restart

# Check port
# Should be 8501 (Docker)
# Should be 8000 (Local)

# Clear cache
# Browser: Ctrl+Shift+Delete
```

---

## Risk Management Issues

### Max Daily Loss Triggered

**Error**: Bot stops trading after -2% loss

**Solution**:
```yaml
# Adjust daily loss limit
risk:
  max_daily_loss: 0.03  # Was 0.02 (now -3%)

# Or review strategy
# Check win rate and average loss
```

### Max Drawdown Exceeded

**Error**: Bot goes into defensive mode

**Solution**:
```yaml
# Adjust drawdown limit
risk:
  max_drawdown: 0.15  # Was 0.10 (now -15%)

# Or reduce position size
risk:
  max_position_size: 0.02  # Was 0.05
```

---

## Logging & Debugging

### Enable Debug Logging

```yaml
logging:
  level: DEBUG  # Was INFO
```

### View Logs

```bash
# Docker
docker-compose logs -f trading_bot

# Local
tail -f trading_bot.log

# Show last 50 lines
docker-compose logs -f --tail 50 trading_bot
```

### Check Specific Errors

```bash
# Search logs for errors
docker-compose logs trading_bot | grep ERROR

# Search for specific symbol
docker-compose logs trading_bot | grep AAPL
```

---

## Testing Your Setup

```bash
# Test imports
python -c "from trading_bot.learn.orchestrator import MultiAlgorithmOrchestrator"

# Test data provider
python -c "from trading_bot.data.providers import YahooDataProvider; p = YahooDataProvider(); print(p.get_data('AAPL'))"

# Test configuration
python -c "from trading_bot.config import load_config; config = load_config('configs/production.yaml'); print(config)"

# Test Docker
docker-compose up -d
docker-compose ps  # Should show trading_bot running
docker-compose logs trading_bot | tail -20
```

---

## Still Having Issues?

1. **Check logs** - `docker-compose logs trading_bot`
2. **Verify configuration** - `cat configs/production.yaml`
3. **Test imports** - `python -c "import trading_bot"`
4. **Check environment** - `echo $ALPACA_API_KEY`
5. **Review [Quick Start](Quick-Start)** - Verify setup
6. **Check [Configuration](Configuration)** - Verify settings

---

## Getting Help

- **GitHub Issues**: [Report a bug](https://github.com/yourusername/algo-trading-bot/issues)
- **Discussions**: [Ask questions](https://github.com/yourusername/algo-trading-bot/discussions)
- **Documentation**: [Read the wiki](/)

---

## Next

- **Quick Start**: [Get running](Quick-Start)
- **Configuration**: [Customize settings](Configuration)
- **Docker**: [Deployment guide](Docker)
