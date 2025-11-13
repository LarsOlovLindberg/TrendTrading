#!/usr/bin/env python3
"""
Test different poll intervals for the adaptive strategy.
Analyzes performance with various tick frequencies (1s, 2s, 5s, 10s, 30s).
"""

import json
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone

# Load historical data
DATA_FILE = Path("data") / "klines_analysis.csv"

if not DATA_FILE.exists():
    print(f"Error: Data file not found: {DATA_FILE}")
    print("Please ensure historical data exists in data/klines_analysis.csv")
    exit(1)

# Parse CSV data
prices = []
timestamps = []

with open(DATA_FILE, 'r') as f:
    lines = f.readlines()[1:]  # Skip header
    for line in lines:
        parts = line.strip().split(',')
        if len(parts) >= 2:
            ts = int(parts[0])
            price = float(parts[1])  # Close price (index 1)
            if price > 0:  # Only include valid prices
                timestamps.append(ts)
                prices.append(price)

print(f"✅ Loaded {len(prices)} price points from {DATA_FILE}")
print(f"📅 Period: {datetime.fromtimestamp(timestamps[0]/1000)} to {datetime.fromtimestamp(timestamps[-1]/1000)}")
print(f"💵 Price range: ${min(prices):.0f} - ${max(prices):.0f}")
print()

# Test configurations
POLL_INTERVALS = [1, 2, 5, 10, 30]  # seconds
INITIAL_CAPITAL = 10000  # USDT

def simulate_strategy(poll_sec, prices, timestamps):
    """
    Simplified simulation of adaptive strategy with given poll interval.
    Returns: (total_trades, win_rate, final_pnl, avg_hold_time)
    """
    from collections import deque
    
    # Config
    POSITION_SIZE = 0.05  # BTC
    TAKE_PROFIT_PCT = Decimal("0.007")  # 0.7%
    MAX_LOSS_PCT = Decimal("0.01")  # 1.0%
    FEE_PCT = Decimal("0.001")  # 0.1% taker fee
    
    # State
    position = None  # {'side': 'LONG', 'entry': price, 'entry_time': ts, 'qty': qty}
    balance_usdt = Decimal(str(INITIAL_CAPITAL))
    balance_btc = Decimal("0")
    
    trades = []
    
    # Sample prices according to poll interval
    sampled_prices = []
    sampled_timestamps = []
    last_sample_time = timestamps[0]
    
    for i, (ts, price) in enumerate(zip(timestamps, prices)):
        # Sample every poll_sec seconds
        if (ts - last_sample_time) >= (poll_sec * 1000):
            sampled_prices.append(price)
            sampled_timestamps.append(ts)
            last_sample_time = ts
    
    print(f"  Poll {poll_sec}s: {len(sampled_prices)} ticks (from {len(prices)} original)")
    
    # Simple L-line calculation (rolling average)
    window = deque(maxlen=30)
    
    for i, (ts, price) in enumerate(zip(sampled_timestamps, sampled_prices)):
        price_d = Decimal(str(price))
        window.append(price_d)
        
        if len(window) < 30:
            continue
        
        L = sum(window) / len(window)
        
        # Check existing position
        if position:
            entry_price = position['entry']
            side = position['side']
            
            # Calculate P&L
            if side == 'LONG':
                pnl_pct = (price_d - entry_price) / entry_price
                # Exit conditions: TP, SL, or L-cross
                if pnl_pct >= TAKE_PROFIT_PCT:
                    reason = 'TP'
                    exit_trade = True
                elif pnl_pct <= -MAX_LOSS_PCT:
                    reason = 'SL'
                    exit_trade = True
                elif price_d <= L:
                    reason = 'L_CROSS'
                    exit_trade = True
                else:
                    exit_trade = False
            else:  # SHORT
                pnl_pct = (entry_price - price_d) / entry_price
                # Exit conditions
                if pnl_pct >= TAKE_PROFIT_PCT:
                    reason = 'TP'
                    exit_trade = True
                elif pnl_pct <= -MAX_LOSS_PCT:
                    reason = 'SL'
                    exit_trade = True
                elif price_d >= L:
                    reason = 'L_CROSS'
                    exit_trade = True
                else:
                    exit_trade = False
            
            if exit_trade:
                # Calculate actual P&L with fees
                qty = position['qty']
                entry_value = entry_price * qty
                exit_value = price_d * qty
                
                if side == 'LONG':
                    # Buy fee + Sell fee
                    entry_fee = entry_value * FEE_PCT
                    exit_fee = exit_value * FEE_PCT
                    pnl = exit_value - entry_value - entry_fee - exit_fee
                else:  # SHORT
                    # Sell fee + Buy fee
                    entry_fee = entry_value * FEE_PCT
                    exit_fee = exit_value * FEE_PCT
                    pnl = entry_value - exit_value - entry_fee - exit_fee
                
                hold_time = (ts - position['entry_time']) / 1000  # seconds
                
                trades.append({
                    'side': side,
                    'entry': float(entry_price),
                    'exit': float(price_d),
                    'pnl_pct': float(pnl_pct * 100),
                    'pnl_usdt': float(pnl),
                    'reason': reason,
                    'hold_time': hold_time
                })
                
                balance_usdt += pnl
                position = None
        
        # Entry logic (if no position)
        if not position:
            # Simple trend detection: price vs L
            if price_d > L:
                # LONG entry
                side = 'LONG'
                qty = Decimal(str(POSITION_SIZE))
                entry_value = price_d * qty
                entry_fee = entry_value * FEE_PCT
                
                if balance_usdt >= (entry_value + entry_fee):
                    balance_usdt -= (entry_value + entry_fee)
                    position = {
                        'side': side,
                        'entry': price_d,
                        'entry_time': ts,
                        'qty': qty
                    }
            elif price_d < L:
                # SHORT entry (futures-style)
                side = 'SHORT'
                qty = Decimal(str(POSITION_SIZE))
                entry_value = price_d * qty
                margin_required = entry_value * Decimal("0.5")  # 2x leverage
                
                if balance_usdt >= margin_required:
                    position = {
                        'side': side,
                        'entry': price_d,
                        'entry_time': ts,
                        'qty': qty
                    }
    
    # Calculate metrics
    if not trades:
        return {
            'poll_sec': poll_sec,
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'final_balance': float(balance_usdt),
            'avg_hold_time': 0,
            'trades_per_day': 0
        }
    
    wins = [t for t in trades if t['pnl_usdt'] > 0]
    losses = [t for t in trades if t['pnl_usdt'] < 0]
    
    total_pnl = sum(t['pnl_usdt'] for t in trades)
    avg_hold_time = sum(t['hold_time'] for t in trades) / len(trades)
    
    # Calculate trades per day
    duration_days = (sampled_timestamps[-1] - sampled_timestamps[0]) / (1000 * 86400)
    trades_per_day = len(trades) / duration_days if duration_days > 0 else 0
    
    return {
        'poll_sec': poll_sec,
        'total_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': len(wins) / len(trades) * 100,
        'total_pnl': total_pnl,
        'final_balance': float(balance_usdt),
        'avg_hold_time': avg_hold_time,
        'trades_per_day': trades_per_day
    }

# Run tests
print("=" * 80)
print("🧪 TESTING DIFFERENT POLL INTERVALS")
print("=" * 80)
print()

results = []

for poll_sec in POLL_INTERVALS:
    print(f"Testing poll_sec = {poll_sec}s...")
    result = simulate_strategy(poll_sec, prices, timestamps)
    results.append(result)
    print()

# Display results
print("=" * 80)
print("📊 RESULTS SUMMARY")
print("=" * 80)
print()

print(f"{'Poll':<6} {'Trades':<8} {'Wins':<6} {'Loss':<6} {'WinRate':<8} {'PnL':<10} {'Balance':<10} {'AvgHold':<10} {'Trades/Day':<12}")
print("-" * 80)

for r in results:
    print(f"{r['poll_sec']}s    "
          f"{r['total_trades']:<8} "
          f"{r['wins']:<6} "
          f"{r['losses']:<6} "
          f"{r['win_rate']:<7.1f}% "
          f"${r['total_pnl']:<9.2f} "
          f"${r['final_balance']:<9.2f} "
          f"{r['avg_hold_time']/60:<9.1f}m "
          f"{r['trades_per_day']:<11.1f}")

print()

# Find best configuration
best = max(results, key=lambda x: x['total_pnl'])
print(f"🏆 BEST PERFORMANCE: poll_sec = {best['poll_sec']}s")
print(f"   Total P&L: ${best['total_pnl']:.2f}")
print(f"   Win Rate: {best['win_rate']:.1f}%")
print(f"   Avg Hold: {best['avg_hold_time']/60:.1f} minutes")
print(f"   Trades/Day: {best['trades_per_day']:.1f}")
print()

# Recommendations
print("=" * 80)
print("💡 RECOMMENDATIONS")
print("=" * 80)
print()

if best['poll_sec'] <= 2:
    print("⚠️  WARNING: Very short poll interval detected!")
    print("   - High frequency trading creates many small trades")
    print("   - In real trading, this increases:")
    print("     • Slippage costs")
    print("     • Network latency issues")
    print("     • API rate limits")
    print("   - Consider using 5s or higher for live trading")
    print()

if best['trades_per_day'] > 100:
    print("⚠️  WARNING: Very high trading frequency!")
    print(f"   - {best['trades_per_day']:.0f} trades/day may not be sustainable")
    print("   - Real-world considerations:")
    print("     • Binance has rate limits")
    print("     • Higher slippage on frequent trades")
    print("     • Psychological fatigue from monitoring")
    print()

print("✅ OPTIMAL CONFIGURATION:")
# Find good balance between profit and practicality
practical = [r for r in results if r['poll_sec'] >= 5 and r['trades_per_day'] < 50]
if practical:
    recommended = max(practical, key=lambda x: x['total_pnl'])
    print(f"   poll_sec: {recommended['poll_sec']}s")
    print(f"   Expected P&L: ${recommended['total_pnl']:.2f}")
    print(f"   Win Rate: {recommended['win_rate']:.1f}%")
    print(f"   Trades/Day: {recommended['trades_per_day']:.1f}")
else:
    print(f"   poll_sec: {best['poll_sec']}s (best profit)")
    print("   Note: Consider practical limitations for live trading")

print()
print("=" * 80)
