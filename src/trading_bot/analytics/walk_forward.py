"""Walk-Forward Analysis - Realistic backtesting with out-of-sample validation"""

from typing import Dict, List, Tuple, Callable, Optional
import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class WalkForwardWindow:
    """Single walk-forward window"""
    window_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_data: pd.DataFrame
    test_data: pd.DataFrame
    train_size: int
    test_size: int


@dataclass
class WalkForwardResult:
    """Results for a single window"""
    window_id: int
    in_sample_return: float
    out_of_sample_return: float
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    in_sample_drawdown: float
    out_of_sample_drawdown: float
    parameter_set: Dict
    train_dates: Tuple[pd.Timestamp, pd.Timestamp]
    test_dates: Tuple[pd.Timestamp, pd.Timestamp]


class WalkForwardAnalyzer:
    """Perform walk-forward analysis"""
    
    def __init__(self, data: pd.DataFrame, 
                 train_size: int = 252,  # 1 year of daily data
                 test_size: int = 63,    # 3 months
                 step_size: int = 63):   # Roll forward 3 months
        """
        Args:
            data: Time series data (DataFrame with returns or prices)
            train_size: In-sample training period (days)
            test_size: Out-of-sample test period (days)
            step_size: Period to move forward each window (days)
        """
        self.data = data.sort_index()
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size
        self.windows: List[WalkForwardWindow] = []
        self.results: List[WalkForwardResult] = []
    
    def generate_windows(self) -> List[WalkForwardWindow]:
        """Generate walk-forward windows"""
        self.windows.clear()
        
        total_size = len(self.data)
        min_required = self.train_size + self.test_size
        
        if total_size < min_required:
            raise ValueError(
                f"Data too short: {total_size} < {min_required} required"
            )
        
        window_id = 0
        train_start = 0
        
        while train_start + min_required <= total_size:
            train_end = train_start + self.train_size
            test_start = train_end
            test_end = min(test_start + self.test_size, total_size)
            
            train_data = self.data.iloc[train_start:train_end]
            test_data = self.data.iloc[test_start:test_end]
            
            window = WalkForwardWindow(
                window_id=window_id,
                train_start=train_data.index[0],
                train_end=train_data.index[-1],
                test_start=test_data.index[0],
                test_end=test_data.index[-1],
                train_data=train_data,
                test_data=test_data,
                train_size=len(train_data),
                test_size=len(test_data)
            )
            
            self.windows.append(window)
            
            train_start += self.step_size
            window_id += 1
        
        return self.windows
    
    def run(self, strategy_func: Callable, 
            param_ranges: Optional[Dict] = None) -> List[WalkForwardResult]:
        """Run walk-forward analysis
        
        Args:
            strategy_func: Function taking (data, params) -> returns pd.Series
            param_ranges: Dict of {param_name: [values]} to test
            
        Returns:
            List of walk-forward results
        """
        self.results.clear()
        
        for window in self.windows:
            # Optimize parameters on training data
            best_params = self._optimize_parameters(
                window.train_data, 
                strategy_func,
                param_ranges
            )
            
            # Generate signals on training data
            train_returns = strategy_func(window.train_data, best_params)
            
            # Generate signals on test data (out-of-sample)
            test_returns = strategy_func(window.test_data, best_params)
            
            # Calculate metrics
            in_sample_ret = self._calculate_return(train_returns)
            out_sample_ret = self._calculate_return(test_returns)
            
            in_sample_sharpe = self._calculate_sharpe(train_returns)
            out_sample_sharpe = self._calculate_sharpe(test_returns)
            
            in_sample_dd = self._calculate_max_drawdown(train_returns)
            out_sample_dd = self._calculate_max_drawdown(test_returns)
            
            result = WalkForwardResult(
                window_id=window.window_id,
                in_sample_return=in_sample_ret,
                out_of_sample_return=out_sample_ret,
                in_sample_sharpe=in_sample_sharpe,
                out_of_sample_sharpe=out_sample_sharpe,
                in_sample_drawdown=in_sample_dd,
                out_of_sample_drawdown=out_sample_dd,
                parameter_set=best_params,
                train_dates=(window.train_start, window.train_end),
                test_dates=(window.test_start, window.test_end)
            )
            
            self.results.append(result)
        
        return self.results
    
    def _optimize_parameters(self, data: pd.DataFrame,
                           strategy_func: Callable,
                           param_ranges: Optional[Dict]) -> Dict:
        """Find best parameters (simplified grid search)"""
        if param_ranges is None or not param_ranges:
            return {}
        
        best_sharpe = -np.inf
        best_params = {}
        
        # Grid search (simple exhaustive)
        param_combinations = self._generate_param_combinations(param_ranges)
        
        for params in param_combinations:
            try:
                returns = strategy_func(data, params)
                sharpe = self._calculate_sharpe(returns)
                
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = params.copy()
            except Exception:
                continue
        
        return best_params
    
    def _generate_param_combinations(self, param_ranges: Dict) -> List[Dict]:
        """Generate all parameter combinations"""
        import itertools
        
        params = list(param_ranges.keys())
        values = [param_ranges[p] for p in params]
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(params, combo)))
        
        return combinations
    
    def _calculate_return(self, returns: pd.Series) -> float:
        """Calculate cumulative return %"""
        if returns.empty:
            return 0.0
        return (1 + returns).prod() - 1
    
    def _calculate_sharpe(self, returns: pd.Series, 
                         risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        
        excess = returns - risk_free_rate / 252
        std = excess.std()
        
        if std == 0:
            return 0.0
        
        sharpe = excess.mean() / std * np.sqrt(252)
        return sharpe if not np.isnan(sharpe) else 0.0
    
    def _calculate_max_drawdown(self, returns: pd.Series) -> float:
        """Calculate maximum drawdown"""
        if returns.empty:
            return 0.0
        
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        
        return drawdown.min()
    
    def get_summary(self) -> Dict:
        """Get walk-forward analysis summary"""
        if not self.results:
            return {}
        
        in_sample_returns = [r.in_sample_return for r in self.results]
        out_sample_returns = [r.out_of_sample_return for r in self.results]
        in_sample_sharpes = [r.in_sample_sharpe for r in self.results]
        out_sample_sharpes = [r.out_of_sample_sharpe for r in self.results]
        
        return {
            "num_windows": len(self.results),
            "in_sample_avg_return": np.mean(in_sample_returns),
            "in_sample_std_return": np.std(in_sample_returns),
            "out_of_sample_avg_return": np.mean(out_sample_returns),
            "out_of_sample_std_return": np.std(out_sample_returns),
            "optimization_decay": np.mean(in_sample_returns) - np.mean(out_sample_returns),
            "in_sample_avg_sharpe": np.mean(in_sample_sharpes),
            "out_of_sample_avg_sharpe": np.mean(out_sample_sharpes),
            "in_sample_avg_dd": np.mean([r.in_sample_drawdown for r in self.results]),
            "out_of_sample_avg_dd": np.mean([r.out_of_sample_drawdown for r in self.results])
        }
    
    def get_results_df(self) -> pd.DataFrame:
        """Get results as DataFrame"""
        data = []
        for r in self.results:
            data.append({
                "window": r.window_id,
                "train_start": r.train_dates[0],
                "train_end": r.train_dates[1],
                "test_start": r.test_dates[0],
                "test_end": r.test_dates[1],
                "is_return": r.in_sample_return,
                "oos_return": r.out_of_sample_return,
                "is_sharpe": r.in_sample_sharpe,
                "oos_sharpe": r.out_of_sample_sharpe,
                "is_dd": r.in_sample_drawdown,
                "oos_dd": r.out_of_sample_drawdown
            })
        
        return pd.DataFrame(data)
    
    def check_robustness(self, decay_threshold: float = 0.1) -> Dict:
        """Check if strategy is robust
        
        Args:
            decay_threshold: Max acceptable performance decay (in-sample - out-of-sample)
            
        Returns:
            Robustness assessment
        """
        summary = self.get_summary()
        
        decay = summary.get("optimization_decay", 0)
        is_robust = decay < decay_threshold
        
        return {
            "is_robust": is_robust,
            "optimization_decay": decay,
            "decay_threshold": decay_threshold,
            "in_sample_sharpe": summary.get("in_sample_avg_sharpe", 0),
            "out_of_sample_sharpe": summary.get("out_of_sample_avg_sharpe", 0),
            "issues": self._identify_issues(summary)
        }
    
    def _identify_issues(self, summary: Dict) -> List[str]:
        """Identify potential issues"""
        issues = []
        
        if summary.get("optimization_decay", 0) > 0.15:
            issues.append("High optimization decay - potential overfitting")
        
        if summary.get("out_of_sample_avg_sharpe", 0) < 0.5:
            issues.append("Low out-of-sample Sharpe ratio")
        
        if summary.get("out_of_sample_std_return", 0) > abs(summary.get("out_of_sample_avg_return", 1)):
            issues.append("High volatility relative to returns")
        
        return issues
