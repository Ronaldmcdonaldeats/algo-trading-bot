# Discord Webhook Integration - Trading Bot

## ✅ Status: WORKING

Your Discord webhook is **configured and tested**. The trading bot will send real-time notifications to Discord.

---

## 📤 What Gets Sent to Discord

The bot automatically sends these notifications:

### 🟢 Trade Notifications
- **Trade Executed** - When a trade is placed
  - Symbol, Side (BUY/SELL), Quantity, Price, Order ID
- **Position Closed** - When a trade exits with profit/loss
  - Entry/Exit prices, P/L amount, P/L percentage

### 🔔 Market Notifications
- **Market Opened** - When market opens at 9:30 AM EST
- **Market Closed** - When market closes at 4:00 PM EST

### ⚠️ Alert Notifications
- **Low Balance** - Account balance warning
- **High Loss** - Position hit stop loss
- **Strategy Error** - Bot encountered an error

### 🤖 Status Notifications
- **Strategy Started** - Bot began trading
- **Strategy Stopped** - Bot halted
- **Service Health** - Periodic status checks

---

## 🧪 Test Results

**All 3 test messages were sent successfully:**

```
✅ Test 1: Simple Notification (Blue)
   Status: PASSED - Message delivered to Discord

✅ Test 2: Trade Example (Green)
   Status: PASSED - Message with trade details delivered

✅ Test 3: Error Alert Example (Red)
   Status: PASSED - Message with error details delivered
```

---

## 🔧 Configuration

Your Discord webhook is stored in `.env`:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1465174784064225355/lpmhqgLdeDgeOkF5l7BrXL5g3FqVkHMYbqQALvDZN-G49sAL0uNzZc-dpPVWWbxd0OII
```

### How It Works

1. **Webhook Creation** (already done)
   - Your Discord server has a webhook channel configured
   - URL stored securely in `.env`

2. **Message Format**
   - Rich Discord embeds with colors, timestamps, and structured data
   - Color coding: Green=Success, Yellow=Warning, Red=Error

3. **Delivery**
   - Messages sent via HTTPS (encrypted)
   - Asynchronous - doesn't block trading
   - Fallback if Discord is down - continues trading anyway

---

## 📝 Example Messages

### Trade Execution
```
📈 TRADE EXECUTED - AAPL

Gen 364 Strategy executed BUY order

Symbol: AAPL
Side: BUY
Quantity: 10
Price: $150.25
Order ID: 12345
```

### Position Closed (Profit)
```
📊 POSITION CLOSED - AAPL

Trade closed with +$25.00 P/L

Symbol: AAPL
Quantity: 10
Entry Price: $150.00
Exit Price: $152.50
P/L Amount: $25.00
P/L %: 1.67%
```

### Market Events
```
🔔 MARKET OPENED

Stock market opened - trading bot is now active
```

### Alerts
```
⚠️ ERROR: Low Balance

Account balance is below minimum threshold

Current Balance: $500
Minimum Required: $1000
```

---

## 🚀 How to Use

### Monitoring Your Bot

1. **Open your Discord server**
   - Look for the channel receiving webhook messages
   - You'll see all trading bot notifications in real-time

2. **Check notifications**
   - Each trade shows detailed execution info
   - Market opens/closes show clearly
   - Errors are flagged in red

3. **Set Discord alerts** (optional)
   - @mention yourself for important trades
   - Set up custom Discord roles
   - Configure sound/desktop alerts

### Example Discord Workflow

```
1. Market opens (9:30 AM EST)
   → Discord: "🔔 MARKET OPENED"
   
2. Strategy analyzes first stock
   → Discord: "📈 TRADE EXECUTED - SPY (BUY 10 shares @ $450)"
   
3. Trade profits after 30 minutes
   → Discord: "📊 POSITION CLOSED - SPY (+$125.50, +2.79%)"
   
4. Market closes (4:00 PM EST)
   → Discord: "🔔 MARKET CLOSED"
   
5. Daily summary
   → Discord: "📊 Daily P/L: +$487.25 (7 trades)"
```

---

## 🔐 Security

- **Webhook URL is private** - Only your Discord server receives messages
- **No sensitive data** - API keys/passwords never sent to Discord
- **HTTPS encrypted** - All communication encrypted in transit
- **Isolated channel** - Consider creating a private Discord channel
- **Rate limited** - Discord prevents spam/DDoS

---

## 📱 Mobile Notifications

You can get mobile alerts by:

1. **Enable Discord mobile app notifications**
   - Download Discord mobile app
   - Set channel to "All Messages"
   - Enable notifications on your phone

2. **Discord mobile widget** (if you have Nitro)
   - Desktop alerts when bot sends messages

3. **Browser notifications**
   - Keep Discord web open in background
   - Browser sends notifications when messages arrive

---

## 🧪 Testing & Troubleshooting

### Verify Webhook Works
```bash
# From your local machine
python test_discord_webhook.py

# From Oracle instance
ssh ubuntu@129.213.99.89
cd ~/bot
sudo docker-compose run --rm strategy python3 test_discord_webhook.py
```

### If Messages Don't Appear

1. **Check Discord channel exists**
   - Verify webhook is connected to the right channel
   - Check channel permissions

2. **Verify webhook URL in .env**
   ```bash
   ssh ubuntu@129.213.99.89
   grep DISCORD_WEBHOOK ~/.env
   ```

3. **Check bot permissions**
   - Ensure bot has "Send Messages" permission in channel
   - Check Discord server settings

4. **View bot logs**
   ```bash
   ssh ubuntu@129.213.99.89
   tail -f ~/bot/logs/live_trading/live_trading_24_7.log | grep -i discord
   ```

---

## 💡 Customization Ideas

You can customize Discord messages by editing `discord_notifier.py`:

### Add Custom Messages
```python
def custom_alert(self, title, message):
    """Send custom alert to Discord"""
    embed = self._create_embed(title, message, color=3447003)
    return self._send_embed(embed)
```

### Add Emoji Indicators
```python
emoji_map = {
    'buy': '📈',
    'sell': '📉',
    'hold': '⏸️',
    'error': '⚠️'
}
```

### Schedule Daily Reports
```python
def daily_summary(self, total_trades, total_pl, win_rate):
    """Send daily P/L summary"""
    # Automatically sent each day at 4:01 PM EST
```

---

## ✅ Next Steps

1. **Keep an eye on Discord** during market hours
2. **Monitor first trades Thursday morning** to see notifications in action
3. **Adjust notification preferences** in Discord server settings
4. **Set up mobile alerts** if you want phone notifications

---

## Summary

✅ **Discord webhook is working**
✅ **Test messages delivered successfully**
✅ **Ready for live trading notifications**
✅ **All trade events will be sent to Discord**

Your bot will keep you informed of every trade, every market event, and every alert — directly in Discord!

---

**Updated**: January 29, 2026  
**Status**: ✅ ACTIVE & TESTED  
**Webhook**: Configured and working
