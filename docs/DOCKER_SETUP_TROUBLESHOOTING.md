# Docker Installation & Setup Guide

## Issue: Docker Not Running

The Docker daemon is not running on your system. You have two options:

### Option 1: Install Docker Desktop (Recommended)

1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop
2. Run the installer
3. Complete the installation and restart your computer
4. Open PowerShell and run:
   ```powershell
   docker --version
   ```

### Option 2: Use Docker as a Service (WSL 2)

If you have Windows Subsystem for Linux (WSL 2) installed:
1. Install Docker Desktop
2. In Docker Desktop Settings > General, enable "Use the WSL 2 based engine"

## Alternative: Run Without Docker

If you can't install Docker, run the trading bot directly on your machine:

```powershell
cd "C:\Users\Ronald mcdonald\projects\algo-trading-bot"
python -m trading_bot paper --symbols AAPL,GOOGL,MSFT --period 6mo
```

This will run the trading bot and store data in `data/trades.sqlite`.

## Web Dashboard Without Docker

To run just the web dashboard:

```powershell
cd "C:\Users\Ronald mcdonald\projects\algo-trading-bot"
python -m pip install flask flask-cors
python -m trading_bot.ui.web
```

Then visit: http://localhost:5000

## After Installing Docker

Once Docker is installed and running, try:

```powershell
cd "C:\Users\Ronald mcdonald\projects\algo-trading-bot"
docker-compose up --build
```

You'll see:
- Web dashboard at http://localhost:5000
- PostgreSQL at localhost:5432
- Trading bot running in the background

---

**Need Docker?**
- Home Users: Download from docker.com (free Community Edition)
- Work/Enterprise: Check with your IT department
- Linux Server: Use your package manager (apt, yum, etc.)
