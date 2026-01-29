#!/usr/bin/env python3
"""
Test evolved strategy (Gen 364) on different symbol sets to evaluate generalization
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

# Load all data
conn = sqlite3.connect('data/real_market_data.db')
query = 'SELECT symbol, date, open, high, low, close, volume FROM daily_prices ORDER BY symbol, date'
df = pd.read_sql_query(query, conn)
conn.close()

df['date'] = pd.to_datetime(df['date'])
all_symbols = df['symbol'].unique()

print("=" * 120)
print("STRATEGY GENERALIZATION TEST - DIFFERENT SYMBOL SETS")
print("=" * 120)
print(f"\nTotal Available Symbols: {len(all_symbols)}")
print(f"Best Parameters from Gen 364")

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

def backtest_symbols(symbols_list, df, params):
    market_data = {}
    for symbol in symbols_list:
        symbol_df = df[df['symbol'] == symbol].copy()
        if len(symbol_df) > 0:
            market_data[symbol] = symbol_df
    
    start_cash = 100000
    cash = start_cash
    positions = {}
    entry_prices = {}
    total_pnl = 0
    trades = 0
    commission_bps = 10
    
    for symbol in market_data:
        data = market_data[symbol].copy()
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

# Define symbol sets
symbol_sets = {
    'All 140 Symbols': list(all_symbols),
    'Top 10 Tech (AAPL, MSFT, NVDA, TSLA, META, GOOG, GOOGL, AMZN, AVGO, ASML)': ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META', 'GOOG', 'GOOGL', 'AMZN', 'AVGO', 'ASML'],
    'Top 10 Financial (BRK.B, JPM, V, WFC, BAC, GS, MS, PNC, USB, STT)': ['BRK.B', 'JPM', 'V', 'WFC', 'BAC', 'GS', 'MS', 'PNC', 'USB', 'STT'],
    'Top 10 Energy (XOM, COP, SLB, EOG, MPC, PSX, VLO, OXY, HES, APA)': ['XOM', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'HES', 'APA'],
    'Top 10 Healthcare (UNH, ABBV, LLY, MRK, AMGN, ABT, TMO, GILD, BIIB, REGN)': ['UNH', 'ABBV', 'LLY', 'MRK', 'AMGN', 'ABT', 'TMO', 'GILD', 'BIIB', 'REGN'],
    'Top 10 Consumer (DIS, MCD, KO, PEP, COST, NKE, SBUX, LOW, HD, TJX)': ['DIS', 'MCD', 'KO', 'PEP', 'COST', 'NKE', 'SBUX', 'LOW', 'HD', 'TJX'],
    'Top 10 Industrial (CAT, BA, MMM, HON, RTX, LMT, GD, TT, NOC, HII)': ['CAT', 'BA', 'MMM', 'HON', 'RTX', 'LMT', 'GD', 'TT', 'NOC', 'HII'],
    'Top 10 Utilities (NEE, DUK, SO, EXC, D, AEP, PEG, XEL, WEC, CMS)': ['NEE', 'DUK', 'SO', 'EXC', 'D', 'AEP', 'PEG', 'XEL', 'WEC', 'CMS'],
    'Top 10 Communications (VZ, T, CMCSA, CHTR, TMUS, DISH, DTV, ATVI, EA, TTWO)': ['VZ', 'T', 'CMCSA', 'CHTR', 'TMUS', 'DISH', 'DTV', 'ATVI', 'EA', 'TTWO'],
}

print(f"\n{'Symbol Set':<50} {'Symbols':<12} {'Return %':<15} {'Trades':<15}")
print("=" * 120)

results = []
for set_name, symbols in symbol_sets.items():
    available = [s for s in symbols if s in all_symbols]
    if len(available) == 0:
        continue
    
    ret, trades = backtest_symbols(available, df, best_params)
    results.append({'name': set_name, 'count': len(available), 'return': ret, 'trades': trades})
    
    status = "PROFIT" if ret > 0 else "LOSS"
    print(f"{set_name:<50} {len(available):<12} {ret*100:>14.2f}% {trades:>14} [{status}]")

# Statistics
print("\n" + "=" * 120)
print("GENERALIZATION ANALYSIS")
print("=" * 120)

returns = [r['return'] for r in results]
profitable = sum(1 for r in results if r['return'] > 0)

print(f"\nNumber of Symbol Sets Tested:   {len(results)}")
print(f"Profitable Sets:                {profitable}/{len(results)} ({profitable/len(results)*100:.1f}%)")
print(f"Average Return (all sets):      {np.mean(returns)*100:+.2f}%")
print(f"Median Return:                  {np.median(returns)*100:+.2f}%")
print(f"Min Return:                     {np.min(returns)*100:+.2f}%")
print(f"Max Return:                     {np.max(returns)*100:+.2f}%")

best_set = max(results, key=lambda x: x['return'])
worst_set = min(results, key=lambda x: x['return'])

print(f"\nBest Performing Set:            {best_set['name']} ({best_set['return']*100:+.2f}%)")
print(f"Worst Performing Set:           {worst_set['name']} ({worst_set['return']*100:+.2f}%)")

print("\n" + "=" * 120)
print("CONCLUSION:")
if profitable / len(results) > 0.7:
    print("✓ Strategy generalizes VERY WELL across different sectors")
elif profitable / len(results) > 0.5:
    print("✓ Strategy generalizes REASONABLY WELL across different sectors")
else:
    print("⚠ Strategy may need sector-specific parameter tuning")
print("=" * 120)
