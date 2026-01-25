"""Bot Manager - Controls bot lifecycle and modes"""

import time
import threading
import logging
from datetime import datetime
from typing import Optional, Dict

from trading_bot.integrated_bot import IntegratedTradingBot

logger = logging.getLogger(__name__)


class BotManager:
    """Manages bot lifecycle, trading loop, and modes"""
    
    def __init__(self, strategy_name: str = "DefaultStrategy", config_path: Optional[str] = None):
        self.strategy_name = strategy_name
        self.config_path = config_path
        self.bot = IntegratedTradingBot(strategy_name, config_path)
        
        self.is_running = False
        self.is_paused = False
        self.trade_thread: Optional[threading.Thread] = None
        self.stats = {
            'start_time': None,
            'total_trades': 0,
            'total_pnl': 0,
            'daily_sessions': 0
        }
    
    def start(self, live=False):
        """Start the trading bot"""
        if self.is_running:
            logger.warning("[Bot] Already running")
            return
        
        self.is_running = True
        self.stats['start_time'] = datetime.now()
        
        logger.info(f"[Bot] Starting {self.strategy_name} bot (mode: {'LIVE' if live else 'PAPER'})")
        
        # Start trading thread
        self.trade_thread = threading.Thread(
            target=self._trading_loop,
            args=(live,),
            daemon=True
        )
        self.trade_thread.start()
        logger.info("[Bot] Trading thread started")
    
    def stop(self):
        """Stop the trading bot"""
        if not self.is_running:
            logger.warning("[Bot] Not running")
            return
        
        logger.info("[Bot] Stopping bot...")
        self.is_running = False
        
        if self.trade_thread:
            self.trade_thread.join(timeout=5)
        
        # Export session
        self.bot.export_session(f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        logger.info("[Bot] Session exported")
    
    def pause(self):
        """Pause trading (recovery or manual)"""
        self.is_paused = True
        logger.info("[Bot] Trading paused")
    
    def resume(self):
        """Resume trading"""
        self.is_paused = False
        logger.info("[Bot] Trading resumed")
    
    def _trading_loop(self, live: bool):
        """Main trading loop"""
        logger.info("[Loop] Trading loop started")
        
        loop_count = 0
        while self.is_running:
            try:
                loop_count += 1
                
                # Check recovery status
                should_trade, recovery_reason = self.bot.should_trade()
                if not should_trade:
                    if self.is_paused:
                        logger.debug(f"[Loop] Paused: {recovery_reason}")
                    else:
                        logger.warning(f"[Loop] Cannot trade: {recovery_reason}")
                    time.sleep(60)  # Wait before next check
                    continue
                
                # Get position size adjusted for recovery
                base_size = 100
                adjusted_size = self.bot.get_position_size(base_size)
                
                if adjusted_size != base_size:
                    logger.info(f"[Recovery] Position size adjusted: {base_size} -> {adjusted_size:.0f}")
                
                # Simulate trade (replace with your actual strategy)
                self._simulate_trade_decision()
                
                # Check for nightly optimization
                if self.bot.auto_tuner.should_tune():
                    logger.info("[Tuning] Running nightly optimization...")
                    self.bot.auto_tuner.optimize_parameters()
                    logger.info("[Tuning] Optimization complete")
                
                # Sleep before next loop iteration
                time.sleep(60)
                
                if loop_count % 60 == 0:  # Log every hour
                    daily_report = self.bot.generate_daily_report()
                    logger.info(f"[Report] Equity: ${daily_report['equity']:.2f}, "
                              f"Day P&L: ${daily_report['day_pnl']:.2f}, "
                              f"Trades: {daily_report['day_trades']}")
                
            except Exception as e:
                logger.error(f"[Loop] Error in trading loop: {e}", exc_info=True)
                time.sleep(60)
    
    def _simulate_trade_decision(self):
        """Simulate trading decision (replace with your strategy)"""
        # This is a placeholder - replace with your actual trading strategy
        pass
    
    def get_status(self) -> Dict:
        """Get current bot status"""
        recovery_status = self.bot.check_recovery_status()
        return {
            'running': self.is_running,
            'paused': self.is_paused,
            'equity': self.bot.current_equity,
            'day_pnl': self.bot.today_pnl,
            'day_trades': self.bot.today_trades,
            'recovery': recovery_status,
            'start_time': self.stats['start_time'].isoformat() if self.stats['start_time'] else None,
            'uptime': self._get_uptime()
        }
    
    def _get_uptime(self) -> str:
        """Get uptime string"""
        if not self.stats['start_time']:
            return "Not started"
        
        elapsed = datetime.now() - self.stats['start_time']
        hours = int(elapsed.total_seconds() // 3600)
        minutes = int((elapsed.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes}m"
