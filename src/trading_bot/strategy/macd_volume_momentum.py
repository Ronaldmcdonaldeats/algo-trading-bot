from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pandas as pd
from ta.trend import MACD

from trading_bot.strategy.base import StrategyOutput


@dataclass
class MacdVolumeMomentumStrategy:
    name: str = "momentum_macd_volume"
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    vol_sma: int = 20
    vol_mult: float = 1.0

    def evaluate(self, df: pd.DataFrame) -> StrategyOutput:
        if df.empty:
            return StrategyOutput(signal=0, confidence=0.0, explanation={"error": "empty_df"})

        for col in ("Close", "Volume"):
            if col not in df.columns:
                raise ValueError(f"Missing {col} column")

        close = df["Close"].astype(float)
        volume = df["Volume"].astype(float)

        macd = MACD(
            close=close,
            window_fast=int(self.macd_fast),
            window_slow=int(self.macd_slow),
            window_sign=int(self.macd_signal),
        )
        macd_diff = macd.macd_diff()

        vol_ma = volume.rolling(window=int(self.vol_sma)).mean()
        vol_ok = volume >= (vol_ma * float(self.vol_mult))

        sig = pd.Series(0, index=df.index, dtype="int64")
        in_long = False
        for idx in df.index:
            md = macd_diff.loc[idx]
            v_ok = bool(vol_ok.loc[idx]) if pd.notna(vol_ok.loc[idx]) else False

            if not in_long and pd.notna(md) and float(md) > 0 and v_ok:
                in_long = True
            elif in_long and pd.notna(md) and float(md) < 0:
                in_long = False
            sig.loc[idx] = 1 if in_long else 0

        last_md = float(macd_diff.iloc[-1]) if pd.notna(macd_diff.iloc[-1]) else float("nan")
        last_vol = float(volume.iloc[-1])
        last_vol_ma = float(vol_ma.iloc[-1]) if pd.notna(vol_ma.iloc[-1]) else float("nan")
        signal = int(sig.iloc[-1])

        # Confidence: MACD diff magnitude plus volume confirmation.
        md_conf = 0.0 if pd.isna(last_md) else min(1.0, abs(last_md) / 0.5)
        v_conf = 0.0 if pd.isna(last_vol_ma) or last_vol_ma <= 0 else min(1.0, last_vol / last_vol_ma)
        conf = min(1.0, 0.5 * md_conf + 0.5 * min(1.0, v_conf / float(self.vol_mult)))

        explanation: Dict[str, Any] = {
            "macd_diff": last_md,
            "macd_fast": int(self.macd_fast),
            "macd_slow": int(self.macd_slow),
            "macd_signal": int(self.macd_signal),
            "volume": last_vol,
            "vol_sma": int(self.vol_sma),
            "vol_mult": float(self.vol_mult),
            "vol_ma": last_vol_ma,
        }
        return StrategyOutput(signal=signal, confidence=float(conf), explanation=explanation)
