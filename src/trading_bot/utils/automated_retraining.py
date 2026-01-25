"""Automated model retraining with regime detection and strategy adaptation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging
import numpy as np
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classifications."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    MEAN_REVERT = "mean_revert"
    RANGE_BOUND = "range_bound"
    HIGH_VOL = "high_vol"
    LOW_VOL = "low_vol"
    CRISIS = "crisis"


class StrategyAlignment(Enum):
    """Strategy alignment with current regime."""
    EXCELLENT = "excellent"
    GOOD = "good"
    NEUTRAL = "neutral"
    POOR = "poor"
    MISALIGNED = "misaligned"


@dataclass
class RegimeIndicators:
    """Market regime indicators."""
    volatility: float
    trend_strength: float  # -1 to 1
    mean_revert_score: float  # 0 to 1
    correlation: float  # to market
    vol_regime: str  # high, normal, low
    
    @property
    def detected_regime(self) -> MarketRegime:
        """Detect current regime.
        
        Returns:
            Detected market regime
        """
        if self.volatility > 30:  # High volatility
            if self.trend_strength > 0.5:
                return MarketRegime.TRENDING_UP
            elif self.trend_strength < -0.5:
                return MarketRegime.TRENDING_DOWN
            else:
                return MarketRegime.CRISIS
        else:
            if self.mean_revert_score > 0.6:
                return MarketRegime.MEAN_REVERT
            elif abs(self.trend_strength) > 0.4:
                if self.trend_strength > 0:
                    return MarketRegime.TRENDING_UP
                else:
                    return MarketRegime.TRENDING_DOWN
            else:
                return MarketRegime.RANGE_BOUND


@dataclass
class StrategyMetrics:
    """Strategy performance metrics."""
    strategy_name: str
    recent_return: float  # Last 20 trades
    recent_win_rate: float
    sharpe_ratio: float
    max_drawdown: float
    trades_count: int
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def performance_score(self) -> float:
        """Overall performance score (0-100)."""
        score = 0.0
        score += min(50, max(0, (self.recent_return / 100) * 10))  # Return contribution
        score += min(30, self.recent_win_rate * 30)  # Win rate contribution
        score += min(20, self.sharpe_ratio * 5)  # Sharpe contribution
        return score


@dataclass
class RetrainingEvent:
    """Retraining event record."""
    timestamp: datetime
    trigger: str  # reason for retraining
    old_params: Dict[str, float]
    new_params: Dict[str, float]
    performance_before: float
    performance_after: float
    regime: str


class RegimeDetector:
    """Detects market regimes."""
    
    def __init__(self, lookback_window: int = 60):
        """Initialize detector.
        
        Args:
            lookback_window: Days to analyze
        """
        self.lookback_window = lookback_window
        self.price_history: deque = deque(maxlen=lookback_window)
        self.volume_history: deque = deque(maxlen=lookback_window)
        self.regime_history: List[Tuple[datetime, MarketRegime]] = []
    
    def add_bar(self, price: float, volume: int) -> None:
        """Add price bar.
        
        Args:
            price: Close price
            volume: Volume
        """
        self.price_history.append(price)
        self.volume_history.append(volume)
    
    def detect_regime(self) -> Optional[RegimeIndicators]:
        """Detect current market regime.
        
        Returns:
            RegimeIndicators or None if insufficient data
        """
        if len(self.price_history) < 20:
            return None
        
        prices = np.array(list(self.price_history))
        
        # Calculate indicators
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * np.sqrt(252) * 100
        
        # Trend strength (using slope)
        x = np.arange(len(prices))
        z = np.polyfit(x, prices, 1)
        trend = np.gradient(prices)[-1]
        trend_strength = np.mean(trend) / (np.std(prices) + 1e-8)
        trend_strength = np.clip(trend_strength, -1, 1)
        
        # Mean reversion (reverse autocorrelation)
        if len(returns) > 1:
            mean_revert_score = abs(np.corrcoef(returns[:-1], returns[1:])[0, 1])
            mean_revert_score = max(0, -np.corrcoef(returns[:-1], returns[1:])[0, 1])
        else:
            mean_revert_score = 0.5
        
        # Volume regime
        avg_vol = np.mean(self.volume_history)
        vol_regime = 'high' if np.mean(list(self.volume_history)[-5:]) > avg_vol * 1.5 else 'normal'
        
        indicators = RegimeIndicators(
            volatility=volatility,
            trend_strength=trend_strength,
            mean_revert_score=mean_revert_score,
            correlation=0.7,  # Placeholder
            vol_regime=vol_regime,
        )
        
        # Record regime
        detected = indicators.detected_regime
        self.regime_history.append((datetime.utcnow(), detected))
        
        return indicators


class StrategyAdaptor:
    """Adapts strategies to market regimes."""
    
    def __init__(self):
        """Initialize adaptor."""
        self.strategy_params: Dict[str, Dict[str, float]] = {}
        self.regime_alignments: Dict[str, Dict[MarketRegime, float]] = {}
    
    def register_strategy(
        self,
        strategy_name: str,
        default_params: Dict[str, float],
    ) -> None:
        """Register strategy.
        
        Args:
            strategy_name: Strategy name
            default_params: Default parameters
        """
        self.strategy_params[strategy_name] = default_params.copy()
        self.regime_alignments[strategy_name] = {}
    
    def set_regime_alignment(
        self,
        strategy_name: str,
        regime: MarketRegime,
        alignment_score: float,  # 0-1
    ) -> None:
        """Set strategy-regime alignment.
        
        Args:
            strategy_name: Strategy name
            regime: Market regime
            alignment_score: Alignment score (0-1)
        """
        if strategy_name not in self.regime_alignments:
            self.regime_alignments[strategy_name] = {}
        
        self.regime_alignments[strategy_name][regime] = alignment_score
    
    def get_regime_alignment(
        self,
        strategy_name: str,
        regime: MarketRegime,
    ) -> StrategyAlignment:
        """Get strategy alignment with regime.
        
        Args:
            strategy_name: Strategy name
            regime: Market regime
            
        Returns:
            StrategyAlignment
        """
        if strategy_name not in self.regime_alignments:
            return StrategyAlignment.NEUTRAL
        
        score = self.regime_alignments[strategy_name].get(regime, 0.5)
        
        if score >= 0.8:
            return StrategyAlignment.EXCELLENT
        elif score >= 0.6:
            return StrategyAlignment.GOOD
        elif score >= 0.4:
            return StrategyAlignment.NEUTRAL
        elif score >= 0.2:
            return StrategyAlignment.POOR
        else:
            return StrategyAlignment.MISALIGNED
    
    def adapt_parameters(
        self,
        strategy_name: str,
        regime: MarketRegime,
        adjustment_factor: float = 1.0,
    ) -> Dict[str, float]:
        """Adapt strategy parameters for regime.
        
        Args:
            strategy_name: Strategy name
            regime: Market regime
            adjustment_factor: Adjustment multiplier
            
        Returns:
            Adapted parameters
        """
        if strategy_name not in self.strategy_params:
            return {}
        
        base_params = self.strategy_params[strategy_name].copy()
        adapted = base_params.copy()
        
        # Adjust parameters based on regime
        if regime == MarketRegime.TRENDING_UP:
            adapted['trend_multiplier'] = 1.5
            adapted['mean_revert_strength'] = 0.5
        elif regime == MarketRegime.TRENDING_DOWN:
            adapted['trend_multiplier'] = 1.5
            adapted['short_bias'] = 0.2
        elif regime == MarketRegime.MEAN_REVERT:
            adapted['mean_revert_strength'] = 1.5
            adapted['trend_multiplier'] = 0.5
        elif regime == MarketRegime.HIGH_VOL:
            adapted['position_size'] = 0.7
            adapted['stop_loss_pct'] = 3.0
        elif regime == MarketRegime.LOW_VOL:
            adapted['position_size'] = 1.3
            adapted['take_profit_pct'] = 1.5
        
        # Apply adjustment factor
        for key in adapted:
            if isinstance(adapted[key], (int, float)):
                adapted[key] *= adjustment_factor
        
        return adapted


class AutomatedRetrainer:
    """Handles automated model retraining."""
    
    def __init__(
        self,
        retraining_frequency: int = 20,  # Every N trades
        performance_threshold: float = 0.05,  # 5% degradation
    ):
        """Initialize retrainer.
        
        Args:
            retraining_frequency: Retrain every N trades
            performance_threshold: Trigger retraining if performance drops X%
        """
        self.retraining_frequency = retraining_frequency
        self.performance_threshold = performance_threshold
        self.trade_count = 0
        self.last_retrain = datetime.utcnow()
        self.retraining_history: List[RetrainingEvent] = []
        self.strategy_metrics: Dict[str, StrategyMetrics] = {}
    
    def should_retrain(self) -> bool:
        """Check if should retrain.
        
        Returns:
            True if should retrain
        """
        # Frequency-based
        if self.trade_count % self.retraining_frequency == 0:
            return True
        
        # Performance-based
        for strategy, metrics in self.strategy_metrics.items():
            if metrics.recent_return < -self.performance_threshold:
                return True
        
        return False
    
    def trigger_retraining(
        self,
        strategy_name: str,
        old_params: Dict[str, float],
        new_params: Dict[str, float],
        old_score: float,
        new_score: float,
        regime: str,
    ) -> RetrainingEvent:
        """Trigger retraining event.
        
        Args:
            strategy_name: Strategy name
            old_params: Previous parameters
            new_params: New parameters
            old_score: Previous performance score
            new_score: New performance score
            regime: Current regime
            
        Returns:
            RetrainingEvent
        """
        trigger_reason = "scheduled"
        if new_score > old_score * (1 + self.performance_threshold):
            trigger_reason = "performance_degradation"
        
        event = RetrainingEvent(
            timestamp=datetime.utcnow(),
            trigger=trigger_reason,
            old_params=old_params,
            new_params=new_params,
            performance_before=old_score,
            performance_after=new_score,
            regime=regime,
        )
        
        self.retraining_history.append(event)
        self.last_retrain = datetime.utcnow()
        self.trade_count = 0
        
        logger.info(f"Retraining triggered for {strategy_name}: {trigger_reason}")
        
        return event
    
    def record_trade(self, strategy_name: str, result: float) -> None:
        """Record trade.
        
        Args:
            strategy_name: Strategy name
            result: Trade result (P&L)
        """
        self.trade_count += 1
        
        # Update metrics
        if strategy_name not in self.strategy_metrics:
            self.strategy_metrics[strategy_name] = StrategyMetrics(
                strategy_name=strategy_name,
                recent_return=0.0,
                recent_win_rate=0.0,
                sharpe_ratio=0.0,
                trades_count=0,
            )
        
        metrics = self.strategy_metrics[strategy_name]
        metrics.trades_count += 1
    
    def evaluate_strategy_performance(
        self,
        strategy_name: str,
        recent_trades: List[float],
    ) -> StrategyMetrics:
        """Evaluate strategy performance.
        
        Args:
            strategy_name: Strategy name
            recent_trades: Recent trade results
            
        Returns:
            StrategyMetrics
        """
        if not recent_trades:
            return StrategyMetrics(strategy_name, 0, 0, 0, 0, 0)
        
        recent_array = np.array(recent_trades)
        total_return = np.sum(recent_array)
        win_rate = np.sum(recent_array > 0) / len(recent_array)
        
        # Calculate Sharpe (rough estimate)
        if len(recent_array) > 1:
            returns = recent_array / np.mean(np.abs(recent_array)) if np.mean(np.abs(recent_array)) > 0 else recent_array
            sharpe = np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(252)
        else:
            sharpe = 0.0
        
        # Max drawdown
        cumulative = np.cumsum(recent_array)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = np.min(cumulative - running_max) if len(cumulative) > 0 else 0
        
        metrics = StrategyMetrics(
            strategy_name=strategy_name,
            recent_return=total_return / len(recent_trades),
            recent_win_rate=win_rate * 100,
            sharpe_ratio=sharpe,
            max_drawdown=drawdown,
            trades_count=len(recent_trades),
        )
        
        self.strategy_metrics[strategy_name] = metrics
        return metrics


class ModelPerformanceMonitor:
    """Monitors model performance degradation."""
    
    def __init__(self, window_size: int = 20):
        """Initialize monitor.
        
        Args:
            window_size: Window for performance calculation
        """
        self.window_size = window_size
        self.prediction_history: Dict[str, deque] = {}
        self.actual_history: Dict[str, deque] = {}
    
    def record_prediction(
        self,
        model_name: str,
        prediction: float,
        actual: float,
    ) -> None:
        """Record model prediction.
        
        Args:
            model_name: Model name
            prediction: Predicted value
            actual: Actual value
        """
        if model_name not in self.prediction_history:
            self.prediction_history[model_name] = deque(maxlen=self.window_size)
            self.actual_history[model_name] = deque(maxlen=self.window_size)
        
        self.prediction_history[model_name].append(prediction)
        self.actual_history[model_name].append(actual)
    
    def get_model_accuracy(self, model_name: str) -> float:
        """Get model accuracy.
        
        Args:
            model_name: Model name
            
        Returns:
            Accuracy score (0-1)
        """
        if model_name not in self.prediction_history:
            return 0.5
        
        preds = np.array(list(self.prediction_history[model_name]))
        actuals = np.array(list(self.actual_history[model_name]))
        
        if len(preds) == 0:
            return 0.5
        
        # Direction accuracy (sign agreement)
        direction_correct = np.sum((preds * actuals) > 0)
        direction_accuracy = direction_correct / len(preds)
        
        return direction_accuracy
    
    def detect_degradation(self, model_name: str, threshold: float = 0.45) -> bool:
        """Detect if model accuracy has degraded.
        
        Args:
            model_name: Model name
            threshold: Minimum acceptable accuracy
            
        Returns:
            True if degraded
        """
        accuracy = self.get_model_accuracy(model_name)
        return accuracy < threshold
    
    def get_degradation_report(self) -> Dict[str, Dict[str, float]]:
        """Get degradation report for all models.
        
        Returns:
            Dict of model -> metrics
        """
        report = {}
        
        for model_name in self.prediction_history:
            accuracy = self.get_model_accuracy(model_name)
            is_degraded = self.detect_degradation(model_name)
            
            report[model_name] = {
                'accuracy': accuracy,
                'degraded': is_degraded,
                'predictions_recorded': len(self.prediction_history[model_name]),
            }
        
        return report
