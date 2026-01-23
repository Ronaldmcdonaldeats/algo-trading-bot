from __future__ import annotations

from datetime import datetime, timedelta, timezone

from trading_bot.schedule.us_equities import is_market_open, next_bar_time, parse_interval


def test_parse_interval() -> None:
    assert parse_interval("15m") == timedelta(minutes=15)
    assert parse_interval("1h") == timedelta(hours=1)


def test_market_open_window_weekday() -> None:
    # January is typically EST (UTC-5). 10:00 ET => 15:00 UTC.
    dt = datetime(2026, 1, 2, 15, 0, tzinfo=timezone.utc)  # Fri
    assert is_market_open(dt) is True

    dt2 = datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc)  # 09:00 ET
    assert is_market_open(dt2) is False


def test_next_bar_time_intraday_from_before_open() -> None:
    # 09:00 ET (14:00 UTC) should schedule first 15m bar close at 09:45 ET (14:45 UTC).
    now = datetime(2026, 1, 2, 14, 0, tzinfo=timezone.utc)
    nxt = next_bar_time(now, interval=timedelta(minutes=15))
    assert nxt == datetime(2026, 1, 2, 14, 45, tzinfo=timezone.utc)


def test_next_bar_time_intraday_from_mid_session() -> None:
    # 10:07 ET (15:07 UTC) -> next 15m close is 10:15 ET (15:15 UTC)
    now = datetime(2026, 1, 2, 15, 7, tzinfo=timezone.utc)
    nxt = next_bar_time(now, interval=timedelta(minutes=15))
    assert nxt == datetime(2026, 1, 2, 15, 15, tzinfo=timezone.utc)
