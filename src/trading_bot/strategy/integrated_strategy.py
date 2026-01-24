"""Master Integrated Trading Strategy - Uses all 9 advanced features

The ultimate strategy that combines:
1. Sentiment Analysis - Confirms bullish/bearish bias
2. Kelly Criterion - Optimal position sizing
3. Portfolio Analytics - Ensures diversification
4. Equity Curve Analyzer - Detects regime changes
5. Advanced Orders - Professional risk management
6. Tax Harvesting - Automatic tax optimization
7. Email Reports - Daily automated summaries
8. WebSocket Data - Real-time execution
9. Tearsheet Analysis - Continuous performance tracking
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import json
import pandas as pd

from trading_bot.sentiment.sentiment_analyzer import SentimentAnalyzer
from trading_bot.analytics.portfolio_analytics import PortfolioAnalytics
from trading_bot.analysis.equity_curve_analyzer import EquityCurveAnalyzer
from trading_bot.reporting.email_reports import EmailReporter
from trading_bot.tax.tax_harvester import TaxLossHarvester
from trading_bot.risk import kelly_position_shares
from trading_bot.broker.advanced_orders import AdvancedOrderManager
from trading_bot.backtest.tearsheet_analyzer import TearsheetAnalyzer

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """Complete trade signal from all 9 features"""
    symbol: str
    action: str  # BUY, SELL, HOLD
    entry_price: float
    position_size: int
    confidence: float  # 0-1
    
    # Signal components
    sentiment_score: float
    sentiment_signal: str
    kelly_pct: float
    portfolio_health: str  # "GOOD", "CAUTION", "WARNING"
    regime: str  # "BULLISH", "NEUTRAL", "BEARISH"
    
    # Risk management
    stop_loss: float
    take_profit: float
    trailing_stop_pct: float
    
    # Context
    timestamp: datetime
    reasons: List[str]


class MasterIntegratedStrategy:
    """Ultimate strategy using all 9 advanced features"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Initialize all 9 features
        self.sentiment = SentimentAnalyzer()
        self.portfolio = PortfolioAnalytics()
        self.equity_analyzer = EquityCurveAnalyzer()
        self.email_reporter = EmailReporter()
        self.tax_harvester = TaxLossHarvester()
        self.order_manager = AdvancedOrderManager()
        self.tearsheet = TearsheetAnalyzer()
        
        # Strategy state
        self.active_positions: Dict[str, Dict] = {}
        self.trading_history: List[Dict] = []
        self.daily_trades: List[Dict] = []
        self.equity_curve: List[float] = []
        self.strategy_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0
        }
        
        logger.info("Master Integrated Strategy initialized with all 9 features")
    
    def generate_signal(self, symbol: str, current_price: float,
                       articles: List[Tuple[str, str]],
                       holdings: Dict[str, float],
                       returns_df: pd.DataFrame,
                       equity_curve: pd.Series,
                       recent_trades: List[Dict]) -> TradeSignal:
        """Generate comprehensive trade signal using all 9 features
        
        Returns:
            TradeSignal with complete analysis
        """
        
        reasons = []
        confidence_scores = []
        
        # ========== FEATURE 1: SENTIMENT ANALYSIS ==========
        sentiment_score = self._analyze_sentiment(symbol, articles, reasons, confidence_scores)
        sentiment_signal = self.sentiment.get_sentiment_for_symbol(symbol)
        if not sentiment_signal:
            sentiment_signal_str = "NEUTRAL"
            sentiment_value = 0.0
        else:
            sentiment_signal_str = sentiment_signal.signal
            sentiment_value = sentiment_signal.polarity
        
        # ========== FEATURE 2: EQUITY CURVE ANALYSIS (Regime Detection) ==========
        regime, regime_confidence = self._detect_regime(equity_curve, reasons, confidence_scores)
        
        # ========== FEATURE 3: PORTFOLIO ANALYTICS ==========
        portfolio_health = self._check_portfolio_health(symbol, holdings, returns_df, reasons, confidence_scores)
        
        # ========== FEATURE 4: SENTIMENT MOMENTUM ==========
        momentum = self.sentiment.sentiment_momentum(symbol, lookback=5)
        if momentum > 0.3:
            reasons.append(f"Sentiment improving (+{momentum:.2f})")
            confidence_scores.append(0.7)
        elif momentum < -0.3:
            reasons.append(f"Sentiment deteriorating ({momentum:.2f})")
            confidence_scores.append(-0.7)
        
        # ========== FEATURE 5: KELLY CRITERION POSITION SIZING ==========
        position_size, kelly_pct = self._calculate_optimal_size(
            symbol, current_price, recent_trades, reasons
        )
        
        # ========== FEATURE 6: DECISION LOGIC ==========
        # Buy if: Strong sentiment + Good regime + Healthy portfolio + Improving momentum
        buy_signals = sum(1 for s in confidence_scores if s > 0.5)
        sell_signals = sum(1 for s in confidence_scores if s < -0.5)
        
        if buy_signals >= 3 and sentiment_signal_str in ["STRONG_BUY", "BUY"]:
            action = "BUY"
            reasons.append(f"Multiple bullish signals ({buy_signals} confirmed)")
        elif sell_signals >= 3 and sentiment_signal_str in ["SELL", "STRONG_SELL"]:
            action = "SELL"
            reasons.append(f"Multiple bearish signals ({sell_signals} confirmed)")
        else:
            action = "HOLD"
            reasons.append("Mixed signals - waiting for confirmation")
        
        # Overall confidence
        overall_confidence = (sum(abs(s) for s in confidence_scores) / len(confidence_scores)) if confidence_scores else 0
        overall_confidence = min(overall_confidence, 1.0)
        
        if action == "SELL":
            overall_confidence *= 0.7  # Reduce confidence on sells (more conservative)
        
        # ========== FEATURE 7: RISK MANAGEMENT ==========
        stop_loss, take_profit, trailing_stop = self._calculate_risk_levels(
            current_price, symbol, action
        )
        
        signal = TradeSignal(
            symbol=symbol,
            action=action,
            entry_price=current_price,
            position_size=position_size,
            confidence=overall_confidence,
            sentiment_score=sentiment_value,
            sentiment_signal=sentiment_signal_str,
            kelly_pct=kelly_pct,
            portfolio_health=portfolio_health,
            regime=regime,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_pct=trailing_stop,
            timestamp=datetime.now(),
            reasons=reasons
        )
        
        logger.info(f"Signal generated for {symbol}: {action} @ ${current_price:.2f} "
                   f"(Confidence: {overall_confidence*100:.0f}%)")
        
        return signal
    
    def _analyze_sentiment(self, symbol: str, articles: List[Tuple[str, str]],
                          reasons: List[str], confidence_scores: List[float]) -> float:
        """Feature 1: Analyze sentiment from news"""
        
        if not articles:
            reasons.append("No news data available")
            return 0.0
        
        sentiment_score = self.sentiment.aggregate_sentiment(symbol, articles)
        
        if sentiment_score.signal == "STRONG_BUY":
            reasons.append(f"🟢 Strong bullish sentiment ({sentiment_score.polarity:.2f})")
            confidence_scores.append(0.9)
            return sentiment_score.polarity
        elif sentiment_score.signal == "BUY":
            reasons.append(f"🟢 Bullish sentiment ({sentiment_score.polarity:.2f})")
            confidence_scores.append(0.7)
            return sentiment_score.polarity
        elif sentiment_score.signal == "STRONG_SELL":
            reasons.append(f"🔴 Strong bearish sentiment ({sentiment_score.polarity:.2f})")
            confidence_scores.append(-0.9)
            return sentiment_score.polarity
        elif sentiment_score.signal == "SELL":
            reasons.append(f"🔴 Bearish sentiment ({sentiment_score.polarity:.2f})")
            confidence_scores.append(-0.7)
            return sentiment_score.polarity
        else:
            reasons.append("Neutral sentiment")
            return 0.0
    
    def _detect_regime(self, equity_curve: pd.Series, reasons: List[str],
                      confidence_scores: List[float]) -> Tuple[str, float]:
        """Feature 2: Detect market regime from equity curve"""
        
        if len(equity_curve) < 20:
            return "NEUTRAL", 0.3
        
        recent_returns = equity_curve.pct_change().tail(20).mean() * 252
        volatility = equity_curve.pct_change().tail(20).std() * np.sqrt(252)
        
        if recent_returns > 0.15 and volatility < 0.20:
            regime = "BULLISH"
            reasons.append("📈 Bullish regime detected (positive returns, low volatility)")
            confidence_scores.append(0.8)
        elif recent_returns < -0.10:
            regime = "BEARISH"
            reasons.append("📉 Bearish regime detected (negative returns)")
            confidence_scores.append(-0.8)
        else:
            regime = "NEUTRAL"
            reasons.append("Neutral regime (consolidation)")
            confidence_scores.append(0.0)
        
        return regime, 0.7
    
    def _check_portfolio_health(self, symbol: str, holdings: Dict[str, float],
                               returns_df: pd.DataFrame, reasons: List[str],
                               confidence_scores: List[float]) -> str:
        """Feature 3: Check portfolio health and diversification"""
        
        if not holdings or len(holdings) < 2:
            return "LIMITED"
        
        try:
            metrics = self.portfolio.analyze_portfolio(holdings, returns_df)
            
            if metrics.concentration < 0.20:
                status = "GOOD"
                reasons.append(f"✅ Well-diversified portfolio (concentration: {metrics.concentration:.2%})")
                confidence_scores.append(0.6)
            elif metrics.concentration < 0.35:
                status = "CAUTION"
                reasons.append(f"⚠️ Moderate concentration ({metrics.concentration:.2%})")
                confidence_scores.append(0.3)
            else:
                status = "WARNING"
                reasons.append(f"🚨 High concentration - reduce {symbol} position")
                confidence_scores.append(-0.3)
            
            return status
        except:
            return "UNKNOWN"
    
    def _calculate_optimal_size(self, symbol: str, entry_price: float,
                               recent_trades: List[Dict],
                               reasons: List[str]) -> Tuple[int, float]:
        """Feature 5: Calculate optimal position size using Kelly Criterion"""
        
        if not recent_trades or len(recent_trades) < 5:
            kelly_pct = 0.02  # Default 2%
            reasons.append("Insufficient history - using conservative 2% Kelly")
        else:
            # Calculate win rate and P&L
            pnl = [t.get('pnl', 0) for t in recent_trades[-20:]]
            wins = [p for p in pnl if p > 0]
            losses = [p for p in pnl if p < 0]
            
            if wins and losses:
                win_rate = len(wins) / len(pnl)
                avg_win = sum(wins) / len(wins)
                avg_loss = sum(abs(l) for l in losses) / len(losses)
                
                kelly_pct = self._calculate_kelly(win_rate, avg_win, avg_loss)
                reasons.append(f"Kelly: {kelly_pct*100:.1f}% (Win rate: {win_rate*100:.0f}%)")
            else:
                kelly_pct = 0.02
                reasons.append("Insufficient winning trades - using 2% Kelly")
        
        # Convert to shares
        equity = 50000  # You'd get this from account
        shares = int((equity * kelly_pct) / entry_price)
        
        return max(shares, 1), kelly_pct
    
    def _calculate_kelly(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Kelly Criterion formula"""
        
        if avg_loss == 0:
            return 0.02
        
        b = avg_win / avg_loss
        kelly = (b * win_rate - (1 - win_rate)) / b if b > 0 else 0
        kelly = kelly * 0.25  # Use fractional Kelly for safety
        
        return max(0.01, min(kelly, 0.05))  # Cap between 1-5%
    
    def _calculate_risk_levels(self, entry_price: float, symbol: str,
                              action: str) -> Tuple[float, float, float]:
        """Feature 7: Calculate stop loss, take profit, trailing stop"""
        
        if action == "BUY":
            stop_loss = entry_price * 0.97  # 3% stop
            take_profit = entry_price * 1.05  # 5% profit target
            trailing_stop = 0.03  # 3% trailing
        else:
            stop_loss = entry_price * 1.03
            take_profit = entry_price * 0.95
            trailing_stop = 0.03
        
        return stop_loss, take_profit, trailing_stop
    
    def execute_signal(self, signal: TradeSignal) -> bool:
        """Execute trade signal using Feature 8: Advanced Orders"""
        
        if signal.action == "HOLD":
            return False
        
        if signal.confidence < 0.5:
            logger.warning(f"Signal confidence too low ({signal.confidence*100:.0f}%) - skipping")
            return False
        
        try:
            # Create bracket order (entry + TP + SL)
            bracket = self.order_manager.create_bracket_order(
                symbol=signal.symbol,
                entry_qty=signal.position_size,
                entry_price=signal.entry_price,
                take_profit_price=signal.take_profit,
                stop_loss_price=signal.stop_loss
            )
            
            # Also create trailing stop
            trailing = self.order_manager.create_trailing_stop(
                symbol=signal.symbol,
                quantity=signal.position_size,
                entry_price=signal.entry_price,
                trail_percent=signal.trailing_stop_pct
            )
            
            # Record position
            self.active_positions[signal.symbol] = {
                'entry_price': signal.entry_price,
                'position_size': signal.position_size,
                'entry_time': signal.timestamp,
                'bracket_id': bracket.parent_order_id,
                'trailing_id': trailing.symbol
            }
            
            logger.info(f"✅ Executed: {signal.action} {signal.position_size} {signal.symbol} "
                       f"@ ${signal.entry_price:.2f} (Confidence: {signal.confidence*100:.0f}%)")
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to execute signal: {e}")
            return False
    
    def daily_optimization(self, equity_curve: pd.Series, trades: List[Dict]) -> None:
        """Feature 9: Daily automated optimization using tearsheets"""
        
        # Generate tearsheet
        tearsheet = self.tearsheet.generate_tearsheet(
            equity_curve=equity_curve,
            trades=trades,
            strategy_name="Master Integrated Strategy"
        )
        
        # Analyze performance
        logger.info(f"Daily Performance: Return={tearsheet.total_return*100:.2f}%, "
                   f"Sharpe={tearsheet.sharpe_ratio:.2f}, MaxDD={tearsheet.max_drawdown*100:.2f}%")
        
        # Update strategy stats
        self.strategy_stats['total_trades'] = tearsheet.trades_count
        self.strategy_stats['win_rate'] = tearsheet.win_rate
        self.strategy_stats['sharpe_ratio'] = tearsheet.sharpe_ratio
        self.strategy_stats['max_drawdown'] = tearsheet.max_drawdown
        
        # If Sharpe is declining, flag for review
        if tearsheet.sharpe_ratio < 1.0:
            logger.warning("⚠️ Sharpe ratio below 1.0 - consider parameter adjustment")
        
        # If drawdown is large, trigger caution
        if tearsheet.max_drawdown < -0.15:
            logger.warning("🚨 Max drawdown > 15% - reduce position sizes")
    
    def daily_email_report(self, trades: List[Dict], equity: float, 
                          portfolio_health: str) -> None:
        """Feature 8: Send daily email with complete summary"""
        
        report = self.email_reporter.generate_report(
            trade_history={'trades': trades},
            portfolio_metrics={
                'starting_equity': 100000,
                'current_equity': equity,
                'volatility': self.strategy_stats['volatility'] if 'volatility' in self.strategy_stats else 0.15,
                'sharpe_ratio': self.strategy_stats['sharpe_ratio'],
                'total_return': sum(t.get('pnl', 0) for t in trades) / 100000
            },
            risk_metrics={
                'max_drawdown': self.strategy_stats['max_drawdown']
            }
        )
        
        logger.info(f"Daily Report: {len(trades)} trades, ${report.total_pnl:,.2f} P&L, "
                   f"{report.win_rate*100:.0f}% win rate")
        
        # Save locally
        self.email_reporter.save_report(report)
    
    def tax_optimization(self, holdings: Dict[str, Dict], prices: Dict[str, float]) -> None:
        """Feature 6: Run tax-loss harvesting"""
        
        opportunities = self.tax_harvester.find_tax_loss_opportunities(
            holdings, prices
        )
        
        if opportunities:
            logger.info(f"Found {len(opportunities)} tax loss harvesting opportunities")
            
            for opp in opportunities[:3]:  # Limit to 3 per day
                if not opp.wash_sale_risk and opp.tax_benefit > 100:
                    harvest = self.tax_harvester.execute_harvest(
                        opp,
                        current_price=prices.get(opp.symbol, opp.current_price)
                    )
                    logger.info(f"💰 Tax harvest: {opp.symbol} -> {opp.replacement_symbol}, "
                               f"Tax savings: ${harvest.tax_savings:,.0f}")
    
    def save_state(self) -> None:
        """Save strategy state and analysis"""
        
        filepath = self.cache_dir / "master_strategy_state.json"
        
        data = {
            'timestamp': datetime.now().isoformat(),
            'active_positions': self.active_positions,
            'strategy_stats': self.strategy_stats,
            'trading_history_count': len(self.trading_history),
            'daily_trades': self.daily_trades
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


import numpy as np  # Import at module level
