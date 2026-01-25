"""Self-learning components (Phase 3): ensemble weighting + bounded parameter tuning."""

try:
    from .ensemble import ExponentialWeightsEnsemble
except ImportError:
    ExponentialWeightsEnsemble = None

try:
    from .tuner import ParameterTuner
except ImportError:
    ParameterTuner = None

from .hyperparameter_optimizer import HyperparameterOptimizer, OptimizationObjective

__all__ = [
    "HyperparameterOptimizer",
    "OptimizationObjective",
]

if ExponentialWeightsEnsemble:
    __all__.append("ExponentialWeightsEnsemble")

if ParameterTuner:
    __all__.append("ParameterTuner")
