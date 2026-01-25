"""
Advanced Risk Management Module
Options support (Greeks), correlation-based hedging, dynamic position sizing.
Prevents catastrophic losses through multi-layer risk controls.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from enum import Enum
from scipy.stats import norm

logger = logging.getLogger(__name__)


class OptionType(Enum):
    """Option contract types"""
    CALL = "call"
    PUT = "put"


@dataclass
class OptionPrice:
    """Option pricing components"""
    symbol: str
    option_type: OptionType
    strike: float
    expiration_days: int
    underlying_price: float
    volatility: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    price: float


@dataclass
class PositionRisk:
    """Risk metrics for a position"""
    symbol: str
    position_size: int
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    stop_loss_price: float
    take_profit_price: float
    max_loss_potential: float
    risk_reward_ratio: float
    position_concentration: float  # % of portfolio


@dataclass
class PortfolioRisk:
    """Aggregate portfolio risk metrics"""
    total_positions: int
    gross_leverage: float  # Sum of abs position sizes / capital
    net_leverage: float  # (Long - Short) / capital
    max_sector_concentration: float
    max_symbol_concentration: float
    correlation_risk: float  # Average inter-position correlation
    var_95: float  # Value at Risk at 95% confidence
    cvar_95: float  # Conditional VAR (expected shortfall)
    max_drawdown_projected: float
    liquidity_risk_score: float


@dataclass
class HedgeRecommendation:
    """Recommendation for hedging a position"""
    primary_symbol: str
    hedge_symbol: str
    hedge_type: str  # "put", "call", "short_correlated"
    quantity: int
    cost_bps: float  # Cost in basis points
    effectiveness: float  # 0-1, how well it hedges


class BlackScholesCalculator:
    """Calculates option Greeks using Black-Scholes model"""

    def __init__(self, risk_free_rate: float = 0.05):
        self.risk_free_rate = risk_free_rate

    def calculate_d1_d2(
        self,
        S: float,  # Current stock price
        K: float,  # Strike price
        T: float,  # Time to expiration (years)
        sigma: float,  # Volatility
        r: float = None,  # Risk-free rate
    ) -> Tuple[float, float]:
        """Calculate d1 and d2 for Black-Scholes"""
        if r is None:
            r = self.risk_free_rate

        if T <= 0 or sigma <= 0:
            return 0.0, 0.0

        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        return d1, d2

    def calculate_call_price(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        r: float = None,
    ) -> float:
        """Calculate call option price"""
        if r is None:
            r = self.risk_free_rate

        d1, d2 = self.calculate_d1_d2(S, K, T, sigma, r)

        call_price = (
            S * norm.cdf(d1)
            - K * np.exp(-r * T) * norm.cdf(d2)
        )

        return call_price

    def calculate_put_price(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        r: float = None,
    ) -> float:
        """Calculate put option price"""
        if r is None:
            r = self.risk_free_rate

        d1, d2 = self.calculate_d1_d2(S, K, T, sigma, r)

        put_price = (
            K * np.exp(-r * T) * norm.cdf(-d2)
            - S * norm.cdf(-d1)
        )

        return put_price

    def calculate_delta(
        self,
        option_type: OptionType,
        S: float,
        K: float,
        T: float,
        sigma: float,
        r: float = None,
    ) -> float:
        """Calculate option delta"""
        if r is None:
            r = self.risk_free_rate

        d1, _ = self.calculate_d1_d2(S, K, T, sigma, r)

        if option_type == OptionType.CALL:
            return norm.cdf(d1)
        else:  # PUT
            return norm.cdf(d1) - 1

    def calculate_gamma(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        r: float = None,
    ) -> float:
        """Calculate option gamma"""
        if r is None:
            r = self.risk_free_rate

        if T <= 0 or sigma <= 0:
            return 0.0

        d1, _ = self.calculate_d1_d2(S, K, T, sigma, r)

        return norm.pdf(d1) / (S * sigma * np.sqrt(T))

    def calculate_vega(
        self,
        S: float,
        K: float,
        T: float,
        sigma: float,
        r: float = None,
    ) -> float:
        """Calculate option vega (per 1% change in volatility)"""
        if r is None:
            r = self.risk_free_rate

        if T <= 0 or sigma <= 0:
            return 0.0

        d1, _ = self.calculate_d1_d2(S, K, T, sigma, r)

        return S * norm.pdf(d1) * np.sqrt(T) / 100

    def calculate_theta(
        self,
        option_type: OptionType,
        S: float,
        K: float,
        T: float,
        sigma: float,
        r: float = None,
    ) -> float:
        """Calculate option theta (per day)"""
        if r is None:
            r = self.risk_free_rate

        if T <= 0 or sigma <= 0:
            return 0.0

        d1, d2 = self.calculate_d1_d2(S, K, T, sigma, r)

        if option_type == OptionType.CALL:
            theta = (
                -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                - r * K * np.exp(-r * T) * norm.cdf(d2)
            )
        else:  # PUT
            theta = (
                -S * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                + r * K * np.exp(-r * T) * norm.cdf(-d2)
            )

        return theta / 365  # Per day

    def calculate_all_greeks(
        self,
        option_type: OptionType,
        S: float,
        K: float,
        T: float,
        sigma: float,
        r: float = None,
    ) -> Dict[str, float]:
        """Calculate all Greeks"""
        if r is None:
            r = self.risk_free_rate

        return {
            "delta": self.calculate_delta(option_type, S, K, T, sigma, r),
            "gamma": self.calculate_gamma(S, K, T, sigma, r),
            "vega": self.calculate_vega(S, K, T, sigma, r),
            "theta": self.calculate_theta(option_type, S, K, T, sigma, r),
            "rho": r,  # Simplified rho
        }


class DynamicPositionSizer:
    """Dynamically sizes positions based on risk metrics"""

    def __init__(
        self,
        initial_capital: float = 100_000,
        max_risk_per_trade: float = 0.02,  # 2% max risk per trade
    ):
        self.initial_capital = initial_capital
        self.max_risk_per_trade = max_risk_per_trade

    def calculate_position_size(
        self,
        current_price: float,
        stop_loss_price: float,
        volatility: float,
        current_capital: float,
    ) -> int:
        """Calculate position size based on risk"""

        # Risk per share
        risk_per_share = abs(current_price - stop_loss_price)

        if risk_per_share == 0:
            risk_per_share = current_price * volatility * 0.5

        # Max position size based on capital
        max_risk_amount = current_capital * self.max_risk_per_trade
        position_size = max_risk_amount / risk_per_share

        return int(position_size)

    def adjust_for_volatility(
        self,
        base_position_size: int,
        historical_volatility: float,
        target_volatility: float = 0.20,
    ) -> int:
        """Adjust position size for volatility regime"""

        vol_adjustment = target_volatility / max(historical_volatility, 0.01)
        adjusted_size = base_position_size * vol_adjustment

        return int(adjusted_size)

    def adjust_for_correlation(
        self,
        base_position_size: int,
        portfolio_correlation: float,
    ) -> int:
        """Adjust position size based on portfolio correlation"""

        # Higher correlation = reduce size
        correlation_adjustment = 1 - (portfolio_correlation * 0.5)
        adjusted_size = base_position_size * max(correlation_adjustment, 0.3)

        return int(adjusted_size)


class CorrelationBasedHedger:
    """Identifies and implements correlation-based hedges"""

    def __init__(self):
        self.correlation_threshold = 0.7  # High correlation threshold
        self.hedge_effectiveness_threshold = 0.5

    def calculate_correlation_matrix(
        self,
        returns_data: Dict[str, pd.Series],
    ) -> pd.DataFrame:
        """Calculate correlation matrix of holdings"""

        df = pd.concat(returns_data.values(), axis=1, keys=returns_data.keys())
        return df.corr()

    def identify_correlated_pairs(
        self,
        correlation_matrix: pd.DataFrame,
        threshold: float = 0.7,
    ) -> List[Tuple[str, str, float]]:
        """Identify correlated symbol pairs"""

        pairs = []

        for i, sym1 in enumerate(correlation_matrix.columns):
            for j, sym2 in enumerate(correlation_matrix.columns):
                if i < j:  # Avoid duplicates
                    corr = correlation_matrix.loc[sym1, sym2]
                    if abs(corr) > threshold:
                        pairs.append((sym1, sym2, corr))

        return sorted(pairs, key=lambda x: abs(x[2]), reverse=True)

    def calculate_hedge_effectiveness(
        self,
        position_symbol: str,
        hedge_symbol: str,
        correlation: float,
        hedge_beta: float,
    ) -> float:
        """Calculate how effective a hedge would be"""

        # Effectiveness based on negative correlation and beta
        correlation_effectiveness = 1 - abs(correlation + 1) / 2
        beta_effectiveness = 1 - abs(hedge_beta)

        effectiveness = (correlation_effectiveness * 0.7 + beta_effectiveness * 0.3)
        return np.clip(effectiveness, 0, 1)

    def recommend_hedge(
        self,
        symbol: str,
        position_size: int,
        current_price: float,
        correlation_matrix: pd.DataFrame,
        symbol_prices: Dict[str, float],
    ) -> Optional[HedgeRecommendation]:
        """Recommend a hedge for a position"""

        # Find most negatively correlated symbol
        if symbol not in correlation_matrix.columns:
            return None

        correlations = correlation_matrix[symbol].copy()
        correlations = correlations[correlations.index != symbol]

        if correlations.empty:
            return None

        # Find lowest correlation (most negatively correlated)
        hedge_candidate = correlations.idxmin()
        correlation = correlations.min()

        # Calculate hedge quantity to offset 50% of risk
        hedge_size = int(position_size * 0.5)

        cost_bps = 5  # 5 bps transaction cost
        effectiveness = abs(correlation)  # -0.9 correlation = 0.9 effectiveness

        if effectiveness < self.hedge_effectiveness_threshold:
            return None

        return HedgeRecommendation(
            primary_symbol=symbol,
            hedge_symbol=hedge_candidate,
            hedge_type="short_correlated",
            quantity=hedge_size,
            cost_bps=cost_bps,
            effectiveness=effectiveness,
        )


class PortfolioRiskAnalyzer:
    """Analyzes aggregate portfolio risk"""

    def __init__(self):
        self.position_sizer = DynamicPositionSizer()
        self.hedger = CorrelationBasedHedger()

    def calculate_var(
        self,
        returns: pd.Series,
        confidence_level: float = 0.95,
    ) -> float:
        """Calculate Value at Risk"""
        return returns.quantile(1 - confidence_level)

    def calculate_cvar(
        self,
        returns: pd.Series,
        confidence_level: float = 0.95,
    ) -> float:
        """Calculate Conditional VaR (Expected Shortfall)"""
        var = self.calculate_var(returns, confidence_level)
        return returns[returns <= var].mean()

    def analyze_portfolio_risk(
        self,
        positions: Dict[str, int],  # symbol -> quantity
        prices: Dict[str, float],  # symbol -> price
        returns_data: Dict[str, pd.Series],  # symbol -> returns
        current_capital: float,
        sector_map: Dict[str, str],  # symbol -> sector
    ) -> PortfolioRisk:
        """Analyze aggregate portfolio risk"""

        # Calculate leverage
        total_long = sum(qty for qty in positions.values() if qty > 0)
        total_short = sum(abs(qty) for qty in positions.values() if qty < 0)
        gross_leverage = (total_long + total_short) / current_capital
        net_leverage = (total_long - total_short) / current_capital

        # Calculate correlation
        corr_matrix = self.hedger.calculate_correlation_matrix(returns_data)
        avg_correlation = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()

        # Sector concentration
        sector_positions = {}
        for symbol, qty in positions.items():
            sector = sector_map.get(symbol, "Unknown")
            sector_positions[sector] = sector_positions.get(sector, 0) + qty * prices.get(symbol, 0)

        total_position_value = sum(abs(qty * prices.get(symbol, 0)) for symbol, qty in positions.items())
        max_sector_concentration = max(
            (abs(v) / total_position_value) if total_position_value > 0 else 0
            for v in sector_positions.values()
        )

        # Symbol concentration
        max_symbol_concentration = max(
            (abs(qty * prices.get(symbol, 0)) / total_position_value) if total_position_value > 0 else 0
            for symbol, qty in positions.items()
        )

        # Portfolio returns
        portfolio_returns = self._calculate_portfolio_returns(positions, prices, returns_data)

        var_95 = self.calculate_var(portfolio_returns, 0.95)
        cvar_95 = self.calculate_cvar(portfolio_returns, 0.95)

        # Projected max drawdown
        equity_curve = (1 + portfolio_returns).cumprod()
        running_max = equity_curve.expanding().max()
        drawdowns = (equity_curve - running_max) / running_max
        max_drawdown = drawdowns.min()

        # Liquidity risk (simplified)
        liquidity_risk = max_symbol_concentration + (avg_correlation * 0.2)

        return PortfolioRisk(
            total_positions=len(positions),
            gross_leverage=gross_leverage,
            net_leverage=net_leverage,
            max_sector_concentration=max_sector_concentration,
            max_symbol_concentration=max_symbol_concentration,
            correlation_risk=avg_correlation,
            var_95=var_95 * 100,
            cvar_95=cvar_95 * 100,
            max_drawdown_projected=max_drawdown * 100,
            liquidity_risk_score=liquidity_risk,
        )

    def _calculate_portfolio_returns(
        self,
        positions: Dict[str, int],
        prices: Dict[str, float],
        returns_data: Dict[str, pd.Series],
    ) -> pd.Series:
        """Calculate portfolio returns"""

        total_value = sum(abs(qty * prices.get(symbol, 1)) for symbol, qty in positions.items())

        if total_value == 0:
            return pd.Series()

        # Weighted returns
        portfolio_ret = pd.Series(0.0, index=next(iter(returns_data.values())).index)

        for symbol, qty in positions.items():
            if symbol in returns_data:
                weight = (qty * prices.get(symbol, 1)) / total_value
                portfolio_ret += returns_data[symbol] * weight

        return portfolio_ret


class RiskLimits:
    """Enforces risk limits on trading"""

    def __init__(
        self,
        max_position_size: float = 0.05,  # Max 5% per symbol
        max_sector_concentration: float = 0.25,  # Max 25% per sector
        max_gross_leverage: float = 3.0,
        max_daily_loss: float = 0.05,  # 5% daily loss limit
        max_var: float = 0.10,  # 10% VaR limit
    ):
        self.max_position_size = max_position_size
        self.max_sector_concentration = max_sector_concentration
        self.max_gross_leverage = max_gross_leverage
        self.max_daily_loss = max_daily_loss
        self.max_var = max_var

    def check_position_limit(
        self,
        symbol: str,
        quantity: int,
        price: float,
        portfolio_value: float,
    ) -> Tuple[bool, str]:
        """Check if position respects size limits"""

        position_value = quantity * price
        position_pct = position_value / portfolio_value if portfolio_value > 0 else 0

        if position_pct > self.max_position_size:
            return False, f"Position exceeds {self.max_position_size*100:.1f}% limit"

        return True, "Position size OK"

    def check_leverage_limit(
        self,
        gross_leverage: float,
    ) -> Tuple[bool, str]:
        """Check gross leverage limit"""

        if gross_leverage > self.max_gross_leverage:
            return False, f"Leverage {gross_leverage:.2f}x exceeds {self.max_gross_leverage:.2f}x limit"

        return True, "Leverage OK"

    def check_var_limit(
        self,
        var_95: float,
    ) -> Tuple[bool, str]:
        """Check VaR limit"""

        if var_95 > self.max_var * 100:
            return False, f"VaR {var_95:.2f}% exceeds {self.max_var*100:.2f}% limit"

        return True, "VaR OK"

    def check_all_limits(
        self,
        portfolio_risk: PortfolioRisk,
        new_position_symbol: str,
        new_position_qty: int,
        new_position_price: float,
        portfolio_value: float,
    ) -> Tuple[bool, List[str]]:
        """Check all risk limits"""

        violations = []

        # Position size
        is_ok, msg = self.check_position_limit(new_position_symbol, new_position_qty, new_position_price, portfolio_value)
        if not is_ok:
            violations.append(msg)

        # Leverage
        new_gross_leverage = portfolio_risk.gross_leverage + (new_position_qty * new_position_price / portfolio_value)
        is_ok, msg = self.check_leverage_limit(new_gross_leverage)
        if not is_ok:
            violations.append(msg)

        # VaR
        is_ok, msg = self.check_var_limit(portfolio_risk.var_95)
        if not is_ok:
            violations.append(msg)

        return len(violations) == 0, violations
