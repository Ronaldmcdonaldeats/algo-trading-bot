"""Advanced position sizing strategies (Kelly Criterion, Risk Parity, etc)."""

import numpy as np
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""
    size: float
    max_size: float
    risk_pct: float
    method: str


class PositionSizer:
    """Calculate optimal position sizes using various methods."""
    
    def __init__(self, account_size: float, max_risk_per_trade: float = 0.02):
        """
        Args:
            account_size: Total account equity
            max_risk_per_trade: Max % of account to risk per trade (default 2%)
        """
        self.account_size = account_size
        self.max_risk_per_trade = max_risk_per_trade
    
    def kelly_criterion(
        self, 
        win_rate: float, 
        win_loss_ratio: float,
        max_kelly_fraction: float = 0.25
    ) -> float:
        """
        Calculate Kelly Criterion for optimal position sizing.
        
        Kelly % = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        Args:
            win_rate: Historical win rate (0-1)
            win_loss_ratio: Average win / Average loss
            max_kelly_fraction: Use fraction of Kelly (safety factor, typically 0.25)
        
        Returns:
            Optimal position size as % of account
        """
        if win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        if win_loss_ratio <= 0:
            return 0.0
        
        kelly_pct = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        # Clamp to [0, 1]
        kelly_pct = max(0, min(1, kelly_pct))
        
        # Use fractional Kelly for safety
        return kelly_pct * max_kelly_fraction
    
    def fixed_risk_size(self, entry_price: float, stop_loss: float) -> float:
        """
        Size position based on fixed risk per trade.
        
        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
        
        Returns:
            Number of shares to buy
        """
        risk_per_share = abs(entry_price - stop_loss)
        
        if risk_per_share == 0:
            return 0.0
        
        risk_amount = self.account_size * self.max_risk_per_trade
        return risk_amount / risk_per_share
    
    def volatility_adjusted_size(
        self, 
        current_price: float,
        volatility: float,
        target_risk_pct: float = None
    ) -> float:
        """
        Size position inversely to volatility (high vol = smaller position).
        
        Args:
            current_price: Current stock price
            volatility: Historical volatility (annualized, e.g., 0.3 for 30%)
            target_risk_pct: Target loss if volatility move occurs (default: max_risk_per_trade)
        
        Returns:
            Number of shares to buy
        """
        if target_risk_pct is None:
            target_risk_pct = self.max_risk_per_trade
        
        if volatility == 0 or current_price == 0:
            return 0.0
        
        # Daily volatility
        daily_vol = volatility / np.sqrt(252)
        
        # Expected daily loss = price * daily_vol
        expected_loss = current_price * daily_vol
        
        # Position size = (account * risk_pct) / expected_loss
        risk_amount = self.account_size * target_risk_pct
        return risk_amount / expected_loss if expected_loss > 0 else 0.0
    
    def risk_parity_weights(self, volatilities: Dict[str, float]) -> Dict[str, float]:
        """
        Calculate risk parity weights (inverse volatility weighting).
        Each position contributes equal risk.
        
        Args:
            volatilities: {symbol: volatility}
        
        Returns:
            {symbol: weight} where weights sum to 1
        """
        if not volatilities:
            return {}
        
        # Inverse volatility (lower vol = higher weight)
        inverse_vols = {sym: 1 / vol if vol > 0 else 0 for sym, vol in volatilities.items()}
        
        total_inverse_vol = sum(inverse_vols.values())
        
        if total_inverse_vol == 0:
            # Equal weight if no valid volatility
            n = len(volatilities)
            return {sym: 1/n for sym in volatilities}
        
        return {sym: weight / total_inverse_vol for sym, weight in inverse_vols.items()}
    
    def equal_weight(self, symbols: List[str]) -> Dict[str, float]:
        """Equal weight allocation across all symbols."""
        n = len(symbols)
        return {sym: 1/n for sym in symbols} if n > 0 else {}
    
    def maximum_sharpe_weights(
        self, 
        returns_dict: Dict[str, np.ndarray],
        num_simulations: int = 1000
    ) -> Dict[str, float]:
        """
        Find weights that maximize Sharpe ratio.
        Uses random portfolio sampling.
        
        Args:
            returns_dict: {symbol: array_of_returns}
            num_simulations: Number of portfolios to sample
        
        Returns:
            {symbol: optimal_weight}
        """
        symbols = list(returns_dict.keys())
        n = len(symbols)
        
        if n == 0:
            return {}
        
        # Align returns
        min_length = min(len(r) for r in returns_dict.values())
        returns_array = np.array([returns_dict[sym][-min_length:] for sym in symbols])
        
        mean_returns = np.mean(returns_array, axis=1)
        cov_matrix = np.cov(returns_array)
        
        best_sharpe = -np.inf
        best_weights = np.array([1/n] * n)
        
        for _ in range(num_simulations):
            # Random weights
            weights = np.random.random(n)
            weights /= weights.sum()
            
            # Portfolio metrics
            portfolio_return = np.sum(weights * mean_returns) * 252
            portfolio_std = np.sqrt(weights @ cov_matrix @ weights) * np.sqrt(252)
            
            sharpe = portfolio_return / portfolio_std if portfolio_std > 0 else 0
            
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_weights = weights
        
        return dict(zip(symbols, best_weights))
    
    def pyramid_sizing(
        self, 
        total_position: float, 
        num_tranches: int = 3
    ) -> List[float]:
        """
        Pyramid sizing - smaller initial position, increase on favorable moves.
        
        Args:
            total_position: Total position size wanted
            num_tranches: Number of entry tranches (3 = 1/6, 2/6, 3/6)
        
        Returns:
            [tranche_1_size, tranche_2_size, ...]
        """
        # Triangular distribution: 1, 2, 3, ... n
        triangle_sum = num_tranches * (num_tranches + 1) / 2
        
        return [total_position * (i + 1) / triangle_sum for i in range(num_tranches)]
    
    def optimal_f_sizing(
        self,
        trades: List[Dict[str, Any]],
        account_size: float
    ) -> Tuple[float, float]:
        """
        Calculate Optimal f (Kelly-like) from historical trades.
        
        Args:
            trades: List of {entry_price, exit_price, size, symbol}
            account_size: Account equity
        
        Returns:
            (optimal_f, max_drawdown_from_f)
        """
        if not trades or len(trades) == 0:
            return 0.02, 0.0
        
        # Calculate returns
        returns = []
        for trade in trades:
            if 'entry_price' in trade and 'exit_price' in trade and 'size' in trade:
                pnl = (trade['exit_price'] - trade['entry_price']) * trade['size']
                returns.append(pnl / account_size)
        
        if not returns:
            return 0.02, 0.0
        
        returns = np.array(returns)
        
        # Find optimal f that minimizes drawdown
        best_f = 0.02
        min_dd = float('inf')
        
        for f in np.linspace(0.01, 0.1, 100):
            positions = returns / f
            cumulative = np.cumprod(1 + positions)
            cummax = np.maximum.accumulate(cumulative)
            drawdowns = (cumulative - cummax) / cummax
            max_dd = np.min(drawdowns)
            
            if abs(max_dd) < abs(min_dd):
                min_dd = max_dd
                best_f = f
        
        return best_f, min_dd
    
    def scale_existing_position(
        self,
        current_size: float,
        current_profit_loss: float,
        max_profit_target: float
    ) -> float:
        """
        Scale out of profitable position.
        
        Args:
            current_size: Current position size
            current_profit_loss: Current unrealized P&L
            max_profit_target: Max P&L target for full exit
        
        Returns:
            Size to close (partial exit)
        """
        if max_profit_target <= 0:
            return 0.0
        
        # Linear scaling: at 50% of max profit, close 25% of position
        close_pct = min(0.5, current_profit_loss / max_profit_target / 2)
        return current_size * max(0, close_pct)
