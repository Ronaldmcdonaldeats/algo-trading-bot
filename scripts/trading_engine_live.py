#!/usr/bin/env python3
"""
Live Trading Engine - Gen 364 Strategy
Monitors markets, generates buy/sell signals, and executes via Alpaca
Runs on Oracle Cloud 24/7 during market hours
"""
import os
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
import yaml
import pandas as pd
import numpy as np
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AlpacaTrader:
    """Interface with Alpaca API for live paper trading"""
    
    def __init__(self):
        self.api_key = os.getenv('APCA_API_KEY_ID')
        self.api_secret = os.getenv('APCA_API_SECRET_KEY')
        self.base_url = os.getenv('APCA_API_BASE_URL', 'https://paper-api.alpaca.markets')
        self.headers = {
            'APCA-API-KEY-ID': self.api_key,
            'APCA-API-SECRET-KEY': self.api_secret,
        }
        self.mode = os.getenv('MODE', 'paper')
        logger.info(f"✓ Alpaca Trader initialized (Mode: {self.mode})")
    
    def get_account(self) -> Dict:
        """Get account info"""
        try:
            resp = requests.get(f"{self.base_url}/v2/account", headers=self.headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"✗ Failed to get account: {e}")
            return {}
    
    def get_positions(self) -> List[Dict]:
        """Get current positions"""
        try:
            resp = requests.get(f"{self.base_url}/v2/positions", headers=self.headers)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"✗ Failed to get positions: {e}")
            return []
    
    def submit_order(self, symbol: str, qty: int, side: str, order_type: str = 'market') -> Dict:
        """Submit buy/sell order to Alpaca"""
        try:
            data = {
                'symbol': symbol,
                'qty': qty,
                'side': side,
                'type': order_type,
                'time_in_force': 'day',
            }
            resp = requests.post(f"{self.base_url}/v2/orders", headers=self.headers, json=data)
            resp.raise_for_status()
            order = resp.json()
            logger.info(f"✓ ORDER SUBMITTED: {side.upper()} {qty} {symbol} @ market")
            return order
        except Exception as e:
            logger.error(f"✗ Failed to submit order: {e}")
            return {}
    
    def get_bars(self, symbol: str, timeframe: str = '5min', limit: int = 100) -> pd.DataFrame:
        """Get historical bars (OHLCV data)"""
        try:
            resp = requests.get(
                f"{self.base_url}/v2/stocks/{symbol}/bars",
                headers=self.headers,
                params={'timeframe': timeframe, 'limit': limit}
            )
            resp.raise_for_status()
            data = resp.json()
            if 'bars' in data:
                return pd.DataFrame(data['bars'])
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"✗ Failed to get bars for {symbol}: {e}")
            return pd.DataFrame()


class Gen364Strategy:
    """Gen 364 Trading Strategy - Ultra Ensemble Model"""
    
    def __init__(self, config_file: str = '/app/config/evolved_strategy_gen364.yaml'):
        self.entry_threshold = 0.7756
        self.profit_target = 0.1287  # 12.87%
        self.stop_loss = 0.0927      # 9.27%
        self.position_size_pct = 0.05
        self.max_positions = 20
        
        # Load config if exists
        if Path(config_file).exists():
            try:
                with open(config_file, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    self.entry_threshold = config.get('entry_threshold', self.entry_threshold)
                    self.profit_target = config.get('profit_target', self.profit_target)
                    self.stop_loss = config.get('stop_loss', self.stop_loss)
                    self.position_size_pct = config.get('position_size_pct', self.position_size_pct)
                    logger.info(f"✓ Strategy loaded from {config_file}")
            except Exception as e:
                logger.warning(f"Could not load config, using defaults: {e}")
        
        logger.info(f"Gen 364 Strategy Initialized:")
        logger.info(f"  Entry Threshold: {self.entry_threshold:.4f}")
        logger.info(f"  Profit Target: {self.profit_target*100:.2f}%")
        logger.info(f"  Stop Loss: {self.stop_loss*100:.2f}%")
    
    def calculate_signal(self, df: pd.DataFrame) -> float:
        """
        Calculate trading signal (-1 to 1)
        Uses momentum, trend, and mean reversion indicators
        """
        if df.empty or len(df) < 20:
            return 0.0
        
        try:
            close = df['close'].values
            
            # Momentum (recent returns)
            returns = (close[-1] - close[-5]) / close[-5]
            momentum = np.tanh(returns * 10)  # Normalize to -1 to 1
            
            # Trend (20-day MA crossover)
            ma20 = pd.Series(close).rolling(20).mean().iloc[-1]
            ma5 = pd.Series(close).rolling(5).mean().iloc[-1]
            trend = 1.0 if ma5 > ma20 else -0.5
            
            # Mean reversion (Bollinger Bands)
            sma = pd.Series(close).rolling(20).mean().iloc[-1]
            std = pd.Series(close).rolling(20).std().iloc[-1]
            zscore = (close[-1] - sma) / std if std > 0 else 0
            reversion = -np.tanh(zscore)  # Overbought → sell, oversold → buy
            
            # Combine signals (weighted ensemble)
            signal = (momentum * 0.4 + trend * 0.4 + reversion * 0.2)
            signal = np.clip(signal, -1.0, 1.0)
            
            return signal
        except Exception as e:
            logger.error(f"Error calculating signal: {e}")
            return 0.0
    
    def generate_trade_signal(self, symbol: str, df: pd.DataFrame, current_price: float) -> Optional[str]:
        """
        Generate BUY/SELL/HOLD signal
        Returns: 'buy', 'sell', or None
        """
        if df.empty:
            return None
        
        signal = self.calculate_signal(df)
        
        # BUY signal: strong momentum + signal above threshold
        if signal > self.entry_threshold:
            logger.info(f"📈 BUY SIGNAL: {symbol} (signal={signal:.4f}, price=${current_price:.2f})")
            return 'buy'
        
        # SELL signal: strong downward + signal below negative threshold
        elif signal < -self.entry_threshold:
            logger.info(f"📉 SELL SIGNAL: {symbol} (signal={signal:.4f}, price=${current_price:.2f})")
            return 'sell'
        
        return None


class DiscordNotifier:
    """Send trade notifications to Discord"""
    
    def __init__(self):
        self.webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        if not self.webhook_url:
            logger.warning("⚠️  DISCORD_WEBHOOK_URL not set - notifications disabled")
    
    def send_message(self, title: str, message: str, color: int = 0x00FF00):
        """Send embed message to Discord"""
        if not self.webhook_url:
            return
        
        try:
            data = {
                "embeds": [{
                    "title": title,
                    "description": message,
                    "color": color,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            resp = requests.post(self.webhook_url, json=data, timeout=5)
            resp.raise_for_status()
            logger.debug(f"✓ Discord notification sent")
        except Exception as e:
            logger.error(f"✗ Discord notification failed: {e}")
    
    def send_trade(self, action: str, symbol: str, qty: int, price: float, signal: float):
        """Notify of trade execution"""
        color = 0x00FF00 if action == 'BUY' else 0xFF0000
        title = f"🤖 {action} Signal - {symbol}"
        message = f"**Action**: {action}\n**Symbol**: {symbol}\n**Quantity**: {qty}\n**Price**: ${price:.2f}\n**Signal**: {signal:.4f}"
        self.send_message(title, message, color)
    
    def send_heartbeat(self, account_value: str, positions_count: int):
        """Send periodic status update"""
        title = "💓 Trading Bot Heartbeat"
        message = f"**Status**: 🟢 RUNNING\n**Account Value**: {account_value}\n**Positions**: {positions_count}\n**Timestamp**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EST"
        self.send_message(title, message, 0x0099FF)


class TradingEngine:
    """Main trading engine - coordinates strategy, trading, and monitoring"""
    
    def __init__(self):
        self.alpaca = AlpacaTrader()
        self.strategy = Gen364Strategy()
        self.discord = DiscordNotifier()
        self.symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA']  # Core watchlist
        self.heartbeat_interval = 3600  # 1 hour
        self.last_heartbeat = time.time()
    
    def is_market_open(self) -> bool:
        """Check if market is open (9:30 AM - 4:00 PM EST)"""
        now = datetime.now()
        
        # Get EST time (UTC-5 in winter, UTC-4 in summer)
        est_offset = -4 if now.astimezone().dst() else -5
        est_time = now.astimezone().replace(tzinfo=None) + timedelta(hours=est_offset - datetime.now().astimezone().utcoffset().total_seconds() / 3600)
        
        hour = est_time.hour
        minute = est_time.minute
        weekday = est_time.weekday()
        
        # Market hours: 9:30 AM - 4:00 PM, Mon-Fri
        is_weekday = weekday < 5
        is_trading_hours = (hour > 9 and hour < 16) or (hour == 9 and minute >= 30)
        
        return is_weekday and is_trading_hours
    
    def run(self):
        """Main trading loop"""
        logger.info("=" * 60)
        logger.info("🚀 LIVE TRADING ENGINE STARTED")
        logger.info("=" * 60)
        logger.info(f"Strategy: Gen 364 (Ultra Ensemble)")
        logger.info(f"Mode: {self.alpaca.mode}")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info("=" * 60)
        
        iteration = 0
        while True:
            iteration += 1
            now = datetime.now()
            
            try:
                # Check market status
                market_open = self.is_market_open()
                status = "🟢 OPEN" if market_open else "🔴 CLOSED"
                logger.info(f"\n[{now.strftime('%H:%M:%S')}] Market {status} | Iteration #{iteration}")
                
                if not market_open:
                    logger.info("⏸️  Market closed - skipping analysis")
                    time.sleep(60)
                    continue
                
                # Get account info
                account = self.alpaca.get_account()
                if not account:
                    logger.warning("Could not fetch account info, retrying...")
                    time.sleep(30)
                    continue
                
                cash = float(account.get('cash', 0))
                portfolio_value = float(account.get('portfolio_value', 0))
                logger.info(f"💰 Account: ${portfolio_value:,.2f} | Cash: ${cash:,.2f}")
                
                # Send heartbeat every hour
                if time.time() - self.last_heartbeat > self.heartbeat_interval:
                    positions = self.alpaca.get_positions()
                    self.discord.send_heartbeat(f"${portfolio_value:,.2f}", len(positions))
                    self.last_heartbeat = time.time()
                
                # Analyze each symbol
                trades_today = 0
                for symbol in self.symbols:
                    try:
                        # Get market data
                        df = self.alpaca.get_bars(symbol, timeframe='5min', limit=100)
                        if df.empty:
                            continue
                        
                        # Convert to correct format if needed
                        if 't' in df.columns:
                            df = df.rename(columns={'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
                        
                        current_price = df['close'].iloc[-1] if 'close' in df.columns else 0
                        
                        # Generate signal
                        signal = self.strategy.generate_trade_signal(symbol, df, current_price)
                        
                        if signal == 'buy':
                            # Calculate position size
                            qty = max(1, int((cash * self.strategy.position_size_pct) / current_price))
                            order = self.alpaca.submit_order(symbol, qty, 'buy')
                            if order:
                                trades_today += 1
                                self.discord.send_trade('BUY', symbol, qty, current_price, self.strategy.calculate_signal(df))
                        
                        elif signal == 'sell':
                            # Get current position
                            positions = self.alpaca.get_positions()
                            for pos in positions:
                                if pos.get('symbol') == symbol:
                                    qty = int(pos.get('qty', 0))
                                    order = self.alpaca.submit_order(symbol, qty, 'sell')
                                    if order:
                                        trades_today += 1
                                        self.discord.send_trade('SELL', symbol, qty, current_price, self.strategy.calculate_signal(df))
                    
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                
                logger.info(f"✓ Trades executed: {trades_today} | Next check in 5 minutes")
                time.sleep(300)  # Check every 5 minutes
            
            except KeyboardInterrupt:
                logger.info("\n✓ Trading engine stopped by user")
                break
            except Exception as e:
                logger.error(f"✗ Unexpected error: {e}")
                time.sleep(30)


if __name__ == '__main__':
    engine = TradingEngine()
    engine.run()
