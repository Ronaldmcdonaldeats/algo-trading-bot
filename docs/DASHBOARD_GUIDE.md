# 📊 Enhanced Real-Time Dashboard Guide

## What Changed

Your trading bot dashboard now shows **exactly what it's doing** in real-time:

### Before
```
"Stepping engine..."
[Generic status with no details]
```

### After
```
🟢 BUYING 3 position(s): AAPL, MSFT, NVDA
🔴 SELLING 2 position(s): TSLA, GOOGL  
🔄 REBALANCING | Bought 2, Sold 1
📊 ANALYZING 500 stocks | Found 15 buy signals
⚠️  3 order(s) rejected: Insufficient capital
```

---

## Dashboard Features

### 1. **Real-Time Activity Panel** (Cyan Border)
Shows current action at the top - immediately visible what the bot is doing

```
┌────────────────────────────────────────────┐
│ Current Activity                           │
│ 🟢 BUYING 3 position(s): AAPL, MSFT, NVDA │
└────────────────────────────────────────────┘
```

### 2. **Buy/Sell Indicators**
- 🟢 **BUYING** - Purchasing new positions
- 🔴 **SELLING** - Closing positions or taking profits
- 🔄 **REBALANCING** - Simultaneous buys and sells
- 📊 **ANALYZING** - Evaluating stocks for signals
- ⚠️ **REJECTED** - Orders that failed conditions

### 3. **Enhanced Fills Table**
Shows exactly what was executed with emoji indicators

```
Symbol | Side | Qty | Price    | Fee   | Action
-------|------|-----|----------|-------|---------------------------
AAPL   | BUY  | 15  | $150.25  | $2.25 | 🟢 BOUGHT - Momentum breakout
MSFT   | SELL | 8   | $385.25  | $3.08 | 🔴 SOLD - RSI overbought signal
NVDA   | BUY  | 5   | $875.00  | $4.38 | 🟢 BOUGHT - Volume surge
```

### 4. **Portfolio Summary**
Always shows:
- Cash balance
- Total equity
- Unrealized P&L
- Realized P&L
- Fees paid

### 5. **Open Positions**
All current positions with:
- Quantity held
- Average purchase price
- Current market price
- Unrealized profit/loss
- Stop loss and take profit levels

### 6. **Equity Curve**
Real-time sparkline showing portfolio growth or decline

### 7. **Recent Fills**
Last 10 trades executed with complete details

### 8. **Rejections**
Any orders that were rejected and why

---

## Status Messages Explained

### Buying Phase
```
🟢 BUYING 3 position(s): AAPL, MSFT, NVDA
```
- Bot found buy signals
- Executing purchase orders
- Shows first 3 symbols (more if additional)

### Selling Phase
```
🔴 SELLING 2 position(s): TSLA, GOOGL
```
- Stop losses triggered OR
- Take profits hit OR
- Exit signals generated
- Shows which positions being closed

### Rebalancing
```
🔄 REBALANCING | Bought 2, Sold 1
```
- Simultaneous buying and selling
- Portfolio being optimized
- Shows count of each action

### Analysis Phase
```
📊 ANALYZING 500 stocks | Found 15 buy signals
```
- Evaluating stock universe
- Checking technical indicators
- Generating trading signals

### Holding
```
📊 ANALYZING 500 stocks | Holding 5 positions
```
- No trades this iteration
- Existing positions held
- Waiting for next signal

### Rejection
```
⚠️ 3 order(s) rejected: Insufficient capital
```
- Orders didn't meet conditions
- Examples: Not enough cash, liquidity too low
- Shows first rejection reason

---

## How To Use

### Run Trading
```bash
python -m trading_bot auto
```
The dashboard will appear and update in real-time as:
1. Data downloads
2. Stocks are analyzed
3. Trades execute
4. Learning improves
5. Performance is tracked

### Run Quick Test (2 stocks)
```bash
python -m trading_bot paper --symbols AAPL,MSFT
```
Watch the dashboard show:
- Initial analysis
- Buy signals detected
- Trades executed
- Position management
- Profit/loss tracking

### Run Smart Selection (500 stocks)
```bash
python -m trading_bot auto
```
Dashboard shows:
- ✓ Downloading data
- ✓ Analyzing 500 stocks
- ✓ Buying top candidates
- ✓ Managing positions
- ✓ Tracking returns

---

## Dashboard Layout

```
╔═══════════════════════════════════════════════╗
║ Paper Trading | iter=10 | 2026-01-24T...     ║ ← Iteration number & timestamp
╠═══════════════════════════════════════════════╣
║ 🟢 BUYING 3 position(s): AAPL, MSFT, NVDA    ║ ← REAL-TIME ACTIVITY (NEW!)
╠════════════════════════════════════════════════╣
║ Portfolio        │                    ▄▆█▃█   ║
║ ─────────────    │ Equity: $105,250   ▂▄▆█▇  ║
║ Cash: $45,250    │                    ▁▂▃▄▅  ║
║ Equity: $105,250 │                           ║
║ Unrealized: $850 │                    Equity  ║
║ Realized: $5,000 │                    curve   ║
║                  │                           ║
║ Positions        │                           ║
║ ─────────────    │                           ║
║ AAPL: 15 @ 150.25│                           ║
║ MSFT: 8 @ 380.50 │                           ║
║ NVDA: 5 @ 875.00 │                           ║
║                  │                           ║
║ Recent Fills     │                           ║
║ ─────────────    │                           ║
║ 🟢 BOUGHT AAPL   │                           ║
║ 🟢 BOUGHT MSFT   │                           ║
║ 🟢 BOUGHT NVDA   │                           ║
╚════════════════════════════════════════════════╝
```

---

## Examples in Action

### Example 1: Morning Analysis
```
📊 ANALYZING 500 stocks | Found 12 buy signals
```
Bot is:
- Scoring all 500 stocks
- Found 12 meeting criteria
- Waiting for confirmation or capital

### Example 2: Execution
```
🟢 BUYING 3 position(s): AAPL, MSFT, NVDA
```
Dashboard shows:
- Actual transaction prices
- Fees charged
- Shares acquired
- Positions table updates in real-time

### Example 3: Profit Taking
```
🔴 SELLING 2 position(s): TSLA, GOOGL
```
Shows:
- Exit price achieved
- Profit/loss realized
- Fees on exit
- New cash available

### Example 4: Rebalancing
```
🔄 REBALANCING | Bought 2, Sold 1
```
- Trimming winners (AAPL)
- Adding emerging momentum (TSLA, NVDA)
- Optimizing portfolio

---

## What Each Column Means

### Fills Table
- **Symbol**: Ticker being traded
- **Side**: BUY or SELL action
- **Qty**: Shares traded
- **Price**: Execution price
- **Fee**: Commission paid
- **Action**: 🟢/🔴 indicator + reason
  - "Momentum breakout"
  - "RSI overbought"
  - "Take profit triggered"
  - "Stop loss hit"

### Positions Table
- **Symbol**: Stock ticker
- **Qty**: Current shares held
- **Avg**: Average purchase price
- **Last**: Current market price
- **Unrl PnL**: Unrealized profit/loss
- **SL**: Stop loss price (if set)
- **TP**: Take profit price (if set)

---

## Performance Metrics

Dashboard tracks:
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Worst peak-to-trough decline
- **Win Rate**: % of winning trades
- **Num Trades**: Total executed
- **Current P&L**: Total profit/loss

---

## Tips

1. **Watch the Activity Panel** - Top shows exactly what's happening
2. **Check Equity Curve** - Right side shows portfolio performance
3. **Monitor Fills** - Latest executions with reasoning
4. **Review Positions** - Current holdings and levels
5. **Track Metrics** - Performance indicators update each iteration

---

## Now Your Bot Shows

✅ What it's downloading
✅ What it's analyzing  
✅ What it's buying
✅ What it's selling
✅ How much it's making
✅ Why it's making trades

**No more "stepping engine" - real visibility into trading!** 🚀
