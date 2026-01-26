# HOW TO DEPLOY BOT TO ORACLE CLOUD - STEP BY STEP

## Prerequisites
- Oracle Cloud account with free instance running (Ubuntu 22.04)
- SSH key downloaded to your computer
- Alpaca API key and secret (from your trading account)

---

## SIMPLE 5-MINUTE SETUP

### Step 1: Find Your Instance Details

Go to Oracle Cloud Console:
1. Click "Compute" → "Instances"
2. Find your instance, note:
   - **Public IP Address** (e.g., 129.213.45.123)
   - **Username** (usually "ubuntu")

### Step 2: SSH Into Your Instance

Open Terminal/PowerShell on your computer:

```bash
ssh -i C:\path\to\your\ssh\key.key ubuntu@YOUR_INSTANCE_IP
```

**Example:**
```bash
ssh -i C:\Users\Ronald\Downloads\oracle_key.key ubuntu@129.213.45.123
```

**Windows users:** Use PowerShell or Git Bash
**Mac/Linux users:** Use Terminal

### Step 3: Download & Run Setup Script

Once you're logged in (you'll see `ubuntu@instance-name:~$`):

```bash
cd /home/ubuntu
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/algo-trading-bot/main/deploy_oracle.sh
bash deploy_oracle.sh
```

Or if you can't access GitHub, I'll provide the script inline below.

### Step 4: Add Your Alpaca Credentials

The script will create a `.env` file. Edit it:

```bash
nano /home/ubuntu/trading-bot-cloud/.env
```

**Replace these lines with YOUR credentials:**
```
APCA_API_KEY_ID=PK1234567890ABCDEF
APCA_API_SECRET_KEY=your_secret_key_here
```

**How to get your Alpaca keys:**
1. Go to https://app.alpaca.markets
2. Click "Account" → "Settings"
3. Click "API Keys"
4. Copy your **Key ID** and **Secret Key**
5. Paste them into the .env file

Save file: Press `Ctrl+X`, then `Y`, then `Enter`

### Step 5: Copy Your Bot Code

**Option A: Clone from GitHub**
```bash
cd /home/ubuntu/trading-bot-cloud
git clone https://github.com/YOUR_USERNAME/algo-trading-bot.git .
```

**Option B: Upload from your computer**
```bash
# From your local computer (new terminal):
scp -i C:\path\to\key.key -r C:\Users\Ronald\projects\algo-trading-bot/* ubuntu@YOUR_IP:/home/ubuntu/trading-bot-cloud/
```

### Step 6: Build Docker Image

```bash
cd /home/ubuntu/trading-bot-cloud
docker build -t trading-bot-cloud:latest .
```

This takes 2-3 minutes. You'll see lots of output. It's normal!

### Step 7: Start the Bot (Runs Forever!)

```bash
docker-compose up -d
```

✅ **Bot is now running 24/7 on Oracle Cloud!**

### Step 8: Verify It's Running

```bash
docker logs -f trading-bot-cloud
```

You should see:
```
[ITERATION 1] Analyzing 50 symbols...
[SIGNAL] PSTG: consensus=+1 @ $71.00
...
```

Press `Ctrl+C` to exit logs (bot keeps running!)

---

## Common Commands

### View logs (see what bot is doing):
```bash
docker logs -f trading-bot-cloud
```

### Stop the bot:
```bash
docker-compose down
```

### Start bot again:
```bash
docker-compose up -d
```

### Check if running:
```bash
docker ps
```

### Restart bot:
```bash
docker-compose restart
```

### Download results to your computer:
```bash
# From your local computer:
scp -i C:\path\to\key.key ubuntu@YOUR_IP:/home/ubuntu/trading-bot-cloud/data/* ./backup/
```

---

## Troubleshooting

### Error: "Permission denied (publickey)"
- Make sure SSH key has correct permissions: `chmod 600 your_key.key`
- Check you're using the right instance IP

### Error: "docker: not found"
- Run setup script again: `bash deploy_oracle.sh`
- Logout and login again: `exit` then reconnect

### Error: "Failed to build image"
- Check Dockerfile is in the directory
- Ensure all bot code files are copied

### Bot not trading
- Check logs: `docker logs trading-bot-cloud`
- Verify .env file has correct API keys
- Make sure Alpaca account is funded (even $0 works for paper trading)

### Want to see your 19 existing positions?
- They'll transfer to the cloud bot automatically if you copy the entire project

---

## Security Tips for Cloud Bot

1. **Firewall**: Restrict SSH access to your IP only
   ```bash
   # In Oracle Cloud Console:
   # Compute → Instances → Click instance
   # Scroll to "Attached VNICs"
   # Edit security list
   # Add rule: Protocol TCP, Source YOUR_IP, Port 22
   ```

2. **Backup your .env file locally**:
   ```bash
   # From your computer:
   scp -i key.key ubuntu@IP:/home/ubuntu/trading-bot-cloud/.env ./env_backup
   ```

3. **Monitor regularly**:
   ```bash
   ssh -i key.key ubuntu@IP "docker logs trading-bot-cloud | tail -20"
   ```

---

## You're Done!

Your bot is now:
✅ Running 24/7 on Oracle Cloud (FREE!)
✅ Automatically restarts if it crashes
✅ Accessible from anywhere via SSH
✅ Logging all trades and signals
✅ Trading with your 19 existing positions

---

## Questions?

If something doesn't work, tell me:
1. What's the error message?
2. What step did you get stuck on?
3. Include any error logs

I can help you fix it!
