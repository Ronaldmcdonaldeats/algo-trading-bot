# Web Dashboard

The web dashboard provides real-time visualization of your trading activity with a modern, responsive interface.

## 🎯 Features

### Live Metrics Display
- **Current Equity** - Total account value (starting balance + P&L)
- **Current P&L** - Profit/loss from initial capital
- **Sharpe Ratio** - Risk-adjusted return metric
- **Max Drawdown %** - Largest peak-to-trough decline
- **Win Rate %** - Percentage of profitable trades
- **Total Trades** - Number of completed trades

### Charts & Visualizations
- **Equity Curve** - Real-time line chart of account value
- **Holdings Breakdown** - Pie chart showing position allocation

### Positions Table
Live table showing all open positions:
- Symbol and quantity
- Entry and current price
- Unrealized P&L
- Return percentage (color-coded: green=profit, red=loss)

### Auto-Refresh
Dashboard updates every 2 seconds with latest data.

---

## 🚀 Accessing the Dashboard

### With Docker
```bash
docker-compose up --build
# Visit: http://localhost:5000
```

### Local Python
```bash
pip install flask flask-cors
python -m trading_bot.ui.web
# Visit: http://localhost:5000
```

---

## 📊 Data Flow

```
Trading Bot Engine
        ↓
  PaperEngineUpdate
        ↓
  Shared Data Store
        ↓
  Flask API (/api/data)
        ↓
  Web Browser (JavaScript)
        ↓
  Dashboard UI
```

---

## 🔧 Configuration

The dashboard reads data from:
- `src/trading_bot/engine/paper.py` - Live trading metrics
- `src/trading_bot/ui/web.py` - Flask web server
- `data/trades.sqlite` - Trade history database

---

## 🎨 Customization

To modify the dashboard appearance, edit `src/trading_bot/ui/web.py`:

```python
# Customize colors in the HTML template
background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);  # Change these
color: #e0e0e0;  # Text color
```

---

## 📱 Browser Support

- Chrome/Edge (recommended)
- Firefox
- Safari
- Mobile browsers (responsive design)

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| Dashboard shows "Loading data..." | Wait 10-15 seconds for server startup |
| Port 5000 already in use | Change port in `docker-compose.yml` |
| Data not updating | Ensure trading bot (app service) is running |
| Blank page on refresh | Clear browser cache (Ctrl+Shift+Delete) |

---

## 💡 Tips

- **Wider Screen**: Dashboard works best on desktop (1200px+)
- **Fullscreen**: Press F11 for fullscreen mode
- **Performance**: For 100+ trades, consider using backtest mode instead
- **Data Persistence**: Trade history saved in `data/trades.sqlite`
