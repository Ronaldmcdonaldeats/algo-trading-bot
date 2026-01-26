"""
Phase 11: Performance Analytics & Reporting

Real-time analytics for Sharpe ratio, max drawdown, Sortino ratio,
win rate, trade statistics, and per-strategy performance tracking.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class TradeStats:
    """Statistics for a single trade"""
    symbol: str
    side: str  # "BUY" or "SELL"
    entry_price: float
    exit_price: float
    qty: int
    pnl: float
    pnl_pct: float
    entry_time: datetime
    exit_time: datetime
    strategy: str = "consensus"
    hold_minutes: float = 0.0

    def __post_init__(self):
        if self.exit_time and self.entry_time:
            # Handle timezone-naive vs timezone-aware datetimes
            try:
                self.hold_minutes = (self.exit_time - self.entry_time).total_seconds() / 60
            except TypeError:
                # If one is naive and one is aware, just set to 0
                self.hold_minutes = 0.0


@dataclass
class StrategyPerformance:
    """Performance metrics for a single strategy"""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    cumulative_pnl_curve: list[float] = field(default_factory=list)
    trades: list[TradeStats] = field(default_factory=list)

    def update(self, trade: TradeStats):
        """Update metrics with new trade"""
        self.total_trades += 1
        self.total_pnl += trade.pnl

        if trade.pnl > 0:
            self.winning_trades += 1
            self.largest_win = max(self.largest_win, trade.pnl)
            self.avg_win = (self.avg_win * (self.winning_trades - 1) + trade.pnl) / self.winning_trades
        else:
            self.losing_trades += 1
            self.largest_loss = min(self.largest_loss, trade.pnl)
            self.avg_loss = (self.avg_loss * (self.losing_trades - 1) + trade.pnl) / self.losing_trades

        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0

        # Profit factor = total wins / abs(total losses)
        total_wins = self.avg_win * self.winning_trades if self.winning_trades > 0 else 0
        total_losses = abs(self.avg_loss * self.losing_trades) if self.losing_trades > 0 else 1
        self.profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        self.cumulative_pnl_curve.append(self.total_pnl)
        self.trades.append(trade)

    def calculate_sharpe_ratio(self, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio (annualized, assuming 252 trading days)"""
        if len(self.cumulative_pnl_curve) < 2:
            return 0.0

        # Daily returns
        returns = []
        for i in range(1, len(self.cumulative_pnl_curve)):
            daily_return = self.cumulative_pnl_curve[i] - self.cumulative_pnl_curve[i-1]
            returns.append(daily_return)

        if not returns or len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return 0.0

        # Annualize: sqrt(252)
        annual_sharpe = ((mean_return * 252) - risk_free_rate) / (std_dev * math.sqrt(252))
        return annual_sharpe

    def calculate_sortino_ratio(self, target_return: float = 0.0) -> float:
        """Calculate Sortino ratio (only downside volatility)"""
        if len(self.cumulative_pnl_curve) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self.cumulative_pnl_curve)):
            daily_return = self.cumulative_pnl_curve[i] - self.cumulative_pnl_curve[i-1]
            returns.append(daily_return)

        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)

        # Downside variance (only negative deviations)
        downside_returns = [r - target_return for r in returns if r < target_return]
        if not downside_returns:
            downside_variance = 0.0
        else:
            downside_variance = sum(r ** 2 for r in downside_returns) / len(returns)

        downside_std = math.sqrt(downside_variance) if downside_variance > 0 else 0.0

        if downside_std == 0:
            return 0.0

        # Annualize
        annual_sortino = ((mean_return * 252) - target_return) / (downside_std * math.sqrt(252))
        return annual_sortino

    def calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown from peak"""
        if not self.cumulative_pnl_curve:
            return 0.0

        max_peak = self.cumulative_pnl_curve[0]
        max_dd = 0.0

        for value in self.cumulative_pnl_curve:
            if value > max_peak:
                max_peak = value
            drawdown = (max_peak - value) / max(abs(max_peak), 1)
            max_dd = max(max_dd, drawdown)

        self.max_drawdown = max_dd * 100  # Convert to percentage
        return self.max_drawdown

    def calculate_all_metrics(self):
        """Recalculate all metrics"""
        self.calculate_sharpe_ratio()
        self.calculate_sortino_ratio()
        self.calculate_max_drawdown()


@dataclass
class PortfolioAnalytics:
    """Overall portfolio analytics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    cumulative_pnl_curve: list[float] = field(default_factory=list)
    strategy_performance: dict[str, StrategyPerformance] = field(default_factory=dict)
    all_trades: list[TradeStats] = field(default_factory=list)

    def add_trade(self, trade: TradeStats):
        """Add trade and update metrics"""
        self.all_trades.append(trade)

        # Update overall
        self.total_trades += 1
        self.total_pnl += trade.pnl
        self.cumulative_pnl_curve.append(self.total_pnl)

        if trade.pnl > 0:
            self.winning_trades += 1
            self.largest_win = max(self.largest_win, trade.pnl)
            if self.winning_trades == 1:
                self.avg_win = trade.pnl
            else:
                self.avg_win = (self.avg_win * (self.winning_trades - 1) + trade.pnl) / self.winning_trades
        else:
            self.losing_trades += 1
            self.largest_loss = min(self.largest_loss, trade.pnl)
            if self.losing_trades == 1:
                self.avg_loss = trade.pnl
            else:
                self.avg_loss = (self.avg_loss * (self.losing_trades - 1) + trade.pnl) / self.losing_trades

        # Update per-strategy
        if trade.strategy not in self.strategy_performance:
            self.strategy_performance[trade.strategy] = StrategyPerformance(trade.strategy)

        self.strategy_performance[trade.strategy].update(trade)

        # Recalculate
        self._calculate_metrics()

    def _calculate_metrics(self):
        """Recalculate all metrics"""
        if self.total_trades == 0:
            return

        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0.0

        # Profit factor
        total_wins = self.avg_win * self.winning_trades if self.winning_trades > 0 else 0
        total_losses = abs(self.avg_loss * self.losing_trades) if self.losing_trades > 0 else 1
        self.profit_factor = total_wins / total_losses if total_losses > 0 else 0.0

        # Sharpe ratio
        self.sharpe_ratio = self._calculate_sharpe()

        # Sortino ratio
        self.sortino_ratio = self._calculate_sortino()

        # Max drawdown
        self.max_drawdown = self._calculate_max_drawdown()

    def _calculate_sharpe(self) -> float:
        """Calculate Sharpe ratio"""
        if len(self.cumulative_pnl_curve) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self.cumulative_pnl_curve)):
            returns.append(self.cumulative_pnl_curve[i] - self.cumulative_pnl_curve[i-1])

        if not returns or len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance) if variance > 0 else 0.0

        if std_dev == 0:
            return 0.0

        annual_sharpe = ((mean_return * 252) - 0.02) / (std_dev * math.sqrt(252))
        return annual_sharpe

    def _calculate_sortino(self) -> float:
        """Calculate Sortino ratio"""
        if len(self.cumulative_pnl_curve) < 2:
            return 0.0

        returns = []
        for i in range(1, len(self.cumulative_pnl_curve)):
            returns.append(self.cumulative_pnl_curve[i] - self.cumulative_pnl_curve[i-1])

        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)
        downside_returns = [r for r in returns if r < 0]

        if not downside_returns:
            downside_std = 0.0
        else:
            downside_variance = sum(r ** 2 for r in downside_returns) / len(returns)
            downside_std = math.sqrt(downside_variance) if downside_variance > 0 else 0.0

        if downside_std == 0:
            return 0.0

        annual_sortino = ((mean_return * 252) - 0.0) / (downside_std * math.sqrt(252))
        return annual_sortino

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown"""
        if not self.cumulative_pnl_curve:
            return 0.0

        max_peak = self.cumulative_pnl_curve[0]
        max_dd = 0.0

        for value in self.cumulative_pnl_curve:
            if value > max_peak:
                max_peak = value
            drawdown = (max_peak - value) / max(abs(max_peak), 1)
            max_dd = max(max_dd, drawdown)

        return max_dd * 100

    def get_per_trade_expectancy(self) -> float:
        """Expected value per trade"""
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades

    def print_summary(self):
        """Print comprehensive analytics summary"""
        print("\n" + "=" * 80)
        print("[PORTFOLIO ANALYTICS]")
        print("=" * 80)

        print(f"\n[OVERALL PERFORMANCE]")
        print(f"  Total Trades: {self.total_trades}")
        print(f"  Winning: {self.winning_trades} | Losing: {self.losing_trades}")
        print(f"  Win Rate: {self.win_rate * 100:.1f}%")
        print(f"  Total P&L: ${self.total_pnl:,.2f}")
        print(f"  Per-Trade Expectancy: ${self.get_per_trade_expectancy():.2f}")

        print(f"\n[TRADE STATISTICS]")
        print(f"  Avg Win: ${self.avg_win:,.2f}")
        print(f"  Avg Loss: ${self.avg_loss:,.2f}")
        print(f"  Largest Win: ${self.largest_win:,.2f}")
        print(f"  Largest Loss: ${self.largest_loss:,.2f}")
        print(f"  Profit Factor: {self.profit_factor:.2f}")

        print(f"\n[RISK-ADJUSTED METRICS]")
        print(f"  Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"  Sortino Ratio: {self.sortino_ratio:.2f}")
        print(f"  Max Drawdown: {self.max_drawdown:.2f}%")

        print(f"\n[PER-STRATEGY BREAKDOWN]")
        for strategy_name, perf in sorted(
            self.strategy_performance.items(),
            key=lambda x: x[1].total_pnl,
            reverse=True
        ):
            perf.calculate_all_metrics()
            print(f"\n  {strategy_name.upper()}")
            print(f"    Trades: {perf.total_trades} ({perf.win_rate * 100:.1f}% win)")
            print(f"    P&L: ${perf.total_pnl:,.2f}")
            print(f"    Sharpe: {perf.sharpe_ratio:.2f} | Sortino: {perf.calculate_sortino_ratio():.2f}")
            print(f"    Max DD: {perf.max_drawdown:.2f}%")

        print("\n" + "=" * 80 + "\n")

    def get_best_strategy(self) -> Optional[str]:
        """Get strategy with highest Sharpe ratio"""
        if not self.strategy_performance:
            return None

        best_strategy = max(
            self.strategy_performance.items(),
            key=lambda x: x[1].calculate_sharpe_ratio()
        )
        return best_strategy[0]

    def get_strategy_ranking(self) -> list[tuple[str, float]]:
        """Get strategies ranked by Sharpe ratio"""
        ranking = []
        for name, perf in self.strategy_performance.items():
            sharpe = perf.calculate_sharpe_ratio()
            ranking.append((name, sharpe))

        return sorted(ranking, key=lambda x: x[1], reverse=True)

    def reset(self):
        """Reset all analytics"""
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.win_rate = 0.0
        self.avg_win = 0.0
        self.avg_loss = 0.0
        self.largest_win = 0.0
        self.largest_loss = 0.0
        self.sharpe_ratio = 0.0
        self.sortino_ratio = 0.0
        self.max_drawdown = 0.0
        self.profit_factor = 0.0
        self.cumulative_pnl_curve.clear()
        self.strategy_performance.clear()
        self.all_trades.clear()
