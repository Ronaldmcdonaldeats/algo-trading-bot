"""Analytics and metrics tracking for trading bot."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import logging

logger = logging.getLogger(__name__)


class TradeMetrics:
    """Track and calculate trading metrics."""

    def __init__(self, trades_log_path: str = ".trades_log.json"):
        """Initialize metrics tracker.
        
        Args:
            trades_log_path: Path to store trade logs
        """
        self.trades_log_path = Path(trades_log_path)
        self.trades = []
        self.strategy_performance = {}  # Track wins by strategy
        self._load_trades()

    def _load_trades(self):
        """Load existing trades from log file."""
        if self.trades_log_path.exists():
            try:
                with open(self.trades_log_path, "r") as f:
                    self.trades = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load trades: {e}")
                self.trades = []

    def _save_trades(self):
        """Save trades to log file."""
        try:
            with open(self.trades_log_path, "w") as f:
                json.dump(self.trades, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save trades: {e}")

    def log_trade(
        self,
        symbol: str,
        side: str,
        qty: int,
        price: float,
        timestamp: datetime,
        pnl: Optional[float] = None,
        strategy: Optional[str] = None,
    ):
        """Log a trade.
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            qty: Quantity
            price: Execution price
            timestamp: Trade timestamp
            pnl: P&L if available
            strategy: Which strategy generated this signal (RSI, MACD, etc.)
        """
        trade = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": float(price),
            "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else str(timestamp),
            "pnl": float(pnl) if pnl is not None else None,
            "strategy": strategy,
        }
        self.trades.append(trade)
        
        # Track strategy performance
        if strategy and pnl is not None:
            if strategy not in self.strategy_performance:
                self.strategy_performance[strategy] = {"wins": 0, "losses": 0, "pnl": 0.0}
            
            if pnl > 0:
                self.strategy_performance[strategy]["wins"] += 1
            elif pnl < 0:
                self.strategy_performance[strategy]["losses"] += 1
            
            self.strategy_performance[strategy]["pnl"] += pnl
        
        self._save_trades()

    def get_win_rate(self) -> float:
        """Calculate win rate (% of profitable trades).
        
        Returns:
            Win rate as percentage (0-100)
        """
        closed_trades = [t for t in self.trades if t.get("pnl") is not None]
        if not closed_trades:
            return 0.0
        
        wins = sum(1 for t in closed_trades if t["pnl"] > 0)
        return (wins / len(closed_trades)) * 100

    def get_avg_win(self) -> float:
        """Calculate average profit per winning trade."""
        wins = [t for t in self.trades if t.get("pnl") and t.get("pnl", 0) > 0]
        return sum(t["pnl"] for t in wins) / len(wins) if wins else 0.0

    def get_avg_loss(self) -> float:
        """Calculate average loss per losing trade."""
        losses = [t for t in self.trades if t.get("pnl") and t.get("pnl", 0) < 0]
        return abs(sum(t["pnl"] for t in losses) / len(losses)) if losses else 0.0

    def get_profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)."""
        gross_profit = sum(t["pnl"] for t in self.trades if t.get("pnl") and t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t["pnl"] for t in self.trades if t.get("pnl") and t.get("pnl", 0) < 0))
        
        if gross_loss == 0:
            return 0.0
        
        return gross_profit / gross_loss

    def get_total_pnl(self) -> float:
        """Calculate total P&L from closed trades."""
        return sum(t.get("pnl", 0) for t in self.trades if t.get("pnl") is not None)

    def get_trade_count(self) -> int:
        """Get total number of trades."""
        return len(self.trades)

    def get_today_metrics(self) -> dict:
        """Get today's trading metrics.
        
        Returns:
            Dict with today's metrics
        """
        today = datetime.now().date()
        today_trades = [
            t for t in self.trades
            if datetime.fromisoformat(t["timestamp"]).date() == today
        ]
        
        buy_count = sum(1 for t in today_trades if t["side"] == "BUY")
        sell_count = sum(1 for t in today_trades if t["side"] == "SELL")
        
        closed_trades = [t for t in today_trades if t.get("pnl") is not None]
        today_pnl = sum(t.get("pnl", 0) for t in closed_trades)
        today_wins = sum(1 for t in closed_trades if t.get("pnl", 0) > 0)
        
        return {
            "date": str(today),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "total_trades": len(today_trades),
            "closed_trades": len(closed_trades),
            "pnl": today_pnl,
            "wins": today_wins,
            "win_rate": (today_wins / len(closed_trades) * 100) if closed_trades else 0.0,
        }

    def generate_daily_report(self) -> str:
        """Generate a text report of daily metrics.
        
        Returns:
            Formatted report string
        """
        metrics = self.get_today_metrics()
        all_metrics = {
            "win_rate": self.get_win_rate(),
            "avg_win": self.get_avg_win(),
            "avg_loss": self.get_avg_loss(),
            "profit_factor": self.get_profit_factor(),
            "total_pnl": self.get_total_pnl(),
            "total_trades": self.get_trade_count(),
        }
        
        report = f"""
╔════════════════════════════════════════════════╗
║         DAILY TRADING REPORT                   ║
╚════════════════════════════════════════════════╝

Date: {metrics['date']}

TODAY'S PERFORMANCE:
  Trades:         {metrics['total_trades']} ({metrics['buy_count']} BUY / {metrics['sell_count']} SELL)
  Closed:         {metrics['closed_trades']}
  P&L:            ${metrics['pnl']:+.2f}
  Win Rate:       {metrics['win_rate']:.1f}%

CUMULATIVE PERFORMANCE:
  Total Trades:   {all_metrics['total_trades']}
  Overall Win %:  {all_metrics['win_rate']:.1f}%
  Avg Win:        ${all_metrics['avg_win']:.2f}
  Avg Loss:       ${all_metrics['avg_loss']:.2f}
  Profit Factor:  {all_metrics['profit_factor']:.2f}x
  Cumulative P&L: ${all_metrics['total_pnl']:+.2f}

╔════════════════════════════════════════════════╗
"""
        return report

    def export_trades_csv(self, filepath: str = "trades.csv"):
        """Export all trades to CSV.
        
        Args:
            filepath: Output file path
        """
        if not self.trades:
            logger.warning("No trades to export")
            return
        
        df = pd.DataFrame(self.trades)
        df.to_csv(filepath, index=False)
        logger.info(f"Exported {len(self.trades)} trades to {filepath}")

    def get_strategy_performance(self) -> dict:
        """Get performance breakdown by strategy.
        
        Returns:
            Dict with win rate and P&L per strategy
        """
        result = {}
        for strategy, stats in self.strategy_performance.items():
            total_trades = stats["wins"] + stats["losses"]
            win_rate = (stats["wins"] / total_trades * 100) if total_trades > 0 else 0.0
            result[strategy] = {
                "total_trades": total_trades,
                "wins": stats["wins"],
                "losses": stats["losses"],
                "win_rate": win_rate,
                "pnl": stats["pnl"],
                "avg_pnl": stats["pnl"] / total_trades if total_trades > 0 else 0.0,
            }
        return result
