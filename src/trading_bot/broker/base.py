from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from trading_bot.core.models import Fill, Order, Portfolio


@dataclass(frozen=True)
class OrderRejection:
    order: Order
    reason: str


class Broker(Protocol):
    def set_price(self, symbol: str, price: float) -> None:  # mark-to-market
        ...

    def submit_order(self, order: Order) -> Fill | OrderRejection:
        ...

    def portfolio(self) -> Portfolio:
        ...
