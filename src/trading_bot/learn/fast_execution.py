"""Intelligent order batching and execution - reduces latency and improves fill rates."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types."""
    BUY = "buy"
    SELL = "sell"
    COVER = "cover"
    SHORT = "short"


class OrderPriority(Enum):
    """Order priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Order:
    """Single trading order."""
    symbol: str
    type: OrderType
    quantity: float
    signal_confidence: float
    priority: OrderPriority = OrderPriority.NORMAL
    strategy_source: str = "unknown"
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __hash__(self):
        return hash((self.symbol, self.type.value))
    
    def __lt__(self, other):
        """For sorting by priority."""
        return self.priority.value > other.priority.value  # Higher priority first


@dataclass
class BatchedOrder:
    """Multiple orders batched together for execution."""
    symbol: str
    orders: List[Order]
    total_quantity: float
    avg_confidence: float
    batch_time: datetime = field(default_factory=datetime.now)
    estimated_execution_time_ms: float = 0.0
    
    def combine_quantity(self) -> float:
        """Combine quantities intelligently."""
        buy_qty = sum(o.quantity for o in self.orders if o.type in [OrderType.BUY, OrderType.COVER])
        sell_qty = sum(o.quantity for o in self.orders if o.type in [OrderType.SELL, OrderType.SHORT])
        
        # Net position
        net_qty = buy_qty - sell_qty
        
        return net_qty
    
    def get_net_position(self) -> Tuple[str, float]:
        """Get net position (direction, quantity)."""
        buy_qty = sum(o.quantity for o in self.orders if o.type in [OrderType.BUY, OrderType.COVER])
        sell_qty = sum(o.quantity for o in self.orders if o.type in [OrderType.SELL, OrderType.SHORT])
        
        net = buy_qty - sell_qty
        
        if net > 0:
            return "BUY", net
        elif net < 0:
            return "SELL", abs(net)
        else:
            return "NONE", 0


class SmartOrderBatcher:
    """Batches orders intelligently for faster execution."""
    
    def __init__(
        self,
        batch_window_ms: int = 100,
        max_batch_size: int = 50,
        priority_aware: bool = True
    ):
        self.batch_window_ms = batch_window_ms
        self.max_batch_size = max_batch_size
        self.priority_aware = priority_aware
        
        self.pending_orders: List[Order] = []
        self.order_queue_by_symbol: Dict[str, List[Order]] = defaultdict(list)
        self.batches_ready: List[BatchedOrder] = []
        
        self.lock = threading.Lock()
        self.last_batch_time = time.time()
        self.batch_count = 0
        self.execution_times: List[float] = []
    
    def add_order(self, order: Order) -> None:
        """Add order to pending batch."""
        with self.lock:
            self.pending_orders.append(order)
            self.order_queue_by_symbol[order.symbol].append(order)
    
    def add_orders(self, orders: List[Order]) -> None:
        """Add multiple orders."""
        for order in orders:
            self.add_order(order)
    
    def should_batch(self) -> bool:
        """Check if should create batch."""
        if not self.pending_orders:
            return False
        
        current_time = time.time()
        time_since_last = (current_time - self.last_batch_time) * 1000
        
        # Batch if: window exceeded OR max size reached OR critical priority order
        return (
            time_since_last >= self.batch_window_ms or
            len(self.pending_orders) >= self.max_batch_size or
            any(o.priority == OrderPriority.CRITICAL for o in self.pending_orders)
        )
    
    def create_batch(self) -> List[BatchedOrder]:
        """Create optimized batches from pending orders."""
        if not self.should_batch():
            return []
        
        with self.lock:
            if not self.pending_orders:
                return []
            
            # Sort by priority if enabled
            if self.priority_aware:
                orders = sorted(self.pending_orders, key=lambda o: o.priority.value, reverse=True)
            else:
                orders = self.pending_orders[:]
            
            batches = []
            processed_symbols = set()
            
            for symbol in self.order_queue_by_symbol.keys():
                if symbol in processed_symbols:
                    continue
                
                symbol_orders = self.order_queue_by_symbol[symbol]
                if not symbol_orders:
                    continue
                
                # Create batch for this symbol
                batch = BatchedOrder(
                    symbol=symbol,
                    orders=symbol_orders,
                    total_quantity=sum(o.quantity for o in symbol_orders),
                    avg_confidence=sum(o.signal_confidence for o in symbol_orders) / len(symbol_orders) if symbol_orders else 0
                )
                
                batches.append(batch)
                processed_symbols.add(symbol)
            
            # Clear pending
            self.pending_orders.clear()
            self.order_queue_by_symbol.clear()
            self.last_batch_time = time.time()
            self.batch_count += 1
            
            return batches
    
    def optimize_batch_execution_order(self, batches: List[BatchedOrder]) -> List[BatchedOrder]:
        """Optimize order of batch execution (liquidity, volatility, etc)."""
        
        # Sort by confidence (execute high-confidence orders first)
        return sorted(batches, key=lambda b: b.avg_confidence, reverse=True)
    
    def merge_same_symbol_orders(self, batches: List[BatchedOrder]) -> List[BatchedOrder]:
        """Merge orders for same symbol from different batches."""
        merged: Dict[str, BatchedOrder] = {}
        
        for batch in batches:
            if batch.symbol in merged:
                # Merge with existing
                existing = merged[batch.symbol]
                existing.orders.extend(batch.orders)
                existing.total_quantity += batch.total_quantity
                existing.avg_confidence = (
                    (existing.avg_confidence * len(existing.orders) + 
                     batch.avg_confidence * len(batch.orders)) /
                    (len(existing.orders) + len(batch.orders))
                )
            else:
                merged[batch.symbol] = batch
        
        return list(merged.values())
    
    def get_batch_stats(self) -> Dict:
        """Get batching statistics."""
        avg_execution_time = (
            sum(self.execution_times) / len(self.execution_times)
            if self.execution_times else 0
        )
        
        return {
            "total_batches_created": self.batch_count,
            "pending_orders": len(self.pending_orders),
            "avg_execution_time_ms": avg_execution_time,
            "max_execution_time_ms": max(self.execution_times) if self.execution_times else 0,
            "min_execution_time_ms": min(self.execution_times) if self.execution_times else 0,
        }


class FastExecutionPipeline:
    """Ultra-fast execution pipeline combining batching, caching, and priority handling."""
    
    def __init__(
        self,
        batch_window_ms: int = 50,
        enable_smart_routing: bool = True,
        enable_prediction: bool = True
    ):
        self.batcher = SmartOrderBatcher(batch_window_ms=batch_window_ms)
        self.enable_smart_routing = enable_smart_routing
        self.enable_prediction = enable_prediction
        
        self.execution_history: List[Tuple[datetime, str, str, float]] = []
        self.max_history = 1000
        
        self.symbol_execution_times: Dict[str, List[float]] = defaultdict(list)
        self.liquidity_cache: Dict[str, float] = {}
    
    def add_signal_as_orders(
        self,
        signals: Dict[str, Tuple[int, float]],  # {strategy: (signal, confidence)}
        current_prices: Dict[str, float],
        position_sizes: Dict[str, float] = None,
        default_position_size: float = 100.0
    ) -> None:
        """Convert signals to orders and add to batch."""
        
        if position_sizes is None:
            position_sizes = {}
        
        orders = []
        
        for strategy_name, (signal, confidence) in signals.items():
            if signal == 0:
                continue  # No action
            
            for symbol in current_prices.keys():
                qty = position_sizes.get(symbol, default_position_size)
                
                # Determine order type based on signal
                if signal > 0:
                    order_type = OrderType.BUY
                else:
                    order_type = OrderType.SELL
                
                # Set priority based on confidence
                if confidence >= 0.8:
                    priority = OrderPriority.CRITICAL
                elif confidence >= 0.6:
                    priority = OrderPriority.HIGH
                elif confidence >= 0.4:
                    priority = OrderPriority.NORMAL
                else:
                    priority = OrderPriority.LOW
                
                order = Order(
                    symbol=symbol,
                    type=order_type,
                    quantity=qty,
                    signal_confidence=confidence,
                    priority=priority,
                    strategy_source=strategy_name
                )
                
                orders.append(order)
        
        self.batcher.add_orders(orders)
    
    def execute_batches_smart(self, batches: List[BatchedOrder]) -> Dict[str, Dict]:
        """Execute batches with smart routing and prediction."""
        
        # Optimize execution order
        batches = self.batcher.optimize_batch_execution_order(batches)
        
        # Merge same symbol
        batches = self.batcher.merge_same_symbol_orders(batches)
        
        results = {}
        
        for batch in batches:
            start_time = time.time()
            
            # Get net position
            direction, quantity = batch.get_net_position()
            
            # Predict execution time
            predicted_time = self._predict_execution_time(batch.symbol, quantity)
            batch.estimated_execution_time_ms = predicted_time
            
            # Execute (simulated for now, replace with actual broker API)
            execution_success = True  # In real system: check fill, slippage, etc
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Record
            self.symbol_execution_times[batch.symbol].append(execution_time_ms)
            self.execution_history.append(
                (datetime.now(), batch.symbol, direction, quantity)
            )
            if len(self.execution_history) > self.max_history:
                self.execution_history.pop(0)
            
            results[batch.symbol] = {
                "direction": direction,
                "quantity": quantity,
                "confidence": batch.avg_confidence,
                "execution_time_ms": execution_time_ms,
                "estimated_time_ms": predicted_time,
                "success": execution_success,
                "orders_combined": len(batch.orders)
            }
        
        return results
    
    def _predict_execution_time(self, symbol: str, quantity: float) -> float:
        """Predict execution time based on symbol and quantity."""
        
        if not self.enable_prediction:
            return 100.0  # Default
        
        # Get historical execution times
        exec_times = self.symbol_execution_times.get(symbol, [50.0])
        avg_time = sum(exec_times[-10:]) / min(10, len(exec_times))  # Use last 10
        
        # Adjust for quantity (larger orders take longer)
        quantity_multiplier = min(quantity / 100.0, 2.0)  # Cap at 2x
        
        predicted = avg_time * quantity_multiplier
        
        return predicted
    
    def get_pipeline_stats(self) -> Dict:
        """Get pipeline statistics."""
        return {
            "batcher_stats": self.batcher.get_batch_stats(),
            "avg_symbol_execution_times": {
                symbol: sum(times[-10:]) / min(10, len(times))
                for symbol, times in self.symbol_execution_times.items()
                if times
            },
            "total_executions": len(self.execution_history),
        }
