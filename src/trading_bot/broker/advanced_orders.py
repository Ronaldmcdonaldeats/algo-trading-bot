"""Advanced Order Types - Bracket orders, OCO, trailing stops

Implements advanced order management:
- Bracket orders (entry + profit/stop)
- OCO (One-Cancels-Other) orders
- Trailing stops with dynamic adjustments
- Conditional orders
- Time-based exits
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """Base order"""
    order_id: str
    symbol: str
    side: str  # BUY, SELL
    quantity: int
    price: float
    order_type: str  # MARKET, LIMIT, STOP, TRAILING_STOP
    status: str  # PENDING, FILLED, CANCELLED, REJECTED
    timestamp: datetime
    filled_price: Optional[float] = None
    filled_qty: int = 0


@dataclass
class BracketOrder:
    """Bracket order: entry + profit target + stop loss"""
    entry_order: Order
    take_profit_order: Order
    stop_loss_order: Order
    parent_order_id: str
    created_at: datetime
    status: str  # ACTIVE, PARTIAL_FILLED, FILLED, CANCELLED


@dataclass
class OCOOrder:
    """One-Cancels-Other order pair"""
    primary_order: Order
    secondary_order: Order
    parent_order_id: str
    created_at: datetime
    status: str  # WAITING, PRIMARY_FILLED, SECONDARY_FILLED, CANCELLED


@dataclass
class TrailingStopOrder:
    """Trailing stop order that adjusts with price movement"""
    symbol: str
    quantity: int
    entry_price: float
    trail_percent: float  # e.g., 0.05 for 5% trailing
    trail_amount: Optional[float] = None  # Dollar amount instead of percent
    high_water_mark: float = 0.0
    stop_price: float = 0.0
    status: str = "ACTIVE"
    created_at: datetime = None


class AdvancedOrderManager:
    """Manage advanced order types"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.bracket_orders: Dict[str, BracketOrder] = {}
        self.oco_orders: Dict[str, OCOOrder] = {}
        self.trailing_stops: Dict[str, TrailingStopOrder] = {}
        self.order_counter = 0
        
    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        self.order_counter += 1
        return f"ORD_{self.order_counter}_{int(datetime.now().timestamp())}"
    
    def create_bracket_order(self, symbol: str, entry_qty: int, entry_price: float,
                           take_profit_price: float, stop_loss_price: float) -> BracketOrder:
        """Create bracket order (entry + profit target + stop)
        
        Args:
            symbol: Stock symbol
            entry_qty: Quantity to buy/sell
            entry_price: Entry price
            take_profit_price: Profit target price
            stop_loss_price: Stop loss price
        """
        
        entry_id = self._generate_order_id()
        tp_id = self._generate_order_id()
        sl_id = self._generate_order_id()
        parent_id = self._generate_order_id()
        
        entry = Order(
            order_id=entry_id,
            symbol=symbol,
            side="BUY",
            quantity=entry_qty,
            price=entry_price,
            order_type="LIMIT",
            status="PENDING",
            timestamp=datetime.now()
        )
        
        tp = Order(
            order_id=tp_id,
            symbol=symbol,
            side="SELL",
            quantity=entry_qty,
            price=take_profit_price,
            order_type="LIMIT",
            status="PENDING",
            timestamp=datetime.now()
        )
        
        sl = Order(
            order_id=sl_id,
            symbol=symbol,
            side="SELL",
            quantity=entry_qty,
            price=stop_loss_price,
            order_type="STOP",
            status="PENDING",
            timestamp=datetime.now()
        )
        
        bracket = BracketOrder(
            entry_order=entry,
            take_profit_order=tp,
            stop_loss_order=sl,
            parent_order_id=parent_id,
            created_at=datetime.now(),
            status="ACTIVE"
        )
        
        self.bracket_orders[parent_id] = bracket
        logger.info(f"Bracket order created: {symbol} - Entry: ${entry_price}, "
                   f"TP: ${take_profit_price}, SL: ${stop_loss_price}")
        
        return bracket
    
    def create_oco_order(self, symbol: str, quantity: int, 
                        primary_price: float, secondary_price: float,
                        primary_side: str = "SELL") -> OCOOrder:
        """Create OCO (One-Cancels-Other) order
        
        Example: Buy at $100 OR buy at $95 (whichever fills first)
        """
        
        primary_id = self._generate_order_id()
        secondary_id = self._generate_order_id()
        parent_id = self._generate_order_id()
        
        primary = Order(
            order_id=primary_id,
            symbol=symbol,
            side=primary_side,
            quantity=quantity,
            price=primary_price,
            order_type="LIMIT",
            status="WAITING",
            timestamp=datetime.now()
        )
        
        secondary_side = "BUY" if primary_side == "SELL" else "SELL"
        secondary = Order(
            order_id=secondary_id,
            symbol=symbol,
            side=secondary_side,
            quantity=quantity,
            price=secondary_price,
            order_type="LIMIT",
            status="WAITING",
            timestamp=datetime.now()
        )
        
        oco = OCOOrder(
            primary_order=primary,
            secondary_order=secondary,
            parent_order_id=parent_id,
            created_at=datetime.now(),
            status="WAITING"
        )
        
        self.oco_orders[parent_id] = oco
        logger.info(f"OCO order created: {symbol} - "
                   f"Primary: {primary_side} {quantity} @ ${primary_price}, "
                   f"Secondary: {secondary_side} {quantity} @ ${secondary_price}")
        
        return oco
    
    def create_trailing_stop(self, symbol: str, quantity: int, entry_price: float,
                            trail_percent: Optional[float] = None,
                            trail_amount: Optional[float] = None) -> TrailingStopOrder:
        """Create trailing stop order
        
        Args:
            symbol: Stock symbol
            quantity: Number of shares
            entry_price: Entry price
            trail_percent: Trailing percentage (e.g., 0.05 = 5%)
            trail_amount: Trailing amount in dollars (alternative to percent)
        """
        
        if not trail_percent and not trail_amount:
            trail_percent = 0.02  # Default 2%
        
        trailing_stop = TrailingStopOrder(
            symbol=symbol,
            quantity=quantity,
            entry_price=entry_price,
            trail_percent=trail_percent,
            trail_amount=trail_amount,
            high_water_mark=entry_price,
            stop_price=self._calculate_stop_price(entry_price, trail_percent, trail_amount),
            status="ACTIVE",
            created_at=datetime.now()
        )
        
        order_id = self._generate_order_id()
        self.trailing_stops[order_id] = trailing_stop
        
        logger.info(f"Trailing stop created: {symbol} {quantity} shares "
                   f"(Entry: ${entry_price}, Trail: {trail_percent*100 if trail_percent else 0}%)")
        
        return trailing_stop
    
    def _calculate_stop_price(self, current_price: float, 
                             trail_percent: Optional[float],
                             trail_amount: Optional[float]) -> float:
        """Calculate stop price given current price and trail parameters"""
        
        if trail_amount:
            return current_price - trail_amount
        elif trail_percent:
            return current_price * (1 - trail_percent)
        else:
            return current_price * 0.98  # Default 2% trail
    
    def update_trailing_stops(self, prices: Dict[str, float]):
        """Update all trailing stops with new prices"""
        
        for order_id, trailing in self.trailing_stops.items():
            if trailing.status != "ACTIVE":
                continue
            
            current_price = prices.get(trailing.symbol)
            if not current_price:
                continue
            
            # Update high water mark
            if current_price > trailing.high_water_mark:
                trailing.high_water_mark = current_price
                # Adjust stop price
                new_stop = self._calculate_stop_price(
                    current_price,
                    trailing.trail_percent,
                    trailing.trail_amount
                )
                trailing.stop_price = new_stop
                logger.debug(f"Trailing stop updated: {trailing.symbol} - "
                           f"Stop now: ${trailing.stop_price:.2f}")
            
            # Check if stop is hit
            if current_price <= trailing.stop_price:
                trailing.status = "STOP_HIT"
                logger.warning(f"Trailing stop triggered: {trailing.symbol} - "
                             f"Stop: ${trailing.stop_price:.2f}, Price: ${current_price:.2f}")
    
    def cancel_bracket_order(self, parent_order_id: str) -> bool:
        """Cancel entire bracket order"""
        
        if parent_order_id not in self.bracket_orders:
            return False
        
        bracket = self.bracket_orders[parent_order_id]
        bracket.status = "CANCELLED"
        logger.info(f"Bracket order cancelled: {parent_order_id}")
        
        return True
    
    def cancel_oco_order(self, parent_order_id: str) -> bool:
        """Cancel OCO order"""
        
        if parent_order_id not in self.oco_orders:
            return False
        
        oco = self.oco_orders[parent_order_id]
        oco.status = "CANCELLED"
        logger.info(f"OCO order cancelled: {parent_order_id}")
        
        return True
    
    def get_active_orders(self) -> Dict:
        """Get all active orders"""
        
        return {
            'bracket_orders': [b for b in self.bracket_orders.values() if b.status == "ACTIVE"],
            'oco_orders': [o for o in self.oco_orders.values() if o.status == "WAITING"],
            'trailing_stops': [t for t in self.trailing_stops.values() if t.status == "ACTIVE"]
        }
    
    def save_orders(self, filename: str = "advanced_orders.json"):
        """Save order history to JSON"""
        
        filepath = self.cache_dir / filename
        
        data = {
            'bracket_orders': [
                {
                    'parent_id': b.parent_order_id,
                    'symbol': b.entry_order.symbol,
                    'entry_price': b.entry_order.price,
                    'tp_price': b.take_profit_order.price,
                    'sl_price': b.stop_loss_order.price,
                    'status': b.status,
                    'created_at': b.created_at.isoformat()
                }
                for b in self.bracket_orders.values()
            ],
            'oco_orders': [
                {
                    'parent_id': o.parent_order_id,
                    'symbol': o.primary_order.symbol,
                    'primary_price': o.primary_order.price,
                    'secondary_price': o.secondary_order.price,
                    'status': o.status,
                    'created_at': o.created_at.isoformat()
                }
                for o in self.oco_orders.values()
            ],
            'trailing_stops': [
                {
                    'symbol': t.symbol,
                    'quantity': t.quantity,
                    'entry_price': t.entry_price,
                    'trail_percent': t.trail_percent,
                    'current_stop': t.stop_price,
                    'status': t.status,
                    'created_at': t.created_at.isoformat()
                }
                for t in self.trailing_stops.values()
            ],
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Advanced orders saved to {filepath}")
        return str(filepath)
