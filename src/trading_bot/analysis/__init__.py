"""Analysis Module"""

from .equity_curve_analyzer import EquityCurveAnalyzer, EquityCurveAnalysis
from .multi_timeframe import MultiTimeframeAnalyzer, Signal, TimeFrames

__all__ = [
    'EquityCurveAnalyzer', 
    'EquityCurveAnalysis',
    'MultiTimeframeAnalyzer',
    'Signal',
    'TimeFrames',
]
