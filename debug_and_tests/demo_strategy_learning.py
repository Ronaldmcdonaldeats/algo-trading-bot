#!/usr/bin/env python
"""
Comprehensive demo of the AI-powered strategy learning system.

This demonstrates:
1. Learning from multiple trading strategies
2. Combining learned strategies into hybrid strategies
3. Building new strategies from learned patterns
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from trading_bot.learn.strategy_learner import StrategyLearner
from trading_bot.data.performance_tracker import PerformanceTracker
from trading_bot.data.ml_predictor import MLPredictor
from trading_bot.data.portfolio_optimizer import PortfolioOptimizer
from trading_bot.data.risk_manager import RiskManager
import json


def demo_basic_learning():
    """Demo 1: Learn from different strategies."""
    print("\n" + "="*80)
    print("DEMO 1: LEARNING FROM MULTIPLE TRADING STRATEGIES")
    print("="*80)
    
    learner = StrategyLearner()
    
    # Simulate three different strategies
    strategies = [
        {
            'name': 'mean_reversion_rsi',
            'backtest_results': {
                'sharpe_ratio': 1.5,
                'max_drawdown': -0.08,
                'win_rate': 0.55,
                'profit_factor': 1.8,
                'total_return': 0.25,
                'num_trades': 50,
            },
            'params': {'rsi_threshold': 30, 'lookback': 14},
        },
        {
            'name': 'macd_volume_momentum',
            'backtest_results': {
                'sharpe_ratio': 1.2,
                'max_drawdown': -0.12,
                'win_rate': 0.60,
                'profit_factor': 1.5,
                'total_return': 0.20,
                'num_trades': 45,
            },
            'params': {'fast_period': 12, 'slow_period': 26},
        },
        {
            'name': 'atr_breakout',
            'backtest_results': {
                'sharpe_ratio': 1.8,
                'max_drawdown': -0.06,
                'win_rate': 0.52,
                'profit_factor': 2.1,
                'total_return': 0.30,
                'num_trades': 60,
            },
            'params': {'atr_period': 14, 'breakout_level': 2.0},
        },
    ]
    
    print("\n🔍 Learning from 3 trading strategies...")
    learned_params = {}
    
    for strat in strategies:
        params = learner.learn_from_backtest(
            strat['name'],
            strat['params'],
            strat['backtest_results']
        )
        learned_params[strat['name']] = params
        
        print(f"\n✓ {strat['name']}:")
        print(f"  Sharpe Ratio:  {params.performance['sharpe_ratio']:.2f}")
        print(f"  Win Rate:      {params.performance['win_rate']:.1%}")
        print(f"  Profit Factor: {params.performance['profit_factor']:.2f}")
        print(f"  Confidence:    {params.confidence:.1%} ({params.samples} trades)")
    
    # Show top strategies
    print("\n📊 TOP STRATEGIES BY SHARPE RATIO:")
    top_strategies = learner.get_top_strategies(top_n=3, metric='sharpe_ratio')
    for i, strat in enumerate(top_strategies, 1):
        print(f"  {i}. {strat.name:30} Sharpe={strat.performance['sharpe_ratio']:.2f}")
    
    return learner, learned_params


def demo_hybrid_building(learner, learned_params):
    """Demo 2: Build hybrid strategies from learned ones."""
    print("\n" + "="*80)
    print("DEMO 2: BUILDING HYBRID STRATEGIES")
    print("="*80)
    
    strategy_names = list(learned_params.keys())
    
    # Create hybrid strategy 1: Combine all three
    print("\n🤖 Creating Hybrid 1: All-in-one strategy (equal weighted)...")
    hybrid1 = learner.build_hybrid_strategy(
        'hybrid_all_strategies',
        [f"{name}_learned" for name in strategy_names],
        learner.learned_strategies,
        weight_by='sharpe_ratio'
    )
    
    if hybrid1:
        print(f"  ✓ {hybrid1.name}")
        print(f"    Base Strategies: {', '.join(hybrid1.base_strategies)}")
        print(f"    Weights:")
        for strat, weight in sorted(hybrid1.weights.items(), key=lambda x: x[1], reverse=True):
            print(f"      - {strat.split('_')[0]:25} {weight:.1%}")
        print(f"    Expected Metrics:")
        print(f"      - Sharpe:       {hybrid1.expected_metrics.get('sharpe_ratio', 0):.2f}")
        print(f"      - Win Rate:     {hybrid1.expected_metrics.get('win_rate', 0):.1%}")
        print(f"      - Profit Factor: {hybrid1.expected_metrics.get('profit_factor', 0):.2f}")
    
    # Create hybrid strategy 2: Combine best performers
    print("\n🤖 Creating Hybrid 2: Best performers combo...")
    top_strats = learner.get_top_strategies(top_n=2, metric='sharpe_ratio')
    top_strat_names = [s.name for s in top_strats]
    
    hybrid2 = learner.build_hybrid_strategy(
        'hybrid_best_performers',
        top_strat_names,
        learner.learned_strategies,
        weight_by='profit_factor'
    )
    
    if hybrid2:
        print(f"  ✓ {hybrid2.name}")
        print(f"    Combining: {', '.join([n.split('_')[0] for n in top_strat_names])}")
        print(f"    Weights by Profit Factor:")
        for strat, weight in sorted(hybrid2.weights.items(), key=lambda x: x[1], reverse=True):
            print(f"      - {strat.split('_')[0]:25} {weight:.1%}")


def demo_learning_from_trades(learner):
    """Demo 3: Learn from actual trade history."""
    print("\n" + "="*80)
    print("DEMO 3: LEARNING FROM ACTUAL TRADING PERFORMANCE")
    print("="*80)
    
    # Simulate trade history
    recent_trades = [
        {'entry_price': 100.0, 'exit_price': 103.0},  # +3%
        {'entry_price': 103.0, 'exit_price': 101.0},  # -1.9%
        {'entry_price': 101.0, 'exit_price': 105.0},  # +3.96%
        {'entry_price': 105.0, 'exit_price': 103.0},  # -1.9%
        {'entry_price': 103.0, 'exit_price': 108.0},  # +4.85%
        {'entry_price': 108.0, 'exit_price': 107.0},  # -0.92%
        {'entry_price': 107.0, 'exit_price': 112.0},  # +4.67%
        {'entry_price': 112.0, 'exit_price': 110.0},  # -1.78%
    ]
    
    print(f"\n📈 Learning from {len(recent_trades)} recent trades...")
    
    initial_params = {
        'entry_threshold': 2.0,
        'stop_loss_pct': 2.0,
        'take_profit_pct': 3.0,
    }
    
    learned = learner.learn_from_performance_history(
        'live_trading_optimized',
        recent_trades,
        initial_params
    )
    
    if learned:
        # Calculate win/loss stats
        wins = sum(1 for t in recent_trades if t['exit_price'] > t['entry_price'])
        losses = len(recent_trades) - wins
        
        print(f"\n  Trade Statistics:")
        print(f"    - Total Trades:  {len(recent_trades)}")
        print(f"    - Winning:       {wins} ({wins/len(recent_trades):.1%})")
        print(f"    - Losing:        {losses} ({losses/len(recent_trades):.1%})")
        
        print(f"\n  ✓ Learned Optimized Parameters:")
        print(f"    Suggested Adjustments:")
        for param, value in learned.parameters.items():
            original = initial_params.get(param, value)
            change = (value - original) / original * 100
            print(f"      - {param:25} {original:6.2f} → {value:6.2f} ({change:+.1f}%)")


def demo_ml_prediction(learner):
    """Demo 4: ML-based winner prediction."""
    print("\n" + "="*80)
    print("DEMO 4: ML-BASED STOCK WINNER PREDICTION")
    print("="*80)
    
    print("\n🧠 Training ML model on strategy performance history...")
    
    predictor = MLPredictor()
    
    # Simulate performance history for multiple stocks
    stock_performances = {
        'AAPL': {
            'wins': 12,
            'losses': 5,
            'total_return': 0.35,
            'num_trades': 17,
        },
        'MSFT': {
            'wins': 10,
            'losses': 4,
            'total_return': 0.28,
            'num_trades': 14,
        },
        'NVDA': {
            'wins': 8,
            'losses': 10,
            'total_return': 0.05,
            'num_trades': 18,
        },
        'TSLA': {
            'wins': 5,
            'losses': 12,
            'total_return': -0.15,
            'num_trades': 17,
        },
    }
    
    print("\n  Stock Performance Summary:")
    for symbol, perf in stock_performances.items():
        win_rate = perf['wins'] / perf['num_trades']
        print(f"    - {symbol:5} Win Rate: {win_rate:.1%}, Return: {perf['total_return']:+.1%}")
    
    # Create mock performance tracker data
    from trading_bot.data.performance_tracker import StockPerformance
    
    perf_dict = {}
    for symbol, stats in stock_performances.items():
        perf = StockPerformance(
            symbol=symbol,
            trades=stats['num_trades'],
            wins=stats['wins'],
            losses=stats['losses'],
            win_rate=stats['wins'] / stats['num_trades'],
        )
        perf_dict[symbol] = perf
    
    # Try to train (will work if sklearn is available)
    try:
        success = predictor.train(perf_dict)
        if success:
            print("\n  ✓ ML Model Trained Successfully!")
            
            # Get predictions
            predictions = predictor.predict(perf_dict)
            
            print("\n  📊 Predictions (Win Probability):")
            for symbol, pred in sorted(predictions.items(), key=lambda x: x[1].win_probability, reverse=True):
                print(f"    - {symbol:5} {pred.win_probability:.1%} confidence, "
                      f"expected return: {pred.expected_return_pct:+.1%}")
        else:
            print("\n  ⚠️ Model training skipped (insufficient data)")
    except Exception as e:
        print(f"\n  ⚠️ ML prediction not available: {e}")


def demo_portfolio_optimization():
    """Demo 5: Portfolio optimization with learned insights."""
    print("\n" + "="*80)
    print("DEMO 5: PORTFOLIO OPTIMIZATION WITH LEARNED INSIGHTS")
    print("="*80)
    
    optimizer = PortfolioOptimizer(max_position_pct=15.0, min_position_pct=2.0)
    risk_manager = RiskManager(max_daily_loss_pct=2.0)
    
    # Symbols to allocate
    symbols = ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'TSLA']
    
    # Learned scores from our strategies
    scores = {
        'AAPL': 85,
        'MSFT': 80,
        'NVDA': 90,
        'GOOGL': 75,
        'TSLA': 65,
    }
    
    # Current prices
    prices = {
        'AAPL': 150.0,
        'MSFT': 300.0,
        'NVDA': 450.0,
        'GOOGL': 140.0,
        'TSLA': 200.0,
    }
    
    # Volatility estimates
    volatilities = {
        'AAPL': 0.20,
        'MSFT': 0.18,
        'NVDA': 0.28,
        'GOOGL': 0.22,
        'TSLA': 0.35,
    }
    
    portfolio_value = 100000
    
    print(f"\n💼 Allocating ${portfolio_value:,.0f} across {len(symbols)} stocks...")
    print("\n  Input Scores:")
    for sym in sorted(symbols, key=lambda s: scores.get(s, 0), reverse=True):
        print(f"    - {sym:5} Score: {scores.get(sym, 0):3.0f}, Vol: {volatilities.get(sym, 0):.0%}")
    
    allocations = optimizer.allocate_portfolio(
        symbols=symbols,
        scores=scores,
        prices=prices,
        portfolio_value=portfolio_value,
        volatilities=volatilities,
    )
    
    print("\n  📊 Optimized Allocation:")
    total_allocated = 0
    for sym in sorted(symbols, key=lambda s: allocations.get(s).allocation_pct, reverse=True):
        alloc = allocations[sym]
        total_allocated += alloc.allocation_pct
        print(f"    - {sym:5} {alloc.allocation_pct:6.2f}% (${alloc.target_value:10,.0f}, "
              f"{alloc.num_shares:4.0f} shares)")
    
    print(f"\n  Total Allocated: {total_allocated:.1f}%")
    
    # Portfolio metrics
    metrics = optimizer.calculate_portfolio_metrics(allocations, volatilities)
    print(f"\n  📈 Portfolio Metrics:")
    print(f"    - Effective Positions: {metrics['effective_positions']:.1f} (out of {metrics['num_positions']})")
    print(f"    - Portfolio Volatility: {metrics['portfolio_volatility']:.1%}")
    print(f"    - Diversification Score: {metrics['diversification']:.1%}")
    print(f"    - Concentration (Herfindahl): {metrics['concentration']:.4f}")
    
    # Risk check
    risk_mgr = RiskManager()
    risk_mgr.reset_daily(portfolio_value)
    should_stop, reason = risk_mgr.should_stop_trading(
        portfolio_value * 0.98,  # 2% loss
        len(allocations),
        max(alloc.allocation_pct for alloc in allocations.values())
    )
    print(f"\n  🛡️ Risk Status: {'⚠️ STOP' if should_stop else '✓ OK'}")


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "AI-POWERED STRATEGY LEARNING & PORTFOLIO OPTIMIZATION DEMO".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    # Run demos
    learner, learned_params = demo_basic_learning()
    demo_hybrid_building(learner, learned_params)
    demo_learning_from_trades(learner)
    demo_ml_prediction(learner)
    demo_portfolio_optimization()
    
    # Save all learned strategies
    print("\n" + "="*80)
    print("SAVING LEARNED STRATEGIES")
    print("="*80)
    learner.save()
    print("\n✅ All learned strategies saved to cache")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"""
✨ System Features Demonstrated:

1. ✓ Multiple Strategy Learning
   - Learns optimal parameters from different trading strategies
   - Tracks performance metrics and confidence levels

2. ✓ Hybrid Strategy Building
   - Combines multiple strategies into a single hybrid strategy
   - Allocates weights based on performance metrics

3. ✓ Performance-Based Learning
   - Learns from actual trading history
   - Suggests parameter adjustments based on outcomes

4. ✓ ML-Based Prediction
   - Trains Random Forest on historical performance
   - Predicts win probability for stocks

5. ✓ Portfolio Optimization
   - Allocates capital based on learned scores
   - Respects risk limits and position sizing

6. ✓ Risk Management
   - Enforces daily loss limits
   - Monitors drawdown and position concentrations

🎯 How It Works:
   ├─ Learn from backtests → store optimal parameters
   ├─ Learn from live trades → refine parameters
   ├─ Combine strategies → build hybrid approaches
   ├─ Predict winners → allocate capital wisely
   └─ Enforce limits → protect capital

💡 Next Steps:
   - Deploy to paper trading for real-world validation
   - Monitor performance metrics continuously
   - Adapt strategies based on market regimes
   - Build ensemble of hybrid strategies
""")


if __name__ == '__main__':
    main()
