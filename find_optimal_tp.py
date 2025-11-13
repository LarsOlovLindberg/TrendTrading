#!/usr/bin/env python3
"""
OPTIMAL TP FINDER
=================
Analyserar historisk data för att hitta optimalt Take Profit %.
Tittar på faktiska prisrörelser och hittar den TP som ger:
1. Högst win rate
2. Bäst risk/reward ratio
3. Mest frekventa hits
"""

import json
import sys
from decimal import Decimal
from collections import deque
import matplotlib.pyplot as plt
import numpy as np

# Kopiera klasser från backtest (enklare än import)
import importlib.util
spec = importlib.util.spec_from_file_location("backtest", "markov_adaptive_backtest.py")
backtest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backtest)

TrendDetector = backtest.TrendDetector
StrategyModeManager = backtest.StrategyModeManager  
Position = backtest.Position
PaperAccount = backtest.PaperAccount

def load_data():
    """Generate realistic BTC price data"""
    import random
    random.seed(42)  # Reproducible
    
    base_price = 67000.0
    data = []
    
    # Simulate more realistic price action with trends and reversions
    trend_direction = 1
    trend_strength = 0
    
    for i in range(10000):
        # Change trend periodically
        if i % 500 == 0:
            trend_direction = random.choice([-1, 1])
            trend_strength = random.uniform(0.5, 2.0)
        
        # Add trend component + noise
        trend_move = trend_direction * trend_strength * random.uniform(0, 50)
        noise = random.uniform(-100, 100)
        base_price += trend_move + noise
        
        # Keep price reasonable
        base_price = max(60000, min(75000, base_price))
        
        high = base_price + random.uniform(0, 100)
        low = base_price - random.uniform(0, 100)
        close = base_price + random.uniform(-50, 50)
        
        data.append({
            'timestamp': 1700000000 + i * 60,
            'open': base_price,
            'high': high,
            'low': low,
            'close': close,
            'volume': random.uniform(1, 10)
        })
    
    return data

def analyze_price_moves(data):
    """Analyze actual price movements to find realistic TP levels"""
    print("📊 Analyzing price movements...\n")
    
    moves = []
    for i in range(1, len(data)):
        prev_close = data[i-1]['close']
        curr_close = data[i]['close']
        curr_high = data[i]['high']
        curr_low = data[i]['low']
        
        # Calculate potential gains if we entered at prev_close
        long_gain = (curr_high - prev_close) / prev_close
        short_gain = (prev_close - curr_low) / prev_close
        
        moves.append({
            'long_gain': long_gain,
            'short_gain': short_gain,
            'actual_close': (curr_close - prev_close) / prev_close
        })
    
    # Calculate percentiles
    long_gains = [m['long_gain'] for m in moves]
    short_gains = [m['short_gain'] for m in moves]
    
    print("LONG Potential (% gains if entered at prev close):")
    for pct in [50, 75, 90, 95, 99]:
        val = np.percentile(long_gains, pct) * 100
        print(f"  {pct}th percentile: {val:.3f}%")
    
    print("\nSHORT Potential (% gains if entered at prev close):")
    for pct in [50, 75, 90, 95, 99]:
        val = np.percentile(short_gains, pct) * 100
        print(f"  {pct}th percentile: {val:.3f}%")
    
    return moves

def test_tp_level(data, tp_pct, max_hold=30):
    """Test a specific TP level and calculate win rate"""
    SYMBOL = "BTCUSDT"
    ORDER_QTY = Decimal("0.001")
    INITIAL_USDT = Decimal("5000.0")
    INITIAL_BTC = Decimal("0.05")
    TREND_WINDOW_SIZE = 50
    
    paper = PaperAccount(INITIAL_USDT, INITIAL_BTC)
    pos = Position()
    trend_detector = TrendDetector(TREND_WINDOW_SIZE)
    mode_manager = StrategyModeManager(threshold=0.45, hysteresis=0.03, cooldown=3.0)
    
    L = Decimal(str(data[0]['close']))
    
    total_trades = 0
    winning_trades = 0
    tp_hits = 0
    sl_hits = 0
    time_exits = 0
    mode_exits = 0
    
    for i, candle in enumerate(data):
        price = Decimal(str(candle['close']))
        current_time = candle.get('timestamp', i * 60)
        trend_detector.add_price(price)
        
        if len(trend_detector.price_history) >= TREND_WINDOW_SIZE:
            trend_strength = trend_detector.calculate_trend_strength()
            current_mode, mode_changed = mode_manager.update_mode(trend_strength, current_time)
            
            if mode_changed and pos.side != "FLAT":
                qty = pos.qty if pos.qty > 0 else ORDER_QTY
                entry_price = pos.entry
                pnl_usd, pnl_pct = paper.log_exit("MODE_SWITCH", pos.side, SYMBOL, qty, price, entry_price)
                total_trades += 1
                mode_exits += 1
                if pnl_pct > 0:
                    winning_trades += 1
                pos.flat()
                L = price
        
        # Entry
        if pos.side == "FLAT":
            current_mode = mode_manager.current_mode
            if price > L:
                if current_mode == "BREAKOUT":
                    paper.market_buy(SYMBOL, ORDER_QTY, price)
                    pos.side = "LONG"
                    pos.entry = price
                    pos.qty = ORDER_QTY
                    pos.entry_time = i
                else:
                    paper.market_sell(SYMBOL, ORDER_QTY, price)
                    pos.side = "SHORT"
                    pos.entry = price
                    pos.qty = ORDER_QTY
                    pos.entry_time = i
            elif price < L:
                if current_mode == "BREAKOUT":
                    paper.market_sell(SYMBOL, ORDER_QTY, price)
                    pos.side = "SHORT"
                    pos.entry = price
                    pos.qty = ORDER_QTY
                    pos.entry_time = i
                else:
                    paper.market_buy(SYMBOL, ORDER_QTY, price)
                    pos.side = "LONG"
                    pos.entry = price
                    pos.qty = ORDER_QTY
                    pos.entry_time = i
        
        # Exit logic with TP
        if pos.side != "FLAT" and pos.entry is not None:
            qty = pos.qty if pos.qty > 0 else ORDER_QTY
            entry_price = pos.entry
            hold_time = i - pos.entry_time
            
            # Time-based exit
            if hold_time >= max_hold:
                pnl_usd, pnl_pct = paper.log_exit("TIME", pos.side, SYMBOL, qty, price, entry_price)
                total_trades += 1
                time_exits += 1
                if pnl_pct > 0:
                    winning_trades += 1
                pos.flat()
                L = price
                continue
            
            if pos.side == "LONG":
                tp_target = entry_price * (Decimal("1") + tp_pct)
                if price >= tp_target:
                    pnl_usd, pnl_pct = paper.log_exit("LW", "LONG", SYMBOL, qty, price, entry_price)
                    total_trades += 1
                    winning_trades += 1
                    tp_hits += 1
                    pos.flat()
                    L = price
                elif price <= L:
                    pnl_usd, pnl_pct = paper.log_exit("LB", "LONG", SYMBOL, qty, price, entry_price)
                    total_trades += 1
                    sl_hits += 1
                    pos.flat()
                    L = price
            else:  # SHORT
                tp_target = entry_price * (Decimal("1") - tp_pct)
                if price <= tp_target:
                    pnl_usd, pnl_pct = paper.log_exit("SW", "SHORT", SYMBOL, qty, price, entry_price)
                    total_trades += 1
                    winning_trades += 1
                    tp_hits += 1
                    pos.flat()
                    L = price
                elif price >= L:
                    pnl_usd, pnl_pct = paper.log_exit("SB", "SHORT", SYMBOL, qty, price, entry_price)
                    total_trades += 1
                    sl_hits += 1
                    pos.flat()
                    L = price
    
    # Calculate metrics
    current_usdt = float(paper.balances['USDT'])
    current_btc = float(paper.balances['BTC'])
    final_value = current_usdt + (current_btc * float(price))
    initial_value = float(INITIAL_USDT) + (float(INITIAL_BTC) * float(data[0]['close']))
    return_pct = (final_value - initial_value) / initial_value * 100
    
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    tp_rate = (tp_hits / total_trades * 100) if total_trades > 0 else 0
    
    return {
        'return': return_pct,
        'trades': total_trades,
        'win_rate': win_rate,
        'tp_hits': tp_hits,
        'tp_rate': tp_rate,
        'sl_hits': sl_hits,
        'time_exits': time_exits,
        'mode_exits': mode_exits
    }

def find_optimal_tp():
    """Test different TP levels and find the best one"""
    print("=" * 70)
    print("OPTIMAL TAKE PROFIT FINDER")
    print("=" * 70)
    print()
    
    data = load_data()
    print(f"✅ Generated {len(data)} data points (~{len(data)/1440:.1f} days)\n")
    
    # First, analyze price movements
    analyze_price_moves(data)
    print("\n" + "=" * 70)
    print("TESTING DIFFERENT TP LEVELS")
    print("=" * 70)
    print()
    
    # Test different TP levels
    tp_levels = [0.002, 0.003, 0.004, 0.005, 0.007, 0.010, 0.015, 0.020, 0.025, 0.030]
    results = []
    
    for tp_pct in tp_levels:
        print(f"Testing TP = {tp_pct*100:.2f}%...", end=" ")
        result = test_tp_level(data, Decimal(str(tp_pct)))
        result['tp_pct'] = tp_pct
        results.append(result)
        print(f"✓ Return: {result['return']:+.2f}%, Win: {result['win_rate']:.1f}%, TP Hits: {result['tp_hits']}")
    
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY (sorted by return)")
    print("=" * 70)
    print(f"{'TP %':<8} {'Return':<10} {'Trades':<8} {'Win %':<8} {'TP Hits':<8} {'TP Rate':<8}")
    print("-" * 70)
    
    # Sort by return
    results.sort(key=lambda x: x['return'], reverse=True)
    
    for r in results:
        print(f"{r['tp_pct']*100:>6.2f}%  {r['return']:>+8.2f}%  {r['trades']:>6}   {r['win_rate']:>6.1f}%  {r['tp_hits']:>6}   {r['tp_rate']:>6.1f}%")
    
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    best = results[0]
    print(f"\n🏆 BEST OVERALL RETURN: {best['tp_pct']*100:.2f}%")
    print(f"   Return: {best['return']:+.2f}%")
    print(f"   Trades: {best['trades']}")
    print(f"   Win Rate: {best['win_rate']:.1f}%")
    print(f"   TP Hits: {best['tp_hits']} ({best['tp_rate']:.1f}% of trades)")
    
    # Find highest TP hit rate
    best_tp_rate = max(results, key=lambda x: x['tp_rate'])
    print(f"\n🎯 MOST TP HITS: {best_tp_rate['tp_pct']*100:.2f}%")
    print(f"   TP Hit Rate: {best_tp_rate['tp_rate']:.1f}%")
    print(f"   Return: {best_tp_rate['return']:+.2f}%")
    print(f"   Win Rate: {best_tp_rate['win_rate']:.1f}%")
    
    # Find best win rate
    best_win = max(results, key=lambda x: x['win_rate'])
    print(f"\n✅ HIGHEST WIN RATE: {best_win['tp_pct']*100:.2f}%")
    print(f"   Win Rate: {best_win['win_rate']:.1f}%")
    print(f"   Return: {best_win['return']:+.2f}%")
    print(f"   TP Hits: {best_win['tp_hits']}")
    
    # Plot results
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    tp_vals = [r['tp_pct'] * 100 for r in results]
    
    axes[0, 0].plot(tp_vals, [r['return'] for r in results], 'b-o', linewidth=2)
    axes[0, 0].set_xlabel('Take Profit %')
    axes[0, 0].set_ylabel('Return %')
    axes[0, 0].set_title('Return vs TP Level')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].axhline(y=0, color='r', linestyle='--', alpha=0.5)
    
    axes[0, 1].plot(tp_vals, [r['win_rate'] for r in results], 'g-o', linewidth=2)
    axes[0, 1].set_xlabel('Take Profit %')
    axes[0, 1].set_ylabel('Win Rate %')
    axes[0, 1].set_title('Win Rate vs TP Level')
    axes[0, 1].grid(True, alpha=0.3)
    
    axes[1, 0].plot(tp_vals, [r['tp_hits'] for r in results], 'm-o', linewidth=2)
    axes[1, 0].set_xlabel('Take Profit %')
    axes[1, 0].set_ylabel('TP Hits (count)')
    axes[1, 0].set_title('TP Hits vs TP Level')
    axes[1, 0].grid(True, alpha=0.3)
    
    axes[1, 1].plot(tp_vals, [r['tp_rate'] for r in results], 'c-o', linewidth=2)
    axes[1, 1].set_xlabel('Take Profit %')
    axes[1, 1].set_ylabel('TP Hit Rate %')
    axes[1, 1].set_title('TP Hit Rate vs TP Level')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('optimal_tp_analysis.png', dpi=150)
    print(f"\n📊 Charts saved to: optimal_tp_analysis.png")
    plt.show()

if __name__ == "__main__":
    try:
        find_optimal_tp()
    except KeyboardInterrupt:
        print("\n\n⏹️  Analysis interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
