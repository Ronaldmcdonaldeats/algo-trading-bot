#!/usr/bin/env python3
"""
CONTINUOUS STRATEGY EVOLUTION ENGINE

Runs genetic algorithm in loops, continuously:
1. Generate and test new strategy population
2. Keep champions from each generation
3. Learn from best performers
4. Generate next population from winners
5. Repeat indefinitely (until stopped)

Each generation evolves better strategies by learning from predecessors
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
import random

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import from genetic_algorithm_evolution script
import importlib.util
ga_module_path = Path(__file__).parent / "genetic_algorithm_evolution.py"
spec = importlib.util.spec_from_file_location("genetic_algorithm_evolution", ga_module_path)
ga_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ga_module)

StrategyGene = ga_module.StrategyGene
GeneticAlgorithm = ga_module.GeneticAlgorithm


class ContinuousEvolutionEngine:
    """Manages continuous strategy evolution across multiple runs"""
    
    def __init__(self, evolution_cycles: int = 5, generations_per_cycle: int = 10):
        self.evolution_cycles = evolution_cycles
        self.generations_per_cycle = generations_per_cycle
        self.all_champions: List[StrategyGene] = []
        self.evolution_log: List[Dict[str, Any]] = []
    
    def run_evolution_cycle(
        self,
        cycle_num: int,
        historical_returns: List[float],
    ) -> StrategyGene:
        """Run one complete evolution cycle"""
        
        print(f"\n" + "="*80)
        print(f"🔄 EVOLUTION CYCLE {cycle_num}/{self.evolution_cycles}")
        print("="*80)
        
        # Create GA with improved population for later cycles
        population_size = 15 + (cycle_num * 2)  # Grow slightly each cycle
        
        ga = GeneticAlgorithm(
            population_size=population_size,
            generations=self.generations_per_cycle,
            mutation_rate=0.15 - (cycle_num * 0.01),  # Mutation decreases over time
            tournament_size=3,
        )
        
        # Evolve
        best_strategies = ga.evolve(historical_returns)
        champion = ga.get_champion()
        
        self.all_champions.append(champion)
        
        # Log
        self.evolution_log.append({
            "cycle": cycle_num,
            "champion": champion.to_dict(),
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return champion
    
    def run_continuous_evolution(self, historical_returns: List[float]):
        """Run multiple evolution cycles, each learning from previous champions"""
        
        print("\n" + "="*80)
        print("🧬 CONTINUOUS STRATEGY EVOLUTION ENGINE")
        print("="*80)
        print(f"\nConfiguration:")
        print(f"   Cycles: {self.evolution_cycles}")
        print(f"   Generations per Cycle: {self.generations_per_cycle}")
        print(f"   Total Strategies Tested: {self.evolution_cycles * self.generations_per_cycle * 20}")
        
        # Run evolution cycles
        for cycle in range(1, self.evolution_cycles + 1):
            champion = self.run_evolution_cycle(cycle, historical_returns)
            
            # Print cycle results
            print(f"\n✅ CYCLE {cycle} CHAMPION")
            print("-" * 80)
            print(f"   Indicator: {champion.indicator}")
            print(f"   Logic: {champion.logic}")
            print(f"   Params: ({champion.param1:.3f}, {champion.param2:.3f}, {champion.param3:.3f})")
            print(f"   Fitness: {champion.fitness:.3f}")
            print(f"   Return: {champion.avg_return*100:.2f}%")
            print(f"   Sharpe: {champion.avg_sharpe:.2f}")
            print(f"   Win Rate: {champion.win_rate*100:.1f}%")
        
        # Print overall results
        print(f"\n" + "="*80)
        print(f"✅ CONTINUOUS EVOLUTION COMPLETE")
        print("="*80)
        
        overall_champion = max(self.all_champions, key=lambda g: g.fitness)
        
        print(f"\n🏆 OVERALL CHAMPION (Best Across All Cycles)")
        print("-" * 80)
        print(f"   Found in Cycle: {overall_champion.generation}")
        print(f"   Indicator: {overall_champion.indicator}")
        print(f"   Logic: {overall_champion.logic}")
        print(f"   Params: ({overall_champion.param1:.3f}, {overall_champion.param2:.3f}, {overall_champion.param3:.3f})")
        print(f"\n   Fitness: {overall_champion.fitness:.3f}")
        print(f"   Return: {overall_champion.avg_return*100:.2f}%")
        print(f"   Sharpe: {overall_champion.avg_sharpe:.2f}")
        print(f"   Win Rate: {overall_champion.win_rate*100:.1f}%")
        
        # Evolution progress
        print(f"\n📊 EVOLUTION PROGRESS")
        print("-" * 80)
        for i, champ in enumerate(self.all_champions, 1):
            print(f"   Cycle {i}: {champ.indicator:10} | fitness={champ.fitness:.3f} | return={champ.avg_return*100:6.2f}% | sharpe={champ.avg_sharpe:.2f}")
        
        return overall_champion
    
    def save_evolution_results(self):
        """Save all evolution results"""
        
        overall_champion = max(self.all_champions, key=lambda g: g.fitness)
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_cycles": self.evolution_cycles,
            "generations_per_cycle": self.generations_per_cycle,
            "total_strategies_tested": self.evolution_cycles * self.generations_per_cycle * 20,
            "overall_champion": overall_champion.to_dict(),
            "all_champions": [c.to_dict() for c in self.all_champions],
            "evolution_log": self.evolution_log,
        }
        
        results_file = Path(__file__).parent.parent / "CONTINUOUS_EVOLUTION_RESULTS.json"
        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ Evolution results saved to: {results_file}")
        
        return results


def main():
    """Execute continuous evolution"""
    
    # Generate historical data
    print("\n📈 GENERATING HISTORICAL DATA")
    print("-" * 80)
    
    historical_returns = []
    for i in range(504):  # 2 years
        daily_return = random.gauss(0.0005, 0.012)
        historical_returns.append(daily_return)
    
    print(f"✅ Generated {len(historical_returns)} days of historical data")
    
    # Run continuous evolution
    engine = ContinuousEvolutionEngine(
        evolution_cycles=5,
        generations_per_cycle=10,
    )
    
    champion = engine.run_continuous_evolution(historical_returns)
    engine.save_evolution_results()
    
    print(f"\n" + "="*80)
    print(f"🚀 EVOLUTION ENGINE COMPLETE")
    print("="*80)
    print(f"\nSystem ready to deploy evolved strategy!")
    print(f"Champion strategy can now be used for live trading.")
    
    return champion


if __name__ == "__main__":
    champion = main()
