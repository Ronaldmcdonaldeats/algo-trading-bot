# Docker Deployment Guide

## Overview

Docker makes deployment consistent across all systems. This guide covers containerized setup.

---

## Prerequisites

- **Docker**: [Install Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Docker Compose**: Usually included with Docker Desktop
- **Git**: To clone the repository
- **API Keys** (for live trading): Alpaca account and API credentials

Verify installation:
```bash
docker --version          # Should be 20.10+
docker-compose --version  # Should be 1.29+
```

---

## Quick Start (2 minutes)

### 1. Clone and Prepare
```bash
git clone https://github.com/yourusername/algo-trading-bot.git
cd algo-trading-bot

# Copy default config
cp configs/default.yaml configs/production.yaml

# Update symbols and parameters in production.yaml
nano configs/production.yaml  # Edit as needed
```

### 2. Run with Docker Compose
```bash
# Paper trading (safe, no money at risk)
docker-compose up -d

# View logs
docker-compose logs -f trading_bot

# Stop when done
docker-compose down
```

### 3. Access Dashboard
- **Dashboard**: http://localhost:8501
- **Logs**: `docker-compose logs trading_bot`
- **Container**: `docker ps` to see running containers

---

## Configuration for Docker

### Using Environment Variables

```bash
# Create .env file
cat > .env << EOF
TRADING_MODE=paper
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
MAX_WORKERS=4
CACHE_SIZE=256
EOF

# Run with environment variables
docker-compose --env-file .env up -d
```

### Using Config Files

```bash
# Edit configuration
nano configs/production.yaml

# Mount config file in docker-compose.yml
# (see docker-compose.yml volumes section)

# Run
docker-compose up -d
```

---

## Docker Compose File

The `docker-compose.yml` includes:

```yaml
version: '3.8'

services:
  trading_bot:
    build: .
    container_name: trading_bot
    environment:
      - TRADING_MODE=paper
      - ALPACA_API_KEY=${ALPACA_API_KEY}
      - ALPACA_SECRET_KEY=${ALPACA_SECRET_KEY}
      - MAX_WORKERS=4
      - CACHE_SIZE=256
    ports:
      - "8501:8501"              # Dashboard
    volumes:
      - ./configs:/app/configs    # Config files
      - ./logs:/app/logs          # Log files
      - trading_data:/app/data    # Data persistence
    restart: unless-stopped

  # Optional: PostgreSQL for trade history
  postgres:
    image: postgres:15-alpine
    container_name: trading_bot_db
    environment:
      - POSTGRES_DB=trading_bot
      - POSTGRES_USER=trader
      - POSTGRES_PASSWORD=secure_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  trading_data:
  postgres_data:
```

---

## Dockerfile

The project includes a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY pyproject.toml setup.py* ./

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src ./src
COPY configs ./configs

# Create logs directory
RUN mkdir -p logs data

# Expose dashboard port
EXPOSE 8501

# Run trading bot
CMD ["python", "-m", "trading_bot", "--config", "configs/production.yaml"]
```

---

## Common Deployment Scenarios

### Scenario 1: Paper Trading (Safe Testing)
```bash
# .env file
TRADING_MODE=paper
MAX_WORKERS=4

# Run
docker-compose up -d

# Monitor at http://localhost:8501
```

### Scenario 2: Live Trading (Real Money ⚠️)
```bash
# .env file - KEEP THIS SECURE!
TRADING_MODE=live
ALPACA_API_KEY=your_real_key
ALPACA_SECRET_KEY=your_real_secret
MAX_WORKERS=4

# Run
docker-compose up -d

# Monitor at http://localhost:8501
```

### Scenario 3: Development with Live Reload
```bash
# docker-compose.yml modification
volumes:
  - ./src:/app/src              # Auto-reload code changes
  - ./configs:/app/configs

# Run with
docker-compose up -d

# Edit code and it reloads automatically
```

### Scenario 4: Production on Cloud (AWS/GCP/Azure)

#### AWS EC2
```bash
# SSH into instance
ssh -i key.pem ec2-user@instance-ip

# Install Docker
sudo yum update && sudo yum install docker docker-compose

# Clone and run
git clone <repo>
cd algo-trading-bot
docker-compose up -d
```

#### Google Cloud Run
```bash
# Push to Google Container Registry
docker tag algo-trading-bot gcr.io/PROJECT_ID/algo-trading-bot
docker push gcr.io/PROJECT_ID/algo-trading-bot

# Deploy
gcloud run deploy algo-trading-bot \
  --image gcr.io/PROJECT_ID/algo-trading-bot \
  --set-env-vars TRADING_MODE=paper
```

#### Docker Hub
```bash
# Build and push
docker build -t yourusername/algo-trading-bot:latest .
docker push yourusername/algo-trading-bot:latest

# Others can run with
docker run -p 8501:8501 yourusername/algo-trading-bot:latest
```

---

## Docker Commands Reference

### Common Commands
```bash
# Start containers
docker-compose up -d

# View logs
docker-compose logs -f trading_bot        # Stream logs
docker-compose logs --tail 50 trading_bot # Last 50 lines

# Stop containers
docker-compose stop

# Restart
docker-compose restart

# Remove containers and volumes
docker-compose down -v

# Execute command in container
docker-compose exec trading_bot bash
docker-compose exec trading_bot python -c "import trading_bot"

# View container status
docker-compose ps

# View container resource usage
docker stats trading_bot
```

### Build Commands
```bash
# Build image
docker-compose build

# Build without cache
docker-compose build --no-cache

# View images
docker images

# Remove old images
docker image prune -a
```

---

## Persistence & Data

### Volume Mounting

```yaml
volumes:
  - ./configs:/app/configs      # Config files (host → container)
  - ./logs:/app/logs            # Log files (container → host)
  - trading_data:/app/data      # Named volume (docker managed)
  - postgres_data:/var/lib/postgresql/data
```

### Data Locations
```
Host Machine          Container
./configs/        →   /app/configs      (read/write)
./logs/           →   /app/logs         (write)
trading_data/*    →   /app/data         (database)
```

### Backup Strategy
```bash
# Backup logs
docker-compose cp trading_bot:/app/logs ./backups/logs_$(date +%Y%m%d)

# Backup database volume
docker run --rm -v trading_data:/data -v $(pwd)/backups:/backup \
  ubuntu tar czf /backup/trading_data.tar.gz /data

# Restore
docker run --rm -v trading_data:/data -v $(pwd)/backups:/backup \
  ubuntu tar xzf /backup/trading_data.tar.gz
```

---

## Networking

### Port Mappings
```yaml
ports:
  - "8501:8501"     # Dashboard (Streamlit)
  - "8000:8000"     # API server (optional)
  - "5432:5432"     # PostgreSQL (optional)
```

### Container Communication
```bash
# Containers can communicate by service name
# Example: trading_bot can connect to postgres:5432

# Host can access at localhost:5432
```

### Multi-Container Setup
```yaml
services:
  trading_bot:
    # Can reach postgres at postgres:5432
    environment:
      - DATABASE_URL=postgresql://trader:password@postgres:5432/trading_bot

  postgres:
    # Database service
    environment:
      - POSTGRES_PASSWORD=password
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Port 8501 already in use** | Change port mapping: `8502:8501` or stop other containers |
| **Container crashes** | Check logs: `docker-compose logs trading_bot` |
| **Config file not found** | Mount volume: `volumes: - ./configs:/app/configs` |
| **API key errors** | Check `.env` file and Docker environment vars |
| **Out of memory** | Increase Docker memory limit in Docker Desktop settings |
| **Slow performance** | Increase CPU cores in Docker Desktop settings |
| **Database connection fails** | Ensure postgres container is running: `docker-compose ps` |
| **Permission denied errors** | Run as root or adjust volume permissions |

### Debug Commands
```bash
# Shell into container
docker-compose exec trading_bot /bin/bash

# Check environment variables
docker-compose exec trading_bot env

# Check network connectivity
docker-compose exec trading_bot ping postgres

# View detailed logs
docker-compose logs --follow --timestamps trading_bot

# Inspect container
docker inspect trading_bot_trading_bot_1
```

---

## Production Checklist

- ✅ Use `.env` file for secrets (never commit!)
- ✅ Set `TRADING_MODE=paper` first to test
- ✅ Configure risk limits properly in `configs/production.yaml`
- ✅ Monitor dashboard at http://localhost:8501
- ✅ Set up log rotation (optional)
- ✅ Enable database persistence (optional)
- ✅ Test with paper trading for 1-2 weeks
- ✅ Only then switch to `TRADING_MODE=live`
- ✅ Set up monitoring/alerting
- ✅ Plan for backup and recovery

---

## Performance Optimization

```yaml
# In docker-compose.yml
services:
  trading_bot:
    deploy:
      resources:
        limits:
          cpus: '2'          # Limit to 2 CPUs
          memory: 2G         # Limit to 2GB RAM
        reservations:
          cpus: '1'          # Reserve 1 CPU minimum
          memory: 1G         # Reserve 1GB minimum
```

---

## Health Checks

```yaml
services:
  trading_bot:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## Next Steps

1. **Test Locally**: Run `docker-compose up -d` and access dashboard
2. **Configure**: Update `configs/production.yaml` for your symbols
3. **Test Paper Trading**: Run for 1-2 weeks with `TRADING_MODE=paper`
4. **Add Persistence**: Set up database if needed
5. **Deploy to Cloud**: Push to AWS/GCP/Azure when confident

See [Configuration Guide](CONFIG.md) for detailed settings, or [Quick Start](../getting-started/QUICK_START.md) for other deployment methods.
