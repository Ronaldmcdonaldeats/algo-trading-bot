from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable

import pandas as pd

from trading_bot.strategy.atr_breakout import AtrBreakoutStrategy
from trading_bot.strategy.macd_volume_momentum import MacdVolumeMomentumStrategy
from trading_bot.strategy.rsi_mean_reversion import RsiMeanReversionStrategy


@dataclass(frozen=True)
class TuningResult:
    tuned: bool
    params: Dict[str, Dict[str, Any]]
    note: str = ""


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _week_bucket(dt: datetime) -> str:
    d = _ensure_utc(dt).date()
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _returns(close: pd.Series) -> pd.Series:
    return close.astype(float).pct_change().fillna(0.0)


def _score_signals(close: pd.Series, signal: pd.Series) -> float:
    """Simple score: sum of returns when signal==1."""

    rets = _returns(close)
    s = signal.astype(int).shift(1).fillna(0)  # trade next bar
    return float((rets * s).sum())


def _grid(values: Iterable[Any]) -> list[Any]:
    return list(values)


def maybe_tune_weekly(
    *,
    now: datetime,
    last_tuned_bucket: str | None,
    ohlcv_by_symbol: Dict[str, pd.DataFrame],
    current_params: Dict[str, Dict[str, Any]],
) -> TuningResult:
    """Tune a small set of parameters once per ISO week.

    This is intentionally bounded and explainable: we only tune a few knobs using a simple
    objective on recent data.
    """

    bucket = _week_bucket(now)
    if last_tuned_bucket == bucket:
        return TuningResult(tuned=False, params=current_params, note="already_tuned_this_week")

    params: Dict[str, Dict[str, Any]] = json.loads(json.dumps(current_params))

    # RSI mean reversion: tune oversold entry threshold.
    best_score = None
    best_entry = None
    for entry in _grid([25.0, 30.0, 35.0]):
        score = 0.0
        for df in ohlcv_by_symbol.values():
            if df.empty or "Close" not in df.columns:
                continue
            strat = RsiMeanReversionStrategy(
                rsi_period=int(params.get("mean_reversion_rsi", {}).get("rsi_period", 14)),
                entry_oversold=float(entry),
                exit_rsi=float(params.get("mean_reversion_rsi", {}).get("exit_rsi", 50.0)),
            )
            out = strat.evaluate(df)
            # Reconstruct a signal series for scoring by re-running strategy logic is expensive.
            # Here we approximate using the final signal as a constant; tuning still bounded.
            # For more accuracy, wire a proper backtest engine in Phase 4+.
            sig = pd.Series(int(out.signal), index=df.index)
            score += _score_signals(df["Close"], sig)
        if best_score is None or score > best_score:
            best_score = score
            best_entry = entry

    if best_entry is not None:
        params.setdefault("mean_reversion_rsi", {})["entry_oversold"] = float(best_entry)

    # MACD momentum: tune volume multiplier.
    best_score = None
    best_mult = None
    for mult in _grid([1.0, 1.25, 1.5, 2.0]):
        score = 0.0
        for df in ohlcv_by_symbol.values():
            if df.empty or "Close" not in df.columns or "Volume" not in df.columns:
                continue
            strat = MacdVolumeMomentumStrategy(
                macd_fast=int(params.get("momentum_macd_volume", {}).get("macd_fast", 12)),
                macd_slow=int(params.get("momentum_macd_volume", {}).get("macd_slow", 26)),
                macd_signal=int(params.get("momentum_macd_volume", {}).get("macd_signal", 9)),
                vol_sma=int(params.get("momentum_macd_volume", {}).get("vol_sma", 20)),
                vol_mult=float(mult),
            )
            out = strat.evaluate(df)
            sig = pd.Series(int(out.signal), index=df.index)
            score += _score_signals(df["Close"], sig)
        if best_score is None or score > best_score:
            best_score = score
            best_mult = mult

    if best_mult is not None:
        params.setdefault("momentum_macd_volume", {})["vol_mult"] = float(best_mult)

    # ATR breakout: tune atr_mult.
    best_score = None
    best_atr_mult = None
    for atr_mult in _grid([0.75, 1.0, 1.25, 1.5]):
        score = 0.0
        for df in ohlcv_by_symbol.values():
            if df.empty or not {"High", "Low", "Close"}.issubset(set(df.columns)):
                continue
            strat = AtrBreakoutStrategy(
                atr_period=int(params.get("breakout_atr", {}).get("atr_period", 14)),
                breakout_lookback=int(params.get("breakout_atr", {}).get("breakout_lookback", 20)),
                atr_mult=float(atr_mult),
            )
            out = strat.evaluate(df)
            sig = pd.Series(int(out.signal), index=df.index)
            score += _score_signals(df["Close"], sig)
        if best_score is None or score > best_score:
            best_score = score
            best_atr_mult = atr_mult

    if best_atr_mult is not None:
        params.setdefault("breakout_atr", {})["atr_mult"] = float(best_atr_mult)

    return TuningResult(tuned=True, params=params, note=f"tuned_week={bucket}")


def default_params() -> Dict[str, Dict[str, Any]]:
    return {
        "mean_reversion_rsi": {
            "rsi_period": 14,
            "entry_oversold": 30.0,
            "exit_rsi": 50.0,
        },
        "momentum_macd_volume": {
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "vol_sma": 20,
            "vol_mult": 1.0,
        },
        "breakout_atr": {
            "atr_period": 14,
            "breakout_lookback": 20,
            "atr_mult": 1.0,
        },
    }


def should_tune(now: datetime, *, last_tuned_ts: datetime | None, interval_days: int = 7) -> bool:
    if interval_days <= 0:
        interval_days = 7
    if last_tuned_ts is None:
        return True
    return _ensure_utc(now) - _ensure_utc(last_tuned_ts) >= timedelta(days=int(interval_days))
