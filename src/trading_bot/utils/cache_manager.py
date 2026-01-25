"""DataFrame caching and memory management."""

from __future__ import annotations

from typing import Dict, Optional, Any, Callable
import pandas as pd
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, field
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class CachedDataFrame:
    """Cached DataFrame entry."""
    df: pd.DataFrame
    timestamp: datetime
    ttl_seconds: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.utcnow() - self.timestamp > timedelta(seconds=self.ttl_seconds)
    
    @property
    def age_seconds(self) -> float:
        """Get age of cached data in seconds."""
        return (datetime.utcnow() - self.timestamp).total_seconds()
    
    def touch(self) -> None:
        """Mark access for LRU eviction."""
        self.access_count += 1


class DataFrameCache:
    """LRU cache for DataFrames with TTL."""
    
    def __init__(self, max_size: int = 100, default_ttl: int = 3600):
        """Initialize cache.
        
        Args:
            max_size: Maximum cached DataFrames
            default_ttl: Default TTL in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CachedDataFrame] = {}
        self.hits = 0
        self.misses = 0
    
    def _make_key(self, **kwargs) -> str:
        """Generate cache key from parameters."""
        import json
        key_data = json.dumps(kwargs, default=str, sort_keys=True)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, **kwargs) -> Optional[pd.DataFrame]:
        """Get cached DataFrame.
        
        Args:
            **kwargs: Cache key components
            
        Returns:
            Cached DataFrame or None
        """
        key = self._make_key(**kwargs)
        entry = self.cache.get(key)
        
        if entry is None:
            self.misses += 1
            return None
        
        if entry.is_expired:
            del self.cache[key]
            self.misses += 1
            logger.debug(f"Cache miss (expired): {key[:8]}")
            return None
        
        entry.touch()
        self.hits += 1
        logger.debug(f"Cache hit: {key[:8]} (age: {entry.age_seconds:.1f}s)")
        return entry.df.copy()
    
    def set(
        self,
        df: pd.DataFrame,
        ttl_seconds: Optional[int] = None,
        **kwargs,
    ) -> None:
        """Set cached DataFrame.
        
        Args:
            df: DataFrame to cache
            ttl_seconds: TTL override
            **kwargs: Cache key components
        """
        key = self._make_key(**kwargs)
        
        # Evict LRU if cache full
        if len(self.cache) >= self.max_size:
            lru_key = min(self.cache, key=lambda k: self.cache[k].access_count)
            del self.cache[lru_key]
            logger.debug(f"Evicted LRU: {lru_key[:8]}")
        
        self.cache[key] = CachedDataFrame(
            df=df.copy(),
            timestamp=datetime.utcnow(),
            ttl_seconds=ttl_seconds or self.default_ttl,
            metadata={
                "shape": df.shape,
                "memory_mb": df.memory_usage(deep=True).sum() / 1024 / 1024,
            },
        )
        
        logger.debug(f"Cached DataFrame: {key[:8]} (shape: {df.shape})")
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def invalidate_symbol(self, symbol: str) -> int:
        """Invalidate cache entries for symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Number of entries invalidated
        """
        count = 0
        keys_to_delete = []
        
        for key, entry in self.cache.items():
            if entry.metadata.get("symbol") == symbol:
                keys_to_delete.append(key)
                count += 1
        
        for key in keys_to_delete:
            del self.cache[key]
        
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Cache stats
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        total_memory = sum(
            e.metadata.get("memory_mb", 0) for e in self.cache.values()
        )
        
        return {
            "entries": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "total_memory_mb": total_memory,
            "max_size": self.max_size,
        }


class SmartDataFrameLoader:
    """Intelligently load and cache OHLC data."""
    
    def __init__(self, cache: Optional[DataFrameCache] = None):
        """Initialize loader.
        
        Args:
            cache: DataFrameCache instance
        """
        self.cache = cache or DataFrameCache(max_size=100, default_ttl=3600)
    
    def load_ohlc(
        self,
        symbol: str,
        timeframe: str,
        fetch_func: Callable[[str, str], pd.DataFrame],
    ) -> pd.DataFrame:
        """Load OHLC data with caching.
        
        Args:
            symbol: Stock symbol
            timeframe: Timeframe (1h, 1d, etc.)
            fetch_func: Function to fetch data if not cached
            
        Returns:
            DataFrame with OHLC data
        """
        # Try cache first
        cached = self.cache.get(symbol=symbol, timeframe=timeframe)
        if cached is not None:
            return cached
        
        # Fetch and cache
        logger.info(f"Fetching {symbol} {timeframe}")
        df = fetch_func(symbol, timeframe)
        
        self.cache.set(df, symbol=symbol, timeframe=timeframe)
        
        return df
    
    def load_batch(
        self,
        symbols: list[str],
        timeframe: str,
        fetch_func: Callable[[list[str]], Dict[str, pd.DataFrame]],
    ) -> Dict[str, pd.DataFrame]:
        """Load OHLC data for multiple symbols.
        
        Args:
            symbols: List of symbols
            timeframe: Timeframe
            fetch_func: Batch fetch function
            
        Returns:
            Dict of symbol -> DataFrame
        """
        result = {}
        to_fetch = []
        
        # Check cache for each symbol
        for symbol in symbols:
            cached = self.cache.get(symbol=symbol, timeframe=timeframe)
            if cached is not None:
                result[symbol] = cached
            else:
                to_fetch.append(symbol)
        
        # Batch fetch missing
        if to_fetch:
            logger.info(f"Fetching {len(to_fetch)} symbols (cache hit: {len(result)})")
            fetched = fetch_func(to_fetch)
            
            for symbol, df in fetched.items():
                self.cache.set(df, symbol=symbol, timeframe=timeframe)
                result[symbol] = df
        
        return result


class IndicatorCache:
    """Cache computed indicators."""
    
    def __init__(self, max_size: int = 50):
        """Initialize indicator cache.
        
        Args:
            max_size: Max cached indicators
        """
        self.max_size = max_size
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, symbol: str, indicator: str) -> Optional[pd.Series]:
        """Get cached indicator.
        
        Args:
            symbol: Stock symbol
            indicator: Indicator name
            
        Returns:
            Cached Series or None
        """
        key = f"{symbol}:{indicator}"
        cached = self.cache.get(key)
        
        if cached and not cached["expired"]:
            return cached["data"]
        
        return None
    
    def set(self, symbol: str, indicator: str, data: pd.Series, ttl_seconds: int = 300) -> None:
        """Set cached indicator.
        
        Args:
            symbol: Stock symbol
            indicator: Indicator name
            data: Series data
            ttl_seconds: TTL
        """
        key = f"{symbol}:{indicator}"
        
        if len(self.cache) >= self.max_size:
            # Evict oldest
            oldest_key = min(self.cache, key=lambda k: self.cache[k]["timestamp"])
            del self.cache[oldest_key]
        
        self.cache[key] = {
            "data": data,
            "timestamp": datetime.utcnow(),
            "ttl": ttl_seconds,
            "expired": False,
        }
    
    def is_expired(self, key: str) -> bool:
        """Check if indicator expired.
        
        Args:
            key: Cache key
            
        Returns:
            True if expired
        """
        entry = self.cache.get(key)
        if not entry:
            return True
        
        age = (datetime.utcnow() - entry["timestamp"]).total_seconds()
        return age > entry["ttl"]


class DataFramePool:
    """Object pool for DataFrames (high-frequency optimization)."""
    
    def __init__(self, pool_size: int = 10):
        """Initialize pool.
        
        Args:
            pool_size: Number of DataFrames to pool
        """
        self.pool_size = pool_size
        self.available: list[pd.DataFrame] = []
        self.in_use: set = set()
    
    def acquire(self, shape: tuple[int, int] = None) -> pd.DataFrame:
        """Acquire DataFrame from pool.
        
        Args:
            shape: Expected shape
            
        Returns:
            DataFrame (new or reused)
        """
        if self.available:
            df = self.available.pop()
            df.iloc[:] = 0  # Clear data
            self.in_use.add(id(df))
            return df
        
        # Create new
        if shape:
            df = pd.DataFrame(index=range(shape[0]), columns=range(shape[1]))
        else:
            df = pd.DataFrame()
        
        self.in_use.add(id(df))
        return df
    
    def release(self, df: pd.DataFrame) -> None:
        """Release DataFrame back to pool.
        
        Args:
            df: DataFrame to release
        """
        df_id = id(df)
        
        if df_id not in self.in_use:
            return
        
        self.in_use.remove(df_id)
        
        if len(self.available) < self.pool_size:
            self.available.append(df)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics.
        
        Returns:
            Pool stats
        """
        return {
            "pool_size": self.pool_size,
            "available": len(self.available),
            "in_use": len(self.in_use),
            "utilization": len(self.in_use) / self.pool_size * 100,
        }
