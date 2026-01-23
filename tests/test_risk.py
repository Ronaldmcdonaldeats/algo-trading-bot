from __future__ import annotations

from trading_bot.risk import position_size_shares, stop_loss_price, take_profit_price


def test_stop_loss_take_profit_prices():
    entry = 100.0
    assert stop_loss_price(entry, 0.015) == 98.5
    assert take_profit_price(entry, 0.03) == 103.0


def test_position_size_shares_basic():
    equity = 10_000
    entry = 100.0
    sl = 98.5
    shares = position_size_shares(
        equity=equity,
        entry_price=entry,
        stop_loss_price_=sl,
        max_risk=0.02,
    )
    # risk budget = 200, per-share risk = 1.5 => floor(133.33..) = 133
    assert shares == 133
