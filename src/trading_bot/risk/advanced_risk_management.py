"""
Advanced Risk Management Module
Value at Risk (VaR), Monte Carlo Simulation, Regime Detection, Dynamic Position Sizing
"""

import numpy as np
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass
from scipy import stats


@dataclass
class RiskMetrics:
    """Container for risk metrics"""
    var_95: float  # Value at Risk at 95% confidence
    var_99: float  # Value at Risk at 99% confidence
    cvar_95: float  # Conditional VaR (Expected Shortfall) at 95%
    expected_loss: float  # Expected loss (mean of worst 5%)
    kelly_fraction: float  # Kelly Criterion optimal position size


class ValueAtRisk:
    """Calculate Value at Risk and Conditional VaR"""
    
    @staticmethod
    def calculate_var(returns: List[float], confidence_level: float = 0.95) -> float:
        """
        Calculate Historical VaR
        
        Args:
            returns: Daily returns
            confidence_level: 0.95 for 95% VaR
            
        Returns:
            VaR as percentage (negative = loss)
        """
        if len(returns) < 100:
            raise ValueError("Need at least 100 returns for reliable VaR")
        
        var = np.percentile(returns, (1 - confidence_level) * 100)
        return var
    
    @staticmethod
    def calculate_cvar(returns: List[float], confidence_level: float = 0.95) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall)
        Average loss exceeding VaR
        
        Args:
            returns: Daily returns
            confidence_level: 0.95 for 95% CVaR
            
        Returns:
            CVaR as percentage
        """
        var = ValueAtRisk.calculate_var(returns, confidence_level)
        worse_returns = [r for r in returns if r <= var]
        
        if len(worse_returns) == 0:
            return var
        
        return np.mean(worse_returns)


class MonteCarloSimulation:
    """Monte Carlo simulation for strategy stress testing"""
    
    @staticmethod
    def simulate_returns(
        mean_return: float,
        volatility: float,
        days: int = 504,
        simulations: int = 10000,
        seed: Optional[int] = None
    ) -> np.ndarray:
        """
        Simulate future returns using geometric Brownian motion
        
        Args:
            mean_return: Daily mean return (e.g., 0.0005)
            volatility: Daily volatility/std dev (e.g., 0.012)
            days: Number of days to simulate
            simulations: Number of Monte Carlo paths
            seed: Random seed for reproducibility
            
        Returns:
            Array of shape (simulations, days) with simulated returns
        """
        if seed is not None:
            np.random.seed(seed)
        
        # Generate random normal shocks
        shocks = np.random.normal(mean_return, volatility, (simulations, days))
        
        # Cumulative returns (geometric Brownian motion)
        returns = np.exp(np.cumsum(np.log(1 + shocks), axis=1)) - 1
        
        return returns
    
    @staticmethod
    def simulate_portfolio_value(
        initial_capital: float,
        mean_return: float,
        volatility: float,
        days: int = 504,
        simulations: int = 10000
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Simulate portfolio value paths
        
        Args:
            initial_capital: Starting capital
            mean_return: Daily return
            volatility: Daily volatility
            days: Number of days
            simulations: Number of paths
            
        Returns:
            Tuple of (portfolio_values, percentiles_5, percentiles_95)
        """
        returns = MonteCarloSimulation.simulate_returns(
            mean_return, volatility, days, simulations
        )
        
        # Convert returns to portfolio values
        portfolio_values = initial_capital * (1 + returns)
        
        # Calculate percentiles
        p5 = np.percentile(portfolio_values, 5, axis=0)
        p95 = np.percentile(portfolio_values, 95, axis=0)
        
        return portfolio_values, p5, p95


class RegimeDetection:
    """Detect market regimes (bull, bear, sideways)"""
    
    @staticmethod
    def detect_regime(
        returns: List[float],
        window: int = 20
    ) -> str:
        """
        Detect current market regime
        
        Args:
            returns: Daily returns
            window: Rolling window for analysis (default 20 days)
            
        Returns:
            Regime: 'bull', 'bear', or 'sideways'
        """
        if len(returns) < window:
            return 'sideways'
        
        recent = returns[-window:]
        mean_return = np.mean(recent)
        volatility = np.std(recent)
        
        # Bull: positive return, low volatility
        if mean_return > 0.001 and volatility < 0.015:
            return 'bull'
        
        # Bear: negative return, high volatility
        elif mean_return < -0.001 and volatility > 0.015:
            return 'bear'
        
        # Sideways: low mean return
        else:
            return 'sideways'
    
    @staticmethod
    def get_regime_multiplier(regime: str) -> float:
        """
        Get position size multiplier based on regime
        
        Args:
            regime: Market regime
            
        Returns:
            Multiplier for position sizing (0.5-1.5)
        """
        multipliers = {
            'bull': 1.5,      # Increase size in bull markets
            'sideways': 1.0,  # Normal size
            'bear': 0.5       # Reduce size in bear markets
        }
        return multipliers.get(regime, 1.0)


class DynamicPositionSizing:
    """Kelly Criterion and volatility-based position sizing"""
    
    @staticmethod
    def kelly_fraction(
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate optimal position size using Kelly Criterion
        
        Args:
            win_rate: Fraction of winning trades (0-1)
            avg_win: Average win size
            avg_loss: Average loss size (positive)
            
        Returns:
            Optimal fraction of capital to risk (0-1)
        """
        if avg_loss == 0 or avg_win == 0:
            return 0.0
        
        loss_rate = 1 - win_rate
        win_loss_ratio = avg_win / avg_loss
        
        # Kelly formula: f = (p*b - q) / b
        # where p=win_rate, q=loss_rate, b=win_loss_ratio
        kelly = (win_rate * win_loss_ratio - loss_rate) / win_loss_ratio
        
        # Clamp between 0 and 0.25 (fractional Kelly for safety)
        kelly = max(0.0, min(0.25, kelly / 2))  # Half Kelly for robustness
        
        return kelly
    
    @staticmethod
    def volatility_adjusted_size(
        base_position: float,
        current_volatility: float,
        target_volatility: float = 0.015
    ) -> float:
        """
        Adjust position size based on volatility
        
        Args:
            base_position: Base position size
            current_volatility: Current market volatility
            target_volatility: Target volatility
            
        Returns:
            Adjusted position size
        """
        if current_volatility == 0:
            return base_position
        
        # Inverse volatility: smaller positions when volatility is high
        multiplier = target_volatility / current_volatility
        adjusted = base_position * multiplier
        
        # Clamp to reasonable range (0.25x - 2.0x)
        return max(base_position * 0.25, min(base_position * 2.0, adjusted))
    
    @staticmethod
    def calculate_position_size(
        capital: float,
        kelly_fraction: float,
        volatility: float,
        target_volatility: float = 0.015,
        max_risk_pct: float = 0.02
    ) -> float:
        """
        Calculate final position size with multiple constraints
        
        Args:
            capital: Total capital
            kelly_fraction: Kelly Criterion fraction
            volatility: Current volatility
            target_volatility: Target volatility
            max_risk_pct: Maximum risk as % of capital
            
        Returns:
            Position size in dollars
        """
        # Kelly-based position
        kelly_position = capital * kelly_fraction
        
        # Volatility-adjusted position
        adjusted_position = DynamicPositionSizing.volatility_adjusted_size(
            kelly_position, volatility, target_volatility
        )
        
        # Risk constraint (don't risk more than max_risk_pct per trade)
        max_position = capital * max_risk_pct / volatility
        
        # Take minimum of all constraints
        final_position = min(adjusted_position, max_position)
        
        return final_position


class ComprehensiveRiskAnalysis:
    """Combine all risk metrics into single analysis"""
    
    @staticmethod
    def analyze_strategy(
        returns: List[float],
        capital: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> RiskMetrics:
        """
        Comprehensive risk analysis
        
        Args:
            returns: Daily returns
            capital: Total capital
            win_rate: Fraction of winning trades
            avg_win: Average win
            avg_loss: Average loss
            
        Returns:
            RiskMetrics dataclass with all metrics
        """
        # VaR calculations
        var_95 = ValueAtRisk.calculate_var(returns, 0.95)
        var_99 = ValueAtRisk.calculate_var(returns, 0.99)
        cvar_95 = ValueAtRisk.calculate_cvar(returns, 0.95)
        
        # Expected loss
        expected_loss = np.mean([r for r in returns if r < 0])
        
        # Kelly Criterion
        kelly = DynamicPositionSizing.kelly_fraction(win_rate, avg_win, avg_loss)
        
        return RiskMetrics(
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            expected_loss=expected_loss,
            kelly_fraction=kelly
        )
