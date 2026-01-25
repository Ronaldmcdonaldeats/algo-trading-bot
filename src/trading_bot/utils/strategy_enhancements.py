"""
Strategy Enhancements Module
Options strategies (covered calls, cash-secured puts), pairs trading, statistical arbitrage, crypto support.
Advanced multi-leg and alternative asset strategies for higher alpha.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from enum import Enum

logger = logging.getLogger(__name__)


class OptionStrategy(Enum):
    """Options strategies"""
    COVERED_CALL = "covered_call"  # Own stock + sell call
    CASH_SECURED_PUT = "cash_secured_put"  # Sell put, cash reserved
    BULL_CALL_SPREAD = "bull_call_spread"  # Buy call, sell higher strike call
    BEAR_PUT_SPREAD = "bear_put_spread"  # Sell put, buy lower strike put
    COLLAR = "collar"  # Sell call, buy put (downside protection)
    IRON_CONDOR = "iron_condor"  # 4-leg strategy
    STRADDLE = "straddle"  # Long call + long put (volatility play)


@dataclass
class OptionsLeg:
    """Single option contract leg"""
    symbol: str
    option_type: str  # "call" or "put"
    strike: float
    expiration: datetime
    quantity: int
    action: str  # "buy" or "sell"
    price: float
    greeks: Dict = None  # delta, gamma, vega, theta


@dataclass
class OptionStrategyOrder:
    """Multi-leg options strategy order"""
    strategy_id: str
    strategy_type: OptionStrategy
    legs: List[OptionsLeg]
    underlying_symbol: str
    created_at: datetime
    status: str  # "created", "submitted", "filled", "closed"
    max_loss: float
    max_profit: float
    breakeven_points: List[float]


@dataclass
class PairsTradingSignal:
    """Signal from pairs trading analysis"""
    symbol_a: str
    symbol_b: str
    correlation: float
    z_score: float
    signal_strength: float  # 0-1
    action: str  # "open_pair", "close_pair", "none"
    entry_prices: Tuple[float, float]
    stop_loss: float
    take_profit: float


@dataclass
class StatArbitrageOpportunity:
    """Statistical arbitrage opportunity"""
    symbol_set: List[str]
    strategy_type: str  # "mean_reversion", "momentum_divergence"
    expected_return: float
    win_probability: float
    kelly_fraction: float
    position_sizing: Dict[str, float]  # symbol -> position size


class CoveredCallWriter:
    """Generates covered call strategies"""

    def __init__(self, min_return_target: float = 0.02):  # 2% minimum return
        self.min_return_target = min_return_target

    def identify_opportunities(
        self,
        positions: Dict[str, int],  # symbol -> quantity
        prices: Dict[str, float],
        call_prices: Dict[str, float],  # symbol -> 1-month ATM call price
        days_to_expiration: int = 30,
    ) -> List[OptionStrategyOrder]:
        """Identify covered call opportunities"""

        opportunities = []

        for symbol, quantity in positions.items():
            if quantity <= 0:
                continue  # Can only sell calls against long positions

            current_price = prices.get(symbol, 0)
            call_price = call_prices.get(symbol, 0)

            if current_price <= 0 or call_price <= 0:
                continue

            # Calculate return from call premium
            premium_return = (call_price / current_price) * 100

            if premium_return < self.min_return_target:
                continue  # Not enough premium

            # Create short call leg
            call_leg = OptionsLeg(
                symbol=symbol,
                option_type="call",
                strike=current_price * 1.05,  # 5% OTM
                expiration=datetime.now() + timedelta(days=days_to_expiration),
                quantity=quantity // 100,  # 1 contract per 100 shares
                action="sell",
                price=call_price,
                greeks={"delta": -0.30, "theta": 0.02},  # Simplified
            )

            strategy = OptionStrategyOrder(
                strategy_id=f"CC_{symbol}_{int(datetime.now().timestamp())}",
                strategy_type=OptionStrategy.COVERED_CALL,
                legs=[call_leg],
                underlying_symbol=symbol,
                created_at=datetime.now(),
                status="created",
                max_loss=0,  # Protected by shares
                max_profit=(call_leg.strike - current_price) * quantity + (call_price * quantity),
                breakeven_points=[current_price - call_price],
            )

            opportunities.append(strategy)

        return opportunities


class CashSecuredPutSeller:
    """Generates cash-secured put strategies"""

    def __init__(self, cash_requirement: float = 1.0):  # 100% of strike * 100
        self.cash_requirement = cash_requirement

    def identify_opportunities(
        self,
        cash_available: float,
        put_prices: Dict[str, float],  # symbol -> put price
        symbols_to_own: List[str],
        target_prices: Dict[str, float],  # symbol -> desired entry price
        days_to_expiration: int = 30,
    ) -> List[OptionStrategyOrder]:
        """Identify cash-secured put opportunities"""

        opportunities = []

        for symbol in symbols_to_own:
            put_price = put_prices.get(symbol, 0)
            target_price = target_prices.get(symbol, 0)

            if put_price <= 0 or target_price <= 0:
                continue

            # Cash needed = strike * 100 shares
            strike = target_price * 0.95  # 5% below current
            cash_needed = strike * 100 * self.cash_requirement

            if cash_needed > cash_available:
                continue  # Not enough cash

            # Create short put leg
            put_leg = OptionsLeg(
                symbol=symbol,
                option_type="put",
                strike=strike,
                expiration=datetime.now() + timedelta(days=days_to_expiration),
                quantity=1,
                action="sell",
                price=put_price,
                greeks={"delta": -0.30, "theta": 0.02},
            )

            strategy = OptionStrategyOrder(
                strategy_id=f"CSP_{symbol}_{int(datetime.now().timestamp())}",
                strategy_type=OptionStrategy.CASH_SECURED_PUT,
                legs=[put_leg],
                underlying_symbol=symbol,
                created_at=datetime.now(),
                status="created",
                max_loss=(strike * 100) - (put_price * 100),
                max_profit=put_price * 100,
                breakeven_points=[strike - put_price],
            )

            opportunities.append(strategy)

        return opportunities


class PairsTrader:
    """Implements pairs trading strategy (long-short"""

    def __init__(self, z_score_threshold: float = 2.0):
        self.z_score_threshold = z_score_threshold
        self.pair_history: Dict[str, List] = {}

    def identify_pairs(
        self,
        returns_data: Dict[str, pd.Series],
        min_correlation: float = 0.7,
    ) -> List[Tuple[str, str, float]]:
        """Identify cointegrated pairs"""

        pairs = []

        symbols = list(returns_data.keys())

        for i, sym_a in enumerate(symbols):
            for sym_b in symbols[i+1:]:
                returns_a = returns_data[sym_a]
                returns_b = returns_data[sym_b]

                # Calculate correlation
                if len(returns_a) > 0 and len(returns_b) > 0:
                    correlation = returns_a.corr(returns_b)

                    if abs(correlation) > min_correlation:
                        pairs.append((sym_a, sym_b, correlation))

        return pairs

    def calculate_spread_zscore(
        self,
        prices_a: pd.Series,
        prices_b: pd.Series,
        lookback: int = 20,
    ) -> float:
        """Calculate z-score of price spread (cointegration)"""

        # Normalized spread
        ratio = prices_a / prices_b
        mean_ratio = ratio.tail(lookback).mean()
        std_ratio = ratio.tail(lookback).std()

        current_ratio = prices_a.iloc[-1] / prices_b.iloc[-1]

        if std_ratio == 0:
            return 0.0

        z_score = (current_ratio - mean_ratio) / std_ratio
        return z_score

    def generate_signal(
        self,
        symbol_a: str,
        symbol_b: str,
        prices_a: pd.Series,
        prices_b: pd.Series,
        correlation: float,
    ) -> PairsTradingSignal:
        """Generate pairs trading signal"""

        z_score = self.calculate_spread_zscore(prices_a, prices_b)

        # Trading logic
        action = "none"
        if z_score > self.z_score_threshold:
            action = "open_pair"  # Short A, long B
        elif z_score < -self.z_score_threshold:
            action = "open_pair"  # Long A, short B
        elif abs(z_score) < 0.5:
            action = "close_pair"  # Mean reversion complete

        signal_strength = min(abs(z_score) / self.z_score_threshold, 1.0)

        return PairsTradingSignal(
            symbol_a=symbol_a,
            symbol_b=symbol_b,
            correlation=correlation,
            z_score=z_score,
            signal_strength=signal_strength,
            action=action,
            entry_prices=(prices_a.iloc[-1], prices_b.iloc[-1]),
            stop_loss=z_score * 3.0,  # 3 sigma stop
            take_profit=z_score * 0.2,  # Close on mean reversion
        )


class StatisticalArbitragist:
    """Implements statistical arbitrage strategies"""

    def __init__(self):
        self.kelly_criterion = 0.25  # Use 1/4 Kelly

    def identify_mean_reversion_opportunities(
        self,
        returns_data: Dict[str, pd.Series],
        z_score_threshold: float = 2.0,
    ) -> List[StatArbitrageOpportunity]:
        """Identify mean reversion arbitrage opportunities"""

        opportunities = []

        for symbol, returns in returns_data.items():
            # Calculate z-score
            mean_return = returns.mean()
            std_return = returns.std()

            if std_return == 0:
                continue

            z_score = (returns.iloc[-1] - mean_return) / std_return

            if abs(z_score) > z_score_threshold:
                # Estimate win probability from z-score
                win_prob = 1 - (1 / (1 + np.exp(-abs(z_score))))

                # Kelly fraction
                edge = win_prob - (1 - win_prob)  # Win % - loss %
                kelly = edge * self.kelly_criterion if edge > 0 else 0

                opportunity = StatArbitrageOpportunity(
                    symbol_set=[symbol],
                    strategy_type="mean_reversion",
                    expected_return=edge * 0.02,  # 2% expected return if right
                    win_probability=win_prob,
                    kelly_fraction=kelly,
                    position_sizing={symbol: kelly},
                )

                opportunities.append(opportunity)

        return opportunities

    def identify_momentum_divergence(
        self,
        returns_data: Dict[str, pd.Series],
        lookback: int = 20,
    ) -> List[StatArbitrageOpportunity]:
        """Identify momentum divergence opportunities (one leads other)"""

        opportunities = []

        symbols = list(returns_data.keys())

        for i, sym_a in enumerate(symbols):
            for sym_b in symbols[i+1:]:
                returns_a = returns_data[sym_a].tail(lookback)
                returns_b = returns_data[sym_b].tail(lookback)

                # Leading indicator: sym_a momentum vs sym_b
                momentum_a = returns_a.tail(5).mean() - returns_a.head(5).mean()
                momentum_b = returns_b.tail(5).mean() - returns_b.head(5).mean()

                # If A is outperforming B recently but should lag
                if momentum_a > momentum_b * 1.5:
                    win_prob = 0.55  # Slight edge
                    kelly = 0.05 * self.kelly_criterion

                    opportunity = StatArbitrageOpportunity(
                        symbol_set=[sym_a, sym_b],
                        strategy_type="momentum_divergence",
                        expected_return=0.01,
                        win_probability=win_prob,
                        kelly_fraction=kelly,
                        position_sizing={sym_a: -kelly, sym_b: kelly},
                    )

                    opportunities.append(opportunity)

        return opportunities


class CryptoIntegration:
    """Crypto asset support for trading bot"""

    def __init__(self):
        self.supported_cryptos = ["BTC", "ETH", "SOL", "AVAX", "LINK"]
        self.crypto_markets = {}

    def is_crypto_symbol(self, symbol: str) -> bool:
        """Check if symbol is cryptocurrency"""
        return symbol.upper() in self.supported_cryptos

    def get_crypto_24h_volatility(self, symbol: str) -> float:
        """Get 24-hour volatility for crypto"""
        # Simplified - actual implementation would fetch from price API
        volatility_map = {
            "BTC": 0.45,  # 45% annualized from 24h
            "ETH": 0.55,
            "SOL": 0.75,
            "AVAX": 0.70,
            "LINK": 0.65,
        }
        return volatility_map.get(symbol.upper(), 0.50)

    def adjust_position_size_for_crypto(
        self,
        base_position_size: int,
        symbol: str,
    ) -> int:
        """Adjust position sizing for crypto volatility"""

        if not self.is_crypto_symbol(symbol):
            return base_position_size

        volatility = self.get_crypto_24h_volatility(symbol)
        target_volatility = 0.30  # Target 30% vol

        # Reduce position size for higher volatility
        adjustment = target_volatility / volatility

        return int(base_position_size * adjustment)

    def calculate_crypto_position_value(
        self,
        symbol: str,
        quantity: float,
        price: float,
    ) -> float:
        """Calculate position value with crypto precision"""
        # Crypto uses fractional shares
        return quantity * price

    def get_crypto_trading_hours(self) -> Tuple[datetime, datetime]:
        """Crypto trades 24/7"""
        # Return None for market hours check since crypto is 24/7
        return None, None


class StrategyFactory:
    """Factory for creating advanced strategies"""

    def __init__(self):
        self.covered_call_writer = CoveredCallWriter()
        self.put_seller = CashSecuredPutSeller()
        self.pairs_trader = PairsTrader()
        self.stat_arb = StatisticalArbitragist()
        self.crypto = CryptoIntegration()

    def create_covered_calls(
        self,
        positions: Dict[str, int],
        prices: Dict[str, float],
        call_prices: Dict[str, float],
    ) -> List[OptionStrategyOrder]:
        """Create covered call strategies"""
        return self.covered_call_writer.identify_opportunities(
            positions, prices, call_prices
        )

    def create_put_sells(
        self,
        cash_available: float,
        put_prices: Dict[str, float],
        target_symbols: List[str],
        target_prices: Dict[str, float],
    ) -> List[OptionStrategyOrder]:
        """Create cash-secured put strategies"""
        return self.put_seller.identify_opportunities(
            cash_available, put_prices, target_symbols, target_prices
        )

    def create_pairs_trades(
        self,
        returns_data: Dict[str, pd.Series],
    ) -> List[PairsTradingSignal]:
        """Create pairs trading positions"""
        pairs = self.pairs_trader.identify_pairs(returns_data)
        signals = []

        for sym_a, sym_b, corr in pairs:
            if sym_a in returns_data and sym_b in returns_data:
                signal = self.pairs_trader.generate_signal(
                    sym_a, sym_b,
                    returns_data[sym_a], returns_data[sym_b],
                    corr
                )
                signals.append(signal)

        return signals

    def create_stat_arb_trades(
        self,
        returns_data: Dict[str, pd.Series],
    ) -> List[StatArbitrageOpportunity]:
        """Create statistical arbitrage positions"""
        mr_opps = self.stat_arb.identify_mean_reversion_opportunities(returns_data)
        md_opps = self.stat_arb.identify_momentum_divergence(returns_data)
        return mr_opps + md_opps
