# Prometheus & Grafana Monitoring Guide

## Overview

This guide covers setting up Prometheus for metrics collection and Grafana for visualization of Algo Trading Bot performance.

## Architecture

```
Algo Trading Bot
    ↓ (Prometheus metrics on :9090/metrics)
Prometheus Server
    ↓ (Data queries)
Grafana Dashboard
    ↓ (Visualization)
User Browser
```

## Quick Start

### 1. Generate Configuration Files

```bash
# Generate Prometheus config, alert rules, and Grafana dashboards
python monitoring/monitoring_config.py

# Output:
# ✓ Saved: prometheus.yml
# ✓ Saved: alert-rules.yml
# ✓ Saved: grafana-dashboard-trading.json
# ✓ Saved: grafana-dashboard-system.json
```

### 2. Deploy to Kubernetes

```bash
# Deploy Prometheus and Grafana
kubectl apply -f monitoring/prometheus-grafana-k8s.yaml

# Verify deployment
kubectl get deployments -n algo-trading
kubectl get pods -n algo-trading
```

### 3. Access Grafana

```bash
# Port-forward Grafana
kubectl port-forward -n algo-trading svc/grafana 3000:3000

# Access: http://localhost:3000
# Default credentials:
#   Username: admin
#   Password: admin (change in production!)
```

### 4. Import Dashboards

1. Open Grafana UI (http://localhost:3000)
2. Go to: Dashboards → Import
3. Upload `grafana-dashboard-trading.json`
4. Upload `grafana-dashboard-system.json`
5. Select Prometheus as data source

## Available Metrics

### Trading Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `trading_trades_executed_total` | Counter | Total trades executed |
| `trading_total_pnl` | Gauge | Total profit/loss |
| `trading_win_rate` | Gauge | Winning trade percentage (0-1) |
| `trading_total_return_pct` | Gauge | Total return percentage |
| `trading_max_drawdown` | Gauge | Maximum drawdown |
| `trading_sharpe_ratio` | Gauge | Sharpe ratio |
| `trading_avg_slippage_bps` | Gauge | Average slippage in basis points |
| `trading_daily_loss` | Gauge | Daily loss amount |
| `trading_portfolio_value` | Gauge | Current portfolio value |
| `trading_cumulative_return` | Gauge | Cumulative return percentage |

### System Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `system_cpu_usage` | Gauge | CPU usage percentage (0-100) |
| `system_memory_usage` | Gauge | Memory usage percentage (0-100) |
| `system_request_latency_ms` | Histogram | API request latency |
| `system_api_errors_total` | Counter | Total API errors |
| `system_request_duration_seconds` | Histogram | Request duration in seconds |

### Infrastructure Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `redis_connected_clients` | Gauge | Redis connected clients |
| `redis_memory_used_bytes` | Gauge | Redis memory usage |
| `postgres_connections` | Gauge | PostgreSQL connections |
| `postgres_slow_queries_total` | Counter | Slow queries |

## Dashboard Overview

### Trading Dashboard

**Main Cards:**
- Win Rate - Percentage of winning trades (target: 50%+)
- Total P&L - Cumulative profit/loss
- Max Drawdown - Largest peak-to-trough decline
- Trade Count - Total trades executed

**Charts:**
- Portfolio Value Over Time - Equity curve
- Cumulative Returns - Return percentage over time
- Daily P&L Distribution - Distribution of daily returns
- Slippage Analysis - Execution quality metrics

### System Health Dashboard

**Main Cards:**
- CPU Usage - % of CPU utilized
- Memory Usage - % of RAM utilized
- API Latency - Average request time (ms)
- Error Rate - % of failed requests

**Charts:**
- CPU Over Time - CPU usage timeline
- Memory Over Time - Memory usage timeline
- API Request Latency - Latency distribution
- Error Rate Timeline - Error trends

## Alerting Rules

### Trading Alerts

**Alert: High Drawdown**
- Triggers when: Max drawdown > 20%
- Duration: 1 hour
- Severity: Warning
- Action: Review risk management

**Alert: Low Win Rate**
- Triggers when: Win rate < 40%
- Duration: 1 hour
- Severity: Warning
- Action: Analyze strategy effectiveness

**Alert: Excessive Slippage**
- Triggers when: Average slippage > 50 basis points
- Duration: 30 minutes
- Severity: Warning
- Action: Check market conditions / order execution

**Alert: Daily Loss Exceeded**
- Triggers when: Daily loss > $5,000
- Duration: 5 minutes
- Severity: Critical
- Action: Halt trading / investigate

### System Alerts

**Alert: High CPU Usage**
- Triggers when: CPU > 80%
- Duration: 5 minutes
- Severity: Warning
- Action: Scale up or optimize code

**Alert: High Memory Usage**
- Triggers when: Memory > 85%
- Duration: 5 minutes
- Severity: Warning
- Action: Check for memory leaks / scale up

**Alert: API Latency**
- Triggers when: Request latency > 1000ms
- Duration: 5 minutes
- Severity: Warning
- Action: Investigate performance bottlenecks

## Advanced Configuration

### Custom Metrics

Add custom metrics to your trading bot:

```python
from metrics_exporter import MetricsCollector

collector = MetricsCollector()

# Counter metric
collector.increment_counter("trades_executed", labels={"strategy": "momentum"})

# Gauge metric
collector.set_gauge("portfolio_value", 100000, labels={"account": "main"})

# Histogram metric
collector.record_histogram("slippage_bps", 15, labels={"symbol": "AAPL"})
```

### Custom Dashboards

Edit `monitoring_config.py` to add custom panels:

```python
CUSTOM_PANEL = {
    "title": "My Custom Panel",
    "type": "timeseries",
    "targets": [{"expr": "my_custom_metric"}],
    "gridPos": {"x": 0, "y": 0, "w": 12, "h": 6}
}
```

### Alert Webhooks

Configure AlertManager to send notifications:

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: 'slack'
  
receivers:
- name: 'slack'
  slack_configs:
  - api_url: 'YOUR_SLACK_WEBHOOK_URL'
    channel: '#alerts'
    title: 'Trading Alert'
```

## Troubleshooting

### Metrics Not Appearing

1. Check Prometheus is scraping:
   - Visit `http://prometheus:9090/targets`
   - Verify status is "UP"

2. Verify metrics endpoint:
   ```bash
   curl http://algo-trading-bot:9090/metrics
   ```

3. Check Prometheus logs:
   ```bash
   kubectl logs -n algo-trading deployment/prometheus
   ```

### High Cardinality Issues

If you see high memory usage, check for high-cardinality labels:

```bash
# Query high cardinality metrics
curl 'http://prometheus:9090/api/v1/label/__name__/values' | grep trading
```

### Grafana Dashboard Not Updating

1. Check data source connection:
   - Grafana → Configuration → Data Sources
   - Test connection to Prometheus

2. Verify refresh interval:
   - Dashboard settings → General → Auto-refresh

3. Check time range matches data:
   - Ensure you're viewing time period with data

## Performance Tuning

### Prometheus Storage

Adjust retention based on storage capacity:

```yaml
# prometheus.yml
--storage.tsdb.retention.time=30d  # Keep 30 days of data
--storage.tsdb.retention.size=10GB  # Or limit by size
```

### Scrape Intervals

Balance accuracy vs load:

```yaml
global:
  scrape_interval: 15s    # More frequent = more storage
  evaluation_interval: 15s
```

### Query Optimization

Use efficient PromQL queries:

```promql
# Good: specific label matcher
trading_total_pnl{instance="bot-1"}

# Avoid: high cardinality without grouping
trading_total_pnl
```

## Integration with Alerting Systems

### Slack Notifications
```bash
# Setup Slack webhook and configure AlertManager
kubectl create secret generic slack-webhook \
  --from-literal=webhook_url=https://hooks.slack.com/...
```

### PagerDuty Integration
```bash
# For critical alerts
kubectl create secret generic pagerduty-key \
  --from-literal=integration_key=...
```

### Email Notifications
```bash
# SMTP configuration for email alerts
kubectl create secret generic smtp-creds \
  --from-literal=username=... \
  --from-literal=password=...
```

## Backup & Recovery

### Prometheus Data Backup

```bash
# Backup Prometheus data
kubectl exec -n algo-trading prometheus-0 -- \
  tar czf /tmp/prometheus-backup.tar.gz /prometheus

kubectl cp algo-trading/prometheus-0:/tmp/prometheus-backup.tar.gz ./
```

### Grafana Dashboards Backup

```bash
# Export all dashboards
for id in $(curl -s http://localhost:3000/api/search?query=* | grep '"id"' | awk '{print $2}'); do
  curl -s http://localhost:3000/api/dashboards/uid/$id > dashboard_$id.json
done
```

## Best Practices

1. **Set Appropriate Thresholds**
   - Win Rate: >50% for profitable strategies
   - Drawdown: <20% maximum acceptable loss
   - Slippage: <50 basis points

2. **Monitor Early Warning Indicators**
   - Increasing slippage (execution deterioration)
   - Rising error rates (system stability)
   - Memory growth (possible leak)

3. **Regular Review**
   - Weekly: Review P&L and risk metrics
   - Daily: Check alerts and system health
   - Monthly: Analyze performance trends

4. **Maintain Dashboards**
   - Keep thresholds current
   - Update alerts as trading parameters change
   - Document custom metrics

## Next Steps

1. **Enable Alerting**
   - Configure Slack/PagerDuty integration
   - Test alert delivery

2. **Add Custom Dashboards**
   - Create strategy-specific dashboards
   - Add risk analysis views

3. **Setup Data Export**
   - Export daily reports to BI system
   - Archive historical performance data

4. **Integrate with ML**
   - Send metrics to ML pipeline
   - Detect anomalies automatically
