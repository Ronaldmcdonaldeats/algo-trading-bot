"""
Phase 25: Risk-Adjusted Position Sizing

Dynamically adjusts position size based on portfolio state and performance.
Increases size during winning streaks and reduces during drawdowns.
Accounts for portfolio volatility, win rate, and drawdown recovery state.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List
import numpy as np


@dataclass
class PortfolioRiskState:
    """Tracks portfolio risk metrics for sizing adjustments"""
    current_equity: float = 100000.0
    start_equity: float = 100000.0
    max_equity: float = 100000.0
    
    # Win/loss tracking
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # Volatility
    volatility: float = 0.02  # Daily volatility
    sharpe_ratio: float = 0.0
    
    # Drawdown
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    
    @property
    def win_rate(self) -> float:
        """Win rate of all trades"""
        if self.total_trades == 0:
            return 0.5
        return self.winning_trades / self.total_trades
    
    @property
    def in_drawdown(self) -> bool:
        """Check if currently in drawdown"""
        return self.current_equity < self.max_equity
    
    @property
    def drawdown_severity(self) -> float:
        """How severe is the current drawdown (0-1, clamped)"""
        if self.max_equity <= 0:
            return 0.0
        severity = abs(self.drawdown_pct)
        return min(1.0, severity / 0.15)  # 15% drawdown = 1.0 severity
    
    @property
    def equity_ratio(self) -> float:
        """Current equity as ratio of starting equity"""
        if self.start_equity <= 0:
            return 1.0
        return self.current_equity / self.start_equity


class RiskAdjustedSizer:
    """Adjusts position size based on portfolio risk state"""
    
    def __init__(
        self,
        base_risk_pct: float = 0.01,  # 1% risk per trade
        max_position_pct: float = 0.15,  # Max 15% of portfolio per trade
        min_position_pct: float = 0.001,  # Min 0.1% of portfolio per trade
        
        # Risk adjustment parameters
        volatility_scale: float = 1.0,  # Higher vol = smaller positions
        drawdown_scale: float = 1.0,  # Higher drawdown = smaller positions
        win_streak_boost: float = 1.2,  # Up to 20% boost during wins
        loss_streak_reduction: float = 0.7,  # Down to 70% reduction during losses
        
        # Thresholds
        hot_streak_min: int = 3,  # Min consecutive wins for boost
        cold_streak_min: int = 2,  # Min consecutive losses for reduction
        drawdown_threshold: float = 0.05,  # Start reducing at 5% drawdown
        recovery_boost_after_dd: float = 0.07,  # Boost sizing if recovered >7% from max DD
    ):
        self.base_risk_pct = base_risk_pct
        self.max_position_pct = max_position_pct
        self.min_position_pct = min_position_pct
        
        self.volatility_scale = volatility_scale
        self.drawdown_scale = drawdown_scale
        self.win_streak_boost = win_streak_boost
        self.loss_streak_reduction = loss_streak_reduction
        
        self.hot_streak_min = hot_streak_min
        self.cold_streak_min = cold_streak_min
        self.drawdown_threshold = drawdown_threshold
        self.recovery_boost_after_dd = recovery_boost_after_dd
        
        # Tracking
        self.state = PortfolioRiskState()
        self.equity_history: List[float] = [100000.0]
    
    def update_state(
        self,
        current_equity: float,
        consecutive_wins: int = 0,
        consecutive_losses: int = 0,
        total_trades: int = 0,
        winning_trades: int = 0,
        losing_trades: int = 0,
        volatility: float = 0.02,
        sharpe_ratio: float = 0.0,
    ):
        """Update portfolio state for sizing calculations"""
        self.state.current_equity = current_equity
        self.state.consecutive_wins = consecutive_wins
        self.state.consecutive_losses = consecutive_losses
        self.state.total_trades = total_trades
        self.state.winning_trades = winning_trades
        self.state.losing_trades = losing_trades
        self.state.volatility = volatility
        self.state.sharpe_ratio = sharpe_ratio
        
        # Track equity history for drawdown
        self.equity_history.append(current_equity)
        
        # Calculate drawdown metrics
        max_equity_so_far = max(self.equity_history)
        self.state.max_equity = max_equity_so_far
        self.state.drawdown_pct = (current_equity - max_equity_so_far) / max_equity_so_far if max_equity_so_far > 0 else 0.0
        self.state.max_drawdown_pct = abs(min(self.state.drawdown_pct, 0.0))
    
    def get_position_multiplier(self) -> float:
        """
        Get position size multiplier (0.0 - 2.0)
        
        Factors:
        - Base: 1.0x
        - Volatility: 0.5x - 2.0x (high vol = smaller)
        - Win streak: 1.0x - 1.2x (hot streak boost)
        - Loss streak: 0.3x - 1.0x (cold streak reduction)
        - Drawdown: 0.3x - 1.0x (deeper DD = smaller)
        - Recovery boost: up to 1.3x after recovery from DD
        
        Returns:
            Multiplier to apply to base position size
        """
        multiplier = 1.0
        
        # 1. Volatility adjustment (inverse relationship)
        vol_mult = self._calculate_volatility_mult()
        multiplier *= vol_mult
        
        # 2. Win/Loss streak adjustment
        streak_mult = self._calculate_streak_mult()
        multiplier *= streak_mult
        
        # 3. Drawdown adjustment
        dd_mult = self._calculate_drawdown_mult()
        multiplier *= dd_mult
        
        # 4. Recovery boost (after deep drawdowns)
        recovery_mult = self._calculate_recovery_mult()
        multiplier *= recovery_mult
        
        # Clamp to reasonable bounds
        return max(self.min_position_pct / self.base_risk_pct, 
                  min(self.max_position_pct / self.base_risk_pct, multiplier))
    
    def _calculate_volatility_mult(self) -> float:
        """
        Volatility adjustment: High vol = smaller positions
        
        Normal vol (0.02): 1.0x
        High vol (0.05): 0.6x
        Very high vol (0.10): 0.4x
        """
        if self.state.volatility <= 0:
            return 1.0
        
        # Volatility range: 0.01 (very calm) to 0.10+ (extreme)
        normal_vol = 0.02
        vol_ratio = self.state.volatility / normal_vol
        
        # Quadratic scaling: higher volatility = much smaller position
        vol_mult = 1.0 / (1.0 + vol_ratio * self.volatility_scale)
        return max(0.4, min(1.5, vol_mult))
    
    def _calculate_streak_mult(self) -> float:
        """
        Win/loss streak adjustment
        
        3+ consecutive wins: Boost up to 1.2x
        2+ consecutive losses: Reduce to 0.7x or less
        Even performance: 1.0x
        """
        streak_mult = 1.0
        
        # Winning streak boost
        if self.state.consecutive_wins >= self.hot_streak_min:
            wins_over_threshold = self.state.consecutive_wins - self.hot_streak_min
            boost = 1.0 + (wins_over_threshold * 0.05)  # +5% per win after threshold
            streak_mult *= min(self.win_streak_boost, boost)
        
        # Losing streak reduction
        if self.state.consecutive_losses >= self.cold_streak_min:
            losses_over_threshold = self.state.consecutive_losses - self.cold_streak_min
            reduction = 1.0 - (losses_over_threshold * 0.15)  # -15% per loss after threshold
            streak_mult *= max(self.loss_streak_reduction, reduction)
        
        return max(0.5, min(1.5, streak_mult))
    
    def _calculate_drawdown_mult(self) -> float:
        """
        Drawdown adjustment: Deeper DD = smaller positions
        
        No DD: 1.0x
        5% DD: 0.9x
        10% DD: 0.7x
        15% DD: 0.4x
        20%+ DD: 0.2x
        """
        if not self.state.in_drawdown:
            return 1.0
        
        severity = self.state.drawdown_severity
        # Quadratic scaling: deeper drawdowns reduce more
        dd_mult = 1.0 - (severity * severity * self.drawdown_scale)
        return max(0.2, min(1.0, dd_mult))
    
    def _calculate_recovery_mult(self) -> float:
        """
        Recovery boost: After severe DD, reward recovery
        
        If we've recovered > 7% from worst DD: get boost
        More recovery = more boost (up to 1.3x)
        """
        if not self.state.in_drawdown or self.state.max_drawdown_pct <= 0.05:
            return 1.0
        
        # Calculate recovery from worst point
        recovery_from_worst = abs(self.state.drawdown_pct) - self.recovery_boost_after_dd
        if recovery_from_worst > 0:
            # We've recovered more than threshold
            recovery_pct = recovery_from_worst / self.state.max_drawdown_pct
            recovery_mult = 1.0 + (recovery_pct * 0.3)  # Up to 30% boost
            return min(1.3, recovery_mult)
        
        return 1.0
    
    def get_adjusted_position_size(
        self,
        base_size: float,
    ) -> float:
        """
        Get adjusted position size for a trade
        
        Args:
            base_size: Base position size in shares
            
        Returns:
            Adjusted position size
        """
        multiplier = self.get_position_multiplier()
        adjusted_size = base_size * multiplier
        return float(adjusted_size)
    
    def get_position_limits(self) -> tuple[float, float]:
        """
        Get min/max position size as % of equity
        
        Returns:
            (min_pct, max_pct) of portfolio
        """
        multiplier = self.get_position_multiplier()
        min_limit = self.min_position_pct * multiplier
        max_limit = self.max_position_pct * multiplier
        return (min_limit, max_limit)
    
    def get_risk_level(self) -> str:
        """
        Get current risk level description
        
        Returns:
            "very_low", "low", "normal", "high", "very_high"
        """
        multiplier = self.get_position_multiplier()
        
        if multiplier < 0.5:
            return "very_low"
        elif multiplier < 0.8:
            return "low"
        elif multiplier < 1.2:
            return "normal"
        elif multiplier < 1.5:
            return "high"
        else:
            return "very_high"
    
    def get_sizing_breakdown(self) -> dict:
        """Get breakdown of sizing components for debugging"""
        vol_mult = self._calculate_volatility_mult()
        streak_mult = self._calculate_streak_mult()
        dd_mult = self._calculate_drawdown_mult()
        recovery_mult = self._calculate_recovery_mult()
        total_mult = self.get_position_multiplier()
        
        return {
            "total_multiplier": round(total_mult, 3),
            "volatility_mult": round(vol_mult, 3),
            "streak_mult": round(streak_mult, 3),
            "drawdown_mult": round(dd_mult, 3),
            "recovery_mult": round(recovery_mult, 3),
            "risk_level": self.get_risk_level(),
            "state": {
                "volatility": round(self.state.volatility, 4),
                "win_rate": f"{self.state.win_rate:.0%}",
                "drawdown": f"{self.state.drawdown_pct:.1%}",
                "consecutive_wins": self.state.consecutive_wins,
                "consecutive_losses": self.state.consecutive_losses,
            }
        }
    
    def print_status(self):
        """Print sizing status for monitoring"""
        breakdown = self.get_sizing_breakdown()
        print(
            f"   [SIZING] Risk: {breakdown['risk_level']} | "
            f"Mult: {breakdown['total_multiplier']:.2f}x | "
            f"Vol: {breakdown['volatility_mult']:.2f}x | "
            f"Streak: {breakdown['streak_mult']:.2f}x | "
            f"DD: {breakdown['drawdown_mult']:.2f}x | "
            f"Win: {breakdown['state']['win_rate']}",
            flush=True,
        )
