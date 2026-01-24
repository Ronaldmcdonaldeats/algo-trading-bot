"""Performance optimizations for data processing and indicators.

This module provides optimized versions of common operations:
- Batch indicator calculation with numpy vectorization
- Async data processing for multiple symbols
- Lazy evaluation patterns
- Memory-efficient streaming for large datasets
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Track performance of optimized operations."""
    operation: str
    duration_ms: float
    items_processed: int
    throughput: float  # items per second


class VectorizedIndicators:
    """Vectorized indicator calculations using NumPy for better performance."""
    
    @staticmethod
    def sma(prices: np.ndarray, period: int) -> np.ndarray:
        """Vectorized Simple Moving Average."""
        if len(prices) < period:
            return np.full_like(prices, np.nan)
        
        weights = np.ones(period) / period
        return np.convolve(prices, weights, mode='valid').reshape(-1, 1) if period == len(prices) else \
               np.concatenate([np.full(period - 1, np.nan), np.convolve(prices, weights, mode='valid')])
    
    @staticmethod
    def ema(prices: np.ndarray, period: int) -> np.ndarray:
        """Vectorized Exponential Moving Average."""
        if len(prices) < period:
            return np.full_like(prices, np.nan)
        
        alpha = 2.0 / (period + 1)
        ema_values = np.zeros_like(prices, dtype=float)
        ema_values[period - 1] = np.mean(prices[:period])
        
        for i in range(period, len(prices)):
            ema_values[i] = alpha * prices[i] + (1 - alpha) * ema_values[i - 1]
        
        ema_values[:period - 1] = np.nan
        return ema_values
    
    @staticmethod
    def rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
        """Vectorized Relative Strength Index."""
        if len(prices) < period + 1:
            return np.full_like(prices, np.nan)
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.convolve(gains, np.ones(period) / period, mode='valid')
        avg_loss = np.convolve(losses, np.ones(period) / period, mode='valid')
        
        rs = np.divide(avg_gain, avg_loss, where=(avg_loss != 0), out=np.zeros_like(avg_gain))
        rsi = 100 - (100 / (1 + rs))
        
        result = np.full_like(prices, np.nan)
        result[period:] = rsi
        return result
    
    @staticmethod
    def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
        """Vectorized Average True Range."""
        if len(high) < period:
            return np.full_like(high, np.nan)
        
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        tr[0] = tr1[0]
        
        atr_values = np.convolve(tr, np.ones(period) / period, mode='valid')
        result = np.full_like(high, np.nan)
        result[period - 1:] = atr_values
        return result


class BatchDataProcessor:
    """Process multiple symbols efficiently in batches."""
    
    def __init__(self, batch_size: int = 10, max_workers: int = 4):
        self.batch_size = batch_size
        self.max_workers = max_workers
    
    async def process_async(
        self,
        data: List[pd.DataFrame],
        operation: Callable[[pd.DataFrame], pd.DataFrame],
    ) -> List[pd.DataFrame]:
        """Process multiple dataframes concurrently.
        
        Args:
            data: List of DataFrames (one per symbol)
            operation: Function to apply to each DataFrame
        
        Returns:
            List of processed DataFrames
        """
        tasks = [
            asyncio.to_thread(operation, df)
            for df in data
        ]
        
        results = []
        for i in range(0, len(tasks), self.max_workers):
            batch_tasks = tasks[i:i + self.max_workers]
            batch_results = await asyncio.gather(*batch_tasks)
            results.extend(batch_results)
        
        return results
    
    def process_batches(
        self,
        data: List[pd.DataFrame],
        operation: Callable[[pd.DataFrame], pd.DataFrame],
    ) -> List[pd.DataFrame]:
        """Process multiple dataframes in batches (synchronous).
        
        Useful for I/O bound operations.
        """
        results = []
        for i in range(0, len(data), self.batch_size):
            batch = data[i:i + self.batch_size]
            for df in batch:
                results.append(operation(df))
            logger.info(f"Processed batch {i // self.batch_size + 1}/{(len(data) + self.batch_size - 1) // self.batch_size}")
        
        return results


class StreamingDataProcessor:
    """Memory-efficient streaming processor for large datasets."""
    
    def __init__(self, chunk_size: int = 10000):
        self.chunk_size = chunk_size
    
    def process_chunks(
        self,
        data_source: Callable[[], pd.DataFrame],
        operation: Callable[[pd.DataFrame], None],
    ) -> None:
        """Process data in chunks to minimize memory usage.
        
        Args:
            data_source: Function that yields chunks of data
            operation: Function to apply to each chunk
        """
        chunk_count = 0
        while True:
            chunk = data_source()
            if chunk is None or chunk.empty:
                break
            
            operation(chunk)
            chunk_count += 1
            logger.debug(f"Processed chunk {chunk_count}")


class IndicatorBatcher:
    """Batch calculate indicators for multiple symbols efficiently."""
    
    def __init__(self):
        self.vectorized = VectorizedIndicators()
    
    def calculate_indicators_batch(
        self,
        symbol_data: dict[str, pd.DataFrame],
        indicators: List[str] = None,
    ) -> dict[str, pd.DataFrame]:
        """Calculate indicators for multiple symbols in parallel.
        
        Args:
            symbol_data: Dict of symbol -> DataFrame
            indicators: List of indicators to calculate (default: all)
        
        Returns:
            Dict of symbol -> DataFrame with indicators added
        """
        if indicators is None:
            indicators = ["sma", "ema", "rsi", "atr"]
        
        results = {}
        for symbol, df in symbol_data.items():
            logger.debug(f"Calculating indicators for {symbol}")
            
            df_copy = df.copy()
            close = df["Close"].values
            high = df.get("High", close).values
            low = df.get("Low", close).values
            
            if "sma" in indicators:
                df_copy["sma_20"] = self.vectorized.sma(close, 20)
                df_copy["sma_50"] = self.vectorized.sma(close, 50)
            
            if "ema" in indicators:
                df_copy["ema_12"] = self.vectorized.ema(close, 12)
                df_copy["ema_26"] = self.vectorized.ema(close, 26)
            
            if "rsi" in indicators:
                df_copy["rsi"] = self.vectorized.rsi(close, 14)
            
            if "atr" in indicators and "High" in df.columns and "Low" in df.columns:
                df_copy["atr"] = self.vectorized.atr(high, low, close, 14)
            
            results[symbol] = df_copy
        
        return results
