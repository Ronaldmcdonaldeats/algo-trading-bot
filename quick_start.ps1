# Quick-start script for Windows PowerShell
# Run this to automatically start trading with learning

Write-Host "========================================" -ForegroundColor Green
Write-Host "AI-Powered Trading Bot with Learning" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if Python is installed
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Found Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found! Install Python 3.8+ from https://www.python.org" -ForegroundColor Red
    exit 1
}

# Activate virtual environment if it exists
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "✓ Activating virtual environment..." -ForegroundColor Green
    & .venv\Scripts\Activate.ps1
} else {
    Write-Host "⚠ Virtual environment not found" -ForegroundColor Yellow
    Write-Host "Creating it now..." -ForegroundColor Yellow
    python -m venv .venv
    & .venv\Scripts\Activate.ps1
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -e .
}

Write-Host ""
Write-Host "Starting auto-trading..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Cyan
Write-Host ""

# Run the auto command
python -m trading_bot auto

Read-Host "Press Enter to exit"
