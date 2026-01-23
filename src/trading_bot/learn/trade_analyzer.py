"""Trade outcome analysis for pattern recognition and strategy learning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from trading_bot.learn.regime import Regime


@dataclass(frozen=True)
class TradePattern:
    """Pattern observed in trades."""
    description: str
    confidence: float  # 0.0-1.0
    sample_size: int
    metrics: dict[str, float]


@dataclass(frozen=True)
class StrategyAnalysis:
    """Per-strategy performance in current period."""
    strategy_name: str
    trades: int
    wins: int
    losses: int
    total_pnl: float
    avg_trade_return: float
    win_rate: float
    regime_performance: dict[str, float]  # Regime -> win rate


def analyze_recent_trades(
    trades: list[dict],
    *,
    regime_history: list[tuple[int, Regime]] | None = None,
    lookback_count: int = 20,
) -> dict[str, StrategyAnalysis]:
    """Analyze recent trades by strategy and regime.
    
    Args:
        trades: List of completed trades with strategy_name, entry_price, exit_price, qty, ts
        regime_history: List of (bar_num, regime) tuples
        lookback_count: How many recent trades to analyze
    
    Returns:
        Dict mapping strategy_name -> StrategyAnalysis
    """
    if not trades:
        return {}
    
    # Get recent trades only
    recent = trades[-lookback_count:] if len(trades) > lookback_count else trades
    
    analysis = {}
    
    for trade in recent:
        strategy = str(trade.get("strategy_name", "unknown"))
        entry_px = float(trade.get("entry_price", 0))
        exit_px = float(trade.get("exit_price", 0))
        qty = int(trade.get("qty", 1))
        
        if strategy not in analysis:
            analysis[strategy] = {
                "trades": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0.0,
                "returns": [],
                "regimes": [],
            }
        
        pnl = (exit_px - entry_px) * qty
        trade_return = (exit_px - entry_px) / entry_px if entry_px > 0 else 0.0
        
        analysis[strategy]["trades"] += 1
        if pnl > 0:
            analysis[strategy]["wins"] += 1
        else:
            analysis[strategy]["losses"] += 1
        analysis[strategy]["total_pnl"] += pnl
        analysis[strategy]["returns"].append(trade_return)
    
    # Convert to StrategyAnalysis objects
    result = {}
    for strat_name, stats in analysis.items():
        total_trades = stats["trades"]
        wins = stats["wins"]
        losses = stats["losses"]
        total_pnl = stats["total_pnl"]
        returns = stats["returns"]
        
        win_rate = wins / max(total_trades, 1)
        avg_return = sum(returns) / max(len(returns), 1)
        
        result[strat_name] = StrategyAnalysis(
            strategy_name=strat_name,
            trades=total_trades,
            wins=wins,
            losses=losses,
            total_pnl=float(total_pnl),
            avg_trade_return=float(avg_return),
            win_rate=float(win_rate),
            regime_performance={},  # Could be extended per regime
        )
    
    return result


def detect_win_loss_patterns(trades: list[dict], *, lookback: int = 20) -> list[TradePattern]:
    """Detect patterns in win/loss streaks and conditions.
    
    Returns:
        List of TradePattern objects
    """
    patterns = []
    
    if not trades or len(trades) < 3:
        return patterns
    
    recent = trades[-lookback:] if len(trades) > lookback else trades
    
    # Detect win streaks
    wins = [1 if float(t.get("exit_price", 0)) > float(t.get("entry_price", 0)) else 0 for t in recent]
    
    max_streak = 0
    current_streak = 0
    for w in wins:
        if w == 1:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0
    
    if max_streak >= 3:
        patterns.append(
            TradePattern(
                description=f"Winning streak of {max_streak}+ detected",
                confidence=0.7,
                sample_size=len(wins),
                metrics={"max_streak": float(max_streak), "current_win_rate": sum(wins) / len(wins)},
            )
        )
    
    # Detect loss streaks
    current_loss_streak = 0
    max_loss_streak = 0
    for w in wins:
        if w == 0:
            current_loss_streak += 1
            max_loss_streak = max(max_loss_streak, current_loss_streak)
        else:
            current_loss_streak = 0
    
    if max_loss_streak >= 2:
        patterns.append(
            TradePattern(
                description=f"Losing streak of {max_loss_streak}+ detected - review parameters",
                confidence=0.8,
                sample_size=len(wins),
                metrics={"max_loss_streak": float(max_loss_streak)},
            )
        )
    
    return patterns


def recommend_parameter_changes(
    analysis: dict[str, StrategyAnalysis],
    current_params: dict[str, dict],
) -> dict[str, dict]:
    """Recommend parameter adjustments based on trade analysis.
    
    Args:
        analysis: Strategy analysis results
        current_params: Current strategy parameters
    
    Returns:
        Dict of strategy_name -> suggested parameter changes
    """
    recommendations = {}
    
    for strat_name, stats in analysis.items():
        if stats.trades < 5:
            continue  # Not enough data
        
        suggested = dict(current_params.get(strat_name, {}))
        
        # If win rate is very low, consider tightening entry filters
        if stats.win_rate < 0.3 and strat_name == "mean_reversion_rsi":
            # More conservative RSI entry
            suggested["entry_oversold"] = float(suggested.get("entry_oversold", 30.0)) - 5.0
            recommendations[strat_name] = suggested
        
        # If win rate is high, consider relaxing slightly
        elif stats.win_rate > 0.7 and strat_name == "mean_reversion_rsi":
            suggested["entry_oversold"] = float(suggested.get("entry_oversold", 30.0)) + 2.5
            recommendations[strat_name] = suggested
        
        # MACD volume: adjust based on effectiveness
        if strat_name == "momentum_macd_volume":
            if stats.win_rate < 0.4:
                # Increase volume requirement
                suggested["vol_mult"] = min(2.0, float(suggested.get("vol_mult", 1.0)) + 0.25)
            elif stats.win_rate > 0.65:
                # Relax volume requirement slightly
                suggested["vol_mult"] = max(1.0, float(suggested.get("vol_mult", 1.0)) - 0.1)
            
            if suggested != current_params.get(strat_name, {}):
                recommendations[strat_name] = suggested
        
        # ATR breakout: adjust based on volatility regime
        if strat_name == "breakout_atr":
            if stats.win_rate < 0.35:
                suggested["atr_mult"] = min(1.5, float(suggested.get("atr_mult", 1.0)) + 0.25)
            elif stats.win_rate > 0.60:
                suggested["atr_mult"] = max(0.75, float(suggested.get("atr_mult", 1.0)) - 0.1)
            
            if suggested != current_params.get(strat_name, {}):
                recommendations[strat_name] = suggested
    
    return recommendations
