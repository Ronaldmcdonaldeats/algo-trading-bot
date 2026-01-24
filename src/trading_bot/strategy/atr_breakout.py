from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pandas as pd
from ta.volatility import AverageTrueRange

from trading_bot.strategy.base import StrategyOutput


@dataclass
class AtrBreakoutStrategy:
    name: str = "breakout_atr"
    atr_period: int = 14
    breakout_lookback: int = 20
    atr_mult: float = 1.0

    def evaluate(self, df: pd.DataFrame) -> StrategyOutput:
        if df.empty:
            return StrategyOutput(signal=0, confidence=0.0, explanation={"error": "empty_df"})

        for col in ("High", "Low", "Close"):
            if col not in df.columns:
                raise ValueError(f"Missing {col} column")

        # Check if we have enough data for the ATR window
        if len(df) < int(self.atr_period):
            return StrategyOutput(
                signal=0,
                confidence=0.0,
                explanation={
                    "error": "insufficient_data",
                    "rows": len(df),
                    "atr_period": int(self.atr_period),
                },
            )

        high = df["High"].astype(float)
        low = df["Low"].astype(float)
        close = df["Close"].astype(float)

        atr = AverageTrueRange(
            high=high,
            low=low,
            close=close,
            window=int(self.atr_period),
        ).average_true_range()

        # Use previous rolling high/low to avoid lookahead.
        roll_high = high.rolling(window=int(self.breakout_lookback)).max().shift(1)
        roll_low = low.rolling(window=int(self.breakout_lookback)).min().shift(1)

        sig = pd.Series(0, index=df.index, dtype="int64")
        in_long = False
        for idx in df.index:
            rh = roll_high.loc[idx]
            if isinstance(rh, pd.Series):
                rh = rh.iloc[0] if len(rh) > 0 else float('nan')
            rl = roll_low.loc[idx]
            if isinstance(rl, pd.Series):
                rl = rl.iloc[0] if len(rl) > 0 else float('nan')
            a = atr.loc[idx]
            if isinstance(a, pd.Series):
                a = a.iloc[0] if len(a) > 0 else float('nan')
            c = close.loc[idx]
            if isinstance(c, pd.Series):
                c = c.iloc[0] if len(c) > 0 else float('nan')

            if not in_long and pd.notna(rh) and pd.notna(a) and float(c) > float(rh) + float(a) * float(self.atr_mult):
                in_long = True
            elif in_long and pd.notna(rl) and pd.notna(a) and float(c) < float(rl) - float(a) * float(self.atr_mult):
                in_long = False

            sig.loc[idx] = 1 if in_long else 0

        last_atr = float(atr.iloc[-1]) if pd.notna(atr.iloc[-1]) else float("nan")
        last_rh = float(roll_high.iloc[-1]) if pd.notna(roll_high.iloc[-1]) else float("nan")
        last_rl = float(roll_low.iloc[-1]) if pd.notna(roll_low.iloc[-1]) else float("nan")
        last_close = float(close.iloc[-1])
        signal = int(sig.iloc[-1])

        # Confidence increases with distance beyond the breakout threshold.
        if pd.isna(last_atr) or last_atr <= 0 or pd.isna(last_rh):
            conf = 0.0
        else:
            thresh = last_rh + last_atr * float(self.atr_mult)
            conf = min(1.0, max(0.0, (last_close - thresh) / (2.0 * last_atr)))
            if signal == 0 and pd.notna(last_rl):
                # if we're flat, confidence is how far below breakdown threshold we are
                thresh2 = last_rl - last_atr * float(self.atr_mult)
                conf = min(1.0, max(0.0, (thresh2 - last_close) / (2.0 * last_atr)))

        explanation: Dict[str, Any] = {
            "atr": last_atr,
            "atr_period": int(self.atr_period),
            "breakout_lookback": int(self.breakout_lookback),
            "atr_mult": float(self.atr_mult),
            "roll_high_prev": last_rh,
            "roll_low_prev": last_rl,
            "close": last_close,
        }
        return StrategyOutput(signal=signal, confidence=float(conf), explanation=explanation)
