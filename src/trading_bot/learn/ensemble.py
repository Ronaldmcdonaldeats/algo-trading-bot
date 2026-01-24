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
    - eta decays over time for learning stability
    """

    weights: Dict[str, float]
    eta: float = 0.3
    min_weight: float = 1e-6
    update_count: int = 0  # Track updates for decay
    _normalized_cache: Dict[str, float] | None = None  # Cache normalized weights

    @classmethod
    def uniform(cls, names: list[str], *, eta: float = 0.3) -> "ExponentialWeightsEnsemble":
        w = {n: 1.0 for n in names}
        return cls(weights=w, eta=float(eta))

    def normalized(self) -> Dict[str, float]:
        # Return cached result if available
        if self._normalized_cache is not None:
            return self._normalized_cache
        
        total = sum(max(self.min_weight, float(v)) for v in self.weights.values())
        if total <= 0:
            result = {k: 1.0 / max(1, len(self.weights)) for k in self.weights}
        else:
            result = {k: max(self.min_weight, float(v)) / total for k, v in self.weights.items()}
        
        self._normalized_cache = result
        return result

    def update(self, rewards_01: Mapping[str, float]) -> None:
        # multiplicative weights update with learning rate decay
        # eta decays: 0.3 → 0.05 over 1000 updates (smooth convergence)
        decayed_eta = self.eta * (1.0 / (1.0 + (float(self.update_count) / 1000.0)))
        
        for name, r in rewards_01.items():
            if name not in self.weights:
                continue
            rr = _clip(float(r), 0.0, 1.0)
            self.weights[name] = max(
                self.min_weight,
                float(self.weights[name]) * math.exp(decayed_eta * (rr - 0.5)),
            )
        
        self.update_count += 1
        self._normalized_cache = None  # Invalidate cache

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

        signal = 1 if score >= 0.3 else (-1 if score <= -0.3 else 0)

        return StrategyDecision(
            signal=int(signal),
            confidence=float(_clip(conf, 0.0, 1.0)),
            votes=votes,
            weights=w,
            explanations=explanations,
        )

    def to_json(self) -> str:
        return json.dumps(self.normalized(), sort_keys=True)
