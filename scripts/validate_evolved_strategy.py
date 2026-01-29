#!/usr/bin/env python3
"""
Validate the best evolved strategy on full 140-symbol dataset
"""

import sqlite3
import pandas as pd
import numpy as np
import json

# Load best parameters from Gen 364
conn = sqlite3.connect('data/real_market_data.db')
cursor = conn.cursor()
cursor.execute("SELECT best_params FROM evolution_fast_1000gen WHERE generation = 364")
params_json = cursor.fetchone()[0]
best_params = json.loads(params_json)
conn.close()

print("=" * 80)
print("VALIDATING BEST EVOLVED STRATEGY ON ALL 140 SYMBOLS")
print("=" * 80)
print(f"\nBest Parameters (Gen 364):")
for k, v in best_params.items():
    print(f"  {k}: {v:.4f}")

# Load all market data
conn = sqlite3.connect('data/real_market_data.db')
query = '''
    SELECT symbol, date, open, high, low, close, volume
    FROM daily_prices
    ORDER BY symbol, date
'''
df = pd.read_sql_query(query, conn)
conn.close()

# Group by symbol - ALL 140
market_data = {}
for symbol in df['symbol'].unique():
    symbol_df = df[df['symbol'] == symbol].copy()
    symbol_df['date'] = pd.to_datetime(symbol_df['date'])
    symbol_df = symbol_df.sort_values('date').reset_index(drop=True)
    market_data[symbol] = symbol_df

print(f"\nLoaded {len(market_data)} symbols")

# Helper functions
def extract_features(hist_df):
    """Extract features"""
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

def calculate_score(features, weights):
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

# Backtest
start_cash = 100000
cash = start_cash
positions = {}
entry_prices = {}
total_pnl = 0
trades = 0
commission_bps = 10

print("\nRunning backtest on all 140 symbols with evolved parameters...")

for symbol in list(market_data.keys()):
    df = market_data[symbol].copy()
    if len(df) < 25:
        continue
    
    # Daily backtest (not sampled)
    for idx in range(25, len(df)):
        hist_df = df.iloc[:idx]
        features = extract_features(hist_df)
        
        if not features:
            continue
        
        score = calculate_score(features, {
            'momentum_weight': best_params['momentum_weight'],
            'rsi_weight': best_params['rsi_weight'],
        })
        
        price = float(hist_df['close'].iloc[-1])
        
        # Entry
        if score > best_params['entry_threshold'] and symbol not in positions:
            risk = start_cash * best_params['position_size_pct']
            shares = int(risk / price * (0.5 + score))
            max_shares = int(start_cash * best_params['max_position_pct'] / price)
            shares = min(shares, max_shares)
            
            cost = shares * price * (1 + commission_bps / 10000)
            
            if cost <= cash and shares > 0:
                cash -= cost
                positions[symbol] = shares
                entry_prices[symbol] = price
                trades += 1
        
        # Exit
        elif symbol in positions:
            pnl_pct = (price - entry_prices[symbol]) / entry_prices[symbol]
            
            if (pnl_pct > best_params['profit_target'] or 
                pnl_pct < -best_params['stop_loss'] or
                score < (best_params['entry_threshold'] - 0.20)):
                
                revenue = positions[symbol] * price * (1 - commission_bps / 10000)
                cost = positions[symbol] * entry_prices[symbol] * (1 + commission_bps / 10000)
                pnl = revenue - cost
                
                total_pnl += pnl
                cash += revenue
                del positions[symbol]
                del entry_prices[symbol]

# Close remaining positions
final_equity = cash
for symbol in positions:
    last_price = float(market_data[symbol]['close'].iloc[-1])
    final_equity += positions[symbol] * last_price

# Results
final_return = (final_equity - start_cash) / start_cash
max_drawdown_pct = -5.0  # Placeholder

print("\n" + "=" * 80)
print("BACKTEST RESULTS - ALL 140 SYMBOLS")
print("=" * 80)
print(f"\nStarting Capital:    ${start_cash:,.2f}")
print(f"Final Equity:        ${final_equity:,.2f}")
print(f"Total Return:        {final_return*100:+.2f}%")
print(f"Profit/Loss:         ${final_equity - start_cash:+,.2f}")
print(f"Total Trades:        {trades}")
print(f"\nComparison vs Manual Tuning:")
print(f"  Manual (Gen 1):    -5.49% ($94,510)")
print(f"  Evolved (Gen 364): {final_return*100:+.2f}% (${final_equity:,.0f})")
improvement = final_return - (-0.0549)
print(f"  Improvement:       {improvement*100:+.2f} percentage points")

print("\n" + "=" * 80)
