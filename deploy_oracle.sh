#!/bin/bash

# ============================================================================
# AUTOMATED BOT DEPLOYMENT SCRIPT FOR ORACLE CLOUD
# ============================================================================
# Usage: bash deploy_oracle.sh
# This script will:
# 1. Install Docker
# 2. Download the bot code
# 3. Set up environment variables
# 4. Build and run the bot 24/7
# ============================================================================

set -e  # Exit on error

echo ""
echo "================================================================================"
echo "TRADING BOT - ORACLE CLOUD AUTO-DEPLOYMENT"
echo "================================================================================"
echo ""

# ============================================================================
# STEP 1: UPDATE SYSTEM
# ============================================================================
echo "[STEP 1/6] Updating system packages..."
sudo apt-get update > /dev/null 2>&1
sudo apt-get upgrade -y > /dev/null 2>&1
echo "✓ System updated"

# ============================================================================
# STEP 2: INSTALL DOCKER
# ============================================================================
echo "[STEP 2/6] Installing Docker..."
sudo apt-get install -y docker.io git curl > /dev/null 2>&1
sudo usermod -aG docker ubuntu > /dev/null 2>&1
echo "✓ Docker installed"

# ============================================================================
# STEP 3: VERIFY DOCKER
# ============================================================================
echo "[STEP 3/6] Verifying Docker installation..."
docker --version
echo "✓ Docker verified"

# ============================================================================
# STEP 4: CREATE PROJECT DIRECTORY
# ============================================================================
echo "[STEP 4/6] Setting up bot directory..."
mkdir -p /home/ubuntu/trading-bot-cloud
cd /home/ubuntu/trading-bot-cloud
echo "✓ Directory created: /home/ubuntu/trading-bot-cloud"

# ============================================================================
# STEP 5: CREATE .env FILE (USER NEEDS TO FILL THIS)
# ============================================================================
echo "[STEP 5/6] Creating environment file..."

if [ ! -f /home/ubuntu/trading-bot-cloud/.env ]; then
    cat > /home/ubuntu/trading-bot-cloud/.env << 'EOF'
# Alpaca API Credentials (REQUIRED - Fill these in!)
APCA_API_KEY_ID=YOUR_ALPACA_API_KEY_HERE
APCA_API_SECRET_KEY=YOUR_ALPACA_SECRET_KEY_HERE
APCA_API_BASE_URL=https://paper-api.alpaca.markets

# Bot Configuration
BOT_NAME=trading-bot-cloud
BOT_SYMBOLS=50
BOT_INTERVAL=30
EOF
    
    echo "⚠ .env file created at: /home/ubuntu/trading-bot-cloud/.env"
    echo ""
    echo "YOU MUST EDIT THIS FILE AND ADD YOUR ALPACA CREDENTIALS:"
    echo "  nano /home/ubuntu/trading-bot-cloud/.env"
    echo ""
    echo "Then run this script again!"
    echo ""
    exit 1
else
    echo "✓ Environment file exists: /home/ubuntu/trading-bot-cloud/.env"
fi

# ============================================================================
# STEP 6: PREPARE DOCKER SETUP
# ============================================================================
echo "[STEP 6/6] Preparing Docker deployment..."

# Load environment variables
export $(cat /home/ubuntu/trading-bot-cloud/.env | xargs)

# Create docker-compose file
cat > /home/ubuntu/trading-bot-cloud/docker-compose.yml << 'EOF'
version: '3.8'

services:
  trading-bot:
    image: trading-bot-cloud:latest
    container_name: trading-bot-cloud
    restart: unless-stopped
    environment:
      - APCA_API_KEY_ID=${APCA_API_KEY_ID}
      - APCA_API_SECRET_KEY=${APCA_API_SECRET_KEY}
      - APCA_API_BASE_URL=${APCA_API_BASE_URL}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    networks:
      - trading-network

networks:
  trading-network:
    driver: bridge
EOF

echo "✓ Docker compose configured"

# ============================================================================
# PROMPT USER FOR NEXT STEPS
# ============================================================================
echo ""
echo "================================================================================"
echo "✓ ORACLE CLOUD SETUP COMPLETE!"
echo "================================================================================"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Download your bot code to this instance:"
echo "   git clone https://github.com/YOUR_USERNAME/algo-trading-bot.git ."
echo "   (Or upload your existing code)"
echo ""
echo "2. Build the Docker image:"
echo "   cd /home/ubuntu/trading-bot-cloud"
echo "   docker build -t trading-bot-cloud:latest ."
echo ""
echo "3. Start the bot (runs 24/7 automatically):"
echo "   docker-compose up -d"
echo ""
echo "4. View logs anytime:"
echo "   docker logs -f trading-bot-cloud"
echo ""
echo "5. Stop the bot (if needed):"
echo "   docker-compose down"
echo ""
echo "================================================================================"
echo ""
