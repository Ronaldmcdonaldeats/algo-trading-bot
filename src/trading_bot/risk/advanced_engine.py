"""Integration module for advanced risk management features."""

from typing import Dict, List, Any, Tuple
import numpy as np
from datetime import datetime

from trading_bot.risk.portfolio_risk import PortfolioRiskManager
from trading_bot.risk.position_sizing import PositionSizer
from trading_bot.analysis.multi_timeframe import MultiTimeframeAnalyzer, Signal


class AdvancedRiskEngine:
    """Unified engine combining portfolio risk, position sizing, and multi-timeframe analysis."""
    
    def __init__(self, account_size: float, max_risk_per_trade: float = 0.02):
        self.account_size = account_size
        self.max_risk_per_trade = max_risk_per_trade
        
        self.risk_manager = PortfolioRiskManager(confidence_level=0.95, lookback_days=252)
        self.position_sizer = PositionSizer(account_size, max_risk_per_trade)
        self.mtf_analyzer = MultiTimeframeAnalyzer()
        
        self.positions = {}
        self.trade_history = []
    
    def generate_trade_signal(
        self,
        symbol: str,
        price: float,
        signals_by_timeframe: Dict[str, Dict[str, float]],
        entry_price: float = None,
        stop_loss: float = None,
        historical_performance: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive trade signal combining all analysis.
        
        Args:
            symbol: Stock symbol
            price: Current price
            signals_by_timeframe: {
                '1m': {'sma20': x, 'sma50': x, 'rsi': x, 'macd': x, 'volume': x, 'avg_volume': x},
                '5m': {...},
                ...
            }
            entry_price: Proposed entry price
            stop_loss: Proposed stop loss
            historical_performance: {win_rate, avg_win, avg_loss, volatility}
        
        Returns:
            Comprehensive signal with size, risk, confluence score, etc.
        """
        
        # 1. Multi-timeframe analysis
        mtf_signals = {}
        for tf, data in signals_by_timeframe.items():
            mtf_signals[tf] = self.mtf_analyzer.analyze_timeframe(
                symbol=symbol,
                timeframe=tf,
                price=price,
                sma_20=data.get('sma20', price),
                sma_50=data.get('sma50', price),
                sma_200=data.get('sma200', price),
                rsi=data.get('rsi', 50),
                macd=data.get('macd', 0),
                volume=data.get('volume', 0),
                avg_volume=data.get('avg_volume', 1)
            )
        
        confluence = self.mtf_analyzer.calculate_confluence(symbol, mtf_signals)
        
        # 2. Position sizing
        position_size = self._calculate_position_size(
            symbol, price, stop_loss, confluence, historical_performance
        )
        
        # 3. Risk assessment
        risk_metrics = {
            'entry_price': entry_price or price,
            'stop_loss': stop_loss,
            'max_loss': abs((entry_price or price) - (stop_loss or price)) * position_size if stop_loss else 0,
            'risk_pct_account': (abs((entry_price or price) - (stop_loss or price)) * position_size / self.account_size) if stop_loss else 0
        }
        
        # 4. Recommendation
        direction = confluence['dominant_direction']
        strength = confluence['signal_strength']
        
        recommendation = self._generate_recommendation(direction, strength, confluence['confluence_score'])
        
        return {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'price': price,
            'multi_timeframe': confluence,
            'position_size': position_size,
            'risk_metrics': risk_metrics,
            'recommendation': recommendation,
            'signals_by_timeframe': {tf: s.name for tf, s in mtf_signals.items()},
            'confidence': confluence['confluence_score'],
            'action': 'BUY' if direction == 'up' and position_size > 0 else ('SELL' if direction == 'down' and position_size > 0 else 'HOLD')
        }
    
    def _calculate_position_size(
        self,
        symbol: str,
        price: float,
        stop_loss: float = None,
        confluence: Dict[str, Any] = None,
        historical_perf: Dict[str, float] = None
    ) -> float:
        """Calculate optimal position size using multiple methods."""
        
        if stop_loss is None or price == stop_loss:
            return 0.0
        
        # Base size: fixed risk
        base_size = self.position_sizer.fixed_risk_size(price, stop_loss)
        
        # Adjust for confluence strength
        if confluence:
            confidence_multiplier = 1.0 + abs(confluence['confluence_score']) * 0.5
            base_size *= confidence_multiplier
        
        # Adjust for historical performance (Kelly Criterion)
        if historical_perf and 'win_rate' in historical_perf:
            kelly_size = self.position_sizer.kelly_criterion(
                win_rate=historical_perf.get('win_rate', 0.55),
                win_loss_ratio=historical_perf.get('win_loss_ratio', 1.5),
                max_kelly_fraction=0.25
            )
            base_size *= kelly_size
        
        return max(0, base_size)
    
    def _generate_recommendation(self, direction: str, strength: str, score: float) -> str:
        """Generate actionable recommendation."""
        
        if direction == 'up':
            if strength == 'strong':
                return "STRONG BUY - Highest probability setup"
            elif strength == 'moderate':
                return "BUY - Moderate probability, favorable bias"
            else:
                return "WEAK BUY - Low confidence"
        
        elif direction == 'down':
            if strength == 'strong':
                return "STRONG SELL - Highest probability setup"
            elif strength == 'moderate':
                return "SELL - Moderate probability, favorable bias"
            else:
                return "WEAK SELL - Low confidence"
        
        else:
            return "HOLD - Wait for stronger confluence"
    
    def update_portfolio_risk(
        self,
        positions: Dict[str, float],
        returns_dict: Dict[str, np.ndarray],
        equity_curve: np.ndarray
    ) -> Dict[str, Any]:
        """Update portfolio-level risk metrics."""
        
        self.positions = positions
        
        return self.risk_manager.risk_metrics_summary(
            positions=positions,
            returns_dict=returns_dict,
            equity_curve=equity_curve
        )
    
    def should_reduce_position(
        self,
        symbol: str,
        current_position: float,
        current_pnl: float,
        portfolio_risk: Dict[str, Any]
    ) -> Tuple[bool, float, str]:
        """
        Decide if we should reduce position based on risk limits.
        
        Returns:
            (should_reduce, amount_to_reduce, reason)
        """
        
        concentration = portfolio_risk.get('concentration_risk', {})
        max_position_weight = concentration.get('max_position', 0)
        
        # Rule 1: Max position limit (20% of portfolio)
        if max_position_weight > 0.20:
            reduce_amount = current_position * 0.25  # Reduce by 25%
            return True, reduce_amount, "Max position concentration exceeded (20%)"
        
        # Rule 2: Max drawdown limit
        current_dd = portfolio_risk.get('current_drawdown', 0)
        if current_dd < -0.15:  # -15% drawdown
            reduce_amount = current_position * 0.5
            return True, reduce_amount, "Portfolio drawdown limit exceeded (-15%)"
        
        # Rule 3: Profitable position - scale out
        if current_pnl > 0 and current_position > 0:
            # Scale out 10% of position for every 2% profit
            scale_out_pct = min(0.5, current_pnl * 0.05)  # Max 50% scale out
            if scale_out_pct > 0.05:
                reduce_amount = current_position * scale_out_pct
                return True, reduce_amount, f"Scale out profitable position ({scale_out_pct*100:.1f}%)"
        
        return False, 0.0, "No reduction needed"
    
    def validate_new_trade(
        self,
        symbol: str,
        size: float,
        entry_price: float,
        portfolio_risk: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Validate if new trade meets risk criteria.
        
        Returns:
            (is_valid, reason)
        """
        
        # Check 1: Risk per trade
        risk_amount = size * abs(entry_price - 0) * 0.02  # Assuming 2% stop
        if risk_amount > self.account_size * self.max_risk_per_trade:
            return False, f"Trade size ({size}) exceeds max risk per trade"
        
        # Check 2: Portfolio concentration after trade
        concentration = portfolio_risk.get('concentration_risk', {})
        if concentration.get('herfindahl_index', 0) > 0.4:
            return False, "Portfolio already too concentrated"
        
        # Check 3: Current drawdown
        current_dd = portfolio_risk.get('current_drawdown', 0)
        if current_dd < -0.20:
            return False, "Portfolio drawdown too severe (-20%)"
        
        # Check 4: VAR limit
        var_limit = self.account_size * 0.05  # Max 5% daily VAR
        portfolio_var = portfolio_risk.get('portfolio_var', 0)
        if portfolio_var < -var_limit:
            return False, f"Portfolio VAR limit exceeded: {portfolio_var:.2f}"
        
        return True, "Trade approved"
    
    def get_risk_report(self) -> Dict[str, Any]:
        """Generate comprehensive risk report."""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'account_size': self.account_size,
            'max_risk_per_trade': self.max_risk_per_trade,
            'num_positions': len(self.positions),
            'total_positions_tracked': len(self.mtf_analyzer.confluences),
            'risk_manager_status': 'active',
            'position_sizer_status': 'active',
            'mtf_analyzer_status': 'active',
            'trade_history_count': len(self.trade_history)
        }
