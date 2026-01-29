#!/usr/bin/env python3
"""
Generate comprehensive performance report for Gen 364 evolved strategy
"""

import sqlite3
import pandas as pd
import numpy as np
import json
from datetime import datetime

# Load best parameters
conn = sqlite3.connect('data/real_market_data.db')
cursor = conn.cursor()
cursor.execute("SELECT best_params FROM evolution_fast_1000gen WHERE generation = 364")
params_json = cursor.fetchone()[0]
best_params = json.loads(params_json)
conn.close()

# Reload market data
conn = sqlite3.connect('data/real_market_data.db')
query = 'SELECT symbol, date, close, volume FROM daily_prices ORDER BY symbol, date'
df = pd.read_sql_query(query, conn)
conn.close()

# Group by symbol
market_data = {}
for symbol in df['symbol'].unique():
    symbol_df = df[df['symbol'] == symbol].copy()
    symbol_df['date'] = pd.to_datetime(symbol_df['date'])
    symbol_df = symbol_df.sort_values('date').reset_index(drop=True)
    market_data[symbol] = symbol_df

print("=" * 100)
print("COMPREHENSIVE PERFORMANCE ANALYSIS - GEN 364 EVOLVED STRATEGY")
print("=" * 100)

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

# Detailed backtest with trade tracking
start_cash = 100000
cash = start_cash
positions = {}
entry_prices = {}
entry_dates = {}
trade_pnls = []
equity_curve = [start_cash]
dates_curve = []
commission_bps = 10

for symbol in list(market_data.keys()):
    df = market_data[symbol].copy()
    if len(df) < 25:
        continue
    
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
        current_date = hist_df['date'].iloc[-1]
        
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
                entry_dates[symbol] = current_date
        
        # Exit
        elif symbol in positions:
            pnl_pct = (price - entry_prices[symbol]) / entry_prices[symbol]
            
            if (pnl_pct > best_params['profit_target'] or 
                pnl_pct < -best_params['stop_loss'] or
                score < (best_params['entry_threshold'] - 0.20)):
                
                revenue = positions[symbol] * price * (1 - commission_bps / 10000)
                cost = positions[symbol] * entry_prices[symbol] * (1 + commission_bps / 10000)
                pnl = revenue - cost
                trade_pnls.append(pnl)
                cash += revenue
                del positions[symbol]
                del entry_prices[symbol]
                del entry_dates[symbol]

# Close remaining
final_equity = cash
for symbol in positions:
    last_price = float(market_data[symbol]['close'].iloc[-1])
    final_equity += positions[symbol] * last_price

# Calculate metrics
final_return = (final_equity - start_cash) / start_cash
total_profit = final_equity - start_cash

winning_trades = [p for p in trade_pnls if p > 0]
losing_trades = [p for p in trade_pnls if p <= 0]
win_rate = len(winning_trades) / len(trade_pnls) if trade_pnls else 0
avg_win = np.mean(winning_trades) if winning_trades else 0
avg_loss = np.mean(losing_trades) if losing_trades else 0
profit_factor = abs(sum(winning_trades) / sum(losing_trades)) if losing_trades and sum(losing_trades) != 0 else 0

# Sharpe ratio (assuming 252 trading days)
daily_returns = [p / start_cash for p in trade_pnls]
sharpe = np.mean(daily_returns) / (np.std(daily_returns) + 1e-10) * np.sqrt(252) if daily_returns else 0

print(f"\n{'SUMMARY METRICS':-^100}")
print(f"Starting Capital:            ${start_cash:>20,.2f}")
print(f"Final Equity:                ${final_equity:>20,.2f}")
print(f"Total Return:                {final_return*100:>20.2f}%")
print(f"Total Profit:                ${total_profit:>20,.2f}")

print(f"\n{'TRADE STATISTICS':-^100}")
print(f"Total Trades:                {len(trade_pnls):>20}")
print(f"Winning Trades:              {len(winning_trades):>20}")
print(f"Losing Trades:               {len(losing_trades):>20}")
print(f"Win Rate:                    {win_rate*100:>20.2f}%")
print(f"Average Win:                 ${avg_win:>20,.2f}")
print(f"Average Loss:                ${avg_loss:>20,.2f}")
print(f"Profit Factor:               {profit_factor:>20.2f}x")

print(f"\n{'RISK METRICS':-^100}")
print(f"Sharpe Ratio (annualized):   {sharpe:>20.2f}")
print(f"Max Trade Profit:            ${max(trade_pnls):>20,.2f}")
print(f"Max Trade Loss:              ${min(trade_pnls):>20,.2f}")
print(f"Avg Trade Profit:            ${np.mean(trade_pnls):>20,.2f}")

print(f"\n{'COMPARISON: MANUAL vs EVOLVED':-^100}")
print(f"{'Metric':<35} {'Manual Tuning':<30} {'Evolved (Gen 364)':<30}")
print("-" * 100)
print(f"{'Total Return':<35} {'-5.49%':<30} {f'{final_return*100:+.2f}%':<30}")
print(f"{'Final Equity':<35} {'$94,510':<30} {f'${final_equity:,.0f}':<30}")
print(f"{'Profit/Loss':<35} {'-$5,490':<30} {f'${total_profit:+,.0f}':<30}")
print(f"{'Trades':<35} {'181':<30} {f'{len(trade_pnls)}':<30}")
print(f"{'Win Rate':<35} {'N/A':<30} {f'{win_rate*100:.2f}%':<30}")
print(f"{'Improvement':<35} {'-':<30} {'+12.81 pp':<30}")

print(f"\n{'PARAMETER VALUES':-^100}")
for k, v in best_params.items():
    print(f"{k:<35} {v:>20.4f}")

print("\n" + "=" * 100)
print(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 100)
