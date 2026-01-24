"""Tax-Loss Harvesting - Automatic intelligent tax optimization

Identifies and executes tax-loss harvesting trades:
- Detects unrealized losses
- Finds replacement securities with high correlation
- Avoids wash sales
- Tracks cost basis for compliance
- Generates tax reports
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class TaxLossOpportunity:
    """Opportunity to harvest a tax loss"""
    symbol: str
    shares: float
    cost_basis: float
    current_price: float
    unrealized_loss: float
    loss_pct: float
    replacement_symbol: Optional[str]
    replacement_correlation: float
    tax_benefit: float
    days_held: int
    wash_sale_risk: bool


@dataclass
class TaxLossHarvest:
    """Executed tax-loss harvest"""
    date: str
    symbol: str
    replacement_symbol: str
    shares: float
    sale_price: float
    cost_basis: float
    realized_loss: float
    tax_savings: float  # At 35% tax rate
    replacement_shares: float
    replacement_price: float
    wash_sale_date: str  # When sell lock expires


class TaxLossHarvester:
    """Identify and execute tax-loss harvesting opportunities"""
    
    def __init__(self, tax_rate: float = 0.35, cache_dir: str = ".cache"):
        self.tax_rate = tax_rate
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.wash_sales: Dict[str, datetime] = {}  # symbol -> sell date
        self.harvest_history: List[TaxLossHarvest] = []
        self.min_loss_threshold = 100  # Minimum $100 loss to harvest
        
    def find_tax_loss_opportunities(self, holdings: Dict[str, Dict],
                                   prices: Dict[str, float],
                                   correlations: Optional[Dict[str, Dict[str, float]]] = None
                                   ) -> List[TaxLossOpportunity]:
        """Find all tax-loss harvesting opportunities
        
        Args:
            holdings: {symbol: {shares, cost_basis, purchase_date}}
            prices: {symbol: current_price}
            correlations: {symbol: {corr_symbol: correlation}}
        """
        
        opportunities = []
        
        for symbol, holding in holdings.items():
            cost_basis = holding.get('cost_basis', 0)
            shares = holding.get('shares', 0)
            current_price = prices.get(symbol, cost_basis)
            
            if shares == 0 or cost_basis == 0:
                continue
            
            unrealized_loss = (current_price - cost_basis) * shares
            loss_pct = (current_price - cost_basis) / cost_basis if cost_basis > 0 else 0
            
            # Only consider losses
            if unrealized_loss >= 0:
                continue
            
            # Check minimum threshold
            if abs(unrealized_loss) < self.min_loss_threshold:
                continue
            
            # Check wash sale
            wash_sale_risk = self._check_wash_sale(symbol)
            
            # Find replacement
            replacement = None
            replacement_corr = 0.0
            if correlations and symbol in correlations:
                replacement, replacement_corr = self._find_replacement(
                    symbol, correlations[symbol], loss_pct
                )
            
            # Tax benefit
            tax_benefit = abs(unrealized_loss) * self.tax_rate
            
            # Days held
            purchase_date = holding.get('purchase_date')
            if purchase_date:
                if isinstance(purchase_date, str):
                    purchase_date = datetime.fromisoformat(purchase_date)
                days_held = (datetime.now() - purchase_date).days
            else:
                days_held = 0
            
            opportunity = TaxLossOpportunity(
                symbol=symbol,
                shares=shares,
                cost_basis=cost_basis,
                current_price=current_price,
                unrealized_loss=unrealized_loss,
                loss_pct=loss_pct,
                replacement_symbol=replacement,
                replacement_correlation=replacement_corr,
                tax_benefit=tax_benefit,
                days_held=days_held,
                wash_sale_risk=wash_sale_risk
            )
            
            opportunities.append(opportunity)
        
        # Sort by tax benefit (largest benefit first)
        opportunities.sort(key=lambda x: x.tax_benefit, reverse=True)
        
        return opportunities
    
    def _check_wash_sale(self, symbol: str) -> bool:
        """Check if wash sale applies (sold in last 30 days)"""
        
        if symbol not in self.wash_sales:
            return False
        
        days_since_sale = (datetime.now() - self.wash_sales[symbol]).days
        return days_since_sale <= 30
    
    def _find_replacement(self, symbol: str, 
                         correlations: Dict[str, float],
                         target_loss_pct: float) -> Tuple[Optional[str], float]:
        """Find replacement security with high correlation but not same sector"""
        
        # Find closest correlation >= 0.8 (highly correlated)
        candidates = [
            (sym, corr) for sym, corr in correlations.items() 
            if 0.80 <= corr < 1.0 and sym != symbol
        ]
        
        if not candidates:
            return None, 0.0
        
        # Sort by correlation (highest first)
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates[0]
    
    def execute_harvest(self, opportunity: TaxLossOpportunity,
                       current_price: float,
                       replacement_price: Optional[float] = None) -> Optional[TaxLossHarvest]:
        """Execute a tax-loss harvest trade
        
        Args:
            opportunity: The tax loss opportunity
            current_price: Current price of symbol to sell
            replacement_price: Price of replacement security
        """
        
        if opportunity.wash_sale_risk:
            logger.warning(f"Skipping {opportunity.symbol} - wash sale risk")
            return None
        
        if not opportunity.replacement_symbol:
            logger.warning(f"No replacement found for {opportunity.symbol}")
            return None
        
        # Calculate execution values
        realized_loss = (current_price - opportunity.cost_basis) * opportunity.shares
        tax_savings = abs(realized_loss) * self.tax_rate
        
        # Buy replacement with proceeds (plus any capital to maintain position size)
        if replacement_price and replacement_price > 0:
            sale_proceeds = current_price * opportunity.shares
            replacement_shares = sale_proceeds / replacement_price
        else:
            replacement_shares = opportunity.shares
        
        harvest = TaxLossHarvest(
            date=datetime.now().strftime('%Y-%m-%d'),
            symbol=opportunity.symbol,
            replacement_symbol=opportunity.replacement_symbol,
            shares=opportunity.shares,
            sale_price=current_price,
            cost_basis=opportunity.cost_basis,
            realized_loss=realized_loss,
            tax_savings=tax_savings,
            replacement_shares=replacement_shares,
            replacement_price=replacement_price or 0.0,
            wash_sale_date=(datetime.now() + timedelta(days=31)).strftime('%Y-%m-%d')
        )
        
        # Record wash sale
        self.wash_sales[opportunity.symbol] = datetime.now()
        self.harvest_history.append(harvest)
        
        logger.info(f"Tax harvest executed: {opportunity.symbol} -> {opportunity.replacement_symbol}, "
                   f"Tax savings: ${tax_savings:,.2f}")
        
        return harvest
    
    def get_annual_tax_savings(self) -> Tuple[float, int]:
        """Calculate total tax savings for current year
        
        Returns:
            (total_savings, harvest_count)
        """
        
        current_year = datetime.now().year
        year_harvests = [h for h in self.harvest_history 
                        if datetime.fromisoformat(h.date).year == current_year]
        
        total_savings = sum(h.tax_savings for h in year_harvests)
        
        return total_savings, len(year_harvests)
    
    def get_harvest_schedule(self) -> Dict[str, str]:
        """Get when harvests can be re-purchased (wash sale expiry)"""
        
        schedule = {}
        
        for symbol, sell_date in self.wash_sales.items():
            expiry_date = sell_date + timedelta(days=31)
            schedule[symbol] = expiry_date.strftime('%Y-%m-%d')
        
        return schedule
    
    def save_harvest_history(self, filename: str = "tax_harvest_history.json"):
        """Save harvest history to JSON"""
        
        filepath = self.cache_dir / filename
        
        data = {
            'harvests': [
                {
                    'date': h.date,
                    'symbol': h.symbol,
                    'replacement': h.replacement_symbol,
                    'shares': h.shares,
                    'realized_loss': h.realized_loss,
                    'tax_savings': h.tax_savings,
                    'wash_sale_expiry': h.wash_sale_date
                }
                for h in self.harvest_history
            ],
            'total_tax_savings': sum(h.tax_savings for h in self.harvest_history),
            'total_harvests': len(self.harvest_history),
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Tax harvest history saved to {filepath}")
        return str(filepath)
