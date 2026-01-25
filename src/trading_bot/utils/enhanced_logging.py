"""Enhanced structured logging system for trading bot with JSON output and real-time metrics."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from dataclasses import asdict, is_dataclass


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Convert log record to JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            extra = record.extra_data
            if is_dataclass(extra):
                extra = asdict(extra)
            log_data.update(extra)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class TradeLogger:
    """Specialized logger for trading events with metrics tracking."""

    def __init__(self, name: str = "trading_bot", log_dir: str = "logs"):
        """Initialize trade logger.
        
        Args:
            name: Logger name
            log_dir: Directory for log files
        """
        self.name = name
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Main logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.handlers.clear()

        # JSON file handler (all events)
        json_handler = logging.FileHandler(self.log_dir / "trading_bot_events.json")
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(json_handler)

        # Text file handler (human readable)
        text_handler = logging.FileHandler(self.log_dir / "trading_bot.log")
        text_handler.setLevel(logging.INFO)
        text_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        text_handler.setFormatter(text_formatter)
        self.logger.addHandler(text_handler)

        # Console handler (console output)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # Metrics tracking
        self.trades_count = 0
        self.wins_count = 0
        self.losses_count = 0
        self.total_pnl = 0.0

    def log_trade_entry(
        self,
        symbol: str,
        price: float,
        quantity: int,
        strategy: str,
        signal_strength: float = 1.0,
    ) -> None:
        """Log trade entry event."""
        message = f"ENTRY: {symbol} @ ${price:.2f} x {quantity} ({strategy}, strength={signal_strength:.2f})"
        self.logger.info(message)
        self.trades_count += 1

    def log_trade_exit(
        self,
        symbol: str,
        entry_price: float,
        exit_price: float,
        quantity: int,
        pnl: float,
        pnl_pct: float,
        reason: str = "profit_target",
    ) -> None:
        """Log trade exit event."""
        status = "WIN" if pnl > 0 else "LOSS"
        message = (
            f"EXIT: {symbol} @ ${exit_price:.2f} | "
            f"P&L: ${pnl:.2f} ({pnl_pct:.2f}%) [{status}] ({reason})"
        )
        self.logger.info(message)

        if pnl > 0:
            self.wins_count += 1
        else:
            self.losses_count += 1
        self.total_pnl += pnl

    def log_position_update(
        self,
        symbol: str,
        quantity: int,
        entry_price: float,
        current_price: float,
        unrealized_pnl: float,
        unrealized_pnl_pct: float,
    ) -> None:
        """Log position update."""
        message = (
            f"POSITION: {symbol} x{quantity} | "
            f"Entry: ${entry_price:.2f}, Current: ${current_price:.2f} | "
            f"Unrealized P&L: ${unrealized_pnl:.2f} ({unrealized_pnl_pct:.2f}%)"
        )
        self.logger.debug(message)

    def log_portfolio_update(
        self,
        total_value: float,
        cash: float,
        invested: float,
        daily_pnl: float,
        daily_pnl_pct: float,
        sharpe_ratio: Optional[float] = None,
    ) -> None:
        """Log portfolio update."""
        message = (
            f"PORTFOLIO: Value=${total_value:,.2f} | "
            f"Cash=${cash:,.2f}, Invested=${invested:,.2f} | "
            f"Daily P&L: ${daily_pnl:.2f} ({daily_pnl_pct:.2f}%)"
        )
        if sharpe_ratio is not None:
            message += f" | Sharpe: {sharpe_ratio:.2f}"
        self.logger.info(message)

    def log_risk_alert(self, alert_type: str, message: str, severity: str = "warning") -> None:
        """Log risk management alert."""
        full_message = f"RISK [{alert_type.upper()}]: {message}"
        if severity == "critical":
            self.logger.critical(full_message)
        elif severity == "warning":
            self.logger.warning(full_message)
        else:
            self.logger.info(full_message)

    def log_circuit_breaker(self, reason: str, daily_loss: float, limit: float) -> None:
        """Log circuit breaker trigger."""
        message = (
            f"CIRCUIT BREAKER TRIGGERED: {reason} | "
            f"Daily Loss: ${daily_loss:.2f} (Limit: ${limit:.2f})"
        )
        self.logger.critical(message)

    def get_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        total_trades = self.wins_count + self.losses_count
        win_rate = (self.wins_count / total_trades * 100) if total_trades > 0 else 0.0

        return {
            "total_trades": self.trades_count,
            "wins": self.wins_count,
            "losses": self.losses_count,
            "win_rate": win_rate,
            "total_pnl": self.total_pnl,
            "avg_pnl_per_trade": self.total_pnl / total_trades if total_trades > 0 else 0.0,
        }

    def log_metrics_summary(self) -> None:
        """Log metrics summary."""
        metrics = self.get_metrics()
        message = (
            f"METRICS SUMMARY: Trades={metrics['total_trades']}, "
            f"Wins={metrics['wins']}, Losses={metrics['losses']}, "
            f"Win Rate={metrics['win_rate']:.1f}%, "
            f"Total P&L=${metrics['total_pnl']:.2f}"
        )
        self.logger.info(message)


# Global logger instance
_logger: Optional[TradeLogger] = None


def get_trade_logger(name: str = "trading_bot", log_dir: str = "logs") -> TradeLogger:
    """Get or create global trade logger."""
    global _logger
    if _logger is None:
        _logger = TradeLogger(name=name, log_dir=log_dir)
    return _logger


def reset_logger() -> None:
    """Reset global logger instance."""
    global _logger
    _logger = None
