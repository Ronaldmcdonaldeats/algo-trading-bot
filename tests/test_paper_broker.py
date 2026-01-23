from __future__ import annotations

import uuid

from trading_bot.broker.base import OrderRejection
from trading_bot.broker.paper import PaperBroker
from trading_bot.core.models import Order


def test_buy_then_sell_updates_cash_and_pnl() -> None:
    broker = PaperBroker(start_cash=1000.0)
    broker.set_price("TEST", 10.0)

    buy = Order(
        id=uuid.uuid4().hex,
        ts=__import__("datetime").datetime.utcnow(),
        symbol="TEST",
        side="BUY",
        qty=50,
        type="MARKET",
        tag="test",
    )
    res = broker.submit_order(buy)
    assert not isinstance(res, OrderRejection)

    pf = broker.portfolio()
    assert pf.cash == 500.0
    assert pf.get_position("TEST").qty == 50

    broker.set_price("TEST", 12.0)
    sell = Order(
        id=uuid.uuid4().hex,
        ts=__import__("datetime").datetime.utcnow(),
        symbol="TEST",
        side="SELL",
        qty=50,
        type="MARKET",
        tag="test",
    )
    res2 = broker.submit_order(sell)
    assert not isinstance(res2, OrderRejection)

    pf2 = broker.portfolio()
    assert pf2.cash == 1100.0
    assert pf2.get_position("TEST").qty == 0
    assert pf2.realized_pnl() == 100.0


def test_cannot_sell_without_position() -> None:
    broker = PaperBroker(start_cash=1000.0)
    broker.set_price("TEST", 10.0)

    sell = Order(
        id=uuid.uuid4().hex,
        ts=__import__("datetime").datetime.utcnow(),
        symbol="TEST",
        side="SELL",
        qty=1,
        type="MARKET",
        tag="test",
    )
    res = broker.submit_order(sell)
    assert isinstance(res, OrderRejection)
