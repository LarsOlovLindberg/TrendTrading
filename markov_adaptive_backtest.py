#!/usr/bin/env python3
"""
MARKOV ADAPTIVE STRATEGY BACKTEST
==================================
Backtesting av hybrid-strategin som växlar mellan:
- BREAKOUT mode (följer trends)
- MEAN_REVERSION mode (satsar på återgång till medelvärde)

Strategin använder 6 olika trend-metriker för att besluta vilket mode som är bäst.
"""

import json
import time
import sys
from decimal import Decimal
from datetime import datetime, timezone
from collections import deque
from typing import Optional, Tuple, List, Dict
import matplotlib.pyplot as plt

# ----------------------- Configuration ---------------------------------------
CONFIG_FILE = "config.json"

# Läs config
try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        cfg = json.load(f)
except FileNotFoundError:
    print(f"❌ {CONFIG_FILE} saknas!")
    sys.exit(1)

# Parametrar från config
SYMBOL = cfg.get("symbol", "BTCUSDT")
ORDER_QTY = Decimal(str(cfg.get("order_quantity", 0.001)))
TP_PCT = Decimal(str(cfg.get("take_profit_pct", 0.025)))
MAX_LOSS_PCT = Decimal(str(cfg.get("max_loss_pct", 0.015)))
MAX_HOLD_SEC = cfg.get("max_hold_seconds", 1800)
SCALE_IN_FACTOR = Decimal(str(cfg.get("scale_in_factor", 1.5)))
SCALE_OUT_FACTOR = Decimal(str(cfg.get("scale_out_factor", 0.5)))

# Initial balances
INITIAL_USDT = Decimal(str(cfg.get("initial_usdt", 5000.0)))
INITIAL_BTC = Decimal(str(cfg.get("initial_btc", 0.05)))

# Adaptive mode parameters
MODE_SWITCH_COOLDOWN = cfg.get("mode_switch_cooldown", 5.0)
TREND_WINDOW_SIZE = cfg.get("trend_window_size", 50)
HYSTERESIS = cfg.get("hysteresis", 0.05)
FORCE_EXIT_ON_MODE_SWITCH = cfg.get("force_exit_on_mode_switch", True)

print(f"""
╔═══════════════════════════════════════════════════════════════╗
║  MARKOV ADAPTIVE STRATEGY BACKTEST                            ║
║  Symbol: {SYMBOL}                                             ║
║  Trend Window: {TREND_WINDOW_SIZE} ticks                      ║
║  Mode Switch Cooldown: {MODE_SWITCH_COOLDOWN}s                ║
║  Force Exit on Mode Switch: {FORCE_EXIT_ON_MODE_SWITCH}       ║
╚═══════════════════════════════════════════════════════════════╝
""")

# ----------------------- Trend Detection Module ------------------------------
class TrendDetector:
    """
    Beräknar trend strength från 0.0 (ingen trend) till 1.0 (stark trend)
    Använder 6 olika metriker för bästa precision
    """
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.price_history: deque = deque(maxlen=window_size)
        self.weights = {
            'directional_consistency': 0.25,
            'regression_r2': 0.20,
            'adx_strength': 0.20,
            'trend_structure': 0.15,
            'ma_separation': 0.12,
            'volatility_ratio': 0.08
        }
    
    def add_price(self, price: Decimal) -> None:
        self.price_history.append(float(price))
    
    def calculate_trend_strength(self) -> float:
        if len(self.price_history) < self.window_size:
            return 0.5
        
        prices = list(self.price_history)
        
        # 1. Directional Consistency
        moves = [prices[i+1] - prices[i] for i in range(len(prices)-1)]
        ups = sum(1 for m in moves if m > 0)
        consistency = abs(2 * ups / len(moves) - 1) if moves else 0
        
        # 2. Linear Regression R²
        n = len(prices)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(prices) / n
        
        numerator = sum((x[i] - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator_x = sum((x[i] - x_mean) ** 2 for i in range(n))
        denominator_y = sum((prices[i] - y_mean) ** 2 for i in range(n))
        
        if denominator_x > 0 and denominator_y > 0:
            r = numerator / (denominator_x ** 0.5 * denominator_y ** 0.5)
            r2 = r ** 2
        else:
            r2 = 0
        
        # 3. ADX-like strength
        true_ranges = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
        avg_tr = sum(true_ranges) / len(true_ranges) if true_ranges else 1
        
        directional_moves = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        avg_dir_move = abs(sum(directional_moves) / len(directional_moves)) if directional_moves else 0
        
        adx = min(avg_dir_move / avg_tr, 1.0) if avg_tr > 0 else 0
        
        # 4. Trend Structure (Higher Highs & Lower Lows)
        highs = [prices[i] for i in range(1, len(prices)-1) 
                if prices[i] >= prices[i-1] and prices[i] >= prices[i+1]]
        lows = [prices[i] for i in range(1, len(prices)-1)
               if prices[i] <= prices[i-1] and prices[i] <= prices[i+1]]
        
        hh_count = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i-1])
        ll_count = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i-1])
        
        total_pivots = len(highs) + len(lows)
        structure = abs(hh_count - ll_count) / total_pivots if total_pivots > 0 else 0
        
        # 5. MA Separation
        ma_fast = sum(prices[-10:]) / 10
        ma_slow = sum(prices) / len(prices)
        separation = abs(ma_fast - ma_slow) / ma_slow if ma_slow != 0 else 0
        separation = min(separation * 10, 1.0)
        
        # 6. Volatility Ratio
        intrabar_vol = sum(abs(prices[i] - prices[i-1]) for i in range(1, len(prices)))
        range_vol = max(prices) - min(prices)
        vol_ratio = 1 - (intrabar_vol / (range_vol * len(prices))) if range_vol > 0 else 0
        vol_ratio = max(0, min(vol_ratio, 1.0))
        
        # Weighted sum
        trend_strength = (
            self.weights['directional_consistency'] * consistency +
            self.weights['regression_r2'] * r2 +
            self.weights['adx_strength'] * adx +
            self.weights['trend_structure'] * structure +
            self.weights['ma_separation'] * separation +
            self.weights['volatility_ratio'] * vol_ratio
        )
        
        return max(0.0, min(1.0, trend_strength))

# ----------------------- Strategy Mode Manager -------------------------------
class StrategyModeManager:
    """
    Hanterar byte mellan BREAKOUT och MEAN_REVERSION modes
    """
    def __init__(self, threshold: float = 0.50, hysteresis: float = 0.05, 
                 cooldown: float = 30.0):
        self.threshold = threshold
        self.hysteresis = hysteresis
        self.cooldown = cooldown
        self.current_mode = "BREAKOUT"
        self.last_switch_time = 0.0
        self.mode_changes = []
    
    def update_mode(self, trend_strength: float, current_time: float) -> Tuple[str, bool]:
        """
        Uppdatera mode baserat på trend strength
        Returns: (current_mode, mode_changed)
        """
        time_since_switch = current_time - self.last_switch_time
        
        if time_since_switch < self.cooldown:
            return (self.current_mode, False)
        
        mode_changed = False
        
        if self.current_mode == "BREAKOUT":
            if trend_strength < (self.threshold - self.hysteresis):
                self.current_mode = "MEAN_REVERSION"
                mode_changed = True
        else:  # MEAN_REVERSION
            if trend_strength > (self.threshold + self.hysteresis):
                self.current_mode = "BREAKOUT"
                mode_changed = True
        
        if mode_changed:
            self.last_switch_time = current_time
            self.mode_changes.append({
                'time': current_time,
                'from_mode': "MEAN_REVERSION" if self.current_mode == "BREAKOUT" else "BREAKOUT",
                'to_mode': self.current_mode,
                'trend_strength': trend_strength
            })
        
        return (self.current_mode, mode_changed)
    
    def get_mode_color(self) -> str:
        return 'orange' if self.current_mode == "BREAKOUT" else 'cyan'

# ----------------------- Position Tracker ------------------------------------
class Position:
    def __init__(self):
        self.side: str = "FLAT"
        self.entry: Optional[Decimal] = None
        self.qty: Decimal = Decimal("0")
        self.entry_time: Optional[float] = None
        self.high: Optional[Decimal] = None
        self.low: Optional[Decimal] = None
        self.total_cost: Decimal = Decimal("0")
    
    def flat(self):
        self.side = "FLAT"
        self.entry = None
        self.qty = Decimal("0")
        self.entry_time = None
        self.high = None
        self.low = None
        self.total_cost = Decimal("0")
    
    def avg_entry_price(self) -> Decimal:
        if self.qty > 0:
            return self.total_cost / self.qty
        return self.entry if self.entry else Decimal("0")
    
    def update_extremes(self, price: Decimal):
        if self.high is None or price > self.high:
            self.high = price
        if self.low is None or price < self.low:
            self.low = price

# ----------------------- Paper Account ---------------------------------------
class PaperAccount:
    def __init__(self, initial_usdt: Decimal, initial_btc: Decimal):
        self.balances = {
            'USDT': initial_usdt,
            'BTC': initial_btc
        }
        self.trades = []
    
    def market_buy(self, symbol: str, qty: Decimal, price: Decimal):
        cost = qty * price
        if self.balances['USDT'] >= cost:
            self.balances['USDT'] -= cost
            self.balances['BTC'] += qty
            return True
        return False
    
    def market_sell(self, symbol: str, qty: Decimal, price: Decimal):
        if self.balances['BTC'] >= qty:
            self.balances['BTC'] -= qty
            self.balances['USDT'] += qty * price
            return True
        return False
    
    def log_exit(self, state: str, side: str, symbol: str, qty: Decimal,
                 exit_price: Decimal, entry_price: Decimal) -> Tuple[Decimal, Decimal]:
        if entry_price == 0:
            return (Decimal("0"), Decimal("0"))
        
        if side == "LONG":
            pnl_pct = (exit_price - entry_price) / entry_price * Decimal("100")
        else:
            pnl_pct = (entry_price - exit_price) / entry_price * Decimal("100")
        
        pnl_usd = (qty * entry_price) * (pnl_pct / Decimal("100"))
        
        self.trades.append({
            'side': side,
            'state': state,
            'entry': float(entry_price),
            'exit': float(exit_price),
            'pnl_pct': float(pnl_pct),
            'pnl_usd': float(pnl_usd)
        })
        
        return (pnl_usd, pnl_pct)

# ----------------------- Load Historical Data --------------------------------
def load_historical_data(filename: str = "data/btc_1m_sample.json") -> List[Dict]:
    """Load historical price data from JSON file"""
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        print(f"✅ Loaded {len(data)} data points from {filename}")
        return data
    except FileNotFoundError:
        print(f"❌ File not found: {filename}")
        print("Creating sample data...")
        # Generate sample data if file doesn't exist
        import random
        base_price = 67000.0
        data = []
        for i in range(10000):
            base_price += random.uniform(-100, 100)
            data.append({
                'timestamp': 1700000000 + i * 60,
                'open': base_price,
                'high': base_price + random.uniform(0, 50),
                'low': base_price - random.uniform(0, 50),
                'close': base_price + random.uniform(-30, 30),
                'volume': random.uniform(1, 10)
            })
        return data

# ----------------------- Backtest Strategy -----------------------------------
def run_backtest():
    # Load data
    data = load_historical_data()
    
    if not data:
        print("❌ No data to backtest")
        return
    
    # Initialize
    paper = PaperAccount(INITIAL_USDT, INITIAL_BTC)
    pos = Position()
    trend_detector = TrendDetector(TREND_WINDOW_SIZE)
    mode_manager = StrategyModeManager(
        threshold=0.50,
        hysteresis=HYSTERESIS,
        cooldown=MODE_SWITCH_COOLDOWN
    )
    
    L = Decimal(str(data[0]['close']))
    
    # Tracking
    prices = []
    L_values = []
    balances = []
    modes = []
    
    print("\n🔄 Running backtest...")
    
    for i, candle in enumerate(data):
        price = Decimal(str(candle['close']))
        current_time = float(candle['timestamp'])
        
        prices.append(float(price))
        L_values.append(float(L))
        
        # Update trend detector
        trend_detector.add_price(price)
        
        # Check mode switch every tick
        if len(trend_detector.price_history) >= trend_detector.window_size:
            trend_strength = trend_detector.calculate_trend_strength()
            current_mode, mode_changed = mode_manager.update_mode(trend_strength, current_time)
            modes.append(current_mode)
            
            # Force exit on mode switch
            if mode_changed and FORCE_EXIT_ON_MODE_SWITCH and pos.side != "FLAT":
                qty = pos.qty if pos.qty > 0 else ORDER_QTY
                if pos.side == "LONG":
                    paper.market_sell(SYMBOL, qty, price)
                else:
                    paper.market_buy(SYMBOL, qty, price)
                
                paper.log_exit("MODE_SWITCH", pos.side, SYMBOL, qty, price, pos.avg_entry_price())
                pos.flat()
                L = price
        else:
            modes.append("BREAKOUT")
        
        # Update position extremes
        if pos.side != "FLAT":
            pos.update_extremes(price)
        
        # Entry logic
        if pos.side == "FLAT":
            current_mode = mode_manager.current_mode
            
            if price > L:
                if current_mode == "BREAKOUT":
                    # LONG
                    paper.market_buy(SYMBOL, ORDER_QTY, price)
                    pos.side = "LONG"
                    pos.entry = price
                    pos.qty = ORDER_QTY
                    pos.entry_time = current_time
                    pos.total_cost = ORDER_QTY * price
                    pos.high = price
                    pos.low = price
                else:
                    # SHORT
                    paper.market_sell(SYMBOL, ORDER_QTY, price)
                    pos.side = "SHORT"
                    pos.entry = price
                    pos.qty = ORDER_QTY
                    pos.entry_time = current_time
                    pos.total_cost = ORDER_QTY * price
                    pos.high = price
                    pos.low = price
            
            elif price < L:
                if current_mode == "BREAKOUT":
                    # SHORT
                    paper.market_sell(SYMBOL, ORDER_QTY, price)
                    pos.side = "SHORT"
                    pos.entry = price
                    pos.qty = ORDER_QTY
                    pos.entry_time = current_time
                    pos.total_cost = ORDER_QTY * price
                    pos.high = price
                    pos.low = price
                else:
                    # LONG
                    paper.market_buy(SYMBOL, ORDER_QTY, price)
                    pos.side = "LONG"
                    pos.entry = price
                    pos.qty = ORDER_QTY
                    pos.entry_time = current_time
                    pos.total_cost = ORDER_QTY * price
                    pos.high = price
                    pos.low = price
        
        # Exit logic
        if pos.side == "LONG" and pos.entry:
            current_mode = mode_manager.current_mode
            qty = pos.qty if pos.qty > 0 else ORDER_QTY
            
            if current_mode == "BREAKOUT":
                tp_target = pos.avg_entry_price() * (Decimal("1") + TP_PCT)
                if price >= tp_target:
                    paper.market_sell(SYMBOL, qty, price)
                    paper.log_exit("LW", "LONG", SYMBOL, qty, price, pos.avg_entry_price())
                    L = price
                    pos.flat()
                elif price <= L:
                    paper.market_sell(SYMBOL, qty, price)
                    paper.log_exit("LB", "LONG", SYMBOL, qty, price, pos.avg_entry_price())
                    L = price
                    pos.flat()
            else:  # MEAN_REVERSION
                if price >= L:
                    paper.market_sell(SYMBOL, qty, price)
                    paper.log_exit("LW", "LONG", SYMBOL, qty, price, pos.avg_entry_price())
                    L = price
                    pos.flat()
        
        elif pos.side == "SHORT" and pos.entry:
            current_mode = mode_manager.current_mode
            qty = pos.qty if pos.qty > 0 else ORDER_QTY
            
            if current_mode == "BREAKOUT":
                tp_target = pos.avg_entry_price() * (Decimal("1") - TP_PCT)
                if price <= tp_target:
                    paper.market_buy(SYMBOL, qty, price)
                    paper.log_exit("SW", "SHORT", SYMBOL, qty, price, pos.avg_entry_price())
                    L = price
                    pos.flat()
                elif price >= L:
                    paper.market_buy(SYMBOL, qty, price)
                    paper.log_exit("SB", "SHORT", SYMBOL, qty, price, pos.avg_entry_price())
                    L = price
                    pos.flat()
            else:  # MEAN_REVERSION
                if price <= L:
                    paper.market_buy(SYMBOL, qty, price)
                    paper.log_exit("SW", "SHORT", SYMBOL, qty, price, pos.avg_entry_price())
                    L = price
                    pos.flat()
        
        # Track balance
        current_btc = float(paper.balances['BTC'])
        current_usdt = float(paper.balances['USDT'])
        total_value = current_usdt + (current_btc * float(price))
        balances.append(total_value)
        
        if i % 1000 == 0:
            print(f"  Progress: {i}/{len(data)} ({i/len(data)*100:.1f}%)")
    
    # Results
    print("\n" + "="*70)
    print("BACKTEST RESULTS")
    print("="*70)
    
    initial_total = float(INITIAL_USDT) + (float(INITIAL_BTC) * float(data[0]['close']))
    final_total = balances[-1]
    total_return = ((final_total - initial_total) / initial_total) * 100
    
    print(f"\nInitial Balance: ${initial_total:.2f}")
    print(f"Final Balance:   ${final_total:.2f}")
    print(f"Total Return:    {total_return:+.2f}%")
    
    print(f"\nTotal Trades: {len(paper.trades)}")
    
    if paper.trades:
        wins = [t for t in paper.trades if t['pnl_pct'] > 0]
        losses = [t for t in paper.trades if t['pnl_pct'] < 0]
        
        win_rate = (len(wins) / len(paper.trades)) * 100
        avg_win = sum(t['pnl_pct'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl_pct'] for t in losses) / len(losses) if losses else 0
        
        print(f"Wins: {len(wins)} ({win_rate:.1f}%)")
        print(f"Losses: {len(losses)}")
        print(f"Avg Win: {avg_win:+.2f}%")
        print(f"Avg Loss: {avg_loss:+.2f}%")
        
        # Mode switches
        print(f"\nMode Switches: {len(mode_manager.mode_changes)}")
        breakout_trades = [t for t in paper.trades if modes[paper.trades.index(t)] == "BREAKOUT"]
        reversion_trades = [t for t in paper.trades if modes[paper.trades.index(t)] == "MEAN_REVERSION"]
        
        if breakout_trades:
            breakout_win_rate = (len([t for t in breakout_trades if t['pnl_pct'] > 0]) / len(breakout_trades)) * 100
            print(f"  BREAKOUT mode: {len(breakout_trades)} trades, {breakout_win_rate:.1f}% win rate")
        
        if reversion_trades:
            reversion_win_rate = (len([t for t in reversion_trades if t['pnl_pct'] > 0]) / len(reversion_trades)) * 100
            print(f"  MEAN_REVERSION mode: {len(reversion_trades)} trades, {reversion_win_rate:.1f}% win rate")
    
    # Plot results
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    
    # Price and L
    ax1.plot(prices, label='Price', color='blue', alpha=0.7)
    ax1.plot(L_values, label='L', color='orange', linestyle='--')
    ax1.set_ylabel('Price')
    ax1.set_title(f'{SYMBOL} - Adaptive Strategy Backtest')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Balance
    ax2.plot(balances, label='Total Balance (USDT)', color='green')
    ax2.axhline(y=initial_total, color='gray', linestyle='--', label='Initial Balance')
    ax2.set_ylabel('Balance (USDT)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Modes
    mode_colors = ['orange' if m == "BREAKOUT" else 'cyan' for m in modes]
    ax3.scatter(range(len(modes)), [1 if m == "BREAKOUT" else 0 for m in modes], 
                c=mode_colors, alpha=0.3, s=1)
    ax3.set_ylabel('Mode')
    ax3.set_yticks([0, 1])
    ax3.set_yticklabels(['MEAN_REVERSION', 'BREAKOUT'])
    ax3.set_xlabel('Time (ticks)')
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('backtest_results.png', dpi=150)
    print("\n📊 Results saved to: backtest_results.png")
    plt.show()

# ----------------------- Main ------------------------------------------------
if __name__ == "__main__":
    try:
        run_backtest()
    except KeyboardInterrupt:
        print("\n\n⏹️  Backtest interrupted")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
