#!/bin/bash

# ============================================================================
# AUTOMATED BOT SETUP FOR ORACLE CLOUD FREE TIER
# ============================================================================
# This script will:
# 1. Install Docker
# 2. Clone the bot repository
# 3. Configure environment variables
# 4. Build and run the bot 24/7
# ============================================================================

set -e

echo "=========================================="
echo "TRADING BOT - ORACLE CLOUD SETUP"
echo "=========================================="
echo ""

# Step 1: Update system
echo "[1/6] Updating system packages..."
sudo apt update > /dev/null 2>&1
sudo apt upgrade -y > /dev/null 2>&1

# Step 2: Install Docker and Git
echo "[2/6] Installing Docker and Git..."
sudo apt install -y docker.io git > /dev/null 2>&1

# Step 3: Add ubuntu user to docker group
echo "[3/6] Configuring Docker permissions..."
sudo usermod -aG docker ubuntu > /dev/null 2>&1

# Step 4: Clone repository
echo "[4/6] Cloning bot repository..."
cd /home/ubuntu
if [ ! -d "algo-trading-bot" ]; then
  git clone https://github.com/YOUR_USERNAME/algo-trading-bot.git > /dev/null 2>&1
else
  echo "   Repository already exists, skipping clone"
fi

cd algo-trading-bot

# Step 5: Create environment file
echo "[5/6] Setting up environment variables..."
cat > .env << 'EOF'
export APCA_API_KEY_ID=YOUR_ALPACA_API_KEY
export APCA_API_SECRET_KEY=YOUR_ALPACA_SECRET_KEY
export APCA_API_BASE_URL=https://paper-api.alpaca.markets
EOF

echo "   Created .env file"
echo "   ⚠️  IMPORTANT: Edit .env with your Alpaca API keys:"
echo "      nano /home/ubuntu/algo-trading-bot/.env"
echo ""

# Step 6: Build and run bot
echo "[6/6] Building Docker image..."
source .env
docker build -t trading-bot . > /dev/null 2>&1

echo "[6/6] Starting bot container..."
docker run -d \
  --restart unless-stopped \
  --name trading-bot-cloud \
  -e APCA_API_KEY_ID=$APCA_API_KEY_ID \
  -e APCA_API_SECRET_KEY=$APCA_API_SECRET_KEY \
  -e APCA_API_BASE_URL=$APCA_API_BASE_URL \
  trading-bot > /dev/null 2>&1

echo ""
echo "=========================================="
echo "✅ SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "📋 NEXT STEPS:"
echo ""
echo "1. EDIT ENVIRONMENT VARIABLES:"
echo "   nano /home/ubuntu/algo-trading-bot/.env"
echo "   Replace YOUR_ALPACA_API_KEY and YOUR_ALPACA_SECRET_KEY"
echo ""
echo "2. RESTART BOT WITH YOUR KEYS:"
echo "   docker stop trading-bot-cloud"
echo "   docker rm trading-bot-cloud"
echo "   cd /home/ubuntu/algo-trading-bot"
echo "   source .env"
echo "   docker run -d --restart unless-stopped --name trading-bot-cloud ..."
echo ""
echo "3. VIEW LIVE LOGS:"
echo "   docker logs -f trading-bot-cloud"
echo ""
echo "4. CHECK STATUS:"
echo "   docker ps"
echo ""
echo "✨ Bot is now running 24/7 on Oracle Cloud!"
echo "=========================================="
