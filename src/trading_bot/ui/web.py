"""Optimized web dashboard for trading bot - Flask application with logs page."""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request
from flask_cors import CORS

from trading_bot.engine.paper import PaperEngineUpdate

# Configure logging to also send to dashboard
class DashboardLogHandler(logging.Handler):
    """Handler that stores logs for dashboard streaming."""
    def __init__(self, log_buffer, max_size=500):
        super().__init__()
        self.log_buffer = log_buffer
        self.max_size = max_size
    
    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_buffer.append({
                'timestamp': record.created,
                'level': record.levelname,
                'message': msg,
            })
        except Exception:
            self.handleError(record)


def create_web_app():
    """Create and configure Flask application."""
    app = Flask(__name__, template_folder=str(Path(__file__).parent))
    CORS(app)

    # Shared state - use deque for O(1) performance
    log_buffer = deque(maxlen=500)
    app.state = {
        "current_update": None,
        "equity_history": [],
        "log_buffer": log_buffer,
    }
    
    # Add log handler
    log_handler = DashboardLogHandler(log_buffer)
    log_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    ))
    logging.getLogger().addHandler(log_handler)

    # ============ MAIN DASHBOARD PAGE ============
    @app.route("/")
    def index():
        """Serve main dashboard with 2-page navigation."""
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Trading Bot Dashboard</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
                    color: #e0e0e0;
                    min-height: 100vh;
                }
                .header {
                    background: rgba(0, 0, 0, 0.3);
                    border-bottom: 1px solid rgba(0, 212, 255, 0.3);
                    padding: 20px;
                    position: sticky;
                    top: 0;
                    z-index: 100;
                }
                .header-content {
                    max-width: 1400px;
                    margin: 0 auto;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                h1 {
                    font-size: 2em;
                    background: linear-gradient(135deg, #00d4ff, #0099ff);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                    background-clip: text;
                }
                .nav-tabs {
                    display: flex;
                    gap: 10px;
                }
                .nav-tab {
                    padding: 10px 20px;
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    background: transparent;
                    color: #e0e0e0;
                    border-radius: 8px;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    font-size: 0.95em;
                }
                .nav-tab:hover {
                    border-color: #00d4ff;
                    color: #00d4ff;
                }
                .nav-tab.active {
                    background: rgba(0, 212, 255, 0.2);
                    border-color: #00d4ff;
                    color: #00d4ff;
                }
                .container {
                    max-width: 1400px;
                    margin: 0 auto;
                    padding: 20px;
                }
                .page { display: none; }
                .page.active { display: block; }
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
                @keyframes spin { to { transform: rotate(360deg); } }
                
                .status-section {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                    gap: 15px;
                    margin-bottom: 20px;
                }
                .metric-card {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    border-radius: 10px;
                    padding: 15px;
                    backdrop-filter: blur(10px);
                }
                .metric-label {
                    font-size: 0.85em;
                    color: #9090b0;
                    margin-bottom: 8px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                .metric-value {
                    font-size: 1.6em;
                    font-weight: bold;
                    color: #00d4ff;
                }
                .metric-value.positive { color: #00ff88; }
                .metric-value.negative { color: #ff3366; }
                
                .charts-section {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
                    gap: 20px;
                    margin-bottom: 20px;
                }
                .chart-card {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    border-radius: 10px;
                    padding: 15px;
                    backdrop-filter: blur(10px);
                }
                .chart-title {
                    margin-bottom: 10px;
                    color: #00d4ff;
                    font-weight: bold;
                    font-size: 1.1em;
                }
                canvas { width: 100% !important; height: 250px !important; }
                
                .positions-table {
                    width: 100%;
                    border-collapse: collapse;
                    background: rgba(255, 255, 255, 0.02);
                    border-radius: 10px;
                    overflow: hidden;
                }
                .positions-table th {
                    background: rgba(0, 212, 255, 0.1);
                    padding: 10px;
                    text-align: left;
                    color: #00d4ff;
                    font-weight: bold;
                    border-bottom: 1px solid rgba(0, 212, 255, 0.3);
                }
                .positions-table td {
                    padding: 10px;
                    border-bottom: 1px solid rgba(0, 212, 255, 0.1);
                    font-size: 0.95em;
                }
                .positions-table tr:hover { background: rgba(0, 212, 255, 0.05); }
                
                /* LOGS PAGE STYLES */
                .logs-container {
                    display: flex;
                    flex-direction: column;
                    height: calc(100vh - 150px);
                }
                .logs-controls {
                    display: flex;
                    gap: 10px;
                    margin-bottom: 15px;
                    flex-wrap: wrap;
                }
                .log-filter {
                    padding: 8px 12px;
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    color: #e0e0e0;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 0.9em;
                    transition: all 0.3s ease;
                }
                .log-filter:hover, .log-filter.active {
                    background: rgba(0, 212, 255, 0.2);
                    border-color: #00d4ff;
                    color: #00d4ff;
                }
                #logsBox {
                    flex: 1;
                    background: rgba(0, 0, 0, 0.4);
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    border-radius: 8px;
                    padding: 12px;
                    overflow-y: auto;
                    font-family: 'Monaco', 'Courier New', monospace;
                    font-size: 0.85em;
                    line-height: 1.4;
                }
                .log-entry {
                    padding: 4px 0;
                    margin: 2px 0;
                    border-left: 3px solid transparent;
                    padding-left: 8px;
                    white-space: pre-wrap;
                    word-break: break-word;
                }
                .log-entry.DEBUG { color: #9090b0; border-color: #6666a0; }
                .log-entry.INFO { color: #e0e0e0; border-color: #00d4ff; }
                .log-entry.WARNING { color: #ffa500; border-color: #ff9500; }
                .log-entry.ERROR { color: #ff3366; border-color: #ff3366; }
                .log-entry.CRITICAL { color: #ff3366; border-color: #ff0000; font-weight: bold; }
                .log-timestamp { color: #6666a0; font-size: 0.9em; }
                
                /* SCROLLBAR */
                ::-webkit-scrollbar {
                    width: 8px;
                    height: 8px;
                }
                ::-webkit-scrollbar-track {
                    background: rgba(0, 212, 255, 0.05);
                }
                ::-webkit-scrollbar-thumb {
                    background: rgba(0, 212, 255, 0.3);
                    border-radius: 4px;
                }
                ::-webkit-scrollbar-thumb:hover {
                    background: rgba(0, 212, 255, 0.6);
                }
                /* CARD STYLES */
                .card {
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(0, 212, 255, 0.2);
                    border-radius: 10px;
                    padding: 20px;
                    backdrop-filter: blur(10px);
                    margin-bottom: 20px;
                }
                .card h2 {
                    color: #00d4ff;
                    margin-bottom: 15px;
                    font-size: 1.3em;
                    border-bottom: 2px solid rgba(0, 212, 255, 0.3);
                    padding-bottom: 10px;
                }
                /* TABLE STYLES */
                table {
                    width: 100%;
                    border-collapse: collapse;
                    color: #e0e0e0;
                }
                table thead {
                    background: rgba(0, 212, 255, 0.1);
                    border-bottom: 2px solid rgba(0, 212, 255, 0.3);
                }
                table th {
                    padding: 12px;
                    text-align: left;
                    color: #00d4ff;
                    font-weight: 600;
                    text-transform: uppercase;
                    font-size: 0.9em;
                }
                table td {
                    padding: 12px;
                    border-bottom: 1px solid rgba(0, 212, 255, 0.1);
                }
                table tr:hover {
                    background: rgba(0, 212, 255, 0.05);
                }
                /* FORM STYLES */
                form {
                    display: flex;
                    flex-direction: column;
                    gap: 15px;
                }
                form div {
                    display: flex;
                    flex-direction: column;
                    gap: 5px;
                }
                form label {
                    color: #9090b0;
                    font-weight: 600;
                    text-transform: uppercase;
                    font-size: 0.9em;
                }
                form select, form input {
                    padding: 10px;
                    background: rgba(255, 255, 255, 0.05);
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    color: #e0e0e0;
                    border-radius: 6px;
                    font-size: 1em;
                }
                form select:focus, form input:focus {
                    outline: none;
                    border-color: #00d4ff;
                    background: rgba(0, 212, 255, 0.1);
                }
                form button {
                    padding: 12px 24px;
                    background: linear-gradient(135deg, #00d4ff, #0099ff);
                    border: none;
                    color: white;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: bold;
                    transition: all 0.3s ease;
                }
                form button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 5px 15px rgba(0, 212, 255, 0.4);
                }            </style>
        </head>
        <body>
            <div class="header">
                <div class="header-content">
                    <h1>📈 Trading Bot Dashboard</h1>
                    <div style="display: flex; align-items: center; gap: 20px;">
                        <div id="market-status" style="display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: rgba(0, 212, 255, 0.1); border-radius: 6px; border: 1px solid rgba(0, 212, 255, 0.3);">
                            <div id="market-indicator" style="width: 10px; height: 10px; border-radius: 50%; background: #ff6b6b;"></div>
                            <span id="market-text" style="font-size: 0.9em; color: #ff6b6b;">Market Closed</span>
                        </div>
                        <div class="nav-tabs">
                            <button class="nav-tab active" onclick="switchPage('stats')">📊 Statistics</button>
                            <button class="nav-tab" onclick="switchPage('performance')">💰 Performance</button>
                            <button class="nav-tab" onclick="switchPage('positions')">📍 Positions</button>
                            <button class="nav-tab" onclick="switchPage('orders')">📋 Orders</button>
                            <button class="nav-tab" onclick="switchPage('analysis')">📈 Analysis</button>
                            <button class="nav-tab" onclick="switchPage('logs')">📝 Logs</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- STATS PAGE -->
            <div id="stats" class="page active">
                <div class="container">
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
                                <div class="metric-label">P&L</div>
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
                            <table class="positions-table">
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
                                <tbody id="positionsBody"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- LOGS PAGE -->
            <div id="logs" class="page">
                <div class="container">
                    <div class="logs-container">
                        <div class="logs-controls">
                            <button class="log-filter active" onclick="filterLogs('ALL')">All</button>
                            <button class="log-filter" onclick="filterLogs('DEBUG')">DEBUG</button>
                            <button class="log-filter" onclick="filterLogs('INFO')">INFO</button>
                            <button class="log-filter" onclick="filterLogs('WARNING')">WARNING</button>
                            <button class="log-filter" onclick="filterLogs('ERROR')">ERROR</button>
                            <button class="log-filter" onclick="clearLogs()" style="margin-left: auto;">Clear</button>
                        </div>
                        <div id="logsBox"></div>
                    </div>
                </div>
            </div>
                
            <!-- PERFORMANCE PAGE -->
            <div id="performance" class="page">
                <div class="container">
                    <div class="card">
                        <h2>Performance Metrics</h2>
                        <table>
                            <tr><td>Return %</td><td id="return-pct">0%</td></tr>
                            <tr><td>Profit Factor</td><td id="profit-factor">0.00</td></tr>
                            <tr><td>Max Drawdown</td><td id="max-drawdown">0%</td></tr>
                            <tr><td>Win Rate</td><td id="win-rate">0%</td></tr>
                            <tr><td>Total Trades</td><td id="total-trades">0</td></tr>
                        </table>
                    </div>
                </div>
            </div>
                
            <!-- POSITIONS PAGE -->
            <div id="positions" class="page">
                <div class="container">
                    <div class="card">
                        <h2>Open Positions</h2>
                        <table>
                            <thead><tr><th>Symbol</th><th>Size</th><th>Entry</th><th>Current</th><th>P&L</th></tr></thead>
                            <tbody id="positions-list"><tr><td colspan="5">No open positions</td></tr></tbody>
                        </table>
                    </div>
                </div>
            </div>
                
            <!-- ORDERS PAGE -->
            <div id="orders" class="page">
                <div class="container">
                    <div class="card">
                        <h2>Pending Orders</h2>
                        <table>
                            <thead><tr><th>Symbol</th><th>Type</th><th>Qty</th><th>Price</th><th>Status</th></tr></thead>
                            <tbody id="orders-list"><tr><td colspan="5">No pending orders</td></tr></tbody>
                        </table>
                    </div>
                </div>
            </div>
                
            <!-- ANALYSIS PAGE -->
            <div id="analysis" class="page">
                <div class="container">
                    <div class="card">
                        <h2>Market Analysis</h2>
                        <table>
                            <tr><td>Volatility</td><td id="volatility">--</td></tr>
                            <tr><td>Trend</td><td id="trend">--</td></tr>
                            <tr><td>Momentum</td><td id="momentum">--</td></tr>
                            <tr><td>RSI</td><td id="rsi">--</td></tr>
                            <tr><td>MACD</td><td id="macd">--</td></tr>
                        </table>
                    </div>
                    
                    <div class="card">
                        <h2>🤖 Multi-Strategy Ensemble</h2>
                        <table>
                            <tr><td><strong>Ensemble Signal</strong></td><td id="ensemble-signal">NEUTRAL (0)</td></tr>
                            <tr><td><strong>Confidence</strong></td><td id="ensemble-confidence">0%</td></tr>
                            <tr style="border-top: 1px solid rgba(0, 212, 255, 0.2); margin-top: 10px;"><td colspan="2" style="padding-top: 15px;"><strong>Strategy Signals</strong></td></tr>
                        </table>
                        <div id="strategy-signals-container"></div>
                        
                        <div style="margin-top: 15px;">
                            <strong style="color: #00d4ff;">Strategy Weights</strong>
                            <div id="strategy-weights-container"></div>
                        </div>
                    </div>
                </div>
            </div>

            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <script>
                let equityChart, holdingsChart;
                let allLogs = [];
                let currentFilter = 'ALL';
                let autoScroll = true;

                function switchPage(page) {
                    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
                    document.getElementById(page).classList.add('active');
                    
                    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
                    event.target.classList.add('active');
                    
                    if (page === 'logs') startLogPolling();
                }
                
                function updateMarketStatus() {
                    const now = new Date();
                    const easternTime = now.toLocaleString('en-US', { timeZone: 'America/New_York' });
                    const easternDate = new Date(easternTime);
                    const dayOfWeek = easternDate.getDay();
                    const hours = easternDate.getHours();
                    const minutes = easternDate.getMinutes();
                    
                    // Market open: Mon-Fri 9:30 AM - 4:00 PM ET
                    const isWeekday = dayOfWeek >= 1 && dayOfWeek <= 5;
                    const isOpenHours = hours > 9 || (hours === 9 && minutes >= 30) && hours < 16;
                    const isMarketOpen = isWeekday && isOpenHours;
                    
                    const indicator = document.getElementById('market-indicator');
                    const statusText = document.getElementById('market-text');
                    
                    if (isMarketOpen) {
                        indicator.style.background = '#00ff88';
                        statusText.style.color = '#00ff88';
                        statusText.textContent = '🔴 MARKET OPEN';
                    } else if (dayOfWeek === 0 || dayOfWeek === 6) {
                        indicator.style.background = '#9090b0';
                        statusText.style.color = '#9090b0';
                        statusText.textContent = '🔴 MARKET CLOSED (Weekend)';
                    } else if (hours < 9) {
                        indicator.style.background = '#ffa500';
                        statusText.style.color = '#ffa500';
                        statusText.textContent = '🟡 PRE-MARKET';
                    } else if (hours >= 16) {
                        indicator.style.background = '#ffa500';
                        statusText.style.color = '#ffa500';
                        statusText.textContent = '🟡 AFTER-HOURS';
                    } else {
                        indicator.style.background = '#ff6b6b';
                        statusText.style.color = '#ff6b6b';
                        statusText.textContent = '🔴 MARKET CLOSED';
                    }
                }

                async function fetchData() {
                    try {
                        const response = await fetch('/api/data');
                        const data = await response.json();
                        
                        const statusEl = document.getElementById('status');
                        const contentEl = document.getElementById('content');
                        if (statusEl) statusEl.style.display = 'none';
                        if (contentEl) contentEl.style.display = 'block';
                        
                        updateMarketStatus();
                        updateMetrics(data);
                        updateCharts(data);
                        updatePositions(data);
                        updatePerformanceMetrics(data);
                        updatePositionsList(data);
                        updateEnsembleDisplay(data);
                        fetchLogs();
                    } catch (error) {
                        console.error('Error fetching data:', error);
                    }
                }

                function updateMetrics(data) {
                    try {
                        const fmt = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
                        const fmt2 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                        
                        const equity = data.portfolio?.equity || 0;
                        const cash = data.portfolio?.cash || 0;
                        const total = equity + cash;
                        const pnl = total - 100000;
                        
                        const equityEl = document.getElementById('equity');
                        if (equityEl) equityEl.textContent = fmt.format(total);
                        
                        const pnlEl = document.getElementById('pnl');
                        if (pnlEl) {
                            pnlEl.textContent = fmt.format(pnl);
                            pnlEl.className = 'metric-value ' + (pnl >= 0 ? 'positive' : 'negative');
                        }
                        
                        const sharpeEl = document.getElementById('sharpe');
                        if (sharpeEl) sharpeEl.textContent = fmt2.format(data.sharpe_ratio || 0);
                        
                        const drawdownEl = document.getElementById('drawdown');
                        if (drawdownEl) drawdownEl.textContent = fmt2.format((data.max_drawdown_pct || 0) * 100) + '%';
                        
                        const winrateEl = document.getElementById('winrate');
                        if (winrateEl) winrateEl.textContent = fmt2.format((data.win_rate || 0) * 100) + '%';
                        
                        const tradesEl = document.getElementById('trades');
                        if (tradesEl) tradesEl.textContent = (data.num_trades || 0).toString();
                    } catch (error) {
                        console.error('Error in updateMetrics:', error);
                    }
                }

                function updateCharts(data) {
                    const equity = data.equity_history || [];
                    const holdings = data.portfolio?.holdings || {};

                    // Update equity chart data without destroying
                    if (equityChart) {
                        equityChart.data.labels = equity.map((_, i) => i);
                        equityChart.data.datasets[0].data = equity;
                        equityChart.update('none'); // 'none' = no animation
                    } else {
                        const ctx1 = document.getElementById('equityChart').getContext('2d');
                        equityChart = new Chart(ctx1, {
                            type: 'line',
                            data: {
                                labels: equity.map((_, i) => i),
                                datasets: [{
                                    label: 'Equity',
                                    data: equity,
                                    borderColor: '#00d4ff',
                                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                                    borderWidth: 2,
                                    fill: true,
                                    tension: 0.4,
                                    pointRadius: 0
                                }]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: { legend: { display: false } },
                                scales: {
                                    y: { grid: { color: 'rgba(0, 212, 255, 0.1)' }, ticks: { color: '#9090b0' } },
                                    x: { display: false }
                                }
                            }
                        });
                    }

                    // Update holdings chart data without destroying
                    if (holdingsChart) {
                        holdingsChart.data.labels = Object.keys(holdings);
                        holdingsChart.data.datasets[0].data = Object.values(holdings).map(h => h.quantity);
                        holdingsChart.update('none');
                    } else {
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

                async function fetchLogs() {
                    try {
                        const response = await fetch('/api/logs');
                        const data = await response.json();
                        allLogs = data.logs || [];
                        renderLogs();
                    } catch (error) {
                        console.error('Error fetching logs:', error);
                    }
                }

                function filterLogs(level) {
                    currentFilter = level;
                    
                    document.querySelectorAll('.log-filter').forEach(b => b.classList.remove('active'));
                    event.target.classList.add('active');
                    
                    renderLogs();
                }

                function renderLogs() {
                    const logsBox = document.getElementById('logsBox');
                    let filtered = allLogs;
                    
                    if (currentFilter !== 'ALL') {
                        filtered = allLogs.filter(log => log.level === currentFilter);
                    }
                    
                    logsBox.innerHTML = filtered.map(log => {
                        const date = new Date(log.timestamp * 1000).toLocaleTimeString();
                        return `<div class="log-entry ${log.level}"><span class="log-timestamp">${date}</span> [${log.level}] ${log.message}</div>`;
                    }).join('');
                    
                    if (autoScroll) {
                        logsBox.scrollTop = logsBox.scrollHeight;
                    }
                }

                function clearLogs() {
                    if (confirm('Clear all logs?')) {
                        fetch('/api/logs/clear', { method: 'POST' }).then(() => fetchLogs());
                    }
                }

                function startLogPolling() {
                    fetchLogs();
                    setInterval(fetchLogs, 500);
                }
                
                // Update performance metrics
                function updatePerformanceMetrics(data) {
                    const totalReturn = (((data.portfolio?.equity || 0) + (data.portfolio?.cash || 100000)) - 100000) / 100000 * 100;
                    document.getElementById('return-pct').textContent = totalReturn.toFixed(2) + '%';
                    document.getElementById('profit-factor').textContent = '0.00';
                    document.getElementById('max-drawdown').textContent = ((data.max_drawdown_pct || 0) * 100).toFixed(2) + '%';
                    document.getElementById('win-rate').textContent = ((data.win_rate || 0) * 100).toFixed(2) + '%';
                    document.getElementById('total-trades').textContent = (data.num_trades || 0).toString();
                    
                    // Update ensemble data
                    updateEnsembleDisplay(data);
                }
                
                // Update ensemble strategy display
                function updateEnsembleDisplay(data) {
                    const ensemble = data.ensemble || {};
                    
                    // Ensemble signal
                    const signalEl = document.getElementById('ensemble-signal');
                    if (signalEl) {
                        const signal = ensemble.signal || 0;
                        const signalText = signal > 0 ? 'LONG (↑)' : signal < 0 ? 'SHORT (↓)' : 'NEUTRAL (→)';
                        const color = signal > 0 ? '#00ff88' : signal < 0 ? '#ff3366' : '#9090b0';
                        signalEl.textContent = signalText;
                        signalEl.style.color = color;
                    }
                    
                    // Confidence
                    const confEl = document.getElementById('ensemble-confidence');
                    if (confEl) {
                        const conf = (ensemble.confidence || 0) * 100;
                        confEl.textContent = conf.toFixed(1) + '%';
                    }
                    
                    // Strategy signals
                    const signalsContainer = document.getElementById('strategy-signals-container');
                    if (signalsContainer && ensemble.strategy_signals) {
                        signalsContainer.innerHTML = '';
                        const signals = ensemble.strategy_signals;
                        
                        const table = document.createElement('table');
                        table.style.marginTop = '10px';
                        
                        for (const [strategy, signal] of Object.entries(signals)) {
                            const row = table.insertRow();
                            const strategyName = strategy.replace(/_/g, ' ').toUpperCase();
                            const signalText = signal > 0 ? 'LONG ↑' : signal < 0 ? 'SHORT ↓' : 'NEUTRAL →';
                            const color = signal > 0 ? '#00ff88' : signal < 0 ? '#ff3366' : '#9090b0';
                            row.innerHTML = `<td style="padding: 6px 0;">• ${strategyName}</td><td style="color: ${color}; text-align: right;">${signalText}</td>`;
                        }
                        
                        signalsContainer.appendChild(table);
                    }
                    
                    // Strategy weights
                    const weightsContainer = document.getElementById('strategy-weights-container');
                    if (weightsContainer && ensemble.weights) {
                        weightsContainer.innerHTML = '';
                        const weights = ensemble.weights;
                        
                        for (const [strategy, weight] of Object.entries(weights)) {
                            const pct = (weight * 100).toFixed(1);
                            const barWidth = (weight * 200);
                            const strategyName = strategy.replace(/_/g, ' ').charAt(0).toUpperCase() + strategy.replace(/_/g, ' ').slice(1);
                            
                            const container = document.createElement('div');
                            container.style.marginBottom = '8px';
                            container.innerHTML = `
                                <div style="display: flex; justify-content: space-between; font-size: 0.85em;">
                                    <span>${strategyName}</span>
                                    <span style="color: #00d4ff;">${pct}%</span>
                                </div>
                                <div style="width: 100%; height: 6px; background: rgba(0, 212, 255, 0.1); border-radius: 3px; overflow: hidden;">
                                    <div style="width: ${barWidth}px; height: 100%; background: linear-gradient(90deg, #00d4ff, #00ff88); border-radius: 3px;"></div>
                                </div>
                            `;
                            weightsContainer.appendChild(container);
                        }
                    }
                }
                
                // Update positions list
                function updatePositionsList(data) {
                    const holdings = data.portfolio?.holdings || {};
                    const prices = data.prices || {};
                    const tbody = document.getElementById('positions-list');
                    
                    if (Object.keys(holdings).length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5">No open positions</td></tr>';
                        return;
                    }
                    
                    tbody.innerHTML = '';
                    for (const [symbol, holding] of Object.entries(holdings)) {
                        if (holding.quantity === 0) continue;
                        const price = prices[symbol] || 0;
                        const pnl = (price * holding.quantity) - (holding.cost_basis || 0);
                        const row = tbody.insertRow();
                        row.innerHTML = `
                            <td>${symbol}</td>
                            <td>${holding.quantity.toFixed(2)}</td>
                            <td>$${((holding.cost_basis || 0) / holding.quantity).toFixed(2)}</td>
                            <td>$${price.toFixed(2)}</td>
                            <td style="color: ${pnl >= 0 ? '#00ff88' : '#ff3366'}">${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}</td>
                        `;
                    }
                }
                
                // Save settings
                function saveSettings() {
                    alert('Settings saved successfully!');
                }

                // Initialize on DOM ready with fast update interval
                document.addEventListener('DOMContentLoaded', function() {
                    fetchData();
                    setInterval(fetchData, 500);
                });
                
                // Fallback for already-loaded DOM
                if (document.readyState !== 'loading') {
                    fetchData();
                    setInterval(fetchData, 500);
                }
            </script>
        </body>
        </html>
        """
        return render_template_string(html)

    # ============ API ENDPOINTS ============
    @app.route("/api/data")
    def get_data():
        """API endpoint to return current trading data from database or live update."""
        update = app.state.get("current_update")
        
        # Try to read from SQLite database if available
        import os
        from sqlalchemy import create_engine, desc
        from sqlalchemy.orm import Session
        from trading_bot.db.models import PortfolioSnapshot, FillEvent, Base
        
        db_path = "/app/data/trades.sqlite"
        equity_history = []
        portfolio_data = {
            "equity": 100000,
            "cash": 100000,
            "holdings": {}
        }
        
        if os.path.exists(db_path):
            try:
                engine = create_engine(f"sqlite:///{db_path}")
                Base.metadata.create_all(engine)
                with Session(engine) as session:
                    # Get latest portfolio snapshot
                    latest_snapshot = session.query(PortfolioSnapshot).order_by(desc(PortfolioSnapshot.ts)).first()
                    if latest_snapshot:
                        portfolio_data["equity"] = float(latest_snapshot.equity)
                        portfolio_data["cash"] = float(latest_snapshot.cash)
                    
                    # Get equity history from all snapshots
                    snapshots = session.query(PortfolioSnapshot).order_by(PortfolioSnapshot.ts).all()
                    equity_history = [float(s.equity) for s in snapshots[-100:]]  # Last 100
                    
                    # Get recent fills for holdings
                    recent_fills = session.query(FillEvent).order_by(desc(FillEvent.ts)).limit(1000).all()
                    holdings_qty = {}
                    for fill in reversed(recent_fills):  # Process in chronological order
                        if fill.symbol not in holdings_qty:
                            holdings_qty[fill.symbol] = 0
                        if fill.side.upper() == 'BUY':
                            holdings_qty[fill.symbol] += fill.qty
                        else:
                            holdings_qty[fill.symbol] -= fill.qty
                    
                    # Only show positions with qty > 0
                    for symbol, qty in holdings_qty.items():
                        if qty > 0:
                            portfolio_data["holdings"][symbol] = {
                                "quantity": qty,
                                "cost_basis": 0,
                                "avg_cost": 0
                            }
            except Exception as e:
                logger.warning(f"Could not read database: {e}")
        
        # If we have live update from bot, use it, otherwise use database data
        if update:
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
                    "equity": float(update.portfolio.equity(update.prices)) if hasattr(update.portfolio, 'equity') else portfolio_data["equity"],
                    "cash": float(update.portfolio.cash) if hasattr(update.portfolio, 'cash') else portfolio_data["cash"],
                    "holdings": holdings if holdings else portfolio_data["holdings"]
                },
                "prices": {k: float(v) for k, v in update.prices.items()} if update.prices else {},
                "sharpe_ratio": float(update.sharpe_ratio) if update.sharpe_ratio else 0,
                "max_drawdown_pct": float(update.max_drawdown_pct) if update.max_drawdown_pct else 0,
                "win_rate": float(update.win_rate) if update.win_rate else 0,
                "num_trades": int(update.num_trades) if update.num_trades else 0,
                "equity_history": [float(x) for x in app.state.get("equity_history", equity_history)],
                "ensemble": app.state.get("ensemble_data", {
                    "signal": 0,
                    "confidence": 0.0,
                    "weights": {"atr_breakout": 0.33, "macd_volume": 0.33, "rsi_mean_reversion": 0.34},
                    "strategy_signals": {"atr_breakout": 0, "macd_volume": 0, "rsi_mean_reversion": 0}
                })
            })
        else:
            # Return database data when no live update
            return jsonify({
                "portfolio": {
                    "equity": portfolio_data["equity"],
                    "cash": portfolio_data["cash"],
                    "holdings": portfolio_data["holdings"]
                },
                "prices": {},
                "sharpe_ratio": 0,
                "max_drawdown_pct": 0,
                "win_rate": 0,
                "num_trades": len([h for h in portfolio_data["holdings"]]),
                "equity_history": equity_history,
                "ensemble": {
                    "signal": 0,
                    "confidence": 0.0,
                    "weights": {"atr_breakout": 0.33, "macd_volume": 0.33, "rsi_mean_reversion": 0.34},
                    "strategy_signals": {"atr_breakout": 0, "macd_volume": 0, "rsi_mean_reversion": 0}
                }
            })

    @app.route("/api/logs")
    def get_logs():
        """API endpoint to stream logs from the log file."""
        logs = list(app.state.get("log_buffer", []))
        
        # Also try to read from the actual bot log file
        import os
        from datetime import datetime
        log_file = "/app/logs/trading_bot.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                    # Parse the last 100 lines
                    for line in lines[-100:]:
                        line = line.strip()
                        if line:
                            # Try to parse timestamps from common log formats
                            try:
                                # Skip if already in log_buffer
                                if {'message': line} not in logs:
                                    logs.append({
                                        'timestamp': datetime.now().timestamp(),
                                        'level': 'INFO' if '[INFO]' in line else 'DEBUG' if '[DEBUG]' in line else 'ERROR' if '[ERROR]' in line else 'WARN',
                                        'message': line
                                    })
                            except:
                                pass
            except Exception as e:
                logger.warning(f"Could not read log file: {e}")
        
        # If still no logs, show a message that bot is running
        if not logs:
            logs = [
                {
                    'timestamp': datetime.now().timestamp(),
                    'level': 'INFO',
                    'message': '[INFO] Bot is running with Alpaca paper trading - check docker logs algo-trading-bot'
                }
            ]
        
        return jsonify({"logs": logs[-100:]})

    @app.route("/api/logs/clear", methods=["POST"])
    def clear_logs():
        """Clear all logs."""
        app.state["log_buffer"].clear()
        return jsonify({"status": "ok"})

    @app.route("/health")
    def health():
        """Health check endpoint."""
        return jsonify({"status": "healthy"})

    return app


# Create app instance for Gunicorn WSGI server
app = create_web_app()


def run_web_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """Run the web server."""
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    run_web_server()
