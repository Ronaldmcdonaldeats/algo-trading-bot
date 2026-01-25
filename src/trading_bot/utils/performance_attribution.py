"""Performance attribution analysis and execution quality metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import numpy as np
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class AttributionType(Enum):
    """Attribution analysis types."""
    STRATEGY = "strategy"
    SECTOR = "sector"
    FACTOR = "factor"
    SYMBOL = "symbol"
    TIME = "time"


@dataclass
class TradeRecord:
    """Single trade record."""
    symbol: str
    entry_time: datetime
    exit_time: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    strategy: str
    sector: str
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0
    win: bool = False
    
    def calculate_metrics(self) -> None:
        """Calculate P&L metrics."""
        if self.exit_price is not None:
            self.pnl = (self.exit_price - self.entry_price) * self.quantity
            self.pnl_pct = (self.exit_price - self.entry_price) / self.entry_price * 100
            self.win = self.pnl > 0
            
            if self.exit_time:
                self.holding_days = (self.exit_time - self.entry_time).days


@dataclass
class StrategyPerformance:
    """Performance metrics by strategy."""
    strategy: str
    trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_pnl: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_holding_days: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    
    @property
    def contribution_pct(self) -> float:
        """Contribution to total P&L."""
        return 0.0  # Set by parent class


@dataclass
class ExecutionMetrics:
    """Trade execution quality metrics."""
    symbol: str
    trades: int
    avg_slippage: float = 0.0  # vs predicted
    avg_commission: float = 0.0
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    cost_efficiency: float = 0.0  # actual vs estimated
    best_execution_rate: float = 0.0  # % at best bid/ask
    venue_performance: Dict[str, float] = field(default_factory=dict)


class PerformanceAttributor:
    """Attributes performance to different sources."""
    
    def __init__(self):
        """Initialize attributor."""
        self.trades: List[TradeRecord] = []
        self.strategy_performance: Dict[str, StrategyPerformance] = {}
        self.sector_performance: Dict[str, StrategyPerformance] = {}
        self.symbol_performance: Dict[str, StrategyPerformance] = {}
        self.daily_performance: Dict[str, float] = {}
    
    def add_trade(self, trade: TradeRecord) -> None:
        """Add trade to analysis.
        
        Args:
            trade: Trade record
        """
        trade.calculate_metrics()
        self.trades.append(trade)
        
        # Update daily performance
        date_key = trade.entry_time.date()
        self.daily_performance[str(date_key)] = self.daily_performance.get(str(date_key), 0) + trade.pnl
    
    def calculate_strategy_performance(self) -> Dict[str, StrategyPerformance]:
        """Calculate performance by strategy.
        
        Returns:
            Dict of strategy -> performance
        """
        strategies = defaultdict(lambda: StrategyPerformance(strategy=""))
        
        for trade in self.trades:
            if trade.exit_price is None:
                continue
            
            perf = strategies[trade.strategy]
            perf.strategy = trade.strategy
            perf.trades += 1
            
            if trade.win:
                perf.winning_trades += 1
                perf.gross_profit += trade.pnl
            else:
                perf.losing_trades += 1
                perf.gross_loss += abs(trade.pnl)
            
            perf.net_pnl += trade.pnl
            perf.best_trade = max(perf.best_trade, trade.pnl)
            perf.worst_trade = min(perf.worst_trade, trade.pnl)
            perf.avg_holding_days += trade.holding_days
        
        # Calculate aggregated metrics
        for strategy, perf in strategies.items():
            if perf.trades > 0:
                perf.win_rate = perf.winning_trades / perf.trades * 100
                perf.avg_win = perf.gross_profit / perf.winning_trades if perf.winning_trades > 0 else 0
                perf.avg_loss = perf.gross_loss / perf.losing_trades if perf.losing_trades > 0 else 0
                perf.profit_factor = perf.gross_profit / perf.gross_loss if perf.gross_loss > 0 else 0
                perf.avg_holding_days = perf.avg_holding_days / perf.trades
        
        self.strategy_performance = dict(strategies)
        return self.strategy_performance
    
    def calculate_sector_performance(self) -> Dict[str, StrategyPerformance]:
        """Calculate performance by sector.
        
        Returns:
            Dict of sector -> performance
        """
        sectors = defaultdict(lambda: StrategyPerformance(strategy=""))
        
        for trade in self.trades:
            if trade.exit_price is None:
                continue
            
            perf = sectors[trade.sector]
            perf.strategy = trade.sector
            perf.trades += 1
            
            if trade.win:
                perf.winning_trades += 1
                perf.gross_profit += trade.pnl
            else:
                perf.losing_trades += 1
                perf.gross_loss += abs(trade.pnl)
            
            perf.net_pnl += trade.pnl
        
        # Calculate metrics
        for sector, perf in sectors.items():
            if perf.trades > 0:
                perf.win_rate = perf.winning_trades / perf.trades * 100
                perf.profit_factor = perf.gross_profit / perf.gross_loss if perf.gross_loss > 0 else 0
        
        self.sector_performance = dict(sectors)
        return self.sector_performance
    
    def get_attribution_breakdown(self) -> Dict[str, Dict]:
        """Get complete attribution breakdown.
        
        Returns:
            Attribution dict
        """
        total_pnl = sum(t.pnl for t in self.trades if t.exit_price is not None)
        
        # Strategy attribution
        strategy_perf = self.calculate_strategy_performance()
        strategy_attribution = {}
        
        for strategy, perf in strategy_perf.items():
            attribution_pct = (perf.net_pnl / total_pnl * 100) if total_pnl != 0 else 0
            strategy_attribution[strategy] = {
                'pnl': perf.net_pnl,
                'contribution_pct': attribution_pct,
                'trades': perf.trades,
                'win_rate': perf.win_rate,
                'profit_factor': perf.profit_factor,
            }
        
        # Sector attribution
        sector_perf = self.calculate_sector_performance()
        sector_attribution = {}
        
        for sector, perf in sector_perf.items():
            attribution_pct = (perf.net_pnl / total_pnl * 100) if total_pnl != 0 else 0
            sector_attribution[sector] = {
                'pnl': perf.net_pnl,
                'contribution_pct': attribution_pct,
                'trades': perf.trades,
                'win_rate': perf.win_rate,
            }
        
        return {
            'total_pnl': total_pnl,
            'strategy': strategy_attribution,
            'sector': sector_attribution,
            'total_trades': len([t for t in self.trades if t.exit_price is not None]),
        }
    
    def get_winning_strategies(self, top_n: int = 5) -> List[Tuple[str, float]]:
        """Get top winning strategies.
        
        Args:
            top_n: Number of strategies to return
            
        Returns:
            List of (strategy, pnl)
        """
        perf = self.calculate_strategy_performance()
        sorted_strats = sorted(perf.items(), key=lambda x: x[1].net_pnl, reverse=True)
        return [(s, p.net_pnl) for s, p in sorted_strats[:top_n]]
    
    def get_factor_contribution(self) -> Dict[str, float]:
        """Estimate contribution of different factors.
        
        Returns:
            Dict of factor -> contribution %
        """
        if not self.trades:
            return {}
        
        # Analyze what drives wins
        winning_trades = [t for t in self.trades if t.win and t.exit_price is not None]
        losing_trades = [t for t in self.trades if not t.win and t.exit_price is not None]
        
        if not winning_trades or not losing_trades:
            return {}
        
        # Win rate by strategy
        strategy_win_rate = {}
        for strategy in set(t.strategy for t in self.trades):
            trades = [t for t in self.trades if t.strategy == strategy and t.exit_price is not None]
            wins = [t for t in trades if t.win]
            strategy_win_rate[strategy] = len(wins) / len(trades) if trades else 0
        
        # Rank factors
        best_strategy = max(strategy_win_rate.items(), key=lambda x: x[1])
        
        return {
            'best_strategy': best_strategy[0],
            'strategy_win_rate': best_strategy[1],
        }


class ExecutionQualityAnalyzer:
    """Analyzes trade execution quality."""
    
    def __init__(self):
        """Initialize analyzer."""
        self.execution_records: List[Dict] = []
    
    def record_execution(
        self,
        symbol: str,
        action: str,
        quantity: int,
        predicted_slippage: float,
        actual_slippage: float,
        predicted_commission: float,
        actual_commission: float,
        venue: str,
    ) -> None:
        """Record trade execution.
        
        Args:
            symbol: Stock symbol
            action: BUY or SELL
            quantity: Quantity executed
            predicted_slippage: Predicted slippage %
            actual_slippage: Actual slippage %
            predicted_commission: Predicted commission $
            actual_commission: Actual commission $
            venue: Execution venue
        """
        self.execution_records.append({
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'predicted_slippage': predicted_slippage,
            'actual_slippage': actual_slippage,
            'predicted_commission': predicted_commission,
            'actual_commission': actual_commission,
            'venue': venue,
            'timestamp': datetime.utcnow(),
        })
    
    def get_execution_summary(self) -> Dict[str, float]:
        """Get execution quality summary.
        
        Returns:
            Summary metrics
        """
        if not self.execution_records:
            return {}
        
        records = self.execution_records
        
        # Slippage analysis
        predicted_slippages = [r['predicted_slippage'] for r in records]
        actual_slippages = [r['actual_slippage'] for r in records]
        
        slippage_accuracy = np.mean(
            [1 - abs(a - p) / (p + 1e-8) for a, p in zip(actual_slippages, predicted_slippages)]
        ) * 100
        
        # Commission analysis
        total_predicted_commission = sum(r['predicted_commission'] for r in records)
        total_actual_commission = sum(r['actual_commission'] for r in records)
        
        commission_efficiency = (
            total_predicted_commission / total_actual_commission
            if total_actual_commission > 0 else 0
        ) * 100
        
        # Venue analysis
        venue_efficiency = {}
        by_venue = defaultdict(list)
        
        for record in records:
            by_venue[record['venue']].append({
                'slippage_diff': abs(record['actual_slippage'] - record['predicted_slippage']),
                'commission': record['actual_commission'],
            })
        
        for venue, records_list in by_venue.items():
            avg_slippage_error = np.mean([r['slippage_diff'] for r in records_list])
            avg_commission = np.mean([r['commission'] for r in records_list])
            
            venue_efficiency[venue] = {
                'avg_slippage_error': avg_slippage_error,
                'avg_commission': avg_commission,
                'trades': len(records_list),
            }
        
        return {
            'total_executions': len(records),
            'avg_predicted_slippage': np.mean(predicted_slippages),
            'avg_actual_slippage': np.mean(actual_slippages),
            'slippage_accuracy': slippage_accuracy,
            'total_predicted_commission': total_predicted_commission,
            'total_actual_commission': total_actual_commission,
            'commission_efficiency': commission_efficiency,
            'venue_efficiency': venue_efficiency,
        }
    
    def get_worst_executions(self, top_n: int = 5) -> List[Dict]:
        """Get worst executions.
        
        Args:
            top_n: Number to return
            
        Returns:
            List of worst executions
        """
        records = sorted(
            self.execution_records,
            key=lambda r: abs(r['actual_slippage'] - r['predicted_slippage']),
            reverse=True
        )
        
        return records[:top_n]


class DailyPerformanceTracker:
    """Tracks daily performance metrics."""
    
    def __init__(self):
        """Initialize tracker."""
        self.daily_records: Dict[str, Dict] = {}
    
    def record_daily_close(
        self,
        date: datetime,
        portfolio_value: float,
        trades_executed: int,
        gross_pnl: float,
        net_pnl: float,
        win_rate: float,
    ) -> None:
        """Record daily close.
        
        Args:
            date: Trade date
            portfolio_value: Ending portfolio value
            trades_executed: Number of trades
            gross_pnl: Gross P&L
            net_pnl: Net P&L
            win_rate: Win rate %
        """
        date_key = str(date.date())
        
        self.daily_records[date_key] = {
            'portfolio_value': portfolio_value,
            'trades': trades_executed,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'win_rate': win_rate,
            'return_pct': (net_pnl / (portfolio_value - net_pnl)) * 100 if portfolio_value > net_pnl else 0,
        }
    
    def get_monthly_summary(self, year: int, month: int) -> Dict:
        """Get monthly summary.
        
        Args:
            year: Year
            month: Month
            
        Returns:
            Monthly summary
        """
        month_str = f"{year:04d}-{month:02d}"
        
        month_records = {
            k: v for k, v in self.daily_records.items()
            if k.startswith(month_str)
        }
        
        if not month_records:
            return {}
        
        values = list(month_records.values())
        
        return {
            'month': month_str,
            'trading_days': len(month_records),
            'total_trades': sum(v['trades'] for v in values),
            'total_pnl': sum(v['net_pnl'] for v in values),
            'avg_daily_pnl': np.mean([v['net_pnl'] for v in values]),
            'avg_win_rate': np.mean([v['win_rate'] for v in values]),
            'best_day': max(month_records.items(), key=lambda x: x[1]['net_pnl']),
            'worst_day': min(month_records.items(), key=lambda x: x[1]['net_pnl']),
        }
    
    def get_performance_stats(self) -> Dict:
        """Get overall performance statistics.
        
        Returns:
            Performance stats
        """
        if not self.daily_records:
            return {}
        
        values = list(self.daily_records.values())
        pnls = [v['net_pnl'] for v in values]
        returns = [v['return_pct'] for v in values]
        
        return {
            'trading_days': len(self.daily_records),
            'total_trades': sum(v['trades'] for v in values),
            'total_pnl': sum(pnls),
            'avg_daily_pnl': np.mean(pnls),
            'std_dev_pnl': np.std(pnls),
            'avg_return_pct': np.mean(returns),
            'sharpe_ratio': np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252),
            'winning_days': len([p for p in pnls if p > 0]),
            'losing_days': len([p for p in pnls if p < 0]),
        }
