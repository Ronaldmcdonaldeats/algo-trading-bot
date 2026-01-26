@echo off
REM Windows deployment script for Algo Trading Bot with Ultimate Hybrid Strategy
REM Usage: deploy.bat

echo.
echo ==========================================
echo Algo Trading Bot - Deployment
echo Strategy: Ultimate Hybrid
echo ==========================================
echo.

REM 1. Build Docker image
echo Building Docker image...
docker build -t algo-trading-bot:latest .
echo.

REM 2. Stop existing containers
echo Stopping existing containers...
docker-compose down 2>nul || echo No containers running
echo.

REM 3. Start containers
echo Starting containers...
docker-compose up -d
echo.

REM 4. Wait for startup
echo Waiting for services to start (10 seconds)...
timeout /t 10 /nobreak

REM 5. Show status
echo.
echo Checking container status...
docker ps
echo.

echo ==========================================
echo DEPLOYMENT COMPLETE
echo ==========================================
echo.
echo Dashboard URL: http://localhost:5000
echo Strategy: Ultimate Hybrid (426%% backtest return)
echo Database: PostgreSQL (localhost:5432)
echo.
echo View logs:
echo   docker logs -f trading-bot-dashboard
echo.
echo Stop all:
echo   docker-compose down
echo.

pause
