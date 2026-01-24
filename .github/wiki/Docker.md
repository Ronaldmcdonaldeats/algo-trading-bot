# Docker

Production-ready Docker deployment guide.

---

## Quick Start

```bash
# Clone
git clone https://github.com/yourusername/algo-trading-bot.git
cd algo-trading-bot

# Paper trading
docker-compose up --build

# Access dashboard
open http://localhost:8501
```

---

## Setup with Environment Variables

```bash
# Create .env file
cat > .env << EOF
TRADING_MODE=paper
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
MAX_WORKERS=4
CACHE_SIZE=256
EOF

# Run
docker-compose --env-file .env up -d
```

---

## Configuration

### Update Configuration
```bash
# Edit your settings
nano configs/production.yaml

# Update symbols, risk limits, weights
# Mount in docker-compose.yml volumes section
```

### Environment Variables
```bash
# In .env or docker-compose.yml
TRADING_MODE=paper
ALPACA_API_KEY=your_key
MAX_WORKERS=4
CACHE_SIZE=256
```

---

## Docker Compose Structure

```yaml
version: '3.8'

services:
  trading_bot:
    build: .
    container_name: trading_bot
    environment:
      - TRADING_MODE=paper
    ports:
      - "8501:8501"              # Dashboard
    volumes:
      - ./configs:/app/configs    # Config files
      - ./logs:/app/logs          # Logs
    restart: unless-stopped
```

---

## Common Commands

```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f trading_bot

# Stop
docker-compose stop

# Restart
docker-compose restart

# Shell into container
docker-compose exec trading_bot bash

# Remove everything
docker-compose down -v
```

---

## Deployment Scenarios

### Local Development
```bash
# Hot-reload on code changes
volumes:
  - ./src:/app/src              # Mount source
docker-compose up
```

### Production
```bash
# Strict environment
TRADING_MODE=live
MAX_WORKERS=8
CACHE_SIZE=512
risk.max_daily_loss=0.01
```

### Cloud (AWS/GCP/Azure)
```bash
# Push to registry
docker tag algo-trading-bot:latest myregistry/algo-trading-bot:latest
docker push myregistry/algo-trading-bot:latest

# Deploy from registry
docker run -e TRADING_MODE=paper -p 8501:8501 myregistry/algo-trading-bot:latest
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Port in use** | Change port: `8502:8501` |
| **Container crashes** | Check logs: `docker-compose logs trading_bot` |
| **Config not found** | Mount volume: `- ./configs:/app/configs` |
| **API key errors** | Verify .env file or environment variables |
| **Out of memory** | Increase Docker memory in settings |

---

## Production Checklist

- [ ] Use `.env` file for secrets (never commit!)
- [ ] Set `TRADING_MODE=paper` for testing
- [ ] Configure risk limits properly
- [ ] Monitor dashboard at http://localhost:8501
- [ ] Test with paper trading for 1-2 weeks
- [ ] Only then switch to `TRADING_MODE=live`
- [ ] Set up log rotation
- [ ] Plan for backup and recovery

---

## Next

- **Configuration**: [Customize settings](Configuration)
- **Monitoring**: [Health checks](Monitoring)
- **Troubleshooting**: [Common issues](Troubleshooting)
