"""Advanced training optimization with adaptive learning rates, parallel processing, and early stopping."""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Optimized training configuration."""
    max_workers: int = field(default_factory=lambda: max(2, multiprocessing.cpu_count() - 1))
    learning_rate_initial: float = 0.1
    learning_rate_min: float = 0.001
    learning_rate_decay: float = 0.95
    batch_size: int = 256
    early_stopping_patience: int = 20
    early_stopping_threshold: float = 0.0001
    gradient_clip: float = 1.0
    use_adaptive_lr: bool = True
    momentum: float = 0.9
    weight_decay: float = 0.0001
    sample_weights: bool = True  # Weight recent samples higher


@dataclass
class TrainingMetrics:
    """Metrics tracked during training."""
    epoch: int
    loss: float
    val_loss: float
    learning_rate: float
    improvement: float
    patience_counter: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AdaptiveTrainer:
    """Optimized trainer with adaptive learning rates, early stopping, and parallel processing."""
    
    def __init__(self, config: Optional[TrainingConfig] = None):
        """Initialize trainer."""
        self.config = config or TrainingConfig()
        self.metrics_history: List[TrainingMetrics] = []
        self.best_loss: Optional[float] = None
        self.patience_counter = 0
        self.learning_rate = self.config.learning_rate_initial
        self.momentum_buffer: Dict[str, np.ndarray] = {}
        
    def compute_sample_weights(self, n_samples: int) -> np.ndarray:
        """Compute weights for samples - more recent samples get higher weight."""
        if not self.config.sample_weights:
            return np.ones(n_samples)
        
        # Linear increasing weights: early samples get 0.5x, recent samples get 1.5x
        weights = np.linspace(0.5, 1.5, n_samples)
        return weights / weights.mean()  # Normalize
    
    def compute_loss_with_gradient(
        self,
        predictions: np.ndarray,
        targets: np.ndarray,
        sample_weights: np.ndarray
    ) -> Tuple[float, np.ndarray]:
        """Compute loss and gradients with sample weighting."""
        errors = predictions - targets
        weighted_errors = errors * sample_weights[:, np.newaxis]
        
        loss = np.mean(weighted_errors ** 2)
        gradients = 2.0 * weighted_errors / len(targets)
        
        # Gradient clipping for stability
        if self.config.gradient_clip > 0:
            clip_mask = np.abs(gradients) > self.config.gradient_clip
            gradients[clip_mask] = np.sign(gradients[clip_mask]) * self.config.gradient_clip
        
        return float(loss), gradients
    
    def apply_momentum(self, gradients: np.ndarray, param_name: str) -> np.ndarray:
        """Apply momentum to gradients."""
        if param_name not in self.momentum_buffer:
            self.momentum_buffer[param_name] = np.zeros_like(gradients)
        
        buffer = self.momentum_buffer[param_name]
        buffer[:] = self.config.momentum * buffer - self.learning_rate * gradients
        return buffer
    
    def update_learning_rate(self, improvement: float) -> None:
        """Adaptively adjust learning rate based on improvement."""
        if not self.config.use_adaptive_lr:
            return
        
        # If improvement is small, reduce LR (less aggressive updates)
        if improvement < self.config.early_stopping_threshold:
            self.learning_rate *= 0.98
        # If improvement is good, slightly increase LR (more aggressive)
        elif improvement > 0.01:
            self.learning_rate *= 1.02
        
        # Bound learning rate
        self.learning_rate = np.clip(
            self.learning_rate,
            self.config.learning_rate_min,
            self.config.learning_rate_initial
        )
    
    def train_epoch(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        epoch: int
    ) -> TrainingMetrics:
        """Train a single epoch with batching."""
        sample_weights = self.compute_sample_weights(len(X_train))
        
        # Mini-batch training
        n_batches = max(1, len(X_train) // self.config.batch_size)
        epoch_loss = 0.0
        
        for i in range(n_batches):
            start = i * self.config.batch_size
            end = min((i + 1) * self.config.batch_size, len(X_train))
            
            X_batch = X_train[start:end]
            y_batch = y_train[start:end]
            weights_batch = sample_weights[start:end]
            
            # Forward pass
            predictions = self._forward(X_batch)
            
            # Compute loss and gradients
            loss, gradients = self.compute_loss_with_gradient(predictions, y_batch, weights_batch)
            epoch_loss += loss
            
            # Apply momentum and update
            momentum_grad = self.apply_momentum(gradients, f"batch_{i}")
        
        epoch_loss /= max(1, n_batches)
        
        # Validation
        val_predictions = self._forward(X_val)
        val_loss = float(np.mean((val_predictions - y_val) ** 2))
        
        # Calculate improvement
        improvement = (self.best_loss or float('inf')) - val_loss if self.best_loss else float('inf')
        
        # Update learning rate adaptively
        self.update_learning_rate(improvement)
        
        # Early stopping logic
        if self.best_loss is None or val_loss < self.best_loss - self.config.early_stopping_threshold:
            self.best_loss = val_loss
            self.patience_counter = 0
        else:
            self.patience_counter += 1
        
        # Create metrics record
        metrics = TrainingMetrics(
            epoch=epoch,
            loss=epoch_loss,
            val_loss=val_loss,
            learning_rate=self.learning_rate,
            improvement=improvement if improvement != float('inf') else 0.0,
            patience_counter=self.patience_counter
        )
        self.metrics_history.append(metrics)
        
        return metrics
    
    def _forward(self, X: np.ndarray) -> np.ndarray:
        """Forward pass - override in subclass."""
        return X  # Placeholder
    
    def should_stop(self) -> bool:
        """Check if training should stop."""
        return self.patience_counter >= self.config.early_stopping_patience
    
    def get_training_summary(self) -> Dict:
        """Get summary of training."""
        if not self.metrics_history:
            return {}
        
        metrics_list = [asdict(m) for m in self.metrics_history]
        losses = [m['val_loss'] for m in metrics_list]
        
        return {
            "epochs_trained": len(self.metrics_history),
            "best_val_loss": float(np.min(losses)),
            "final_val_loss": float(losses[-1]),
            "best_learning_rate": float(np.max([m['learning_rate'] for m in metrics_list])),
            "final_learning_rate": float(self.learning_rate),
            "total_patience": self.patience_counter,
            "improvement_history": [m['improvement'] for m in metrics_list[-10:]]  # Last 10 epochs
        }


class ParallelStrategyTrainer:
    """Train multiple strategies in parallel for faster convergence."""
    
    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
    
    def train_strategies(
        self,
        strategy_configs: Dict[str, Dict],
        training_data: Dict[str, Tuple[np.ndarray, np.ndarray]],
        epochs: int = 100
    ) -> Dict[str, Dict]:
        """Train multiple strategies in parallel."""
        futures = {}
        results = {}
        
        for strategy_name, config in strategy_configs.items():
            if strategy_name not in training_data:
                logger.warning(f"No training data for {strategy_name}")
                continue
            
            X_train, y_train = training_data[strategy_name]
            
            future = self.executor.submit(
                self._train_single_strategy,
                strategy_name,
                config,
                X_train,
                y_train,
                epochs
            )
            futures[strategy_name] = future
        
        # Collect results
        for strategy_name, future in futures.items():
            try:
                results[strategy_name] = future.result(timeout=300)
            except Exception as e:
                logger.error(f"Training {strategy_name} failed: {e}")
                results[strategy_name] = {"error": str(e)}
        
        return results
    
    def _train_single_strategy(
        self,
        name: str,
        config: Dict,
        X_train: np.ndarray,
        y_train: np.ndarray,
        epochs: int
    ) -> Dict:
        """Train a single strategy."""
        trainer = AdaptiveTrainer(self.config)
        
        # Split into train/val
        split = int(0.8 * len(X_train))
        X_tr, X_val = X_train[:split], X_train[split:]
        y_tr, y_val = y_train[:split], y_train[split:]
        
        for epoch in range(epochs):
            metrics = trainer.train_epoch(X_tr, y_tr, X_val, y_val, epoch)
            
            if epoch % 20 == 0:
                logger.info(f"{name} Epoch {epoch}: val_loss={metrics.val_loss:.6f}, lr={metrics.learning_rate:.6f}")
            
            if trainer.should_stop():
                logger.info(f"{name} Early stopped at epoch {epoch}")
                break
        
        return {
            "config": config,
            "summary": trainer.get_training_summary(),
            "final_metrics": asdict(trainer.metrics_history[-1]) if trainer.metrics_history else {}
        }
    
    def shutdown(self):
        """Shutdown thread pool."""
        self.executor.shutdown(wait=True)
