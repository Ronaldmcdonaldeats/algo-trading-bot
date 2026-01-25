"""
Options hedging strategies for downside protection.
Implements protective puts and collars to manage portfolio risk.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import numpy as np


@dataclass
class OptionsPriceEstimate:
    """Simple Black-Scholes option price estimate"""
    call_price: float
    put_price: float
    implied_vol: float


@dataclass
class HedgePosition:
    """Hedging position (put or collar)"""
    symbol: str
    entry_date: datetime
    position_qty: int  # Shares hedged
    position_price: float  # Entry price of stock
    
    hedge_type: str  # "protective_put" or "collar"
    strike_price: float  # Put strike (protection level)
    hedge_cost: float  # Total cost of hedge
    cost_pct: float  # Hedge cost as % of position value
    
    upside_cap: Optional[float] = None  # For collar
    breakeven: float = 0.0  # Where hedge breaks even
    
    days_to_expiry: int = 30
    notes: str = ""


class OptionsHedger:
    """
    Options hedging engine.
    Implements protective puts and collars for downside protection.
    """
    
    def __init__(
        self,
        hedge_threshold: float = -2.0,  # Hedge if position down 2%
        put_strike_pct: float = 0.95,  # Put strike at 95% of price
        collar_call_pct: float = 1.05,  # Call strike at 105% for collar
        max_hedge_cost_pct: float = 1.0,  # Max 1% cost for hedge
    ):
        self.hedge_threshold = hedge_threshold
        self.put_strike_pct = put_strike_pct
        self.collar_call_pct = collar_call_pct
        self.max_hedge_cost_pct = max_hedge_cost_pct
        
        self.active_hedges: Dict[str, HedgePosition] = {}
        self.hedge_history: List[HedgePosition] = []
    
    def calculate_option_price(
        self,
        spot_price: float,
        strike_price: float,
        days_to_expiry: int = 30,
        volatility: float = 0.25,
        is_call: bool = True,
        risk_free_rate: float = 0.04,
    ) -> float:
        """
        Simplified Black-Scholes option pricing.
        Uses logarithmic approximation for speed.
        """
        if days_to_expiry <= 0:
            return max(0, spot_price - strike_price) if is_call else max(0, strike_price - spot_price)
        
        t = days_to_expiry / 365.0
        
        # Intrinsic value
        intrinsic = max(0, spot_price - strike_price) if is_call else max(0, strike_price - spot_price)
        
        # Time value component
        moneyness = np.log(spot_price / strike_price) if strike_price > 0 else 0
        
        # Simplified formula: time decay and volatility impact
        time_value = volatility * spot_price * np.sqrt(t) * 0.4
        
        # For ITM options, reduce time value
        if is_call and spot_price > strike_price:
            time_value *= (1.0 - (spot_price - strike_price) / spot_price)
        elif not is_call and strike_price > spot_price:
            time_value *= (1.0 - (strike_price - spot_price) / spot_price)
        
        option_price = intrinsic + time_value
        
        return float(np.clip(option_price, 0, spot_price * 2))
    
    def estimate_hedge_cost(
        self,
        position_qty: int,
        position_price: float,
        volatility: float = 0.25,
        hedge_type: str = "protective_put",
    ) -> Optional[OptionsPriceEstimate]:
        """
        Estimate cost of hedging a position
        
        Args:
            position_qty: Number of shares
            position_price: Current stock price
            volatility: Implied volatility (annual)
            hedge_type: "protective_put" or "collar"
            
        Returns:
            OptionsPriceEstimate with costs
        """
        if position_qty <= 0 or position_price <= 0:
            return None
        
        # Put strike at 95% of current price
        put_strike = position_price * 0.95
        
        # Calculate put cost (downside protection)
        put_price = self.calculate_option_price(
            spot_price=position_price,
            strike_price=put_strike,
            volatility=volatility,
            is_call=False,
        )
        
        if hedge_type == "protective_put":
            # Just buy the put
            total_cost = put_price * position_qty
            call_price = 0.0
        else:
            # Collar: buy put, sell call at 105%
            call_strike = position_price * 1.05
            call_price = self.calculate_option_price(
                spot_price=position_price,
                strike_price=call_strike,
                volatility=volatility,
                is_call=True,
            )
            
            # Net cost: put cost minus call credit
            total_cost = (put_price - call_price) * position_qty
        
        return OptionsPriceEstimate(
            call_price=float(call_price),
            put_price=float(put_price),
            implied_vol=float(volatility),
        )
    
    def should_hedge_position(
        self,
        symbol: str,
        position_qty: int,
        entry_price: float,
        current_price: float,
    ) -> bool:
        """
        Determine if position should be hedged
        
        Args:
            symbol: Stock symbol
            position_qty: Number of shares
            entry_price: Entry price
            current_price: Current price
            
        Returns:
            True if position should be hedged
        """
        if symbol in self.active_hedges:
            return False  # Already hedged
        
        if position_qty <= 0:
            return False  # No position
        
        # Check if position is underwater
        pnl_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
        
        # Hedge if loss exceeds threshold
        return pnl_pct <= self.hedge_threshold
    
    def create_protective_put(
        self,
        symbol: str,
        position_qty: int,
        entry_price: float,
        current_price: float,
        volatility: float = 0.25,
    ) -> Optional[HedgePosition]:
        """
        Create protective put hedge
        
        Args:
            symbol: Stock symbol
            position_qty: Number of shares
            entry_price: Entry price of stock
            current_price: Current stock price
            volatility: Implied volatility
            
        Returns:
            HedgePosition or None if not feasible
        """
        # Calculate option price
        put_strike = current_price * self.put_strike_pct
        put_price = self.calculate_option_price(
            spot_price=current_price,
            strike_price=put_strike,
            volatility=volatility,
            is_call=False,
        )
        
        total_cost = put_price * position_qty
        cost_pct = (total_cost / (current_price * position_qty)) * 100 if position_qty > 0 else 0
        
        # Don't hedge if too expensive
        if cost_pct > self.max_hedge_cost_pct:
            return None
        
        hedge = HedgePosition(
            symbol=symbol,
            entry_date=datetime.now(),
            position_qty=position_qty,
            position_price=current_price,
            hedge_type="protective_put",
            strike_price=put_strike,
            hedge_cost=total_cost,
            cost_pct=cost_pct,
            breakeven=current_price - put_price,
            notes=f"Protects against downside below {put_strike:.2f}",
        )
        
        self.active_hedges[symbol] = hedge
        self.hedge_history.append(hedge)
        
        return hedge
    
    def create_collar(
        self,
        symbol: str,
        position_qty: int,
        entry_price: float,
        current_price: float,
        volatility: float = 0.25,
    ) -> Optional[HedgePosition]:
        """
        Create collar (buy put, sell call)
        
        Args:
            symbol: Stock symbol
            position_qty: Number of shares
            entry_price: Entry price of stock
            current_price: Current stock price
            volatility: Implied volatility
            
        Returns:
            HedgePosition or None if not feasible
        """
        # Put strike at 95%
        put_strike = current_price * self.put_strike_pct
        put_price = self.calculate_option_price(
            spot_price=current_price,
            strike_price=put_strike,
            volatility=volatility,
            is_call=False,
        )
        
        # Call strike at 105%
        call_strike = current_price * self.collar_call_pct
        call_price = self.calculate_option_price(
            spot_price=current_price,
            strike_price=call_strike,
            volatility=volatility,
            is_call=True,
        )
        
        # Net cost
        net_cost = (put_price - call_price) * position_qty
        net_cost_pct = (net_cost / (current_price * position_qty)) * 100 if position_qty > 0 else 0
        
        # Collar should be cheap (often free or credit)
        if net_cost_pct > self.max_hedge_cost_pct:
            return None
        
        hedge = HedgePosition(
            symbol=symbol,
            entry_date=datetime.now(),
            position_qty=position_qty,
            position_price=current_price,
            hedge_type="collar",
            strike_price=put_strike,
            upside_cap=call_strike,
            hedge_cost=net_cost,
            cost_pct=net_cost_pct,
            breakeven=current_price - put_price + call_price,
            notes=f"Put floor at {put_strike:.2f}, call cap at {call_strike:.2f}",
        )
        
        self.active_hedges[symbol] = hedge
        self.hedge_history.append(hedge)
        
        return hedge
    
    def evaluate_hedge(
        self,
        hedge: HedgePosition,
        current_price: float,
    ) -> Dict[str, float]:
        """
        Evaluate hedge payoff at current price
        
        Args:
            hedge: HedgePosition to evaluate
            current_price: Current stock price
            
        Returns:
            Dict with P&L metrics
        """
        # Unhedged position P&L
        unhedged_pnl = (current_price - hedge.position_price) * hedge.position_qty
        unhedged_return = ((current_price - hedge.position_price) / hedge.position_price) * 100 if hedge.position_price > 0 else 0
        
        if hedge.hedge_type == "protective_put":
            # Put payoff: max(strike - price, 0)
            put_payoff = max(hedge.strike_price - current_price, 0)
            hedged_price = min(current_price, hedge.strike_price)
        else:  # collar
            # Put payoff: max(strike - price, 0)
            put_payoff = max(hedge.strike_price - current_price, 0)
            # Call payoff: -max(price - strike, 0)
            call_payoff = -max(current_price - hedge.upside_cap, 0)
            
            # Hedged return capped at upside
            hedged_price = min(current_price, hedge.upside_cap)
            hedged_price = max(hedged_price, hedge.strike_price)
        
        hedged_pnl = (hedged_price - hedge.position_price) * hedge.position_qty - hedge.hedge_cost
        hedged_return = ((hedged_price - hedge.position_price) / hedge.position_price) * 100 if hedge.position_price > 0 else 0
        
        # Protection benefit
        protection_benefit = max(0, unhedged_pnl - hedged_pnl)
        
        return {
            "unhedged_pnl": unhedged_pnl,
            "unhedged_return": unhedged_return,
            "hedged_pnl": hedged_pnl,
            "hedged_return": hedged_return,
            "hedge_cost": hedge.hedge_cost,
            "protection_benefit": protection_benefit,
        }
    
    def print_summary(self):
        """Print hedging summary"""
        if not self.active_hedges:
            print("[HEDGING] No active hedges")
            return
        
        print("\n[OPTIONS HEDGING REPORT]")
        print(f"  Active hedges: {len(self.active_hedges)}")
        
        total_protected = 0
        total_cost = 0
        
        for symbol, hedge in self.active_hedges.items():
            position_value = hedge.position_qty * hedge.position_price
            total_protected += position_value
            total_cost += hedge.hedge_cost
            
            print(f"  {symbol}:")
            print(f"    Type: {hedge.hedge_type} | Shares: {hedge.position_qty} | Cost: ${hedge.hedge_cost:.2f} ({hedge.cost_pct:.2f}%)")
            print(f"    Strike: ${hedge.strike_price:.2f}", end="")
            if hedge.upside_cap:
                print(f" | Call cap: ${hedge.upside_cap:.2f}", end="")
            print()
        
        print(f"\n  Total protected: ${total_protected:,.0f} | Total hedge cost: ${total_cost:,.0f}")
