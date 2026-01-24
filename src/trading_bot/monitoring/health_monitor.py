"""
Health check and monitoring system for the trading bot.
Provides system status, performance metrics, and alerts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Overall health status of the trading system."""
    healthy: bool
    timestamp: datetime
    components: dict[str, bool]
    metrics: dict[str, float]
    warnings: list[str]
    errors: list[str]


class HealthMonitor:
    """Monitor trading bot health and performance."""
    
    def __init__(self, db_path: str = "data/trades.sqlite"):
        self.db_path = Path(db_path)
        self.cache_dir = Path(".cache/strategy_learning")
        self.data_dir = Path("data")
    
    def check_environment(self) -> dict[str, bool]:
        """Check if all required files and directories exist."""
        checks = {
            "config_exists": Path("configs/default.yaml").exists(),
            "data_dir_exists": self.data_dir.exists(),
            "cache_dir_exists": self.cache_dir.exists(),
            "database_exists": self.db_path.exists(),
            "learned_strategies_exist": (self.cache_dir / "learned_strategies.json").exists(),
        }
        return checks
    
    def check_dependencies(self) -> dict[str, bool]:
        """Check if required Python packages are available."""
        checks = {}
        
        packages = [
            ("pandas", "pandas"),
            ("numpy", "numpy"),
            ("alpaca", "alpaca_trade_api"),
            ("rich", "rich"),
            ("talib", "talib"),
            ("sklearn", "sklearn"),
        ]
        
        for name, import_name in packages:
            try:
                __import__(import_name)
                checks[name] = True
            except ImportError:
                checks[name] = False
        
        return checks
    
    def check_trading_activity(self) -> dict[str, float]:
        """Check recent trading activity metrics."""
        try:
            from trading_bot.db.repository import TradeRepository
            
            repo = TradeRepository(db_path=str(self.db_path))
            trades = repo.get_recent_trades(limit=100)
            
            if not trades:
                return {
                    "recent_trades": 0,
                    "avg_win_rate": 0.0,
                    "last_trade_hours_ago": float('inf'),
                }
            
            # Calculate metrics
            wins = len([t for t in trades if t.get('pnl', 0) > 0])
            win_rate = wins / len(trades) if trades else 0
            
            # Get last trade time
            latest = trades[0] if trades else None
            last_trade_time = datetime.fromisoformat(latest['timestamp']) if latest else None
            hours_ago = (datetime.now() - last_trade_time).total_seconds() / 3600 if last_trade_time else float('inf')
            
            return {
                "recent_trades": len(trades),
                "win_rate": win_rate,
                "last_trade_hours_ago": hours_ago,
            }
        except Exception as e:
            logger.debug(f"Could not check trading activity: {e}")
            return {
                "recent_trades": 0,
                "win_rate": 0.0,
                "last_trade_hours_ago": float('inf'),
            }
    
    def check_learning_system(self) -> dict[str, int]:
        """Check learning system status."""
        try:
            from trading_bot.learn.strategy_learner import StrategyLearner
            
            learner = StrategyLearner()
            
            return {
                "learned_strategies": len(learner.learned_strategies),
                "hybrid_strategies": len(learner.hybrid_strategies),
            }
        except Exception as e:
            logger.warning(f"Could not check learning system: {e}")
            return {
                "learned_strategies": 0,
                "hybrid_strategies": 0,
            }
    
    def get_warnings(self) -> list[str]:
        """Get system warnings."""
        warnings = []
        
        # Check disk space (simplified)
        if not self.data_dir.exists():
            warnings.append("Data directory doesn't exist")
        
        # Check learning system
        try:
            from trading_bot.learn.strategy_learner import StrategyLearner
            learner = StrategyLearner()
            if len(learner.learned_strategies) == 0:
                warnings.append("No learned strategies yet - system will learn from trading results")
        except Exception:
            warnings.append("Could not check learning system status")
        
        # Check recent trading activity
        metrics = self.check_trading_activity()
        if metrics["recent_trades"] == 0:
            warnings.append("No recent trades found - trading may not have run recently")
        elif metrics["last_trade_hours_ago"] > 24:
            warnings.append(f"No trades in last {int(metrics['last_trade_hours_ago'])} hours")
        
        return warnings
    
    def get_errors(self) -> list[str]:
        """Get system errors."""
        errors = []
        
        # Check critical environment
        env_checks = self.check_environment()
        if not env_checks["config_exists"]:
            errors.append("Configuration file missing: configs/default.yaml")
        if not env_checks["data_dir_exists"]:
            errors.append("Data directory missing: data/")
        
        # Check critical dependencies
        deps = self.check_dependencies()
        critical = ["pandas", "numpy", "alpaca"]
        for dep in critical:
            if dep in deps and not deps[dep]:
                errors.append(f"Missing critical dependency: {dep}")
        
        return errors
    
    def get_status(self) -> HealthStatus:
        """Get overall health status."""
        env_checks = self.check_environment()
        dep_checks = self.check_dependencies()
        trading_metrics = self.check_trading_activity()
        learning_metrics = self.check_learning_system()
        warnings = self.get_warnings()
        errors = self.get_errors()
        
        # Combine all component checks
        components = {
            **env_checks,
            **dep_checks,
            "has_trading_activity": trading_metrics["recent_trades"] > 0,
            "has_learned_strategies": learning_metrics["learned_strategies"] > 0,
        }
        
        # Overall health: no critical errors
        healthy = len(errors) == 0
        
        # Metrics to track
        metrics = {
            **trading_metrics,
            **learning_metrics,
        }
        
        return HealthStatus(
            healthy=healthy,
            timestamp=datetime.now(),
            components=components,
            metrics=metrics,
            warnings=warnings,
            errors=errors,
        )
    
    def print_status(self) -> None:
        """Print human-readable status report."""
        status = self.get_status()
        
        # Overall status
        health_emoji = "[OK]" if status.healthy else "[WARN]"
        print(f"\n{health_emoji} System Status: {'HEALTHY' if status.healthy else 'ISSUES DETECTED'}")
        print(f"  Checked at: {status.timestamp}")
        
        # Components
        print("\nComponent Status:")
        for name, is_ok in status.components.items():
            emoji = "[+]" if is_ok else "[-]"
            print(f"  {emoji} {name}")
        
        # Metrics
        print("\nPerformance Metrics:")
        for name, value in status.metrics.items():
            if isinstance(value, float):
                if name.endswith("_rate"):
                    print(f"  * {name}: {value:.1%}")
                elif name.endswith("_ago"):
                    print(f"  * {name}: {value:.1f}")
                else:
                    print(f"  * {name}: {value:.2f}")
            else:
                print(f"  * {name}: {value}")
        
        # Warnings
        if status.warnings:
            print("\n[WARN] Warnings:")
            for warning in status.warnings:
                print(f"  * {warning}")
        
        # Errors
        if status.errors:
            print("\n[ERR] Errors:")
            for error in status.errors:
                print(f"  * {error}")
        
        print()
    
    def export_json(self, filepath: str | Path = ".cache/health_status.json") -> None:
        """Export status to JSON file."""
        status = self.get_status()
        
        data = {
            "healthy": status.healthy,
            "timestamp": status.timestamp.isoformat(),
            "components": status.components,
            "metrics": status.metrics,
            "warnings": status.warnings,
            "errors": status.errors,
        }
        
        Path(filepath).write_text(json.dumps(data, indent=2))
        logger.info(f"Health status exported to {filepath}")


def main():
    """Print system health status."""
    import sys
    
    monitor = HealthMonitor()
    monitor.print_status()
    
    status = monitor.get_status()
    monitor.export_json()
    
    # Exit code: 0 if healthy, 1 if issues
    sys.exit(0 if status.healthy else 1)


if __name__ == "__main__":
    main()
