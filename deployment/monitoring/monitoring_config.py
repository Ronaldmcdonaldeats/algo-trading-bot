"""
Prometheus & Grafana Configuration for Algo Trading Bot Monitoring
Includes: Prometheus server config, alert rules, and Grafana dashboard definitions
"""

import json


PROMETHEUS_CONFIG = """
# Prometheus configuration for Algo Trading Bot

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'algo-trading'
    environment: 'production'

# Alertmanager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

# Load rules once and periodically evaluate them
rule_files:
  - '/etc/prometheus/rules/*.yml'

# Scrape configurations
scrape_configs:
  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Algo Trading Bot Metrics
  - job_name: 'algo-trading-bot'
    metrics_path: '/metrics'
    scheme: 'http'
    scrape_interval: 10s
    scrape_timeout: 5s
    static_configs:
      - targets: ['algo-trading-bot:9090']
        labels:
          group: 'trading'
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance

  # Redis metrics (via redis_exporter)
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance

  # PostgreSQL metrics (via postgres_exporter)
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance

  # Node exporter for system metrics
  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
"""

ALERT_RULES = """
# Alert rules for Algo Trading Bot

groups:
  - name: trading_alerts
    interval: 30s
    rules:
      # Trading Performance Alerts
      - alert: HighDrawdown
        expr: trading_max_drawdown > 0.20
        for: 1h
        labels:
          severity: warning
          component: trading
        annotations:
          summary: "High drawdown detected: {{ $value | humanizePercentage }}"
          description: "Maximum drawdown exceeded 20% for {{ $labels.instance }}"

      - alert: LowWinRate
        expr: trading_win_rate < 0.40
        for: 1h
        labels:
          severity: warning
          component: trading
        annotations:
          summary: "Low win rate: {{ $value | humanizePercentage }}"
          description: "Win rate below 40% for {{ $labels.instance }}"

      - alert: ExcessiveSlippage
        expr: trading_avg_slippage_bps > 50
        for: 30m
        labels:
          severity: warning
          component: trading
        annotations:
          summary: "Excessive slippage: {{ $value }} bps"
          description: "Average slippage exceeded 50 basis points"

      - alert: DailyLossExceeded
        expr: trading_daily_loss > 5000
        for: 5m
        labels:
          severity: critical
          component: trading
        annotations:
          summary: "Daily loss limit exceeded: ${{ $value | humanize }}"
          description: "Daily loss exceeded $5,000 threshold"

      # System Health Alerts
      - alert: HighCPUUsage
        expr: system_cpu_usage > 80
        for: 5m
        labels:
          severity: warning
          component: system
        annotations:
          summary: "High CPU usage: {{ $value | humanizePercentage }}"
          description: "CPU usage exceeded 80% on {{ $labels.instance }}"

      - alert: HighMemoryUsage
        expr: system_memory_usage > 85
        for: 5m
        labels:
          severity: warning
          component: system
        annotations:
          summary: "High memory usage: {{ $value | humanizePercentage }}"
          description: "Memory usage exceeded 85% on {{ $labels.instance }}"

      - alert: LowDiskSpace
        expr: node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.10
        for: 5m
        labels:
          severity: warning
          component: system
        annotations:
          summary: "Low disk space: {{ $value | humanizePercentage }}"
          description: "Less than 10% disk space available"

      # API & Service Alerts
      - alert: HighAPILatency
        expr: system_request_latency_ms > 1000
        for: 5m
        labels:
          severity: warning
          component: api
        annotations:
          summary: "High API latency: {{ $value | humanize }} ms"
          description: "Request latency exceeded 1 second"

      - alert: APIErrorRate
        expr: rate(system_api_errors_total[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
          component: api
        annotations:
          summary: "High API error rate: {{ $value | humanizePercentage }}"
          description: "Error rate exceeded 5% over 5 minutes"

      # Database Alerts
      - alert: PostgreSQLDown
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
          component: database
        annotations:
          summary: "PostgreSQL is down"
          description: "PostgreSQL database is unreachable"

      - alert: PostgreSQLSlowQueries
        expr: postgres_slow_queries_total > 10
        for: 5m
        labels:
          severity: warning
          component: database
        annotations:
          summary: "Slow queries detected: {{ $value }}"
          description: "High number of slow queries on PostgreSQL"

      # Cache Alerts
      - alert: RedisDown
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: critical
          component: cache
        annotations:
          summary: "Redis is down"
          description: "Redis cache is unreachable"

      - alert: RedisMemoryUsage
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.90
        for: 5m
        labels:
          severity: warning
          component: cache
        annotations:
          summary: "High Redis memory usage: {{ $value | humanizePercentage }}"
          description: "Redis memory usage exceeded 90%"
"""

GRAFANA_DASHBOARD_TRADING = {
    "dashboard": {
        "title": "Algo Trading Bot - Trading Metrics",
        "description": "Real-time trading performance monitoring",
        "tags": ["trading", "performance"],
        "timezone": "browser",
        "panels": [
            {
                "title": "Win Rate",
                "type": "stat",
                "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
                "targets": [
                    {
                        "expr": "trading_win_rate",
                        "legendFormat": "Win Rate"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percentunit",
                        "custom": {"hideFrom": {"tooltip": False, "viz": False, "legend": False}},
                        "color": {"mode": "thresholds"},
                        "thresholds": {"mode": "percentage", "steps": [
                            {"color": "red", "value": 0},
                            {"color": "yellow", "value": 40},
                            {"color": "green", "value": 50}
                        ]}
                    }
                }
            },
            {
                "title": "Total P&L",
                "type": "stat",
                "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4},
                "targets": [
                    {
                        "expr": "trading_total_pnl",
                        "legendFormat": "P&L"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "currencyUSD",
                        "custom": {"hideFrom": {"tooltip": False, "viz": False, "legend": False}},
                        "color": {"mode": "thresholds"},
                        "thresholds": {"mode": "percentage", "steps": [
                            {"color": "red", "value": -10000},
                            {"color": "yellow", "value": 0},
                            {"color": "green", "value": 10000}
                        ]}
                    }
                }
            },
            {
                "title": "Max Drawdown",
                "type": "stat",
                "gridPos": {"x": 12, "y": 0, "w": 6, "h": 4},
                "targets": [
                    {
                        "expr": "trading_max_drawdown",
                        "legendFormat": "Max DD"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percentunit",
                        "custom": {"hideFrom": {"tooltip": False, "viz": False, "legend": False}},
                        "color": {"mode": "thresholds"},
                        "thresholds": {"mode": "percentage", "steps": [
                            {"color": "green", "value": 0},
                            {"color": "yellow", "value": 15},
                            {"color": "red", "value": 25}
                        ]}
                    }
                }
            },
            {
                "title": "Trade Count",
                "type": "stat",
                "gridPos": {"x": 18, "y": 0, "w": 6, "h": 4},
                "targets": [
                    {
                        "expr": "trading_total_trades",
                        "legendFormat": "Trades"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "short",
                        "color": {"mode": "value"}
                    }
                }
            },
            {
                "title": "Portfolio Value Over Time",
                "type": "timeseries",
                "gridPos": {"x": 0, "y": 4, "w": 12, "h": 8},
                "targets": [
                    {
                        "expr": "trading_portfolio_value",
                        "legendFormat": "Portfolio Value"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "currencyUSD",
                        "custom": {"lineWidth": 2}
                    }
                }
            },
            {
                "title": "Equity Curve (Cumulative Returns)",
                "type": "timeseries",
                "gridPos": {"x": 12, "y": 4, "w": 12, "h": 8},
                "targets": [
                    {
                        "expr": "trading_cumulative_return",
                        "legendFormat": "Return %"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percentunit",
                        "custom": {"lineWidth": 2}
                    }
                }
            },
            {
                "title": "Daily P&L Distribution",
                "type": "histogram",
                "gridPos": {"x": 0, "y": 12, "w": 12, "h": 6},
                "targets": [
                    {
                        "expr": "histogram_quantile(0.95, trading_daily_pnl)",
                        "legendFormat": "P&L Distribution"
                    }
                ]
            },
            {
                "title": "Slippage Analysis",
                "type": "timeseries",
                "gridPos": {"x": 12, "y": 12, "w": 12, "h": 6},
                "targets": [
                    {
                        "expr": "trading_avg_slippage_bps",
                        "legendFormat": "Avg Slippage (bps)"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "short",
                        "custom": {"lineWidth": 1}
                    }
                }
            }
        ]
    }
}

GRAFANA_DASHBOARD_SYSTEM = {
    "dashboard": {
        "title": "Algo Trading Bot - System Health",
        "description": "System resource usage and health metrics",
        "tags": ["system", "infrastructure"],
        "timezone": "browser",
        "panels": [
            {
                "title": "CPU Usage",
                "type": "timeseries",
                "gridPos": {"x": 0, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "expr": "system_cpu_usage",
                        "legendFormat": "CPU %"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percent",
                        "custom": {"lineWidth": 2},
                        "thresholds": {"mode": "percentage", "steps": [
                            {"color": "green", "value": 0},
                            {"color": "yellow", "value": 70},
                            {"color": "red", "value": 90}
                        ]}
                    }
                }
            },
            {
                "title": "Memory Usage",
                "type": "timeseries",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 6},
                "targets": [
                    {
                        "expr": "system_memory_usage",
                        "legendFormat": "Memory %"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percent",
                        "custom": {"lineWidth": 2},
                        "thresholds": {"mode": "percentage", "steps": [
                            {"color": "green", "value": 0},
                            {"color": "yellow", "value": 75},
                            {"color": "red", "value": 90}
                        ]}
                    }
                }
            },
            {
                "title": "API Request Latency",
                "type": "timeseries",
                "gridPos": {"x": 0, "y": 6, "w": 12, "h": 6},
                "targets": [
                    {
                        "expr": "system_request_latency_ms",
                        "legendFormat": "Latency (ms)"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "ms",
                        "custom": {"lineWidth": 1}
                    }
                }
            },
            {
                "title": "Error Rate",
                "type": "timeseries",
                "gridPos": {"x": 12, "y": 6, "w": 12, "h": 6},
                "targets": [
                    {
                        "expr": "rate(system_api_errors_total[5m])",
                        "legendFormat": "Error Rate"
                    }
                ],
                "fieldConfig": {
                    "defaults": {
                        "unit": "percentunit",
                        "custom": {"lineWidth": 2},
                        "thresholds": {"mode": "percentage", "steps": [
                            {"color": "green", "value": 0},
                            {"color": "yellow", "value": 0.02},
                            {"color": "red", "value": 0.05}
                        ]}
                    }
                }
            }
        ]
    }
}


def save_prometheus_config(filepath="prometheus.yml"):
    """Save Prometheus configuration"""
    with open(filepath, "w") as f:
        f.write(PROMETHEUS_CONFIG)
    print(f"✓ Saved: {filepath}")


def save_alert_rules(filepath="alert-rules.yml"):
    """Save alert rules"""
    with open(filepath, "w") as f:
        f.write(ALERT_RULES)
    print(f"✓ Saved: {filepath}")


def save_grafana_dashboards(output_dir="."):
    """Save Grafana dashboard definitions"""
    from pathlib import Path
    Path(output_dir).mkdir(exist_ok=True)

    # Save trading dashboard
    with open(f"{output_dir}/grafana-dashboard-trading.json", "w") as f:
        json.dump(GRAFANA_DASHBOARD_TRADING, f, indent=2)
    print(f"✓ Saved: {output_dir}/grafana-dashboard-trading.json")

    # Save system dashboard
    with open(f"{output_dir}/grafana-dashboard-system.json", "w") as f:
        json.dump(GRAFANA_DASHBOARD_SYSTEM, f, indent=2)
    print(f"✓ Saved: {output_dir}/grafana-dashboard-system.json")


if __name__ == "__main__":
    import sys
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    
    save_prometheus_config()
    save_alert_rules()
    save_grafana_dashboards(output_dir)
    
    print("\n✓ Monitoring configuration complete!")
    print("\nNext steps:")
    print("1. Deploy Prometheus: kubectl apply -f prometheus-deployment.yaml")
    print("2. Deploy Grafana: kubectl apply -f grafana-deployment.yaml")
    print("3. Import dashboards in Grafana UI")
    print("4. Configure alerting rules")
