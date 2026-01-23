from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from trading_bot.strategy.base import StrategyDecision, StrategyOutput


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def reward_to_unit_interval(ret: float, *, scale: float = 0.002) -> float:
    """Map a return to [0, 1] for stable multiplicative updates.

    For 15m bars, returns are usually small. `scale` controls sensitivity.
    """

    if scale <= 0:
        scale = 0.002
    z = _clip(float(ret) / float(scale), -10.0, 10.0)
    # tanh -> (-1, 1), map to (0, 1)
    return 0.5 * (1.0 + math.tanh(z))


@dataclass
class ExponentialWeightsEnsemble:
    """Online strategy weighting using exponential updates.

    This behaves like a bandit/ensemble hybrid: we keep a weight per strategy and
    update weights each step based on observed rewards.

    Safety/explainability:
    - weights are bounded and normalized
    - decisions include full vote breakdown + current weights
    """

    weights: Dict[str, float]
    eta: float = 0.3
    min_weight: float = 1e-6

    @classmethod
    def uniform(cls, names: list[str], *, eta: float = 0.3) -> "ExponentialWeightsEnsemble":
        w = {n: 1.0 for n in names}
        return cls(weights=w, eta=float(eta))

    def normalized(self) -> Dict[str, float]:
        total = sum(max(self.min_weight, float(v)) for v in self.weights.values())
        if total <= 0:
            return {k: 1.0 / max(1, len(self.weights)) for k in self.weights}
        return {k: max(self.min_weight, float(v)) / total for k, v in self.weights.items()}

    def update(self, rewards_01: Mapping[str, float]) -> None:
        # multiplicative weights update: w_i <- w_i * exp(eta * (r_i - 0.5))
        for name, r in rewards_01.items():
            if name not in self.weights:
                continue
            rr = _clip(float(r), 0.0, 1.0)
            self.weights[name] = max(
                self.min_weight,
                float(self.weights[name]) * math.exp(float(self.eta) * (rr - 0.5)),
            )

    def decide(self, outputs: Mapping[str, StrategyOutput]) -> StrategyDecision:
        w = self.normalized()

        votes: Dict[str, int] = {}
        explanations: Dict[str, Dict[str, Any]] = {}
        score = 0.0
        conf = 0.0

        for name, out in outputs.items():
            votes[name] = int(out.signal)
            explanations[name] = dict(out.explanation)

            ww = float(w.get(name, 0.0))
            score += ww * float(out.signal)
            conf += ww * float(_clip(float(out.confidence), 0.0, 1.0))

        signal = 1 if score >= 0.5 else 0

        return StrategyDecision(
            signal=int(signal),
            confidence=float(_clip(conf, 0.0, 1.0)),
            votes=votes,
            weights=w,
            explanations=explanations,
        )

    def to_json(self) -> str:
        return json.dumps(self.normalized(), sort_keys=True)
