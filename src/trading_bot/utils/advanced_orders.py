"""Advanced order management with OCO, scale-in/out, and order tracking."""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional, Dict, List


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "PENDING"      # Submitted, awaiting fill
    PARTIAL = "PARTIAL"      # Partially filled
    FILLED = "FILLED"        # Fully filled
    CANCELLED = "CANCELLED"  # Cancelled by user
    REJECTED = "REJECTED"    # Rejected by broker
    EXPIRED = "EXPIRED"      # Expired due to time


@dataclass
class OrderLeg:
    """Single leg of a compound order (e.g., one leg of OCO)."""
    symbol: str
    side: str  # "BUY" or "SELL"
    qty: int
    type: str  # "MARKET" or "LIMIT"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Order:
    """Base order class with tracking."""
    order_id: str
    symbol: str
    side: str
    qty: int
    order_type: str
    limit_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def is_filled(self) -> bool:
        return self.status == OrderStatus.FILLED
    
    @property
    def is_partial(self) -> bool:
        return self.status == OrderStatus.PARTIAL
    
    @property
    def unfilled_qty(self) -> int:
        return self.qty - self.filled_qty
    
    @property
    def fill_rate(self) -> float:
        """Percentage of order filled."""
        if self.qty <= 0:
            return 0
        return self.filled_qty / self.qty


@dataclass
class OCOOrder:
    """One-Cancels-Other order: two linked orders where one fill cancels the other."""
    order_id: str
    primary_leg: OrderLeg      # Primary order (e.g., LIMIT entry)
    cancel_leg: OrderLeg       # Cancel leg (e.g., STOP loss or LIMIT exit)
    status: OrderStatus = OrderStatus.PENDING
    active_leg: Optional[str] = None  # "primary" or "cancel"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    reason: str = ""
    
    def check_fill_status(self, primary_filled: bool, cancel_filled: bool) -> Optional[str]:
        """Check if OCO should be triggered.
        
        Args:
            primary_filled: Whether primary leg filled
            cancel_filled: Whether cancel leg filled
            
        Returns:
            "primary" if primary filled first, "cancel" if cancel filled first, None otherwise
        """
        if primary_filled:
            self.active_leg = "primary"
            self.status = OrderStatus.FILLED
            return "primary"
        
        if cancel_filled:
            self.active_leg = "cancel"
            self.status = OrderStatus.FILLED
            return "cancel"
        
        return None


class ScaleManager:
    """Manage scale-in (pyramid) and scale-out (pyramid profit) orders."""
    
    def __init__(self, symbol: str, initial_qty: int, entry_price: float):
        """Initialize scale manager.
        
        Args:
            symbol: Trading symbol
            initial_qty: Initial position size
            entry_price: Entry price
        """
        self.symbol = symbol
        self.total_qty = initial_qty
        self.avg_price = entry_price
        self.filled_qty = initial_qty
        self.scale_ins: List[Dict] = []  # Scale-in orders
        self.scale_outs: List[Dict] = []  # Scale-out orders
    
    def add_scale_in(self, qty: int, trigger_price: float, order_price: float, level: int = 1) -> Dict:
        """Add scale-in (pyramid) order.
        
        Args:
            qty: Quantity to add
            trigger_price: Price at which to trigger scale-in
            order_price: Price at which to place order
            level: Scale-in level (1, 2, 3, etc)
            
        Returns:
            Scale-in order dict
        """
        scale_in = {
            "level": level,
            "qty": qty,
            "trigger_price": trigger_price,
            "order_price": order_price,
            "status": "PENDING",
            "timestamp": datetime.utcnow(),
        }
        self.scale_ins.append(scale_in)
        return scale_in
    
    def add_scale_out(self, qty: int, trigger_price: float, order_price: float, level: int = 1) -> Dict:
        """Add scale-out (pyramid profit) order.
        
        Args:
            qty: Quantity to exit
            trigger_price: Price at which to trigger scale-out
            order_price: Price at which to place order
            level: Scale-out level (1, 2, 3, etc)
            
        Returns:
            Scale-out order dict
        """
        scale_out = {
            "level": level,
            "qty": qty,
            "trigger_price": trigger_price,
            "order_price": order_price,
            "status": "PENDING",
            "timestamp": datetime.utcnow(),
        }
        self.scale_outs.append(scale_out)
        return scale_out
    
    def get_pending_scale_orders(self, current_price: float) -> Dict:
        """Get scale orders that should be triggered at current price.
        
        Args:
            current_price: Current market price
            
        Returns:
            Dict with pending scale-in and scale-out orders
        """
        pending_in = [s for s in self.scale_ins if s["status"] == "PENDING" 
                      and current_price >= s["trigger_price"]]
        pending_out = [s for s in self.scale_outs if s["status"] == "PENDING"
                       and current_price >= s["trigger_price"]]
        
        return {
            "scale_ins": pending_in,
            "scale_outs": pending_out,
        }
    
    def mark_scale_executed(self, scale_type: str, level: int) -> None:
        """Mark a scale order as executed.
        
        Args:
            scale_type: "in" or "out"
            level: Scale level
        """
        target_list = self.scale_ins if scale_type == "in" else self.scale_outs
        for order in target_list:
            if order["level"] == level:
                order["status"] = "FILLED"
                if scale_type == "in":
                    self.total_qty += order["qty"]
                    self.avg_price = (self.avg_price * self.filled_qty + order["order_price"] * order["qty"]) / (self.filled_qty + order["qty"])
                    self.filled_qty += order["qty"]
                else:
                    self.total_qty -= order["qty"]
                break
    
    def get_scale_summary(self) -> Dict:
        """Get summary of scale orders.
        
        Returns:
            Dict with scale-in and scale-out status
        """
        scale_in_filled = sum(1 for s in self.scale_ins if s["status"] == "FILLED")
        scale_out_filled = sum(1 for s in self.scale_outs if s["status"] == "FILLED")
        
        return {
            "total_qty": self.total_qty,
            "avg_price": round(self.avg_price, 2),
            "scale_ins_completed": scale_in_filled,
            "scale_ins_pending": len(self.scale_ins) - scale_in_filled,
            "scale_outs_completed": scale_out_filled,
            "scale_outs_pending": len(self.scale_outs) - scale_out_filled,
        }


class AdvancedOrderManager:
    """Manage advanced order types and order tracking."""
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.oco_orders: Dict[str, OCOOrder] = {}
        self.scale_managers: Dict[str, ScaleManager] = {}
    
    def create_oco_order(self, primary_leg: OrderLeg, cancel_leg: OrderLeg) -> str:
        """Create One-Cancels-Other order.
        
        Args:
            primary_leg: Primary order leg (e.g., entry order)
            cancel_leg: Cancel leg (e.g., stop-loss or exit)
            
        Returns:
            OCO order ID
        """
        import uuid
        oco_id = f"OCO_{uuid.uuid4().hex[:8]}"
        
        oco = OCOOrder(
            order_id=oco_id,
            primary_leg=primary_leg,
            cancel_leg=cancel_leg,
        )
        
        self.oco_orders[oco_id] = oco
        print(f"[ORDER] Created OCO {oco_id}: Primary={primary_leg.side} {primary_leg.qty} {primary_leg.symbol}")
        print(f"        Cancel leg: {cancel_leg.type} @ {cancel_leg.limit_price or cancel_leg.stop_price}")
        
        return oco_id
    
    def create_scale_position(self, symbol: str, initial_qty: int, entry_price: float) -> ScaleManager:
        """Create scale-in/out manager for a position.
        
        Args:
            symbol: Trading symbol
            initial_qty: Initial position size
            entry_price: Entry price
            
        Returns:
            ScaleManager instance
        """
        scale_mgr = ScaleManager(symbol, initial_qty, entry_price)
        self.scale_managers[symbol] = scale_mgr
        return scale_mgr
    
    def track_order(self, order: Order) -> None:
        """Track an order.
        
        Args:
            order: Order to track
        """
        self.orders[order.order_id] = order
    
    def update_order_fill(self, order_id: str, filled_qty: int, fill_price: float) -> Order:
        """Update order with partial or full fill.
        
        Args:
            order_id: Order ID
            filled_qty: Quantity filled
            fill_price: Price at which filled
            
        Returns:
            Updated order
        """
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        
        order = self.orders[order_id]
        
        # Update fill information
        if order.filled_qty == 0:
            order.avg_fill_price = fill_price
        else:
            # Recalculate average fill price
            total_cost = order.avg_fill_price * order.filled_qty + fill_price * (filled_qty - order.filled_qty)
            order.avg_fill_price = total_cost / filled_qty
        
        order.filled_qty = filled_qty
        
        # Update status
        if filled_qty >= order.qty:
            order.status = OrderStatus.FILLED
        elif filled_qty > 0:
            order.status = OrderStatus.PARTIAL
        
        return order
    
    def cancel_order(self, order_id: str, reason: str = "") -> Order:
        """Cancel an order.
        
        Args:
            order_id: Order ID
            reason: Cancellation reason
            
        Returns:
            Cancelled order
        """
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        
        order = self.orders[order_id]
        order.status = OrderStatus.CANCELLED
        print(f"[ORDER] Cancelled {order_id}: {reason}")
        return order
    
    def get_order_summary(self) -> Dict:
        """Get summary of all tracked orders.
        
        Returns:
            Summary of pending, filled, and cancelled orders
        """
        pending = [o for o in self.orders.values() if o.status == OrderStatus.PENDING]
        filled = [o for o in self.orders.values() if o.status == OrderStatus.FILLED]
        cancelled = [o for o in self.orders.values() if o.status == OrderStatus.CANCELLED]
        
        return {
            "pending_count": len(pending),
            "filled_count": len(filled),
            "cancelled_count": len(cancelled),
            "pending_qty": sum(o.unfilled_qty for o in pending),
            "filled_qty": sum(o.filled_qty for o in filled),
            "oco_count": len(self.oco_orders),
            "scale_managers": len(self.scale_managers),
        }
    
    def print_order_status(self) -> None:
        """Print formatted order status."""
        summary = self.get_order_summary()
        
        print(f"\n[ORDER STATUS]")
        print(f"  Pending: {summary['pending_count']} ({summary['pending_qty']} qty)")
        print(f"  Filled: {summary['filled_count']} ({summary['filled_qty']} qty)")
        print(f"  Cancelled: {summary['cancelled_count']}")
        print(f"  OCO Orders: {summary['oco_count']}")
        print(f"  Scale Managers: {summary['scale_managers']}")
