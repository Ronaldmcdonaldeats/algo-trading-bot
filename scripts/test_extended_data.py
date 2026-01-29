#!/usr/bin/env python3
"""
Test evolved strategy on rolling windows and different market regimes
"""

import sqlite3
import pandas as pd
import numpy as np
import json
from collections import defaultdict

conn = sqlite3.connect('data/real_market_data.db')
cursor = conn.cursor()
cursor.execute("SELECT best_params FROM evolution_fast_1000gen WHERE generation = 364")
params_json = cursor.fetchone()[0]
best_params = json.loads(params_json)
conn.close()

# Load all data
conn = sqlite3.connect('data/real_market_data.db')
query = 'SELECT symbol, date, open, high, low, close, volume FROM daily_prices ORDER BY symbol, date'
df = pd.read_sql_query(query, conn)
conn.close()

# Get date range
df['date'] = pd.to_datetime(df['date'])
min_date = df['date'].min()
max_date = df['date'].max()
total_days = (max_date - min_date).days

print("=" * 100)
print("ROBUSTNESS TESTING - ROLLING WINDOWS & MARKET REGIMES")
print("=" * 100)
print(f"\nData Range: {min_date.date()} to {max_date.date()} ({total_days} days)")

# Test 1: Rolling 30-day windows
print(f"\n{'ROLLING 30-DAY WINDOWS':-^100}")
print(f"{'Start Date':<20} {'End Date':<20} {'Return %':<15} {'Trades':<10} {'Result':<15}")
print("-" * 100)

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

def backtest_period(market_data, start_date, end_date, params):
    start_cash = 100000
    cash = start_cash
    positions = {}
    entry_prices = {}
    total_pnl = 0
    trades = 0
    commission_bps = 10
    
    for symbol in market_data:
        data = market_data[symbol]
        data = data[(data['date'] >= start_date) & (data['date'] <= end_date)].copy()
        if len(data) < 25:
            continue
        
        for idx in range(25, len(data)):
            hist_df = data.iloc[:idx]
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

# Prepare market data
market_data = {}
for symbol in df['symbol'].unique():
    symbol_df = df[df['symbol'] == symbol].copy()
    market_data[symbol] = symbol_df

# Rolling 30-day windows
from datetime import timedelta
current = min_date + timedelta(days=30)
all_returns = []

while current <= max_date:
    start = current - timedelta(days=30)
    try:
        ret, trades = backtest_period(market_data, start, current, best_params)
        all_returns.append(ret)
        status = "Profit" if ret > 0 else "Loss"
        print(f"{start.date():<20} {current.date():<20} {ret*100:>14.2f}% {trades:>9} {status:<15}")
    except:
        pass
    current += timedelta(days=7)

# Statistics
print(f"\n{'ROLLING WINDOW STATISTICS':-^100}")
if all_returns:
    print(f"Avg Return:          {np.mean(all_returns)*100:>20.2f}%")
    print(f"Median Return:       {np.median(all_returns)*100:>20.2f}%")
    print(f"Std Dev:             {np.std(all_returns)*100:>20.2f}%")
    print(f"Min Return:          {np.min(all_returns)*100:>20.2f}%")
    print(f"Max Return:          {np.max(all_returns)*100:>20.2f}%")
    profitable = sum(1 for r in all_returns if r > 0)
    print(f"Profitable Periods:  {profitable}/{len(all_returns)} ({profitable/len(all_returns)*100:.1f}%)")

# Test 2: Full period performance by market phase
print(f"\n{'MARKET REGIME ANALYSIS':-^100}")
print("Testing strategy across different market conditions...")

# Split data into quarters
quarters = {}
for symbol in market_data:
    data = market_data[symbol].copy().sort_values('date')
    q_len = len(data) // 4
    for q in range(4):
        q_name = f"Q{q+1}"
        if q == 3:
            q_data = data.iloc[q*q_len:]
        else:
            q_data = data.iloc[q*q_len:(q+1)*q_len]
        if q_name not in quarters:
            quarters[q_name] = {}
        quarters[q_name][symbol] = q_data

print(f"{'Quarter':<15} {'Return %':<15} {'Trades':<10} {'Result':<15}")
print("-" * 100)

for q_name in sorted(quarters.keys()):
    try:
        ret, trades = backtest_period(quarters[q_name], min_date, max_date, best_params)
        status = "Profit" if ret > 0 else "Loss"
        print(f"{q_name:<15} {ret*100:>14.2f}% {trades:>9} {status:<15}")
    except:
        print(f"{q_name:<15} {'Error':<15} {0:>9} {'N/A':<15}")

print("\n" + "=" * 100)
print("Note: Rolling windows validate consistency. Profitable most periods = robust strategy")
print("=" * 100)
