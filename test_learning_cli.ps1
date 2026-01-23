#!/usr/bin/env powershell
<#
Quick test of learning CLI
#>

cd "c:\Users\Ronald mcdonald\projects\algo-trading-bot"

# Activate venv
& ".\.venv\Scripts\Activate.ps1" | Out-Null

Write-Host ""
Write-Host "===== LEARNING CLI TEST =====" -ForegroundColor Cyan
Write-Host ""

Write-Host "Command: python -m trading_bot learn decisions --limit 2" -ForegroundColor Yellow
Write-Host ""
python -m trading_bot learn decisions --limit 2

Write-Host ""
Write-Host "===== END TEST =====" -ForegroundColor Cyan
