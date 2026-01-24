from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import pandas as pd
from ta.momentum import RSIIndicator

from trading_bot.strategy.base import StrategyOutput


@dataclass
class RsiMeanReversionStrategy:
    name: str = "mean_reversion_rsi"
    rsi_period: int = 14
    entry_oversold: float = 30.0
    exit_rsi: float = 50.0

    def evaluate(self, df: pd.DataFrame) -> StrategyOutput:
        if df.empty:
            return StrategyOutput(signal=0, confidence=0.0, explanation={"error": "empty_df"})
        if "Close" not in df.columns:
            raise ValueError("Missing Close column")

        close = df["Close"].astype(float)
        rsi = RSIIndicator(close=close, window=int(self.rsi_period)).rsi()

        sig = pd.Series(0, index=df.index, dtype="int64")
        in_long = False
        for idx in df.index:
            rsi_val = rsi.loc[idx]
            if isinstance(rsi_val, pd.Series):
                rsi_val = rsi_val.iloc[0] if len(rsi_val) > 0 else float('nan')
            r = float(rsi_val) if pd.notna(rsi_val) else float("nan")
            if not in_long and pd.notna(rsi_val) and r <= float(self.entry_oversold):
                in_long = True
            elif in_long and pd.notna(rsi_val) and r >= float(self.exit_rsi):
                in_long = False
            sig.loc[idx] = 1 if in_long else 0

        last_rsi = float(rsi.iloc[-1]) if pd.notna(rsi.iloc[-1]) else float("nan")
        signal = int(sig.iloc[-1])

        if pd.isna(last_rsi):
            conf = 0.0
        elif signal == 1:
            # more confident when deeper oversold
            conf = min(1.0, max(0.0, (float(self.entry_oversold) - last_rsi) / 20.0))
        else:
            conf = min(1.0, max(0.0, (last_rsi - float(self.exit_rsi)) / 20.0))

        explanation: Dict[str, Any] = {
            "rsi": last_rsi,
            "rsi_period": int(self.rsi_period),
            "entry_oversold": float(self.entry_oversold),
            "exit_rsi": float(self.exit_rsi),
        }
        return StrategyOutput(signal=signal, confidence=float(conf), explanation=explanation)
