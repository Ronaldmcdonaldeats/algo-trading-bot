"""Complete Integration Example - Using all three new systems together"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from trading_bot.trading.trade_journal import TradeJournal, JournalEntry
from trading_bot.risk.drawdown_recovery import DrawdownRecoveryManager
from trading_bot.learn.auto_tuning import AutoTuningSystem, ParameterSet
from trading_bot.learn.ensemble import ExponentialWeightsEnsemble
from trading_bot.options.strategies import (
    CoveredCallStrategy, ProtectiveputStrategy, BullCallSpreadStrategy,
    GreeksCalculator, OptionType, OptionsAnalyzer
)
from trading_bot.strategy.atr_breakout import AtrBreakoutStrategy
from trading_bot.strategy.macd_volume_momentum import MacdVolumeMomentumStrategy
from trading_bot.strategy.rsi_mean_reversion import RsiMeanReversionStrategy


class IntegratedTradingBot:
    """
    Complete trading bot with:
    - Multi-strategy ensemble learning (ATR Breakout, MACD Volume Momentum, RSI Mean Reversion)
    - Trade journaling and analytics
    - Drawdown protection and recovery
    - Auto-parameter tuning
    - Options strategies
    """
    
    def __init__(self, strategy_name: str, config_path: Optional[str] = None):
        """Initialize integrated bot with multi-strategy ensemble"""
        self.strategy_name = strategy_name
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Initialize multi-strategy ensemble
        self.strategies = {
            "atr_breakout": AtrBreakoutStrategy(
                atr_period=14,
                breakout_lookback=20,
                atr_mult=1.0
            ),
            "macd_volume": MacdVolumeMomentumStrategy(
                macd_fast=12,
                macd_slow=26,
                macd_signal=9,
                vol_sma=20,
                vol_mult=1.0
            ),
            "rsi_mean_reversion": RsiMeanReversionStrategy(
                rsi_period=14,
                entry_oversold=30.0,
                exit_rsi=50.0
            )
        }
        
        self.ensemble = ExponentialWeightsEnsemble.uniform(list(self.strategies.keys()), eta=0.3)
        self.last_ensemble_weights = {}
        self.last_strategy_signals = {}
        
        # Initialize other systems
        self.journal = TradeJournal(db_path=self.config['journal_db'])
        self.recovery_manager = DrawdownRecoveryManager(
            daily_loss_threshold=self.config['daily_loss_threshold'],
            portfolio_loss_threshold=self.config['portfolio_loss_threshold'],
        )
        self.auto_tuner = AutoTuningSystem(
            tune_schedule=self.config['tune_schedule']
        )
        
        # State tracking
        self.current_equity = self.config['starting_equity']
        self.peak_equity = self.config['starting_equity']  # For recovery tracking
        self.start_equity = self.config['starting_equity']  # For recovery tracking
        self.open_positions = {}
        self.today_pnl = 0
        self.today_trades = 0
        
        print(f"[OK] Initialized {strategy_name} bot with multi-strategy ensemble")
        print(f"[OK] Strategies: {', '.join(self.strategies.keys())}")
        print(f"[OK] Initial ensemble weights: {self.ensemble.normalized()}")
    
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration"""
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                return json.load(f)
        
        # Default configuration
        return {
            'starting_equity': 100000,
            'journal_db': 'trade_journal.db',
            'daily_loss_threshold': 0.05,
            'portfolio_loss_threshold': 0.20,
            'tune_schedule': 'DAILY',
            'param_bounds': {
                'sma_fast': (10, 50),
                'sma_slow': (50, 200),
                'rsi_threshold': (20, 50),
            }
        }
    
    def should_trade(self) -> Tuple[bool, str]:
        """Check if we should trade (recovery manager)"""
        is_trading, reason = self.recovery_manager.should_trade(
            current_equity=self.current_equity,
            peak_equity=self.peak_equity,
            start_equity=self.start_equity
        )
        return is_trading, reason
    
    def evaluate_all_strategies(self, df) -> Dict:
        """Evaluate all strategies and get ensemble decision
        
        Returns:
            {
                'ensemble_signal': final signal,
                'ensemble_confidence': final confidence,
                'strategy_signals': {name: signal, ...},
                'strategy_confidences': {name: confidence, ...},
                'ensemble_weights': {name: weight, ...},
                'strategy_explanations': {name: explanation, ...}
            }
        """
        import pandas as pd
        
        # Evaluate each strategy
        strategy_outputs = {}
        for name, strategy in self.strategies.items():
            try:
                output = strategy.evaluate(df)
                strategy_outputs[name] = output
                self.last_strategy_signals[name] = int(output.signal)
            except Exception as e:
                print(f"[ERROR] {name} evaluation failed: {e}")
                strategy_outputs[name] = None
        
        # Get ensemble decision
        valid_outputs = {k: v for k, v in strategy_outputs.items() if v is not None}
        
        if not valid_outputs:
            return {
                'ensemble_signal': 0,
                'ensemble_confidence': 0.0,
                'strategy_signals': {},
                'strategy_confidences': {},
                'ensemble_weights': self.ensemble.normalized(),
                'strategy_explanations': {}
            }
        
        decision = self.ensemble.decide(valid_outputs)
        
        # Update ensemble with rewards based on signals
        # Simple reward: +1 for agreeing with ensemble, -1 for disagreeing
        rewards = {}
        for name, output in valid_outputs.items():
            if output.signal == decision.signal and decision.signal != 0:
                rewards[name] = 1.0  # Good agreement
            elif output.signal != decision.signal:
                rewards[name] = 0.0  # Disagreement
            else:
                rewards[name] = 0.5  # Neutral
        
        if rewards:
            self.ensemble.update(rewards)
            self.last_ensemble_weights = self.ensemble.normalized()
        
        # Collect strategy info
        strategy_confidences = {}
        strategy_signals = {}
        strategy_explanations = {}
        
        for name, output in valid_outputs.items():
            strategy_signals[name] = int(output.signal)
            strategy_confidences[name] = float(output.confidence)
            strategy_explanations[name] = output.explanation
        
        return {
            'ensemble_signal': int(decision.signal),
            'ensemble_confidence': float(decision.confidence),
            'strategy_signals': strategy_signals,
            'strategy_confidences': strategy_confidences,
            'ensemble_weights': decision.weights,
            'strategy_explanations': strategy_explanations
        }
    
    def get_position_size(self, base_size: float) -> float:
        """Get position size adjusted for recovery phase"""
        multiplier = self.recovery_manager.get_position_size_multiplier(
            current_equity=self.current_equity,
            start_equity=self.start_equity
        )
        return base_size * multiplier
    
    def record_trade(self, symbol: str, entry_price: float, exit_price: float,
                    quantity: int, side: str, strategy: str, tags: List[str] = None):
        """Record trade in journal"""
        
        pnl = (exit_price - entry_price) * quantity if side == 'long' else (entry_price - exit_price) * quantity
        pnl_pct = (pnl / (entry_price * quantity)) * 100 if entry_price > 0 else 0
        
        entry = JournalEntry(
            trade_id=f"{symbol}_{datetime.now().timestamp()}",
            symbol=symbol,
            entry_price=entry_price,
            exit_price=exit_price,
            quantity=quantity,
            side=side,
            entry_time=datetime.now() - timedelta(hours=1),  # Simplified
            exit_time=datetime.now(),
            profit_loss=pnl,
            profit_loss_pct=pnl_pct,
            strategy=strategy,
            tags=tags or [],
            notes="",
            ab_group=None
        )
        
        self.journal.add_trade(entry)
        
        # Update equity
        self.current_equity += pnl
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
        self.today_pnl += pnl
        self.today_trades += 1
        
        # Record for auto-tuning
        self.auto_tuner.record_performance(
            params={},  # Simplified
            sharpe=0,
            total_return=pnl_pct,
            max_dd=0,
            win_rate=0.5,
            pf=1.0,
            num_trades=self.today_trades
        )
        
        print(f"[Trade] Trade recorded: {symbol} | P&L: ${pnl:.2f} ({pnl_pct:.1f}%)")
    
    def check_recovery_status(self) -> Dict:
        """Get current recovery status"""
        status = self.recovery_manager.get_recovery_status()
        return status
    
    def generate_daily_report(self) -> Dict:
        """Generate end-of-day report"""
        
        # Recovery status
        recovery = self.check_recovery_status()
        
        # Journal analytics
        today_trades = self.journal.analyze_by_symbol(None)  # All symbols
        
        # Auto-tuning status
        should_tune = self.auto_tuner.should_tune()
        if should_tune:
            reason = "Time for optimization"
        else:
            reason = "Not yet time to optimize"
        
        # Options recommendations (if applicable)
        covered_calls = []
        
        report = {
            'date': datetime.now().isoformat(),
            'equity': self.current_equity,
            'day_pnl': self.today_pnl,
            'day_trades': self.today_trades,
            'recovery_status': recovery,
            'journal_summary': today_trades,
            'auto_tuning': {
                'should_tune': should_tune,
                'reason': reason,
            },
            'options_opportunities': {
                'covered_calls': covered_calls,
            }
        }
        
        return report
    
    def analyze_winning_patterns(self) -> Dict:
        """Find winning patterns in trade journal"""
        patterns = self.journal.find_winning_patterns()
        return patterns
    
    def export_session(self, filepath: str):
        """Export all session data"""
        report = {
            'strategy': self.strategy_name,
            'final_equity': self.current_equity,
            'total_trades': self.today_trades,
            'daily_pnl': self.today_pnl,
            'journal_export': self.journal.export_journal(),
            'recovery_metrics': self.recovery_manager.get_recovery_metrics(),
            'tuning_history': self.auto_tuner.get_update_history(),
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"[OK] Session exported to {filepath}")


# Example usage
if __name__ == "__main__":
    # Initialize bot
    bot = IntegratedTradingBot(
        strategy_name="RSI_Mean_Reversion",
        config_path="configs/integrated_bot_config.json"
    )
    
    print("\n" + "="*60)
    print("INTEGRATED TRADING BOT - ALL SYSTEMS ACTIVE")
    print("="*60)
    
    # Check if we should trade
    should_trade, reason = bot.should_trade()
    print(f"\n[Check] Should Trade: {should_trade} ({reason})")
    
    # Get adjusted position size (for recovery phase)
    base_size = 100
    adjusted_size = bot.get_position_size(base_size)
    print(f"[Size] Position Size: {base_size} -> {adjusted_size:.0f} (adjusted for recovery)")
    
    # Simulate a trade
    print("\n" + "-"*60)
    print("SIMULATING TRADES")
    print("-"*60)
    
    bot.record_trade(
        symbol="AAPL",
        entry_price=150.00,
        exit_price=152.50,
        quantity=100,
        side="long",
        strategy="RSI_Mean_Reversion",
        tags=["bullish", "tech"]
    )
    
    bot.record_trade(
        symbol="GOOGL",
        entry_price=140.00,
        exit_price=139.50,
        quantity=50,
        side="long",
        strategy="RSI_Mean_Reversion",
        tags=["loss", "tech"]
    )
    
    bot.record_trade(
        symbol="MSFT",
        entry_price=380.00,
        exit_price=385.00,
        quantity=75,
        side="long",
        strategy="RSI_Mean_Reversion",
        tags=["win", "tech"]
    )
    
    # Check recovery status
    print("\n" + "-"*60)
    print("RECOVERY STATUS")
    print("-"*60)
    recovery_status = bot.check_recovery_status()
    print(f"In Recovery: {recovery_status['in_recovery']}")
    print(f"Trading Paused: {recovery_status['trading_paused']}")
    if recovery_status['current_event']:
        print(f"Current Event: {recovery_status['current_event']}")
    
    # Generate daily report
    print("\n" + "-"*60)
    print("DAILY REPORT")
    print("-"*60)
    report = bot.generate_daily_report()
    print(f"Equity: ${report['equity']:.2f}")
    print(f"Day P&L: ${report['day_pnl']:.2f}")
    print(f"Trades: {report['day_trades']}")
    
    # Analyze patterns
    print("\n" + "-"*60)
    print("WINNING PATTERNS")
    print("-"*60)
    patterns = bot.analyze_winning_patterns()
    if isinstance(patterns, list):
        print(f"Total patterns found: {len(patterns)}")
    else:
        print(f"Total patterns found: {len(patterns.get('patterns', []))}")
    
    # Export session
    bot.export_session("session_report.json")
    
    print("\n[OK] Integration test completed!")
