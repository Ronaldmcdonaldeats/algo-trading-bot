"""Unit tests for core trading bot modules."""

import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np


class TestRequestBatcher:
    """Tests for request_batcher module."""
    
    def test_request_cache_set_get(self):
        """Test cache set and get operations."""
        from trading_bot.utils.request_batcher import RequestCache
        
        cache = RequestCache(max_size=10, default_ttl=60)
        
        # Set and get
        cache.set("test_data", "key1")
        assert cache.get("key1") == "test_data"
        
        # Miss
        assert cache.get("nonexistent") is None
        
        # Stats
        stats = cache.get_stats()
        assert stats["entries"] == 1
        assert stats["hit_rate"] > 0
    
    def test_request_cache_expiration(self):
        """Test cache TTL expiration."""
        from trading_bot.utils.request_batcher import RequestCache
        
        cache = RequestCache(max_size=10, default_ttl=1)  # 1 second TTL
        
        cache.set("data", "key1")
        assert cache.get("key1") is not None
        
        # Wait for expiration
        import time
        time.sleep(1.1)
        
        assert cache.get("key1") is None


class TestDatabaseOptimizer:
    """Tests for db_optimizer module."""
    
    def test_query_profiler(self):
        """Test query profiling."""
        from trading_bot.utils.db_optimizer import QueryProfiler
        
        profiler = QueryProfiler()
        
        # Record queries
        profiler.record_query("test_query", 50.0)
        profiler.record_query("test_query", 75.0)
        profiler.record_query("slow_query", 150.0)
        
        # Get stats
        stats = profiler.get_stats()
        
        assert "test_query" in stats
        assert stats["test_query"]["count"] == 2
        assert stats["test_query"]["avg_ms"] == 62.5
    
    def test_slow_query_detection(self):
        """Test slow query detection."""
        from trading_bot.utils.db_optimizer import QueryProfiler
        
        profiler = QueryProfiler()
        
        profiler.record_query("query1", 50.0)
        profiler.record_query("query1", 200.0)
        profiler.record_query("query2", 300.0)
        
        slow = profiler.get_slow_queries(threshold_ms=100)
        
        assert "query1" in slow
        assert "query2" in slow
        assert len(slow["query1"]) == 1


class TestAsyncWeb:
    """Tests for async_web module."""
    
    @pytest.mark.asyncio
    async def test_async_request_creation(self):
        """Test AsyncRequest creation."""
        from trading_bot.utils.async_web import AsyncRequest
        
        req = AsyncRequest(
            method="GET",
            url="https://api.example.com/data",
            params={"symbol": "AAPL"},
        )
        
        assert req.method == "GET"
        assert "api.example.com" in req.url
        assert req.params["symbol"] == "AAPL"
    
    def test_async_response_success(self):
        """Test AsyncResponse success check."""
        from trading_bot.utils.async_web import AsyncResponse
        
        # Success
        resp = AsyncResponse(status=200, data={"result": "ok"})
        assert resp.is_success
        
        # Failure
        resp = AsyncResponse(status=404, data={"error": "not found"})
        assert not resp.is_success


class TestDataFrameCache:
    """Tests for cache_manager module."""
    
    def test_dataframe_cache_set_get(self):
        """Test DataFrame caching."""
        from trading_bot.utils.cache_manager import DataFrameCache
        
        cache = DataFrameCache(max_size=10, default_ttl=3600)
        
        df = pd.DataFrame({
            "close": [100, 101, 102],
            "volume": [1000, 1100, 1200],
        })
        
        cache.set(df, symbol="AAPL", timeframe="1d")
        cached = cache.get(symbol="AAPL", timeframe="1d")
        
        assert cached is not None
        assert cached.shape == (3, 2)
    
    def test_dataframe_cache_expiration(self):
        """Test DataFrame cache expiration."""
        from trading_bot.utils.cache_manager import DataFrameCache, CachedDataFrame
        from datetime import datetime, timedelta
        
        cache = DataFrameCache(max_size=10, default_ttl=1)  # 1 second TTL
        
        df = pd.DataFrame({"a": [1, 2, 3]})
        cache.set(df, symbol="AAPL", timeframe="1d")
        
        # Check that entry exists
        assert len(cache.cache) == 1
        
        # Manually expire entry
        key = list(cache.cache.keys())[0]
        cache.cache[key].timestamp = datetime.utcnow() - timedelta(seconds=2)
        
        # Should be expired
        cached = cache.get(symbol="AAPL", timeframe="1d")
        assert cached is None
    
    def test_indicator_cache(self):
        """Test indicator caching."""
        from trading_bot.utils.cache_manager import IndicatorCache
        
        cache = IndicatorCache(max_size=10)
        
        series = pd.Series([1, 2, 3, 4, 5], name="SMA")
        
        cache.set("AAPL", "SMA_20", series)
        cached = cache.get("AAPL", "SMA_20")
        
        assert cached is not None
        assert len(cached) == 5


class TestSmartDataFrameLoader:
    """Tests for smart loader."""
    
    def test_smart_loader_caching(self):
        """Test smart DataFrame loader."""
        from trading_bot.utils.cache_manager import SmartDataFrameLoader, DataFrameCache
        
        cache = DataFrameCache()
        loader = SmartDataFrameLoader(cache=cache)
        
        def mock_fetch(symbol, timeframe):
            return pd.DataFrame({
                "open": [100, 101, 102],
                "close": [101, 102, 103],
            })
        
        # First load (cache miss)
        df1 = loader.load_ohlc("AAPL", "1d", mock_fetch)
        assert df1 is not None
        assert len(df1) == 3
        
        # Second load (cache hit)
        stats_before = cache.get_stats()
        df2 = loader.load_ohlc("AAPL", "1d", mock_fetch)
        stats_after = cache.get_stats()
        
        assert stats_after["hits"] > stats_before["hits"]


class TestSymbolBatcher:
    """Tests for symbol batching."""
    
    def test_symbol_batching(self):
        """Test symbol batching."""
        from trading_bot.utils.request_batcher import SymbolBatcher
        
        batcher = SymbolBatcher(batch_size=10)
        
        symbols = [f"SYM{i}" for i in range(35)]
        batches = batcher.batch_symbols(symbols)
        
        assert len(batches) == 4  # 35 symbols / 10 per batch = 4 batches
        assert len(batches[0]) == 10
        assert len(batches[-1]) == 5


class TestRequestDeduplicator:
    """Tests for request deduplication."""
    
    def test_deduplication(self):
        """Test request deduplication."""
        from trading_bot.utils.request_batcher import RequestDeduplicator
        
        dedup = RequestDeduplicator()
        
        # First request
        is_dup_1 = dedup.is_duplicate("/api/data", {"symbol": "AAPL"})
        assert not is_dup_1
        
        # Duplicate
        is_dup_2 = dedup.is_duplicate("/api/data", {"symbol": "AAPL"})
        assert is_dup_2
        
        # Different request
        is_dup_3 = dedup.is_duplicate("/api/data", {"symbol": "MSFT"})
        assert not is_dup_3


class TestPerformanceMetrics:
    """Tests for performance monitoring."""
    
    def test_request_batcher_stats(self):
        """Test request batcher statistics."""
        from trading_bot.utils.request_batcher import RequestBatcher
        
        batcher = RequestBatcher(batch_size=50, enable_caching=True)
        
        # Queue some requests
        for i in range(5):
            batcher.queue_request(
                f"req_{i}",
                "/api/data",
                {"symbol": f"SYM{i}"},
            )
        
        stats = batcher.get_cache_stats()
        assert "entries" in stats
        assert "hit_rate" in stats
    
    def test_dataframe_cache_stats(self):
        """Test DataFrame cache statistics."""
        from trading_bot.utils.cache_manager import DataFrameCache
        
        cache = DataFrameCache(max_size=10)
        
        df = pd.DataFrame({"a": [1, 2, 3]})
        cache.set(df, symbol="AAPL", timeframe="1d")
        cache.get(symbol="AAPL", timeframe="1d")
        
        stats = cache.get_stats()
        
        assert stats["entries"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 0


class TestIntegration:
    """Integration tests."""
    
    def test_api_optimizer_flow(self):
        """Test complete API optimization flow."""
        from trading_bot.utils.request_batcher import APIOptimizer
        
        optimizer = APIOptimizer()
        
        symbols = ["AAPL", "MSFT", "GOOG", "AMZN"] * 20  # 80 symbols with duplicates
        
        result = optimizer.optimize_symbol_requests(symbols)
        
        assert result["original_symbols"] == 80
        assert result["unique_symbols"] == 4
        assert result["reduction_factor"] == 20.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
