"""
Phase 12: Adaptive Strategy Weighting

Automatically adjust strategy weights based on recent performance.
Higher-performing strategies get larger position allocations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class StrategyWeight:
    """Weight for a single strategy"""
    strategy_name: str
    base_weight: float = 1.0  # Default equal weight
    performance_weight: float = 1.0  # Adjusted based on recent performance
    total_weight: float = 1.0  # base_weight * performance_weight
    recent_trades: int = 0
    recent_win_rate: float = 0.0
    recent_sharpe: float = 0.0
    recent_pnl: float = 0.0
    last_updated: Optional[datetime] = None

    def calculate_total_weight(self):
        """Recalculate total weight"""
        self.total_weight = self.base_weight * self.performance_weight


@dataclass
class AdaptiveWeightManager:
    """Manages adaptive strategy weighting"""
    strategies: list[str]
    base_weight: float = 1.0
    rebalance_interval: int = 20  # Rebalance every N trades
    min_trades_for_reweight: int = 5  # Min trades before considering performance
    lookback_trades: int = 20  # Consider last N trades for performance
    performance_boost_factor: float = 1.5  # Max weight multiplier for best strategy
    performance_penalty_factor: float = 0.5  # Min weight multiplier for worst strategy
    
    strategy_weights: dict[str, StrategyWeight] = field(default_factory=dict)
    trade_history: list[tuple[str, float]] = field(default_factory=list)  # (strategy, pnl)
    total_trades_recorded: int = 0

    def __post_init__(self):
        """Initialize weights for all strategies"""
        for strategy in self.strategies:
            self.strategy_weights[strategy] = StrategyWeight(
                strategy_name=strategy,
                base_weight=self.base_weight
            )

    def record_trade(self, strategy: str, pnl: float):
        """Record a trade result"""
        self.trade_history.append((strategy, pnl))
        self.total_trades_recorded += 1

        # Rebalance if interval reached
        if self.total_trades_recorded % self.rebalance_interval == 0:
            self.rebalance_weights()

    def rebalance_weights(self):
        """Recalculate weights based on recent performance"""
        if self.total_trades_recorded < self.min_trades_for_reweight:
            return

        # Get recent trades
        recent_trades = self.trade_history[-self.lookback_trades:]

        # Calculate per-strategy metrics
        for strategy in self.strategies:
            trades_for_strategy = [pnl for s, pnl in recent_trades if s == strategy]

            if len(trades_for_strategy) == 0:
                # No recent trades = neutral weight
                self.strategy_weights[strategy].performance_weight = 1.0
                continue

            # Win rate
            wins = sum(1 for pnl in trades_for_strategy if pnl > 0)
            win_rate = wins / len(trades_for_strategy) if trades_for_strategy else 0.0

            # Sharpe ratio (simplified - just avg return / std dev)
            total_pnl = sum(trades_for_strategy)
            avg_pnl = total_pnl / len(trades_for_strategy) if trades_for_strategy else 0.0

            if len(trades_for_strategy) > 1:
                variance = sum((pnl - avg_pnl) ** 2 for pnl in trades_for_strategy) / len(trades_for_strategy)
                std_dev = variance ** 0.5
                sharpe = (avg_pnl / std_dev) if std_dev > 0 else 0.0
            else:
                sharpe = avg_pnl

            # Update weights
            weight = self.strategy_weights[strategy]
            weight.recent_trades = len(trades_for_strategy)
            weight.recent_win_rate = win_rate
            weight.recent_sharpe = sharpe
            weight.recent_pnl = total_pnl
            weight.last_updated = datetime.now()

        # Normalize weights by Sharpe ratio
        self._apply_sharpe_weighting()

    def _apply_sharpe_weighting(self):
        """Apply Sharpe-based weighting"""
        sharpe_values = [w.recent_sharpe for w in self.strategy_weights.values()]
        max_sharpe = max(sharpe_values) if sharpe_values else 1.0
        min_sharpe = min(sharpe_values) if sharpe_values else 0.0

        # Handle edge case where all Sharpe values are the same
        if max_sharpe == min_sharpe:
            for weight in self.strategy_weights.values():
                weight.performance_weight = 1.0
            return

        # Normalize Sharpe values to 0-1 range, then scale to boost/penalty factors
        sharpe_range = max_sharpe - min_sharpe
        for weight in self.strategy_weights.values():
            # Normalize to 0-1
            normalized_sharpe = (weight.recent_sharpe - min_sharpe) / sharpe_range if sharpe_range > 0 else 0.5

            # Scale: 0 → penalty_factor, 0.5 → 1.0, 1.0 → boost_factor
            if normalized_sharpe < 0.5:
                # Scale from penalty to 1.0
                weight.performance_weight = (
                    self.performance_penalty_factor +
                    (1.0 - self.performance_penalty_factor) * (normalized_sharpe * 2)
                )
            else:
                # Scale from 1.0 to boost
                weight.performance_weight = (
                    1.0 +
                    (self.performance_boost_factor - 1.0) * ((normalized_sharpe - 0.5) * 2)
                )

            weight.calculate_total_weight()

    def get_strategy_weight(self, strategy: str) -> float:
        """Get current weight for a strategy"""
        if strategy not in self.strategy_weights:
            return self.base_weight
        return self.strategy_weights[strategy].total_weight

    def get_normalized_weights(self) -> dict[str, float]:
        """Get weights normalized to sum to 1.0"""
        total_weight = sum(w.total_weight for w in self.strategy_weights.values())
        if total_weight == 0:
            total_weight = 1.0

        return {
            name: weight.total_weight / total_weight
            for name, weight in self.strategy_weights.items()
        }

    def get_position_allocation(self, total_capital: float) -> dict[str, float]:
        """Get dollar allocation per strategy"""
        normalized = self.get_normalized_weights()
        return {
            strategy: total_capital * weight
            for strategy, weight in normalized.items()
        }

    def apply_weights_to_positions(
        self,
        base_positions: dict[str, int],
        strategy_assignments: dict[str, str]
    ) -> dict[str, int]:
        """
        Apply strategy weights to position sizes.
        
        Args:
            base_positions: {symbol: quantity}
            strategy_assignments: {symbol: strategy_name}
        
        Returns:
            {symbol: weighted_quantity}
        """
        weighted_positions = {}
        for symbol, qty in base_positions.items():
            strategy = strategy_assignments.get(symbol, "consensus")
            weight = self.get_strategy_weight(strategy)
            weighted_positions[symbol] = max(1, int(qty * weight))

        return weighted_positions

    def get_best_strategy(self) -> str:
        """Get highest-weight strategy"""
        if not self.strategy_weights:
            return self.strategies[0] if self.strategies else "consensus"

        best = max(
            self.strategy_weights.items(),
            key=lambda x: x[1].total_weight
        )
        return best[0]

    def get_worst_strategy(self) -> str:
        """Get lowest-weight strategy"""
        if not self.strategy_weights:
            return self.strategies[0] if self.strategies else "consensus"

        worst = min(
            self.strategy_weights.items(),
            key=lambda x: x[1].total_weight
        )
        return worst[0]

    def get_weight_ranking(self) -> list[tuple[str, float]]:
        """Get strategies ranked by weight"""
        return sorted(
            [(name, w.total_weight) for name, w in self.strategy_weights.items()],
            key=lambda x: x[1],
            reverse=True
        )

    def print_weight_status(self):
        """Print weight summary"""
        print("\n[ADAPTIVE WEIGHTS]")
        print(f"  Total trades recorded: {self.total_trades_recorded}")
        print(f"  Rebalance interval: {self.rebalance_interval}")
        print(f"  Lookback window: {self.lookback_trades} trades\n")

        for strategy, weight in self.get_weight_ranking():
            print(f"  {strategy.upper()}")
            print(f"    Weight: {weight:.2f}x")
            print(f"    Recent Trades: {self.strategy_weights[strategy].recent_trades}")
            print(f"    Win Rate: {self.strategy_weights[strategy].recent_win_rate * 100:.1f}%")
            print(f"    Sharpe: {self.strategy_weights[strategy].recent_sharpe:.2f}")
            print(f"    P&L: ${self.strategy_weights[strategy].recent_pnl:,.2f}\n")

    def reset(self):
        """Reset all weights and history"""
        for weight in self.strategy_weights.values():
            weight.performance_weight = 1.0
            weight.total_weight = 1.0
            weight.recent_trades = 0
            weight.recent_win_rate = 0.0
            weight.recent_sharpe = 0.0
            weight.recent_pnl = 0.0

        self.trade_history.clear()
        self.total_trades_recorded = 0
