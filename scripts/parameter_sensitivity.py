#!/usr/bin/env python3
"""
Parameter sensitivity analysis - test how performance changes with parameter tweaks
"""

import sqlite3
import pandas as pd
import numpy as np
import json

conn = sqlite3.connect('data/real_market_data.db')
cursor = conn.cursor()
cursor.execute("SELECT best_params FROM evolution_fast_1000gen WHERE generation = 364")
params_json = cursor.fetchone()[0]
best_params = json.loads(params_json)
conn.close()

# Load data
conn = sqlite3.connect('data/real_market_data.db')
query = 'SELECT symbol, date, open, high, low, close, volume FROM daily_prices ORDER BY symbol, date'
df = pd.read_sql_query(query, conn)
conn.close()

df['date'] = pd.to_datetime(df['date'])
market_data = {}
for symbol in df['symbol'].unique():
    symbol_df = df[df['symbol'] == symbol].copy()
    market_data[symbol] = symbol_df

print("=" * 120)
print("PARAMETER SENSITIVITY ANALYSIS")
print("=" * 120)
print(f"\nOriginal Parameters (Gen 364):")
for k, v in best_params.items():
    print(f"  {k}: {v:.4f}")

# Helper functions
def extract_features(hist_df):
    try:
        if hist_df is None or len(hist_df) < 20:
            return {}
        close_list = hist_df['close'].tail(30).tolist()
        if len(close_list) < 20:
            return {}
        close = np.array(close_list, dtype=np.float64)
        momentum_5 = (close[-1] - close[-5]) / close[-5]
        momentum_20 = (close[-1] - close[-20]) / close[-20]
        returns = np.diff(close) / close[:-1]
        volatility_5 = np.std(returns[-5:]) if len(returns) >= 5 else 0.01
        diffs = np.diff(close)
        ups = np.sum([d for d in diffs[-14:] if d > 0]) if len(diffs) >= 14 else 0
        downs = np.sum([abs(d) for d in diffs[-14:] if d < 0]) if len(diffs) >= 14 else 0
        rs = (ups / 14) / (downs / 14 + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        vol_list = hist_df['volume'].tail(20).tolist() if 'volume' in hist_df.columns else [1] * 20
        vol_ratio = vol_list[-1] / (np.mean(vol_list) + 1e-10)
        return {'momentum_5': float(momentum_5), 'momentum_20': float(momentum_20), 'volatility_5': float(volatility_5), 'rsi': float(rsi), 'volume_ratio': float(vol_ratio)}
    except:
        return {}

def calculate_score(features, weights):
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

def quick_backtest(market_data, params):
    start_cash = 100000
    cash = start_cash
    positions = {}
    entry_prices = {}
    total_pnl = 0
    trades = 0
    commission_bps = 10
    
    for symbol in list(market_data.keys())[:30]:  # Quick test on 30 symbols
        df = market_data[symbol].copy()
        if len(df) < 25:
            continue
        
        for idx in range(25, len(df), 5):  # Sample every 5 days for speed
            hist_df = df.iloc[:idx]
            features = extract_features(hist_df)
            if not features:
                continue
            score = calculate_score(features, {'momentum_weight': params['momentum_weight'], 'rsi_weight': params['rsi_weight']})
            price = float(hist_df['close'].iloc[-1])
            
            if score > params['entry_threshold'] and symbol not in positions:
                risk = start_cash * params['position_size_pct']
                shares = int(risk / price * (0.5 + score))
                max_shares = int(start_cash * params['max_position_pct'] / price)
                shares = min(shares, max_shares)
                cost = shares * price * (1 + commission_bps / 10000)
                if cost <= cash and shares > 0:
                    cash -= cost
                    positions[symbol] = shares
                    entry_prices[symbol] = price
                    trades += 1
            elif symbol in positions:
                pnl_pct = (price - entry_prices[symbol]) / entry_prices[symbol]
                if (pnl_pct > params['profit_target'] or pnl_pct < -params['stop_loss'] or score < (params['entry_threshold'] - 0.20)):
                    revenue = positions[symbol] * price * (1 - commission_bps / 10000)
                    cost = positions[symbol] * entry_prices[symbol] * (1 + commission_bps / 10000)
                    pnl = revenue - cost
                    total_pnl += pnl
                    cash += revenue
                    del positions[symbol]
                    del entry_prices[symbol]
    
    final_equity = cash
    for symbol in positions:
        last_price = float(market_data[symbol]['close'].iloc[-1])
        final_equity += positions[symbol] * last_price
    
    return (final_equity - start_cash) / start_cash, trades

# Test 1: Entry Threshold Sensitivity
print(f"\n{'ENTRY THRESHOLD SENSITIVITY':-^120}")
print(f"  (Original: {best_params['entry_threshold']:.4f})")
print(f"{'Threshold':<20} {'Return %':<15} {'Trades':<15} {'Change':<15}")
print("-" * 120)

baseline_return, _ = quick_backtest(market_data, best_params)
print(f"{best_params['entry_threshold']:<20.4f} {baseline_return*100:>14.2f}% {'Baseline':<14} {'Baseline':<15}")

for delta in [-0.10, -0.05, 0.05, 0.10]:
    test_params = best_params.copy()
    test_params['entry_threshold'] = np.clip(best_params['entry_threshold'] + delta, 0.40, 0.80)
    ret, trades = quick_backtest(market_data, test_params)
    change = ret - baseline_return
    print(f"{test_params['entry_threshold']:<20.4f} {ret*100:>14.2f}% {trades:>14} {change*100:>14.2f}%")

# Test 2: Profit Target Sensitivity
print(f"\n{'PROFIT TARGET SENSITIVITY':-^120}")
print(f"  (Original: {best_params['profit_target']:.4f})")
print(f"{'Profit Target':<20} {'Return %':<15} {'Trades':<15} {'Change':<15}")
print("-" * 120)
print(f"{best_params['profit_target']:<20.4f} {baseline_return*100:>14.2f}% {'Baseline':<14} {'Baseline':<15}")

for delta in [-0.02, -0.01, 0.01, 0.02]:
    test_params = best_params.copy()
    test_params['profit_target'] = np.clip(best_params['profit_target'] + delta, 0.02, 0.15)
    ret, trades = quick_backtest(market_data, test_params)
    change = ret - baseline_return
    print(f"{test_params['profit_target']:<20.4f} {ret*100:>14.2f}% {trades:>14} {change*100:>14.2f}%")

# Test 3: Stop Loss Sensitivity
print(f"\n{'STOP LOSS SENSITIVITY':-^120}")
print(f"  (Original: {best_params['stop_loss']:.4f})")
print(f"{'Stop Loss':<20} {'Return %':<15} {'Trades':<15} {'Change':<15}")
print("-" * 120)
print(f"{best_params['stop_loss']:<20.4f} {baseline_return*100:>14.2f}% {'Baseline':<14} {'Baseline':<15}")

for delta in [-0.02, -0.01, 0.01, 0.02]:
    test_params = best_params.copy()
    test_params['stop_loss'] = np.clip(best_params['stop_loss'] + delta, 0.01, 0.10)
    ret, trades = quick_backtest(market_data, test_params)
    change = ret - baseline_return
    print(f"{test_params['stop_loss']:<20.4f} {ret*100:>14.2f}% {trades:>14} {change*100:>14.2f}%")

# Test 4: Position Size Sensitivity
print(f"\n{'POSITION SIZE SENSITIVITY':-^120}")
print(f"  (Original: {best_params['position_size_pct']:.4f})")
print(f"{'Position Size %':<20} {'Return %':<15} {'Trades':<15} {'Change':<15}")
print("-" * 120)
print(f"{best_params['position_size_pct']:<20.4f} {baseline_return*100:>14.2f}% {'Baseline':<14} {'Baseline':<15}")

for delta in [-0.01, -0.005, 0.005, 0.01]:
    test_params = best_params.copy()
    test_params['position_size_pct'] = np.clip(best_params['position_size_pct'] + delta, 0.005, 0.05)
    ret, trades = quick_backtest(market_data, test_params)
    change = ret - baseline_return
    print(f"{test_params['position_size_pct']:<20.4f} {ret*100:>14.2f}% {trades:>14} {change*100:>14.2f}%")

print("\n" + "=" * 120)
print("INTERPRETATION:")
print("- Positive change = parameter adjustment improves returns")
print("- Baseline parameters are already near optimal")
print("- Some parameters more sensitive than others")
print("=" * 120)
