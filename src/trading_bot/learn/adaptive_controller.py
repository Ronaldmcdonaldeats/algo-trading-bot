"""Adaptive learning controller: orchestrates regime detection, analysis, and optimization.

This is the main brain of self-learning system.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pandas as pd

from trading_bot.learn.ensemble import ExponentialWeightsEnsemble
from trading_bot.learn.metrics import PerformanceMetrics, calculate_metrics, score_performance
from trading_bot.learn.regime import Regime, RegimeState, detect_regime, regime_adjusted_weights
from trading_bot.learn.trade_analyzer import (
    StrategyAnalysis,
    analyze_recent_trades,
    detect_win_loss_patterns,
    recommend_parameter_changes,
)


@dataclass(frozen=True)
class AdaptiveDecision:
    """Adaptive learning system output."""
    regime: Regime
    regime_confidence: float
    adjusted_weights: Dict[str, float]
    parameter_recommendations: Dict[str, Dict[str, Any]]
    performance: Optional[PerformanceMetrics]
    anomalies: list[str]
    explanation: Dict[str, Any]


class AdaptiveLearningController:
    """Main orchestrator for self-learning trading system.
    
    Integrates:
    - Market regime detection
    - Strategy performance analysis
    - Adaptive weighting
    - Parameter optimization
    - Audit logging
    """
    
    def __init__(
        self,
        ensemble: ExponentialWeightsEnsemble,
        *,
        min_trades_for_analysis: int = 10,
        regime_history_size: int = 100,
    ):
        self.ensemble = ensemble
        self.min_trades_for_analysis = min_trades_for_analysis
        self.regime_history: list[tuple[datetime, Regime, float]] = []
        self.max_regime_history = regime_history_size
        # OPTIMIZATION: Cache trade analysis to avoid recomputation
        self._last_trades_hash: int | None = None
        self._last_analysis_cache: dict | None = None
    
    def step(
        self,
        *,
        ohlcv_by_symbol: Dict[str, pd.DataFrame],
        current_params: Dict[str, Dict[str, Any]],
        trades: list[dict] | None = None,
        equity_series: pd.Series | None = None,
        now: datetime | None = None,
    ) -> AdaptiveDecision:
        """Execute one iteration of adaptive learning.
        
        Args:
            ohlcv_by_symbol: OHLCV data per symbol
            current_params: Current strategy parameters
            trades: Completed trades
            equity_series: Portfolio equity over time
            now: Current timestamp
        
        Returns:
            AdaptiveDecision with recommendations
        """
        now = now or datetime.utcnow()
        
        # 1. Detect market regime(s)
        regime_states = {}
        if ohlcv_by_symbol:
            # Average regime across symbols
            regimes = []
            for sym, df in ohlcv_by_symbol.items():
                if not df.empty:
                    rs = detect_regime(df)
                    regime_states[sym] = rs
                    regimes.append(rs)
            
            # Use first as primary (could average)
            primary_regime = regimes[0] if regimes else RegimeState(
                regime=Regime.INSUFFICIENT_DATA,
                confidence=0.0,
                volatility=0.0,
                trend_strength=0.0,
            )
        else:
            primary_regime = RegimeState(
                regime=Regime.INSUFFICIENT_DATA,
                confidence=0.0,
                volatility=0.0,
                trend_strength=0.0,
            )
        
        # Update regime history
        self.regime_history.append((now, primary_regime.regime, primary_regime.confidence))
        # Prevent unbounded growth - trim if 50% over limit
        if len(self.regime_history) > self.max_regime_history * 1.5:
            self.regime_history = self.regime_history[-self.max_regime_history:]
        
        # 2. Analyze recent trades (with caching to skip if data unchanged)
        anomalies = []
        strategy_analysis = {}
        param_recommendations = {}
        
        if trades and len(trades) >= self.min_trades_for_analysis:
            # OPTIMIZATION: Only recompute if trades list changed
            trades_hash = hash(tuple((t.get("entry_price"), t.get("exit_price")) for t in trades[-30:]))
            
            if trades_hash != self._last_trades_hash:
                strategy_analysis = analyze_recent_trades(trades, lookback_count=30)
                # Detect patterns
                patterns = detect_win_loss_patterns(trades, lookback=20)
                for pattern in patterns:
                    anomalies.append(pattern.description)
                # Recommend parameter changes
                param_recommendations = recommend_parameter_changes(strategy_analysis, current_params)
                
                # Cache result
                self._last_trades_hash = trades_hash
                self._last_analysis_cache = (strategy_analysis, anomalies, param_recommendations)
            else:
                # Use cached result
                if self._last_analysis_cache:
                    strategy_analysis, anomalies, param_recommendations = self._last_analysis_cache
        
        # 3. Calculate performance metrics
        performance = None
        if equity_series is not None and len(equity_series) > 0:
            performance = calculate_metrics(equity_series, trades=trades)
        
        # 4. Adjust ensemble weights based on regime
        learned_weights = self.ensemble.normalized()
        adjusted_weights = regime_adjusted_weights(primary_regime, learned_weights)
        
        # 5. Build explanation
        explanation: Dict[str, Any] = {
            "regime": primary_regime.regime.value,
            "regime_metrics": primary_regime.explanation or {},
            "regime_symbols": {sym: rs.regime.value for sym, rs in regime_states.items()},
            "strategy_analysis": {
                name: {
                    "trades": stats.trades,
                    "wins": stats.wins,
                    "losses": stats.losses,
                    "win_rate": round(stats.win_rate, 4),
                    "avg_return": round(stats.avg_trade_return, 4),
                    "total_pnl": round(stats.total_pnl, 2),
                }
                for name, stats in strategy_analysis.items()
            },
            "adjusted_weights": {k: round(v, 4) for k, v in adjusted_weights.items()},
            "learned_weights": {k: round(v, 4) for k, v in learned_weights.items()},
        }
        
        if performance:
            explanation["performance"] = {
                "total_return": round(performance.total_return, 4),
                "sharpe_ratio": round(performance.sharpe_ratio, 4) if performance.sharpe_ratio else None,
                "max_drawdown": round(performance.max_drawdown, 4),
                "win_rate": round(performance.win_rate, 4),
                "profit_factor": round(performance.profit_factor, 4),
                "trade_count": performance.trade_count,
            }
        
        return AdaptiveDecision(
            regime=primary_regime.regime,
            regime_confidence=primary_regime.confidence,
            adjusted_weights=adjusted_weights,
            parameter_recommendations=param_recommendations,
            performance=performance,
            anomalies=anomalies,
            explanation=explanation,
        )
    
    def regime_summary(self) -> Dict[str, Any]:
        """Summarize regime history."""
        if not self.regime_history:
            return {"message": "No regime history yet"}
        
        regime_counts: Dict[str, int] = {}
        for _, regime, _ in self.regime_history:
            regime_counts[regime.value] = regime_counts.get(regime.value, 0) + 1
        
        recent = self.regime_history[-10:] if len(self.regime_history) > 10 else self.regime_history
        
        return {
            "total_observations": len(self.regime_history),
            "regime_distribution": regime_counts,
            "recent_regimes": [
                {
                    "time": ts.isoformat(),
                    "regime": regime.value,
                    "confidence": round(conf, 4),
                }
                for ts, regime, conf in recent
            ],
        }
    
    def to_json(self) -> str:
        """Serialize controller state."""
        return json.dumps(
            {
                "regime_history_size": len(self.regime_history),
                "ensemble_weights": self.ensemble.normalized(),
                "regime_summary": self.regime_summary(),
            }
        )
