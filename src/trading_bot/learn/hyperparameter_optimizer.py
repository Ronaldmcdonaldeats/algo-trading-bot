"""Hyperparameter Optimizer - Bayesian optimization for strategy parameters"""

from typing import Dict, List, Callable, Optional, Tuple
import numpy as np
import pandas as pd
from dataclasses import dataclass
from enum import Enum
import warnings

try:
    from skopt import gp_minimize, space
    SKOPT_AVAILABLE = True
except ImportError:
    SKOPT_AVAILABLE = False
    warnings.warn("scikit-optimize not installed. Using grid search only.")


class OptimizationObjective(Enum):
    """Optimization objective"""
    MAXIMIZE_SHARPE = "sharpe"
    MAXIMIZE_RETURN = "return"
    MINIMIZE_DRAWDOWN = "drawdown"
    MAXIMIZE_PROFIT_FACTOR = "profit_factor"


@dataclass
class OptimizationResult:
    """Optimization result"""
    best_params: Dict
    best_score: float
    objective: OptimizationObjective
    iterations: int
    convergence_history: List[float]
    parameter_history: List[Dict]


class HyperparameterOptimizer:
    """Optimize strategy hyperparameters"""
    
    def __init__(self, objective: OptimizationObjective = OptimizationObjective.MAXIMIZE_SHARPE):
        """
        Args:
            objective: What to optimize for
        """
        self.objective = objective
        self.results: List[OptimizationResult] = []
    
    def optimize_grid_search(self, 
                            strategy_func: Callable,
                            data: pd.DataFrame,
                            param_ranges: Dict,
                            evaluation_func: Callable) -> OptimizationResult:
        """Grid search optimization (exhaustive)
        
        Args:
            strategy_func: Function taking (data, params) -> results
            data: Input data
            param_ranges: Dict of {param_name: [values]}
            evaluation_func: Function taking (results) -> score
            
        Returns:
            OptimizationResult
        """
        best_score = -np.inf if "maximize" in self.objective.name else np.inf
        best_params = {}
        convergence = []
        param_history = []
        
        # Generate all combinations
        combinations = self._generate_combinations(param_ranges)
        
        for i, params in enumerate(combinations):
            try:
                results = strategy_func(data, params)
                score = evaluation_func(results)
                
                convergence.append(score)
                param_history.append(params.copy())
                
                # Update best
                if "maximize" in self.objective.name:
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                else:
                    if score < best_score:
                        best_score = score
                        best_params = params.copy()
                
            except Exception as e:
                print(f"Error evaluating params {params}: {e}")
                continue
        
        result = OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            objective=self.objective,
            iterations=len(convergence),
            convergence_history=convergence,
            parameter_history=param_history
        )
        
        self.results.append(result)
        return result
    
    def optimize_bayesian(self,
                         strategy_func: Callable,
                         data: pd.DataFrame,
                         param_space: Dict,
                         evaluation_func: Callable,
                         n_calls: int = 50,
                         random_state: int = 42) -> OptimizationResult:
        """Bayesian optimization using Gaussian processes
        
        Args:
            strategy_func: Function taking (data, params) -> results
            data: Input data
            param_space: Dict of {param_name: (min, max, step)} or categorical
            evaluation_func: Function taking (results) -> score
            n_calls: Number of iterations
            random_state: Random seed
            
        Returns:
            OptimizationResult
        """
        if not SKOPT_AVAILABLE:
            print("scikit-optimize not available. Falling back to grid search.")
            return self.optimize_grid_search(
                strategy_func, data, 
                {k: list(range(int(v[0]), int(v[1]), int(v[2])))
                 for k, v in param_space.items()},
                evaluation_func
            )
        
        # Build space
        sk_space = []
        param_names = []
        
        for name, spec in param_space.items():
            param_names.append(name)
            
            if isinstance(spec, tuple) and len(spec) == 3:
                # Continuous range (min, max, step)
                sk_space.append(space.Real(spec[0], spec[1]))
            elif isinstance(spec, (list, tuple)):
                # Categorical
                sk_space.append(space.Categorical(spec))
            else:
                raise ValueError(f"Invalid param spec for {name}: {spec}")
        
        convergence = []
        param_history = []
        
        def objective_function(values):
            """Objective function for optimization"""
            params = dict(zip(param_names, values))
            
            try:
                results = strategy_func(data, params)
                score = evaluation_func(results)
                convergence.append(score)
                param_history.append(params.copy())
                
                # Return negative if maximizing
                if "maximize" in self.objective.name:
                    return -score
                else:
                    return score
                    
            except Exception as e:
                print(f"Error: {e}")
                return np.inf
        
        # Run optimization
        result = gp_minimize(
            objective_function,
            sk_space,
            n_calls=n_calls,
            random_state=random_state,
            n_initial_points=10,
            acq_func="EI"
        )
        
        # Extract best result
        best_params = dict(zip(param_names, result.x))
        best_score = convergence[np.argmin(convergence)] if convergence else 0
        
        opt_result = OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            objective=self.objective,
            iterations=len(convergence),
            convergence_history=convergence,
            parameter_history=param_history
        )
        
        self.results.append(opt_result)
        return opt_result
    
    def optimize_random_search(self,
                              strategy_func: Callable,
                              data: pd.DataFrame,
                              param_ranges: Dict,
                              evaluation_func: Callable,
                              n_iterations: int = 100,
                              random_state: int = 42) -> OptimizationResult:
        """Random search optimization
        
        Args:
            strategy_func: Function taking (data, params) -> results
            data: Input data
            param_ranges: Dict of {param_name: (min, max, step)}
            evaluation_func: Function taking (results) -> score
            n_iterations: Number of random samples
            random_state: Random seed
            
        Returns:
            OptimizationResult
        """
        np.random.seed(random_state)
        
        best_score = -np.inf if "maximize" in self.objective.name else np.inf
        best_params = {}
        convergence = []
        param_history = []
        
        for i in range(n_iterations):
            # Generate random params
            params = {}
            for name, (min_val, max_val, step) in param_ranges.items():
                # Generate random integer in range
                n_steps = int((max_val - min_val) / step)
                rand_idx = np.random.randint(0, n_steps + 1)
                params[name] = min_val + rand_idx * step
            
            try:
                results = strategy_func(data, params)
                score = evaluation_func(results)
                
                convergence.append(score)
                param_history.append(params.copy())
                
                if "maximize" in self.objective.name:
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                else:
                    if score < best_score:
                        best_score = score
                        best_params = params.copy()
                        
            except Exception as e:
                print(f"Error: {e}")
                continue
        
        result = OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            objective=self.objective,
            iterations=len(convergence),
            convergence_history=convergence,
            parameter_history=param_history
        )
        
        self.results.append(result)
        return result
    
    def _generate_combinations(self, param_ranges: Dict) -> List[Dict]:
        """Generate all parameter combinations for grid search"""
        import itertools
        
        params = list(param_ranges.keys())
        values = [param_ranges[p] for p in params]
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(params, combo)))
        
        return combinations
    
    def get_sensitivity_analysis(self) -> Dict:
        """Analyze parameter sensitivity"""
        if not self.results:
            return {}
        
        result = self.results[-1]
        sensitivity = {}
        
        # Calculate impact of each parameter
        param_df = pd.DataFrame(result.parameter_history)
        scores = pd.Series(result.convergence_history)
        
        for col in param_df.columns:
            # Correlation between parameter and score
            corr = param_df[col].corr(scores)
            sensitivity[col] = {
                "correlation": corr,
                "importance": abs(corr)
            }
        
        # Sort by importance
        sorted_sens = sorted(
            sensitivity.items(),
            key=lambda x: x[1]["importance"],
            reverse=True
        )
        
        return dict(sorted_sens)
    
    def get_optimization_report(self, result: Optional[OptimizationResult] = None) -> Dict:
        """Get optimization report"""
        if result is None and self.results:
            result = self.results[-1]
        
        if result is None:
            return {}
        
        convergence = np.array(result.convergence_history)
        
        return {
            "best_params": result.best_params,
            "best_score": result.best_score,
            "objective": result.objective.value,
            "iterations": result.iterations,
            "mean_score": convergence.mean(),
            "std_score": convergence.std(),
            "improvement_pct": (
                (convergence[-1] - convergence[0]) / abs(convergence[0]) * 100
                if convergence[0] != 0 else 0
            ),
            "sensitivity": self.get_sensitivity_analysis()
        }


class ParameterTuner:
    """High-level parameter tuning interface"""
    
    def __init__(self, strategy_func: Callable, data: pd.DataFrame):
        """
        Args:
            strategy_func: Strategy function to optimize
            data: Training data
        """
        self.strategy_func = strategy_func
        self.data = data
        self.optimizer = None
        self.best_result = None
    
    def tune(self, param_ranges: Dict, 
            objective_func: Callable,
            method: str = "bayesian",
            **kwargs) -> Dict:
        """Tune parameters
        
        Args:
            param_ranges: Parameter ranges
            objective_func: Objective function
            method: "grid", "bayesian", or "random"
            **kwargs: Method-specific arguments
            
        Returns:
            Best parameters
        """
        # Determine objective
        if "sharpe" in objective_func.__name__.lower():
            objective = OptimizationObjective.MAXIMIZE_SHARPE
        elif "return" in objective_func.__name__.lower():
            objective = OptimizationObjective.MAXIMIZE_RETURN
        elif "drawdown" in objective_func.__name__.lower():
            objective = OptimizationObjective.MINIMIZE_DRAWDOWN
        else:
            objective = OptimizationObjective.MAXIMIZE_SHARPE
        
        self.optimizer = HyperparameterOptimizer(objective)
        
        if method == "grid":
            self.best_result = self.optimizer.optimize_grid_search(
                self.strategy_func,
                self.data,
                param_ranges,
                objective_func
            )
        elif method == "bayesian":
            self.best_result = self.optimizer.optimize_bayesian(
                self.strategy_func,
                self.data,
                param_ranges,
                objective_func,
                **kwargs
            )
        elif method == "random":
            self.best_result = self.optimizer.optimize_random_search(
                self.strategy_func,
                self.data,
                param_ranges,
                objective_func,
                **kwargs
            )
        else:
            raise ValueError(f"Unknown method: {method}")
        
        return self.best_result.best_params
