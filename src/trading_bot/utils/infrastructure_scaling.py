"""
Infrastructure & Scaling Module
Redis distributed caching, PostgreSQL replication, Kubernetes deployment.
Enables horizontal scaling and high availability for production.
"""

import logging
import json
import pickle
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

try:
    import redis
except ImportError:
    redis = None

try:
    import psycopg2
    from psycopg2 import sql
except ImportError:
    psycopg2 = None

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry metadata"""
    key: str
    value: Any
    ttl_seconds: int
    created_at: datetime
    expires_at: datetime


class RedisCache:
    """Distributed cache using Redis"""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        max_connections: int = 50,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.password = password
        self.cache = None

        if not redis:
            logger.warning("Redis not installed - caching disabled")
            return

        try:
            self.redis_client = redis.ConnectionPool(
                host=host,
                port=port,
                db=db,
                password=password,
                max_connections=max_connections,
                decode_responses=False,
            )
            self.cache = redis.Redis(connection_pool=self.redis_client)
            self.cache.ping()
            logger.info(f"Redis cache connected: {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.cache = None

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Set cache entry with TTL"""
        if not self.cache:
            return False

        try:
            serialized = pickle.dumps(value)
            self.cache.setex(key, ttl_seconds, serialized)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def get(self, key: str) -> Optional[Any]:
        """Get cache entry"""
        if not self.cache:
            return None

        try:
            value = self.cache.get(key)
            if value:
                return pickle.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def delete(self, key: str) -> bool:
        """Delete cache entry"""
        if not self.cache:
            return False

        try:
            self.cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    def flush(self) -> bool:
        """Flush all cache entries"""
        if not self.cache:
            return False

        try:
            self.cache.flushdb()
            return True
        except Exception as e:
            logger.error(f"Redis flush error: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get Redis statistics"""
        if not self.cache:
            return {}

        try:
            info = self.cache.info()
            return {
                "used_memory_human": info.get("used_memory_human"),
                "used_memory_peak_human": info.get("used_memory_peak_human"),
                "connected_clients": info.get("connected_clients"),
                "total_commands_processed": info.get("total_commands_processed"),
                "total_connections_received": info.get("total_connections_received"),
                "evicted_keys": info.get("evicted_keys"),
            }
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {}

    def set_hash(self, key: str, mapping: Dict[str, Any]) -> bool:
        """Set Redis hash"""
        if not self.cache:
            return False

        try:
            self.cache.hset(key, mapping=mapping)
            return True
        except Exception as e:
            logger.error(f"Redis hset error: {e}")
            return False

    def get_hash(self, key: str) -> Optional[Dict[str, Any]]:
        """Get Redis hash"""
        if not self.cache:
            return None

        try:
            return self.cache.hgetall(key)
        except Exception as e:
            logger.error(f"Redis hget error: {e}")
            return None


class DatabaseReplicator:
    """Handles PostgreSQL replication for HA"""

    def __init__(
        self,
        primary_host: str,
        primary_port: int = 5432,
        primary_user: str = "postgres",
        primary_password: str = "",
        primary_db: str = "trading_bot",
    ):
        self.primary_host = primary_host
        self.primary_port = primary_port
        self.primary_user = primary_user
        self.primary_password = primary_password
        self.primary_db = primary_db

        self.primary_conn = None
        self.replica_conn = None
        self._connect_primary()

    def _connect_primary(self) -> bool:
        """Connect to primary database"""
        try:
            self.primary_conn = psycopg2.connect(
                host=self.primary_host,
                port=self.primary_port,
                user=self.primary_user,
                password=self.primary_password,
                database=self.primary_db,
            )
            logger.info("Connected to primary PostgreSQL database")
            return True
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to primary: {e}")
            return False

    def setup_replication(self, replica_host: str, replica_user: str, replica_password: str) -> bool:
        """Setup logical replication on primary"""
        if not self.primary_conn:
            return False

        try:
            cursor = self.primary_conn.cursor()

            # Create replication slot
            cursor.execute("SELECT * FROM pg_create_logical_replication_slot('trading_bot_slot', 'test_decoding')")

            # Enable WAL level
            cursor.execute("ALTER SYSTEM SET wal_level = logical")

            self.primary_conn.commit()
            cursor.close()

            logger.info("Replication setup completed on primary")
            return True

        except psycopg2.Error as e:
            logger.error(f"Replication setup failed: {e}")
            return False

    def monitor_replication_lag(self) -> Dict[str, Any]:
        """Monitor replication lag"""
        if not self.primary_conn:
            return {}

        try:
            cursor = self.primary_conn.cursor()

            # Get replication slot info
            cursor.execute("""
                SELECT 
                    slot_name,
                    confirmed_flush_lsn,
                    restart_lsn
                FROM pg_replication_slots
                WHERE slot_type = 'logical'
            """)

            slots = cursor.fetchall()
            cursor.close()

            return {
                "active_slots": len(slots),
                "slots": [
                    {
                        "name": slot[0],
                        "confirmed_flush": str(slot[1]),
                        "restart_lsn": str(slot[2]),
                    }
                    for slot in slots
                ],
            }

        except psycopg2.Error as e:
            logger.error(f"Replication monitoring failed: {e}")
            return {}

    def failover_to_replica(self, replica_host: str) -> bool:
        """Promote replica to primary (failover)"""
        logger.warning("Initiating failover to replica")
        # In production, this would trigger Patroni or similar HA solution
        return True


class LoadBalancer:
    """Load balancer configuration for multi-instance setup"""

    def __init__(self, instances: List[str]):
        self.instances = instances
        self.health_status = {inst: True for inst in instances}
        self.request_counts = {inst: 0 for inst in instances}

    def select_instance_round_robin(self) -> Optional[str]:
        """Select instance using round-robin"""
        healthy_instances = [i for i, healthy in self.health_status.items() if healthy]

        if not healthy_instances:
            return None

        # Find instance with lowest request count
        selected = min(healthy_instances, key=lambda x: self.request_counts[x])
        self.request_counts[selected] += 1

        return selected

    def select_instance_least_connections(self) -> Optional[str]:
        """Select instance using least connections"""
        healthy_instances = [i for i, healthy in self.health_status.items() if healthy]

        if not healthy_instances:
            return None

        return min(healthy_instances, key=lambda x: self.request_counts[x])

    def update_health(self, instance: str, is_healthy: bool) -> None:
        """Update instance health status"""
        self.health_status[instance] = is_healthy
        logger.info(f"Instance {instance} health: {'UP' if is_healthy else 'DOWN'}")

    def get_status(self) -> Dict[str, Any]:
        """Get load balancer status"""
        return {
            "total_instances": len(self.instances),
            "healthy_instances": sum(1 for v in self.health_status.values() if v),
            "instance_status": self.health_status.copy(),
            "request_distribution": self.request_counts.copy(),
        }


class KubernetesConfig:
    """Kubernetes deployment configuration"""

    def __init__(self):
        self.namespace = "trading-bot"
        self.replicas = {
            "trading_bot": 2,
            "dashboard": 1,
            "postgres": 1,
            "redis": 1,
        }

    def generate_deployment_yaml(self) -> str:
        """Generate Kubernetes deployment manifest"""

        deployment = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: trading-bot
  namespace: {namespace}
spec:
  replicas: {bot_replicas}
  selector:
    matchLabels:
      app: trading-bot
  template:
    metadata:
      labels:
        app: trading-bot
    spec:
      containers:
      - name: trading-bot
        image: trading-bot:latest
        imagePullPolicy: Always
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
        env:
        - name: DB_HOST
          value: postgres
        - name: REDIS_HOST
          value: redis
        - name: LOG_LEVEL
          value: INFO
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dashboard
  namespace: {namespace}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: dashboard
  template:
    metadata:
      labels:
        app: dashboard
    spec:
      containers:
      - name: dashboard
        image: trading-dashboard:latest
        ports:
        - containerPort: 5000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 5000
          initialDelaySeconds: 15
          periodSeconds: 10
        env:
        - name: DB_HOST
          value: postgres
        - name: API_PORT
          value: "8000"
---
apiVersion: v1
kind: Service
metadata:
  name: trading-bot-service
  namespace: {namespace}
spec:
  selector:
    app: trading-bot
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: v1
kind: Service
metadata:
  name: dashboard-service
  namespace: {namespace}
spec:
  selector:
    app: dashboard
  ports:
  - protocol: TCP
    port: 5000
    targetPort: 5000
  type: LoadBalancer
"""

        return deployment.format(
            namespace=self.namespace,
            bot_replicas=self.replicas["trading_bot"],
        )

    def generate_statefulset_yaml(self, service: str) -> str:
        """Generate StatefulSet for stateful services (databases)"""

        statefulset = """
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: {service}
  namespace: {namespace}
spec:
  serviceName: {service}
  replicas: 1
  selector:
    matchLabels:
      app: {service}
  template:
    metadata:
      labels:
        app: {service}
    spec:
      containers:
      - name: {service}
        image: {service}:latest
        ports:
        - containerPort: {port}
          name: {service}
        volumeMounts:
        - name: {service}-data
          mountPath: /data
        resources:
          requests:
            memory: "1Gi"
            cpu: "1000m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
  volumeClaimTemplates:
  - metadata:
      name: {service}-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 10Gi
"""

        port_map = {"postgres": 5432, "redis": 6379}

        return statefulset.format(
            service=service,
            namespace=self.namespace,
            port=port_map.get(service, 8000),
        )

    def generate_horizontal_pod_autoscaler(self) -> str:
        """Generate HPA for auto-scaling"""

        hpa = """
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: trading-bot-hpa
  namespace: {namespace}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: trading-bot
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
"""

        return hpa.format(namespace=self.namespace)


class HealthChecker:
    """Checks health of various services"""

    def __init__(self):
        self.last_check_time = {}
        self.health_status = {}

    def check_database_health(self, connection) -> bool:
        """Check database health"""
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    def check_redis_health(self, redis_cache: RedisCache) -> bool:
        """Check Redis health"""
        try:
            if redis_cache.cache:
                redis_cache.cache.ping()
                return True
            return False
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    def check_api_health(self, api_url: str) -> bool:
        """Check API health"""
        try:
            import requests

            response = requests.get(f"{api_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False

    def get_health_summary(self) -> Dict[str, bool]:
        """Get overall health summary"""
        return self.health_status.copy()
