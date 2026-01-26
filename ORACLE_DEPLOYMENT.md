# Oracle Cloud Deployment Guide

**Instance IP:** 150.136.13.134

## STEP 1: SSH Into Your Instance

```powershell
# Using your SSH key (ssh-key-2025-03-28(1).key)
ssh -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2025-03-28(1).key" ubuntu@150.136.13.134
```

**Note:** If you get permission errors, you may need to use the minecraft.ppk key or convert the key format.

---

## STEP 2: Upload Setup Script

**On your local machine (PowerShell):**

```powershell
# Copy the setup script to your instance
scp -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2025-03-28(1).key" `
  "C:\Users\Ronald mcdonald\projects\algo-trading-bot\setup-oracle-cloud.sh" `
  ubuntu@150.136.13.134:/tmp/setup-oracle-cloud.sh
```

---

## STEP 3: Run Setup Script

**After SSHing into the instance:**

```bash
# Run the automated setup
bash /tmp/setup-oracle-cloud.sh
```

This will:
- ✅ Update system packages
- ✅ Install Docker
- ✅ Clone your bot repository
- ✅ Build the Docker image
- ✅ Create .env file placeholder

---

## STEP 4: Configure Alpaca API Keys

**On the Oracle instance, edit the .env file:**

```bash
nano /home/ubuntu/algo-trading-bot/.env
```

**Add these lines (replace with your REAL Alpaca keys):**

```bash
export APCA_API_KEY_ID=YOUR_ALPACA_KEY_ID_HERE
export APCA_API_SECRET_KEY=YOUR_ALPACA_SECRET_KEY_HERE
export APCA_API_BASE_URL=https://paper-api.alpaca.markets
```

**To save:** Press `Ctrl+X`, then `Y`, then `Enter`

---

## STEP 5: Start The Bot

**On the Oracle instance:**

```bash
cd /home/ubuntu/algo-trading-bot

# Load environment variables
source .env

# Start bot in background (runs 24/7)
docker run -d \
  --restart unless-stopped \
  --name trading-bot-cloud \
  -e APCA_API_KEY_ID=$APCA_API_KEY_ID \
  -e APCA_API_SECRET_KEY=$APCA_API_SECRET_KEY \
  -e APCA_API_BASE_URL=$APCA_API_BASE_URL \
  trading-bot
```

---

## STEP 6: Monitor Bot Live

**Check status:**

```bash
# Is it running?
docker ps

# View live logs
docker logs -f trading-bot-cloud
```

**From your local machine (to pull logs):**

```powershell
# Copy logs from instance to your local machine
scp -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2025-03-28(1).key" `
  ubuntu@150.136.13.134:/tmp/trading-bot.log `
  C:\Users\Ronald mcdonald\projects\algo-trading-bot\oracle-logs.txt
```

---

## TROUBLESHOOTING

**If bot doesn't start:**

```bash
# Check Docker logs for errors
docker logs trading-bot-cloud

# Stop and remove container
docker stop trading-bot-cloud
docker rm trading-bot-cloud

# Try running again
docker run -d \
  --restart unless-stopped \
  --name trading-bot-cloud \
  -e APCA_API_KEY_ID=$APCA_API_KEY_ID \
  -e APCA_API_SECRET_KEY=$APCA_API_SECRET_KEY \
  -e APCA_API_BASE_URL=$APCA_API_BASE_URL \
  trading-bot
```

**If API keys are wrong:**

```bash
# Stop bot
docker stop trading-bot-cloud

# Edit .env again
nano /home/ubuntu/algo-trading-bot/.env

# Reload and restart
source .env
docker start trading-bot-cloud
```

---

## QUICK REFERENCE - SSH Commands

```powershell
# SSH in
ssh -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2025-03-28(1).key" ubuntu@150.136.13.134

# Upload file
scp -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2025-03-28(1).key" LOCAL_FILE ubuntu@150.136.13.134:/remote/path

# Download file
scp -i "C:\Users\Ronald mcdonald\Downloads\ssh-key-2025-03-28(1).key" ubuntu@150.136.13.134:/remote/file LOCAL_PATH
```

---

## BENEFITS - Your Bot Now Runs 24/7 ✅

- ✅ Trades while your PC is off
- ✅ Free for 12 months (Oracle Free Tier)
- ✅ 4 CPU cores + 24GB RAM included
- ✅ 99.9% uptime SLA
- ✅ Monitor from anywhere via SSH
- ✅ 19 existing positions preserved
- ✅ New 3% take-profit active on new trades

---

## NEXT STEPS

1. SSH into 150.136.13.134
2. Run setup script
3. Configure Alpaca keys in .env
4. Start bot
5. Monitor logs
6. Report back when you see "ITERATION" logs! 🚀
