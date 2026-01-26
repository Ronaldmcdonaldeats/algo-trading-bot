#!/usr/bin/env python3
from alpaca.trading.client import TradingClient
import os

api_key = os.environ.get('APCA_API_KEY_ID')
api_secret = os.environ.get('APCA_API_SECRET_KEY')

client = TradingClient(api_key=api_key, secret_key=api_secret, paper=True)
positions = client.get_all_positions()

print(f'\nTotal Open Positions: {len(positions)}\n')
print('Symbol | Qty | Entry Price | Current | P&L% | Stop Loss | Take Profit')
print('-' * 85)

for pos in sorted(positions, key=lambda p: p.symbol):
    try:
        qty = int(pos.qty)
        entry = float(pos.avg_entry_price)
        current = float(pos.current_price or entry)
        pnl_pct = float(pos.unrealized_plpc or 0) * 100
        
        stop_loss = entry * 0.98
        take_profit = entry * 1.05
        
        print(f'{pos.symbol:6} | {qty:3} | ${entry:8.2f} | ${current:8.2f} | {pnl_pct:6.2f}% | ${stop_loss:8.2f} | ${take_profit:8.2f}')
    except Exception as e:
        print(f'{pos.symbol}: Error - {e}')

print(f'\nExit Conditions:')
print(f'- Stop Loss (SL): Price drops 2% below entry')
print(f'- Take Profit (TP): Price rises 5% above entry')
print(f'- SELL Signal: Strategy generates sell signal')
print(f'- Position Rotation: Max holding time exceeded')
