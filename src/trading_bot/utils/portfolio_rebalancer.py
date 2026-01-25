"""Portfolio rebalancing with correlation-aware sizing, sector rotation, and momentum allocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List
import logging
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class RebalanceFrequency(Enum):
    """Rebalancing frequency options."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class SectorClassification(Enum):
    """Sector classifications for portfolio balancing."""
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"
    ENERGY = "energy"
    UTILITIES = "utilities"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    CONSUMER_STAPLES = "consumer_staples"
    INDUSTRIALS = "industrials"
    MATERIALS = "materials"
    REAL_ESTATE = "real_estate"
    COMMUNICATION = "communication"


SECTOR_SYMBOLS = {
    SectorClassification.TECHNOLOGY: [
        'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'META', 'TSLA', 'AVGO', 'ASML',
        'ADBE', 'CRM', 'NFLX', 'INTC', 'AMD', 'QCOM', 'CSCO', 'INTU'
    ],
    SectorClassification.HEALTHCARE: [
        'JNJ', 'UNH', 'AZN', 'LLY', 'MRK', 'PFE', 'ABBV', 'TMO',
        'AMGN', 'GILD', 'BIIB', 'VRNA', 'MRNA', 'REGN'
    ],
    SectorClassification.FINANCIALS: [
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'BLK', 'SCHW', 'SPGI',
        'ICE', 'CME', 'CBOE', 'COIN', 'HOOD'
    ],
    SectorClassification.ENERGY: [
        'XOM', 'CVX', 'COP', 'EOG', 'MPC', 'PXD', 'SLB', 'HES',
        'OXY', 'FANG', 'MRO', 'DVN'
    ],
    SectorClassification.INDUSTRIALS: [
        'GE', 'BA', 'CAT', 'LMT', 'HON', 'RTX', 'NOC', 'GD',
        'LUV', 'UAL', 'DAL', 'ALK', 'CPAC'
    ],
    SectorClassification.CONSUMER_DISCRETIONARY: [
        'AMZN', 'TM', 'GM', 'F', 'MCD', 'NKE', 'SBUX', 'HD',
        'LOW', 'DRI', 'RCL', 'CCL', 'MAR', 'CMG'
    ],
    SectorClassification.UTILITIES: [
        'NEE', 'DUK', 'SO', 'AEP', 'XEL', 'EXC', 'WEC', 'CMS',
        'ED', 'PEG', 'PPL', 'AES', 'AWK'
    ],
}


@dataclass
class PortfolioPosition:
    """Single portfolio position."""
    symbol: str
    quantity: int
    entry_price: float
    current_price: float
    sector: SectorClassification
    momentum_score: float = 0.0  # -1 to 1
    correlation: float = 0.0  # correlation to portfolio
    target_allocation: float = 0.0  # % of portfolio
    
    @property
    def value(self) -> float:
        """Current position value."""
        return self.quantity * self.current_price
    
    @property
    def pnl(self) -> float:
        """Unrealized P&L."""
        return (self.current_price - self.entry_price) * self.quantity
    
    @property
    def pnl_pct(self) -> float:
        """Unrealized P&L percentage."""
        if self.entry_price == 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price * 100


@dataclass
class RebalanceAction:
    """Single rebalancing action."""
    symbol: str
    action: str  # 'BUY', 'SELL', 'HOLD'
    quantity_change: int
    reason: str
    priority: int  # 1 (high) to 5 (low)
    sector: SectorClassification
    estimated_cost: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


class SectorBalancer:
    """Manages sector allocation within portfolio."""
    
    def __init__(self, sector_limits: Optional[Dict[SectorClassification, float]] = None):
        """Initialize sector balancer.
        
        Args:
            sector_limits: Max allocation % per sector (default: 25% each)
        """
        self.sector_limits = sector_limits or {
            sector: 25.0 for sector in SectorClassification
        }
        self.sector_allocations = defaultdict(float)
    
    def get_sector_allocation(self, positions: List[PortfolioPosition], 
                            total_value: float) -> Dict[SectorClassification, float]:
        """Calculate current sector allocations.
        
        Args:
            positions: List of portfolio positions
            total_value: Total portfolio value
            
        Returns:
            Dict of sector -> allocation %
        """
        allocations = defaultdict(float)
        
        for pos in positions:
            allocation = (pos.value / total_value * 100) if total_value > 0 else 0.0
            allocations[pos.sector] += allocation
        
        return dict(allocations)
    
    def get_sector_rebalancing_actions(
        self, positions: List[PortfolioPosition], total_value: float
    ) -> List[RebalanceAction]:
        """Get rebalancing actions to normalize sector allocations.
        
        Args:
            positions: List of portfolio positions
            total_value: Total portfolio value
            
        Returns:
            List of rebalancing actions
        """
        actions = []
        allocations = self.get_sector_allocation(positions, total_value)
        
        # Identify over/under-allocated sectors
        for sector, limit in self.sector_limits.items():
            current = allocations.get(sector, 0.0)
            
            if current > limit:
                # Reduce sector allocation
                excess = current - limit
                sector_value = current / 100 * total_value
                reduction_amount = excess / 100 * total_value
                
                # Find positions to sell
                sector_positions = [p for p in positions if p.sector == sector]
                sector_positions.sort(key=lambda x: x.momentum_score)  # Sell lowest momentum first
                
                for pos in sector_positions:
                    if reduction_amount <= 0:
                        break
                    
                    sell_qty = min(
                        pos.quantity,
                        int(reduction_amount / pos.current_price)
                    )
                    
                    actions.append(RebalanceAction(
                        symbol=pos.symbol,
                        action='SELL',
                        quantity_change=-sell_qty,
                        reason=f"Sector {sector.value} over-allocated ({current:.1f}% > {limit:.1f}%)",
                        priority=1,
                        sector=sector,
                        estimated_cost=sell_qty * pos.current_price
                    ))
                    
                    reduction_amount -= sell_qty * pos.current_price
        
        return actions


class CorrelationOptimizer:
    """Optimizes portfolio based on correlation analysis."""
    
    def __init__(self, correlation_threshold: float = 0.75):
        """Initialize correlation optimizer.
        
        Args:
            correlation_threshold: Max allowed correlation between positions
        """
        self.correlation_threshold = correlation_threshold
        self.correlations = {}
    
    def set_correlations(self, correlations: Dict[tuple, float]) -> None:
        """Set correlation matrix.
        
        Args:
            correlations: Dict of (symbol1, symbol2) -> correlation
        """
        self.correlations = correlations
    
    def get_redundant_positions(
        self, positions: List[PortfolioPosition]
    ) -> List[tuple]:
        """Find highly correlated positions that are redundant.
        
        Args:
            positions: List of portfolio positions
            
        Returns:
            List of (symbol1, symbol2, correlation) tuples
        """
        redundant = []
        symbols = [p.symbol for p in positions]
        
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i+1:]:
                key = (sym1, sym2) if sym1 < sym2 else (sym2, sym1)
                corr = self.correlations.get(key, 0.0)
                
                if abs(corr) > self.correlation_threshold:
                    redundant.append((sym1, sym2, corr))
        
        return redundant
    
    def get_diversification_actions(
        self, positions: List[PortfolioPosition]
    ) -> List[RebalanceAction]:
        """Get actions to reduce correlation/improve diversification.
        
        Args:
            positions: List of portfolio positions
            
        Returns:
            List of rebalancing actions
        """
        actions = []
        redundant = self.get_redundant_positions(positions)
        
        # For each redundant pair, reduce the weaker position
        for sym1, sym2, corr in redundant:
            pos1 = next((p for p in positions if p.symbol == sym1), None)
            pos2 = next((p for p in positions if p.symbol == sym2), None)
            
            if not pos1 or not pos2:
                continue
            
            # Keep higher momentum, reduce lower
            if pos1.momentum_score < pos2.momentum_score:
                actions.append(RebalanceAction(
                    symbol=sym1,
                    action='REDUCE',
                    quantity_change=int(-pos1.quantity * 0.5),
                    reason=f"High correlation ({corr:.2f}) with {sym2}",
                    priority=2,
                    sector=pos1.sector,
                    estimated_cost=pos1.value * 0.5
                ))
            else:
                actions.append(RebalanceAction(
                    symbol=sym2,
                    action='REDUCE',
                    quantity_change=int(-pos2.quantity * 0.5),
                    reason=f"High correlation ({corr:.2f}) with {sym1}",
                    priority=2,
                    sector=pos2.sector,
                    estimated_cost=pos2.value * 0.5
                ))
        
        return actions


class MomentumAllocator:
    """Allocates capital based on momentum scores."""
    
    def __init__(self, min_allocation_pct: float = 0.5, 
                 max_allocation_pct: float = 5.0):
        """Initialize momentum allocator.
        
        Args:
            min_allocation_pct: Minimum allocation to single position
            max_allocation_pct: Maximum allocation to single position
        """
        self.min_allocation_pct = min_allocation_pct
        self.max_allocation_pct = max_allocation_pct
    
    def calculate_momentum_weights(
        self, positions: List[PortfolioPosition]
    ) -> Dict[str, float]:
        """Calculate position weights based on momentum.
        
        Args:
            positions: List of portfolio positions
            
        Returns:
            Dict of symbol -> target weight %
        """
        if not positions:
            return {}
        
        # Normalize momentum scores to 0-1 range
        momentum_scores = [max(0, p.momentum_score) for p in positions]
        total_momentum = sum(momentum_scores)
        
        if total_momentum == 0:
            # Equal weight if no positive momentum
            equal_weight = 100.0 / len(positions)
            return {p.symbol: equal_weight for p in positions}
        
        # Weight by momentum
        weights = {}
        for pos, score in zip(positions, momentum_scores):
            weight = (score / total_momentum) * 100
            # Apply min/max constraints
            weight = max(self.min_allocation_pct, 
                        min(self.max_allocation_pct, weight))
            weights[pos.symbol] = weight
        
        # Renormalize to sum to 100
        total = sum(weights.values())
        weights = {k: (v / total * 100) for k, v in weights.items()}
        
        return weights
    
    def get_momentum_rebalancing_actions(
        self, positions: List[PortfolioPosition], total_value: float
    ) -> List[RebalanceAction]:
        """Get rebalancing actions based on momentum.
        
        Args:
            positions: List of portfolio positions
            total_value: Total portfolio value
            
        Returns:
            List of rebalancing actions
        """
        actions = []
        target_weights = self.calculate_momentum_weights(positions)
        
        for pos in positions:
            target_weight = target_weights.get(pos.symbol, 0.0)
            current_weight = (pos.value / total_value * 100) if total_value > 0 else 0.0
            diff = target_weight - current_weight
            
            if abs(diff) > 0.5:  # Only rebalance if > 0.5% difference
                target_value = (target_weight / 100) * total_value
                target_qty = int(target_value / pos.current_price)
                qty_change = target_qty - pos.quantity
                
                action_type = 'BUY' if qty_change > 0 else 'SELL'
                
                actions.append(RebalanceAction(
                    symbol=pos.symbol,
                    action=action_type,
                    quantity_change=qty_change,
                    reason=f"Momentum rebalance: target {target_weight:.1f}% vs {current_weight:.1f}%",
                    priority=3,
                    sector=pos.sector,
                    estimated_cost=abs(qty_change * pos.current_price)
                ))
        
        return actions


class PortfolioRebalancer:
    """Main portfolio rebalancing engine."""
    
    def __init__(
        self,
        frequency: RebalanceFrequency = RebalanceFrequency.DAILY,
        sector_limits: Optional[Dict[SectorClassification, float]] = None,
        correlation_threshold: float = 0.75
    ):
        """Initialize portfolio rebalancer.
        
        Args:
            frequency: Rebalancing frequency
            sector_limits: Sector allocation limits
            correlation_threshold: Max correlation threshold
        """
        self.frequency = frequency
        self.sector_balancer = SectorBalancer(sector_limits)
        self.correlation_optimizer = CorrelationOptimizer(correlation_threshold)
        self.momentum_allocator = MomentumAllocator()
        self.last_rebalance = None
        self.rebalance_history = []
    
    def should_rebalance(self) -> bool:
        """Check if rebalancing should occur based on frequency.
        
        Returns:
            True if should rebalance
        """
        if self.last_rebalance is None:
            return True
        
        from datetime import timedelta
        now = datetime.utcnow()
        
        if self.frequency == RebalanceFrequency.DAILY:
            return (now - self.last_rebalance).days >= 1
        elif self.frequency == RebalanceFrequency.WEEKLY:
            return (now - self.last_rebalance).days >= 7
        elif self.frequency == RebalanceFrequency.MONTHLY:
            return (now - self.last_rebalance).days >= 30
        elif self.frequency == RebalanceFrequency.QUARTERLY:
            return (now - self.last_rebalance).days >= 90
        
        return False
    
    def generate_rebalance_plan(
        self, positions: List[PortfolioPosition], total_value: float
    ) -> List[RebalanceAction]:
        """Generate complete rebalancing plan.
        
        Args:
            positions: List of portfolio positions
            total_value: Total portfolio value
            
        Returns:
            List of rebalancing actions
        """
        actions = []
        
        # Sector balancing
        actions.extend(
            self.sector_balancer.get_sector_rebalancing_actions(positions, total_value)
        )
        
        # Correlation optimization
        actions.extend(
            self.correlation_optimizer.get_diversification_actions(positions)
        )
        
        # Momentum-based allocation
        actions.extend(
            self.momentum_allocator.get_momentum_rebalancing_actions(positions, total_value)
        )
        
        # Sort by priority
        actions.sort(key=lambda x: x.priority)
        
        return actions
    
    def execute_rebalance(
        self, positions: List[PortfolioPosition], total_value: float
    ) -> Dict:
        """Execute rebalancing plan.
        
        Args:
            positions: List of portfolio positions
            total_value: Total portfolio value
            
        Returns:
            Execution summary
        """
        if not self.should_rebalance():
            return {"status": "skipped", "reason": "Not yet time to rebalance"}
        
        actions = self.generate_rebalance_plan(positions, total_value)
        
        self.last_rebalance = datetime.utcnow()
        self.rebalance_history.append({
            "timestamp": self.last_rebalance,
            "actions": actions,
            "portfolio_value": total_value
        })
        
        logger.info(f"Generated rebalance plan: {len(actions)} actions")
        
        return {
            "status": "executed",
            "actions": actions,
            "total_actions": len(actions),
            "estimated_trades": len([a for a in actions if a.action != 'HOLD']),
            "timestamp": self.last_rebalance
        }
    
    def get_rebalance_summary(self) -> Dict:
        """Get rebalancing summary statistics.
        
        Returns:
            Summary dict
        """
        return {
            "frequency": self.frequency.value,
            "last_rebalance": self.last_rebalance,
            "total_rebalances": len(self.rebalance_history),
            "correlation_threshold": self.correlation_optimizer.correlation_threshold,
        }
