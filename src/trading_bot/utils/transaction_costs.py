"""Transaction cost optimization with slippage modeling and commission adjustment."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List
import logging
import numpy as np

logger = logging.getLogger(__name__)


class ExecutionVenue(Enum):
    """Execution venue types."""
    MARKET_ORDER = "market_order"
    LIMIT_ORDER = "limit_order"
    VWAP = "vwap"
    TWAP = "twap"
    ALGO = "algo"


class MarketCondition(Enum):
    """Market conditions affecting execution costs."""
    NORMAL = "normal"
    MODERATE = "moderate"
    VOLATILE = "volatile"
    CRISIS = "crisis"


@dataclass
class SlippageModel:
    """Models expected slippage based on market conditions."""
    base_slippage: float = 0.001  # 0.1% base slippage
    volume_sensitivity: float = 0.0005  # Additional % per million shares/day
    volatility_sensitivity: float = 0.0002  # Additional % per 1% volatility
    spread_multiplier: float = 1.5  # Times bid-ask spread
    market_impact_factor: float = 0.0001  # Market impact coefficient
    
    def calculate_slippage(
        self,
        order_size: int,
        daily_volume: int,
        volatility: float,
        bid_ask_spread: float,
        market_condition: MarketCondition = MarketCondition.NORMAL
    ) -> float:
        """Calculate expected slippage.
        
        Args:
            order_size: Order size in shares
            daily_volume: Daily volume in shares
            volatility: Annualized volatility (%)
            bid_ask_spread: Bid-ask spread (%)
            market_condition: Current market condition
            
        Returns:
            Expected slippage as %
        """
        # Base slippage
        slippage = self.base_slippage
        
        # Volume impact
        if daily_volume > 0:
            volume_ratio = order_size / daily_volume
            slippage += self.volume_sensitivity * (volume_ratio * 1_000_000)
        
        # Volatility impact
        slippage += self.volatility_sensitivity * volatility
        
        # Bid-ask spread impact
        slippage += bid_ask_spread * self.spread_multiplier
        
        # Market condition multiplier
        condition_multipliers = {
            MarketCondition.NORMAL: 1.0,
            MarketCondition.MODERATE: 1.5,
            MarketCondition.VOLATILE: 2.5,
            MarketCondition.CRISIS: 4.0,
        }
        
        slippage *= condition_multipliers.get(market_condition, 1.0)
        
        return slippage


@dataclass
class CommissionStructure:
    """Commission fee structure."""
    per_trade_fixed: float = 0.0  # $ per trade
    per_share: float = 0.0001  # $ per share
    percentage: float = 0.0  # % of trade value
    min_commission: float = 0.0  # Minimum commission per trade
    max_commission: float = np.inf  # Maximum commission per trade
    volume_discounts: Dict[int, float] = field(default_factory=dict)  # shares -> discount %
    
    def calculate_commission(self, order_size: int, price: float, order_value: float) -> float:
        """Calculate commission for order.
        
        Args:
            order_size: Order size in shares
            price: Share price
            order_value: Total order value
            
        Returns:
            Commission amount in $
        """
        # Fixed commission
        commission = self.per_trade_fixed
        
        # Per-share commission
        commission += self.per_share * order_size
        
        # Percentage commission
        commission += order_value * (self.percentage / 100)
        
        # Apply volume discounts
        for share_threshold in sorted(self.volume_discounts.keys(), reverse=True):
            if order_size >= share_threshold:
                discount = self.volume_discounts[share_threshold]
                commission *= (1 - discount / 100)
                break
        
        # Apply min/max limits
        commission = max(self.min_commission, min(commission, self.max_commission))
        
        return commission


@dataclass
class ExecutionCost:
    """Complete execution cost breakdown."""
    symbol: str
    order_size: int
    price: float
    slippage_amount: float
    commission_amount: float
    market_impact: float
    total_cost: float = field(default=0.0)
    total_cost_pct: float = field(default=0.0)
    
    def __post_init__(self):
        """Calculate totals."""
        self.total_cost = self.slippage_amount + self.commission_amount + self.market_impact
        order_value = self.order_size * self.price
        self.total_cost_pct = (self.total_cost / order_value * 100) if order_value > 0 else 0.0


class TransactionCostCalculator:
    """Calculates total transaction costs."""
    
    def __init__(
        self,
        slippage_model: Optional[SlippageModel] = None,
        commission_structure: Optional[CommissionStructure] = None
    ):
        """Initialize calculator.
        
        Args:
            slippage_model: Slippage model (default: standard)
            commission_structure: Commission structure (default: retail)
        """
        self.slippage_model = slippage_model or SlippageModel()
        self.commission_structure = commission_structure or CommissionStructure()
    
    def calculate_execution_cost(
        self,
        symbol: str,
        order_size: int,
        price: float,
        daily_volume: int,
        volatility: float,
        bid_ask_spread: float,
        market_condition: MarketCondition = MarketCondition.NORMAL,
    ) -> ExecutionCost:
        """Calculate total execution cost.
        
        Args:
            symbol: Stock symbol
            order_size: Order size in shares
            price: Share price
            daily_volume: Daily trading volume
            volatility: Annualized volatility
            bid_ask_spread: Bid-ask spread %
            market_condition: Market condition
            
        Returns:
            ExecutionCost breakdown
        """
        order_value = order_size * price
        
        # Calculate slippage
        slippage_pct = self.slippage_model.calculate_slippage(
            order_size, daily_volume, volatility, bid_ask_spread, market_condition
        )
        slippage_amount = order_value * (slippage_pct / 100)
        
        # Calculate commission
        commission_amount = self.commission_structure.calculate_commission(
            order_size, price, order_value
        )
        
        # Market impact
        market_impact = order_value * (self.slippage_model.market_impact_factor / 100) * (order_size / daily_volume if daily_volume > 0 else 0)
        
        return ExecutionCost(
            symbol=symbol,
            order_size=order_size,
            price=price,
            slippage_amount=slippage_amount,
            commission_amount=commission_amount,
            market_impact=market_impact,
        )
    
    def compare_execution_venues(
        self,
        symbol: str,
        order_size: int,
        price: float,
        daily_volume: int,
        volatility: float,
        bid_ask_spread: float,
        market_condition: MarketCondition = MarketCondition.NORMAL,
    ) -> Dict[str, ExecutionCost]:
        """Compare costs across execution venues.
        
        Args:
            symbol: Stock symbol
            order_size: Order size
            price: Share price
            daily_volume: Daily volume
            volatility: Volatility
            bid_ask_spread: Bid-ask spread
            market_condition: Market condition
            
        Returns:
            Dict of venue -> cost
        """
        base_cost = self.calculate_execution_cost(
            symbol, order_size, price, daily_volume, volatility, bid_ask_spread, market_condition
        )
        
        # Venue-specific adjustments
        costs = {
            'market_order': base_cost,
            'limit_order': ExecutionCost(
                symbol=symbol,
                order_size=order_size,
                price=price,
                slippage_amount=base_cost.slippage_amount * 0.5,  # 50% less slippage
                commission_amount=base_cost.commission_amount,
                market_impact=base_cost.market_impact * 0.5,
            ),
            'vwap': ExecutionCost(
                symbol=symbol,
                order_size=order_size,
                price=price,
                slippage_amount=base_cost.slippage_amount * 0.3,  # 70% less slippage
                commission_amount=base_cost.commission_amount * 1.1,  # 10% higher commission
                market_impact=base_cost.market_impact * 0.2,
            ),
            'algo': ExecutionCost(
                symbol=symbol,
                order_size=order_size,
                price=price,
                slippage_amount=base_cost.slippage_amount * 0.2,  # 80% less slippage
                commission_amount=base_cost.commission_amount * 1.5,  # 50% higher commission
                market_impact=base_cost.market_impact * 0.1,
            ),
        }
        
        return costs
    
    def find_optimal_venue(
        self,
        symbol: str,
        order_size: int,
        price: float,
        daily_volume: int,
        volatility: float,
        bid_ask_spread: float,
        market_condition: MarketCondition = MarketCondition.NORMAL,
    ) -> tuple[str, ExecutionCost]:
        """Find execution venue with minimum cost.
        
        Args:
            symbol: Stock symbol
            order_size: Order size
            price: Share price
            daily_volume: Daily volume
            volatility: Volatility
            bid_ask_spread: Bid-ask spread
            market_condition: Market condition
            
        Returns:
            (venue_name, cost)
        """
        costs = self.compare_execution_venues(
            symbol, order_size, price, daily_volume, volatility, bid_ask_spread, market_condition
        )
        
        optimal_venue = min(costs.items(), key=lambda x: x[1].total_cost)
        
        logger.info(f"Optimal venue for {symbol}: {optimal_venue[0]} (cost: ${optimal_venue[1].total_cost:.2f})")
        
        return optimal_venue


class CostAwareOrderSizer:
    """Adjusts order sizes based on transaction costs."""
    
    def __init__(self, calculator: TransactionCostCalculator):
        """Initialize sizer.
        
        Args:
            calculator: TransactionCostCalculator instance
        """
        self.calculator = calculator
    
    def adjust_position_size(
        self,
        target_shares: int,
        symbol: str,
        price: float,
        daily_volume: int,
        volatility: float,
        bid_ask_spread: float,
        max_cost_pct: float = 0.5,  # Max 0.5% cost
        market_condition: MarketCondition = MarketCondition.NORMAL,
    ) -> tuple[int, ExecutionCost]:
        """Adjust position size to keep costs under limit.
        
        Args:
            target_shares: Desired order size
            symbol: Stock symbol
            price: Share price
            daily_volume: Daily volume
            volatility: Volatility
            bid_ask_spread: Bid-ask spread
            max_cost_pct: Max cost as % of order value
            market_condition: Market condition
            
        Returns:
            (adjusted_shares, estimated_cost)
        """
        cost = self.calculator.calculate_execution_cost(
            symbol, target_shares, price, daily_volume, volatility, bid_ask_spread, market_condition
        )
        
        if cost.total_cost_pct <= max_cost_pct:
            return target_shares, cost
        
        # Binary search for optimal size
        low, high = 0, target_shares
        best_shares = 0
        best_cost = cost
        
        while low <= high:
            mid = (low + high) // 2
            mid_cost = self.calculator.calculate_execution_cost(
                symbol, mid, price, daily_volume, volatility, bid_ask_spread, market_condition
            )
            
            if mid_cost.total_cost_pct <= max_cost_pct:
                best_shares = mid
                best_cost = mid_cost
                low = mid + 1
            else:
                high = mid - 1
        
        logger.info(
            f"Adjusted {symbol} from {target_shares} to {best_shares} "
            f"(cost: {cost.total_cost_pct:.3f}% → {best_cost.total_cost_pct:.3f}%)"
        )
        
        return best_shares, best_cost
    
    def rank_symbols_by_cost(
        self,
        symbols: List[str],
        order_sizes: Dict[str, int],
        prices: Dict[str, float],
        daily_volumes: Dict[str, int],
        volatilities: Dict[str, float],
        bid_ask_spreads: Dict[str, float],
        market_condition: MarketCondition = MarketCondition.NORMAL,
    ) -> List[tuple[str, ExecutionCost]]:
        """Rank symbols by execution cost.
        
        Args:
            symbols: List of symbols
            order_sizes: Dict of symbol -> size
            prices: Dict of symbol -> price
            daily_volumes: Dict of symbol -> volume
            volatilities: Dict of symbol -> volatility
            bid_ask_spreads: Dict of symbol -> spread %
            market_condition: Market condition
            
        Returns:
            Sorted list of (symbol, cost) by total cost
        """
        costs = []
        
        for symbol in symbols:
            cost = self.calculator.calculate_execution_cost(
                symbol,
                order_sizes.get(symbol, 0),
                prices.get(symbol, 0),
                daily_volumes.get(symbol, 0),
                volatilities.get(symbol, 0),
                bid_ask_spreads.get(symbol, 0),
                market_condition
            )
            costs.append((symbol, cost))
        
        return sorted(costs, key=lambda x: x[1].total_cost_pct)


class CostAnalytics:
    """Analyzes transaction costs over time."""
    
    def __init__(self):
        """Initialize analytics."""
        self.execution_history: List[ExecutionCost] = []
        self.daily_costs: Dict[str, float] = {}
    
    def record_execution(self, cost: ExecutionCost) -> None:
        """Record executed trade.
        
        Args:
            cost: ExecutionCost
        """
        self.execution_history.append(cost)
        
        today = datetime.utcnow().date()
        today_key = str(today)
        self.daily_costs[today_key] = self.daily_costs.get(today_key, 0) + cost.total_cost
    
    def get_average_costs(self) -> Dict[str, float]:
        """Get average costs statistics.
        
        Returns:
            Dict with avg metrics
        """
        if not self.execution_history:
            return {}
        
        costs = np.array([e.total_cost_pct for e in self.execution_history])
        slippage = np.array([e.slippage_amount for e in self.execution_history])
        commission = np.array([e.commission_amount for e in self.execution_history])
        
        return {
            'avg_total_cost_pct': np.mean(costs),
            'median_total_cost_pct': np.median(costs),
            'max_total_cost_pct': np.max(costs),
            'avg_slippage': np.mean(slippage),
            'avg_commission': np.mean(commission),
            'total_executions': len(self.execution_history),
            'total_cost': np.sum([e.total_cost for e in self.execution_history]),
        }
    
    def get_daily_cost_summary(self) -> Dict[str, float]:
        """Get daily cost summary.
        
        Returns:
            Dict of date -> total cost
        """
        return self.daily_costs.copy()
    
    def estimate_annual_costs(self, annual_trades: int = 250) -> float:
        """Estimate annual transaction costs.
        
        Args:
            annual_trades: Expected annual trades
            
        Returns:
            Estimated annual cost
        """
        avg_metrics = self.get_average_costs()
        if not avg_metrics:
            return 0.0
        
        avg_cost = avg_metrics.get('avg_total_cost_pct', 0.0)
        portfolio_value = 100_000  # Assume 100k
        
        return (avg_cost / 100) * portfolio_value * annual_trades
