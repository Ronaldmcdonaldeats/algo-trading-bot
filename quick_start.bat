@echo off
REM Quick-start script for Windows
REM Run this file to automatically start trading with learning

echo ========================================
echo AI-Powered Trading Bot with Learning
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.8+ from https://www.python.org
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
) else (
    echo WARNING: Virtual environment not found
    echo Creating it now...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -e .
)

echo.
echo Starting auto-trading...
echo Press Ctrl+C to stop
echo.

REM Run the auto command
python -m trading_bot auto

pause
