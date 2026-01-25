"""API request batching and caching for efficient data fetching."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cached response entry."""
    data: Any
    timestamp: datetime
    ttl_minutes: int = 60
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.utcnow() - self.timestamp > timedelta(minutes=self.ttl_minutes)


class RequestCache:
    """Simple in-memory cache with TTL."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 60):
        """Initialize cache.
        
        Args:
            max_size: Maximum cache entries
            default_ttl: Default TTL in minutes
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: Dict[str, CacheEntry] = {}
        self.hits = 0
        self.misses = 0
    
    def _make_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        key_data = json.dumps({"args": args, "kwargs": sorted(kwargs.items())}, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, *args, **kwargs) -> Optional[Any]:
        """Get cached value.
        
        Args:
            *args: Cache key components
            **kwargs: Cache key components
            
        Returns:
            Cached value or None
        """
        key = self._make_key(*args, **kwargs)
        entry = self.cache.get(key)
        
        if entry is None:
            self.misses += 1
            return None
        
        if entry.is_expired:
            del self.cache[key]
            self.misses += 1
            return None
        
        self.hits += 1
        return entry.data
    
    def set(self, data: Any, ttl_minutes: Optional[int] = None, *args, **kwargs) -> None:
        """Set cached value.
        
        Args:
            data: Data to cache
            ttl_minutes: TTL override
            *args: Cache key components
            **kwargs: Cache key components
        """
        key = self._make_key(*args, **kwargs)
        
        # Evict oldest entry if cache full
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache, key=lambda k: self.cache[k].timestamp)
            del self.cache[oldest_key]
        
        self.cache[key] = CacheEntry(
            data=data,
            timestamp=datetime.utcnow(),
            ttl_minutes=ttl_minutes or self.default_ttl,
        )
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Cache stats dict
        """
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        
        return {
            "entries": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "max_size": self.max_size,
        }


class RequestBatcher:
    """Batch API requests for efficiency."""
    
    def __init__(
        self,
        batch_size: int = 50,
        max_batch_wait_ms: int = 100,
        enable_caching: bool = True,
    ):
        """Initialize batcher.
        
        Args:
            batch_size: Max requests per batch
            max_batch_wait_ms: Max wait before flushing partial batch
            enable_caching: Enable response caching
        """
        self.batch_size = batch_size
        self.max_batch_wait_ms = max_batch_wait_ms
        self.enable_caching = enable_caching
        
        self.cache = RequestCache(max_size=1000, default_ttl=60)
        self.pending_requests: List[Dict[str, Any]] = []
        self.last_flush = datetime.utcnow()
    
    def queue_request(
        self,
        request_id: str,
        endpoint: str,
        params: Dict[str, Any],
        cache_ttl: Optional[int] = None,
    ) -> None:
        """Queue a request for batching.
        
        Args:
            request_id: Unique request identifier
            endpoint: API endpoint
            params: Request parameters
            cache_ttl: Cache TTL override
        """
        # Check cache first
        if self.enable_caching:
            cached = self.cache.get(endpoint, **params)
            if cached is not None:
                logger.debug(f"Cache hit for {request_id}")
                return
        
        self.pending_requests.append({
            "id": request_id,
            "endpoint": endpoint,
            "params": params,
            "cache_ttl": cache_ttl,
        })
    
    def should_flush(self) -> bool:
        """Check if batch should be flushed.
        
        Returns:
            True if should flush
        """
        if not self.pending_requests:
            return False
        
        # Flush if batch full
        if len(self.pending_requests) >= self.batch_size:
            return True
        
        # Flush if waiting too long
        wait_time = (datetime.utcnow() - self.last_flush).total_seconds() * 1000
        if wait_time > self.max_batch_wait_ms:
            return True
        
        return False
    
    def get_pending_batch(self) -> List[Dict[str, Any]]:
        """Get current pending batch.
        
        Returns:
            List of pending requests
        """
        return self.pending_requests.copy()
    
    def flush_batch(self, responses: Dict[str, Any]) -> None:
        """Process batch responses.
        
        Args:
            responses: Dict of request_id -> response
        """
        for request in self.pending_requests:
            req_id = request["id"]
            if req_id in responses:
                # Cache response
                if self.enable_caching:
                    self.cache.set(
                        responses[req_id],
                        request["cache_ttl"],
                        request["endpoint"],
                        **request["params"],
                    )
                logger.debug(f"Cached response for {req_id}")
        
        self.pending_requests.clear()
        self.last_flush = datetime.utcnow()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Cache stats
        """
        return self.cache.get_stats()


class SymbolBatcher:
    """Batch requests by symbol group."""
    
    def __init__(self, batch_size: int = 50):
        """Initialize symbol batcher.
        
        Args:
            batch_size: Max symbols per batch
        """
        self.batch_size = batch_size
    
    def batch_symbols(self, symbols: List[str]) -> List[List[str]]:
        """Split symbols into batches.
        
        Args:
            symbols: List of symbols
            
        Returns:
            List of symbol batches
        """
        batches = []
        for i in range(0, len(symbols), self.batch_size):
            batches.append(symbols[i : i + self.batch_size])
        return batches
    
    def batch_by_exchange(self, symbols: List[str]) -> Dict[str, List[List[str]]]:
        """Batch symbols by exchange.
        
        Args:
            symbols: List of symbols
            
        Returns:
            Dict of exchange -> symbol batches
        """
        # Separate by exchange (assume NASDAQ, NYSE, AMEX based on symbol patterns)
        nasdaq = [s for s in symbols if self._is_nasdaq(s)]
        nyse = [s for s in symbols if self._is_nyse(s)]
        
        return {
            "NASDAQ": self.batch_symbols(nasdaq),
            "NYSE": self.batch_symbols(nyse),
        }
    
    @staticmethod
    def _is_nasdaq(symbol: str) -> bool:
        """Check if symbol is typically NASDAQ."""
        # Heuristic: NASDAQ symbols often 4-5 chars
        return len(symbol) >= 4 or symbol in ["AAPL", "MSFT", "GOOG", "AMZN"]
    
    @staticmethod
    def _is_nyse(symbol: str) -> bool:
        """Check if symbol is typically NYSE."""
        return len(symbol) <= 3 or symbol in ["BRK.B", "BAC", "JPM", "WFC"]


class RequestDeduplicator:
    """Deduplicate redundant requests."""
    
    def __init__(self):
        """Initialize deduplicator."""
        self.request_hashes: Set[str] = set()
        self.deduplicated_count = 0
    
    def is_duplicate(self, endpoint: str, params: Dict[str, Any]) -> bool:
        """Check if request is duplicate.
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            True if duplicate
        """
        req_hash = self._hash_request(endpoint, params)
        
        if req_hash in self.request_hashes:
            self.deduplicated_count += 1
            return True
        
        self.request_hashes.add(req_hash)
        return False
    
    def reset(self) -> None:
        """Reset deduplication state."""
        self.request_hashes.clear()
        self.deduplicated_count = 0
    
    @staticmethod
    def _hash_request(endpoint: str, params: Dict[str, Any]) -> str:
        """Hash request for deduplication.
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            Request hash
        """
        key_data = json.dumps({"endpoint": endpoint, "params": sorted(params.items())}, default=str)
        return hashlib.md5(key_data.encode()).hexdigest()


class APIOptimizer:
    """Comprehensive API request optimizer."""
    
    def __init__(self):
        """Initialize optimizer."""
        self.batcher = RequestBatcher(batch_size=50, max_batch_wait_ms=100)
        self.symbol_batcher = SymbolBatcher(batch_size=50)
        self.deduplicator = RequestDeduplicator()
    
    def optimize_symbol_requests(self, symbols: List[str]) -> Dict[str, Any]:
        """Optimize symbol data requests.
        
        Args:
            symbols: List of symbols
            
        Returns:
            Optimization report
        """
        # Remove duplicates
        unique_symbols = list(set(symbols))
        deduplicated = len(symbols) - len(unique_symbols)
        
        # Batch by exchange
        batched = self.symbol_batcher.batch_by_exchange(unique_symbols)
        
        # Count batches
        total_batches = sum(len(b) for b in batched.values())
        
        return {
            "original_symbols": len(symbols),
            "unique_symbols": len(unique_symbols),
            "deduplicated": deduplicated,
            "batches": total_batches,
            "expected_api_calls": total_batches,
            "reduction_factor": len(symbols) / max(1, total_batches),
        }
    
    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get overall optimization statistics.
        
        Returns:
            Optimization stats
        """
        return {
            "cache": self.batcher.get_cache_stats(),
            "deduplicated_requests": self.deduplicator.deduplicated_count,
            "pending_batch_size": len(self.batcher.get_pending_batch()),
        }
