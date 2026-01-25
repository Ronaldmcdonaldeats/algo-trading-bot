"""Real-time market data streaming with WebSocket support."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Dict, List, Any
import asyncio
import logging
import json

logger = logging.getLogger(__name__)


class DataInterval(Enum):
    """Supported data intervals."""
    TICK = "tick"  # Tick-by-tick
    ONE_MIN = "1min"
    FIVE_MIN = "5min"
    FIFTEEN_MIN = "15min"
    THIRTY_MIN = "30min"
    ONE_HOUR = "1h"
    DAILY = "1d"


@dataclass
class TickData:
    """Single tick of market data."""
    symbol: str
    timestamp: datetime
    price: float
    size: int
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    exchange: str = "SMART"
    
    @property
    def spread(self) -> float:
        """Bid-ask spread."""
        return self.ask - self.bid
    
    @property
    def spread_pct(self) -> float:
        """Bid-ask spread as percentage."""
        if self.bid == 0:
            return 0.0
        return (self.spread / self.bid) * 100
    
    @property
    def midpoint(self) -> float:
        """Midpoint between bid and ask."""
        return (self.bid + self.ask) / 2


@dataclass
class BarData:
    """OHLCV bar data."""
    symbol: str
    timestamp: datetime
    interval: DataInterval
    open: float
    high: float
    low: float
    close: float
    volume: int
    trades: int = 0  # Number of trades in bar
    vwap: float = 0.0  # Volume-weighted average price
    
    @property
    def hl_range(self) -> float:
        """High-low range."""
        return self.high - self.low
    
    @property
    def hl_range_pct(self) -> float:
        """High-low range as percentage."""
        if self.open == 0:
            return 0.0
        return (self.hl_range / self.open) * 100
    
    @property
    def body(self) -> float:
        """Candle body size."""
        return abs(self.close - self.open)
    
    @property
    def body_pct(self) -> float:
        """Candle body as percentage."""
        if self.open == 0:
            return 0.0
        return (self.body / self.open) * 100


@dataclass
class StreamSession:
    """Real-time data stream session."""
    symbol: str
    interval: DataInterval
    stream_id: str = field(default_factory=lambda: f"stream_{datetime.utcnow().timestamp()}")
    started_at: datetime = field(default_factory=datetime.utcnow)
    last_tick: Optional[TickData] = None
    last_bar: Optional[BarData] = None
    tick_count: int = 0
    bar_count: int = 0
    status: str = "active"  # active, paused, closed
    
    @property
    def uptime_seconds(self) -> float:
        """Stream uptime in seconds."""
        return (datetime.utcnow() - self.started_at).total_seconds()


class StreamBuffer:
    """Buffers ticks and bars for efficient processing."""
    
    def __init__(self, buffer_size: int = 100):
        """Initialize buffer.
        
        Args:
            buffer_size: Max buffer size before flush
        """
        self.buffer_size = buffer_size
        self.tick_buffer: List[TickData] = []
        self.bar_buffer: List[BarData] = []
    
    def add_tick(self, tick: TickData) -> List[TickData]:
        """Add tick to buffer.
        
        Args:
            tick: Tick data
            
        Returns:
            Ticks to flush (if buffer full)
        """
        self.tick_buffer.append(tick)
        
        if len(self.tick_buffer) >= self.buffer_size:
            return self.flush_ticks()
        
        return []
    
    def add_bar(self, bar: BarData) -> List[BarData]:
        """Add bar to buffer.
        
        Args:
            bar: Bar data
            
        Returns:
            Bars to flush (if buffer full)
        """
        self.bar_buffer.append(bar)
        
        if len(self.bar_buffer) >= self.buffer_size:
            return self.flush_bars()
        
        return []
    
    def flush_ticks(self) -> List[TickData]:
        """Flush tick buffer.
        
        Returns:
            All buffered ticks
        """
        result = self.tick_buffer.copy()
        self.tick_buffer.clear()
        return result
    
    def flush_bars(self) -> List[BarData]:
        """Flush bar buffer.
        
        Returns:
            All buffered bars
        """
        result = self.bar_buffer.copy()
        self.bar_buffer.clear()
        return result


class RealtimeDataStreamer:
    """Real-time market data streaming engine."""
    
    def __init__(self):
        """Initialize streaming engine."""
        self.sessions: Dict[str, StreamSession] = {}
        self.buffers: Dict[str, StreamBuffer] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
        self.is_running = False
    
    def start_stream(
        self, symbol: str, interval: DataInterval = DataInterval.TICK
    ) -> StreamSession:
        """Start streaming data for symbol.
        
        Args:
            symbol: Stock symbol
            interval: Data interval
            
        Returns:
            Stream session
        """
        session = StreamSession(symbol=symbol, interval=interval)
        self.sessions[session.stream_id] = session
        self.buffers[session.stream_id] = StreamBuffer()
        
        logger.info(f"Started stream for {symbol} at {interval.value}")
        
        return session
    
    def stop_stream(self, stream_id: str) -> None:
        """Stop streaming data.
        
        Args:
            stream_id: Stream session ID
        """
        if stream_id in self.sessions:
            session = self.sessions[stream_id]
            session.status = "closed"
            logger.info(f"Stopped stream {stream_id} after {session.uptime_seconds:.1f}s")
    
    def register_callback(self, stream_id: str, callback: Callable) -> None:
        """Register callback for stream updates.
        
        Args:
            stream_id: Stream session ID
            callback: Function to call on data arrival
        """
        if stream_id not in self.callbacks:
            self.callbacks[stream_id] = []
        self.callbacks[stream_id].append(callback)
    
    def add_tick(self, stream_id: str, tick: TickData) -> None:
        """Add tick data to stream.
        
        Args:
            stream_id: Stream session ID
            tick: Tick data
        """
        if stream_id not in self.sessions:
            return
        
        session = self.sessions[stream_id]
        session.last_tick = tick
        session.tick_count += 1
        
        # Buffer the tick
        buffer = self.buffers[stream_id]
        flush_ticks = buffer.add_tick(tick)
        
        # Execute callbacks
        if stream_id in self.callbacks:
            for callback in self.callbacks[stream_id]:
                try:
                    callback(tick=tick, bars=None)
                except Exception as e:
                    logger.error(f"Error in tick callback: {e}")
    
    def add_bar(self, stream_id: str, bar: BarData) -> None:
        """Add bar data to stream.
        
        Args:
            stream_id: Stream session ID
            bar: Bar data
        """
        if stream_id not in self.sessions:
            return
        
        session = self.sessions[stream_id]
        session.last_bar = bar
        session.bar_count += 1
        
        # Buffer the bar
        buffer = self.buffers[stream_id]
        flush_bars = buffer.add_bar(bar)
        
        # Execute callbacks
        if stream_id in self.callbacks:
            for callback in self.callbacks[stream_id]:
                try:
                    callback(tick=None, bars=[bar])
                except Exception as e:
                    logger.error(f"Error in bar callback: {e}")
    
    def get_session(self, stream_id: str) -> Optional[StreamSession]:
        """Get stream session.
        
        Args:
            stream_id: Stream session ID
            
        Returns:
            Session or None
        """
        return self.sessions.get(stream_id)
    
    def get_all_sessions(self) -> List[StreamSession]:
        """Get all active sessions.
        
        Returns:
            List of sessions
        """
        return list(self.sessions.values())
    
    def get_active_streams(self) -> Dict[str, StreamSession]:
        """Get active streams.
        
        Returns:
            Dict of stream_id -> session
        """
        return {
            stream_id: session 
            for stream_id, session in self.sessions.items()
            if session.status == "active"
        }
    
    def get_stream_stats(self, stream_id: str) -> Dict[str, Any]:
        """Get stream statistics.
        
        Args:
            stream_id: Stream session ID
            
        Returns:
            Statistics dict
        """
        session = self.sessions.get(stream_id)
        if not session:
            return {}
        
        return {
            "symbol": session.symbol,
            "interval": session.interval.value,
            "uptime_seconds": session.uptime_seconds,
            "tick_count": session.tick_count,
            "bar_count": session.bar_count,
            "ticks_per_second": session.tick_count / max(1, session.uptime_seconds),
            "last_tick": session.last_tick.timestamp if session.last_tick else None,
            "last_price": session.last_tick.price if session.last_tick else None,
        }


class WebSocketStreamManager:
    """Manages WebSocket connections for real-time data."""
    
    def __init__(self):
        """Initialize WebSocket manager."""
        self.connections: Dict[str, Any] = {}
        self.streamer = RealtimeDataStreamer()
        self.is_connected = False
    
    async def connect(self, stream_url: str) -> bool:
        """Connect to data stream.
        
        Args:
            stream_url: WebSocket URL
            
        Returns:
            True if connected
        """
        try:
            logger.info(f"Connecting to {stream_url}")
            # In production, would use websockets library
            self.is_connected = True
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    async def subscribe_quotes(self, symbols: List[str]) -> None:
        """Subscribe to quote updates.
        
        Args:
            symbols: List of symbols
        """
        logger.info(f"Subscribing to quotes: {symbols}")
        for symbol in symbols:
            session = self.streamer.start_stream(symbol, DataInterval.TICK)
    
    async def subscribe_bars(self, symbols: List[str], interval: DataInterval) -> None:
        """Subscribe to bar updates.
        
        Args:
            symbols: List of symbols
            interval: Bar interval
        """
        logger.info(f"Subscribing to {interval.value} bars: {symbols}")
        for symbol in symbols:
            session = self.streamer.start_stream(symbol, interval)
    
    async def listen(self) -> None:
        """Listen to incoming data.
        
        Should be run in event loop.
        """
        logger.info("Listening for stream data")
        # In production, would listen to WebSocket
        while self.is_connected:
            await asyncio.sleep(1)
    
    async def disconnect(self) -> None:
        """Disconnect from stream."""
        self.is_connected = False
        logger.info("Disconnected from stream")
    
    def get_streamer(self) -> RealtimeDataStreamer:
        """Get underlying streamer.
        
        Returns:
            RealtimeDataStreamer instance
        """
        return self.streamer


class StreamProcessor:
    """Processes stream data for trading decisions."""
    
    def __init__(self):
        """Initialize processor."""
        self.tick_processors: List[Callable] = []
        self.bar_processors: List[Callable] = []
    
    def register_tick_processor(self, processor: Callable) -> None:
        """Register tick processor.
        
        Args:
            processor: Function to process ticks
        """
        self.tick_processors.append(processor)
    
    def register_bar_processor(self, processor: Callable) -> None:
        """Register bar processor.
        
        Args:
            processor: Function to process bars
        """
        self.bar_processors.append(processor)
    
    async def process_tick(self, tick: TickData) -> Dict[str, Any]:
        """Process incoming tick.
        
        Args:
            tick: Tick data
            
        Returns:
            Processing results
        """
        results = {}
        
        for processor in self.tick_processors:
            try:
                result = processor(tick)
                if result:
                    results.update(result)
            except Exception as e:
                logger.error(f"Error in tick processor: {e}")
        
        return results
    
    async def process_bar(self, bar: BarData) -> Dict[str, Any]:
        """Process incoming bar.
        
        Args:
            bar: Bar data
            
        Returns:
            Processing results
        """
        results = {}
        
        for processor in self.bar_processors:
            try:
                result = processor(bar)
                if result:
                    results.update(result)
            except Exception as e:
                logger.error(f"Error in bar processor: {e}")
        
        return results
