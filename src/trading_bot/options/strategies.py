"""Options Strategies - Covered calls, protective puts, spreads, Greeks calculation

Phase 5.3: Advanced options strategies for income and protection
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from enum import Enum
import math


class OptionType(Enum):
    CALL = "CALL"
    PUT = "PUT"


class StrategyType(Enum):
    COVERED_CALL = "COVERED_CALL"
    PROTECTIVE_PUT = "PROTECTIVE_PUT"
    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_CALL_SPREAD = "BEAR_CALL_SPREAD"
    BULL_PUT_SPREAD = "BULL_PUT_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    COLLAR = "COLLAR"
    STRADDLE = "STRADDLE"
    STRANGLE = "STRANGLE"


@dataclass
class Greeks:
    """Option Greeks - price sensitivity measures"""
    delta: float      # -1 to 1: Price sensitivity
    gamma: float      # Rate of delta change
    vega: float       # Volatility sensitivity
    theta: float      # Time decay
    rho: float        # Interest rate sensitivity


@dataclass
class OptionContract:
    """Option contract specification"""
    symbol: str
    option_type: OptionType
    strike_price: float
    expiration_date: datetime
    premium: float
    quantity: int = 1
    bid: float = 0.0
    ask: float = 0.0
    implied_volatility: float = 0.20


@dataclass
class OptionsStrategy:
    """Options strategy with multiple legs"""
    strategy_type: StrategyType
    underlying_symbol: str
    underlying_price: float
    legs: Dict[str, OptionContract]
    entry_date: datetime
    objective: str  # "INCOME", "PROTECTION", "DIRECTIONAL"
    max_profit: float
    max_loss: float
    breakeven: float
    probability_of_profit: float


class GreeksCalculator:
    """Calculate option Greeks using Black-Scholes model"""
    
    @staticmethod
    def d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d1 from Black-Scholes"""
        return (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    
    @staticmethod
    def d2(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate d2 from Black-Scholes"""
        d1 = GreeksCalculator.d1(S, K, T, r, sigma)
        return d1 - sigma * math.sqrt(T)
    
    @staticmethod
    def calculate_call_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Delta for call option (0 to 1)"""
        if T <= 0:
            return 1.0 if S > K else 0.0
        d1 = GreeksCalculator.d1(S, K, T, r, sigma)
        return 0.5 * (1 + math.erf(d1 / math.sqrt(2)))  # Approximation of N(d1)
    
    @staticmethod
    def calculate_put_delta(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Delta for put option (-1 to 0)"""
        call_delta = GreeksCalculator.calculate_call_delta(S, K, T, r, sigma)
        return call_delta - 1.0
    
    @staticmethod
    def calculate_gamma(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Gamma for both calls and puts (same)"""
        if T <= 0:
            return 0.0
        d1 = GreeksCalculator.d1(S, K, T, r, sigma)
        return math.exp(-0.5 * d1 ** 2) / (S * sigma * math.sqrt(2 * math.pi * T))
    
    @staticmethod
    def calculate_vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Vega per 1% change in volatility"""
        if T <= 0:
            return 0.0
        d1 = GreeksCalculator.d1(S, K, T, r, sigma)
        return S * math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi * T) / 100
    
    @staticmethod
    def calculate_theta(S: float, K: float, T: float, r: float, sigma: float, 
                       option_type: OptionType) -> float:
        """Theta per day"""
        if T <= 0:
            return 0.0
        d1 = GreeksCalculator.d1(S, K, T, r, sigma)
        d2 = GreeksCalculator.d2(S, K, T, r, sigma)
        
        if option_type == OptionType.CALL:
            theta = (-S * math.exp(-0.5 * d1 ** 2) * sigma / (2 * math.sqrt(2 * math.pi * T)) -
                    r * K * math.exp(-r * T) * (0.5 * (1 + math.erf(d2 / math.sqrt(2)))))
        else:
            theta = (-S * math.exp(-0.5 * d1 ** 2) * sigma / (2 * math.sqrt(2 * math.pi * T)) +
                    r * K * math.exp(-r * T) * (0.5 * (1 + math.erf(-d2 / math.sqrt(2)))))
        
        return theta / 365  # Convert to daily
    
    @staticmethod
    def calculate_greeks(S: float, K: float, T: float, r: float, 
                        sigma: float, option_type: OptionType) -> Greeks:
        """Calculate all Greeks"""
        if option_type == OptionType.CALL:
            delta = GreeksCalculator.calculate_call_delta(S, K, T, r, sigma)
        else:
            delta = GreeksCalculator.calculate_put_delta(S, K, T, r, sigma)
        
        gamma = GreeksCalculator.calculate_gamma(S, K, T, r, sigma)
        vega = GreeksCalculator.calculate_vega(S, K, T, r, sigma)
        theta = GreeksCalculator.calculate_theta(S, K, T, r, sigma, option_type)
        rho = 0.0  # Simplified - assume rates constant
        
        return Greeks(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)


class CoveredCallStrategy:
    """Covered Call - Own stock, sell call for income"""
    
    @staticmethod
    def create(symbol: str, stock_quantity: int, stock_price: float,
              call_strike: float, call_premium: float, 
              expiration_days: int = 30) -> OptionsStrategy:
        """Create covered call strategy"""
        
        expiration = datetime.now() + timedelta(days=expiration_days)
        
        call = OptionContract(
            symbol=symbol,
            option_type=OptionType.CALL,
            strike_price=call_strike,
            expiration_date=expiration,
            premium=call_premium,
            quantity=stock_quantity
        )
        
        # Max profit: called away at strike + premium
        max_profit = (call_strike - stock_price) * stock_quantity + call_premium * stock_quantity * 100
        
        # Max loss: stock to zero
        max_loss = stock_price * stock_quantity - call_premium * stock_quantity * 100
        
        # Breakeven
        breakeven = stock_price - (call_premium / 100)
        
        return OptionsStrategy(
            strategy_type=StrategyType.COVERED_CALL,
            underlying_symbol=symbol,
            underlying_price=stock_price,
            legs={'long_stock': call, 'short_call': call},
            entry_date=datetime.now(),
            objective="INCOME",
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            probability_of_profit=0.65  # Conservative estimate
        )


class ProtectiveputStrategy:
    """Protective Put - Own stock, buy put for downside protection"""
    
    @staticmethod
    def create(symbol: str, stock_quantity: int, stock_price: float,
              put_strike: float, put_premium: float,
              expiration_days: int = 30) -> OptionsStrategy:
        """Create protective put strategy"""
        
        expiration = datetime.now() + timedelta(days=expiration_days)
        
        put = OptionContract(
            symbol=symbol,
            option_type=OptionType.PUT,
            strike_price=put_strike,
            expiration_date=expiration,
            premium=put_premium,
            quantity=stock_quantity
        )
        
        # Max profit: unlimited upside
        max_profit = float('inf')
        
        # Max loss: premium paid + difference to strike
        max_loss = put_premium * stock_quantity * 100 + (stock_price - put_strike) * stock_quantity
        
        # Breakeven
        breakeven = stock_price + (put_premium / 100)
        
        return OptionsStrategy(
            strategy_type=StrategyType.PROTECTIVE_PUT,
            underlying_symbol=symbol,
            underlying_price=stock_price,
            legs={'long_stock': put, 'long_put': put},
            entry_date=datetime.now(),
            objective="PROTECTION",
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            probability_of_profit=0.70
        )


class BullCallSpreadStrategy:
    """Bull Call Spread - Buy call, sell higher call for defined risk/reward"""
    
    @staticmethod
    def create(symbol: str, long_strike: float, long_premium: float,
              short_strike: float, short_premium: float,
              expiration_days: int = 30, contracts: int = 1) -> OptionsStrategy:
        """Create bull call spread"""
        
        expiration = datetime.now() + timedelta(days=expiration_days)
        
        long_call = OptionContract(
            symbol=symbol, option_type=OptionType.CALL, strike_price=long_strike,
            expiration_date=expiration, premium=long_premium, quantity=contracts
        )
        
        short_call = OptionContract(
            symbol=symbol, option_type=OptionType.CALL, strike_price=short_strike,
            expiration_date=expiration, premium=short_premium, quantity=contracts
        )
        
        # Max profit: difference between strikes - net debit
        net_debit = (long_premium - short_premium) * contracts * 100
        max_profit = (short_strike - long_strike) * contracts * 100 - net_debit
        
        # Max loss: net debit paid
        max_loss = net_debit
        
        # Breakeven
        breakeven = long_strike + (long_premium - short_premium) / 100
        
        return OptionsStrategy(
            strategy_type=StrategyType.BULL_CALL_SPREAD,
            underlying_symbol=symbol,
            underlying_price=0,  # Not applicable
            legs={'long_call': long_call, 'short_call': short_call},
            entry_date=datetime.now(),
            objective="DIRECTIONAL",
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            probability_of_profit=0.55
        )


class CollarStrategy:
    """Collar - Long stock, buy put, sell call (zero or low cost protection)"""
    
    @staticmethod
    def create(symbol: str, stock_quantity: int, stock_price: float,
              put_strike: float, put_premium: float,
              call_strike: float, call_premium: float,
              expiration_days: int = 30) -> OptionsStrategy:
        """Create collar strategy"""
        
        expiration = datetime.now() + timedelta(days=expiration_days)
        
        put = OptionContract(
            symbol=symbol, option_type=OptionType.PUT, strike_price=put_strike,
            expiration_date=expiration, premium=put_premium, quantity=stock_quantity
        )
        
        call = OptionContract(
            symbol=symbol, option_type=OptionType.CALL, strike_price=call_strike,
            expiration_date=expiration, premium=call_premium, quantity=stock_quantity
        )
        
        net_cost = (put_premium - call_premium) * stock_quantity * 100
        
        # Max profit: capped at call strike
        max_profit = (call_strike - stock_price) * stock_quantity - net_cost
        
        # Max loss: protected at put strike
        max_loss = (stock_price - put_strike) * stock_quantity + net_cost
        
        # Breakeven
        breakeven = stock_price + net_cost / (stock_quantity * 100)
        
        return OptionsStrategy(
            strategy_type=StrategyType.COLLAR,
            underlying_symbol=symbol,
            underlying_price=stock_price,
            legs={'long_stock': put, 'long_put': put, 'short_call': call},
            entry_date=datetime.now(),
            objective="PROTECTION",
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven=breakeven,
            probability_of_profit=0.60
        )


class OptionsAnalyzer:
    """Analyze options strategies"""
    
    @staticmethod
    def analyze_strategy(strategy: OptionsStrategy, current_price: float,
                        volatility: float, days_to_expiration: int) -> Dict:
        """Analyze current strategy performance"""
        
        # Calculate Greeks for each leg
        greeks_by_leg = {}
        total_delta = 0
        total_gamma = 0
        total_vega = 0
        total_theta = 0
        
        T = days_to_expiration / 365.0
        r = 0.05  # Risk-free rate
        
        for leg_name, contract in strategy.legs.items():
            greeks = GreeksCalculator.calculate_greeks(
                S=current_price,
                K=contract.strike_price,
                T=T,
                r=r,
                sigma=volatility,
                option_type=contract.option_type
            )
            
            greeks_by_leg[leg_name] = {
                'delta': greeks.delta * contract.quantity,
                'gamma': greeks.gamma * contract.quantity,
                'vega': greeks.vega * contract.quantity,
                'theta': greeks.theta * contract.quantity,
            }
            
            total_delta += greeks.delta * contract.quantity
            total_gamma += greeks.gamma * contract.quantity
            total_vega += greeks.vega * contract.quantity
            total_theta += greeks.theta * contract.quantity
        
        # Current P&L (simplified)
        price_change = current_price - strategy.underlying_price
        pnl = price_change * 100  # Per contract
        
        return {
            'strategy': strategy.strategy_type.value,
            'objective': strategy.objective,
            'current_price': current_price,
            'underlying_price': strategy.underlying_price,
            'price_change': price_change,
            'max_profit': strategy.max_profit,
            'max_loss': strategy.max_loss,
            'breakeven': strategy.breakeven,
            'prob_of_profit': strategy.probability_of_profit,
            'greeks': {
                'total_delta': total_delta,
                'total_gamma': total_gamma,
                'total_vega': total_vega,
                'total_theta': total_theta,
            },
            'greeks_by_leg': greeks_by_leg,
            'estimated_pnl': pnl,
        }


class IncomeStrategy:
    """Generate income using covered calls"""
    
    @staticmethod
    def identify_covered_call_targets(stocks: Dict[str, Dict], 
                                     call_strike_offset: float = 0.05,
                                     min_premium: float = 0.50) -> list:
        """Identify candidates for covered call income strategy"""
        
        candidates = []
        
        for symbol, data in stocks.items():
            current_price = data['price']
            recent_high = data.get('52week_high', current_price * 1.5)
            
            # Target call strike 5% above current
            call_strike = current_price * (1 + call_strike_offset)
            
            # Estimate premium (simplified)
            estimated_premium = current_price * 0.02  # 2% of stock price
            
            if estimated_premium >= min_premium:
                candidates.append({
                    'symbol': symbol,
                    'current_price': current_price,
                    'call_strike': call_strike,
                    'estimated_premium': estimated_premium,
                    'annual_income': estimated_premium * 4,  # 4 cycles per year
                    'yield': (estimated_premium * 4) / current_price,
                })
        
        return sorted(candidates, key=lambda x: x['yield'], reverse=True)
