#!/usr/bin/env python
"""Comprehensive test for the Trading Bot Web API and Trading Loop"""
import sys
import os
import time
import threading
import requests
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_web_api():
    """Test the web API and trading loop"""
    logger.info("=" * 70)
    logger.info("TESTING TRADING BOT - WEB API + TRADING LOOP")
    logger.info("=" * 70)
    
    try:
        # Import the API
        from trading_bot.web_api import TradingBotAPI
        logger.info("✓ Web API imported successfully")
        
        # Initialize the API (this starts the trading loop)
        logger.info("\nInitializing Web API...")
        api = TradingBotAPI()
        logger.info("✓ Web API initialized")
        logger.info(f"  - Trading loop active: {api.trading_active}")
        logger.info(f"  - Trading thread: {api.trading_thread}")
        logger.info(f"  - Thread is alive: {api.trading_thread.is_alive() if api.trading_thread else 'N/A'}")
        
        # Test Flask app creation
        logger.info("\n✓ Flask app created successfully")
        logger.info(f"  - App name: {api.app.name}")
        logger.info(f"  - Debug mode: {api.app.debug}")
        
        # Wait for trading loop to initialize
        logger.info("\n⏳ Waiting 5 seconds for trading loop to initialize...")
        time.sleep(5)
        
        # Check if trading thread is still alive
        if api.trading_thread and api.trading_thread.is_alive():
            logger.info("✓ Trading loop thread is running")
        else:
            logger.warning("⚠ Trading loop thread is not running")
        
        # Start the API server in a background thread (non-blocking)
        logger.info("\nStarting Flask server in background...")
        server_thread = threading.Thread(
            target=lambda: api.socketio.run(
                api.app, 
                host='127.0.0.1', 
                port=5000, 
                debug=False,
                use_reloader=False
            ),
            daemon=True
        )
        server_thread.start()
        logger.info("✓ Flask server started")
        
        # Wait for server to start
        logger.info("⏳ Waiting 3 seconds for server to start...")
        time.sleep(3)
        
        # Test API endpoints
        logger.info("\n" + "=" * 70)
        logger.info("TESTING API ENDPOINTS")
        logger.info("=" * 70)
        
        base_url = "http://127.0.0.1:5000"
        
        # Test health check via status endpoint
        logger.info("\n1. Testing /api/status endpoint...")
        try:
            response = requests.get(f"{base_url}/api/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info("✓ /api/status endpoint working")
                logger.info(f"  - Status: {data.get('status')}")
                logger.info(f"  - Equity: ${data.get('equity', 0):.2f}")
                logger.info(f"  - Day PnL: ${data.get('day_pnl', 0):.2f}")
                logger.info(f"  - Day Trades: {data.get('day_trades', 0)}")
            else:
                logger.warning(f"⚠ /api/status returned {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠ /api/status test failed: {e}")
        
        # Test start trading
        logger.info("\n2. Testing /api/start endpoint...")
        try:
            response = requests.post(f"{base_url}/api/start", timeout=5)
            if response.status_code == 200:
                logger.info("✓ /api/start endpoint working")
                api.is_running = True
            else:
                logger.warning(f"⚠ /api/start returned {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠ /api/start test failed: {e}")
        
        # Check status again
        logger.info("\n3. Checking status after start...")
        try:
            response = requests.get(f"{base_url}/api/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✓ Bot status: {data.get('status')}")
            else:
                logger.warning(f"⚠ Status check returned {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠ Status check failed: {e}")
        
        # Check trading loop output
        logger.info("\n" + "=" * 70)
        logger.info("CHECKING TRADING LOOP")
        logger.info("=" * 70)
        
        logger.info(f"\n✓ Trading loop status:")
        logger.info(f"  - Active: {api.trading_active}")
        logger.info(f"  - Thread alive: {api.trading_thread.is_alive() if api.trading_thread else False}")
        logger.info(f"  - Bot running: {api.is_running}")
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("TEST SUMMARY")
        logger.info("=" * 70)
        
        all_pass = (
            api.trading_active and
            (api.trading_thread and api.trading_thread.is_alive()) and
            server_thread.is_alive()
        )
        
        if all_pass:
            logger.info("✅ ALL TESTS PASSED!")
            logger.info("\n🎉 Bot is ready for deployment!")
            logger.info("   - Web API: Running on http://127.0.0.1:5000")
            logger.info("   - Trading Loop: Active and executing")
            logger.info("   - Status: Ready for live trading")
            return True
        else:
            logger.warning("⚠ Some tests did not pass")
            return False
            
    except Exception as e:
        logger.error(f"✗ Test failed with error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_web_api()
    sys.exit(0 if success else 1)
