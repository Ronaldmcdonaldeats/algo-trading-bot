"""Database query optimization and indexing."""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import logging
from sqlalchemy import text, Index
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Strategic indexes for common queries
RECOMMENDED_INDEXES = [
    # Fills queries (most frequent)
    "CREATE INDEX IF NOT EXISTS idx_fills_symbol ON fills(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_fills_entry_symbol ON fills(entry_symbol)",
    "CREATE INDEX IF NOT EXISTS idx_fills_exit_symbol ON fills(exit_symbol)",
    "CREATE INDEX IF NOT EXISTS idx_fills_ts ON fills(ts)",
    "CREATE INDEX IF NOT EXISTS idx_fills_symbol_ts ON fills(symbol, ts)",
    
    # Orders queries
    "CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)",
    
    # Portfolio snapshots (for reporting)
    "CREATE INDEX IF NOT EXISTS idx_portfolio_snapshot_ts ON portfolio_snapshots(ts)",
    "CREATE INDEX IF NOT EXISTS idx_position_snapshot_ts ON position_snapshots(ts)",
    
    # Event lookups
    "CREATE INDEX IF NOT EXISTS idx_event_type ON events(type)",
    "CREATE INDEX IF NOT EXISTS idx_event_ts ON events(ts)",
    "CREATE INDEX IF NOT EXISTS idx_event_type_ts ON events(type, ts)",
]


class DatabaseOptimizer:
    """Optimize database queries and schema."""
    
    def __init__(self, engine):
        """Initialize optimizer.
        
        Args:
            engine: SQLAlchemy engine
        """
        self.engine = engine
    
    def apply_indexes(self) -> Dict[str, bool]:
        """Apply recommended indexes.
        
        Returns:
            Dict of index_name -> success
        """
        results = {}
        
        with Session(self.engine) as session:
            for index_sql in RECOMMENDED_INDEXES:
                try:
                    session.execute(text(index_sql))
                    session.commit()
                    
                    # Extract index name
                    index_name = index_sql.split("idx_")[1].split(" ")[0] if "idx_" in index_sql else "unknown"
                    results[index_name] = True
                    logger.info(f"Applied index: idx_{index_name}")
                except Exception as e:
                    results[index_sql[:30]] = False
                    logger.debug(f"Index already exists or failed: {str(e)[:50]}")
        
        return results
    
    def analyze_indexes(self) -> Dict[str, Any]:
        """Analyze current indexes.
        
        Returns:
            Index analysis report
        """
        with Session(self.engine) as session:
            # SQLite-specific index listing
            query = text("""
                SELECT name, tbl_name, sql 
                FROM sqlite_master 
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
                ORDER BY tbl_name
            """)
            
            indexes = session.execute(query).fetchall()
            
            analysis = {}
            for idx_name, tbl_name, sql in indexes:
                if tbl_name not in analysis:
                    analysis[tbl_name] = []
                
                analysis[tbl_name].append({
                    "name": idx_name,
                    "sql": sql,
                })
            
            return analysis
    
    def get_table_stats(self) -> Dict[str, Any]:
        """Get table row counts and sizes.
        
        Returns:
            Table statistics
        """
        with Session(self.engine) as session:
            stats = {}
            
            tables = ["fills", "orders", "portfolio_snapshots", "position_snapshots", "events"]
            
            for table in tables:
                try:
                    # Row count
                    count_query = text(f"SELECT COUNT(*) FROM {table}")
                    count = session.execute(count_query).scalar()
                    
                    stats[table] = {
                        "rows": count,
                        "estimated_size_kb": count * 0.5,  # Rough estimate
                    }
                except Exception as e:
                    logger.debug(f"Could not get stats for {table}: {e}")
            
            return stats


class QueryOptimizer:
    """Optimize common query patterns."""
    
    def __init__(self, session: Session):
        """Initialize query optimizer.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def get_latest_fills(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get latest fills (optimized).
        
        Args:
            limit: Number of fills to return
            
        Returns:
            List of fill records
        """
        query = text("""
            SELECT * FROM fills 
            ORDER BY ts DESC 
            LIMIT :limit
        """)
        
        return self.session.execute(query, {"limit": limit}).fetchall()
    
    def get_symbol_history(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get fill history for symbol (uses index).
        
        Args:
            symbol: Stock symbol
            limit: Number of records
            
        Returns:
            List of fills for symbol
        """
        query = text("""
            SELECT * FROM fills 
            WHERE symbol = :symbol 
            ORDER BY ts DESC 
            LIMIT :limit
        """)
        
        return self.session.execute(query, {"symbol": symbol, "limit": limit}).fetchall()
    
    def get_daily_statistics(self, date_str: str) -> Dict[str, Any]:
        """Get daily trading stats (batch query).
        
        Args:
            date_str: Date string (YYYY-MM-DD)
            
        Returns:
            Daily statistics
        """
        query = text("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN qty > 0 THEN 1 ELSE 0 END) as buys,
                SUM(CASE WHEN qty < 0 THEN 1 ELSE 0 END) as sells,
                COUNT(DISTINCT symbol) as unique_symbols,
                AVG(price) as avg_price
            FROM fills 
            WHERE DATE(ts) = :date
        """)
        
        result = self.session.execute(query, {"date": date_str}).first()
        
        if result:
            return {
                "total_trades": result[0],
                "buys": result[1],
                "sells": result[2],
                "unique_symbols": result[3],
                "avg_price": result[4],
            }
        
        return {}
    
    def get_portfolio_performance(self) -> Dict[str, Any]:
        """Get overall portfolio performance (single query).
        
        Returns:
            Portfolio performance metrics
        """
        query = text("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN qty > 0 THEN 1 ELSE 0 END) as total_buys,
                SUM(CASE WHEN qty < 0 THEN 1 ELSE 0 END) as total_sells
            FROM fills
        """)
        
        result = self.session.execute(query).first()
        
        if result:
            return {
                "total_trades": result[0],
                "total_buys": result[1],
                "total_sells": result[2],
            }
        
        return {}


class BatchQueryExecutor:
    """Execute batches of queries efficiently."""
    
    def __init__(self, session: Session, batch_size: int = 100):
        """Initialize executor.
        
        Args:
            session: SQLAlchemy session
            batch_size: Batch size for operations
        """
        self.session = session
        self.batch_size = batch_size
        self.pending_queries: List[tuple[str, Dict]] = []
    
    def queue_query(self, query: str, params: Dict[str, Any] = None) -> None:
        """Queue a query for batch execution.
        
        Args:
            query: SQL query string
            params: Query parameters
        """
        self.pending_queries.append((query, params or {}))
    
    def execute_batch(self) -> List[Any]:
        """Execute all queued queries in a transaction.
        
        Returns:
            List of query results
        """
        if not self.pending_queries:
            return []
        
        results = []
        
        try:
            with self.session.begin():
                for query, params in self.pending_queries:
                    try:
                        result = self.session.execute(text(query), params)
                        results.append(result.fetchall())
                    except Exception as e:
                        logger.error(f"Query failed: {e}")
                        results.append(None)
        finally:
            self.pending_queries.clear()
        
        logger.info(f"Executed batch of {len(results)} queries")
        return results
    
    def should_flush(self) -> bool:
        """Check if batch should be flushed.
        
        Returns:
            True if batch size reached
        """
        return len(self.pending_queries) >= self.batch_size


class QueryProfiler:
    """Profile and analyze query performance."""
    
    def __init__(self):
        """Initialize profiler."""
        self.query_times: Dict[str, List[float]] = {}
        self.query_counts: Dict[str, int] = {}
    
    def record_query(self, query_name: str, duration_ms: float) -> None:
        """Record query execution time.
        
        Args:
            query_name: Query identifier
            duration_ms: Execution time in milliseconds
        """
        if query_name not in self.query_times:
            self.query_times[query_name] = []
            self.query_counts[query_name] = 0
        
        self.query_times[query_name].append(duration_ms)
        self.query_counts[query_name] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get query performance statistics.
        
        Returns:
            Performance stats
        """
        stats = {}
        
        for query_name, times in self.query_times.items():
            if not times:
                continue
            
            stats[query_name] = {
                "count": len(times),
                "total_ms": sum(times),
                "avg_ms": sum(times) / len(times),
                "min_ms": min(times),
                "max_ms": max(times),
                "p95_ms": sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0],
            }
        
        return stats
    
    def get_slow_queries(self, threshold_ms: float = 100) -> Dict[str, List[float]]:
        """Get queries slower than threshold.
        
        Args:
            threshold_ms: Slow query threshold
            
        Returns:
            Slow queries and times
        """
        slow = {}
        
        for query_name, times in self.query_times.items():
            slow_times = [t for t in times if t > threshold_ms]
            if slow_times:
                slow[query_name] = slow_times
        
        return slow
