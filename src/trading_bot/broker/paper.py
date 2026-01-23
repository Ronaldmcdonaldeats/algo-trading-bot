from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from trading_bot.broker.base import OrderRejection
from trading_bot.core.models import Fill, Order, Portfolio


@dataclass(frozen=True)
class PaperBrokerConfig:
    commission_bps: float = 0.0  # bps of notional
    slippage_bps: float = 0.0  # applied to market orders
    min_fee: float = 0.0


class PaperBroker:
    """Paper broker with immediate fills using a mark price.

    Supported:
    - MARKET orders (with optional slippage)
    - LIMIT orders (filled immediately if marketable)

    Not supported (Phase 1):
    - stops, stop-limits, time-in-force, partial fills, borrow/shorting
    """

    def __init__(
        self,
        *,
        start_cash: float = 100_000.0,
        config: PaperBrokerConfig | None = None,
    ) -> None:
        self._cfg = config or PaperBrokerConfig()
        self._portfolio = Portfolio(cash=float(start_cash))
        self._prices: dict[str, float] = {}

    def set_price(self, symbol: str, price: float) -> None:
        if price <= 0:
            raise ValueError("price must be positive")
        self._prices[symbol] = float(price)

    def prices(self) -> dict[str, float]:
        return dict(self._prices)

    def portfolio(self) -> Portfolio:
        return self._portfolio

    def _fee(self, *, qty: int, price: float) -> float:
        notional = float(qty) * float(price)
        fee = notional * float(self._cfg.commission_bps) / 10_000.0
        return float(max(fee, float(self._cfg.min_fee)))

    def _market_fill_price(self, *, side: str, mark_price: float) -> tuple[float, float]:
        slip = float(self._cfg.slippage_bps) / 10_000.0
        if side == "BUY":
            px = float(mark_price) * (1.0 + slip)
        else:
            px = float(mark_price) * (1.0 - slip)
        return float(px), float(px - mark_price)

    def submit_order(self, order: Order) -> Fill | OrderRejection:
        if order.qty <= 0:
            return OrderRejection(order=order, reason="qty must be positive")

        mark = self._prices.get(order.symbol)
        if mark is None or mark <= 0:
            return OrderRejection(order=order, reason="missing mark price")

        if order.type == "LIMIT":
            if order.limit_price is None or order.limit_price <= 0:
                return OrderRejection(order=order, reason="limit_price required for LIMIT orders")

            if order.side == "BUY" and float(mark) > float(order.limit_price):
                return OrderRejection(order=order, reason="limit not marketable")
            if order.side == "SELL" and float(mark) < float(order.limit_price):
                return OrderRejection(order=order, reason="limit not marketable")

            fill_price = float(mark)  # fill at best available (simple model)
            slippage = 0.0
        else:
            fill_price, slippage = self._market_fill_price(side=order.side, mark_price=float(mark))

        fee = self._fee(qty=order.qty, price=fill_price)
        ts = datetime.utcnow()

        pos = self._portfolio.get_position(order.symbol)

        if order.side == "BUY":
            cost = float(order.qty) * float(fill_price) + fee
            if cost > self._portfolio.cash:
                return OrderRejection(order=order, reason="insufficient cash")

            new_qty = pos.qty + order.qty
            if new_qty <= 0:
                return OrderRejection(order=order, reason="invalid resulting position")

            if pos.qty == 0:
                pos.avg_price = float(fill_price)
                pos.stop_loss = None
                pos.take_profit = None
            else:
                pos.avg_price = (
                    pos.avg_price * pos.qty + float(fill_price) * order.qty
                ) / float(new_qty)

            pos.qty = new_qty
            self._portfolio.cash -= cost

        elif order.side == "SELL":
            if order.qty > pos.qty:
                return OrderRejection(order=order, reason="insufficient position")

            proceeds = float(order.qty) * float(fill_price) - fee
            pos.realized_pnl += (float(fill_price) - float(pos.avg_price)) * float(order.qty)
            pos.qty -= order.qty
            if pos.qty == 0:
                pos.avg_price = 0.0
                pos.stop_loss = None
                pos.take_profit = None

            self._portfolio.cash += proceeds

        else:
            return OrderRejection(order=order, reason=f"unknown side: {order.side}")

        self._portfolio.fees_paid += float(fee)

        return Fill(
            order_id=order.id or uuid.uuid4().hex,
            ts=ts,
            symbol=order.symbol,
            side=order.side,
            qty=order.qty,
            price=float(fill_price),
            fee=float(fee),
            slippage=float(slippage),
            note=order.tag,
        )
