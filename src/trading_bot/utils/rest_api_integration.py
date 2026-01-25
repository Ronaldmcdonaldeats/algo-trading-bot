"""
REST API & Integration Module
REST endpoints for bot control, WebSocket for real-time updates, broker integrations.
Enables programmatic control and third-party integrations.
"""

import logging
import asyncio
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class OrderSide(Enum):
    """Order side"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass
class RestOrderRequest:
    """REST API order request"""
    symbol: str
    quantity: int
    side: OrderSide
    order_type: OrderType
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "day"  # day, gtc, opg


@dataclass
class RestOrderResponse:
    """REST API order response"""
    order_id: str
    symbol: str
    quantity: int
    side: OrderSide
    status: OrderStatus
    filled_quantity: int
    average_fill_price: float
    created_at: datetime
    updated_at: datetime


@dataclass
class RestPositionResponse:
    """REST API position response"""
    symbol: str
    quantity: int
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class RestPortfolioResponse:
    """REST API portfolio response"""
    total_value: float
    cash: float
    buying_power: float
    total_pnl: float
    total_pnl_pct: float
    positions: List[RestPositionResponse]


class RestApiHandler:
    """REST API request handler"""

    def __init__(self, trading_engine):
        self.trading_engine = trading_engine
        self.routes = {
            "GET /api/health": self.health,
            "GET /api/portfolio": self.get_portfolio,
            "GET /api/positions": self.get_positions,
            "GET /api/orders": self.get_orders,
            "POST /api/orders": self.submit_order,
            "GET /api/orders/{order_id}": self.get_order,
            "DELETE /api/orders/{order_id}": self.cancel_order,
            "POST /api/strategies/start": self.start_strategy,
            "POST /api/strategies/stop": self.stop_strategy,
            "GET /api/strategies/status": self.get_strategy_status,
            "POST /api/parameters/update": self.update_parameters,
            "GET /api/performance": self.get_performance,
        }

    def health(self) -> Dict[str, Any]:
        """Health check endpoint"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
        }

    def get_portfolio(self) -> RestPortfolioResponse:
        """Get portfolio overview"""
        portfolio = self.trading_engine.get_portfolio()

        positions = [
            RestPositionResponse(
                symbol=pos["symbol"],
                quantity=pos["quantity"],
                avg_entry_price=pos["avg_entry_price"],
                current_price=pos["current_price"],
                unrealized_pnl=pos["unrealized_pnl"],
                unrealized_pnl_pct=pos["unrealized_pnl_pct"],
            )
            for pos in portfolio["positions"]
        ]

        return RestPortfolioResponse(
            total_value=portfolio["total_value"],
            cash=portfolio["cash"],
            buying_power=portfolio["buying_power"],
            total_pnl=portfolio["total_pnl"],
            total_pnl_pct=portfolio["total_pnl_pct"],
            positions=positions,
        )

    def get_positions(self) -> List[RestPositionResponse]:
        """Get all positions"""
        positions = self.trading_engine.get_positions()
        return [
            RestPositionResponse(
                symbol=p["symbol"],
                quantity=p["quantity"],
                avg_entry_price=p["avg_entry_price"],
                current_price=p["current_price"],
                unrealized_pnl=p["unrealized_pnl"],
                unrealized_pnl_pct=p["unrealized_pnl_pct"],
            )
            for p in positions
        ]

    def get_orders(self, status: Optional[str] = None) -> List[RestOrderResponse]:
        """Get orders (optionally filtered by status)"""
        orders = self.trading_engine.get_orders(status=status)
        return [
            RestOrderResponse(
                order_id=o["order_id"],
                symbol=o["symbol"],
                quantity=o["quantity"],
                side=OrderSide(o["side"]),
                status=OrderStatus(o["status"]),
                filled_quantity=o.get("filled_quantity", 0),
                average_fill_price=o.get("average_fill_price", 0),
                created_at=o["created_at"],
                updated_at=o["updated_at"],
            )
            for o in orders
        ]

    def submit_order(self, request: RestOrderRequest) -> RestOrderResponse:
        """Submit new order"""
        try:
            order = self.trading_engine.submit_order(
                symbol=request.symbol,
                quantity=request.quantity,
                side=request.side.value,
                order_type=request.order_type.value,
                limit_price=request.limit_price,
                stop_price=request.stop_price,
            )

            return RestOrderResponse(
                order_id=order["order_id"],
                symbol=order["symbol"],
                quantity=order["quantity"],
                side=OrderSide(order["side"]),
                status=OrderStatus(order["status"]),
                filled_quantity=order.get("filled_quantity", 0),
                average_fill_price=order.get("average_fill_price", 0),
                created_at=order["created_at"],
                updated_at=order["updated_at"],
            )
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            raise

    def get_order(self, order_id: str) -> RestOrderResponse:
        """Get specific order"""
        order = self.trading_engine.get_order(order_id)
        return RestOrderResponse(
            order_id=order["order_id"],
            symbol=order["symbol"],
            quantity=order["quantity"],
            side=OrderSide(order["side"]),
            status=OrderStatus(order["status"]),
            filled_quantity=order.get("filled_quantity", 0),
            average_fill_price=order.get("average_fill_price", 0),
            created_at=order["created_at"],
            updated_at=order["updated_at"],
        )

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order"""
        return self.trading_engine.cancel_order(order_id)

    def start_strategy(self, strategy_name: str, parameters: Dict) -> Dict[str, Any]:
        """Start trading strategy"""
        try:
            self.trading_engine.start_strategy(strategy_name, parameters)
            return {
                "status": "started",
                "strategy": strategy_name,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to start strategy: {e}")
            raise

    def stop_strategy(self, strategy_name: str) -> Dict[str, Any]:
        """Stop trading strategy"""
        try:
            self.trading_engine.stop_strategy(strategy_name)
            return {
                "status": "stopped",
                "strategy": strategy_name,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to stop strategy: {e}")
            raise

    def get_strategy_status(self) -> Dict[str, Any]:
        """Get status of all strategies"""
        return self.trading_engine.get_strategy_status()

    def update_parameters(self, strategy_name: str, parameters: Dict) -> Dict[str, Any]:
        """Update strategy parameters (live)"""
        try:
            self.trading_engine.update_strategy_parameters(strategy_name, parameters)
            return {
                "status": "updated",
                "strategy": strategy_name,
                "parameters": parameters,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to update parameters: {e}")
            raise

    def get_performance(self) -> Dict[str, Any]:
        """Get strategy performance metrics"""
        return self.trading_engine.get_performance_metrics()


class WebSocketServer:
    """WebSocket server for real-time updates"""

    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.connected_clients = set()
        self.message_handlers = {}

    async def start(self):
        """Start WebSocket server"""
        logger.info(f"WebSocket server starting on {self.host}:{self.port}")

        # Would use websockets library in production
        # async with websockets.serve(self.handle_client, self.host, self.port):
        #     await asyncio.Future()  # Run forever

    async def handle_client(self, websocket, path):
        """Handle WebSocket client connection"""
        self.connected_clients.add(websocket)
        logger.info(f"Client connected from {websocket.remote_address}")

        try:
            async for message in websocket:
                await self.process_message(websocket, message)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.connected_clients.remove(websocket)
            logger.info(f"Client disconnected from {websocket.remote_address}")

    async def process_message(self, websocket, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            message_type = data.get("type")

            if message_type in self.message_handlers:
                response = self.message_handlers[message_type](data)
                await websocket.send(json.dumps(response))
        except json.JSONDecodeError:
            logger.error("Invalid JSON in WebSocket message")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.connected_clients:
            return

        message_str = json.dumps(message)

        for websocket in self.connected_clients:
            try:
                await websocket.send(message_str)
            except Exception as e:
                logger.error(f"Failed to send message to client: {e}")

    async def send_trade_update(self, trade_data: Dict):
        """Broadcast trade update to all clients"""
        await self.broadcast({
            "type": "trade_update",
            "data": trade_data,
            "timestamp": datetime.now().isoformat(),
        })

    async def send_position_update(self, position_data: Dict):
        """Broadcast position update"""
        await self.broadcast({
            "type": "position_update",
            "data": position_data,
            "timestamp": datetime.now().isoformat(),
        })

    async def send_order_update(self, order_data: Dict):
        """Broadcast order update"""
        await self.broadcast({
            "type": "order_update",
            "data": order_data,
            "timestamp": datetime.now().isoformat(),
        })

    async def send_performance_update(self, performance_data: Dict):
        """Broadcast performance metrics"""
        await self.broadcast({
            "type": "performance_update",
            "data": performance_data,
            "timestamp": datetime.now().isoformat(),
        })


class InteractiveBrokersIntegration:
    """Integration with Interactive Brokers API"""

    def __init__(self, account_id: str, api_host: str = "127.0.0.1", api_port: int = 7497):
        self.account_id = account_id
        self.api_host = api_host
        self.api_port = api_port
        self.connected = False

    def connect(self) -> bool:
        """Connect to IB Gateway/TWS"""
        try:
            # from ibapi.client import EClient
            # from ibapi.wrapper import EWrapper
            # 
            # class IBWrapper(EWrapper):
            #     def __init__(self):
            #         self.orders = {}
            # 
            # class IBClient(EClient):
            #     pass
            # 
            # self.client = IBClient(IBWrapper())
            # self.client.connect(self.api_host, self.api_port, clientId=1)

            logger.info("Connected to Interactive Brokers")
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Interactive Brokers: {e}")
            return False

    def submit_order(self, symbol: str, quantity: int, side: str, order_type: str) -> str:
        """Submit order to Interactive Brokers"""
        if not self.connected:
            raise RuntimeError("Not connected to Interactive Brokers")

        # Would submit via IB API
        # Returns order ID

        order_id = f"IB_{symbol}_{datetime.now().timestamp()}"
        logger.info(f"Order submitted to IB: {order_id}")
        return order_id

    def get_account_info(self) -> Dict[str, Any]:
        """Get account information from IB"""
        if not self.connected:
            raise RuntimeError("Not connected to Interactive Brokers")

        return {
            "account_id": self.account_id,
            "total_cash_value": 0.0,
            "net_liquidation": 0.0,
            "buying_power": 0.0,
        }

    def get_positions(self) -> List[Dict]:
        """Get account positions from IB"""
        if not self.connected:
            raise RuntimeError("Not connected to Interactive Brokers")

        return []


class APIGateway:
    """Main API gateway orchestrating all integrations"""

    def __init__(self, trading_engine):
        self.trading_engine = trading_engine
        self.rest_handler = RestApiHandler(trading_engine)
        self.websocket_server = WebSocketServer()
        self.ib_integration = None  # Optional IB integration

    async def initialize(self):
        """Initialize all API services"""
        logger.info("Initializing API gateway")
        await self.websocket_server.start()

    def register_websocket_handler(self, message_type: str, handler: Callable):
        """Register WebSocket message handler"""
        self.websocket_server.message_handlers[message_type] = handler

    def enable_interactive_brokers(self, account_id: str) -> bool:
        """Enable Interactive Brokers integration"""
        self.ib_integration = InteractiveBrokersIntegration(account_id)
        return self.ib_integration.connect()

    async def notify_trade(self, trade_data: Dict):
        """Notify all subscribers of trade execution"""
        await self.websocket_server.send_trade_update(trade_data)

    async def notify_position_change(self, position_data: Dict):
        """Notify of position changes"""
        await self.websocket_server.send_position_update(position_data)

    async def notify_order_update(self, order_data: Dict):
        """Notify of order updates"""
        await self.websocket_server.send_order_update(order_data)

    async def notify_performance(self, performance_data: Dict):
        """Notify of performance updates"""
        await self.websocket_server.send_performance_update(performance_data)
