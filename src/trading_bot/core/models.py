from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Mapping

Side = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]


@dataclass(frozen=True)
class Order:
    id: str
    ts: datetime
    symbol: str
    side: Side
    qty: int
    type: OrderType = "MARKET"
    limit_price: float | None = None
    tag: str = ""


@dataclass(frozen=True)
class Fill:
    order_id: str
    ts: datetime
    symbol: str
    side: Side
    qty: int
    price: float
    fee: float = 0.0
    slippage: float = 0.0
    note: str = ""


@dataclass
class Position:
    symbol: str
    qty: int = 0
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None

    def market_value(self, price: float) -> float:
        return float(self.qty) * float(price)

    def unrealized_pnl(self, price: float) -> float:
        return (float(price) - float(self.avg_price)) * float(self.qty)


@dataclass
class Portfolio:
    cash: float
    positions: dict[str, Position] = field(default_factory=dict)
    fees_paid: float = 0.0

    def get_position(self, symbol: str) -> Position:
        pos = self.positions.get(symbol)
        if pos is None:
            pos = Position(symbol=symbol)
            self.positions[symbol] = pos
        return pos

    def market_value(self, prices: Mapping[str, float]) -> float:
        mv = 0.0
        for sym, pos in self.positions.items():
            if pos.qty == 0:
                continue
            px = prices.get(sym)
            if px is None:
                continue
            mv += pos.market_value(float(px))
        return float(mv)

    def equity(self, prices: Mapping[str, float]) -> float:
        return float(self.cash) + self.market_value(prices)

    def unrealized_pnl(self, prices: Mapping[str, float]) -> float:
        out = 0.0
        for sym, pos in self.positions.items():
            if pos.qty == 0:
                continue
            px = prices.get(sym)
            if px is None:
                continue
            out += pos.unrealized_pnl(float(px))
        return float(out)

    def realized_pnl(self) -> float:
        return float(sum(p.realized_pnl for p in self.positions.values()))
