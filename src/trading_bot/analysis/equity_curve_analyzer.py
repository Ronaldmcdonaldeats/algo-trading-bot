"""Equity Curve Analyzer - Identify drawdowns, recovery patterns, optimization zones

Analyzes equity curve to find:
- Drawdown periods and recovery time
- Underwater plots
- Optimal parameters for each regime
- Volatility regimes
- Inflection points where strategy changes needed
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class DrawdownPeriod:
    """Information about a drawdown period"""
    start_date: str
    end_date: str
    start_equity: float
    trough_equity: float
    recovery_date: Optional[str]
    max_drawdown_pct: float
    recovery_days: int
    notes: str


@dataclass
class EquityCurveAnalysis:
    """Complete equity curve analysis"""
    total_periods: int
    total_return: float
    annual_return: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    drawdown_periods: List[DrawdownPeriod]
    avg_recovery_days: float
    num_underwater_days: int
    volatility_regimes: List[Dict]
    optimization_zones: List[Dict]
    inflection_points: List[Tuple[str, str]]  # (date, reason)


class EquityCurveAnalyzer:
    """Analyze equity curve for patterns and optimization opportunities"""
    
    def __init__(self, cache_dir: str = ".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
    def analyze_equity_curve(self, equity_series: pd.Series) -> EquityCurveAnalysis:
        """Analyze complete equity curve
        
        Args:
            equity_series: Series with datetime index and equity values
        """
        
        # Basic metrics
        total_return = (equity_series.iloc[-1] - equity_series.iloc[0]) / equity_series.iloc[0]
        daily_returns = equity_series.pct_change()
        annual_return = daily_returns.mean() * 252
        volatility = daily_returns.std() * np.sqrt(252)
        sharpe_ratio = (annual_return - 0.02) / volatility if volatility > 0 else 0
        
        # Drawdown analysis
        drawdown_periods = self._find_drawdown_periods(equity_series)
        
        # Underwater plot (how far below peak)
        running_max = equity_series.expanding().max()
        underwater = (equity_series - running_max) / running_max
        num_underwater_days = (underwater < -0.001).sum()
        
        # Recovery time
        recovery_times = [d.recovery_days for d in drawdown_periods if d.recovery_date]
        avg_recovery = np.mean(recovery_times) if recovery_times else 0
        
        # Volatility regimes
        vol_regimes = self._identify_volatility_regimes(daily_returns)
        
        # Optimization zones (periods with consistent losses)
        opt_zones = self._identify_optimization_zones(daily_returns, equity_series)
        
        # Inflection points (where trend changes)
        inflections = self._find_inflection_points(equity_series)
        
        return EquityCurveAnalysis(
            total_periods=len(equity_series),
            total_return=total_return,
            annual_return=annual_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=min(underwater),
            drawdown_periods=drawdown_periods,
            avg_recovery_days=avg_recovery,
            num_underwater_days=num_underwater_days,
            volatility_regimes=vol_regimes,
            optimization_zones=opt_zones,
            inflection_points=inflections
        )
    
    def _find_drawdown_periods(self, equity_series: pd.Series) -> List[DrawdownPeriod]:
        """Find all drawdown periods in equity curve"""
        
        drawdowns = []
        running_max = equity_series.expanding().max()
        drawdown = (equity_series - running_max) / running_max
        
        in_drawdown = False
        start_idx = None
        trough_idx = None
        start_equity = None
        
        for i in range(1, len(equity_series)):
            if drawdown.iloc[i] < -0.01 and not in_drawdown:  # Start of drawdown
                in_drawdown = True
                start_idx = i
                start_equity = equity_series.iloc[i]
                trough_idx = i
            
            if in_drawdown:
                if equity_series.iloc[i] < equity_series.iloc[trough_idx]:
                    trough_idx = i  # New trough
                
                # Check if recovered
                if equity_series.iloc[i] >= running_max.iloc[start_idx]:
                    # Recovery complete
                    drawdown_period = DrawdownPeriod(
                        start_date=equity_series.index[start_idx].strftime('%Y-%m-%d'),
                        end_date=equity_series.index[trough_idx].strftime('%Y-%m-%d'),
                        start_equity=start_equity,
                        trough_equity=equity_series.iloc[trough_idx],
                        recovery_date=equity_series.index[i].strftime('%Y-%m-%d'),
                        max_drawdown_pct=float(drawdown.iloc[trough_idx]),
                        recovery_days=int((equity_series.index[i] - equity_series.index[start_idx]).days),
                        notes=f"Recovered in {(equity_series.index[i] - equity_series.index[start_idx]).days} days"
                    )
                    drawdowns.append(drawdown_period)
                    in_drawdown = False
        
        # Unrecovered drawdown
        if in_drawdown:
            drawdown_period = DrawdownPeriod(
                start_date=equity_series.index[start_idx].strftime('%Y-%m-%d'),
                end_date=equity_series.index[trough_idx].strftime('%Y-%m-%d'),
                start_equity=start_equity,
                trough_equity=equity_series.iloc[trough_idx],
                recovery_date=None,
                max_drawdown_pct=float(drawdown.iloc[trough_idx]),
                recovery_days=-1,
                notes="Unrecovered drawdown (still underwater)"
            )
            drawdowns.append(drawdown_period)
        
        return drawdowns
    
    def _identify_volatility_regimes(self, returns: pd.Series, window: int = 20) -> List[Dict]:
        """Identify periods of high/low volatility"""
        
        rolling_vol = returns.rolling(window).std() * np.sqrt(252)
        vol_threshold = rolling_vol.median()
        
        regimes = []
        in_high_vol = rolling_vol.iloc[window] > vol_threshold
        start_idx = window
        
        for i in range(window + 1, len(returns)):
            is_high_vol = rolling_vol.iloc[i] > vol_threshold
            
            if is_high_vol != in_high_vol:
                regimes.append({
                    'period': f"{returns.index[start_idx].strftime('%Y-%m-%d')} to {returns.index[i].strftime('%Y-%m-%d')}",
                    'regime': 'HIGH_VOLATILITY' if in_high_vol else 'LOW_VOLATILITY',
                    'avg_vol': float(rolling_vol.iloc[start_idx:i].mean()),
                    'duration_days': i - start_idx
                })
                start_idx = i
                in_high_vol = is_high_vol
        
        return regimes
    
    def _identify_optimization_zones(self, returns: pd.Series, 
                                    equity: pd.Series, window: int = 10) -> List[Dict]:
        """Identify periods where strategy underperformed"""
        
        zones = []
        rolling_return = returns.rolling(window).sum()
        threshold = rolling_return.quantile(0.25)  # Bottom 25%
        
        in_zone = False
        start_idx = None
        
        for i in range(window, len(returns)):
            if rolling_return.iloc[i] < threshold and not in_zone:
                in_zone = True
                start_idx = i
            elif rolling_return.iloc[i] >= threshold and in_zone:
                zones.append({
                    'period': f"{returns.index[start_idx].strftime('%Y-%m-%d')} to {returns.index[i].strftime('%Y-%m-%d')}",
                    'avg_return': float(rolling_return.iloc[start_idx]),
                    'duration_days': i - start_idx,
                    'recommendation': 'Consider parameter adjustment or strategy switch'
                })
                in_zone = False
        
        return zones
    
    def _find_inflection_points(self, equity: pd.Series) -> List[Tuple[str, str]]:
        """Find inflection points where trend changes significantly"""
        
        points = []
        returns = equity.pct_change()
        
        # Simple inflection: where 5-day return changes sign
        ma_5 = returns.rolling(5).mean()
        
        for i in range(1, len(ma_5)):
            if ma_5.iloc[i-1] > 0 and ma_5.iloc[i] <= 0:
                points.append((
                    equity.index[i].strftime('%Y-%m-%d'),
                    "Trend shift from positive to negative"
                ))
            elif ma_5.iloc[i-1] <= 0 and ma_5.iloc[i] > 0:
                points.append((
                    equity.index[i].strftime('%Y-%m-%d'),
                    "Trend shift from negative to positive"
                ))
        
        return points[-20:]  # Last 20 inflection points
    
    def plot_underwater(self, equity_series: pd.Series) -> Dict[str, list]:
        """Generate underwater plot data (for dashboard)"""
        
        running_max = equity_series.expanding().max()
        underwater = (equity_series - running_max) / running_max
        
        return {
            'dates': [d.strftime('%Y-%m-%d') for d in equity_series.index],
            'underwater': underwater.tolist()
        }
    
    def save_analysis(self, analysis: EquityCurveAnalysis, 
                     filename: str = "equity_curve_analysis.json"):
        """Save analysis to JSON"""
        
        filepath = self.cache_dir / filename
        
        data = {
            'total_periods': analysis.total_periods,
            'total_return': analysis.total_return,
            'annual_return': analysis.annual_return,
            'volatility': analysis.volatility,
            'sharpe_ratio': analysis.sharpe_ratio,
            'max_drawdown': analysis.max_drawdown,
            'avg_recovery_days': analysis.avg_recovery_days,
            'num_underwater_days': analysis.num_underwater_days,
            'drawdown_periods': [
                {
                    'start_date': d.start_date,
                    'end_date': d.end_date,
                    'max_drawdown_pct': d.max_drawdown_pct,
                    'recovery_date': d.recovery_date,
                    'recovery_days': d.recovery_days
                }
                for d in analysis.drawdown_periods
            ],
            'volatility_regimes': analysis.volatility_regimes,
            'optimization_zones': analysis.optimization_zones,
            'inflection_points': analysis.inflection_points,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Equity curve analysis saved to {filepath}")
        return str(filepath)
