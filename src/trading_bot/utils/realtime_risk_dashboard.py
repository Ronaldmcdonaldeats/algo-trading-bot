"""Real-time risk dashboard with live portfolio metrics and Greeks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classifications."""
    GREEN = "green"      # Safe (< 5% drawdown)
    YELLOW = "yellow"    # Caution (5-10% drawdown)
    ORANGE = "orange"    # Warning (10-15% drawdown)
    RED = "red"          # Critical (> 15% drawdown)


@dataclass
class PositionGreeks:
    """Options Greeks for position."""
    symbol: str
    delta: float = 0.0      # Price sensitivity
    gamma: float = 0.0      # Delta acceleration
    theta: float = 0.0      # Time decay
    vega: float = 0.0       # Volatility sensitivity
    rho: float = 0.0        # Interest rate sensitivity
    
    @property
    def risk_score(self) -> float:
        """Calculate overall risk score (0-100)."""
        risk = abs(self.delta) * 20  # Delta risk
        risk += abs(self.gamma) * 15  # Convexity risk
        risk += abs(self.vega) * 10   # Vol risk
        risk += abs(self.theta) * 5   # Time risk
        return min(100, risk)


@dataclass
class PortfolioRisk:
    """Overall portfolio risk metrics."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_vega: float = 0.0
    net_theta: float = 0.0
    portfolio_beta: float = 1.0
    value_at_risk: float = 0.0  # VaR (95%)
    conditional_var: float = 0.0  # CVaR
    max_loss_scenario: float = 0.0
    best_case_scenario: float = 0.0
    
    @property
    def overall_risk_score(self) -> float:
        """0-100 risk score."""
        return min(100, abs(self.net_delta) + abs(self.net_vega) + abs(self.net_gamma))


@dataclass
class SectorExposure:
    """Sector-level exposure metrics."""
    sector: str
    allocation_pct: float
    market_exposure: float
    correlation_to_market: float
    volatility: float
    concentration_risk: float  # 0-1, higher = more concentrated
    
    @property
    def risk_adjusted_exposure(self) -> float:
        """Exposure adjusted for volatility and concentration."""
        return self.allocation_pct * (1 + self.volatility / 100) * (1 + self.concentration_risk)


@dataclass
class CorrelationMatrix:
    """Position correlation analysis."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    correlations: Dict[tuple, float] = field(default_factory=dict)
    avg_correlation: float = 0.0
    max_correlation: float = 0.0
    min_correlation: float = 0.0
    diversification_ratio: float = 1.0  # Risk if uncorrelated / actual risk
    
    def add_correlation(self, symbol1: str, symbol2: str, corr: float) -> None:
        """Add correlation pair.
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
            corr: Correlation value (-1 to 1)
        """
        key = (symbol1, symbol2) if symbol1 < symbol2 else (symbol2, symbol1)
        self.correlations[key] = corr
        self._update_stats()
    
    def _update_stats(self) -> None:
        """Update correlation statistics."""
        if not self.correlations:
            return
        
        values = list(self.correlations.values())
        self.avg_correlation = np.mean(values)
        self.max_correlation = np.max(values)
        self.min_correlation = np.min(values)


@dataclass
class LiquidityMetrics:
    """Liquidity analysis for positions."""
    symbol: str
    position_size: int
    daily_volume: int
    days_to_liquidate: float  # At current volume
    liquidity_score: float  # 0-100, higher = more liquid
    
    @property
    def is_highly_liquid(self) -> bool:
        """True if position is less than 5% of daily volume."""
        return (self.position_size / self.daily_volume) < 0.05 if self.daily_volume > 0 else False
    
    @property
    def liquidity_risk(self) -> float:
        """Liquidity risk score (0-100)."""
        ratio = (self.position_size / self.daily_volume) if self.daily_volume > 0 else 1.0
        return min(100, ratio * 100)


class PortfolioRiskCalculator:
    """Calculates real-time portfolio risk metrics."""
    
    def __init__(self):
        """Initialize risk calculator."""
        self.positions: Dict[str, Dict[str, float]] = {}
        self.risk_history: List[PortfolioRisk] = []
    
    def add_position(
        self,
        symbol: str,
        shares: int,
        price: float,
        delta: float = 1.0,
        volatility: float = 0.0,
        correlation_to_market: float = 0.0,
    ) -> None:
        """Add position to portfolio.
        
        Args:
            symbol: Stock symbol
            shares: Number of shares
            price: Current price
            delta: Position delta
            volatility: Annualized volatility
            correlation_to_market: Correlation to market index
        """
        self.positions[symbol] = {
            'shares': shares,
            'price': price,
            'value': shares * price,
            'delta': delta,
            'volatility': volatility,
            'beta': correlation_to_market,
        }
    
    def calculate_portfolio_risk(self) -> PortfolioRisk:
        """Calculate overall portfolio risk.
        
        Returns:
            PortfolioRisk metrics
        """
        if not self.positions:
            return PortfolioRisk()
        
        # Calculate totals
        total_value = sum(p['value'] for p in self.positions.values())
        net_delta = sum(p['shares'] * p['delta'] for p in self.positions.values())
        portfolio_beta = np.mean([p['beta'] for p in self.positions.values()])
        
        # Calculate VaR (95% confidence, 1-day horizon)
        volatilities = [p['volatility'] for p in self.positions.values()]
        weights = [p['value'] / total_value for p in self.positions.values()]
        
        portfolio_volatility = self._calculate_portfolio_volatility(weights, volatilities)
        
        # VaR = 1.645 * volatility * portfolio value (1-day)
        daily_var = 1.645 * (portfolio_volatility / np.sqrt(252)) * total_value
        
        risk = PortfolioRisk(
            net_delta=net_delta,
            net_vega=sum(p['volatility'] * p['value'] / 100 for p in self.positions.values()),
            net_gamma=np.std([p['delta'] for p in self.positions.values()]),
            net_theta=0.0,  # Would need options data
            portfolio_beta=portfolio_beta,
            value_at_risk=daily_var,
            conditional_var=daily_var * 1.5,  # Rough CVaR estimate
            max_loss_scenario=-daily_var * 2,
            best_case_scenario=daily_var * 2,
        )
        
        self.risk_history.append(risk)
        return risk
    
    def _calculate_portfolio_volatility(self, weights: List[float], 
                                       volatilities: List[float]) -> float:
        """Calculate portfolio volatility.
        
        Args:
            weights: Position weights
            volatilities: Individual volatilities
            
        Returns:
            Portfolio volatility
        """
        if len(weights) == 1:
            return volatilities[0]
        
        # Simplified: assume 0.5 average correlation
        weighted_vol = np.sum(np.array(weights) * np.array(volatilities))
        correlation_factor = 1 + (0.5 * (len(weights) - 1))
        
        return weighted_vol / np.sqrt(correlation_factor)
    
    def get_risk_level(self, current_value: float, peak_value: float) -> RiskLevel:
        """Classify risk level based on drawdown.
        
        Args:
            current_value: Current portfolio value
            peak_value: Peak portfolio value
            
        Returns:
            RiskLevel
        """
        if peak_value == 0:
            return RiskLevel.GREEN
        
        drawdown_pct = (peak_value - current_value) / peak_value * 100
        
        if drawdown_pct < 5:
            return RiskLevel.GREEN
        elif drawdown_pct < 10:
            return RiskLevel.YELLOW
        elif drawdown_pct < 15:
            return RiskLevel.ORANGE
        else:
            return RiskLevel.RED


class SectorAnalyzer:
    """Analyzes sector-level risks."""
    
    def __init__(self):
        """Initialize analyzer."""
        self.sector_positions: Dict[str, List[Dict]] = {}
    
    def add_position(
        self,
        symbol: str,
        sector: str,
        shares: int,
        price: float,
        volatility: float,
    ) -> None:
        """Add position by sector.
        
        Args:
            symbol: Stock symbol
            sector: Sector name
            shares: Number of shares
            price: Current price
            volatility: Volatility
        """
        if sector not in self.sector_positions:
            self.sector_positions[sector] = []
        
        self.sector_positions[sector].append({
            'symbol': symbol,
            'shares': shares,
            'price': price,
            'value': shares * price,
            'volatility': volatility,
        })
    
    def get_sector_exposures(self, total_value: float) -> List[SectorExposure]:
        """Get exposure by sector.
        
        Args:
            total_value: Total portfolio value
            
        Returns:
            List of SectorExposure
        """
        exposures = []
        
        for sector, positions in self.sector_positions.items():
            sector_value = sum(p['value'] for p in positions)
            allocation_pct = (sector_value / total_value * 100) if total_value > 0 else 0
            
            # Concentration risk: more positions = lower risk
            concentration_risk = 1.0 / (1 + len(positions))
            
            # Average volatility in sector
            avg_vol = np.mean([p['volatility'] for p in positions])
            
            exposure = SectorExposure(
                sector=sector,
                allocation_pct=allocation_pct,
                market_exposure=allocation_pct * np.mean([p['volatility'] for p in positions]),
                correlation_to_market=0.7,  # Average sector correlation
                volatility=avg_vol,
                concentration_risk=concentration_risk,
            )
            
            exposures.append(exposure)
        
        return exposures
    
    def get_concentrated_sectors(self, threshold_pct: float = 25.0) -> List[str]:
        """Get sectors over-allocated.
        
        Args:
            threshold_pct: Concentration threshold %
            
        Returns:
            List of over-concentrated sectors
        """
        total_value = sum(
            sum(p['value'] for p in positions)
            for positions in self.sector_positions.values()
        )
        
        concentrated = []
        
        for sector, positions in self.sector_positions.items():
            sector_value = sum(p['value'] for p in positions)
            allocation_pct = (sector_value / total_value * 100) if total_value > 0 else 0
            
            if allocation_pct > threshold_pct:
                concentrated.append(sector)
        
        return concentrated


class LiquidityAnalyzer:
    """Analyzes liquidity risks."""
    
    def __init__(self):
        """Initialize analyzer."""
        self.positions: Dict[str, LiquidityMetrics] = {}
    
    def add_position(
        self,
        symbol: str,
        shares: int,
        daily_volume: int,
    ) -> None:
        """Add position for liquidity analysis.
        
        Args:
            symbol: Stock symbol
            shares: Number of shares
            daily_volume: Daily average volume
        """
        days_to_liquidate = shares / daily_volume if daily_volume > 0 else float('inf')
        
        # Liquidity score: 100 = fully liquid in 1 day, 0 = illiquid
        liquidity_score = max(0, 100 - (days_to_liquidate * 10))
        
        self.positions[symbol] = LiquidityMetrics(
            symbol=symbol,
            position_size=shares,
            daily_volume=daily_volume,
            days_to_liquidate=days_to_liquidate,
            liquidity_score=liquidity_score,
        )
    
    def get_illiquid_positions(self, threshold: float = 0.05) -> List[LiquidityMetrics]:
        """Get illiquid positions.
        
        Args:
            threshold: Max position as % of daily volume
            
        Returns:
            List of illiquid positions
        """
        illiquid = []
        
        for metrics in self.positions.values():
            if not metrics.is_highly_liquid:
                illiquid.append(metrics)
        
        return sorted(illiquid, key=lambda x: x.liquidity_risk, reverse=True)
    
    def get_liquidation_plan(self, max_days: int = 5) -> Dict[str, int]:
        """Generate liquidation schedule.
        
        Args:
            max_days: Max days to liquidate all
            
        Returns:
            Dict of symbol -> daily_sell_amount
        """
        plan = {}
        
        for symbol, metrics in self.positions.items():
            daily_volume = metrics.daily_volume
            position_size = metrics.position_size
            
            # Sell 20% of daily volume per day max
            daily_sell = int(daily_volume * 0.2)
            days_needed = (position_size + daily_sell - 1) // daily_sell
            
            if days_needed <= max_days:
                plan[symbol] = daily_sell
        
        return plan


class RealTimeRiskDashboard:
    """Real-time risk monitoring dashboard."""
    
    def __init__(self):
        """Initialize dashboard."""
        self.risk_calc = PortfolioRiskCalculator()
        self.sector_analyzer = SectorAnalyzer()
        self.liquidity_analyzer = LiquidityAnalyzer()
        self.peak_value = 100_000
        self.last_update = datetime.utcnow()
    
    def update_position(
        self,
        symbol: str,
        shares: int,
        price: float,
        sector: str = "Other",
        volatility: float = 0.0,
        daily_volume: int = 1_000_000,
    ) -> None:
        """Update position in dashboard.
        
        Args:
            symbol: Stock symbol
            shares: Number of shares
            price: Current price
            sector: Sector classification
            volatility: Annualized volatility
            daily_volume: Daily trading volume
        """
        self.risk_calc.add_position(symbol, shares, price, volatility=volatility)
        self.sector_analyzer.add_position(symbol, sector, shares, price, volatility)
        self.liquidity_analyzer.add_position(symbol, shares, daily_volume)
        self.last_update = datetime.utcnow()
    
    def get_risk_snapshot(self, current_value: float) -> Dict[str, Any]:
        """Get complete risk snapshot.
        
        Args:
            current_value: Current portfolio value
            
        Returns:
            Risk snapshot dict
        """
        portfolio_risk = self.risk_calc.calculate_portfolio_risk()
        risk_level = self.risk_calc.get_risk_level(current_value, self.peak_value)
        sector_exposures = self.sector_analyzer.get_sector_exposures(current_value)
        illiquid_positions = self.liquidity_analyzer.get_illiquid_positions()
        
        # Update peak
        if current_value > self.peak_value:
            self.peak_value = current_value
        
        drawdown = (self.peak_value - current_value) / self.peak_value * 100
        
        return {
            'timestamp': self.last_update,
            'current_value': current_value,
            'peak_value': self.peak_value,
            'drawdown_pct': drawdown,
            'risk_level': risk_level.value,
            'value_at_risk': portfolio_risk.value_at_risk,
            'portfolio_beta': portfolio_risk.portfolio_beta,
            'net_delta': portfolio_risk.net_delta,
            'net_vega': portfolio_risk.net_vega,
            'sector_exposures': [
                {
                    'sector': e.sector,
                    'allocation_pct': e.allocation_pct,
                    'risk_adjusted_exposure': e.risk_adjusted_exposure,
                }
                for e in sector_exposures
            ],
            'concentrated_sectors': self.sector_analyzer.get_concentrated_sectors(),
            'illiquid_count': len(illiquid_positions),
            'liquidity_plan': self.liquidity_analyzer.get_liquidation_plan(),
        }
    
    def get_alerts(self, current_value: float) -> List[Dict[str, str]]:
        """Get risk alerts.
        
        Args:
            current_value: Current portfolio value
            
        Returns:
            List of alert dicts
        """
        alerts = []
        portfolio_risk = self.risk_calc.calculate_portfolio_risk()
        
        drawdown = (self.peak_value - current_value) / self.peak_value * 100
        
        if drawdown > 15:
            alerts.append({'level': 'critical', 'message': f'Critical drawdown: {drawdown:.1f}%'})
        elif drawdown > 10:
            alerts.append({'level': 'warning', 'message': f'Significant drawdown: {drawdown:.1f}%'})
        
        if abs(portfolio_risk.net_vega) > 100_000:
            alerts.append({'level': 'warning', 'message': f'High volatility exposure: ${abs(portfolio_risk.net_vega):.0f}'})
        
        if abs(portfolio_risk.net_delta) > 10_000:
            alerts.append({'level': 'warning', 'message': f'High directional risk: {abs(portfolio_risk.net_delta):.0f} delta'})
        
        # Concentration alerts
        concentrated = self.sector_analyzer.get_concentrated_sectors(25)
        if concentrated:
            alerts.append({'level': 'info', 'message': f'Concentrated sectors: {", ".join(concentrated)}'})
        
        # Liquidity alerts
        illiquid = self.liquidity_analyzer.get_illiquid_positions(0.1)
        if illiquid:
            alerts.append({'level': 'info', 'message': f'{len(illiquid)} illiquid positions detected'})
        
        return alerts
