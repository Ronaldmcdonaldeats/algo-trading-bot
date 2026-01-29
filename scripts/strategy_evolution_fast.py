#!/usr/bin/env python3
"""
Fast 1000-generation strategy evolution engine.
Optimized for speed with 10 symbols, 10-day sampling.
"""

import sqlite3
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import json
from datetime import datetime

class FastStrategyEvolution:
    def __init__(self, db_path: str = 'data/real_market_data.db'):
        self.db_path = db_path
        self.start_cash = 100000
        self.commission_bps = 10  # 1.0 basis points
        
        # GA parameters
        self.population_size = 50
        self.generations = 1000
        self.elite_rate = 0.2
        self.mutation_rate = 0.15
        
        # Load data
        self._load_market_data()
    
    def _load_market_data(self):
        """Load first 10 symbols only for speed"""
        conn = sqlite3.connect(self.db_path)
        query = '''
            SELECT symbol, date, open, high, low, close, volume
            FROM daily_prices
            ORDER BY symbol, date
        '''
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Group by symbol and keep only first 10
        self.market_data = {}
        symbols = df['symbol'].unique()[:10]
        
        for symbol in symbols:
            symbol_df = df[df['symbol'] == symbol].copy()
            symbol_df['date'] = pd.to_datetime(symbol_df['date'])
            symbol_df = symbol_df.sort_values('date').reset_index(drop=True)
            self.market_data[symbol] = symbol_df
        
        print(f"Loaded data for {len(self.market_data)} symbols")
        min_date = min(self.market_data[s]['date'].min() for s in self.market_data)
        max_date = max(self.market_data[s]['date'].max() for s in self.market_data)
        print(f"Date range: {min_date.date()} to {max_date.date()}")
    
    def _extract_features(self, df: pd.DataFrame) -> Dict[str, float]:
        """Extract features - simplified for speed"""
        try:
            if df is None or len(df) < 20:
                return {}
            
            close = np.array(df['close'].tail(30).tolist(), dtype=float)
            if len(close) < 20:
                return {}
            
            # Momentum
            mom_5 = (close[-1] - close[-5]) / close[-5]
            mom_20 = (close[-1] - close[-20]) / close[-20]
            
            # Volatility
            returns = np.diff(close) / close[:-1]
            vol_5 = np.std(returns[-5:]) if len(returns) >= 5 else 0.01
            
            # RSI
            ups = sum([1 for i in range(1, min(15, len(close))) if close[-(i)] > close[-(i+1)]])
            rsi = 50 + (ups - 7) * 10
            
            # Volume
            vol_list = df['volume'].tail(20).tolist() if 'volume' in df.columns else [1]*20
            vol_ratio = vol_list[-1] / (np.mean(vol_list) + 1e-10)
            
            return {
                'momentum_5': float(mom_5),
                'momentum_20': float(mom_20),
                'volatility_5': float(vol_5),
                'rsi': float(rsi),
                'volume_ratio': float(vol_ratio),
            }
        except:
            return {}
    
    def _calculate_score(self, features: Dict, weights: Dict) -> float:
        """Calculate ML score"""
        if not features:
            return 0.0
        
        try:
            mom_score = (features['momentum_5'] * 0.6 + features['momentum_20'] * 0.4) / 0.05
            if np.isnan(mom_score) or np.isinf(mom_score):
                mom_score = 0
            mom_score = max(0, min(1, (mom_score + 1) / 2))
            
            rsi = features['rsi']
            rsi_signal = 0
            if rsi < 30:
                rsi_signal = (30 - rsi) / 30
            elif rsi > 70:
                rsi_signal = (rsi - 70) / 30
            
            w_mom = weights['momentum_weight']
            w_rsi = weights['rsi_weight']
            w_vol = 1 - w_mom - w_rsi
            
            vol_score = min(1, features['volume_ratio'] * 2)
            
            score = mom_score * w_mom + rsi_signal * w_rsi + vol_score * w_vol
            return max(0, min(1, score))
        except:
            return 0.0
    
    def backtest_strategy(self, params: Dict[str, float]) -> float:
        """Fast backtest using only 10 symbols and 10-day sampling"""
        try:
            cash = self.start_cash
            positions = {}
            entry_prices = {}
            total_pnl = 0
            trades = 0
            
            for symbol in list(self.market_data.keys())[:10]:
                df = self.market_data[symbol].copy()
                if len(df) < 25:
                    continue
                
                # Sample every 10 days
                for idx in range(25, len(df), 10):
                    hist_df = df.iloc[:idx]
                    features = self._extract_features(hist_df)
                    
                    if not features:
                        continue
                    
                    score = self._calculate_score(features, {
                        'momentum_weight': params['momentum_weight'],
                        'rsi_weight': params['rsi_weight'],
                    })
                    
                    price = float(hist_df['close'].iloc[-1])
                    
                    # Entry
                    if score > params['entry_threshold'] and symbol not in positions:
                        risk = self.start_cash * params['position_size_pct']
                        shares = int(risk / price * (0.5 + score))
                        max_shares = int(self.start_cash * params['max_position_pct'] / price)
                        shares = min(shares, max_shares)
                        
                        cost = shares * price * (1 + self.commission_bps / 10000)
                        
                        if cost <= cash and shares > 0:
                            cash -= cost
                            positions[symbol] = shares
                            entry_prices[symbol] = price
                            trades += 1
                    
                    # Exit
                    elif symbol in positions:
                        pnl_pct = (price - entry_prices[symbol]) / entry_prices[symbol]
                        
                        if (pnl_pct > params['profit_target'] or 
                            pnl_pct < -params['stop_loss'] or
                            score < (params['entry_threshold'] - 0.20)):
                            
                            revenue = positions[symbol] * price * (1 - self.commission_bps / 10000)
                            cost = positions[symbol] * entry_prices[symbol] * (1 + self.commission_bps / 10000)
                            pnl = revenue - cost
                            
                            total_pnl += pnl
                            cash += revenue
                            del positions[symbol]
                            del entry_prices[symbol]
            
            # Close remaining positions at final price
            final_equity = cash
            for symbol in positions:
                last_price = float(self.market_data[symbol]['close'].iloc[-1])
                final_equity += positions[symbol] * last_price
            
            final_return = (final_equity - self.start_cash) / self.start_cash
            
            # Fitness = return * trade quality
            trade_quality = 1.0 if trades > 0 else 0.1
            fitness = final_return * trade_quality
            
            return fitness
        except:
            return -0.5  # Bad fitness on error
    
    def create_individual(self) -> Dict[str, float]:
        """Create random individual"""
        return {
            'entry_threshold': np.random.uniform(0.40, 0.80),
            'profit_target': np.random.uniform(0.02, 0.15),
            'stop_loss': np.random.uniform(0.01, 0.10),
            'position_size_pct': np.random.uniform(0.005, 0.05),
            'max_position_pct': np.random.uniform(0.10, 0.50),
            'momentum_weight': np.random.uniform(0.2, 0.8),
            'rsi_weight': np.random.uniform(0.1, 0.6),
        }
    
    def mutate(self, individual: Dict) -> Dict:
        """Mutate individual"""
        mutant = individual.copy()
        
        ranges = {
            'entry_threshold': (0.40, 0.80),
            'profit_target': (0.02, 0.15),
            'stop_loss': (0.01, 0.10),
            'position_size_pct': (0.005, 0.05),
            'max_position_pct': (0.10, 0.50),
            'momentum_weight': (0.2, 0.8),
            'rsi_weight': (0.1, 0.6),
        }
        
        for param, (min_val, max_val) in ranges.items():
            if np.random.random() < self.mutation_rate:
                mutation = np.random.normal(0, (max_val - min_val) * 0.1)
                mutant[param] = np.clip(mutant[param] + mutation, min_val, max_val)
        
        return mutant
    
    def crossover(self, parent1: Dict, parent2: Dict) -> Dict:
        """Crossover two parents"""
        child = {}
        for param in parent1.keys():
            child[param] = parent1[param] if np.random.random() < 0.5 else parent2[param]
        return child
    
    def evolve(self) -> Tuple[List, Dict, float]:
        """Run 1000-generation evolution"""
        print("\n" + "="*80)
        print("FAST 1000-GENERATION STRATEGY EVOLUTION")
        print("="*80)
        print(f"Population: {self.population_size} | Elite Rate: {self.elite_rate}")
        print(f"Start Capital: ${self.start_cash:,}")
        print(f"Symbols: {len(self.market_data)} (first 10 only for speed)")
        print("="*80 + "\n")
        
        # Initialize population
        population = [self.create_individual() for _ in range(self.population_size)]
        
        best_overall = None
        best_fitness_overall = -1.0
        generation_results = []
        
        for gen in range(self.generations):
            # Evaluate fitness
            fitness_scores = []
            for individual in population:
                fitness = self.backtest_strategy(individual)
                fitness_scores.append(fitness)
            
            # Find best
            best_idx = np.argmax(fitness_scores)
            best_fitness = fitness_scores[best_idx]
            best_individual = population[best_idx]
            
            # Track overall best
            if best_fitness > best_fitness_overall:
                best_fitness_overall = best_fitness
                best_overall = best_individual.copy()
            
            # Elite selection
            elite_count = int(self.population_size * self.elite_rate)
            elite_indices = np.argsort(fitness_scores)[-elite_count:]
            elite_population = [population[i] for i in elite_indices]
            
            # Create new population
            new_population = elite_population.copy()
            while len(new_population) < self.population_size:
                if np.random.random() < 0.7:
                    # Crossover
                    parent1 = elite_population[np.random.randint(len(elite_population))]
                    parent2 = elite_population[np.random.randint(len(elite_population))]
                    child = self.crossover(parent1, parent2)
                    child = self.mutate(child)
                else:
                    # Random
                    child = self.create_individual()
                
                new_population.append(child)
            
            population = new_population[:self.population_size]
            
            # Save results
            gen_results = {
                'generation': gen + 1,
                'best_fitness': float(best_fitness),
                'best_params': json.dumps({k: float(v) for k, v in best_individual.items()}),
                'avg_fitness': float(np.mean(fitness_scores)),
                'equity': float(self.start_cash * (1 + best_fitness)),
                'timestamp': datetime.now().isoformat(),
            }
            generation_results.append(gen_results)
            
            # Print progress
            if (gen + 1) % 50 == 0:
                equity = self.start_cash * (1 + best_fitness_overall)
                print(f"Gen {gen+1:4d} | Best Fitness: {best_fitness_overall:+.6f} | Equity: ${equity:,.0f}")
        
        print("\n" + "="*80)
        print("EVOLUTION COMPLETE")
        print("="*80)
        
        # Final results
        final_equity = self.start_cash * (1 + best_fitness_overall)
        total_return = best_fitness_overall * 100
        
        print(f"\nBest Strategy Found:")
        print(f"  Total Return: {total_return:+.2f}%")
        print(f"  Final Equity: ${final_equity:,.2f}")
        print(f"  Profit/Loss: ${final_equity - self.start_cash:+,.2f}")
        
        print(f"\nBest Parameters:")
        for param, value in best_overall.items():
            print(f"  {param}: {value:.4f}")
        
        # Save results
        self._save_results(generation_results, best_overall, best_fitness_overall)
        
        return generation_results, best_overall, best_fitness_overall
    
    def _save_results(self, results: List, best_params: Dict, best_fitness: float):
        """Save evolution results to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS evolution_fast_1000gen (
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
                INSERT OR REPLACE INTO evolution_fast_1000gen 
                (generation, best_fitness, best_params, avg_fitness, equity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                result['generation'],
                result['best_fitness'],
                result['best_params'],
                result['avg_fitness'],
                result['equity'],
                result['timestamp']
            ))
        
        conn.commit()
        conn.close()
        
        print(f"\nResults saved to evolution_fast_1000gen table")

def main():
    evolution = FastStrategyEvolution()
    results, best_params, best_fitness = evolution.evolve()

if __name__ == '__main__':
    main()
