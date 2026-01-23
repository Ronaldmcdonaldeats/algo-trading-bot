from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

try:
    from zoneinfo import ZoneInfo  # py>=3.9
except ModuleNotFoundError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore


NY = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_eastern(dt: datetime) -> datetime:
    return _ensure_utc(dt).astimezone(NY)


def _is_weekday(d: date) -> bool:
    return d.weekday() < 5


def is_market_open(dt: datetime) -> bool:
    et = to_eastern(dt)
    if not _is_weekday(et.date()):
        return False
    t = et.timetz().replace(tzinfo=None)
    return MARKET_OPEN <= t < MARKET_CLOSE


def next_market_open(dt: datetime) -> datetime:
    et = to_eastern(dt)
    d = et.date()

    if _is_weekday(d) and et.timetz().replace(tzinfo=None) < MARKET_OPEN:
        open_et = datetime.combine(d, MARKET_OPEN, tzinfo=NY)
        return open_et.astimezone(timezone.utc)

    # Find next weekday.
    d2 = d + timedelta(days=1)
    while not _is_weekday(d2):
        d2 += timedelta(days=1)

    open_et = datetime.combine(d2, MARKET_OPEN, tzinfo=NY)
    return open_et.astimezone(timezone.utc)


def parse_interval(interval: str) -> timedelta:
    m = re.fullmatch(r"\s*(\d+)\s*([mhd])\s*", str(interval).lower())
    if not m:
        raise ValueError(f"Unsupported interval: {interval!r} (expected like 5m, 15m, 1h, 1d)")

    n = int(m.group(1))
    unit = m.group(2)

    if n <= 0:
        raise ValueError("interval must be positive")

    if unit == "m":
        return timedelta(minutes=n)
    if unit == "h":
        return timedelta(hours=n)
    if unit == "d":
        return timedelta(days=n)

    raise ValueError(f"Unsupported interval unit: {unit}")


def next_bar_time(dt: datetime, *, interval: timedelta) -> datetime:
    """Return the next bar close time in UTC.

    Assumes intraday bars are anchored to US equities session open (9:30 ET).
    The first 15m bar closes at 9:45 ET (open + interval).
    """

    if interval >= timedelta(days=1):
        return _ensure_utc(dt)

    et = to_eastern(dt)
    d = et.date()

    if not _is_weekday(d):
        # Next weekday open, then first bar close.
        return next_market_open(dt) + interval

    open_et = datetime.combine(d, MARKET_OPEN, tzinfo=NY)
    close_et = datetime.combine(d, MARKET_CLOSE, tzinfo=NY)

    if et <= open_et:
        return (open_et + interval).astimezone(timezone.utc)
    if et >= close_et:
        return next_market_open(dt) + interval

    elapsed = et - open_et
    step = int(elapsed.total_seconds() // interval.total_seconds())
    nxt = open_et + (step + 1) * interval

    if nxt > close_et:
        nxt = close_et

    return nxt.astimezone(timezone.utc)


@dataclass
class MarketSchedule:
    interval: timedelta
    market_hours_only: bool = True
    next_run_utc: datetime | None = None

    def initialize(self, now_utc: datetime) -> None:
        if self.next_run_utc is None:
            if self.market_hours_only and not is_market_open(now_utc):
                self.next_run_utc = next_bar_time(now_utc, interval=self.interval)
            elif self.market_hours_only and self.interval < timedelta(days=1):
                self.next_run_utc = next_bar_time(now_utc, interval=self.interval)
            else:
                self.next_run_utc = _ensure_utc(now_utc)

    def due(self, now_utc: datetime) -> bool:
        self.initialize(now_utc)
        assert self.next_run_utc is not None
        return _ensure_utc(now_utc) >= self.next_run_utc

    def mark_ran(self, now_utc: datetime) -> None:
        # Schedule the next bar close.
        self.next_run_utc = next_bar_time(now_utc, interval=self.interval)

    def seconds_until_next(self, now_utc: datetime) -> float:
        self.initialize(now_utc)
        assert self.next_run_utc is not None
        return max(0.0, (self.next_run_utc - _ensure_utc(now_utc)).total_seconds())
