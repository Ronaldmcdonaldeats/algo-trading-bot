"""Web dashboard for trading bot - Flask application."""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS

from trading_bot.engine.paper import PaperEngineUpdate


class DashboardLogHandler(logging.Handler):
    """Custom logging handler to capture logs for dashboard display."""
    
    def __init__(self, max_logs=500):
        super().__init__()
        self.logs = deque(maxlen=max_logs)
        self.formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                          datefmt='%Y-%m-%d %H:%M:%S')
    
    def emit(self, record):
        try:
            log_entry = self.format(record)
            self.logs.append({
                'message': log_entry,
                'level': record.levelname.lower(),
                'timestamp': datetime.fromtimestamp(record.created).isoformat()
            })
        except Exception:
            self.handleError(record)


def create_web_app():
    """Create and configure Flask application."""
    app = Flask(__name__, template_folder=str(Path(__file__).parent))
    CORS(app)

    # Shared state for updates
    app.state = {"current_update": None, "equity_history": []}
    
    # Setup logging
    logger = logging.getLogger()
    log_handler = DashboardLogHandler(max_logs=500)
    logger.addHandler(log_handler)
    app.state['log_handler'] = log_handler

    @app.route("/")
    def index():
        """Serve main dashboard HTML."""
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Trading Bot Dashboard</title>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
                    color: #e0e0e0;
                    min-height: 100vh;
                    padding: 20px;
                }
                .container {
                    max-width: 1400px;
                    margin: 0 auto;
                }
                h1 {
                    text-align: center;
                    margin-bottom: 30px;
                    font-size: 2.5em;
                    background: linear-gradient(135deg, #00d4ff, #0099ff);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                .status-section {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .metric-card {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    border-radius: 12px;
                    padding: 20px;
                    backdrop-filter: blur(10px);
                    transition: all 0.3s ease;
                }
                .metric-card:hover {
                    background: rgba(255, 255, 255, 0.1);
                    border-color: rgba(0, 212, 255, 0.8);
                    transform: translateY(-2px);
                }
                .metric-label {
                    font-size: 0.9em;
                    color: #9090b0;
                    margin-bottom: 8px;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }
                .metric-value {
                    font-size: 1.8em;
                    font-weight: bold;
                    color: #00d4ff;
                }
                .metric-value.positive {
                    color: #00ff88;
                }
                .metric-value.negative {
                    color: #ff3366;
                }
                .charts-section {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .chart-card {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    border-radius: 12px;
                    padding: 20px;
                    backdrop-filter: blur(10px);
                }
                .chart-title {
                    margin-bottom: 15px;
                    color: #00d4ff;
                    font-weight: bold;
                }
                canvas {
                    width: 100% !important;
                    height: 300px !important;
                }
                .positions-table {
                    width: 100%;
                    border-collapse: collapse;
                    background: rgba(255, 255, 255, 0.02);
                    border-radius: 12px;
                    overflow: hidden;
                }
                .positions-table th {
                    background: rgba(0, 212, 255, 0.1);
                    padding: 12px;
                    text-align: left;
                    color: #00d4ff;
                    font-weight: bold;
                    border-bottom: 1px solid rgba(0, 212, 255, 0.3);
                }
                .positions-table td {
                    padding: 12px;
                    border-bottom: 1px solid rgba(0, 212, 255, 0.1);
                }
                .positions-table tr:hover {
                    background: rgba(0, 212, 255, 0.05);
                }
                .status-loading {
                    text-align: center;
                    padding: 40px;
                    color: #9090b0;
                }
                .spinner {
                    display: inline-block;
                    width: 40px;
                    height: 40px;
                    border: 4px solid rgba(0, 212, 255, 0.3);
                    border-radius: 50%;
                    border-top-color: #00d4ff;
                    animation: spin 1s linear infinite;
                }
                @keyframes spin {
                    to { transform: rotate(360deg); }
                }
                .status-badge {
                    display: inline-block;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 0.85em;
                    font-weight: bold;
                    margin-left: 10px;
                }
                .status-active {
                    background: rgba(0, 255, 136, 0.2);
                    color: #00ff88;
                }
                .status-inactive {
                    background: rgba(255, 51, 102, 0.2);
                    color: #ff3366;
                }
                .tabs {
                    display: flex;
                    gap: 10px;
                    margin-bottom: 30px;
                    border-bottom: 2px solid rgba(0, 212, 255, 0.2);
                    padding-bottom: 0;
                }
                .tab-button {
                    padding: 12px 24px;
                    background: transparent;
                    border: none;
                    color: #9090b0;
                    font-size: 1em;
                    cursor: pointer;
                    border-bottom: 3px solid transparent;
                    transition: all 0.3s ease;
                    font-weight: 500;
                }
                .tab-button:hover {
                    color: #00d4ff;
                }
                .tab-button.active {
                    color: #00d4ff;
                    border-bottom-color: #00d4ff;
                }
                .page {
                    display: none;
                }
                .page.active {
                    display: block;
                }
                .logs-container {
                    background: rgba(255, 255, 255, 0.02);
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    border-radius: 12px;
                    padding: 20px;
                    height: 500px;
                    overflow-y: auto;
                    font-family: 'Courier New', monospace;
                    font-size: 0.9em;
                    line-height: 1.6;
                }
                .log-entry {
                    padding: 8px;
                    margin: 4px 0;
                    border-radius: 4px;
                    border-left: 4px solid;
                }
                .log-entry.error {
                    background: rgba(255, 51, 102, 0.1);
                    border-left-color: #ff3366;
                    color: #ff3366;
                }
                .log-entry.warning {
                    background: rgba(255, 165, 0, 0.1);
                    border-left-color: #ffa500;
                    color: #ffa500;
                }
                .log-entry.info {
                    background: rgba(0, 212, 255, 0.1);
                    border-left-color: #00d4ff;
                    color: #00d4ff;
                }
                .log-entry.debug {
                    background: rgba(144, 144, 176, 0.1);
                    border-left-color: #9090b0;
                    color: #9090b0;
                }
                .logs-toolbar {
                    display: flex;
                    gap: 10px;
                    margin-bottom: 15px;
                }
                .logs-toolbar button {
                    padding: 8px 16px;
                    background: rgba(0, 212, 255, 0.2);
                    border: 1px solid rgba(0, 212, 255, 0.5);
                    color: #00d4ff;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 500;
                    transition: all 0.3s ease;
                }
                .logs-toolbar button:hover {
                    background: rgba(0, 212, 255, 0.4);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📈 Trading Bot Dashboard</h1>
                
                <div class="tabs">
                    <button class="tab-button active" onclick="switchPage('overview')">Overview</button>
                    <button class="tab-button" onclick="switchPage('logs')">Logs</button>
                    <button class="tab-button" onclick="switchPage('trades')">Trades</button>
                </div>
                
                <div id="overview" class="page active">
                    <div id="status" class="status-loading">
                    <div class="spinner"></div>
                    <p>Loading data...</p>
                </div>

                <div id="content" style="display: none;">
                    <div class="status-section">
                        <div class="metric-card">
                            <div class="metric-label">Current Equity</div>
                            <div class="metric-value" id="equity">$0.00</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Current P&L</div>
                            <div class="metric-value" id="pnl">$0.00</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Sharpe Ratio</div>
                            <div class="metric-value" id="sharpe">0.00</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Max Drawdown</div>
                            <div class="metric-value" id="drawdown">0.00%</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Win Rate</div>
                            <div class="metric-value" id="winrate">0.00%</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">Total Trades</div>
                            <div class="metric-value" id="trades">0</div>
                        </div>
                    </div>

                    <div class="charts-section">
                        <div class="chart-card">
                            <div class="chart-title">Equity Curve</div>
                            <canvas id="equityChart"></canvas>
                        </div>
                        <div class="chart-card">
                            <div class="chart-title">Holdings</div>
                            <canvas id="holdingsChart"></canvas>
                        </div>
                    </div>

                    <div class="chart-card">
                        <div class="chart-title">Open Positions</div>
                        <table class="positions-table" id="positionsTable">
                            <thead>
                                <tr>
                                    <th>Symbol</th>
                                    <th>Qty</th>
                                    <th>Entry Price</th>
                                    <th>Current Price</th>
                                    <th>P&L</th>
                                    <th>Return %</th>
                                </tr>
                            </thead>
                            <tbody id="positionsBody">
                            </tbody>
                        </table>
                    </div>
                </div>
                </div>
                
                <div id="logs" class="page">
                    <div class="logs-toolbar">
                        <button onclick="copyAllLogs()">Copy All Logs</button>
                        <button onclick="clearLogs()">Clear Logs</button>
                    </div>
                    <div class="logs-container" id="logsContainer">
                        <p style="color: #9090b0;">Loading logs...</p>
                    </div>
                </div>
                
                <div id="trades" class="page">
                    <div class="chart-card">
                        <div class="chart-title">Trade History</div>
                        <table class="positions-table" style="width: 100%;">
                            <thead>
                                <tr>
                                    <th>Date</th>
                                    <th>Symbol</th>
                                    <th>Type</th>
                                    <th>Qty</th>
                                    <th>Entry Price</th>
                                    <th>Exit Price</th>
                                    <th>P&L</th>
                                    <th>Return %</th>
                                </tr>
                            </thead>
                            <tbody id="tradesBody">
                                <tr><td colspan="8" style="text-align: center; color: #9090b0;">No closed trades yet</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script>
                let equityChart, holdingsChart;

                async function fetchData() {
                    try {
                        const response = await fetch('/api/data');
                        const data = await response.json();
                        
                        document.getElementById('status').style.display = 'none';
                        document.getElementById('content').style.display = 'block';
                        
                        updateMetrics(data);
                        updateCharts(data);
                        updatePositions(data);
                    } catch (error) {
                        console.error('Error fetching data:', error);
                        document.getElementById('status').innerHTML = '<p style="color: #ff3366;">Error loading data</p>';
                    }
                }

                function updateMetrics(data) {
                    const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
                    const fmt2 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                    
                    const equity = data.portfolio?.equity || 0;
                    const cash = data.portfolio?.cash || 0;
                    const pnl = (equity + cash) - 100000;
                    
                    document.getElementById('equity').textContent = fmt.format(equity + cash);
                    
                    const pnlEl = document.getElementById('pnl');
                    pnlEl.textContent = fmt.format(pnl);
                    pnlEl.className = 'metric-value ' + (pnl >= 0 ? 'positive' : 'negative');
                    
                    document.getElementById('sharpe').textContent = fmt2.format(data.sharpe_ratio || 0);
                    document.getElementById('drawdown').textContent = fmt2.format((data.max_drawdown_pct || 0) * 100) + '%';
                    document.getElementById('winrate').textContent = fmt2.format((data.win_rate || 0) * 100) + '%';
                    document.getElementById('trades').textContent = (data.num_trades || 0).toString();
                }

                function updateCharts(data) {
                    const equity = data.equity_history || [];
                    const labels = equity.map((_, i) => i);

                    if (equityChart) equityChart.destroy();
                    if (holdingsChart) holdingsChart.destroy();

                    const ctx1 = document.getElementById('equityChart').getContext('2d');
                    equityChart = new Chart(ctx1, {
                        type: 'line',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Equity',
                                data: equity,
                                borderColor: '#00d4ff',
                                backgroundColor: 'rgba(0, 212, 255, 0.1)',
                                borderWidth: 2,
                                fill: true,
                                tension: 0.4,
                                pointRadius: 0,
                                pointHoverRadius: 6
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: { legend: { display: false } },
                            scales: {
                                y: { 
                                    grid: { color: 'rgba(0, 212, 255, 0.1)' },
                                    ticks: { color: '#9090b0' }
                                },
                                x: { display: false }
                            }
                        }
                    });

                    const holdings = data.portfolio?.holdings || {};
                    const ctx2 = document.getElementById('holdingsChart').getContext('2d');
                    holdingsChart = new Chart(ctx2, {
                        type: 'doughnut',
                        data: {
                            labels: Object.keys(holdings),
                            datasets: [{
                                data: Object.values(holdings).map(h => h.quantity),
                                backgroundColor: ['#00d4ff', '#00ff88', '#ffa500', '#ff3366', '#9d4edd', '#3a86ff']
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: { legend: { labels: { color: '#9090b0' } } }
                        }
                    });
                }

                function updatePositions(data) {
                    const holdings = data.portfolio?.holdings || {};
                    const tbody = document.getElementById('positionsBody');
                    tbody.innerHTML = '';
                    
                    const prices = data.prices || {};
                    const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
                    
                    for (const [symbol, holding] of Object.entries(holdings)) {
                        const qty = holding.quantity || 0;
                        if (qty === 0) continue;
                        
                        const price = prices[symbol] || holding.cost_basis / qty;
                        const current_value = qty * price;
                        const cost = (holding.cost_basis || 0);
                        const pnl = current_value - cost;
                        const ret = cost > 0 ? (pnl / cost) * 100 : 0;
                        
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td><strong>${symbol}</strong></td>
                            <td>${qty.toFixed(2)}</td>
                            <td>${fmt.format((cost / qty) || 0)}</td>
                            <td>${fmt.format(price)}</td>
                            <td style="color: ${pnl >= 0 ? '#00ff88' : '#ff3366'}">${fmt.format(pnl)}</td>
                            <td style="color: ${ret >= 0 ? '#00ff88' : '#ff3366'}">${ret.toFixed(2)}%</td>
                        `;
                        tbody.appendChild(row);
                    }
                }

                // Fetch data immediately and every 2 seconds
                fetchData();
                setInterval(fetchData, 2000);
                
                // Page switching function
                function switchPage(pageName) {
                    // Hide all pages
                    const pages = document.querySelectorAll('.page');
                    pages.forEach(page => page.classList.remove('active'));
                    
                    // Remove active class from all buttons
                    const buttons = document.querySelectorAll('.tab-button');
                    buttons.forEach(button => button.classList.remove('active'));
                    
                    // Show selected page
                    document.getElementById(pageName).classList.add('active');
                    
                    // Add active class to clicked button
                    event.target.classList.add('active');
                    
                    // Load logs when logs page is opened
                    if (pageName === 'logs') {
                        loadLogs();
                    }
                }
                
                // Load logs function
                async function loadLogs() {
                    try {
                        const response = await fetch('/api/logs');
                        const data = await response.json();
                        const logsContainer = document.getElementById('logsContainer');
                        
                        if (!data.logs || data.logs.length === 0) {
                            logsContainer.innerHTML = '<p style="color: #9090b0;">No logs yet</p>';
                            return;
                        }
                        
                        logsContainer.innerHTML = '';
                        data.logs.forEach(log => {
                            const logEntry = document.createElement('div');
                            logEntry.className = `log-entry ${log.level}`;
                            logEntry.textContent = log.message;
                            logsContainer.appendChild(logEntry);
                        });
                        
                        // Scroll to bottom
                        logsContainer.scrollTop = logsContainer.scrollHeight;
                    } catch (error) {
                        console.error('Error loading logs:', error);
                    }
                }
                
                // Copy all logs function
                async function copyAllLogs() {
                    try {
                        const response = await fetch('/api/logs');
                        const data = await response.json();
                        const logs = (data.logs || []).map(log => log.message).join('\n');
                        
                        if (navigator.clipboard && navigator.clipboard.writeText) {
                            await navigator.clipboard.writeText(logs);
                            alert('Logs copied to clipboard!');
                        } else {
                            const textarea = document.createElement('textarea');
                            textarea.value = logs;
                            document.body.appendChild(textarea);
                            textarea.select();
                            document.execCommand('copy');
                            document.body.removeChild(textarea);
                            alert('Logs copied to clipboard!');
                        }
                    } catch (error) {
                        console.error('Error copying logs:', error);
                        alert('Failed to copy logs');
                    }
                }
                
                // Clear logs function
                function clearLogs() {
                    document.getElementById('logsContainer').innerHTML = '<p style="color: #9090b0;">Logs cleared</p>';
                }
                
                // Refresh logs every 2 seconds when on logs page
                setInterval(() => {
                    if (document.getElementById('logs').classList.contains('active')) {
                        loadLogs();
                    }
                }, 2000);
            </script>
        </body>
        </html>
        """
        return render_template_string(html)

    @app.route("/api/data")
    def get_data():
        """API endpoint to return current trading data."""
        update = app.state.get("current_update")
        if not update:
            return jsonify({
                "portfolio": {"equity": 0, "cash": 100000, "holdings": {}},
                "prices": {},
                "sharpe_ratio": 0,
                "max_drawdown_pct": 0,
                "win_rate": 0,
                "num_trades": 0,
                "equity_history": []
            })

        holdings = {}
        if hasattr(update.portfolio, 'holdings') and update.portfolio.holdings:
            for symbol, holding in update.portfolio.holdings.items():
                holdings[symbol] = {
                    "quantity": holding.quantity,
                    "cost_basis": holding.cost_basis,
                    "avg_cost": holding.avg_cost
                }

        return jsonify({
            "portfolio": {
                "equity": float(update.portfolio.equity(update.prices)) if hasattr(update.portfolio, 'equity') else 0,
                "cash": float(update.portfolio.cash) if hasattr(update.portfolio, 'cash') else 100000,
                "holdings": holdings
            },
            "prices": {k: float(v) for k, v in update.prices.items()} if update.prices else {},
            "sharpe_ratio": float(update.sharpe_ratio) if update.sharpe_ratio else 0,
            "max_drawdown_pct": float(update.max_drawdown_pct) if update.max_drawdown_pct else 0,
            "win_rate": float(update.win_rate) if update.win_rate else 0,
            "num_trades": int(update.num_trades) if update.num_trades else 0,
            "equity_history": [float(x) for x in app.state.get("equity_history", [])]
        })
    
    @app.route("/api/smart-selection")
    def get_smart_selection():
        """API endpoint for smart selection metrics and predictions."""
        try:
            from trading_bot.data.smart_selector import StockScorer
            from trading_bot.data.performance_tracker import PerformanceTracker
            from trading_bot.data.ml_predictor import MLPredictor
            from trading_bot.data.portfolio_optimizer import PortfolioOptimizer
            from trading_bot.data.risk_manager import RiskManager
            
            # Load latest scores
            scorer = StockScorer()
            scores = scorer.load_scores("latest")
            
            # Load performance history
            tracker = PerformanceTracker()
            top_performers = tracker.get_top_performers(top_n=10)
            
            # Get ML predictions
            predictor = MLPredictor()
            predictor.load_model()
            perf_dict = {p.symbol: p for p in top_performers}
            predictions = predictor.predict(perf_dict)
            
            # Get risk metrics
            update = app.state.get("current_update")
            equity = float(update.portfolio.equity(update.prices)) if update else 100000
            manager = RiskManager()
            risk_metrics = manager.get_metrics(equity, num_positions=len(scores or {}))
            
            # Format response
            score_list = []
            for sym, score in sorted((scores or {}).items(), key=lambda x: x[1].overall_score, reverse=True)[:20]:
                pred = predictions.get(sym)
                score_list.append({
                    "symbol": sym,
                    "score": round(score.overall_score, 1),
                    "trend": round(score.trend_score, 1),
                    "volatility": round(score.volatility_score, 1),
                    "volume": round(score.volume_score, 1),
                    "liquidity": round(score.liquidity_score, 1),
                    "win_probability": round(pred.win_probability * 100, 1) if pred else 0,
                    "expected_return": round(pred.expected_return_pct, 2) if pred else 0,
                })
            
            return jsonify({
                "top_scores": score_list,
                "top_performers": [
                    {
                        "symbol": p.symbol,
                        "wins": p.wins,
                        "losses": p.losses,
                        "win_rate": round(p.win_rate * 100, 1),
                        "profit_factor": round(p.profit_factor, 2),
                    }
                    for p in top_performers[:10]
                ],
                "risk_metrics": {
                    "daily_loss_pct": round(risk_metrics.daily_loss_pct, 2),
                    "max_daily_loss_pct": risk_metrics.max_daily_loss,
                    "current_drawdown": round(risk_metrics.current_drawdown, 2),
                    "max_drawdown_pct": risk_metrics.max_drawdown,
                    "at_risk": risk_metrics.at_risk,
                },
                "timestamp": str(app.state.get("last_update", "N/A")),
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/logs")
    def get_logs():
        """Get application logs."""
        log_handler = app.state.get('log_handler')
        logs = list(log_handler.logs) if log_handler else []
        return jsonify({"logs": logs})

    return app


# Create app instance for Gunicorn WSGI server
app = create_web_app()


def run_web_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """Run the web server."""
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    run_web_server()
