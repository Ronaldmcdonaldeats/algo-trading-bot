"""
Advanced Analytics Module
Factor attribution, correlation analysis, drawdown analysis, tax optimization.
Deep insights into what drives performance and how to optimize returns.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from enum import Enum

logger = logging.getLogger(__name__)


class FactorType(Enum):
    """Performance attribution factors"""
    SECTOR = "sector"
    STRATEGY = "strategy"
    MARKET_REGIME = "market_regime"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"


@dataclass
class FactorContribution:
    """Contribution of a single factor to returns"""
    factor_type: FactorType
    factor_name: str
    contribution_pct: float  # % of total return
    cumulative_return: float
    win_rate: float
    avg_win: float
    avg_loss: float
    sharpe_ratio: float


@dataclass
class CorrelationAnalysis:
    """Correlation matrix analysis"""
    symbol_pairs: List[Tuple[str, str, float]]  # (sym1, sym2, correlation)
    average_correlation: float
    diversification_score: float  # 0-1, higher = more diversified
    cluster_groups: List[List[str]]  # Groups of highly correlated symbols


@dataclass
class DrawdownEvent:
    """Single drawdown event"""
    start_date: datetime
    end_date: datetime
    peak_value: float
    trough_value: float
    recovery_date: Optional[datetime]
    drawdown_pct: float
    recovery_time_days: int
    max_daily_loss_pct: float
    underlying_cause: str


@dataclass
class TaxLossHarvestingOpportunity:
    """Tax loss harvesting opportunity"""
    symbol: str
    current_price: float
    cost_basis: float
    unrealized_loss: float
    loss_pct: float
    days_held: int
    eligible_harvest: bool  # Not wash sale)
    replacement_symbol: str  # Similar but not identical
    estimated_tax_benefit: float


class FactorAttributionEngine:
    """Analyzes performance contribution from different factors"""

    def __init__(self):
        self.sector_returns = {}
        self.strategy_returns = {}

    def attribute_by_sector(
        self,
        trades: List[Dict],
        sector_map: Dict[str, str],
    ) -> Dict[str, FactorContribution]:
        """Attribute performance to sectors"""

        sector_pnl = {}

        for trade in trades:
            symbol = trade.get("symbol")
            pnl = trade.get("pnl", 0)
            sector = sector_map.get(symbol, "Unknown")

            if sector not in sector_pnl:
                sector_pnl[sector] = []

            sector_pnl[sector].append(pnl)

        # Calculate metrics for each sector
        contributions = {}
        total_pnl = sum(sum(pnls) for pnls in sector_pnl.values())

        for sector, pnls in sector_pnl.items():
            if not pnls:
                continue

            sector_total = sum(pnls)
            contributions[sector] = FactorContribution(
                factor_type=FactorType.SECTOR,
                factor_name=sector,
                contribution_pct=(sector_total / total_pnl * 100) if total_pnl != 0 else 0,
                cumulative_return=sector_total,
                win_rate=(len([p for p in pnls if p > 0]) / len(pnls)) * 100,
                avg_win=np.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0,
                avg_loss=np.mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 0,
                sharpe_ratio=self._calculate_sharpe(pnls),
            )

        return contributions

    def attribute_by_strategy(
        self,
        trades: List[Dict],
    ) -> Dict[str, FactorContribution]:
        """Attribute performance to trading strategies"""

        strategy_pnl = {}

        for trade in trades:
            strategy = trade.get("strategy_name", "Unknown")
            pnl = trade.get("pnl", 0)

            if strategy not in strategy_pnl:
                strategy_pnl[strategy] = []

            strategy_pnl[strategy].append(pnl)

        contributions = {}
        total_pnl = sum(sum(pnls) for pnls in strategy_pnl.values())

        for strategy, pnls in strategy_pnl.items():
            if not pnls:
                continue

            strategy_total = sum(pnls)
            contributions[strategy] = FactorContribution(
                factor_type=FactorType.STRATEGY,
                factor_name=strategy,
                contribution_pct=(strategy_total / total_pnl * 100) if total_pnl != 0 else 0,
                cumulative_return=strategy_total,
                win_rate=(len([p for p in pnls if p > 0]) / len(pnls)) * 100,
                avg_win=np.mean([p for p in pnls if p > 0]) if any(p > 0 for p in pnls) else 0,
                avg_loss=np.mean([p for p in pnls if p < 0]) if any(p < 0 for p in pnls) else 0,
                sharpe_ratio=self._calculate_sharpe(pnls),
            )

        return contributions

    def attribute_by_market_regime(
        self,
        returns: pd.Series,
        regime_labels: List[str],  # Market regime for each period
    ) -> Dict[str, FactorContribution]:
        """Attribute performance to market regimes"""

        regime_returns = {}

        for regime, ret in zip(regime_labels, returns):
            if regime not in regime_returns:
                regime_returns[regime] = []

            regime_returns[regime].append(ret)

        contributions = {}
        total_return = returns.sum()

        for regime, rets in regime_returns.items():
            regime_total = sum(rets)
            contributions[regime] = FactorContribution(
                factor_type=FactorType.MARKET_REGIME,
                factor_name=regime,
                contribution_pct=(regime_total / total_return * 100) if total_return != 0 else 0,
                cumulative_return=regime_total,
                win_rate=(len([r for r in rets if r > 0]) / len(rets)) * 100 if rets else 0,
                avg_win=np.mean([r for r in rets if r > 0]) if any(r > 0 for r in rets) else 0,
                avg_loss=np.mean([r for r in rets if r < 0]) if any(r < 0 for r in rets) else 0,
                sharpe_ratio=self._calculate_sharpe(rets),
            )

        return contributions

    def _calculate_sharpe(self, returns: List[float], rf: float = 0.05) -> float:
        """Calculate Sharpe ratio"""
        if not returns or len(returns) < 2:
            return 0.0

        returns_array = np.array(returns)
        excess_return = returns_array.mean() - rf / 252
        volatility = returns_array.std()

        if volatility == 0:
            return 0.0

        return (excess_return / volatility) * np.sqrt(252)

    def get_attribution_summary(
        self,
        trades: List[Dict],
        returns: pd.Series,
        sector_map: Dict[str, str],
    ) -> Dict[str, Dict]:
        """Get comprehensive attribution analysis"""

        return {
            "by_sector": self.attribute_by_sector(trades, sector_map),
            "by_strategy": self.attribute_by_strategy(trades),
        }


class CorrelationAnalyzer:
    """Analyzes correlation structure of portfolio"""

    def __init__(self, min_correlation_threshold: float = 0.6):
        self.min_correlation_threshold = min_correlation_threshold

    def calculate_correlation_matrix(
        self,
        returns_data: Dict[str, pd.Series],
    ) -> pd.DataFrame:
        """Calculate correlation matrix"""

        df = pd.concat(returns_data.values(), axis=1, keys=returns_data.keys())
        return df.corr()

    def identify_correlated_pairs(
        self,
        correlation_matrix: pd.DataFrame,
        threshold: float = 0.7,
    ) -> List[Tuple[str, str, float]]:
        """Identify highly correlated pairs"""

        pairs = []

        for i, col1 in enumerate(correlation_matrix.columns):
            for j, col2 in enumerate(correlation_matrix.columns):
                if i < j:
                    corr = correlation_matrix.loc[col1, col2]
                    if abs(corr) > threshold:
                        pairs.append((col1, col2, corr))

        return sorted(pairs, key=lambda x: abs(x[2]), reverse=True)

    def cluster_symbols(
        self,
        correlation_matrix: pd.DataFrame,
    ) -> List[List[str]]:
        """Cluster symbols by correlation"""

        from sklearn.cluster import AgglomerativeClustering

        # Distance matrix
        distance_matrix = 1 - correlation_matrix

        # Clustering
        clustering = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=0.5,
            linkage="average",
        )

        labels = clustering.fit_predict(distance_matrix)

        # Group symbols by cluster
        clusters = {}
        for symbol, cluster_id in zip(correlation_matrix.columns, labels):
            if cluster_id not in clusters:
                clusters[cluster_id] = []
            clusters[cluster_id].append(symbol)

        return list(clusters.values())

    def calculate_diversification_score(
        self,
        correlation_matrix: pd.DataFrame,
    ) -> float:
        """Calculate portfolio diversification score (0-1)"""

        # Average absolute correlation
        corr_values = correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)]
        avg_correlation = np.mean(np.abs(corr_values))

        # Diversification = 1 - avg_correlation
        # -1 correlation = perfect hedge = high diversification
        # +1 correlation = perfect correlation = low diversification
        diversification = 1 - (avg_correlation + 1) / 2

        return np.clip(diversification, 0, 1)

    def analyze_correlations(
        self,
        returns_data: Dict[str, pd.Series],
    ) -> CorrelationAnalysis:
        """Complete correlation analysis"""

        corr_matrix = self.calculate_correlation_matrix(returns_data)

        pairs = self.identify_correlated_pairs(corr_matrix, threshold=self.min_correlation_threshold)

        clusters = self.cluster_symbols(corr_matrix)

        avg_corr = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()

        return CorrelationAnalysis(
            symbol_pairs=pairs,
            average_correlation=avg_corr,
            diversification_score=self.calculate_diversification_score(corr_matrix),
            cluster_groups=clusters,
        )


class DrawdownAnalyzer:
    """Analyzes drawdown events in detail"""

    def __init__(self):
        self.drawdown_events: List[DrawdownEvent] = []

    def identify_drawdown_events(
        self,
        equity_curve: pd.Series,
        min_drawdown_pct: float = 0.02,  # 2% minimum
    ) -> List[DrawdownEvent]:
        """Identify all significant drawdown events"""

        events = []
        running_max = equity_curve.cummax()
        drawdowns = (equity_curve - running_max) / running_max

        in_drawdown = False
        start_idx = 0
        peak_value = 0

        for i, (date, dd) in enumerate(drawdowns.items()):
            if not in_drawdown and dd < -min_drawdown_pct:
                # Start new drawdown
                in_drawdown = True
                start_idx = i
                peak_value = equity_curve.iloc[i - 1] if i > 0 else equity_curve.iloc[0]

            elif in_drawdown and dd >= -0.001:  # Recovery
                # End drawdown
                trough_idx = drawdowns.iloc[start_idx:i].idxmin()
                trough_value = equity_curve[trough_idx]
                recovery_date = date

                event = DrawdownEvent(
                    start_date=equity_curve.index[start_idx],
                    end_date=date,
                    peak_value=peak_value,
                    trough_value=trough_value,
                    recovery_date=recovery_date,
                    drawdown_pct=((trough_value - peak_value) / peak_value) * 100,
                    recovery_time_days=(date - equity_curve.index[start_idx]).days,
                    max_daily_loss_pct=equity_curve.pct_change().iloc[start_idx:i].min() * 100,
                    underlying_cause="Unknown",  # Would need to analyze market events
                )

                events.append(event)
                in_drawdown = False

        self.drawdown_events = events
        return events

    def get_drawdown_statistics(self) -> Dict[str, float]:
        """Get statistics about drawdown events"""

        if not self.drawdown_events:
            return {}

        drawdown_pcts = [abs(e.drawdown_pct) for e in self.drawdown_events]
        recovery_times = [e.recovery_time_days for e in self.drawdown_events]

        return {
            "total_drawdown_events": len(self.drawdown_events),
            "avg_drawdown_pct": np.mean(drawdown_pcts),
            "max_drawdown_pct": max(drawdown_pcts),
            "median_drawdown_pct": np.median(drawdown_pcts),
            "avg_recovery_time_days": np.mean(recovery_times),
            "max_recovery_time_days": max(recovery_times),
        }

    def worst_drawdowns(self, n: int = 5) -> List[DrawdownEvent]:
        """Get worst N drawdown events"""

        sorted_events = sorted(self.drawdown_events, key=lambda x: x.drawdown_pct)
        return sorted_events[:n]


class TaxLossHarvester:
    """Identifies tax loss harvesting opportunities"""

    def __init__(self, wash_sale_days: int = 30):
        self.wash_sale_days = wash_sale_days
        self.harvestable_positions: List[TaxLossHarvestingOpportunity] = []

    def identify_opportunities(
        self,
        positions: Dict[str, Dict],  # symbol -> {price, cost_basis, purchase_date}
        current_prices: Dict[str, float],
        tax_rate: float = 0.37,  # Top marginal rate
    ) -> List[TaxLossHarvestingOpportunity]:
        """Identify tax loss harvesting opportunities"""

        opportunities = []

        for symbol, position_data in positions.items():
            cost_basis = position_data.get("cost_basis", 0)
            purchase_date = position_data.get("purchase_date", datetime.now())
            current_price = current_prices.get(symbol, 0)

            if current_price <= 0:
                continue

            unrealized_loss = (current_price - cost_basis)
            loss_pct = (unrealized_loss / cost_basis) * 100 if cost_basis != 0 else 0

            days_held = (datetime.now() - purchase_date).days

            # Check if position is at a loss
            if unrealized_loss < 0:
                # Estimate tax benefit
                tax_benefit = abs(unrealized_loss) * tax_rate

                # Find replacement (similar sector/characteristics)
                replacement = self._find_replacement(symbol)

                opportunity = TaxLossHarvestingOpportunity(
                    symbol=symbol,
                    current_price=current_price,
                    cost_basis=cost_basis,
                    unrealized_loss=unrealized_loss,
                    loss_pct=loss_pct,
                    days_held=days_held,
                    eligible_harvest=True,  # Simplified - would check wash sale
                    replacement_symbol=replacement,
                    estimated_tax_benefit=tax_benefit,
                )

                opportunities.append(opportunity)

        self.harvestable_positions = sorted(
            opportunities,
            key=lambda x: x.estimated_tax_benefit,
            reverse=True,
        )

        return self.harvestable_positions

    def _find_replacement(self, symbol: str) -> str:
        """Find similar but not identical replacement symbol"""

        # Simplified mapping - in reality would use correlation/sector
        replacement_map = {
            "AAPL": "MSFT",
            "MSFT": "AAPL",
            "AMZN": "NFLX",
            "NFLX": "AMZN",
            "TSLA": "F",
            "F": "TSLA",
        }

        return replacement_map.get(symbol, "SIMILAR_SECTOR_STOCK")

    def get_total_tax_savings(self) -> float:
        """Get total potential tax savings"""

        return sum(h.estimated_tax_benefit for h in self.harvestable_positions)


class ReturnDecomposition:
    """Decomposes returns into components"""

    @staticmethod
    def decompose_returns(
        total_return: float,
        starting_capital: float,
        contributions: List[Tuple[datetime, float]],  # (date, amount)
        withdrawals: List[Tuple[datetime, float]],
    ) -> Dict[str, float]:
        """Decompose total return into beginning balance, contributions, and ending performance"""

        # Calculate time-weighted return
        periods = []
        current_balance = starting_capital

        for contrib_date, amount in sorted(contributions):
            periods.append({
                "start_balance": current_balance,
                "contribution": amount,
            })
            current_balance += amount

        # This is simplified - full calculation would use TWRR formula
        ending_balance = starting_capital + sum(c[1] for c in contributions) - sum(w[1] for w in withdrawals)
        gain = ending_balance - starting_capital - sum(c[1] for c in contributions) + sum(w[1] for w in withdrawals)

        return {
            "starting_capital": starting_capital,
            "contributions": sum(c[1] for c in contributions),
            "withdrawals": sum(w[1] for w in withdrawals),
            "gains": gain,
            "ending_balance": ending_balance,
            "return_pct": (gain / starting_capital) * 100 if starting_capital != 0 else 0,
        }
