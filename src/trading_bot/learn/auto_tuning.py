"""Automatic Parameter Tuning System - Nightly optimization and daily updates

Features:
- Run parameter optimization nightly
- Track parameter drift over time
- Adaptive parameter updates based on recent performance
- Parameter stability analysis
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable
import json


@dataclass
class ParameterSet:
    """A set of parameters and their performance"""
    params: Dict[str, float]
    timestamp: datetime
    sharpe_ratio: float
    total_return: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    num_trades: int
    sample_size: int = 0  # trades used to compute metrics
    
    def score(self, weights: Dict[str, float] = None) -> float:
        """Calculate composite score for parameters"""
        if weights is None:
            weights = {
                'sharpe': 0.4,
                'return': 0.2,
                'max_dd': 0.15,
                'win_rate': 0.15,
                'profit_factor': 0.1,
            }
        
        # Normalize metrics to 0-1 range
        sharpe_score = min(1.0, max(0, self.sharpe_ratio / 2.0))  # 2.0+ = perfect
        return_score = min(1.0, max(0, self.total_return / 0.5))  # 50%+ = perfect
        dd_score = max(0, 1.0 + self.max_drawdown)  # Range 0-1 (0 = -100%, 1 = 0%)
        wr_score = self.win_rate  # Already 0-1
        pf_score = min(1.0, max(0, self.profit_factor / 2.5))  # 2.5+ = perfect
        
        composite = (
            weights['sharpe'] * sharpe_score +
            weights['return'] * return_score +
            weights['max_dd'] * dd_score +
            weights['win_rate'] * wr_score +
            weights['profit_factor'] * pf_score
        )
        
        return composite
    
    def to_dict(self) -> dict:
        return {
            'params': self.params,
            'timestamp': self.timestamp.isoformat(),
            'sharpe_ratio': self.sharpe_ratio,
            'total_return': self.total_return,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'num_trades': self.num_trades,
            'score': self.score(),
        }


@dataclass
class ParameterUpdate:
    """Record of a parameter update"""
    update_id: str
    timestamp: datetime
    old_params: Dict[str, float]
    new_params: Dict[str, float]
    reason: str  # "NIGHTLY_TUNE", "PERFORMANCE_DRIFT", "MANUAL"
    performance_change: float  # Change in composite score
    
    def to_dict(self) -> dict:
        return {
            'update_id': self.update_id,
            'timestamp': self.timestamp.isoformat(),
            'old_params': self.old_params,
            'new_params': self.new_params,
            'reason': self.reason,
            'performance_change': self.performance_change,
        }


class AutoTuningSystem:
    """Automatic parameter tuning and optimization"""
    
    def __init__(self, 
                 tune_schedule: str = "DAILY",  # DAILY, WEEKLY
                 stability_threshold: float = 0.05):  # 5% change = drift
        """
        Initialize auto-tuning system
        
        Args:
            tune_schedule: How often to run optimization
            stability_threshold: Acceptable parameter drift
        """
        self.tune_schedule = tune_schedule
        self.stability_threshold = stability_threshold
        
        # History
        self.parameter_history: List[ParameterSet] = []
        self.update_history: List[ParameterUpdate] = []
        self.current_params: Optional[ParameterSet] = None
        
        # Scheduling
        self.last_tune_time: Optional[datetime] = None
        self.next_tune_time: Optional[datetime] = None
    
    def record_performance(self, params: Dict[str, float],
                          sharpe: float, total_return: float,
                          max_dd: float, win_rate: float,
                          pf: float, num_trades: int) -> ParameterSet:
        """Record performance metrics for a parameter set"""
        param_set = ParameterSet(
            params=params,
            timestamp=datetime.now(),
            sharpe_ratio=sharpe,
            total_return=total_return,
            max_drawdown=max_dd,
            win_rate=win_rate,
            profit_factor=pf,
            num_trades=num_trades,
        )
        
        self.parameter_history.append(param_set)
        
        # Update current params if better
        if self.current_params is None or param_set.score() > self.current_params.score():
            self.current_params = param_set
        
        return param_set
    
    def should_tune(self) -> bool:
        """Check if optimization should run"""
        if self.last_tune_time is None:
            return True  # First time
        
        if self.tune_schedule == "DAILY":
            # Run if last tune was > 24 hours ago
            return datetime.now() - self.last_tune_time > timedelta(hours=24)
        elif self.tune_schedule == "WEEKLY":
            # Run if last tune was > 7 days ago
            return datetime.now() - self.last_tune_time > timedelta(days=7)
        
        return False
    
    def detect_parameter_drift(self) -> Optional[Tuple[str, float]]:
        """
        Detect if parameters have drifted significantly
        
        Returns:
            (parameter_name, drift_pct) or None if no drift
        """
        if len(self.parameter_history) < 2:
            return None
        
        recent_params = self.parameter_history[-1].params
        older_params = self.parameter_history[-10].params if len(self.parameter_history) >= 10 else self.parameter_history[0].params
        
        # Find most significant drift
        max_drift = 0
        drifted_param = None
        
        for param_name in recent_params:
            if param_name not in older_params:
                continue
            
            old_val = older_params[param_name]
            new_val = recent_params[param_name]
            
            # Calculate percentage change
            if old_val != 0:
                drift = abs(new_val - old_val) / abs(old_val)
                if drift > max_drift:
                    max_drift = drift
                    drifted_param = param_name
        
        if max_drift > self.stability_threshold:
            return drifted_param, max_drift
        
        return None
    
    def optimize_parameters(self,
                          optimization_func: Callable,
                          param_ranges: Dict[str, Tuple[float, float]],
                          num_evaluations: int = 20) -> ParameterSet:
        """
        Run parameter optimization
        
        Args:
            optimization_func: Function that takes params dict and returns metrics
            param_ranges: Dict of {param_name: (min, max)}
            num_evaluations: Number of parameter combinations to test
        
        Returns:
            Best ParameterSet found
        """
        import random
        
        best_result = None
        best_score = -float('inf')
        
        for i in range(num_evaluations):
            # Generate random parameter set
            test_params = {}
            for param_name, (min_val, max_val) in param_ranges.items():
                test_params[param_name] = random.uniform(min_val, max_val)
            
            # Evaluate
            metrics = optimization_func(test_params)
            
            param_set = ParameterSet(
                params=test_params,
                timestamp=datetime.now(),
                sharpe_ratio=metrics.get('sharpe', 0),
                total_return=metrics.get('return', 0),
                max_drawdown=metrics.get('max_dd', -1),
                win_rate=metrics.get('win_rate', 0),
                profit_factor=metrics.get('pf', 1),
                num_trades=metrics.get('num_trades', 0),
            )
            
            score = param_set.score()
            if score > best_score:
                best_score = score
                best_result = param_set
        
        if best_result:
            self.parameter_history.append(best_result)
            self.last_tune_time = datetime.now()
            
            # Calculate improvement
            old_score = self.current_params.score() if self.current_params else 0
            improvement = best_result.score() - old_score
            
            # Record update if significant improvement
            if improvement > 0.05:
                update = ParameterUpdate(
                    update_id=f"UPDATE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now(),
                    old_params=self.current_params.params if self.current_params else {},
                    new_params=best_result.params,
                    reason="NIGHTLY_TUNE",
                    performance_change=improvement,
                )
                self.update_history.append(update)
        
        return best_result
    
    def get_current_params(self) -> Optional[Dict[str, float]]:
        """Get current best parameters"""
        return self.current_params.params if self.current_params else None
    
    def update_parameters(self, new_params: Dict[str, float],
                         reason: str = "MANUAL") -> ParameterUpdate:
        """Manually update parameters"""
        old_params = self.current_params.params if self.current_params else {}
        old_score = self.current_params.score() if self.current_params else 0
        
        # Create placeholder ParameterSet for new params
        new_param_set = ParameterSet(
            params=new_params,
            timestamp=datetime.now(),
            sharpe_ratio=0,  # Unknown until evaluated
            total_return=0,
            max_drawdown=0,
            win_rate=0,
            profit_factor=1,
            num_trades=0,
        )
        
        update = ParameterUpdate(
            update_id=f"UPDATE_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now(),
            old_params=old_params,
            new_params=new_params,
            reason=reason,
            performance_change=0,  # Unknown until evaluated
        )
        
        self.update_history.append(update)
        self.current_params = new_param_set
        
        return update
    
    def get_parameter_stability(self) -> Dict:
        """Analyze parameter stability over time"""
        if len(self.parameter_history) < 2:
            return {}
        
        recent = self.parameter_history[-5:] if len(self.parameter_history) >= 5 else self.parameter_history
        older = self.parameter_history[:5] if len(self.parameter_history) >= 5 else self.parameter_history
        
        stability = {}
        
        for param_name in recent[0].params:
            recent_vals = [p.params.get(param_name, 0) for p in recent]
            older_vals = [p.params.get(param_name, 0) for p in older]
            
            recent_avg = sum(recent_vals) / len(recent_vals)
            older_avg = sum(older_vals) / len(older_vals)
            
            drift = abs(recent_avg - older_avg) / abs(older_avg) if older_avg != 0 else 0
            
            stability[param_name] = {
                'recent_avg': recent_avg,
                'older_avg': older_avg,
                'drift_pct': drift,
                'stable': drift < self.stability_threshold,
            }
        
        return stability
    
    def get_update_history(self, limit: int = 10) -> List[Dict]:
        """Get recent parameter updates"""
        return [u.to_dict() for u in self.update_history[-limit:]]
    
    def get_performance_history(self, limit: int = 50) -> List[Dict]:
        """Get recent parameter performance"""
        return [p.to_dict() for p in self.parameter_history[-limit:]]
    
    def export_tuning_log(self, filepath: str = "tuning_log.json"):
        """Export tuning history to JSON"""
        data = {
            'export_date': datetime.now().isoformat(),
            'current_params': self.current_params.to_dict() if self.current_params else None,
            'update_history': self.get_update_history(),
            'performance_history': self.get_performance_history(),
            'parameter_stability': self.get_parameter_stability(),
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        return filepath
    
    def schedule_next_tune(self):
        """Schedule next tuning time"""
        if self.tune_schedule == "DAILY":
            self.next_tune_time = datetime.now() + timedelta(hours=24)
        elif self.tune_schedule == "WEEKLY":
            self.next_tune_time = datetime.now() + timedelta(days=7)


class NightlyOptimizer:
    """Run nightly parameter optimization"""
    
    def __init__(self, auto_tuner: AutoTuningSystem):
        self.auto_tuner = auto_tuner
    
    def run_nightly(self, 
                   optimization_func: Callable,
                   param_ranges: Dict[str, Tuple[float, float]],
                   run_time: str = "22:00"):  # 10 PM
        """
        Schedule nightly optimization
        
        Args:
            optimization_func: Function for parameter evaluation
            param_ranges: Parameter search space
            run_time: Time to run optimization (HH:MM format)
        """
        import time
        from datetime import datetime
        
        while True:
            now = datetime.now()
            target_time = datetime.strptime(run_time, "%H:%M").time()
            current_time = now.time()
            
            # Check if it's time to run
            if current_time.hour == target_time.hour and current_time.minute >= target_time.minute:
                # Run optimization
                best = self.auto_tuner.optimize_parameters(
                    optimization_func,
                    param_ranges,
                    num_evaluations=30
                )
                
                print(f"✓ Nightly optimization complete: {best.score():.3f} score")
                self.auto_tuner.schedule_next_tune()
                
                # Wait until tomorrow
                time.sleep(3600)  # 1 hour
            
            # Check every 30 seconds
            time.sleep(30)
