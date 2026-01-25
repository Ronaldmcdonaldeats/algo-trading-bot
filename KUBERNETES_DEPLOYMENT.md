# Kubernetes Deployment Guide

## Overview

This guide covers deploying the Algo Trading Bot to a Kubernetes cluster with full HA, monitoring, and auto-scaling capabilities.

**Deployment Includes:**
- 3 replicas of trading bot (rolling updates, zero downtime)
- 3 replicas of Redis (distributed cache with persistence)
- 2 replicas of PostgreSQL (primary + replica for HA)
- Prometheus metrics export (port 9090)
- REST API (port 8000) + WebSocket (port 8001)
- Horizontal Pod Autoscaler (3-10 replicas based on CPU/Memory)
- Network policies for security
- Pod Disruption Budgets for availability

## Prerequisites

### Required Tools
```bash
kubectl v1.24+
docker v20.10+
Kubernetes cluster v1.24+ (local k3s, EKS, GKE, AKS, etc.)
```

### Setup kubectl
```bash
# Configure cluster access
kubectl config use-context <your-cluster-context>

# Verify connection
kubectl cluster-info
kubectl get nodes
```

### Setup Docker Registry
```bash
# Option 1: Use Docker Hub
docker login

# Option 2: Use private registry (edit deploy.sh REGISTRY variable)
export REGISTRY="your-registry.azurecr.io/algo-trading"
```

## Quick Start

### 1. Review Configuration
```bash
# Edit deploy.sh to set:
REGISTRY="docker.io"  # Your Docker registry
NAMESPACE="algo-trading"  # Kubernetes namespace
```

### 2. Set Secrets
```bash
# Edit k8s-deployment.yaml - CHANGE THESE BEFORE PRODUCTION:
- DATABASE_PASSWORD (postgres)
- REDIS_PASSWORD
- ALPACA_API_KEY
- ALPACA_SECRET_KEY

# Or use kubectl secrets:
kubectl create secret generic algo-trading-secrets \
  --from-literal=DATABASE_USER=algo_trader \
  --from-literal=DATABASE_PASSWORD=SecurePass123 \
  --from-literal=REDIS_PASSWORD=SecurePass456 \
  --from-literal=ALPACA_API_KEY=your-key \
  --from-literal=ALPACA_SECRET_KEY=your-secret \
  --namespace=algo-trading
```

### 3. Deploy to Dev Environment
```bash
chmod +x deploy.sh

./deploy.sh dev apply      # Apply manifests to cluster
./deploy.sh dev status     # Check deployment status
./deploy.sh dev logs       # View logs
./deploy.sh dev port-forward  # Access locally
```

### 4. Access the Bot
```bash
# After port-forward:
curl http://localhost:8000/health
curl http://localhost:9090/metrics
```

## Deployment Actions

### Full Deployment (Build → Push → Deploy)
```bash
./deploy.sh prod deploy
```

This will:
1. Build Docker image
2. Push to registry
3. Apply Kubernetes manifests
4. Roll out deployment
5. Check status

### Just Apply Manifests (No Build)
```bash
./deploy.sh prod apply
```

### Roll Out New Version
```bash
./deploy.sh prod rollout
```

### Check Status
```bash
./deploy.sh prod status
```

### View Logs
```bash
./deploy.sh prod logs

# Or manually:
kubectl logs -f deployment/algo-trading-bot -n algo-trading --tail=100
```

### Port Forward for Local Access
```bash
./deploy.sh prod port-forward

# Endpoints available:
# API: http://localhost:8000
# WebSocket: ws://localhost:8001
# Metrics: http://localhost:9090
```

### Delete Deployment
```bash
./deploy.sh prod delete
```

## Architecture

### Network Diagram
```
Internet
    ↓
LoadBalancer Service (port 80, 8000)
    ↓
algo-trading-bot Pod (x3)
    ├→ Redis StatefulSet (x3)
    └→ PostgreSQL StatefulSet (x2)
```

### Service Mesh
- **algo-trading-bot-api**: LoadBalancer service on ports 80/8000/8001
- **algo-trading-bot-metrics**: ClusterIP for Prometheus on port 9090
- **redis-service**: Headless service for Redis StatefulSet
- **postgres-service**: Headless service for PostgreSQL StatefulSet

### Scaling Behavior

**Horizontal Pod Autoscaler (HPA)**
- Minimum: 3 replicas
- Maximum: 10 replicas
- CPU threshold: 70%
- Memory threshold: 80%
- Scale up: 100% per 30s (aggressive)
- Scale down: 50% per 60s (conservative)

Example:
```bash
# Monitor autoscaling in real-time
kubectl get hpa -n algo-trading --watch
```

## Environment-Specific Configuration

### Development
```bash
./deploy.sh dev apply
# Environment: development
# Log Level: DEBUG
# Replicas: 3 (no HPA)
# Resources: 500m CPU, 1Gi RAM per pod
```

### Staging
```bash
./deploy.sh staging apply
# Environment: staging
# Log Level: INFO
# Replicas: 3-5 (HPA enabled)
# Resources: 500m CPU, 1Gi RAM per pod
```

### Production
```bash
./deploy.sh prod apply
# Environment: production
# Log Level: WARN
# Replicas: 3-10 (aggressive HPA)
# Resources: 500m CPU, 1Gi RAM per pod (up to 2000m/4Gi per pod)
# Pod Disruption Budgets: Minimum 2 replicas
# Network Policies: Strict (only allowed traffic)
```

## Monitoring & Observability

### Prometheus Metrics
```bash
# Expose metrics locally
kubectl port-forward -n algo-trading svc/algo-trading-bot-metrics 9090:9090

# Access: http://localhost:9090
# Metrics endpoint: /metrics
```

### Available Metrics
- `trading_trades_executed_total` - Total trades executed
- `trading_pnl` - Profit/Loss
- `trading_win_rate` - Win rate percentage
- `trading_avg_slippage_bps` - Average slippage (basis points)
- `trading_drawdown` - Maximum drawdown
- `system_cpu_usage` - CPU usage
- `system_memory_usage` - Memory usage
- `system_request_latency_ms` - API request latency

### Health Checks
```bash
# Liveness (pod restart if unhealthy for 30s)
curl http://localhost:8000/health

# Readiness (removed from LB if not ready for 10s)
curl http://localhost:8000/ready
```

## Persistence

### Redis Data
- Storage: Persistent Volume (10Gi per replica)
- Strategy: Master-Replica replication
- Persistence: AOF (Append-Only File)

### PostgreSQL Data
- Storage: Persistent Volume (50Gi per replica)
- Strategy: Primary-Standby streaming replication
- Backups: Enable automated backups in production

## Security

### RBAC (Role-Based Access Control)
- Service account: `algo-trading-bot`
- Permissions: Read ConfigMaps, Read Secrets

### Network Policies
- Ingress: Only from specified sources
- Egress: Only to Redis, PostgreSQL, and external APIs
- DNS: Allowed for external connectivity

### Pod Security
- Non-root user (UID 1000)
- Read-only root filesystem
- No privilege escalation
- Dropped all capabilities

## Troubleshooting

### Pods Not Starting
```bash
kubectl describe pod -n algo-trading <pod-name>
kubectl logs -n algo-trading <pod-name> --previous
```

### Redis Connection Issues
```bash
# Test Redis connectivity from pod
kubectl exec -it -n algo-trading <pod-name> -- redis-cli -h redis-0.redis-service ping
```

### PostgreSQL Connection Issues
```bash
# Test PostgreSQL connectivity
kubectl exec -it -n algo-trading <pod-name> -- \
  psql -h postgres-0.postgres-service -U algo_trader -d algo_trading_db
```

### OOMKilled (Out of Memory)
```bash
# Increase memory limits in k8s-deployment.yaml
# resources:
#   limits:
#     memory: 8Gi  # Increase from 4Gi
```

### High CPU Usage
```bash
# Check if autoscaler is active
kubectl get hpa -n algo-trading

# View autoscaler events
kubectl describe hpa algo-trading-bot-hpa -n algo-trading
```

## Advanced Operations

### Rolling Update Strategy
```bash
# Update deployment with new image
kubectl set image deployment/algo-trading-bot \
  algo-trading-bot=myregistry/algo-trading-bot:v2 \
  -n algo-trading --record

# Monitor rollout
kubectl rollout status deployment/algo-trading-bot -n algo-trading

# Rollback if needed
kubectl rollout undo deployment/algo-trading-bot -n algo-trading
```

### Manual Scaling
```bash
# Scale to 5 replicas
kubectl scale deployment algo-trading-bot --replicas=5 -n algo-trading
```

### Update ConfigMap (Environment Variables)
```bash
# Edit and apply
kubectl edit configmap algo-trading-config -n algo-trading

# Pods will restart to pick up new values (if not using reload sidecar)
kubectl rollout restart deployment/algo-trading-bot -n algo-trading
```

### Backup PostgreSQL
```bash
# Create backup
kubectl exec -it -n algo-trading postgres-0 -- \
  pg_dump -U algo_trader algo_trading_db > backup.sql

# Restore from backup
kubectl exec -i -n algo-trading postgres-0 -- \
  psql -U algo_trader algo_trading_db < backup.sql
```

## Performance Tuning

### Adjust Resource Requests/Limits
```yaml
# In k8s-deployment.yaml:
resources:
  requests:
    cpu: 500m      # Min guaranteed
    memory: 1Gi    # Min guaranteed
  limits:
    cpu: 2000m     # Max allowed
    memory: 4Gi    # Max allowed
```

### Enable Container Lifecycle Pre-stop Hook
```yaml
# Graceful shutdown
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 15"]
```

### Redis Optimization
```bash
# Increase maxclients in Redis config
maxclients 10000

# Enable persistence for data durability
appendonly yes
appendfsync everysec
```

## Cost Optimization

1. **Adjust HPA limits** - Reduce max replicas if not needed
2. **Use spot instances** - AWS Spot, GCP Preemptibles for non-critical workloads
3. **Right-size resources** - Monitor actual usage and adjust requests/limits
4. **Enable cluster autoscaling** - Let cloud provider scale underlying nodes
5. **Set Pod Disruption Budgets** - Allow cluster autoscaler to evict safely

## Next Steps

1. **Setup Prometheus + Grafana**
   - Deploy Prometheus to scrape `/metrics` endpoint
   - Create Grafana dashboards for visualization

2. **Setup CI/CD Pipeline**
   - GitHub Actions / GitLab CI to auto-deploy on code push
   - Automated testing before deployment

3. **Enable Distributed Tracing**
   - Deploy Jaeger for request tracing
   - Identify performance bottlenecks

4. **Setup Log Aggregation**
   - Deploy ELK Stack (Elasticsearch, Logstash, Kibana)
   - Centralize logging from all pods

5. **Backup Strategy**
   - Enable automated PostgreSQL backups
   - Setup Redis backup to S3

## Support & Documentation

- Kubernetes Docs: https://kubernetes.io/docs
- kubectl Cheat Sheet: https://kubernetes.io/docs/reference/kubectl/cheatsheet/
- Helm Charts: https://helm.sh (optional - for easier deployments)
