"""Production Logging & Monitoring - Comprehensive system health tracking

Tracks:
- All trades with detailed reasoning
- System health and performance
- Errors and warnings
- Feature-specific metrics
- Automated alerts for anomalies
"""

import logging
import logging.handlers
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import json


class StrategyLogger:
    """Production-grade logging system"""
    
    def __init__(self, log_dir: str = "data"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self._setup_loggers()
        
    def _setup_loggers(self):
        """Setup rotating file loggers for each component"""
        
        # Main logger
        self.main_logger = logging.getLogger('master_strategy')
        self.main_logger.setLevel(logging.DEBUG)
        
        # File handler (rotating)
        main_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'master_strategy.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        main_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.main_logger.addHandler(main_handler)
        
        # Trade logger
        self.trade_logger = logging.getLogger('trades')
        trade_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'trades.log',
            maxBytes=5*1024*1024,
            backupCount=10
        )
        trade_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(message)s'
        ))
        self.trade_logger.addHandler(trade_handler)
        
        # Feature logger
        self.feature_logger = logging.getLogger('features')
        feature_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'features.log',
            maxBytes=5*1024*1024,
            backupCount=5
        )
        feature_handler.setFormatter(logging.Formatter(
            '%(asctime)s - [%(name)s] - %(levelname)s - %(message)s'
        ))
        self.feature_logger.addHandler(feature_handler)
        
        # Error logger
        self.error_logger = logging.getLogger('errors')
        error_handler = logging.handlers.RotatingFileHandler(
            self.log_dir / 'errors.log',
            maxBytes=5*1024*1024,
            backupCount=10
        )
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        self.error_logger.addHandler(error_handler)
    
    def log_trade(self, symbol: str, action: str, price: float, size: int,
                 pnl: Optional[float] = None, reasons: Optional[List[str]] = None):
        """Log a trade execution"""
        
        msg = f"{action} {size}x {symbol} @ ${price:.2f}"
        if pnl is not None:
            msg += f" | P&L: ${pnl:+,.0f}"
        
        self.trade_logger.info(msg)
        self.main_logger.info(f"TRADE EXECUTED: {msg}")
        
        if reasons:
            for reason in reasons:
                self.main_logger.debug(f"  - {reason}")
    
    def log_signal(self, symbol: str, action: str, confidence: float,
                  sentiment: str, regime: str, portfolio_health: str):
        """Log trade signal generation"""
        
        msg = (f"Signal: {action} {symbol} | Confidence: {confidence*100:.0f}% | "
               f"Sentiment: {sentiment} | Regime: {regime} | Portfolio: {portfolio_health}")
        
        self.main_logger.info(msg)
    
    def log_feature_metric(self, feature: str, metric: str, value: float):
        """Log feature-specific metrics"""
        
        self.feature_logger.info(f"{feature}: {metric} = {value}")
    
    def log_portfolio_update(self, holdings: Dict[str, int], values: Dict[str, float],
                            total_equity: float):
        """Log portfolio state"""
        
        self.main_logger.debug(f"Portfolio equity: ${total_equity:,.0f}")
        for symbol, qty in holdings.items():
            self.main_logger.debug(f"  {symbol}: {qty} shares @ ${values.get(symbol, 0):.2f}")
    
    def log_warning(self, category: str, message: str):
        """Log warnings"""
        
        self.main_logger.warning(f"[{category}] {message}")
        
        # Write to errors if critical
        if category in ["CRITICAL", "ALERT", "DRAWDOWN"]:
            self.error_logger.warning(f"[{category}] {message}")
    
    def log_error(self, component: str, error: Exception):
        """Log errors"""
        
        self.error_logger.error(f"{component}: {type(error).__name__}: {str(error)}")
        self.main_logger.error(f"{component}: {str(error)}")
    
    def log_daily_summary(self, summary: Dict):
        """Log daily trading summary"""
        
        msg = f"""
DAILY SUMMARY - {summary.get('date', 'N/A')}
{'='*50}
Trades: {summary.get('trades', 0)} | Wins: {summary.get('wins', 0)} | Losses: {summary.get('losses', 0)}
Win Rate: {summary.get('win_rate', 0)*100:.1f}% | Daily P&L: ${summary.get('pnl', 0):+,.0f}
Sharpe: {summary.get('sharpe', 0):.2f} | Max DD: {summary.get('max_dd', 0)*100:.2f}%
Portfolio: {summary.get('portfolio_health', 'N/A')} | Risk Score: {summary.get('risk_score', 0):.0f}
{'='*50}"""
        
        self.main_logger.info(msg)
        self.trade_logger.info(msg)


class AlertSystem:
    """Automated alerts for anomalies"""
    
    def __init__(self, logger: StrategyLogger):
        self.logger = logger
        self.alert_history: List[Dict] = []
        self.thresholds = {
            'max_drawdown': -0.15,
            'daily_loss': -0.05,
            'win_rate_low': 0.30,
            'sharpe_low': 0.80,
            'concentration_high': 0.40
        }
    
    def check_alerts(self, metrics: Dict) -> List[str]:
        """Check all metrics and return active alerts"""
        
        alerts = []
        
        # Check max drawdown
        if metrics.get('max_drawdown', 0) < self.thresholds['max_drawdown']:
            alert = f"🚨 CRITICAL: Max drawdown {metrics['max_drawdown']*100:.2f}%"
            alerts.append(alert)
            self.logger.log_warning("DRAWDOWN", alert)
        
        # Check daily loss
        if metrics.get('daily_return', 0) < self.thresholds['daily_loss']:
            alert = f"⚠️ Large daily loss: {metrics['daily_return']*100:.2f}%"
            alerts.append(alert)
            self.logger.log_warning("LOSS", alert)
        
        # Check win rate
        if metrics.get('win_rate', 1) < self.thresholds['win_rate_low']:
            alert = f"⚠️ Win rate low: {metrics['win_rate']*100:.1f}%"
            alerts.append(alert)
            self.logger.log_warning("PERFORMANCE", alert)
        
        # Check Sharpe
        if metrics.get('sharpe_ratio', 2) < self.thresholds['sharpe_low']:
            alert = f"⚠️ Sharpe ratio low: {metrics['sharpe_ratio']:.2f}"
            alerts.append(alert)
            self.logger.log_warning("RISK", alert)
        
        # Check concentration
        if metrics.get('concentration', 0) > self.thresholds['concentration_high']:
            alert = f"⚠️ Portfolio concentrated: {metrics['concentration']*100:.1f}%"
            alerts.append(alert)
            self.logger.log_warning("PORTFOLIO", alert)
        
        # Record alerts
        if alerts:
            self.alert_history.append({
                'timestamp': datetime.now().isoformat(),
                'alerts': alerts
            })
        
        return alerts
    
    def get_recent_alerts(self, hours: int = 24) -> List[str]:
        """Get alerts from last N hours"""
        
        recent = []
        cutoff = datetime.now().timestamp() - (hours * 3600)
        
        for entry in self.alert_history:
            entry_time = datetime.fromisoformat(entry['timestamp']).timestamp()
            if entry_time > cutoff:
                recent.extend(entry['alerts'])
        
        return recent


class HealthMonitor:
    """Monitor system health and performance"""
    
    def __init__(self, logger: StrategyLogger):
        self.logger = logger
        self.metrics: Dict = {}
        self.start_time = datetime.now()
    
    def record_metric(self, component: str, metric: str, value: float):
        """Record a system metric"""
        
        if component not in self.metrics:
            self.metrics[component] = {}
        
        self.metrics[component][metric] = {
            'value': value,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_health_status(self) -> Dict:
        """Get overall system health"""
        
        uptime = (datetime.now() - self.start_time).total_seconds() / 3600
        
        return {
            'uptime_hours': uptime,
            'total_metrics': sum(len(v) for v in self.metrics.values()),
            'components_active': len(self.metrics),
            'last_update': datetime.now().isoformat(),
            'metrics': self.metrics
        }
    
    def save_metrics(self, filepath: str = "data/system_health.json"):
        """Save health metrics to file"""
        
        health = self.get_health_status()
        
        with open(filepath, 'w') as f:
            json.dump(health, f, indent=2, default=str)


class PerformanceProfiler:
    """Track performance of each feature"""
    
    def __init__(self):
        self.timings: Dict[str, List[float]] = {}
        self.call_counts: Dict[str, int] = {}
    
    def record_call(self, feature: str, duration_ms: float):
        """Record feature call timing"""
        
        if feature not in self.timings:
            self.timings[feature] = []
            self.call_counts[feature] = 0
        
        self.timings[feature].append(duration_ms)
        self.call_counts[feature] += 1
    
    def get_stats(self, feature: str) -> Dict:
        """Get performance stats for a feature"""
        
        if feature not in self.timings:
            return {}
        
        timings = self.timings[feature]
        
        return {
            'feature': feature,
            'call_count': self.call_counts[feature],
            'avg_ms': sum(timings) / len(timings),
            'min_ms': min(timings),
            'max_ms': max(timings),
            'total_ms': sum(timings)
        }
    
    def get_all_stats(self) -> List[Dict]:
        """Get stats for all features"""
        
        return [self.get_stats(feature) for feature in self.timings.keys()]
    
    def print_report(self, logger: logging.Logger):
        """Print performance report"""
        
        logger.info("PERFORMANCE REPORT")
        logger.info("="*50)
        
        for feature in sorted(self.timings.keys()):
            stats = self.get_stats(feature)
            logger.info(
                f"{feature:30s} | "
                f"Calls: {stats['call_count']:5d} | "
                f"Avg: {stats['avg_ms']:7.2f}ms | "
                f"Total: {stats['total_ms']:10.1f}ms"
            )
