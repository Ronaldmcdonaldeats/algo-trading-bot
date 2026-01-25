"""
Observability Stack Module
Prometheus metrics export, performance tracking, system monitoring.
Real-time insights into trading bot operations and health.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import numpy as np
import pandas as pd
from collections import defaultdict
from threading import Lock

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Prometheus metric types"""
    COUNTER = "counter"  # Only increases
    GAUGE = "gauge"  # Can go up or down
    HISTOGRAM = "histogram"  # Distribution
    SUMMARY = "summary"  # Percentiles


@dataclass
class PrometheusMetric:
    """Prometheus metric definition"""
    name: str
    metric_type: MetricType
    help_text: str
    labels: List[str]
    value: float = 0.0
    timestamp: datetime = None


class MetricsCollector:
    """Collects and exports Prometheus metrics"""

    def __init__(self):
        self.metrics: Dict[str, PrometheusMetric] = {}
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.lock = Lock()

    def register_counter(
        self,
        name: str,
        help_text: str,
        labels: List[str] = None,
    ) -> None:
        """Register a counter metric (only increases)"""
        metric_name = self._sanitize_name(name)
        self.metrics[metric_name] = PrometheusMetric(
            name=metric_name,
            metric_type=MetricType.COUNTER,
            help_text=help_text,
            labels=labels or [],
        )
        self.counters[metric_name] = 0.0

    def register_gauge(
        self,
        name: str,
        help_text: str,
        labels: List[str] = None,
    ) -> None:
        """Register a gauge metric (can fluctuate)"""
        metric_name = self._sanitize_name(name)
        self.metrics[metric_name] = PrometheusMetric(
            name=metric_name,
            metric_type=MetricType.GAUGE,
            help_text=help_text,
            labels=labels or [],
        )
        self.gauges[metric_name] = 0.0

    def register_histogram(
        self,
        name: str,
        help_text: str,
        labels: List[str] = None,
    ) -> None:
        """Register a histogram metric"""
        metric_name = self._sanitize_name(name)
        self.metrics[metric_name] = PrometheusMetric(
            name=metric_name,
            metric_type=MetricType.HISTOGRAM,
            help_text=help_text,
            labels=labels or [],
        )
        self.histograms[metric_name] = []

    def increment_counter(self, name: str, value: float = 1.0) -> None:
        """Increment a counter metric"""
        metric_name = self._sanitize_name(name)
        with self.lock:
            self.counters[metric_name] += value

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric"""
        metric_name = self._sanitize_name(name)
        with self.lock:
            self.gauges[metric_name] = value

    def observe_histogram(self, name: str, value: float) -> None:
        """Record a value in histogram"""
        metric_name = self._sanitize_name(name)
        with self.lock:
            self.histograms[metric_name].append(value)
            # Keep only last 1000 observations
            if len(self.histograms[metric_name]) > 1000:
                self.histograms[metric_name] = self.histograms[metric_name][-1000:]

    def get_percentile(self, name: str, percentile: float) -> float:
        """Get percentile from histogram"""
        metric_name = self._sanitize_name(name)
        values = self.histograms.get(metric_name, [])
        if not values:
            return 0.0
        return float(np.percentile(values, percentile))

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []

        # Export counters
        for name, value in self.counters.items():
            if name in self.metrics:
                metric = self.metrics[name]
                lines.append(f"# HELP {name} {metric.help_text}")
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {value}")
                lines.append("")

        # Export gauges
        for name, value in self.gauges.items():
            if name in self.metrics:
                metric = self.metrics[name]
                lines.append(f"# HELP {name} {metric.help_text}")
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {value}")
                lines.append("")

        # Export histograms
        for name, values in self.histograms.items():
            if name in self.metrics and values:
                metric = self.metrics[name]
                lines.append(f"# HELP {name} {metric.help_text}")
                lines.append(f"# TYPE {name} histogram")

                # Bucket boundaries
                buckets = [0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
                for bucket in buckets:
                    count = len([v for v in values if v <= bucket])
                    lines.append(f'{name}_bucket{{le="{bucket}"}} {count}')

                lines.append(f'{name}_bucket{{le="+Inf"}} {len(values)}')
                lines.append(f"{name}_count {len(values)}")
                lines.append(f"{name}_sum {sum(values)}")
                lines.append("")

        return "\n".join(lines)

    def _sanitize_name(self, name: str) -> str:
        """Sanitize metric name for Prometheus"""
        return name.lower().replace("-", "_").replace(".", "_")


class TradingMetrics:
    """Trading-specific metrics"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

        # Register trading metrics
        self.collector.register_counter("trades_total", "Total trades executed")
        self.collector.register_counter("trades_won", "Winning trades")
        self.collector.register_counter("trades_lost", "Losing trades")

        self.collector.register_gauge("portfolio_value", "Current portfolio value")
        self.collector.register_gauge("portfolio_pnl", "Portfolio P&L")
        self.collector.register_gauge("portfolio_pnl_pct", "Portfolio P&L percentage")
        self.collector.register_gauge("portfolio_positions", "Number of open positions")

        self.collector.register_histogram("trade_pnl", "Trade P&L distribution")
        self.collector.register_histogram("trade_duration_seconds", "Trade duration")
        self.collector.register_histogram("order_slippage_bps", "Order slippage in basis points")

        self.collector.register_gauge("win_rate", "Win rate percentage")
        self.collector.register_gauge("profit_factor", "Profit factor")
        self.collector.register_gauge("sharpe_ratio", "Sharpe ratio")
        self.collector.register_gauge("max_drawdown_pct", "Maximum drawdown percentage")

    def record_trade(
        self,
        pnl: float,
        duration_seconds: float,
        is_winning: bool,
    ) -> None:
        """Record a completed trade"""
        self.collector.increment_counter("trades_total", 1.0)
        if is_winning:
            self.collector.increment_counter("trades_won", 1.0)
        else:
            self.collector.increment_counter("trades_lost", 1.0)

        self.collector.observe_histogram("trade_pnl", pnl)
        self.collector.observe_histogram("trade_duration_seconds", duration_seconds)

    def record_order_execution(self, slippage_bps: float) -> None:
        """Record order execution metrics"""
        self.collector.observe_histogram("order_slippage_bps", slippage_bps)

    def update_portfolio_metrics(
        self,
        portfolio_value: float,
        pnl: float,
        pnl_pct: float,
        open_positions: int,
        win_rate: float,
        profit_factor: float,
        sharpe_ratio: float,
        max_drawdown_pct: float,
    ) -> None:
        """Update portfolio metrics"""
        self.collector.set_gauge("portfolio_value", portfolio_value)
        self.collector.set_gauge("portfolio_pnl", pnl)
        self.collector.set_gauge("portfolio_pnl_pct", pnl_pct)
        self.collector.set_gauge("portfolio_positions", open_positions)
        self.collector.set_gauge("win_rate", win_rate)
        self.collector.set_gauge("profit_factor", profit_factor)
        self.collector.set_gauge("sharpe_ratio", sharpe_ratio)
        self.collector.set_gauge("max_drawdown_pct", max_drawdown_pct)


class SystemMetrics:
    """System performance metrics"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

        # Register system metrics
        self.collector.register_gauge("bot_running", "Bot running status (1=running, 0=stopped)")
        self.collector.register_counter("api_requests_total", "Total API requests")
        self.collector.register_gauge("api_requests_in_flight", "In-flight API requests")
        self.collector.register_histogram("api_latency_ms", "API request latency")
        self.collector.register_counter("db_queries_total", "Total database queries")
        self.collector.register_histogram("db_query_duration_ms", "DB query duration")
        self.collector.register_gauge("db_connections_active", "Active DB connections")
        self.collector.register_histogram("cache_hit_duration_ms", "Cache lookup duration")
        self.collector.register_gauge("memory_usage_mb", "Memory usage in MB")
        self.collector.register_gauge("cpu_usage_pct", "CPU usage percentage")

    def record_api_request(self, latency_ms: float) -> None:
        """Record API request"""
        self.collector.increment_counter("api_requests_total", 1.0)
        self.collector.observe_histogram("api_latency_ms", latency_ms)

    def set_api_in_flight(self, count: int) -> None:
        """Set in-flight API request count"""
        self.collector.set_gauge("api_requests_in_flight", float(count))

    def record_db_query(self, duration_ms: float) -> None:
        """Record database query"""
        self.collector.increment_counter("db_queries_total", 1.0)
        self.collector.observe_histogram("db_query_duration_ms", duration_ms)

    def set_db_connections(self, count: int) -> None:
        """Set active DB connection count"""
        self.collector.set_gauge("db_connections_active", float(count))

    def record_cache_hit(self, duration_ms: float) -> None:
        """Record cache hit"""
        self.collector.observe_histogram("cache_hit_duration_ms", duration_ms)

    def update_resource_usage(
        self,
        memory_mb: float,
        cpu_pct: float,
        bot_running: bool = True,
    ) -> None:
        """Update system resource usage"""
        self.collector.set_gauge("memory_usage_mb", memory_mb)
        self.collector.set_gauge("cpu_usage_pct", cpu_pct)
        self.collector.set_gauge("bot_running", 1.0 if bot_running else 0.0)


class AlertRule:
    """Alert rule definition"""

    def __init__(
        self,
        name: str,
        condition_fn,  # Function that returns True if alert should fire
        severity: str = "warning",  # warning, critical
        cooldown_seconds: int = 300,
    ):
        self.name = name
        self.condition_fn = condition_fn
        self.severity = severity
        self.cooldown_seconds = cooldown_seconds
        self.last_alert_time = 0
        self.is_active = False

    def should_alert(self) -> bool:
        """Check if alert should be triggered"""
        current_time = time.time()
        if current_time - self.last_alert_time < self.cooldown_seconds:
            return False

        if self.condition_fn():
            self.last_alert_time = current_time
            self.is_active = True
            return True

        self.is_active = False
        return False


class AlertManager:
    """Manages alert rules and notifications"""

    def __init__(self):
        self.rules: List[AlertRule] = []
        self.active_alerts: List[str] = []

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule"""
        self.rules.append(rule)

    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check all rules and return triggered alerts"""
        triggered_alerts = []

        for rule in self.rules:
            if rule.should_alert():
                triggered_alerts.append({
                    "name": rule.name,
                    "severity": rule.severity,
                    "timestamp": datetime.now(),
                })
                self.active_alerts.append(rule.name)

        return triggered_alerts

    def create_default_alerts(self, collector: MetricsCollector) -> None:
        """Create standard alerts for trading bot"""

        # Alert: High drawdown
        def high_drawdown():
            return collector.gauges.get("max_drawdown_pct", 0) > 10

        self.add_rule(AlertRule(
            "high_drawdown",
            high_drawdown,
            severity="critical",
        ))

        # Alert: Negative P&L day
        def negative_daily_pnl():
            return collector.gauges.get("portfolio_pnl", 0) < 0

        self.add_rule(AlertRule(
            "negative_daily_pnl",
            negative_daily_pnl,
            severity="warning",
        ))

        # Alert: High API latency
        def high_api_latency():
            p95_latency = collector.get_percentile("api_latency_ms", 95)
            return p95_latency > 500

        self.add_rule(AlertRule(
            "high_api_latency",
            high_api_latency,
            severity="warning",
        ))

        # Alert: Database connection issues
        def db_connection_issue():
            return collector.gauges.get("db_connections_active", 0) > 15

        self.add_rule(AlertRule(
            "db_connection_issue",
            db_connection_issue,
            severity="warning",
        ))

        # Alert: Low win rate
        def low_win_rate():
            return collector.gauges.get("win_rate", 100) < 40

        self.add_rule(AlertRule(
            "low_win_rate",
            low_win_rate,
            severity="warning",
        ))


class DashboardMetrics:
    """Real-time metrics for dashboard display"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get overall performance summary for dashboard"""
        return {
            "portfolio_value": self.collector.gauges.get("portfolio_value", 0),
            "daily_pnl": self.collector.gauges.get("portfolio_pnl", 0),
            "daily_return_pct": self.collector.gauges.get("portfolio_pnl_pct", 0),
            "open_positions": int(self.collector.gauges.get("portfolio_positions", 0)),
            "win_rate": self.collector.gauges.get("win_rate", 0),
            "profit_factor": self.collector.gauges.get("profit_factor", 0),
            "sharpe_ratio": self.collector.gauges.get("sharpe_ratio", 0),
            "max_drawdown": self.collector.gauges.get("max_drawdown_pct", 0),
        }

    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get order execution quality metrics"""
        slippage_values = self.collector.histograms.get("order_slippage_bps", [])

        return {
            "avg_slippage_bps": np.mean(slippage_values) if slippage_values else 0,
            "p95_slippage_bps": self.collector.get_percentile("order_slippage_bps", 95),
            "p99_slippage_bps": self.collector.get_percentile("order_slippage_bps", 99),
            "total_orders": int(self.collector.counters.get("trades_total", 0)),
        }

    def get_system_health(self) -> Dict[str, Any]:
        """Get system health metrics"""
        api_latencies = self.collector.histograms.get("api_latency_ms", [])

        return {
            "bot_running": bool(self.collector.gauges.get("bot_running", 0)),
            "api_requests_total": int(self.collector.counters.get("api_requests_total", 0)),
            "avg_api_latency_ms": np.mean(api_latencies) if api_latencies else 0,
            "p95_api_latency_ms": self.collector.get_percentile("api_latency_ms", 95),
            "db_connections": int(self.collector.gauges.get("db_connections_active", 0)),
            "memory_usage_mb": self.collector.gauges.get("memory_usage_mb", 0),
            "cpu_usage_pct": self.collector.gauges.get("cpu_usage_pct", 0),
        }

    def get_trade_analytics(self) -> Dict[str, Any]:
        """Get trade-level analytics"""
        pnl_values = self.collector.histograms.get("trade_pnl", [])
        duration_values = self.collector.histograms.get("trade_duration_seconds", [])

        return {
            "total_trades": int(self.collector.counters.get("trades_total", 0)),
            "winning_trades": int(self.collector.counters.get("trades_won", 0)),
            "losing_trades": int(self.collector.counters.get("trades_lost", 0)),
            "avg_trade_pnl": np.mean(pnl_values) if pnl_values else 0,
            "avg_trade_duration_min": (np.mean(duration_values) / 60) if duration_values else 0,
            "best_trade_pnl": max(pnl_values) if pnl_values else 0,
            "worst_trade_pnl": min(pnl_values) if pnl_values else 0,
        }


class MetricsExporter:
    """Exports metrics in various formats"""

    def __init__(self, collector: MetricsCollector):
        self.collector = collector

    def export_json(self) -> Dict[str, Any]:
        """Export metrics as JSON"""
        return {
            "timestamp": datetime.now().isoformat(),
            "counters": dict(self.collector.counters),
            "gauges": dict(self.collector.gauges),
            "histograms": {
                name: {
                    "count": len(values),
                    "sum": sum(values),
                    "mean": np.mean(values) if values else 0,
                    "p50": float(np.percentile(values, 50)) if values else 0,
                    "p95": float(np.percentile(values, 95)) if values else 0,
                    "p99": float(np.percentile(values, 99)) if values else 0,
                    "min": min(values) if values else 0,
                    "max": max(values) if values else 0,
                }
                for name, values in self.collector.histograms.items()
            },
        }

    def export_dataframe(self) -> pd.DataFrame:
        """Export metrics as DataFrame"""
        data = {
            "metric_name": [],
            "type": [],
            "value": [],
        }

        for name, value in self.collector.counters.items():
            data["metric_name"].append(name)
            data["type"].append("counter")
            data["value"].append(value)

        for name, value in self.collector.gauges.items():
            data["metric_name"].append(name)
            data["type"].append("gauge")
            data["value"].append(value)

        return pd.DataFrame(data)
