"""Analytics and reporting (DuckDB rebuildable from SQLite event store)."""

try:
    from .duckdb_pipeline import PerformanceSummary
except ImportError:
    PerformanceSummary = None

from .data_validator import DataValidator
from .walk_forward import WalkForwardAnalyzer

__all__ = [
    "DataValidator",
    "WalkForwardAnalyzer",
]

if PerformanceSummary:
    __all__.append("PerformanceSummary")
