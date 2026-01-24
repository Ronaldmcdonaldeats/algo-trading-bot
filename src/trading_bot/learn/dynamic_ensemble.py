"""Advanced ensemble with dynamic strategy weighting based on market conditions."""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    """Detected market regime."""
    name: str  # "trending", "ranging", "volatile", "choppy"
    confidence: float  # 0-1
    atr_ratio: float  # Current ATR vs 20-day avg
    volatility: float  # Current volatility
    trend_strength: float  # -1 to 1
    detected_at: str = ""


class RegimeDetector:
    """Detect market regime from OHLCV data."""
    
    def detect(self, df: pd.DataFrame, symbol: str = "") -> MarketRegime:
        """Detect market regime."""
        if df.empty or len(df) < 20:
            return MarketRegime("unknown", 0.0, 1.0, 0.0, 0.0)
        
        close = df['Close'].astype(float)
        high = df['High'].astype(float)
        low = df['Low'].astype(float)
        
        # Calculate ATR
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        atr_sma = tr.rolling(20).mean().mean()
        atr_ratio = atr / max(atr_sma, 0.001)
        
        # Calculate volatility
        returns = close.pct_change().dropna()
        volatility = float(returns.std()) if len(returns) > 0 else 0.0
        
        # Detect trend
        sma_short = close.rolling(10).mean().iloc[-1]
        sma_long = close.rolling(50).mean().iloc[-1]
        trend_strength = 1.0 if sma_short > sma_long else -1.0
        
        # Classify regime
        if volatility > 0.05:  # High volatility
            regime_name = "volatile"
            confidence = 0.8
        elif atr_ratio > 1.2:  # Expanding volatility
            regime_name = "trending"
            confidence = min(0.9, abs(trend_strength) * 0.9)
        elif atr_ratio < 0.8:  # Contracting volatility
            regime_name = "choppy"
            confidence = 0.7
        else:
            regime_name = "ranging"
            confidence = 0.6
        
        regime = MarketRegime(
            name=regime_name,
            confidence=confidence,
            atr_ratio=float(atr_ratio),
            volatility=volatility,
            trend_strength=float(trend_strength),
            detected_at=datetime.now().isoformat()
        )
        
        return regime


@dataclass
class StrategyPerformance:
    """Track strategy performance metrics."""
    name: str
    win_rate: float  # 0-1
    profit_factor: float  # Total wins / Total losses
    sharpe_ratio: float
    max_drawdown: float  # As percentage
    consecutive_losses: int
    recent_trades: List[float]  # Last 20 returns


class DynamicEnsemble:
    """Ensemble that dynamically adjusts weights based on market regime and recent performance."""
    
    def __init__(self, strategies: List[str], regime_detector: Optional[RegimeDetector] = None):
        """Initialize dynamic ensemble."""
        self.strategies = strategies
        self.regime_detector = regime_detector or RegimeDetector()
        self.weights = {s: 1.0 / len(strategies) for s in strategies}
        self.performance_history: Dict[str, List[StrategyPerformance]] = {s: [] for s in strategies}
        self.regime_weights = {
            "trending": {"atr_breakout": 0.5, "macd_momentum": 0.3, "rsi_mean_reversion": 0.2},
            "ranging": {"rsi_mean_reversion": 0.5, "macd_momentum": 0.3, "atr_breakout": 0.2},
            "volatile": {"atr_breakout": 0.4, "rsi_mean_reversion": 0.4, "macd_momentum": 0.2},
            "choppy": {"rsi_mean_reversion": 0.6, "macd_momentum": 0.3, "atr_breakout": 0.1},
        }
    
    def update_weights(
        self,
        market_data: pd.DataFrame,
        performance_metrics: Dict[str, StrategyPerformance]
    ) -> Dict[str, float]:
        """Update strategy weights based on market regime and performance."""
        
        # Detect current market regime
        regime = self.regime_detector.detect(market_data)
        
        # Get regime-based weights
        base_weights = self.regime_weights.get(regime.name, {s: 1.0/len(self.strategies) for s in self.strategies})
        
        # Apply performance adjustments
        adjusted_weights = {}
        for strategy in self.strategies:
            base_weight = base_weights.get(strategy, 1.0 / len(self.strategies))
            
            if strategy in performance_metrics:
                perf = performance_metrics[strategy]
                
                # Penalize high drawdown
                drawdown_penalty = 1.0 - (min(perf.max_drawdown, 30.0) / 30.0) * 0.3
                
                # Reward high win rate
                win_rate_boost = 1.0 + (perf.win_rate - 0.5) * 0.4
                
                # Penalize consecutive losses
                loss_penalty = 1.0 - min(perf.consecutive_losses / 5.0, 0.5)
                
                # Combine factors
                adjustment = drawdown_penalty * win_rate_boost * loss_penalty
                adjusted_weights[strategy] = base_weight * adjustment
            else:
                adjusted_weights[strategy] = base_weight
        
        # Normalize weights
        total = sum(adjusted_weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in adjusted_weights.items()}
        
        logger.info(f"Regime: {regime.name} (conf={regime.confidence:.2f}), Weights: {json.dumps({k: f'{v:.3f}' for k, v in self.weights.items()})}")
        
        return self.weights
    
    def get_weighted_signal(
        self,
        signals: Dict[str, int],
        confidences: Dict[str, float]
    ) -> tuple[int, float]:
        """Get weighted ensemble signal."""
        weighted_signal = 0.0
        weighted_confidence = 0.0
        total_weight = 0.0
        
        for strategy, signal in signals.items():
            if strategy not in self.weights:
                continue
            
            weight = self.weights[strategy]
            confidence = confidences.get(strategy, 0.5)
            
            weighted_signal += weight * signal * confidence
            weighted_confidence += weight * confidence
            total_weight += weight
        
        if total_weight > 0:
            weighted_confidence /= total_weight
        
        # Convert to -1, 0, 1
        final_signal = 1 if weighted_signal >= 0.3 else (-1 if weighted_signal <= -0.3 else 0)
        
        return final_signal, weighted_confidence


class PerformanceTracker:
    """Track and analyze strategy performance over time."""
    
    def __init__(self, window_size: int = 20):
        """Initialize tracker."""
        self.window_size = window_size
        self.trades: Dict[str, List[Dict]] = {}
    
    def record_trade(self, strategy: str, entry_price: float, exit_price: float, quantity: int) -> None:
        """Record a trade."""
        if strategy not in self.trades:
            self.trades[strategy] = []
        
        pnl = (exit_price - entry_price) * quantity
        return_pct = (exit_price - entry_price) / entry_price if entry_price > 0 else 0.0
        
        self.trades[strategy].append({
            "pnl": pnl,
            "return": return_pct,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only recent trades
        if len(self.trades[strategy]) > self.window_size * 2:
            self.trades[strategy] = self.trades[strategy][-self.window_size*2:]
    
    def get_performance(self, strategy: str) -> StrategyPerformance:
        """Get performance metrics for a strategy."""
        if strategy not in self.trades or not self.trades[strategy]:
            return StrategyPerformance(strategy, 0.5, 1.0, 0.0, 0.0, 0, [])
        
        recent_trades = self.trades[strategy][-self.window_size:]
        all_trades = self.trades[strategy]
        
        # Win rate
        wins = sum(1 for t in recent_trades if t['return'] > 0)
        win_rate = wins / max(len(recent_trades), 1)
        
        # Profit factor
        gross_profit = sum(t['pnl'] for t in recent_trades if t['pnl'] > 0)
        gross_loss = abs(sum(t['pnl'] for t in recent_trades if t['pnl'] < 0))
        profit_factor = gross_profit / max(gross_loss, 0.001)
        
        # Sharpe ratio
        returns = np.array([t['return'] for t in recent_trades])
        sharpe = float(np.mean(returns) / np.std(returns)) if len(returns) > 1 else 0.0
        
        # Max drawdown
        cumsum = np.cumsum(returns)
        max_drawdown = float((np.min(cumsum) - np.max(cumsum[:len(cumsum)//2])) * 100) if len(cumsum) > 0 else 0.0
        
        # Consecutive losses
        recent_returns = [t['return'] for t in recent_trades]
        consecutive_losses = 0
        for ret in reversed(recent_returns):
            if ret < 0:
                consecutive_losses += 1
            else:
                break
        
        return StrategyPerformance(
            name=strategy,
            win_rate=float(win_rate),
            profit_factor=float(profit_factor),
            sharpe_ratio=sharpe,
            max_drawdown=abs(max_drawdown),
            consecutive_losses=consecutive_losses,
            recent_trades=recent_returns[-10:]
        )
    
    def get_all_performance(self) -> Dict[str, StrategyPerformance]:
        """Get performance for all strategies."""
        return {strategy: self.get_performance(strategy) for strategy in self.trades.keys()}
