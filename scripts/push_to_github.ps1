# GitHub Push Script for Algo Trading Bot (PowerShell)
# Run this to push your changes to GitHub

Write-Host "`n🚀 PREPARING FOR GITHUB PUSH`n" -ForegroundColor Green

# Check if git is initialized
if (-not (Test-Path .git)) {
    Write-Host "❌ Git not initialized. Run: git init" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Git repository found`n" -ForegroundColor Green

# Show what will be committed
Write-Host "📊 FILES READY FOR COMMIT:`n" -ForegroundColor Cyan
git status --short
Write-Host ""

# Commit changes
Write-Host "📝 Creating commit...`n" -ForegroundColor Yellow
git add -A
try {
    git commit -m "docs: migrate to GitHub Wiki, add MIT license, clean root folder"
    Write-Host "✅ Commit created`n" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Nothing new to commit`n" -ForegroundColor Yellow
}

# Show instructions
Write-Host "🔐 TO PUSH TO GITHUB:`n" -ForegroundColor Cyan

Write-Host "1️⃣ First time setup (one time only):" -ForegroundColor Yellow
Write-Host "   git remote add origin https://github.com/YOUR_USERNAME/algo-trading-bot.git" -ForegroundColor White
Write-Host "   git branch -M main`n" -ForegroundColor White

Write-Host "2️⃣ Push:" -ForegroundColor Yellow
Write-Host "   git push -u origin main`n" -ForegroundColor White

Write-Host "3️⃣ Verify on GitHub:" -ForegroundColor Yellow
Write-Host "   - Check Wiki tab shows all 7 pages" -ForegroundColor White
Write-Host "   - Verify README displays correctly" -ForegroundColor White
Write-Host "   - Check LICENSE file`n" -ForegroundColor White

Write-Host "✨ Ready to push! Follow the instructions above.`n" -ForegroundColor Green
