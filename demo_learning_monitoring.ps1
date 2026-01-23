#!/usr/bin/env powershell
<#
.SYNOPSIS
Demonstrates concurrent paper trading + learning CLI inspection.

.DESCRIPTION
Terminal 1: Runs continuous paper trading with adaptive learning
Terminal 2: Periodically inspects learning state while trading is active

Usage:
    .\demo_learning_monitoring.ps1

Output shows real-time adaptive decisions being made as market regime is detected.
#>

$ErrorActionPreference = "Stop"

$ProjectRoot = Get-Location
$VenvPath = "$ProjectRoot\.venv"

# Activate venv
& "$VenvPath\Scripts\Activate.ps1"

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Paper Trading + Learning CLI Monitoring Demo                 ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Clean slate
Remove-Item -Path "trades.sqlite" -Force -ErrorAction SilentlyContinue

Write-Host "📊 Starting paper trading with adaptive learning enabled..." -ForegroundColor Yellow
Write-Host "🔍 While that's running, you can monitor learning in another terminal:" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Terminal 2:" -ForegroundColor Green
Write-Host "   python -m trading_bot learn inspect" -ForegroundColor Green
Write-Host "   python -m trading_bot learn decisions" -ForegroundColor Green
Write-Host "   python -m trading_bot learn metrics" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop trading." -ForegroundColor Yellow
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# Run paper trading for 50 iterations
python -m trading_bot paper run `
    --iterations 50 `
    --no-ui `
    --period 180d `
    --interval 1d

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "✅ Paper trading completed!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Final learning state:" -ForegroundColor Cyan
python -m trading_bot learn inspect
Write-Host ""
Write-Host "📊 All adaptive decisions:" -ForegroundColor Cyan
python -m trading_bot learn decisions --limit 10
