"""Kelly Criterion optimal position sizing based on win rate and reward-risk ratio."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PerformanceMetrics:
    """Performance metrics for Kelly calculation."""
    win_rate: float  # 0.0 - 1.0 (e.g., 0.55 = 55% win rate)
    loss_rate: float  # 0.0 - 1.0 (0.45 = 45% loss rate)
    avg_win: float  # Average win size in dollars
    avg_loss: float  # Average loss size in dollars (positive number)
    total_trades: int = 0  # For validity check
    
    @property
    def reward_risk_ratio(self) -> float:
        """Calculate reward-to-risk ratio.
        
        Returns:
            R:R ratio (e.g., 1.5 = win $1.50 for every $1.00 risk)
        """
        if self.avg_loss <= 0:
            return 0
        return self.avg_win / self.avg_loss


class KellyCriterion:
    """Calculate optimal position sizing using Kelly Criterion formula."""
    
    @staticmethod
    def calculate_kelly_percentage(win_rate: float, reward_risk_ratio: float) -> float:
        """Calculate Kelly Criterion position size.
        
        Args:
            win_rate: Win rate as decimal (0.0 - 1.0)
            reward_risk_ratio: Average win / Average loss
            
        Returns:
            Kelly percentage (0.0 - 1.0)
            
        Formula:
            f* = (win_rate × R - loss_rate) / R
            where:
              f* = optimal position size as fraction of bankroll
              win_rate = probability of winning
              R = reward-to-risk ratio (avg_win / avg_loss)
              loss_rate = 1 - win_rate
        
        Examples:
            - 55% win rate, 1.5 R:R → f* = 0.183 (18.3% of bankroll per trade)
            - 60% win rate, 2.0 R:R → f* = 0.400 (40% of bankroll per trade)
            - 50% win rate, 1.0 R:R → f* = 0.000 (0% - break even, don't trade)
            - 45% win rate, 1.0 R:R → f* = -0.050 (negative - don't trade)
        """
        if reward_risk_ratio <= 0 or not (0 <= win_rate <= 1):
            return 0
        
        loss_rate = 1 - win_rate
        
        # Kelly formula: f* = (p*R - q) / R
        # where p = win_rate, q = loss_rate, R = reward_risk_ratio
        kelly_pct = (win_rate * reward_risk_ratio - loss_rate) / reward_risk_ratio
        
        # Kelly percentage should be between 0 and 1
        return max(0, min(1, kelly_pct))
    
    @staticmethod
    def calculate_position_size(
        bankroll: float,
        kelly_percentage: float,
        fractional_kelly: float = 0.25,
        max_position_size: Optional[float] = None,
    ) -> float:
        """Calculate actual position size from Kelly percentage.
        
        Args:
            bankroll: Total trading capital
            kelly_percentage: Kelly percentage (0.0 - 1.0)
            fractional_kelly: Use fraction of Kelly (default 0.25 = 25% Kelly)
                - 1.0 = Full Kelly (aggressive, high volatility)
                - 0.5 = Half Kelly (balanced)
                - 0.25 = Quarter Kelly (conservative, recommended)
                - 0.1 = 10% Kelly (very conservative)
            max_position_size: Cap maximum position size in dollars
            
        Returns:
            Position size in dollars
            
        Note:
            Fractional Kelly reduces volatility while maintaining long-term edge.
            Most traders use 0.25 (quarter Kelly) for safety and steady growth.
        """
        if kelly_percentage <= 0:
            return 0
        
        # Apply fractional Kelly for safety
        effective_kelly = kelly_percentage * fractional_kelly
        position_size = bankroll * effective_kelly
        
        # Cap at maximum if specified
        if max_position_size is not None:
            position_size = min(position_size, max_position_size)
        
        return position_size
    
    @staticmethod
    def get_position_size_from_metrics(
        bankroll: float,
        metrics: PerformanceMetrics,
        fractional_kelly: float = 0.25,
        max_position_size: Optional[float] = None,
        min_trades_for_validity: int = 20,
    ) -> dict:
        """Get position size from performance metrics.
        
        Args:
            bankroll: Total trading capital
            metrics: PerformanceMetrics object with win rate, R:R, etc
            fractional_kelly: Fractional Kelly to use
            max_position_size: Maximum position size cap
            min_trades_for_validity: Minimum trades needed for reliable estimate
            
        Returns:
            Dict with:
              - kelly_percentage: Raw Kelly percentage
              - fractional_kelly: Applied Kelly percentage
              - position_size: Recommended position size in dollars
              - is_valid: Whether estimate is reliable (enough trades)
              - validity_reason: Explanation if not valid
        """
        # Check if metrics are valid
        validity_issues = []
        
        if metrics.total_trades < min_trades_for_validity:
            validity_issues.append(f"Only {metrics.total_trades} trades (need {min_trades_for_validity})")
        
        if metrics.win_rate < 0.35:
            validity_issues.append(f"Win rate too low: {metrics.win_rate:.1%} (need > 35%)")
        
        if metrics.reward_risk_ratio < 0.5:
            validity_issues.append(f"R:R too low: {metrics.reward_risk_ratio:.2f} (need > 0.5)")
        
        # Calculate Kelly
        kelly_pct = KellyCriterion.calculate_kelly_percentage(
            win_rate=metrics.win_rate,
            reward_risk_ratio=metrics.reward_risk_ratio
        )
        
        # If Kelly is negative, don't trade
        if kelly_pct <= 0:
            validity_issues.append("Kelly percentage negative or zero (losing system)")
        
        # Calculate position size
        position_size = KellyCriterion.calculate_position_size(
            bankroll=bankroll,
            kelly_percentage=kelly_pct,
            fractional_kelly=fractional_kelly,
            max_position_size=max_position_size
        )
        
        return {
            "kelly_percentage": round(kelly_pct, 4),
            "fractional_kelly": round(kelly_pct * fractional_kelly, 4),
            "position_size": round(position_size, 2),
            "is_valid": len(validity_issues) == 0,
            "validity_reason": "; ".join(validity_issues) if validity_issues else "Valid",
            "metrics": {
                "win_rate": f"{metrics.win_rate:.1%}",
                "loss_rate": f"{metrics.loss_rate:.1%}",
                "reward_risk_ratio": f"{metrics.reward_risk_ratio:.2f}",
                "avg_win": f"${metrics.avg_win:.2f}",
                "avg_loss": f"${metrics.avg_loss:.2f}",
                "total_trades": metrics.total_trades,
            }
        }
    
    @staticmethod
    def get_recommended_kelly_fraction(win_rate: float, max_drawdown_tolerance: float = 0.15) -> float:
        """Get recommended fractional Kelly based on win rate and drawdown tolerance.
        
        Args:
            win_rate: Win rate as decimal
            max_drawdown_tolerance: Maximum acceptable drawdown (0.15 = 15%)
            
        Returns:
            Recommended fractional Kelly (0.1 - 1.0)
            
        Logic:
            - Low win rate (<45%): Use conservative Kelly (0.1-0.2)
            - Medium win rate (45-55%): Use moderate Kelly (0.25-0.5)
            - High win rate (>55%): Can use aggressive Kelly (0.5-1.0)
            - Adjust based on drawdown tolerance
        """
        if win_rate < 0.45:
            kelly_fraction = 0.1  # Very conservative
        elif win_rate < 0.50:
            kelly_fraction = 0.15
        elif win_rate < 0.55:
            kelly_fraction = 0.25  # Conservative (recommended baseline)
        elif win_rate < 0.60:
            kelly_fraction = 0.5   # Moderate
        else:  # >= 0.60
            kelly_fraction = 0.75  # Aggressive
        
        # Adjust for drawdown tolerance
        # Lower tolerance = lower Kelly fraction
        if max_drawdown_tolerance < 0.10:
            kelly_fraction *= 0.5  # Cut in half
        elif max_drawdown_tolerance < 0.15:
            kelly_fraction *= 0.75
        
        return max(0.1, min(1.0, kelly_fraction))
    
    @staticmethod
    def calculate_expected_drawdown(kelly_percentage: float, win_rate: float) -> float:
        """Estimate maximum expected drawdown using Kelly percentage.
        
        Args:
            kelly_percentage: Kelly percentage (0.0 - 1.0)
            win_rate: Win rate as decimal
            
        Returns:
            Expected maximum drawdown as decimal (0.0 - 1.0)
            
        Logic:
            - Full Kelly: 25-30% max drawdown typical
            - Half Kelly: 10-15% max drawdown
            - Quarter Kelly: 5-10% max drawdown
        """
        # Empirical formula for expected max drawdown with Kelly
        # Based on risk of ruin calculations
        
        if kelly_percentage == 0:
            return 0
        
        # Expected drawdown increases with Kelly percentage
        # Scaling factor based on win rate (lower win rate = higher drawdown)
        scaling_factor = (1 - win_rate) / win_rate if win_rate > 0 else 2
        
        expected_drawdown = 0.05 * (kelly_percentage / 0.25) * scaling_factor
        
        return min(0.5, expected_drawdown)  # Cap at 50%
    
    @staticmethod
    def print_kelly_analysis(metrics: PerformanceMetrics, bankroll: float, 
                           fractional_kelly: float = 0.25) -> None:
        """Print formatted Kelly Criterion analysis.
        
        Args:
            metrics: Performance metrics
            bankroll: Total bankroll
            fractional_kelly: Fractional Kelly to use
        """
        kelly_pct = KellyCriterion.calculate_kelly_percentage(
            metrics.win_rate,
            metrics.reward_risk_ratio
        )
        
        position_size = KellyCriterion.calculate_position_size(
            bankroll,
            kelly_pct,
            fractional_kelly
        )
        
        expected_dd = KellyCriterion.calculate_expected_drawdown(kelly_pct, metrics.win_rate)
        
        print("\n[KELLY CRITERION ANALYSIS]")
        print(f"  Win Rate: {metrics.win_rate:.1%}")
        print(f"  Loss Rate: {metrics.loss_rate:.1%}")
        print(f"  Avg Win: ${metrics.avg_win:.2f}")
        print(f"  Avg Loss: ${metrics.avg_loss:.2f}")
        print(f"  Reward-Risk Ratio: {metrics.reward_risk_ratio:.2f}x")
        print(f"  Bankroll: ${bankroll:,.2f}")
        print(f"  Full Kelly %: {kelly_pct:.1%}")
        print(f"  Fractional Kelly ({fractional_kelly:.0%}): {kelly_pct * fractional_kelly:.1%}")
        print(f"  Position Size: ${position_size:,.2f}")
        print(f"  Expected Max Drawdown: {expected_dd:.1%}")
        print()
