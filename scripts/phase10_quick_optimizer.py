"""
Phase 10: Manual Parameter Tuning + Quick Testing
Based on initial grid search results, test a few promising configurations
"""

import json
import os
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_synthetic_data(symbol: str) -> np.ndarray:
    """Generate synthetic price data"""
    np.random.seed(hash(symbol) % 2**32)
    trading_days = 6540
    returns = np.random.normal(0.0003, 0.015, trading_days)
    
    # Embed crashes
    crashes = {
        int(trading_days * 0.15): -0.15,
        int(trading_days * 0.58): -0.20,
        int(trading_days * 0.85): -0.08,
    }
    for day, impact in crashes.items():
        if 0 <= day < len(returns):
            returns[day] = impact
    
    prices = np.exp(np.cumsum(returns)) * 100
    return prices


def backtest_fast(prices: np.ndarray, sma_f, sma_s, rsi_os, rsi_ob, ma_w) -> float:
    """Fast backtest"""
    if len(prices) < max(sma_s, ma_w, 50):
        return 0.0
    
    capital = 100000.0
    position = 0.0
    start = max(sma_s, ma_w, 50)
    
    for i in range(start, len(prices)):
        price = prices[i]
        ma = np.mean(prices[max(0, i-ma_w):i])
        
        # SMA
        f_ma = np.mean(prices[max(0, i-sma_f):i])
        s_ma = np.mean(prices[max(0, i-sma_s):i])
        sma_sig = 1.0 if f_ma > s_ma else (-1.0 if f_ma < s_ma else 0.0)
        
        # RSI (simple)
        recent = prices[max(0, i-20):i+1]
        if len(recent) > 1:
            changes = np.diff(recent)
            gains = np.mean(changes[changes > 0])
            losses = np.mean(np.abs(changes[changes < 0]))
            rsi = 50.0 if losses == 0 else 100 - (100/(1 + gains/losses if losses else 0))
        else:
            rsi = 50.0
        
        # Regime
        regime = 'bull' if price > ma and sma_sig > 0 else 'bear'
        
        # Signal
        if regime == 'bull':
            sig = sma_sig
        else:
            sig = 1.0 if rsi < rsi_os else (-1.0 if rsi > rsi_ob else 0.0)
        
        # Position
        if position == 0 and sig > 0:
            position = capital * 0.9 / price
        elif position > 0 and sig < 0:
            capital = position * price
            position = 0.0
    
    if position > 0:
        capital = position * prices[-1]
    
    annual = (capital / 100000) ** (1/25) - 1
    return max(annual, -0.5)


# Test best configs found
configs_to_test = [
    {'name': 'From Grid Search', 'sma_f': 10, 'sma_s': 40, 'rsi_os': 25, 'rsi_ob': 75, 'ma_w': 100},
    {'name': 'Conservative', 'sma_f': 15, 'sma_s': 50, 'rsi_os': 30, 'rsi_ob': 70, 'ma_w': 150},
    {'name': 'Aggressive', 'sma_f': 10, 'sma_s': 50, 'rsi_os': 25, 'rsi_ob': 75, 'ma_w': 100},
    {'name': 'Long MA', 'sma_f': 15, 'sma_s': 50, 'rsi_os': 30, 'rsi_ob': 70, 'ma_w': 200},
    {'name': 'Tight RSI', 'sma_f': 12, 'sma_s': 40, 'rsi_os': 20, 'rsi_ob': 80, 'ma_w': 150},
]

logger.info("="*70)
logger.info("PHASE 10: QUICK PARAMETER TEST")
logger.info("="*70 + "\n")

stocks = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'NFLX', 'ADBE', 'INTC']
data = {s: generate_synthetic_data(s) for s in stocks}

best_overall = None
best_overall_return = 0.0

for cfg in configs_to_test:
    logger.info(f"Testing {cfg['name']}...")
    returns = []
    
    for prices in data.values():
        ret = backtest_fast(prices, cfg['sma_f'], cfg['sma_s'], cfg['rsi_os'], cfg['rsi_ob'], cfg['ma_w'])
        returns.append(ret)
    
    avg_ret = np.mean(returns)
    logger.info(f"  Avg Annual: {avg_ret:.2%}\n")
    
    if avg_ret > best_overall_return:
        best_overall_return = avg_ret
        best_overall = cfg

logger.info("="*70)
logger.info(f"BEST CONFIG: {best_overall['name']}")
logger.info(f"Average Annual Return: {best_overall_return:.2%}")
logger.info("="*70 + "\n")

# Save
os.makedirs('phase10_results', exist_ok=True)
cfg_to_save = {
    'sma_fast': best_overall['sma_f'],
    'sma_slow': best_overall['sma_s'],
    'rsi_oversold': best_overall['rsi_os'],
    'rsi_overbought': best_overall['rsi_ob'],
    'ma_window': best_overall['ma_w'],
    'avg_annual_return': best_overall_return,
    'config_name': best_overall['name']
}

with open('phase10_results/phase10_best_config.json', 'w') as f:
    json.dump(cfg_to_save, f, indent=2)

logger.info("Saved best config to phase10_results/phase10_best_config.json")
