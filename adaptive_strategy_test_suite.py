#!/usr/bin/env python3
"""
ADAPTIVE STRATEGY TEST SUITE
=============================
Testar strategin med olika konfigurationer för att hitta optimala parametrar.

Testar kombinationer av:
- Trend threshold (0.45, 0.50, 0.55)
- Hysteresis (0.03, 0.05, 0.08)
- Cooldown (3s, 5s, 10s)
- Force exit on mode switch (True/False)
- Take profit % (2%, 2.5%, 3%)
"""

import json
import sys
from decimal import Decimal
from datetime import datetime, timezone
from collections import deque
from typing import Optional, Tuple, List, Dict
import matplotlib.pyplot as plt
import numpy as np

# ----------------------- Configuration ---------------------------------------
CONFIG_FILE = "config.json"

# Parametrar som inte ändras
SYMBOL = "BTCUSDT"
ORDER_QTY = Decimal("0.001")
MAX_LOSS_PCT = Decimal("0.015")
MAX_HOLD_SEC = 1800
SCALE_IN_FACTOR = Decimal("1.5")
SCALE_OUT_FACTOR = Decimal("0.5")
INITIAL_USDT = Decimal("5000.0")
INITIAL_BTC = Decimal("0.05")
TREND_WINDOW_SIZE = 50

# Test configurations
TEST_CONFIGS = [
    # Baseline
    {"name": "Baseline", "threshold": 0.50, "hysteresis": 0.05, "cooldown": 5.0, "force_exit": True, "tp_pct": 0.025},
    
    # Lower threshold (mer switching)
    {"name": "Low_Threshold", "threshold": 0.45, "hysteresis": 0.05, "cooldown": 5.0, "force_exit": True, "tp_pct": 0.025},
    
    # Higher threshold (mindre switching)
    {"name": "High_Threshold", "threshold": 0.55, "hysteresis": 0.05, "cooldown": 5.0, "force_exit": True, "tp_pct": 0.025},
    
    # Tight hysteresis (mer känslig)
    {"name": "Tight_Hysteresis", "threshold": 0.50, "hysteresis": 0.03, "cooldown": 5.0, "force_exit": True, "tp_pct": 0.025},
    
    # Wide hysteresis (mer stabil)
    {"name": "Wide_Hysteresis", "threshold": 0.50, "hysteresis": 0.08, "cooldown": 5.0, "force_exit": True, "tp_pct": 0.025},
    
    # Fast switching
    {"name": "Fast_Switch", "threshold": 0.50, "hysteresis": 0.05, "cooldown": 3.0, "force_exit": True, "tp_pct": 0.025},
    
    # Slow switching
    {"name": "Slow_Switch", "threshold": 0.50, "hysteresis": 0.05, "cooldown": 10.0, "force_exit": True, "tp_pct": 0.025},
    
    # No forced exit on switch
    {"name": "No_Force_Exit", "threshold": 0.50, "hysteresis": 0.05, "cooldown": 5.0, "force_exit": False, "tp_pct": 0.025},
    
    # Higher TP
    {"name": "High_TP", "threshold": 0.50, "hysteresis": 0.05, "cooldown": 5.0, "force_exit": True, "tp_pct": 0.030},
    
    # Lower TP (ta vinst snabbare)
    {"name": "Low_TP", "threshold": 0.50, "hysteresis": 0.05, "cooldown": 5.0, "force_exit": True, "tp_pct": 0.020},
]

# Import classes from backtest file
sys.path.append('.')
from markov_adaptive_backtest import (
    PaperAccount, Position, TrendDetector, StrategyModeManager,
    load_historical_data
)

def run_single_test(config: Dict, data: List[Dict]) -> Dict:
    """Run backtest with specific configuration"""
    
    # Extract config
    threshold = config['threshold']
    hysteresis = config['hysteresis']
    cooldown = config['cooldown']
    force_exit = config['force_exit']
    tp_pct = Decimal(str(config['tp_pct']))
    
    # Initialize
    paper = PaperAccount(INITIAL_USDT, INITIAL_BTC)
    pos = Position()
    trend_detector = TrendDetector(TREND_WINDOW_SIZE)
    mode_manager = StrategyModeManager(
        threshold=threshold,
        hysteresis=hysteresis,
        cooldown=cooldown
    )
    
    L = Decimal(str(data[0]['close']))
    initial_total = float(INITIAL_USDT) + float(INITIAL_BTC) * float(L)
    
    # Tracking
    balances = []
    mode_switches = 0
    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    total_pnl = Decimal("0")
    
    # Backtest loop
    for i, candle in enumerate(data):
        price = Decimal(str(candle['close']))
        trend_detector.add_price(price)
        
        if len(trend_detector.price_history) >= TREND_WINDOW_SIZE:
            trend_strength = trend_detector.calculate_trend_strength()
            current_mode, mode_changed = mode_manager.update_mode(trend_strength)
            
            if mode_changed:
                mode_switches += 1
                if force_exit and pos.side != "FLAT":
                    # Exit on mode switch
                    qty = pos.qty if pos.qty > 0 else ORDER_QTY
                    entry_price = pos.entry
                    pnl_usd, pnl_pct = paper.log_exit("MODE_SWITCH", pos.side, SYMBOL, qty, price, entry_price)
                    total_pnl += pnl_usd
                    total_trades += 1
                    if pnl_pct > 0:
                        winning_trades += 1
                    else:
                        losing_trades += 1
                    pos.flat()
                    L = price
        
        # Entry logic
        if pos.side == "FLAT":
            current_mode = mode_manager.current_mode
            if price > L:
                if current_mode == "BREAKOUT":
                    pos.enter_long(price, ORDER_QTY)
                else:
                    pos.enter_short(price, ORDER_QTY)
            elif price < L:
                if current_mode == "BREAKOUT":
                    pos.enter_short(price, ORDER_QTY)
                else:
                    pos.enter_long(price, ORDER_QTY)
        
        # Exit logic
        if pos.side != "FLAT" and pos.entry is not None:
            qty = pos.qty if pos.qty > 0 else ORDER_QTY
            entry_price = pos.entry
            
            if pos.side == "LONG":
                tp_target = entry_price * (Decimal("1") + tp_pct)
                if price >= tp_target:
                    pnl_usd, pnl_pct = paper.log_exit("LW", "LONG", SYMBOL, qty, price, entry_price)
                    total_pnl += pnl_usd
                    total_trades += 1
                    winning_trades += 1
                    pos.flat()
                    L = price
                elif price <= L:
                    pnl_usd, pnl_pct = paper.log_exit("LB", "LONG", SYMBOL, qty, price, entry_price)
                    total_pnl += pnl_usd
                    total_trades += 1
                    losing_trades += 1
                    pos.flat()
                    L = price
            else:  # SHORT
                tp_target = entry_price * (Decimal("1") - tp_pct)
                if price <= tp_target:
                    pnl_usd, pnl_pct = paper.log_exit("SW", "SHORT", SYMBOL, qty, price, entry_price)
                    total_pnl += pnl_usd
                    total_trades += 1
                    winning_trades += 1
                    pos.flat()
                    L = price
                elif price >= L:
                    pnl_usd, pnl_pct = paper.log_exit("SB", "SHORT", SYMBOL, qty, price, entry_price)
                    total_pnl += pnl_usd
                    total_trades += 1
                    losing_trades += 1
                    pos.flat()
                    L = price
        
        # Track balance
        current_usdt = float(paper.balances['USDT'])
        current_btc = float(paper.balances['BTC'])
        current_price = float(price)
        
        if pos.side == "LONG":
            total_btc = current_btc + float(pos.qty)
            total_value = current_usdt + (total_btc * current_price)
        elif pos.side == "SHORT":
            unrealized_pnl = float(pos.qty) * (float(pos.entry) - current_price)
            total_value = current_usdt + unrealized_pnl + (current_btc * current_price)
        else:
            total_value = current_usdt + (current_btc * current_price)
        
        balances.append(total_value)
    
    # Calculate final metrics
    final_balance = balances[-1]
    total_return_pct = ((final_balance - initial_total) / initial_total) * 100
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        'name': config['name'],
        'config': config,
        'initial_balance': initial_total,
        'final_balance': final_balance,
        'total_return_pct': total_return_pct,
        'total_pnl_usd': float(total_pnl),
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': win_rate,
        'mode_switches': mode_switches,
        'balances': balances
    }

def run_test_suite():
    """Run all test configurations"""
    print("=" * 80)
    print("ADAPTIVE STRATEGY TEST SUITE")
    print("=" * 80)
    
    # Load data
    data = load_historical_data()
    if not data:
        print("❌ No data to test")
        return
    
    print(f"\n📊 Testing on {len(data)} data points")
    print(f"   Period: ~{len(data) / 60 / 24:.1f} days\n")
    
    # Run all tests
    results = []
    for i, config in enumerate(TEST_CONFIGS, 1):
        print(f"[{i}/{len(TEST_CONFIGS)}] Testing: {config['name']}...", end='')
        result = run_single_test(config, data)
        results.append(result)
        print(f" ✓ Return: {result['total_return_pct']:+.2f}%")
    
    # Sort by performance
    results.sort(key=lambda x: x['total_return_pct'], reverse=True)
    
    # Print summary
    print("\n" + "=" * 80)
    print("RESULTS SUMMARY (sorted by performance)")
    print("=" * 80)
    print(f"{'Rank':<5} {'Name':<20} {'Return %':<12} {'Trades':<8} {'Win %':<8} {'Switches':<10}")
    print("-" * 80)
    
    for i, result in enumerate(results, 1):
        print(f"{i:<5} {result['name']:<20} {result['total_return_pct']:>+10.2f}% {result['total_trades']:>6} "
              f"{result['win_rate']:>6.1f}% {result['mode_switches']:>8}")
    
    # Create comparison chart
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # Balance curves
    ax1 = axes[0]
    for result in results:
        ax1.plot(result['balances'], label=result['name'], alpha=0.7)
    ax1.axhline(y=results[0]['initial_balance'], color='gray', linestyle='--', label='Initial Balance')
    ax1.set_title('Balance Comparison - All Configurations', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Time (ticks)')
    ax1.set_ylabel('Balance (USDT)')
    ax1.legend(loc='best', fontsize=8)
    ax1.grid(True, alpha=0.3)
    
    # Performance bar chart
    ax2 = axes[1]
    names = [r['name'] for r in results]
    returns = [r['total_return_pct'] for r in results]
    colors = ['green' if r > 0 else 'red' for r in returns]
    
    bars = ax2.barh(names, returns, color=colors, alpha=0.7)
    ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
    ax2.set_xlabel('Total Return (%)')
    ax2.set_title('Performance Comparison', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='x')
    
    # Add value labels
    for i, (bar, value) in enumerate(zip(bars, returns)):
        ax2.text(value, i, f' {value:+.2f}%', va='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig('test_suite_results.png', dpi=150)
    print("\n📊 Results saved to: test_suite_results.png")
    
    # Print best configuration details
    best = results[0]
    print("\n" + "=" * 80)
    print("BEST CONFIGURATION")
    print("=" * 80)
    print(f"Name:          {best['name']}")
    print(f"Threshold:     {best['config']['threshold']}")
    print(f"Hysteresis:    {best['config']['hysteresis']}")
    print(f"Cooldown:      {best['config']['cooldown']}s")
    print(f"Force Exit:    {best['config']['force_exit']}")
    print(f"Take Profit:   {best['config']['tp_pct']*100:.1f}%")
    print(f"\nReturn:        {best['total_return_pct']:+.2f}%")
    print(f"Total Trades:  {best['total_trades']}")
    print(f"Win Rate:      {best['win_rate']:.1f}%")
    print(f"Mode Switches: {best['mode_switches']}")
    print("=" * 80)
    
    plt.show()

if __name__ == "__main__":
    try:
        run_test_suite()
    except KeyboardInterrupt:
        print("\n\n⏹️  Test suite interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
