"""Async web server and request handling."""

from __future__ import annotations

from typing import Dict, Any, Optional, Callable, Awaitable
import asyncio
import aiohttp
import logging
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AsyncRequest:
    """Async HTTP request."""
    method: str
    url: str
    params: Optional[Dict[str, Any]] = None
    json_data: Optional[Dict[str, Any]] = None
    timeout: int = 30
    
    @property
    def request_id(self) -> str:
        """Get unique request ID."""
        return f"{self.method}:{self.url}"


@dataclass
class AsyncResponse:
    """Async HTTP response."""
    status: int
    data: Any
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0.0
    
    @property
    def is_success(self) -> bool:
        """Check if response successful."""
        return 200 <= self.status < 300


class AsyncHTTPClient:
    """Async HTTP client for concurrent requests."""
    
    def __init__(self, max_concurrent: int = 10, timeout: int = 30):
        """Initialize client.
        
        Args:
            max_concurrent: Max concurrent connections
            timeout: Request timeout in seconds
        """
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_count = 0
        self.error_count = 0
    
    async def __aenter__(self):
        """Context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.session:
            await self.session.close()
    
    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncResponse:
        """Make async GET request.
        
        Args:
            url: Request URL
            params: Query parameters
            headers: Request headers
            
        Returns:
            AsyncResponse
        """
        return await self._request("GET", url, params=params, headers=headers)
    
    async def post(
        self,
        url: str,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncResponse:
        """Make async POST request.
        
        Args:
            url: Request URL
            json_data: JSON body
            headers: Request headers
            
        Returns:
            AsyncResponse
        """
        return await self._request("POST", url, json_data=json_data, headers=headers)
    
    async def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> AsyncResponse:
        """Internal request handler.
        
        Args:
            method: HTTP method
            url: Request URL
            params: Query parameters
            json_data: JSON body
            headers: Request headers
            
        Returns:
            AsyncResponse
        """
        async with self.semaphore:
            start = datetime.utcnow()
            self.request_count += 1
            
            try:
                async with self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as resp:
                    duration = (datetime.utcnow() - start).total_seconds() * 1000
                    
                    try:
                        data = await resp.json()
                    except:
                        data = await resp.text()
                    
                    return AsyncResponse(
                        status=resp.status,
                        data=data,
                        headers=dict(resp.headers),
                        duration_ms=duration,
                    )
            except Exception as e:
                self.error_count += 1
                logger.error(f"Request failed: {e}")
                return AsyncResponse(
                    status=500,
                    data={"error": str(e)},
                    duration_ms=(datetime.utcnow() - start).total_seconds() * 1000,
                )
    
    async def batch_requests(
        self,
        requests: list[AsyncRequest],
    ) -> Dict[str, AsyncResponse]:
        """Execute multiple requests concurrently.
        
        Args:
            requests: List of AsyncRequest objects
            
        Returns:
            Dict of request_id -> response
        """
        tasks = [
            self._execute_request(req)
            for req in requests
        ]
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        result = {}
        for req, response in zip(requests, responses):
            if isinstance(response, Exception):
                result[req.request_id] = AsyncResponse(
                    status=500,
                    data={"error": str(response)},
                )
            else:
                result[req.request_id] = response
        
        return result
    
    async def _execute_request(self, request: AsyncRequest) -> AsyncResponse:
        """Execute single request.
        
        Args:
            request: AsyncRequest object
            
        Returns:
            AsyncResponse
        """
        if request.method == "GET":
            return await self.get(request.url, params=request.params)
        elif request.method == "POST":
            return await self.post(request.url, json_data=request.json_data)
        else:
            raise ValueError(f"Unsupported method: {request.method}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics.
        
        Returns:
            Client stats
        """
        return {
            "total_requests": self.request_count,
            "errors": self.error_count,
            "success_rate": (1 - self.error_count / max(1, self.request_count)) * 100,
            "max_concurrent": self.max_concurrent,
        }


class AsyncDataFetcher:
    """Fetch data asynchronously from multiple sources."""
    
    def __init__(self, max_concurrent: int = 10):
        """Initialize fetcher.
        
        Args:
            max_concurrent: Max concurrent requests
        """
        self.client = AsyncHTTPClient(max_concurrent=max_concurrent)
        self.cache: Dict[str, Any] = {}
    
    async def fetch_multiple_symbols(
        self,
        symbols: list[str],
        endpoint: str,
        params_template: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch data for multiple symbols concurrently.
        
        Args:
            symbols: List of symbols
            endpoint: API endpoint
            params_template: URL parameters template
            
        Returns:
            Dict of symbol -> data
        """
        requests = []
        for symbol in symbols:
            params = params_template.copy()
            params["symbol"] = symbol
            requests.append(
                AsyncRequest(
                    method="GET",
                    url=endpoint,
                    params=params,
                )
            )
        
        async with self.client:
            responses = await self.client.batch_requests(requests)
        
        result = {}
        for symbol, response in zip(symbols, responses.values()):
            if response.is_success:
                result[symbol] = response.data
                self.cache[symbol] = response.data
            else:
                logger.error(f"Failed to fetch {symbol}: {response.status}")
        
        return result
    
    async def fetch_with_retry(
        self,
        url: str,
        max_retries: int = 3,
        backoff_ms: int = 100,
    ) -> Optional[Any]:
        """Fetch with exponential backoff retry.
        
        Args:
            url: Request URL
            max_retries: Max retry attempts
            backoff_ms: Initial backoff in milliseconds
            
        Returns:
            Response data or None
        """
        async with self.client:
            for attempt in range(max_retries):
                response = await self.client.get(url)
                
                if response.is_success:
                    return response.data
                
                if attempt < max_retries - 1:
                    wait_time = (backoff_ms * (2 ** attempt)) / 1000
                    await asyncio.sleep(wait_time)
        
        return None


class AsyncRouteHandler:
    """Handle async Flask routes."""
    
    @staticmethod
    async def async_wrapper(
        async_func: Callable[..., Awaitable[Any]],
        *args,
        **kwargs,
    ) -> Any:
        """Wrap async function for Flask.
        
        Args:
            async_func: Async function to wrap
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(async_func(*args, **kwargs))
        finally:
            loop.close()
    
    @staticmethod
    def create_async_route(async_func: Callable[..., Awaitable[Any]]) -> Callable:
        """Create async route decorator.
        
        Args:
            async_func: Async function to wrap
            
        Returns:
            Wrapped function for Flask
        """
        def wrapper(*args, **kwargs):
            return AsyncRouteHandler.async_wrapper(async_func, *args, **kwargs)
        
        wrapper.__name__ = async_func.__name__
        return wrapper


class ConcurrentDataLoader:
    """Load data from multiple sources concurrently."""
    
    def __init__(self, max_concurrent: int = 10):
        """Initialize loader.
        
        Args:
            max_concurrent: Max concurrent operations
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def load_multiple(
        self,
        loaders: Dict[str, Callable[[], Awaitable[Any]]],
    ) -> Dict[str, Any]:
        """Load data from multiple sources concurrently.
        
        Args:
            loaders: Dict of name -> async loader function
            
        Returns:
            Dict of name -> loaded data
        """
        async def load_with_semaphore(name: str, loader: Callable) -> tuple[str, Any]:
            async with self.semaphore:
                try:
                    data = await loader()
                    return name, data
                except Exception as e:
                    logger.error(f"Failed to load {name}: {e}")
                    return name, None
        
        tasks = [
            load_with_semaphore(name, loader)
            for name, loader in loaders.items()
        ]
        
        results = await asyncio.gather(*tasks)
        
        return {name: data for name, data in results}
