#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1000-GENERATION STRATEGY EVOLUTION ENGINE
Evolves trading parameters using genetic algorithm to maximize profits.
Each generation learns and improves from the previous generation.
"""

import sys
import os
from pathlib import Path
import sqlite3
import json
import random
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Tuple
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

class StrategyEvolution:
    """Genetic algorithm for strategy parameter evolution"""
    
    def __init__(self, db_path: str = "data/real_market_data.db"):
        self.db_path = db_path
        self.start_cash = 100_000.0
        self.commission_bps = 1.0
        self.slippage_bps = 0.5
        
        # Strategy parameters to evolve
        self.param_ranges = {
            'entry_threshold': (0.40, 0.80, 0.05),  # (min, max, step)
            'profit_target': (0.02, 0.15, 0.01),
            'stop_loss': (0.01, 0.10, 0.01),
            'position_size_pct': (0.005, 0.05, 0.005),
            'max_position_pct': (0.10, 0.50, 0.05),
            'volatility_threshold': (0.01, 0.10, 0.01),
            'momentum_weight': (0.2, 0.8, 0.1),
            'rsi_weight': (0.1, 0.6, 0.1),
        }
        
        self.population_size = 50
        self.generations = 1000
        self.elite_rate = 0.2
        self.mutation_rate = 0.15
        
        # Load data
        self._load_market_data()
    
    def _load_market_data(self):
        """Load all historical data from database"""
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT symbol, date, open, high, low, close, volume
            FROM daily_prices
            ORDER BY symbol, date
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Group by symbol
        self.market_data = {}
        for symbol in df['symbol'].unique():
            symbol_df = df[df['symbol'] == symbol].copy()
            symbol_df['date'] = pd.to_datetime(symbol_df['date'])
            symbol_df = symbol_df.sort_values('date').reset_index(drop=True)
            self.market_data[symbol] = symbol_df
        
        print(f"Loaded data for {len(self.market_data)} symbols")
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    
    def _extract_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Extract technical features from OHLCV data - simplified"""
        try:
            if df is None or len(df) < 20:
                return {}
            
            # Just use tail data directly without conversion
            close_list = df['close'].tail(30).tolist()
            if len(close_list) < 20:
                return {}
            
            close = np.array(close_list, dtype=np.float64)
            
            # Simple momentum
            momentum_5 = (close[-1] - close[-5]) / close[-5]
            momentum_20 = (close[-1] - close[-20]) / close[-20]
            
            # Simple volatility
            returns = np.diff(close) / close[:-1]
            volatility_5 = np.std(returns[-5:]) if len(returns) >= 5 else 0.01
            
            # Simple RSI
            diffs = np.diff(close)
            ups = np.sum([d for d in diffs[-14:] if d > 0]) if len(diffs) >= 14 else 0
            downs = np.sum([abs(d) for d in diffs[-14:] if d < 0]) if len(diffs) >= 14 else 0
            rs = (ups / 14) / (downs / 14 + 1e-10)
            rsi = 100 - (100 / (1 + rs))
            
            # Volume signal
            vol_list = df['volume'].tail(20).tolist() if 'volume' in df.columns else [1] * 20
            vol_ratio = vol_list[-1] / (np.mean(vol_list) + 1e-10) if len(vol_list) > 0 else 1.0
            
            return {
                'momentum_5': float(momentum_5),
                'momentum_20': float(momentum_20),
                'volatility_5': float(volatility_5),
                'rsi': float(rsi),
                'volume_ratio': float(vol_ratio),
            }
        except:
            return {}
    
    def _calculate_ml_score(self, features: Dict, weights: Dict) -> float:
        """Calculate ML score based on features and weights"""
        momentum_signal = (features['momentum_5'] * 0.6 + features['momentum_20'] * 0.4) / 0.05
        momentum_score = (momentum_signal + 1) / 2
        momentum_score = max(0, min(1, momentum_score))  # Clip to [0,1]
        
        rsi = features['rsi']
        rsi_signal = 0
        if rsi < 30:
            rsi_signal = (30 - rsi) / 30
        elif rsi > 70:
            rsi_signal = (rsi - 70) / 30
        
        volume_signal = features['volume_ratio'] * 2
        volume_signal = max(0, min(1, volume_signal))  # Clip to [0,1]
        
        w_mom = weights['momentum_weight']
        w_rsi = weights['rsi_weight']
        w_vol = 1 - w_mom - w_rsi
        
        score = momentum_score * w_mom + rsi_signal * w_rsi + volume_signal * w_vol
        score = max(0, min(1, score))  # Clip to [0,1]
        
        return score
    
    def backtest_strategy(self, params: Dict[str, float]) -> float:
        """Backtest strategy with given parameters and return profit"""
        cash = self.start_cash
        positions = {}
        entry_prices = {}
        total_pnl = 0
        trades = 0
        
        symbols = list(self.market_data.keys())[:30]  # Use first 30 symbols (faster)
        
        for symbol in symbols:
            df = self.market_data[symbol]
            
            # Sample every 5 trading days instead of every day (5x faster)
            sample_indices = range(20, len(df), 5)
            
            for idx in sample_indices:
                hist_df = df.iloc[:idx+1]
                features = self._extract_features(hist_df)
                
                if not features:
                    continue
                
                ml_score = self._calculate_ml_score(features, {
                    'momentum_weight': params['momentum_weight'],
                    'rsi_weight': params['rsi_weight'],
                })
                
                current_price = float(hist_df['close'].iloc[-1])
                
                # Entry logic
                if ml_score > params['entry_threshold'] and symbol not in positions:
                    risk_per_trade = self.start_cash * params['position_size_pct']
                    position_size = int((risk_per_trade / current_price) * (0.5 + ml_score))
                    max_position = int((self.start_cash * params['max_position_pct']) / current_price)
                    position_size = min(position_size, max_position)
                    
                    cost = position_size * current_price * (1 + self.commission_bps / 10000)
                    
                    if cost <= cash and position_size > 0:
                        cash -= cost
                        positions[symbol] = position_size
                        entry_prices[symbol] = current_price
                        trades += 1
                
                # Exit logic
                elif symbol in positions:
                    profit_loss_pct = (current_price - entry_prices[symbol]) / entry_prices[symbol]
                    
                    should_exit = (
                        ml_score < (params['entry_threshold'] - 0.15) or
                        profit_loss_pct > params['profit_target'] or
                        profit_loss_pct < -params['stop_loss']
                    )
                    
                    if should_exit:
                        revenue = positions[symbol] * current_price * (1 - self.commission_bps / 10000)
                        pnl = revenue - (positions[symbol] * entry_prices[symbol] * (1 + self.commission_bps / 10000))
                        cash += revenue
                        total_pnl += pnl
                        del positions[symbol]
                        del entry_prices[symbol]
        
        # Close remaining positions
        for symbol in list(positions.keys()):
            df = self.market_data[symbol]
            final_price = df['close'].iloc[-1]
            revenue = positions[symbol] * final_price * (1 - self.commission_bps / 10000)
            pnl = revenue - (positions[symbol] * entry_prices[symbol] * (1 + self.commission_bps / 10000))
            cash += revenue
            total_pnl += pnl
        
        # Calculate return
        final_equity = cash
        return_pct = (final_equity - self.start_cash) / self.start_cash
        
        # Fitness = return * trade_quality
        trade_quality = 1.0 if trades > 0 else 0.1
        fitness = return_pct * trade_quality
        
        return fitness
    
    def create_individual(self) -> Dict[str, float]:
        """Create random individual (strategy parameters)"""
        individual = {}
        for param, (min_val, max_val, _) in self.param_ranges.items():
            individual[param] = random.uniform(min_val, max_val)
        return individual
    
    def mutate(self, individual: Dict[str, float]) -> Dict[str, float]:
        """Mutate individual with some probability"""
        mutated = individual.copy()
        for param, (min_val, max_val, step) in self.param_ranges.items():
            if random.random() < self.mutation_rate:
                mutation = random.gauss(0, (max_val - min_val) * 0.1)
                mutated[param] = np.clip(mutated[param] + mutation, min_val, max_val)
        return mutated
    
    def crossover(self, parent1: Dict, parent2: Dict) -> Dict:
        """Crossover two parents to create offspring"""
        child = {}
        for param in self.param_ranges.keys():
            if random.random() < 0.5:
                child[param] = parent1[param]
            else:
                child[param] = parent2[param]
        return child
    
    def evolve(self):
        """Run 1000 generation evolution"""
        print("\n" + "="*80)
        print("1000-GENERATION STRATEGY EVOLUTION")
        print("="*80)
        print(f"Population: {self.population_size} | Elite Rate: {self.elite_rate}")
        print(f"Start Capital: ${self.start_cash:,.0f}")
        
        # Initialize population
        population = [self.create_individual() for _ in range(self.population_size)]
        
        best_overall = None
        best_fitness = float('-inf')
        generation_results = []
        
        for gen in range(self.generations):
            # Evaluate fitness
            fitness_scores = []
            for individual in population:
                fitness = self.backtest_strategy(individual)
                fitness_scores.append(fitness)
            
            # Track best
            gen_best_idx = np.argmax(fitness_scores)
            gen_best_fitness = fitness_scores[gen_best_idx]
            gen_best_individual = population[gen_best_idx]
            
            if gen_best_fitness > best_fitness:
                best_fitness = gen_best_fitness
                best_overall = gen_best_individual.copy()
            
            # Elite selection
            elite_count = int(len(population) * self.elite_rate)
            elite_indices = np.argsort(fitness_scores)[-elite_count:]
            elite = [population[i] for i in elite_indices]
            
            # Create new population
            new_population = elite.copy()
            
            while len(new_population) < self.population_size:
                if random.random() < 0.7:
                    parent1, parent2 = random.sample(elite, 2)
                    child = self.crossover(parent1, parent2)
                    child = self.mutate(child)
                else:
                    child = self.create_individual()
                
                new_population.append(child)
            
            population = new_population[:self.population_size]
            
            # Store results
            gen_results = {
                'generation': gen + 1,
                'best_fitness': gen_best_fitness,
                'best_params': gen_best_individual,
                'avg_fitness': float(np.mean(fitness_scores)),
                'max_fitness': gen_best_fitness,
                'equity': self.start_cash * (1 + gen_best_fitness),
            }
            generation_results.append(gen_results)
            
            # Print progress
            if (gen + 1) % 50 == 0:
                equity = self.start_cash * (1 + best_fitness)
                print(f"Gen {gen+1:4d} | Best Fitness: {best_fitness:+.6f} | Equity: ${equity:,.0f}")
        
        print("\n" + "="*80)
        print("EVOLUTION COMPLETE")
        print("="*80)
        
        # Final results
        final_equity = self.start_cash * (1 + best_fitness)
        total_return = best_fitness * 100
        
        print(f"\nBest Strategy Found:")
        print(f"  Total Return: {total_return:+.2f}%")
        print(f"  Final Equity: ${final_equity:,.2f}")
        print(f"  Profit/Loss: ${final_equity - self.start_cash:+,.2f}")
        
        print(f"\nBest Parameters:")
        for param, value in best_overall.items():
            print(f"  {param}: {value:.4f}")
        
        # Save results
        self._save_results(generation_results, best_overall, best_fitness)
        
        return generation_results, best_overall, best_fitness
    
    def _save_results(self, results: List, best_params: Dict, best_fitness: float):
        """Save evolution results to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evolution_1000gen (
                generation INTEGER PRIMARY KEY,
                best_fitness REAL,
                best_params TEXT,
                avg_fitness REAL,
                equity REAL,
                timestamp TEXT
            )
        ''')
        
        # Insert results
        for result in results:
            cursor.execute('''
                INSERT OR REPLACE INTO evolution_1000gen
                (generation, best_fitness, best_params, avg_fitness, equity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                result['generation'],
                result['best_fitness'],
                json.dumps(result['best_params']),
                result['avg_fitness'],
                result['equity'],
                datetime.now().isoformat(),
            ))
        
        conn.commit()
        conn.close()
        
        print(f"\nResults saved to evolution_1000gen table")


def main():
    """Run strategy evolution"""
    evolution = StrategyEvolution()
    results, best_params, best_fitness = evolution.evolve()


if __name__ == "__main__":
    main()
