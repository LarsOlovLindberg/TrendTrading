# -*- coding: utf-8 -*-
"""
Markov ADAPTIVE – LIVE PRICES + PAPER TRADING (INTELLIGENT HYBRID)
-------------------------------------------------------------------
ADAPTIV STRATEGI: Byter automatiskt mellan BREAKOUT och MEAN REVERSION!

INTELLIGENT MODE SELECTION:
- Analyserar trendstyrka i realtid (0.0-1.0 scale)
- Trendstyrka < 0.55: MEAN_REVERSION mode (satsa på återgång till L)
- Trendstyrka > 0.65: BREAKOUT mode (följ trenden)
- Hysterese (±0.05) förhindrar flapping mellan modes

BREAKOUT MODE (stark trend):
- Entry: LONG vid upp-brott, SHORT vid ner-brott (följ momentum)
- Exit: TP vid fortsatt rörelse, Stop vid återgång till L
- L följer entry-priset (trailing stop)

MEAN REVERSION MODE (svag trend/oscillerande):
- Entry: SHORT vid upp-brott, LONG vid ner-brott (satsa på reversion)
- Exit: TP vid återgång till L, Stop vid fortsatt rörelse från L
- L är target-nivå (korsning = exit)

FEATURES:
- Realtids trendanalys (directional consistency, slope, volatility)
- Progressiv scaling (IN/OUT) fungerar i båda modes
- Visuella mode-indikatorer i grafen (📈 Breakout / 🔄 Reversion)
- Mode-byten markerade på grafen för analys

Kör:
    python "Markov adaptive live paper.py"
"""

from __future__ import annotations
import os
import json
import time
import csv
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional, Literal

# ----------------------- Säker import ----------------------------------------
try:
    import requests  # python -m pip install requests
except ImportError as e:
    raise SystemExit(
        "requests saknas. Kör:\n    python -m pip install requests\n"
        "och starta sedan om skriptet."
    ) from e

# (Valfritt men fint): realtids-graf
import matplotlib.pyplot as plt
from collections import deque

# Adaptive L-module (DIN IDÉ!)
try:
    from adaptive_L import AdaptiveLCalculator
    ADAPTIVE_L_AVAILABLE = True
except ImportError:
    print("⚠️ adaptive_L.py saknas - adaptive L disabled")
    ADAPTIVE_L_AVAILABLE = False

# ----------------------- Trend Detection Module (ENHANCED) -------------------
class TrendDetector:
    """
    FÖRBÄTTRAD trend-analys med 6 olika metriker för högre precision!
    
    Beräknar trend_strength (0.0 - 1.0):
    - 0.0 = Ingen trend / oscillerande marknad → MEAN_REVERSION mode
    - 1.0 = Stark trend → BREAKOUT mode
    
    Metoder:
    1. Directional Consistency - Konsekutiva moves åt samma håll
    2. Linear Regression R² - Hur väl data passar en rät linje
    3. ADX-liknande - Average Directional Movement
    4. Higher Highs/Lower Lows - Trend structure
    5. Moving Average Separation - MA avstånd
    6. Volatility Ratio - Intrabar vs range volatilitet
    """
    
    def __init__(self, window_size: int = 50):
        self.window_size = window_size
        self.price_history: deque = deque(maxlen=window_size)
        # Vikter för varje metrik (summerar till 1.0)
        self.weights = {
            'directional_consistency': 0.25,
            'regression_r2': 0.20,
            'adx_strength': 0.20,
            'trend_structure': 0.15,
            'ma_separation': 0.12,
            'volatility_ratio': 0.08
        }
        
    def add_price(self, price: Decimal) -> None:
        """Lägg till nytt pris i historik"""
        self.price_history.append(float(price))
    
    def calculate_trend_strength(self) -> float:
        """
        FÖRBÄTTRAD beräkning med 6 olika metriker
        
        Returns:
            0.0-1.0 där högre värde = starkare trend
        """
        if len(self.price_history) < 15:  # Behöver mer data för robust analys
            return 0.5
        
        prices = list(self.price_history)
        n = len(prices)
        
        # ========== METRIK 1: Directional Consistency ==========
        # Kollar konsekutiva moves åt samma håll (viktigast!)
        moves = [prices[i] - prices[i-1] for i in range(1, n)]
        if not moves:
            return 0.5
        
        # Räkna längsta sekvens av moves åt samma håll
        max_streak = 1
        current_streak = 1
        for i in range(1, len(moves)):
            if (moves[i] > 0 and moves[i-1] > 0) or (moves[i] < 0 and moves[i-1] < 0):
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        
        # Normalisera: längre streaks = starkare trend
        directional_consistency = min(max_streak / (n * 0.3), 1.0)
        
        # ========== METRIK 2: Linear Regression R² ==========
        # R² visar hur väl data passar en linje (0=ingen fit, 1=perfekt fit)
        x_values = list(range(n))
        x_mean = sum(x_values) / n
        y_mean = sum(prices) / n
        
        numerator = sum((x_values[i] - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            regression_r2 = 0.0
        else:
            slope = numerator / denominator
            intercept = y_mean - slope * x_mean
            
            # Beräkna predicted values
            predictions = [slope * x + intercept for x in x_values]
            
            # R² = 1 - (SS_res / SS_tot)
            ss_res = sum((prices[i] - predictions[i]) ** 2 for i in range(n))
            ss_tot = sum((prices[i] - y_mean) ** 2 for i in range(n))
            
            if ss_tot == 0:
                regression_r2 = 0.0
            else:
                regression_r2 = max(0.0, 1.0 - (ss_res / ss_tot))
        
        # ========== METRIK 3: ADX-liknande Directional Movement ==========
        # Mäter styrkan i riktad rörelse vs total rörelse
        positive_dm = sum(max(moves[i], 0) for i in range(len(moves)))
        negative_dm = sum(abs(min(moves[i], 0)) for i in range(len(moves)))
        total_movement = sum(abs(m) for m in moves)
        
        if total_movement == 0:
            adx_strength = 0.0
        else:
            # Dominans av en riktning
            directional_dominance = abs(positive_dm - negative_dm) / total_movement
            adx_strength = directional_dominance
        
        # ========== METRIK 4: Trend Structure (Higher Highs / Lower Lows) ==========
        # En riktig trend gör högre toppar (uptrend) eller lägre bottnar (downtrend)
        # Dela upp i 4 segment och kolla progression
        segment_size = n // 4
        if segment_size < 2:
            trend_structure = 0.5
        else:
            segments_highs = []
            segments_lows = []
            for i in range(4):
                start = i * segment_size
                end = start + segment_size if i < 3 else n
                if end > start:
                    segment = prices[start:end]
                    segments_highs.append(max(segment))
                    segments_lows.append(min(segment))
            
            # Kolla om highs stiger ELLER lows faller konsekvent
            highs_rising = sum(1 for i in range(1, len(segments_highs)) if segments_highs[i] > segments_highs[i-1])
            lows_falling = sum(1 for i in range(1, len(segments_lows)) if segments_lows[i] < segments_lows[i-1])
            
            # Max 3 steg (4 segment = 3 jämförelser)
            trend_structure = max(highs_rising, lows_falling) / 3.0
        
        # ========== METRIK 5: Moving Average Separation ==========
        # Stora avstånd mellan kort och lång MA = stark trend
        if n >= 20:
            short_ma = sum(prices[-10:]) / 10
            long_ma = sum(prices[-20:]) / 20
            ma_diff_pct = abs(short_ma - long_ma) / long_ma if long_ma > 0 else 0.0
            # Normalisera: 0.5% separation = stark trend
            ma_separation = min(ma_diff_pct / 0.005, 1.0)
        else:
            ma_separation = 0.0
        
        # ========== METRIK 6: Volatility Ratio ==========
        # Trend: Stora moves åt ett håll, små moves åt andra
        # Range: Stora moves åt båda håll
        if len(moves) > 1:
            avg_abs_move = sum(abs(m) for m in moves) / len(moves)
            std_moves = (sum((abs(m) - avg_abs_move) ** 2 for m in moves) / len(moves)) ** 0.5
            
            if avg_abs_move == 0:
                volatility_ratio = 0.0
            else:
                # Låg std relativt mean = konsistent rörelse = trend
                # Hög std relativt mean = choppy = ingen trend
                volatility_ratio = 1.0 - min(std_moves / avg_abs_move, 1.0)
        else:
            volatility_ratio = 0.0
        
        # ========== KOMBINERA ALLA METRIKER ==========
        trend_strength = (
            directional_consistency * self.weights['directional_consistency'] +
            regression_r2 * self.weights['regression_r2'] +
            adx_strength * self.weights['adx_strength'] +
            trend_structure * self.weights['trend_structure'] +
            ma_separation * self.weights['ma_separation'] +
            volatility_ratio * self.weights['volatility_ratio']
        )
        
        return max(0.0, min(1.0, trend_strength))
    
    def get_detailed_metrics(self) -> dict:
        """Returnera alla individuella metriker för debugging"""
        if len(self.price_history) < 15:
            return {}
        
        prices = list(self.price_history)
        n = len(prices)
        moves = [prices[i] - prices[i-1] for i in range(1, n)]
        
        # Beräkna varje metrik
        # (Förenklade versioner för snabb överblick)
        max_streak = 1
        current_streak = 1
        for i in range(1, len(moves)):
            if (moves[i] > 0 and moves[i-1] > 0) or (moves[i] < 0 and moves[i-1] < 0):
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 1
        
        return {
            'price_count': n,
            'max_streak': max_streak,
            'current_price': prices[-1],
            'price_change_pct': ((prices[-1] - prices[0]) / prices[0] * 100) if prices[0] > 0 else 0,
            'price_range': max(prices) - min(prices),
        }
    
    def get_trend_description(self) -> str:
        """Textbeskrivning av nuvarande trend"""
        strength = self.calculate_trend_strength()
        if strength < 0.3:
            return "RANGING/OSCILLATING"
        elif strength < 0.6:
            return "WEAK TREND"
        elif strength < 0.8:
            return "MODERATE TREND"
        else:
            return "STRONG TREND"

# ----------------------- Strategy Mode Manager -------------------------------
class StrategyModeManager:
    """
    Beslutar vilken strategi som ska användas baserat på trend_strength.
    
    Modes:
    - BREAKOUT: Följ trenden (som original) när trend_strength >= threshold
    - MEAN_REVERSION: Satsa på återgång till L när trend_strength < threshold
    
    Implementerar hysterese för att undvika flapping mellan modes.
    """
    
    def __init__(self, threshold: float = 0.6, hysteresis: float = 0.05):
        """
        Args:
            threshold: Gränsvärde för mode-byte (default 0.6)
            hysteresis: Bufferzon för att undvika flapping (default 0.05)
        """
        self.threshold = threshold
        self.hysteresis = hysteresis
        self.current_mode: Literal["BREAKOUT", "MEAN_REVERSION"] = "MEAN_REVERSION"
        self.mode_changes: list = []  # Historia av mode-byten
        self.switch_cooldown_until: float = 0.0
        self.switch_cooldown_seconds: float = 30.0  # Vänta minst 30s mellan byten
    
    def update_mode(self, trend_strength: float) -> tuple[str, bool]:
        """
        Uppdatera mode baserat på trend_strength.
        
        Args:
            trend_strength: Värde 0.0-1.0 från TrendDetector
            
        Returns:
            (current_mode, mode_changed)
        """
        now = time.time()
        
        # Vänta med byte om vi nyligen bytte mode
        if now < self.switch_cooldown_until:
            return self.current_mode, False
        
        mode_changed = False
        old_mode = self.current_mode
        
        # Använd hysterese för att undvika flapping
        if self.current_mode == "BREAKOUT":
            # Byt till MEAN_REVERSION om trend_strength faller under threshold - hysteresis
            if trend_strength < (self.threshold - self.hysteresis):
                self.current_mode = "MEAN_REVERSION"
                mode_changed = True
        else:  # MEAN_REVERSION
            # Byt till BREAKOUT om trend_strength stiger över threshold + hysteresis
            if trend_strength >= (self.threshold + self.hysteresis):
                self.current_mode = "BREAKOUT"
                mode_changed = True
        
        # Logga mode-byten
        if mode_changed:
            change_info = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "from_mode": old_mode,
                "to_mode": self.current_mode,
                "trend_strength": trend_strength
            }
            self.mode_changes.append(change_info)
            self.switch_cooldown_until = now + self.switch_cooldown_seconds
            
            print(f"🔄 MODE SWITCH: {old_mode} → {self.current_mode} (trend={trend_strength:.3f})")
        
        return self.current_mode, mode_changed
    
    def get_mode_color(self) -> str:
        """Returnera färgkod för nuvarande mode"""
        return "orange" if self.current_mode == "BREAKOUT" else "cyan"
    
    def get_mode_symbol(self) -> str:
        """Returnera symbol för nuvarande mode"""
        return "📈" if self.current_mode == "BREAKOUT" else "🔄"
    
    def get_mode_description(self) -> str:
        """Beskrivning av vad nuvarande mode gör"""
        if self.current_mode == "BREAKOUT":
            return "Following trend momentum"
        else:
            return "Betting on mean reversion"

# ----------------------- Konfig ----------------------------------------------
ROOT = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ROOT, "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
    cfg = json.load(f)

SYMBOL         = cfg.get("base_symbol", "BTCUSDT")
ORDER_TEST     = bool(cfg.get("order_test", True))        # True = PAPER MODE
ORDER_QTY      = Decimal(str(cfg.get("order_qty", 0.001))).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

# Strategiparametrar
TP_PCT         = Decimal(str(cfg.get("tp_pct", 0.0010)))       # 0.10%
TAKER_FEE_PCT  = Decimal(str(cfg.get("taker_fee_pct", 0.0004)))# 0.04%
POLL_SEC       = float(cfg.get("poll_sec", 0.5))               # pollingintervall sek

# Finjustering anti-fladder / rearm
REARM_GAP_PCT  = Decimal(str(cfg.get("rearm_gap_pct", 0.0003)))    # krav för ”nytt brott” efter re-arm
MIN_MOVE_PCT   = Decimal(str(cfg.get("min_movement_pct", 0.0001))) # min rörelse för entry

# TP-kedja
TP_CHAIN       = bool(cfg.get("tp_chain", True))
TP_CHAIN_GAP_PCT = Decimal(str(cfg.get("tp_chain_gap_pct", 0.0002)))  # litet extra brott för att kedja vidare
TP_CHAIN_MAX   = int(cfg.get("tp_chain_max", 20))   # säkerhetstak mot oändliga kedjor
COOLDOWN_SEC   = float(cfg.get("cooldown_sec", 0.0))

# Volatilitetsfilter och paus efter förluster
VOL_FILTER     = bool(cfg.get("volatility_filter", False))
VOL_PERIOD     = int(cfg.get("volatility_period", 20))
MIN_VOL        = Decimal(str(cfg.get("min_volatility", 0)))
LOSS_PAUSE_CNT = int(cfg.get("loss_pause_count", 0))
LOSS_PAUSE_SEC = float(cfg.get("loss_pause_sec", 0.0))

# Pause resume percent: använd per-lookahead-mapping om tillgänglig
_pause_resume_map = cfg.get("pause_resume_map", {})
_default_pause_resume = cfg.get("pause_resume_pct", 0.0003)
# För framtida utökning: läs lookahead från config eller analysera runtime
# Här använder vi default om ingen map finns eller ingen explicit lookahead-parameter
_lookahead_key = str(cfg.get("lookahead", 20))  # default lookahead=20 om ej angivet
if _pause_resume_map and _lookahead_key in _pause_resume_map:
    PAUSE_RESUME_PCT = Decimal(str(_pause_resume_map[_lookahead_key]))
else:
    PAUSE_RESUME_PCT = Decimal(str(_default_pause_resume))

REENTRY_BREAK_PCT = Decimal(str(cfg.get("reentry_break_pct", 0.0)))
DIR_BIAS_COUNT    = int(cfg.get("direction_bias_count", 0))

# Adaptive L Configuration (DIN IDÉ!)
ADAPTIVE_L_ENABLED = bool(cfg.get("adaptive_L_enabled", False)) and ADAPTIVE_L_AVAILABLE
if ADAPTIVE_L_ENABLED:
    adaptive_L_calc = AdaptiveLCalculator(
        baseline_window=cfg.get("adaptive_L_baseline_window", 800),
        trend_window=cfg.get("adaptive_L_trend_window", 150),
        trend_detect_window=cfg.get("adaptive_L_detect_window", 50),
        trend_threshold=cfg.get("adaptive_L_trend_threshold", 0.0005),
        max_trend_weight=cfg.get("adaptive_L_max_weight", 0.7)
    )
    ADAPTIVE_L_UPDATE_INTERVAL = int(cfg.get("adaptive_L_update_interval", 10))
    print("🧠 Adaptive L aktiverat!")
else:
    adaptive_L_calc = None
    ADAPTIVE_L_UPDATE_INTERVAL = 0
DIR_BIAS_COOLDOWN = float(cfg.get("direction_bias_cooldown", 0.0))

# Dynamisk positionsstorlek
DYNAMIC_SIZING = cfg.get("dynamic_position_sizing", False)
SIZE_LEVELS = cfg.get("position_size_levels", [1.0, 0.5, 0.25])
SIZE_STEP_LOSSES = int(cfg.get("size_step_losses", 2))
SIZE_RESET_ON_WIN = cfg.get("size_reset_on_win", True)

# Progressiv scaling in/out
PROGRESSIVE_SCALING = cfg.get("progressive_scaling", False)
INITIAL_POS_MULT = Decimal(str(cfg.get("initial_position_multiplier", 1.0)))  # Börja liten!
SCALE_IN_ENABLED = cfg.get("scale_in_enabled", True)
SCALE_IN_LEVELS = [Decimal(str(x)) for x in cfg.get("scale_in_levels", [0.0006, 0.0012])]
SCALE_IN_MULT = Decimal(str(cfg.get("scale_in_multiplier", 1.0)))
MAX_SCALE_MULT = Decimal(str(cfg.get("max_scale_multiplier", 3.0)))
SCALE_OUT_ENABLED = cfg.get("scale_out_enabled", True)
SCALE_OUT_LEVELS = [Decimal(str(x)) for x in cfg.get("scale_out_levels", [0.0003, 0.0006, 0.0009])]
SCALE_OUT_MULT = Decimal(str(cfg.get("scale_out_multiplier", 0.3)))
MIN_SCALE_MULT = Decimal(str(cfg.get("min_scale_multiplier", 0.2)))

# ========== MAX LOSS PROTECTION (KRITISKT!) ==========
# Ingen position får förlora mer än initial investment!
MAX_LOSS_PCT = Decimal(str(cfg.get("max_loss_pct", "1.5")))  # Max 1.5% förlust
MAX_POSITION_TIME_SEC = float(cfg.get("max_position_time_sec", 1800))  # Max 30 min per position
FORCE_EXIT_ON_MODE_SWITCH = bool(cfg.get("force_exit_on_mode_switch", True))  # Exit vid mode-byte

print(f"🛡️ SAFETY: Max loss {MAX_LOSS_PCT}% | Max time {MAX_POSITION_TIME_SEC/60:.0f}min | Force exit on mode switch: {FORCE_EXIT_ON_MODE_SWITCH}")

# Startkapital för PAPER
START_USDT     = Decimal(str(cfg.get("paper_usdt", "10000")))
START_BTC      = Decimal(str(cfg.get("paper_btc",  "0.0")))

# Logg-filer
LOG_DIR        = os.path.join(ROOT, "logs")
ORDERS_CSV     = os.path.join(LOG_DIR, "orders_paper.csv")
SUMMARY_CSV    = os.path.join(LOG_DIR, "session_summary.csv")
TRADE_METRICS_CSV = os.path.join(LOG_DIR, "trade_metrics.csv")
TRADE_METRICS_HEADER = [
    "exit_ts",
    "state",
    "side",
    "entry_price",
    "exit_price",
    "duration_sec",
    "mfe_pct",
    "mae_pct",
    "mfe_abs",
    "mae_abs",
    "high_price",
    "low_price",
    "vol_span_pct",
    "triggered_pause",
    "pause_direction",
    "pause_anchor",
    "pause_resume_pct",
    "pause_timeout_sec",
]
os.makedirs(LOG_DIR, exist_ok=True)

# Börja med riktiga priser
BINANCE_PUBLIC = "https://api.binance.com"

def get_live_price(symbol: str) -> Decimal:
    r = requests.get(f"{BINANCE_PUBLIC}/api/v3/ticker/price",
                     params={"symbol": symbol},
                     timeout=5)
    r.raise_for_status()
    return Decimal(r.json()["price"])

# ----------------------- CSV-hjälp -------------------------------------------
def append_csv_row(path: str, row: list, header: Optional[list] = None) -> None:
    max_retries = 5
    retry_delay = 0.2
    exists = os.path.exists(path)
    for attempt in range(max_retries):
        try:
            with open(path, "a", newline="", encoding="utf-8") as wf:
                cw = csv.writer(wf)
                if (not exists) and header:
                    cw.writerow(header)
                    exists = True
                cw.writerow(row)
            return
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print(f"⚠️ Kan inte skriva till {path} - stäng Excel om den är öppen")
                return
        except Exception as e:
            print(f"⚠️ Loggningsfel för {path}: {e}")
            return

# ----------------------- PaperBroker -----------------------------------------
class PaperBroker:
    """
    Simulerar spot-trades lokalt:
      - MARKET BUY/SELL med taker-avgift
      - Kräver USDT för BUY (LONG), BTC för SELL (SHORT-simulering)
      - Loggar varje order till CSV och skriver EXIT-rader med PnL
    """
    def __init__(self, start_usdt: Decimal, start_btc: Decimal):
        self.start_usdt = start_usdt
        self.balances: Dict[str, Decimal] = {"USDT": start_usdt, "BTC": start_btc}
        if not os.path.exists(ORDERS_CSV):
            append_csv_row(
                ORDERS_CSV,
                [],
                header=["ts","state","side","symbol","qty","price","usdt_delta","btc_delta","pnl_usd","pnl_pct","note"]
            )
        self.exits = 0

    def market_buy(self, symbol: str, qty: Decimal, price: Decimal) -> None:
        cost = (price * qty).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        fee  = (cost * TAKER_FEE_PCT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        total = cost + fee
        if self.balances["USDT"] < total:
            raise RuntimeError(f"Otillräckligt USDT: behöver {total}, har {self.balances['USDT']}")
        self.balances["USDT"] -= total
        self.balances["BTC"]  += qty
        append_csv_row(ORDERS_CSV, [
            datetime.now(timezone.utc).isoformat(timespec="seconds")+"Z",
            "", "BUY", symbol, f"{qty}", f"{price}", f"{-total}", f"{qty}", "", "", "paper"
        ])

    def market_sell(self, symbol: str, qty: Decimal, price: Decimal) -> None:
        if self.balances["BTC"] < qty:
            raise RuntimeError(f"Otillräckligt BTC: behöver {qty}, har {self.balances['BTC']}")
        proceeds = (price * qty).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        fee  = (proceeds * TAKER_FEE_PCT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        net  = proceeds - fee
        self.balances["BTC"]  -= qty
        self.balances["USDT"] += net
        append_csv_row(ORDERS_CSV, [
            datetime.now(timezone.utc).isoformat(timespec="seconds")+"Z",
            "", "SELL", symbol, f"{qty}", f"{price}", f"{net}", f"{-qty}", "", "", "paper"
        ])

    def log_exit(self, state: str, side: str, symbol: str, qty: Decimal,
                 exit_price: Decimal, entry_price: Decimal) -> Tuple[Decimal, Decimal]:
        if side == "LONG":
            pnl_usd = (exit_price - entry_price) * qty
        else:
            pnl_usd = (entry_price - exit_price) * qty
        pnl_pct = (pnl_usd / (entry_price * qty) * Decimal("100")) if entry_price != 0 else Decimal("0")
        append_csv_row(ORDERS_CSV, [
            datetime.now(timezone.utc).isoformat(timespec="seconds")+"Z",
            state, "EXIT", symbol, f"{qty}", f"{exit_price}", "", "", f"{pnl_usd:.8f}", f"{pnl_pct:.6f}", "paper-exit"
        ])
        self.exits += 1
        return pnl_usd, pnl_pct

    def snapshot(self) -> Dict[str, str]:
        return {k: str(v) for k, v in self.balances.items()}

    def session_pnl(self) -> Tuple[Decimal, Decimal]:
        change = self.balances["USDT"] - self.start_usdt
        pct = (change / self.start_usdt * Decimal("100")) if self.start_usdt != 0 else Decimal("0")
        return change.quantize(Decimal("0.0001")), pct.quantize(Decimal("0.0001"))

# ----------------------- Markov-räknare --------------------------------------
class MarkovState:
    STATES = ("LW", "LB", "SW", "SB")

    def __init__(self):
        self.counts = {s: 0 for s in self.STATES}
        self.trans = {s: {t: 0 for t in self.STATES} for s in self.STATES}
        self.prev_state: Optional[str] = None
        max_len = max(2, LOSS_PAUSE_CNT or 0, DIR_BIAS_COUNT or 0)
        self.last_states: deque[str] = deque(maxlen=max_len if max_len > 0 else 2)

    def on_state(self, state: str):
        if state not in self.STATES:
            return
        self.counts[state] += 1
        if self.prev_state is not None and self.prev_state in self.STATES:
            self.trans[self.prev_state][state] += 1
        self.prev_state = state
        self.last_states.append(state)

    def empirical_stationary(self) -> Dict[str, float]:
        total = sum(self.counts.values())
        if total == 0:
            return {s: 0.0 for s in self.STATES}
        return {s: float(self.counts[s]) / float(total) for s in self.STATES}

    def transition_matrix(self) -> list[list[float]]:
        mat = []
        for s in self.STATES:
            row_sum = sum(self.trans[s].values())
            if row_sum == 0:
                mat.append([0.0 for _ in self.STATES])
            else:
                mat.append([self.trans[s][t] / row_sum for t in self.STATES])
        return mat

# ----------------------- Globalt tillstånd -----------------------------------
class Position:
    def __init__(self):
        self.side: Literal["LONG","SHORT","FLAT"] = "FLAT"
        self.entry: Optional[Decimal] = None
        self.qty: Decimal = Decimal("0")
        self.initial_qty: Decimal = Decimal("0")  # För scaling tracking
        self.total_cost: Decimal = Decimal("0")  # Totalt investerat (för avg pris)
        self.tp_chain_count: int = 0
        self.entry_time: float = 0.0
        self.high: Optional[Decimal] = None
        self.low: Optional[Decimal] = None
        self.scaled_in_levels: list = []  # Vilka scale-in nivåer som triggats
        self.scaled_out_levels: list = []  # Vilka scale-out nivåer som triggats
        self.scaled_out_amounts: dict = {}  # Hur mycket som scalades out per nivå

    def flat(self):
        self.side = "FLAT"
        self.entry = None
        self.qty = Decimal("0")
        self.initial_qty = Decimal("0")
        self.total_cost = Decimal("0")
        self.tp_chain_count = 0
        self.entry_time = 0.0
        self.high = None
        self.low = None
        self.scaled_in_levels = []
        self.scaled_out_levels = []
        self.scaled_out_amounts = {}
    
    def avg_entry_price(self) -> Decimal:
        """Beräkna genomsnittligt entry-pris baserat på total cost och qty"""
        if self.qty > 0:
            return self.total_cost / self.qty
        return self.entry if self.entry else Decimal("0")

    def update_extremes(self, price: Decimal) -> None:
        if self.entry is None or self.side == "FLAT":
            return
        if self.high is None or price > self.high:
            self.high = price
        if self.low is None or price < self.low:
            self.low = price
    
    def unrealized_pnl_pct(self, current_price: Decimal) -> Decimal:
        """Beräkna unrealized PnL% baserat på genomsnittligt entry-pris"""
        if self.qty == 0 or self.entry is None:
            return Decimal("0")
        
        avg_entry = self.avg_entry_price()
        if avg_entry == 0:
            return Decimal("0")
        
        if self.side == "LONG":
            return (current_price - avg_entry) / avg_entry * Decimal("100")
        else:  # SHORT
            return (avg_entry - current_price) / avg_entry * Decimal("100")

pos   = Position()
mk    = MarkovState()
paper = PaperBroker(START_USDT, START_BTC)

# Adaptive strategy components (OPTIMERADE VÄRDEN)
# Med 6 förbättrade metriker krävs högre threshold för BREAKOUT
# eftersom detection är mer konservativ (mer pålitlig)
trend_detector = TrendDetector(window_size=50)
mode_manager = StrategyModeManager(
    threshold=0.50,      # Sänkt från 0.6 - lättare att nå BREAKOUT
    hysteresis=0.08      # Ökad från 0.05 - mer stabil, mindre flapping
)
# Nu betyder:
# trend < 0.42 (0.50 - 0.08) = MEAN_REVERSION
# trend > 0.58 (0.50 + 0.08) = BREAKOUT  
# 0.42-0.58 = Hysteresis zone (stannar i current mode)

# Dynamisk positionsstorlek state
position_size_state = {
    "consecutive_losses": 0,
    "current_level_index": 0,
    "current_multiplier": 1.0
}

loss_pause_state: Dict[str, Optional[object]] = {
    "active": False,
    "direction": None,
    "anchor": Decimal("0"),
    "high": Decimal("0"),
    "low": Decimal("0"),
    "resume_at": 0.0,
    "started_at": 0.0,
}

def reset_loss_pause_state() -> None:
    loss_pause_state["active"] = False
    loss_pause_state["direction"] = None
    loss_pause_state["anchor"] = Decimal("0")
    loss_pause_state["high"] = Decimal("0")
    loss_pause_state["low"] = Decimal("0")
    loss_pause_state["resume_at"] = 0.0
    loss_pause_state["started_at"] = 0.0
block_long_until: float = 0.0
block_short_until: float = 0.0
consec_long_losses: int = 0
consec_short_losses: int = 0
last_long_rearm: Decimal = Decimal("0")
last_short_rearm: Decimal = Decimal("0")

print("🔄 Hämtar startpris från Binance...")
START_PRICE = get_live_price(SYMBOL)
last_long_rearm = START_PRICE
last_short_rearm = START_PRICE

# Startband ±0.05% (kan justeras)
START_BAND_PCT = Decimal(str(cfg.get("start_band_pct", 0.0005)))
L_lower = (START_PRICE * (Decimal("1") - START_BAND_PCT)).quantize(Decimal("0.01"))
L_upper = (START_PRICE * (Decimal("1") + START_BAND_PCT)).quantize(Decimal("0.01"))
START_MODE = True
L = START_PRICE  # L uppdateras till entry så fort bandet bryts

print(f"🚀 Startar Markov ADAPTIVE Strategy (paper mode={'ON' if ORDER_TEST else 'OFF'})")
print(f"🧠 Intelligent mode: BREAKOUT (trend ≥0.65) ↔️ MEAN_REVERSION (trend <0.55)")
print(f"🔧 Startpris={START_PRICE:.2f}  Startband: [{L_lower:.2f}, {L_upper:.2f}]  för {SYMBOL}")
print(f"📡 Polling: {POLL_SEC}s  TP={TP_PCT*100:.3f}%  Fee≈{TAKER_FEE_PCT*100:.3f}%  RearmGap={REARM_GAP_PCT*100:.3f}%")
print(f"🧊 Cooldown (TP): {COOLDOWN_SEC:.1f}s  | TP-chain max: {TP_CHAIN_MAX}")
if VOL_FILTER:
    print(f"🌬️ Vol-filter aktivt: period={VOL_PERIOD} span≥{MIN_VOL*100:.3f}%")
if LOSS_PAUSE_CNT > 0:
    pause_msg = f"⏸️ Paus efter {LOSS_PAUSE_CNT} BE/LB i rad"
    if LOSS_PAUSE_SEC > 0:
        pause_msg += f" (min {LOSS_PAUSE_SEC:.1f}s"
        if PAUSE_RESUME_PCT > 0:
            pause_msg += f", + rörelse ±{PAUSE_RESUME_PCT*100:.3f}%"
        pause_msg += ")"
    elif PAUSE_RESUME_PCT > 0:
        pause_msg += f" tills priset rör sig ±{PAUSE_RESUME_PCT*100:.3f}%"
    print(pause_msg)
if REENTRY_BREAK_PCT > 0:
    print(f"🔁 Ny entry kräver extra {REENTRY_BREAK_PCT*100:.3f}% utöver senaste exitnivå")
if DIR_BIAS_COUNT > 0 and DIR_BIAS_COOLDOWN > 0:
    print(f"🚫 Riktning spärras {DIR_BIAS_COOLDOWN:.1f}s efter {DIR_BIAS_COUNT} förluster i samma riktning")
if DYNAMIC_SIZING:
    levels_str = " → ".join([f"{int(x*100)}%" for x in SIZE_LEVELS])
    print(f"📊 Dynamisk positionsstorlek: {levels_str} (stegar ner efter {SIZE_STEP_LOSSES} förluster)")
if PROGRESSIVE_SCALING:
    if SCALE_IN_ENABLED:
        in_levels = ", ".join([f"+{float(x)*100:.2f}%" for x in SCALE_IN_LEVELS])
        print(f"➕ Scale IN: {in_levels} (lägg till {float(SCALE_IN_MULT)*100:.0f}% per nivå, max {float(MAX_SCALE_MULT)}x)")
    if SCALE_OUT_ENABLED:
        out_levels = ", ".join([f"-{float(x)*100:.2f}%" for x in SCALE_OUT_LEVELS])
        print(f"➖ Scale OUT: {out_levels} (exita {float(SCALE_OUT_MULT)*100:.0f}% per nivå, min {float(MIN_SCALE_MULT)*100:.0f}%)")
print(f"💰 Startbalans: {paper.snapshot()}\n")

SESSION_START = datetime.now(timezone.utc)

# ----------------------- Hjälpfunktioner -------------------------------------
def crossed(a: Decimal, b: Decimal, direction: Literal["up","down"]) -> bool:
    """True om a har passerat b i given riktning med minrörelse-golv."""
    if direction == "up":
        return a > b and (a - b) / b >= MIN_MOVE_PCT
    else:
        return a < b and (b - a) / b >= MIN_MOVE_PCT

def get_dynamic_qty() -> Decimal:
    """Beräkna initial positionsstorlek (kan vara reducerad vid progressive scaling)."""
    base_qty = ORDER_QTY
    
    # Applicera dynamic sizing (loss streak reduction)
    if DYNAMIC_SIZING:
        multiplier = SIZE_LEVELS[position_size_state["current_level_index"]]
        base_qty = (base_qty * Decimal(str(multiplier))).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    
    # Applicera initial position multiplier (börja liten om progressive scaling)
    if PROGRESSIVE_SCALING:
        base_qty = (base_qty * INITIAL_POS_MULT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    
    return base_qty

def update_position_size_on_loss():
    """Minska positionsstorlek vid förlust."""
    if not DYNAMIC_SIZING:
        return
    
    position_size_state["consecutive_losses"] += 1
    
    # Stega ner till nästa nivå efter SIZE_STEP_LOSSES förluster
    if position_size_state["consecutive_losses"] >= SIZE_STEP_LOSSES:
        current_idx = position_size_state["current_level_index"]
        if current_idx < len(SIZE_LEVELS) - 1:
            position_size_state["current_level_index"] = current_idx + 1
            position_size_state["consecutive_losses"] = 0  # Reset räknare
            new_multiplier = SIZE_LEVELS[position_size_state["current_level_index"]]
            print(f"📉 Minskar positionsstorlek till {new_multiplier*100:.0f}% efter förluster")

def update_position_size_on_win():
    """Återställ positionsstorlek vid vinst."""
    if not DYNAMIC_SIZING or not SIZE_RESET_ON_WIN:
        return
    
    if position_size_state["current_level_index"] > 0:
        position_size_state["current_level_index"] = 0
        position_size_state["consecutive_losses"] = 0
        print(f"📈 Återställer positionsstorlek till 100% efter vinst")

def enter_long(price: Decimal):
    global block_long_until
    pos.side  = "LONG"
    pos.entry = price
    pos.qty = get_dynamic_qty()
    pos.initial_qty = pos.qty  # Spara initial för scaling
    pos.total_cost = price * pos.qty  # Initial kostnad
    pos.entry_time = time.time()
    pos.high = price
    pos.low = price
    pos.scaled_in_levels = []
    pos.scaled_out_levels = []
    if ORDER_TEST:
        paper.market_buy(SYMBOL, pos.qty, price)
    size_pct = (pos.qty / ORDER_QTY * 100) if ORDER_QTY > 0 else 100
    print(f"📈 ENTER LONG @ {price:.2f} qty={pos.qty} ({size_pct:.0f}%)")
    reset_loss_pause_state()
    block_long_until = 0.0
    
    # Lägg till text-markering på grafen (kompakt)
    size_str = f"{size_pct:.0f}%" if size_pct != 100 else "100"
    trade_annotations.append({
        'abs_tick': tick_offset + len(py) - 1,  # Absolut tick-nummer
        'y': float(price),
        'text': f'L↑{size_str}',  # En rad, mer kompakt
        'color': 'white',
        'bgcolor': 'green',
        'size': 6  # Mindre text
    })

def enter_short(price: Decimal):
    global block_short_until
    pos.side  = "SHORT"
    pos.entry = price
    pos.qty = get_dynamic_qty()
    pos.initial_qty = pos.qty  # Spara initial för scaling
    pos.total_cost = price * pos.qty  # Initial kostnad
    pos.entry_time = time.time()
    pos.high = price
    pos.low = price
    pos.scaled_in_levels = []
    pos.scaled_out_levels = []
    if ORDER_TEST:
        paper.market_sell(SYMBOL, pos.qty, price)
    size_pct = (pos.qty / ORDER_QTY * 100) if ORDER_QTY > 0 else 100
    print(f"📉 ENTER SHORT @ {price:.2f} qty={pos.qty} ({size_pct:.0f}%)")
    reset_loss_pause_state()
    block_short_until = 0.0
    
    # Lägg till text-markering på grafen (kompakt)
    size_str = f"{size_pct:.0f}%" if size_pct != 100 else "100"
    trade_annotations.append({
        'abs_tick': tick_offset + len(py) - 1,  # Absolut tick-nummer
        'y': float(price),
        'text': f'S↓{size_str}',  # En rad, mer kompakt
        'color': 'white',
        'bgcolor': 'red',
        'size': 6  # Mindre text
    })

def chain_threshold(side: str, L_: Decimal) -> Decimal:
    """Litet extra brott som krävs för kedje-entry efter TP (anti-dubbeltick)."""
    if side == "LONG":
        return (L_ * (Decimal("1") + TP_CHAIN_GAP_PCT)).quantize(Decimal("0.01"))
    else:
        return (L_ * (Decimal("1") - TP_CHAIN_GAP_PCT)).quantize(Decimal("0.01"))

# ----------------------- SCALING IN/OUT --------------------------------------
def check_scale_in(price: Decimal):
    """Mean Reversion: Öka position när priset går MOT L från extrempunkten!"""
    if not PROGRESSIVE_SCALING or not SCALE_IN_ENABLED:
        return
    if pos.side == "FLAT" or pos.entry is None or pos.initial_qty == 0:
        return
    if pos.high is None or pos.low is None:
        return
    
    # Beräkna retracement från WORST punkt (samma som scale out använder!)
    # Detta gör att scale IN triggar på SAMMA pris som scale OUT
    if pos.side == "LONG":
        # LONG: worst = pos.low, retracement = priset går UPP från low
        retracement_pct = (price - pos.low) / pos.low if pos.low > 0 else Decimal("0")
        direction_str = f"UP from low {pos.low:.2f} to {price:.2f}"
    else:
        # SHORT: worst = pos.high, retracement = priset går NER från high
        retracement_pct = (pos.high - price) / pos.high if pos.high > 0 else Decimal("0")
        direction_str = f"DOWN from high {pos.high:.2f} to {price:.2f}"
    
    # Debug: visa retracement_pct och första nivån
    first_level = SCALE_IN_LEVELS[0] if SCALE_IN_LEVELS else Decimal("0")
    if retracement_pct >= first_level * Decimal("0.8"):  # Visa när vi är nära första nivån
        print(f"🔍 SCALE IN check ({pos.side}): {direction_str} = retracement {float(retracement_pct)*100:.4f}%, need {float(first_level)*100:.2f}% for first scale")
    
    # Kolla varje scale-in nivå (triggad vid retracement från worst)
    for i, level in enumerate(SCALE_IN_LEVELS):
        # VIKTIGT: Om vi passerar en scale OUT-nivå åt motsatt håll, resetta den!
        # Detta möjliggör kontinuerlig scaling när priset pendlar
        if i in pos.scaled_out_levels and retracement_pct >= level:
            pos.scaled_out_levels.remove(i)
            print(f"🔄 Reset scale-out nivå {i} (priset återvände)")
        
        if i in pos.scaled_in_levels:
            continue  # Redan triggad
        
        if retracement_pct >= level:  # När retracement når nivån, öka position!
            # Check att vi inte redan är på max (100%)
            current_mult = pos.qty / pos.initial_qty
            if current_mult >= MAX_SCALE_MULT:
                print(f"⚠️ SCALE IN skip: Redan på max {current_mult:.2f}x (max={MAX_SCALE_MULT}x)")
                continue
            
            # Lägg tillbaka exakt det som scalades out på denna nivå (om den finns)
            if i in pos.scaled_out_amounts:
                add_qty = pos.scaled_out_amounts[i]
                print(f"📥 Återställer exakt mängd från scale-out nivå {i}: {add_qty}")
            else:
                # Om inget scalades out på denna nivå, lägg till standard-belopp
                add_qty = (pos.initial_qty * SCALE_IN_MULT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            
            new_qty = pos.qty + add_qty
            
            # Begränsa till max (initial_qty * MAX_SCALE_MULT = 100%)
            if new_qty > pos.initial_qty * MAX_SCALE_MULT:
                new_qty = pos.initial_qty * MAX_SCALE_MULT
                add_qty = new_qty - pos.qty
                print(f"⚠️ Begränsat till max: add_qty justerad till {add_qty}")
            
            if add_qty > 0:
                if ORDER_TEST:
                    if pos.side == "LONG":
                        paper.market_buy(SYMBOL, add_qty, price)
                    else:
                        paper.market_sell(SYMBOL, add_qty, price)
                
                pos.qty = new_qty
                pos.total_cost += price * add_qty  # Uppdatera total kostnad
                pos.scaled_in_levels.append(i)
                total_mult = pos.qty / pos.initial_qty
                avg_price = pos.avg_entry_price()
                print(f"➕ SCALE IN (retracement +{float(retracement_pct)*100:.2f}%): Add {add_qty} @ {price:.2f} | Total: {pos.qty} ({total_mult:.1f}x) Avg: {avg_price:.2f}")
                
                # Lägg till text-markering på grafen (kompakt) - CYAN för scale in
                trade_annotations.append({
                    'abs_tick': tick_offset + len(py) - 1,  # Absolut tick-nummer
                    'y': float(price),
                    'text': f'↑{total_mult:.1f}x',  # En rad med pil upp
                    'color': 'black',
                    'bgcolor': 'cyan',  # CYAN för scale IN (distinkt från exit)
                    'size': 5  # Mindre för scale events
                })

def check_scale_out(price: Decimal):
    """Mean Reversion: Minska position när priset går FEL håll (bort från L)!"""
    global L
    if not PROGRESSIVE_SCALING or not SCALE_OUT_ENABLED:
        return
    if pos.side == "FLAT" or pos.entry is None or pos.initial_qty == 0:
        return
    
    # Beräkna loss % från ENTRY (priset rör sig BORT från L = dåligt!)
    if pos.side == "LONG":
        # LONG entry UNDER L: loss = priset går NER (bort från L)
        loss_pct = (pos.entry - price) / pos.entry if pos.entry > 0 else Decimal("0")
    else:
        # SHORT entry ÖVER L: loss = priset går UPP (bort från L)
        loss_pct = (price - pos.entry) / pos.entry if pos.entry > 0 else Decimal("0")
    
    # Debug när nära första nivån
    first_level = SCALE_OUT_LEVELS[0] if SCALE_OUT_LEVELS else Decimal("0")
    if loss_pct >= first_level * Decimal("0.5"):
        direction_str = "DOWN" if pos.side == "LONG" else "UP"
        print(f"🔍 SCALE OUT check ({pos.side}): price {direction_str} from {pos.entry:.2f} to {price:.2f} = loss {float(loss_pct)*100:.4f}%, need {float(first_level)*100:.2f}% for first scale")
    
    # Kolla varje scale-out nivå (triggad vid loss bort från L)
    for i, level in enumerate(SCALE_OUT_LEVELS):
        # VIKTIGT: Om vi passerar en scale IN-nivå åt motsatt håll, resetta den!
        # Detta möjliggör kontinuerlig scaling när priset pendlar
        if i in pos.scaled_in_levels and loss_pct >= level:
            pos.scaled_in_levels.remove(i)
            print(f"🔄 Reset scale-in nivå {i} (priset vände åt fel håll igen)")
        
        if i in pos.scaled_out_levels:
            continue  # Redan triggad
        
        if loss_pct >= level:  # När förlusten når nivån, minska position!
            # Scala ner hela vägen till 0% (ingen min-gräns)
            reduce_qty = (pos.qty * SCALE_OUT_MULT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            new_qty = pos.qty - reduce_qty
            
            # Om vi når nästan 0, stäng helt och börja om
            if new_qty < pos.initial_qty * Decimal("0.05"):  # Under 5% = stäng helt
                reduce_qty = pos.qty  # Stäng allt
                new_qty = Decimal("0")
            
            if reduce_qty > 0:
                if ORDER_TEST:
                    if pos.side == "LONG":
                        paper.market_sell(SYMBOL, reduce_qty, price)
                    else:
                        paper.market_buy(SYMBOL, reduce_qty, price)
                
                # Minska total_cost proportionellt
                avg_price = pos.avg_entry_price()
                pos.total_cost -= avg_price * reduce_qty
                pos.qty = new_qty
                pos.scaled_out_levels.append(i)
                pos.scaled_out_amounts[i] = reduce_qty  # Spara hur mycket som togs bort
                total_mult = pos.qty / pos.initial_qty if pos.initial_qty > 0 else Decimal("0")
                
                # Om positionen tynde bort helt (0%), exit och börja om
                if pos.qty == 0:
                    print(f"💀 POSITION TYNADE BORT (loss -{float(loss_pct)*100:.2f}%): Exit allt @ {price:.2f}")
                    do_exit(pos.side, price, "LB" if pos.side == "LONG" else "SB")
                    # Flytta L till nuvarande pris och vänta på ny entry
                    L = price
                    print(f"🔄 Ny L satt till {L:.2f} - väntar på ny entry")
                    return
                
                print(f"➖ SCALE OUT (loss -{float(loss_pct)*100:.2f}%): Exit {reduce_qty} @ {price:.2f} | Remaining: {pos.qty} ({total_mult:.1f}x) Avg: {avg_price:.2f}")
                
                # Lägg till text-markering på grafen (kompakt)
                trade_annotations.append({
                    'abs_tick': tick_offset + len(py) - 1,  # Absolut tick-nummer
                    'y': float(price),
                    'text': f'−{total_mult:.1f}x' if total_mult > 0 else '💀',  # Skalle när 0%
                    'color': 'black',
                    'bgcolor': 'yellow' if total_mult > 0 else 'red',
                    'size': 5  # Mindre för scale events
                })

# ----------------------- EXIT-logik ------------------------------------------
def do_exit(side: str, exit_price: Decimal, state_tag: str):
    """Stäng position, logga, re-arma L, och hantera TP-kedja/BE-vändning."""
    global L, block_long_until, block_short_until, loss_pause_state
    global consec_long_losses, consec_short_losses, last_long_rearm, last_short_rearm
    entry = pos.entry if pos.entry is not None else exit_price
    avg_entry = pos.avg_entry_price()  # Använd genomsnittligt pris för PnL
    entry_price = avg_entry if avg_entry > 0 else entry
    entry_time = pos.entry_time
    price_high = pos.high if pos.high is not None else exit_price
    price_low = pos.low if pos.low is not None else exit_price
    if price_high is not None and price_low is not None and price_high < price_low:
        price_high, price_low = price_low, price_high

    # Logg + PnL (använd faktisk qty och genomsnittligt entry-pris)
    qty = pos.qty if pos.qty > 0 else ORDER_QTY
    pnl_usd, pnl_pct = paper.log_exit(state_tag, side, SYMBOL, qty, exit_price, entry_price)
    if side == "LONG":
        print(f"🔚 EXIT LONG @ {exit_price:.2f} (entry {entry:.2f})  PnL: {pnl_pct:.3f}% (${pnl_usd:.4f}) [{state_tag}]")
    else:
        print(f"🔚 EXIT SHORT @ {exit_price:.2f} (entry {entry:.2f}) PnL: {pnl_pct:.3f}% (${pnl_usd:.4f}) [{state_tag}]")
    
    # Lägg till exit-markering på grafen (kompakt)
    # Grön för vinst (LW/SW), röd för förlust (LB/SB)
    is_win = state_tag in ("LW", "SW")
    trade_annotations.append({
        'abs_tick': tick_offset + len(py) - 1,  # Absolut tick-nummer
        'y': float(exit_price),
        'text': f'{"✓" if is_win else "✗"}{float(pnl_pct):.2f}%',  # En rad
        'color': 'white',
        'bgcolor': 'green' if is_win else 'darkred',
        'size': 6
    })

    exit_epoch = time.time()
    exit_ts_iso = datetime.fromtimestamp(exit_epoch, tz=timezone.utc).isoformat(timespec="seconds") + "Z"
    duration_sec = exit_epoch - entry_time if entry_time else 0.0
    zero = Decimal("0")
    denom = entry_price if entry_price != zero else Decimal("1")
    # Mean Reversion: MFE = rörelse MOT L, MAE = rörelse BORT från L
    mfe_abs: Decimal
    mae_abs: Decimal
    if side == "LONG":
        # LONG entry UNDER L: MFE = priset går UPP mot L, MAE = priset går NER bort från L
        mfe_abs = (price_high - entry_price) if price_high >= entry_price else zero
        mae_abs = (entry_price - price_low) if price_low <= entry_price else zero
    else:
        # SHORT entry ÖVER L: MFE = priset går NER mot L, MAE = priset går UPP bort från L
        mfe_abs = (entry_price - price_low) if price_low <= entry_price else zero
        mae_abs = (price_high - entry_price) if price_high >= entry_price else zero
    mfe_abs = mfe_abs if mfe_abs > zero else zero
    mae_abs = mae_abs if mae_abs > zero else zero
    mfe_pct = (mfe_abs / denom) if denom != zero else zero
    mae_pct = (mae_abs / denom) if denom != zero else zero
    vol_span_pct = ((price_high - price_low) / denom) if denom != zero else zero

    pause_triggered = False
    pause_direction = ""
    pause_anchor = ""

    # L flyttas INTE här - flyttas endast vid L-korsning i maybe_exit
    # (last_long_rearm används inte i denna strategi)
    mk.on_state(state_tag)

    if LOSS_PAUSE_CNT > 0 and len(mk.last_states) >= LOSS_PAUSE_CNT:
        recent = list(mk.last_states)[-LOSS_PAUSE_CNT:]
        if all(s in ("LB", "SB") for s in recent):
            if LOSS_PAUSE_SEC <= 0 and PAUSE_RESUME_PCT <= 0:
                pass
            else:
                pause_triggered = True
                pause_direction = "LONG" if recent[-1] == "LB" else "SHORT"
                pause_anchor = f"{exit_price}"
                reset_loss_pause_state()
                pause_start = exit_epoch
                loss_pause_state["active"] = True
                loss_pause_state["anchor"] = exit_price
                loss_pause_state["high"] = exit_price
                loss_pause_state["low"] = exit_price
                loss_pause_state["resume_at"] = pause_start + LOSS_PAUSE_SEC if LOSS_PAUSE_SEC > 0 else 0.0
                loss_pause_state["started_at"] = pause_start
                loss_pause_state["direction"] = pause_direction
                if PAUSE_RESUME_PCT > 0:
                    print(
                        f"⏸️ Pausar entries efter {LOSS_PAUSE_CNT} BE/LB i rad. "
                        f"Återupptar när priset rör sig ±{PAUSE_RESUME_PCT*100:.3f}% från {exit_price:.2f}."
                    )
                elif LOSS_PAUSE_SEC > 0:
                    print(
                        f"⏸️ Pausar entries i {LOSS_PAUSE_SEC:.1f}s efter {LOSS_PAUSE_CNT} BE/LB i rad."
                    )

    append_csv_row(
        TRADE_METRICS_CSV,
        [
            exit_ts_iso,
            state_tag,
            side,
            f"{entry_price}",
            f"{exit_price}",
            f"{max(0.0, duration_sec):.2f}",
            f"{float(mfe_pct):.6f}",
            f"{float(mae_pct):.6f}",
            f"{float(mfe_abs):.6f}",
            f"{float(mae_abs):.6f}",
            f"{price_high}",
            f"{price_low}",
            f"{float(vol_span_pct):.6f}",
            "1" if pause_triggered else "0",
            pause_direction,
            pause_anchor,
            f"{PAUSE_RESUME_PCT}",
            f"{LOSS_PAUSE_SEC}",
        ],
        header=TRADE_METRICS_HEADER,
    )

    # Uppdatera positionsstorlek baserat på win/loss
    if state_tag in ("LW", "SW"):
        update_position_size_on_win()
    elif state_tag in ("LB", "SB"):
        update_position_size_on_loss()

    # Uppdatera riktningstaktik (blockera ny entry efter flera riktade förluster)
    now_ts = exit_epoch
    if side == "LONG":
        if state_tag == "LB":
            consec_long_losses += 1
            if DIR_BIAS_COUNT > 0 and consec_long_losses >= DIR_BIAS_COUNT:
                if DIR_BIAS_COOLDOWN > 0:
                    block_long_until = now_ts + DIR_BIAS_COOLDOWN
                    print(f"🚫 Blockerar LONG i {DIR_BIAS_COOLDOWN:.1f}s efter {DIR_BIAS_COUNT} långförluster.")
                else:
                    block_long_until = now_ts
                consec_long_losses = 0
        else:
            consec_long_losses = 0
    else:
        if state_tag == "SB":
            consec_short_losses += 1
            if DIR_BIAS_COUNT > 0 and consec_short_losses >= DIR_BIAS_COUNT:
                if DIR_BIAS_COOLDOWN > 0:
                    block_short_until = now_ts + DIR_BIAS_COOLDOWN
                    print(f"🚫 Blockerar SHORT i {DIR_BIAS_COOLDOWN:.1f}s efter {DIR_BIAS_COUNT} kortförluster.")
                else:
                    block_short_until = now_ts
                consec_short_losses = 0
        else:
            consec_short_losses = 0

    # Ingen FLAT här - ny position har redan öppnats i maybe_exit vid L-korsning
    # Position är redan aktiv på andra sidan L

# ----------------------- MAX LOSS PROTECTION ---------------------------------
def check_max_loss_protection(price: Decimal) -> bool:
    """
    KRITISK FUNKTION: Tvingad exit om:
    1. Unrealized loss > MAX_LOSS_PCT
    2. Position hålls > MAX_POSITION_TIME_SEC
    3. Mode bytte och FORCE_EXIT_ON_MODE_SWITCH = True
    
    Returns: True om position stängdes
    """
    global L
    
    if pos.side == "FLAT" or pos.entry is None:
        return False
    
    # 1. Kolla unrealized loss
    unrealized_pnl = pos.unrealized_pnl_pct(price)
    if unrealized_pnl < -MAX_LOSS_PCT:
        print(f"\n{'='*70}")
        print(f"🛑 MAX LOSS PROTECTION TRIGGERED!")
        print(f"   Unrealized loss: {float(unrealized_pnl):.3f}% (max: -{float(MAX_LOSS_PCT):.1f}%)")
        print(f"   Closing position at {price:.2f} to prevent further damage")
        print(f"{'='*70}\n")
        
        qty = pos.qty if pos.qty > 0 else ORDER_QTY
        if ORDER_TEST:
            if pos.side == "LONG":
                paper.market_sell(SYMBOL, qty, price)
            else:
                paper.market_buy(SYMBOL, qty, price)
        
        do_exit(pos.side, price, "MAX_LOSS")
        pos.flat()
        L = price
        return True
    
    # 2. Kolla position tid
    if pos.entry_time > 0:
        time_in_position = time.time() - pos.entry_time
        if time_in_position > MAX_POSITION_TIME_SEC:
            print(f"\n{'='*70}")
            print(f"⏰ MAX TIME PROTECTION TRIGGERED!")
            print(f"   Time in position: {time_in_position/60:.1f} min (max: {MAX_POSITION_TIME_SEC/60:.0f} min)")
            print(f"   Unrealized PnL: {float(unrealized_pnl):.3f}%")
            print(f"   Closing position at {price:.2f}")
            print(f"{'='*70}\n")
            
            qty = pos.qty if pos.qty > 0 else ORDER_QTY
            if ORDER_TEST:
                if pos.side == "LONG":
                    paper.market_sell(SYMBOL, qty, price)
                else:
                    paper.market_buy(SYMBOL, qty, price)
            
            do_exit(pos.side, price, "MAX_TIME")
            pos.flat()
            L = price
            return True
    
    return False

# ----------------------- ENTRY/EXIT kontroller -------------------------------
def maybe_exit(price: Decimal):
    """
    ADAPTIVE EXIT: Använder current_mode för att avgöra exit-logik
    - BREAKOUT mode: TP vid fortsatt rörelse bort från L, Stop vid återgång till L
    - MEAN_REVERSION mode: TP vid återgång till L, Stop vid fortsatt rörelse från L
    """
    global L
    qty = pos.qty if pos.qty > 0 else ORDER_QTY
    current_mode = mode_manager.current_mode
    
    if pos.side == "LONG" and pos.entry is not None:
        if current_mode == "BREAKOUT":
            # BREAKOUT LONG: TP när priset går UPP (fortsatt momentum), Stop vid återgång till L
            # TP: price >= entry + TP_PCT
            tp_target = pos.avg_entry_price() * (Decimal("1") + TP_PCT)
            if price >= tp_target:
                print(f"✅ LONG EXIT [BREAKOUT]: TP nådd @ {price:.2f} (target {tp_target:.2f})")
                if ORDER_TEST:
                    paper.market_sell(SYMBOL, qty, price)
                pnl_usd, pnl_pct = paper.log_exit("LW", "LONG", SYMBOL, qty, price, pos.avg_entry_price())
                do_exit("LONG", price, "LW")
                # I BREAKOUT: L följer entry, flytta L uppåt
                L = price
                # GÅ FLAT vid vinst - låt maybe_enter avgöra nästa trade
                pos.flat()
                print(f"✅ TP hit - going FLAT. PnL: {float(pnl_pct):.2f}%")
                refresh_lines(price)
                return
            # Stop Loss: pris går tillbaka till L eller under
            if price <= L:
                print(f"🛑 LONG STOP [BREAKOUT]: Pris tillbaka till L @ {price:.2f}")
                if ORDER_TEST:
                    paper.market_sell(SYMBOL, qty, price)
                pnl_usd, pnl_pct = paper.log_exit("LB", "LONG", SYMBOL, qty, price, pos.avg_entry_price())
                do_exit("LONG", price, "LB")
                L = price
                # GÅ FLAT vid förlust - låt maybe_enter avgöra om vi ska fortsätta
                pos.flat()
                print(f"🛑 Stop hit - going FLAT. PnL: {float(pnl_pct):.2f}%")
                refresh_lines(price)
        else:  # MEAN_REVERSION
            # MEAN_REVERSION LONG: TP vid återgång till L (uppåt), Stop vid fortsatt fall
            if price >= L:
                print(f"✅ LONG EXIT [REVERSION]: Priset {price:.2f} nådde L {L:.2f}")
                if ORDER_TEST:
                    paper.market_sell(SYMBOL, qty, price)
                pnl_usd, pnl_pct = paper.log_exit("LW", "LONG", SYMBOL, qty, price, pos.avg_entry_price())
                do_exit("LONG", price, "LW")
                # Flytta L till korsningspunkten
                L = price
                # GÅ FLAT istället för att öppna ny position direkt
                # Låt maybe_enter avgöra om/när nästa position ska öppnas
                pos.flat()
                print(f"✅ Win exit - going FLAT. PnL: {float(pnl_pct):.2f}%")
                refresh_lines(price)

    elif pos.side == "SHORT" and pos.entry is not None:
        if current_mode == "BREAKOUT":
            # BREAKOUT SHORT: TP när priset går NER (fortsatt momentum), Stop vid återgång till L
            # TP: price <= entry - TP_PCT
            tp_target = pos.avg_entry_price() * (Decimal("1") - TP_PCT)
            if price <= tp_target:
                print(f"✅ SHORT EXIT [BREAKOUT]: TP nådd @ {price:.2f} (target {tp_target:.2f})")
                if ORDER_TEST:
                    paper.market_buy(SYMBOL, qty, price)
                pnl_usd, pnl_pct = paper.log_exit("SW", "SHORT", SYMBOL, qty, price, pos.avg_entry_price())
                do_exit("SHORT", price, "SW")
                # I BREAKOUT: L följer entry, flytta L nedåt
                L = price
                # GÅ FLAT vid vinst
                pos.flat()
                print(f"✅ TP hit - going FLAT. PnL: {float(pnl_pct):.2f}%")
                refresh_lines(price)
                return
            # Stop Loss: pris går tillbaka till L eller över
            if price >= L:
                print(f"🛑 SHORT STOP [BREAKOUT]: Pris tillbaka till L @ {price:.2f}")
                if ORDER_TEST:
                    paper.market_buy(SYMBOL, qty, price)
                pnl_usd, pnl_pct = paper.log_exit("SB", "SHORT", SYMBOL, qty, price, pos.avg_entry_price())
                do_exit("SHORT", price, "SB")
                L = price
                # GÅ FLAT vid förlust
                pos.flat()
                print(f"🛑 Stop hit - going FLAT. PnL: {float(pnl_pct):.2f}%")
                refresh_lines(price)
        else:  # MEAN_REVERSION
            # MEAN_REVERSION SHORT: TP vid återgång till L (nedåt), Stop vid fortsatt stigning
            if price <= L:
                print(f"✅ SHORT EXIT [REVERSION]: Priset {price:.2f} nådde L {L:.2f}")
                if ORDER_TEST:
                    paper.market_buy(SYMBOL, qty, price)
                pnl_usd, pnl_pct = paper.log_exit("SW", "SHORT", SYMBOL, qty, price, pos.avg_entry_price())
                do_exit("SHORT", price, "SW")
                # Flytta L till korsningspunkten
                L = price
                # GÅ FLAT istället för att öppna ny position direkt
                pos.flat()
                print(f"✅ Win exit - going FLAT. PnL: {float(pnl_pct):.2f}%")
                refresh_lines(price)

def maybe_enter(price: Decimal):
    """
    ADAPTIVE ENTRY: Använder current_mode för att avgöra entry-riktning
    - BREAKOUT mode: Följ trenden (LONG vid upp-brott, SHORT vid ner-brott)
    - MEAN_REVERSION mode: Satsa på återgång (SHORT vid upp-brott, LONG vid ner-brott)
    """
    global START_MODE, L, loss_pause_state

    now_ts = time.time()
    if loss_pause_state["active"]:
        resume_at = float(loss_pause_state.get("resume_at") or 0.0)
        anchor_price = loss_pause_state.get("anchor")
        resume_reason = ""
        move_delta = Decimal("0")

        if isinstance(anchor_price, Decimal) and anchor_price > 0:
            high_price = loss_pause_state.get("high")
            low_price = loss_pause_state.get("low")
            if isinstance(high_price, Decimal) and price > high_price:
                loss_pause_state["high"] = price
                high_price = price
            if isinstance(low_price, Decimal) and price < low_price:
                loss_pause_state["low"] = price
                low_price = price

            high_delta = (high_price - anchor_price) / anchor_price if isinstance(high_price, Decimal) and high_price > anchor_price else Decimal("0")
            low_delta = (anchor_price - low_price) / anchor_price if isinstance(low_price, Decimal) and low_price < anchor_price else Decimal("0")
            move_delta = high_delta if high_delta >= low_delta else low_delta

            if PAUSE_RESUME_PCT > 0 and move_delta >= PAUSE_RESUME_PCT:
                resume_reason = f"prisrörelse på {move_delta * Decimal('100'):.3f}%"

        if not resume_reason and resume_at > 0.0 and now_ts >= resume_at:
            started_at = float(loss_pause_state.get("started_at") or 0.0)
            if started_at > 0.0:
                resume_reason = f"timeout ({now_ts - started_at:.1f}s)"
            else:
                resume_reason = "timeout"

        if resume_reason:
            print(f"▶️ Loss-paus släpper ({resume_reason}).")
            reset_loss_pause_state()
        else:
            return

    # STARTFAS: Gå in direkt när L är redo (efter ~20 ticks för Markov init)
    if START_MODE:
        # Vänta minst 20 ticks för att Markov ska ha data
        if len(py) < 20:
            return
        
        START_MODE = False
        current_mode = mode_manager.current_mode
        
        # Entry baserat på MODE och position relativt L
        if price > L:
            # Priset är ÖVER L
            if current_mode == "BREAKOUT":
                # BREAKOUT: Följ trenden uppåt → LONG
                enter_long(price)
                print(f"🎯 START [{current_mode}]: Priset över L ({L:.2f}) → LONG (följ trend)")
            else:  # MEAN_REVERSION
                # MEAN_REVERSION: Satsa på återgång → SHORT
                enter_short(price)
                print(f"🎯 START [{current_mode}]: Priset över L ({L:.2f}) → SHORT (mean reversion)")
            return
        else:
            # Priset är UNDER L
            if current_mode == "BREAKOUT":
                # BREAKOUT: Följ trenden nedåt → SHORT
                enter_short(price)
                print(f"🎯 START [{current_mode}]: Priset under L ({L:.2f}) → SHORT (följ trend)")
            else:  # MEAN_REVERSION
                # MEAN_REVERSION: Satsa på återgång → LONG
                enter_long(price)
                print(f"🎯 START [{current_mode}]: Priset under L ({L:.2f}) → LONG (mean reversion)")
            return

    # Efter START_MODE: Nya positioner öppnas automatiskt i maybe_exit vid L-korsning
    # (ingen kod behövs här för drift)

# ----------------------- Grafik ----------------------------------------------
plt.ion()
fig, ax = plt.subplots(figsize=(12, 7))
price_line, = ax.plot([], [], lw=1.5, color='blue')
L_line,     = ax.plot([], [], linestyle="--", lw=2.0, color='orange')
TP_line,    = ax.plot([], [], linestyle=":", lw=2.5, color='green')
BE_line,    = ax.plot([], [], linestyle="-.", lw=2.0, color='red')

# Vi visar startbandet bara tills första entry
upper_band_line, = ax.plot([], [], linestyle="--", lw=0.8, color='gray', alpha=0.5)
lower_band_line, = ax.plot([], [], linestyle="--", lw=0.8, color='gray', alpha=0.5)

# Markeringar för entry/scale in/out (textrutor istället för cirklar)
trade_annotations = []  # Lista med alla text-annotations

# Text-labels som följer linjerna (skapas dynamiskt)
L_text = ax.text(0, 0, '', fontsize=9, color='orange', fontweight='bold', va='center')
TP_text = ax.text(0, 0, '', fontsize=9, color='green', fontweight='bold', va='center')
BE_text = ax.text(0, 0, '', fontsize=9, color='red', fontweight='bold', va='center')
pos_text = ax.text(0.99, 0.97, '', transform=ax.transAxes, fontsize=10, 
                   va='top', ha='right', fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.5", alpha=0.8, facecolor='lightyellow'))

ax.set_title(f"{SYMBOL} – Markov ADAPTIVE (Breakout + Mean Reversion)", fontsize=12, fontweight='bold')
ax.set_xlabel("Ticks")
ax.set_ylabel("Price")
ax.grid(True, alpha=0.3)

# Legend för textmarkeringar
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='green', edgecolor='black', label='L↑/S↓: Entry'),
    Patch(facecolor='cyan', edgecolor='black', label='↑: Scale In'),
    Patch(facecolor='yellow', edgecolor='black', label='↓: Scale Out'),
    Patch(facecolor='green', edgecolor='black', label='✓: Exit Vinst'),
    Patch(facecolor='darkred', edgecolor='black', label='✗: Exit Förlust'),
    Patch(facecolor='orange', edgecolor='black', label='📈: Breakout Mode'),
    Patch(facecolor='cyan', edgecolor='black', label='🔄: Reversion Mode'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=8, framealpha=0.9)

max_points = 800
px = deque(maxlen=max_points)
py = deque(maxlen=max_points)

# Cache för redan ritade annotations (för att undvika duplicates)
drawn_annotations = []

# Offset för att tracka absolut tick-nummer (för att kunna rulla grafen)
tick_offset = 0

def _fmt_opt_decimal(d: Optional[Decimal]) -> str:
    """Säker formattering för valfri Decimal (undviker NoneType.__format__-fel)."""
    if d is None:
        return "-"
    try:
        return f"{float(d):.2f}"
    except Exception:
        return str(d)

def refresh_lines(current_price: Decimal):
    # Pris
    xs = list(range(len(py)))
    price_line.set_data(xs, list(py))

    # Visa ALLTID L-linjen (entry-trigger)
    L_val = float(L)
    L_line.set_data(xs, [L_val]*len(xs))
    L_line.set_visible(True)

    # TP-linje visas inte separat - TP = L-korsning (exit sker där)
    if not START_MODE and pos.entry is not None and pos.side != "FLAT":
        # Dölj TP och BE (bara L-linjen behövs)
        TP_line.set_visible(False)
        BE_line.set_visible(False)
        # dölj startband
        upper_band_line.set_visible(False)
        lower_band_line.set_visible(False)
    else:
        # Startband till dess vi fått första entry (eller ingen position)
        if START_MODE:
            upper_band_line.set_data(xs, [float(L_upper)]*len(xs))
            lower_band_line.set_data(xs, [float(L_lower)]*len(xs))
            upper_band_line.set_visible(True)
            lower_band_line.set_visible(True)
        else:
            upper_band_line.set_visible(False)
            lower_band_line.set_visible(False)
        # Dölj TP/BE när ingen position
        TP_line.set_visible(False)
        BE_line.set_visible(False)

    # Håll linjerna i bild - inkludera TP om position aktiv
    if len(py) >= 5:
        lo = min(min(py), float(L_lower))
        hi = max(max(py), float(L_upper))
        
        # L-linjen är alltid inkluderad i zoom (den är alltid synlig)
        
        rng = max(1.0, (hi - lo) * 0.15)
        ax.set_ylim(lo - rng*0.2, hi + rng*0.2)
        ax.set_xlim(max(0, len(py) - max_points), len(py))

    # Labels på linjerna (högerkant)
    if len(xs) > 0:
        x_pos = len(xs) - 1
        
        # L-linje label (alltid synlig)
        L_text.set_position((x_pos, L_val))
        L_text.set_text(f' L: {L_val:.2f}')
        L_text.set_visible(True)
        
        # Ingen separat TP label (TP = L-korsning)
        TP_text.set_visible(False)
    
    # Rensa gamla annotations från grafen
    global drawn_annotations
    for old_ann in drawn_annotations:
        old_ann.remove()
    drawn_annotations.clear()
    
    # Rita trade annotations som är inom synligt tidsfönster (rullande graf)
    # Beräkna synligt tick-range baserat på aktuell deque
    visible_start_tick = tick_offset  # Första tick i py deque
    visible_end_tick = tick_offset + len(py)  # Sista tick i py deque
    
    for ann in trade_annotations:
        abs_tick = ann['abs_tick']
        
        # Kontrollera om annotation är inom synligt tidsfönster
        if visible_start_tick <= abs_tick < visible_end_tick:
            # Konvertera absolut tick till relativ position i grafen
            relative_x = abs_tick - tick_offset
            
            # Använd xytext för att förskjuta texten från punkten (undviker överlappning)
            # Förskjutning beror på typ för att separera entry/exit/scale
            if 'L↑' in ann['text']:  # LONG entry
                offset = (0, 15)
            elif 'S↓' in ann['text']:  # SHORT entry
                offset = (0, -15)
            elif '−' in ann['text']:  # Scale out
                offset = (0, -10)
            elif '+' in ann['text']:  # Scale in
                offset = (0, 10)
            else:  # Exit (✓ eller ✗)
                offset = (0, 0)
            
            text_obj = ax.annotate(
                ann['text'],
                xy=(relative_x, ann['y']),
                xytext=offset,
                textcoords='offset points',
                fontsize=ann['size'],
                color=ann['color'],
                bbox=dict(boxstyle='round,pad=0.3', facecolor=ann['bgcolor'], edgecolor='black', linewidth=0.8),
                ha='center',
                va='center',
                zorder=10,
                alpha=0.9
            )
            drawn_annotations.append(text_obj)
    
    # Kompakt position info MED mode-indikator (höger överkant)
    trend_strength = trend_detector.calculate_trend_strength()
    mode_symbol = mode_manager.get_mode_symbol()
    mode_name = mode_manager.current_mode
    
    if pos.side != "FLAT" and pos.entry is not None:
        pnl_pct = ((float(current_price) - float(pos.entry)) / float(pos.entry) * 100) if pos.side == "LONG" else ((float(pos.entry) - float(current_price)) / float(pos.entry) * 100)
        pos_info = f"{mode_symbol} {mode_name} | {pos.side} @ {float(pos.entry):.2f} | PnL: {pnl_pct:+.2f}%\nTrend: {trend_strength:.2f}"
    else:
        pos_info = f"{mode_symbol} {mode_name} | FLAT | USDT: {float(paper.balances['USDT']):.2f}\nTrend: {trend_strength:.2f}"
    pos_text.set_text(pos_info)
    
    # Ändra färg på info-box baserat på mode
    pos_text.get_bbox_patch().set_facecolor(mode_manager.get_mode_color())
    pos_text.get_bbox_patch().set_alpha(0.7)

    fig.canvas.draw()
    fig.canvas.flush_events()

# ----------------------- Huvudloop -------------------------------------------
last_price_cache: Optional[Decimal] = None

def main():
    global last_price_cache, L
    tick = 0
    print("▶️  Startar trading loop... (Ctrl+C för att avsluta)")
    if _pause_resume_map:
        print(f"📊 Pause-resume-mappning aktiverad: lookahead={_lookahead_key} → {PAUSE_RESUME_PCT*100:.4f}%")
    else:
        print(f"📊 Pause-resume default: {PAUSE_RESUME_PCT*100:.4f}%")
    if ADAPTIVE_L_ENABLED:
        print(f"🧠 Adaptive L: baseline={adaptive_L_calc.baseline_window}, trend={adaptive_L_calc.trend_window}, update var {ADAPTIVE_L_UPDATE_INTERVAL}:e tick")
    print()

    try:
        while True:
            price = get_live_price(SYMBOL)
            last_price_cache = price
            py.append(float(price))
            px.append(tick)
            
            # Uppdatera tick_offset när deque börjar förlora data (rulla grafen)
            global tick_offset
            if len(py) == max_points:
                tick_offset += 1
            
            # ========== ADAPTIVE STRATEGY: Trend Detection & Mode Selection ==========
            # Mata in pris till trend detector
            trend_detector.add_price(price)
            
            # Uppdatera mode var 10:e tick (för att undvika överdriven beräkning)
            if tick % 10 == 0:
                trend_strength = trend_detector.calculate_trend_strength()
                current_mode, mode_changed = mode_manager.update_mode(trend_strength)
                
                # DIAGNOSTIK: Visa detaljerad trend-analys var 50:e tick
                if tick % 50 == 0 and len(py) >= 20:
                    metrics = trend_detector.get_detailed_metrics()
                    trend_desc = trend_detector.get_trend_description()
                    print(f"📊 TREND CHECK (tick {tick}): {trend_desc} | Score: {trend_strength:.3f} | Mode: {current_mode}")
                    if metrics:
                        print(f"   └─ Pris: {metrics['current_price']:.2f} | Δ: {metrics['price_change_pct']:+.3f}% | Range: {metrics['price_range']:.2f} | Max streak: {metrics['max_streak']}")
                
                # Visualisera mode-byten på grafen
                if mode_changed:
                    mode_color = 'orange' if current_mode == "BREAKOUT" else 'cyan'
                    mode_text = "📈BRK" if current_mode == "BREAKOUT" else "🔄REV"
                    trade_annotations.append({
                        'abs_tick': tick_offset + len(py) - 1,
                        'y': float(price),
                        'text': mode_text,
                        'color': 'black',
                        'bgcolor': mode_color,
                        'size': 7
                    })
                    
                    # TVINGAD EXIT vid mode-byte (om aktiverat)
                    if FORCE_EXIT_ON_MODE_SWITCH and pos.side != "FLAT":
                        unrealized_pnl = pos.unrealized_pnl_pct(price)
                        print(f"\n{'='*70}")
                        print(f"🔄 MODE SWITCH EXIT: Closing {pos.side} position")
                        print(f"   Reason: Strategy mode changed to {current_mode}")
                        print(f"   Unrealized PnL: {float(unrealized_pnl):.3f}%")
                        print(f"{'='*70}\n")
                        
                        qty = pos.qty if pos.qty > 0 else ORDER_QTY
                        if ORDER_TEST:
                            if pos.side == "LONG":
                                paper.market_sell(SYMBOL, qty, price)
                            else:
                                paper.market_buy(SYMBOL, qty, price)
                        
                        do_exit(pos.side, price, "MODE_SWITCH")
                        pos.flat()
                        L = price
                    
                    # Visa VARFÖR mode bytte
                    metrics = trend_detector.get_detailed_metrics()
                    print(f"\n{'='*60}")
                    print(f"🔄 MODE SWITCH: {mode_manager.mode_changes[-1]['from_mode']} → {current_mode}")
                    print(f"   Trend Strength: {trend_strength:.3f}")
                    if metrics:
                        print(f"   Pris: {metrics['current_price']:.2f} (Δ {metrics['price_change_pct']:+.3f}%)")
                        print(f"   Max konsekutiv streak: {metrics['max_streak']} moves")
                    print(f"{'='*60}\n")
                    
                    # Om mode bytte och vi har en öppen position: överväg action
                    if pos.side != "FLAT":
                        print(f"⚠️ Mode switched while in {pos.side} position - continuing with new mode")
            # ==========================================================================
            
            # Adaptive L update (om aktiverat)
            if ADAPTIVE_L_ENABLED and not START_MODE:
                # Uppdatera VARJE tick om i position (dynamisk stop), annars var 10:e tick
                update_interval = 1 if pos.side != "FLAT" else ADAPTIVE_L_UPDATE_INTERVAL
                
                if tick % update_interval == 0 and len(py) >= adaptive_L_calc.trend_detect_window:
                    # Konvertera py till Decimal för beräkning
                    price_history = [Decimal(str(p)) for p in py]
                    new_L, diag = adaptive_L_calc.calculate_adaptive_L(price_history)
                    
                    # Uppdatera L om förändringen är signifikant
                    # Trailing stop: L får bara flyttas åt "rätt" håll (upp för LONG, ner för SHORT)
                    min_change = 0.00005 if pos.side != "FLAT" else 0.0001
                    
                    # Beslut om L ska uppdateras
                    should_update = False
                    if pos.side == "FLAT":
                        # Ingen position: uppdatera fritt
                        should_update = adaptive_L_calc.should_update_L(L, new_L, min_change_pct=min_change)
                    elif pos.side == "LONG":
                        # LONG: L får bara gå UPP (trailing stop uppåt)
                        if new_L > L and adaptive_L_calc.should_update_L(L, new_L, min_change_pct=min_change):
                            should_update = True
                    elif pos.side == "SHORT":
                        # SHORT: L får bara gå NER (trailing stop nedåt)
                        if new_L < L and adaptive_L_calc.should_update_L(L, new_L, min_change_pct=min_change):
                            should_update = True
                    
                    if should_update:
                        old_L = L
                        L = new_L
                        # Logga alltid när i position, annars bara vid märkbar trend
                        if pos.side != "FLAT" or diag['trend_strength'] > 0.1:
                            in_pos = f" [TRAILING {pos.side}]" if pos.side != "FLAT" else ""
                            print(f"🧠 Adaptive L: {float(old_L):.2f} → {float(L):.2f} "
                                  f"(trend: {diag['trend_direction']}, styrka: {diag['trend_strength']:.2f}){in_pos}")

            pos.update_extremes(price)

            # Progressiv scaling (om position finns)
            if pos.side != "FLAT":
                check_scale_in(price)
                check_scale_out(price)

            # 🛡️ KRITISK: Kolla max loss protection FÖRST (innan normal exit)
            if pos.side != "FLAT":
                if check_max_loss_protection(price):
                    # Position stängdes av safety - skippa normal exit/entry
                    refresh_lines(price)
                    tick += 1
                    time.sleep(POLL_SEC)
                    continue

            # EXIT → ENTRY (kedja/vändning) sker inne i do_exit/maybe_exit
            maybe_exit(price)
            maybe_enter(price)

            # Uppdatera graf VARJE tick när i position, annars var 3:e tick
            chart_interval = 1 if pos.side != "FLAT" else 3
            if tick % chart_interval == 0:
                refresh_lines(price)

            tick += 1
            time.sleep(POLL_SEC)

    except KeyboardInterrupt:
        change, pct = paper.session_pnl()
        print("\n🛑 Avslutar...")
        print(f"💰 Sessionens resultat (USDT-förändring): {change:+.4f} USDT  ({pct:+.4f} %)")
        
        # Visa alla exit-resultat från denna session
        print("\n📋 Exit-sammanfattning:")
        total_exits = 0
        wins = 0
        losses = 0
        breakevens = 0
        total_pnl = Decimal("0")
        
        # Läs sessions start-tid som string för jämförelse
        session_start_str = SESSION_START.strftime("%Y-%m-%d")
        
        try:
            with open(ORDERS_CSV, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                for line in lines:
                    # Kolla om det är en EXIT-rad från dagens session
                    if 'EXIT' in line and session_start_str in line:
                        parts = line.strip().split(',')
                        if len(parts) >= 10:
                            timestamp = parts[0]
                            state = parts[1]
                            pnl_usd = Decimal(parts[8]) if parts[8] else Decimal("0")
                            pnl_pct = Decimal(parts[9]) if parts[9] else Decimal("0")
                            total_exits += 1
                            total_pnl += pnl_usd
                            
                            if pnl_usd > 0:
                                wins += 1
                                print(f"  ✅ {timestamp[:19]} {state}: +{pnl_usd:.4f} USDT (+{pnl_pct:.2f}%)")
                            elif pnl_usd < 0:
                                losses += 1
                                print(f"  ❌ {timestamp[:19]} {state}: {pnl_usd:.4f} USDT ({pnl_pct:.2f}%)")
                            else:
                                breakevens += 1
                                print(f"  ➖ {timestamp[:19]} {state}: {pnl_usd:.4f} USDT ({pnl_pct:.2f}%)")
        except Exception as e:
            print(f"⚠️ Kunde inte läsa exit-historik: {e}")
        
        if total_exits > 0:
            win_rate = (wins / total_exits * 100) if total_exits > 0 else 0
            print(f"\n📊 Totalt: {total_exits} exits | Vinster: {wins} | Förluster: {losses} | BE: {breakevens}")
            print(f"📈 Win rate: {win_rate:.1f}% | Total PnL från exits: {total_pnl:+.4f} USDT")
        
        print(f"\n💼 Slutliga saldon: {paper.snapshot()}")
        print(f"📁 Orders logg: {ORDERS_CSV}")

        # session summary
        end_usdt = paper.balances["USDT"]
        end_btc  = paper.balances["BTC"]
        SESSION_END = datetime.now(timezone.utc)
        emp_stat = mk.empirical_stationary()
        trans = mk.transition_matrix()

        header = [
            "session_start_utc","session_end_utc","symbol",
            "tp_pct","taker_fee_pct","poll_sec","rearm_gap_pct","min_move_pct",
            "tp_chain","tp_chain_gap_pct","tp_chain_max","cooldown_sec",
            "vol_filter","vol_period","min_volatility",
            "loss_pause_cnt","loss_pause_sec","pause_resume_pct","reentry_break_pct",
            "dir_bias_count","dir_bias_cooldown",
            "exits","pnl_usdt","pnl_pct","end_usdt","end_btc","mode",
            "cnt_LW","cnt_LB","cnt_SW","cnt_SB",
            "emp_LW","emp_LB","emp_SW","emp_SB",
            "T_LW->LW","T_LW->LB","T_LW->SW","T_LW->SB",
            "T_LB->LW","T_LB->LB","T_LB->SW","T_LB->SB",
            "T_SW->LW","T_SW->LB","T_SW->SW","T_SW->SB",
            "T_SB->LW","T_SB->LB","T_SB->SW","T_SB->SB",
        ]
        row = [
            SESSION_START.isoformat(timespec="seconds")+"Z",
            SESSION_END.isoformat(timespec="seconds")+"Z",
            SYMBOL,
            f"{TP_PCT}", f"{TAKER_FEE_PCT}", f"{POLL_SEC}", f"{REARM_GAP_PCT}", f"{MIN_MOVE_PCT}",
            f"{TP_CHAIN}", f"{TP_CHAIN_GAP_PCT}", f"{TP_CHAIN_MAX}", f"{COOLDOWN_SEC}",
            f"{VOL_FILTER}", f"{VOL_PERIOD}", f"{MIN_VOL}",
            f"{LOSS_PAUSE_CNT}", f"{LOSS_PAUSE_SEC}", f"{PAUSE_RESUME_PCT}", f"{REENTRY_BREAK_PCT}",
            f"{DIR_BIAS_COUNT}", f"{DIR_BIAS_COOLDOWN}",
            paper.exits, *paper.session_pnl(), f"{end_usdt}", f"{end_btc}", "paper",
            mk.counts["LW"], mk.counts["LB"], mk.counts["SW"], mk.counts["SB"],
            f"{emp_stat['LW']:.6f}", f"{emp_stat['LB']:.6f}", f"{emp_stat['SW']:.6f}", f"{emp_stat['SB']:.6f}",
            f"{trans[0][0]:.6f}", f"{trans[0][1]:.6f}", f"{trans[0][2]:.6f}", f"{trans[0][3]:.6f}",
            f"{trans[1][0]:.6f}", f"{trans[1][1]:.6f}", f"{trans[1][2]:.6f}", f"{trans[1][3]:.6f}",
            f"{trans[2][0]:.6f}", f"{trans[2][1]:.6f}", f"{trans[2][2]:.6f}", f"{trans[2][3]:.6f}",
            f"{trans[3][0]:.6f}", f"{trans[3][1]:.6f}", f"{trans[3][2]:.6f}", f"{trans[3][3]:.6f}",
        ]
        append_csv_row(SUMMARY_CSV, row, header=header)
        print(f"🧾 Sessions-summering: {SUMMARY_CSV}")

    except requests.exceptions.RequestException as ex:
        print(f"⚠️ Nätverksfel vid prishämtning: {ex}")
        time.sleep(2.0)

    except Exception as ex:
        print(f"❌ Fel i huvudloopen: {ex}")
        time.sleep(1.0)

if __name__ == "__main__":
    main()
