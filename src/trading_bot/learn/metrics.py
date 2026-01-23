"""Performance metrics calculation for learning and adaptation.

Computes Sharpe ratio, max drawdown, win rate, profit factor, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class PerformanceMetrics:
    """Aggregated performance metrics."""
    total_return: float  # net P&L / starting capital
    sharpe_ratio: Optional[float]  # excess return / volatility
    max_drawdown: float  # peak-to-trough decline
    win_rate: float  # winning trades / total trades (0.0-1.0)
    profit_factor: float  # gross profit / gross loss
    trade_count: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    avg_trade_duration_bars: Optional[float]  # average bars in a trade


def calculate_metrics(
    equity_series: pd.Series,
    *,
    trades: list[dict[str, float | int]] | None = None,
    risk_free_rate: float = 0.02,
) -> PerformanceMetrics:
    """Calculate performance metrics from equity curve and trades.
    
    Args:
        equity_series: Equity values over time
        trades: List of completed trades with 'entry_price', 'exit_price', 'qty', 'entry_bar', 'exit_bar'
        risk_free_rate: Annual risk-free rate for Sharpe calculation
    
    Returns:
        PerformanceMetrics
    """
    if equity_series.empty or len(equity_series) < 2:
        return PerformanceMetrics(
            total_return=0.0,
            sharpe_ratio=None,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=1.0,
            trade_count=0,
            winning_trades=0,
            losing_trades=0,
            avg_win=0.0,
            avg_loss=0.0,
            avg_trade_duration_bars=None,
        )
    
    equity_series = equity_series.astype(float)
    start_equity = float(equity_series.iloc[0])
    end_equity = float(equity_series.iloc[-1])
    
    # Total return
    total_return = (end_equity - start_equity) / max(start_equity, 1.0)
    
    # Sharpe ratio from daily returns
    daily_returns = equity_series.pct_change().dropna()
    sharpe = None
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        excess_return = daily_returns.mean() - risk_free_rate / 252
        sharpe = float(excess_return / daily_returns.std() * (252**0.5))
    
    # Max drawdown
    cumulative = (1.0 + daily_returns).cumprod() if len(daily_returns) > 0 else pd.Series([1.0])
    running_max = cumulative.expanding().max()
    drawdowns = (cumulative - running_max) / running_max
    max_dd = float(drawdowns.min()) if len(drawdowns) > 0 else 0.0
    
    # Trade metrics
    trade_count = 0
    winning_trades = 0
    losing_trades = 0
    gross_profit = 0.0
    gross_loss = 0.0
    total_duration = 0
    
    if trades:
        for trade in trades:
            trade_count += 1
            entry_px = float(trade.get("entry_price", 0))
            exit_px = float(trade.get("exit_price", 0))
            qty = int(trade.get("qty", 1))
            
            if entry_px <= 0:
                continue
            
            pnl = (exit_px - entry_px) * qty
            if pnl > 0:
                winning_trades += 1
                gross_profit += pnl
            else:
                losing_trades += 1
                gross_loss += abs(pnl)
            
            # Duration
            entry_bar = trade.get("entry_bar", 0)
            exit_bar = trade.get("exit_bar", 0)
            if isinstance(entry_bar, int) and isinstance(exit_bar, int):
                total_duration += exit_bar - entry_bar
    
    win_rate = winning_trades / max(trade_count, 1)
    profit_factor = gross_profit / max(gross_loss, 0.01)
    avg_win = gross_profit / max(winning_trades, 1)
    avg_loss = gross_loss / max(losing_trades, 1)
    avg_duration = total_duration / max(trade_count, 1) if trade_count > 0 else None
    
    return PerformanceMetrics(
        total_return=float(total_return),
        sharpe_ratio=sharpe,
        max_drawdown=float(max_dd),
        win_rate=float(win_rate),
        profit_factor=float(profit_factor),
        trade_count=int(trade_count),
        winning_trades=int(winning_trades),
        losing_trades=int(losing_trades),
        avg_win=float(avg_win),
        avg_loss=float(avg_loss),
        avg_trade_duration_bars=float(avg_duration) if avg_duration else None,
    )


def score_performance(metrics: PerformanceMetrics, *, objective: str = "sharpe") -> float:
    """Score performance for optimization.
    
    Args:
        metrics: PerformanceMetrics
        objective: 'sharpe', 'return', 'win_rate', or 'balanced'
    
    Returns:
        Score (higher is better)
    """
    if objective == "sharpe":
        return float(metrics.sharpe_ratio or 0.0)
    elif objective == "return":
        return float(metrics.total_return)
    elif objective == "win_rate":
        return float(metrics.win_rate)
    elif objective == "balanced":
        # Blend Sharpe and profit factor
        sharpe_score = float(metrics.sharpe_ratio or 0.0)
        pf_score = min(2.0, float(metrics.profit_factor)) / 2.0  # cap at 1.0
        return 0.6 * sharpe_score + 0.4 * pf_score
    else:
        return 0.0
