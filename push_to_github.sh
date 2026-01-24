#!/usr/bin/env bash
# GitHub Push Script for Algo Trading Bot
# Run this to push your changes to GitHub

set -e

echo "🚀 PREPARING FOR GITHUB PUSH"
echo ""

# Check if git is initialized
if [ ! -d .git ]; then
    echo "❌ Git not initialized. Run: git init"
    exit 1
fi

echo "✅ Git repository found"
echo ""

# Show what will be committed
echo "📊 FILES READY FOR COMMIT:"
git status --short
echo ""

# Commit changes
echo "📝 Creating commit..."
git add -A
git commit -m "docs: migrate to GitHub Wiki, add MIT license, clean root folder" || echo "⚠️ Nothing new to commit"

echo ""
echo "✅ Commit ready"
echo ""

# Instructions for push
echo "🔐 TO PUSH TO GITHUB:"
echo ""
echo "1. First time setup (one time only):"
echo "   git remote add origin https://github.com/YOUR_USERNAME/algo-trading-bot.git"
echo "   git branch -M main"
echo ""
echo "2. Push:"
echo "   git push -u origin main"
echo ""
echo "3. Verify on GitHub:"
echo "   - Check Wiki tab shows all 7 pages"
echo "   - Verify README displays correctly"
echo "   - Check LICENSE file"
echo ""

echo "✨ Ready to push! Follow the instructions above."
