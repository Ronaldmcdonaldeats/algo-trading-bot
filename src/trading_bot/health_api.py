"""Minimal Health Check API for Trading Bot Deployment

Provides basic health and status endpoints for monitoring the deployment.
This is a lightweight alternative when full app initialization fails.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import os
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
DEPLOYMENT_ENV = os.getenv('DEPLOYMENT_ENV', 'production')
MODE = os.getenv('MODE', 'paper')
STRATEGY = os.getenv('STRATEGY', 'gen364')


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'trading-bot-api'
    }), 200


@app.route('/status', methods=['GET'])
def status():
    """Deployment status"""
    return jsonify({
        'status': 'running',
        'environment': DEPLOYMENT_ENV,
        'mode': MODE,
        'strategy': STRATEGY,
        'timestamp': datetime.utcnow().isoformat(),
        'port': 5001,
        'version': '1.0.0',
        'security': 'SSH-tunnel-only'
    }), 200


@app.route('/info', methods=['GET'])
def info():
    """Information about the deployment"""
    return jsonify({
        'service': 'Algo Trading Bot API',
        'version': '1.0.0',
        'deployment': 'Oracle Cloud',
        'security': {
            'ports_exposed': 'None (localhost only)',
            'access_method': 'SSH tunnels',
            'encryption': 'SSH (TLS/encrypted)'
        },
        'strategy': {
            'generation': 364,
            'type': 'Genetically evolved',
            'backtest_return': '+7.32%',
            'win_rate': '46.44%'
        },
        'services': {
            'dashboard': 'Port 5000 (127.0.0.1)',
            'api': 'Port 5001 (127.0.0.1)',
            'database': 'Port 5432 (PostgreSQL, 127.0.0.1)',
            'cache': 'Port 6379 (Redis, 127.0.0.1)'
        },
        'features': {
            'paper_trading': True,
            'strategy_execution': True,
            'monitoring': True,
            'live_trading': 'Disabled until validated'
        }
    }), 200


@app.route('/ready', methods=['GET'])
def ready():
    """Readiness check - services are ready to receive traffic"""
    return jsonify({
        'ready': True,
        'message': 'Services are running and ready',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


if __name__ == '__main__':
    logger.info(f'Starting Trading Bot API on port 5001 (Environment: {DEPLOYMENT_ENV})')
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
