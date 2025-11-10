# -*- coding: utf-8 -*-
"""
Markov Breakout – LIVE PRICES + PAPER TRADING (SMART + TP-CHAIN)
----------------------------------------------------------------
- Läser RIKTIGA marknadspriser från Binance (public API – kräver inga nycklar)
- Kör din breakout/BE-logik i PAPER MODE (inga riktiga orders)
- Startband: två L-startlinjer (övre/nedre). Första brott:
    • öppna position (LONG vid brott uppåt, SHORT vid brott nedåt)
    • sätt L = entry-priset
    • dölj startlinjerna
- Re-arming: L uppdateras till EXIT-priset vid TP eller BE
- BE: direkt vändning (alltid inne efter BE)
- NYTT: TP-kedja (tp_chain): fortsätt i samma riktning efter TP (utan att gå FLAT)
- Grafik: pris + aktiva linjer (L/TP/BE) + kompakt infobox (en ruta)
- CSV-logg: orders_paper.csv + session_summary.csv

Kör:
    python "Markov breakout live paper smart.py"
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
        self.tp_chain_count: int = 0
        self.entry_time: float = 0.0
        self.high: Optional[Decimal] = None
        self.low: Optional[Decimal] = None
        self.scaled_in_levels: list = []  # Vilka scale-in nivåer som triggats
        self.scaled_out_levels: list = []  # Vilka scale-out nivåer som triggats

    def flat(self):
        self.side = "FLAT"
        self.entry = None
        self.qty = Decimal("0")
        self.initial_qty = Decimal("0")
        self.tp_chain_count = 0
        self.entry_time = 0.0
        self.high = None
        self.low = None
        self.scaled_in_levels = []
        self.scaled_out_levels = []

    def update_extremes(self, price: Decimal) -> None:
        if self.entry is None or self.side == "FLAT":
            return
        if self.high is None or price > self.high:
            self.high = price
        if self.low is None or price < self.low:
            self.low = price

pos   = Position()
mk    = MarkovState()
paper = PaperBroker(START_USDT, START_BTC)

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

print(f"🚀 Startar Binance LIVE-priser (paper mode={'ON' if ORDER_TEST else 'OFF'})")
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
    """Öka position när priset går åt rätt håll."""
    if not PROGRESSIVE_SCALING or not SCALE_IN_ENABLED:
        return
    if pos.side == "FLAT" or pos.entry is None or pos.initial_qty == 0:
        return
    
    # Beräkna profit %
    if pos.side == "LONG":
        profit_pct = (price - pos.entry) / pos.entry
    else:
        profit_pct = (pos.entry - price) / pos.entry
    
    # Kolla varje scale-in nivå
    for i, level in enumerate(SCALE_IN_LEVELS):
        if i in pos.scaled_in_levels:
            continue  # Redan triggad
        
        if profit_pct >= level:
            # Check att vi inte överskrider max
            current_mult = pos.qty / pos.initial_qty
            if current_mult >= MAX_SCALE_MULT:
                continue
            
            # Lägg till baserat på ORIGINAL ORDER_QTY, inte initial_qty
            # Detta gör att vi skalar upp snabbt även om vi börjar liten
            add_qty = (ORDER_QTY * SCALE_IN_MULT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            new_qty = pos.qty + add_qty
            
            # Begränsa till max (relativt initial_qty)
            if new_qty / pos.initial_qty > MAX_SCALE_MULT:
                add_qty = (pos.initial_qty * MAX_SCALE_MULT) - pos.qty
                new_qty = pos.qty + add_qty
            
            if add_qty > 0:
                if ORDER_TEST:
                    if pos.side == "LONG":
                        paper.market_buy(SYMBOL, add_qty, price)
                    else:
                        paper.market_sell(SYMBOL, add_qty, price)
                
                pos.qty = new_qty
                pos.scaled_in_levels.append(i)
                total_mult = pos.qty / pos.initial_qty
                print(f"➕ SCALE IN (+{float(profit_pct)*100:.2f}%): Add {add_qty} @ {price:.2f} | Total: {pos.qty} ({total_mult:.1f}x)")
                
                # Lägg till text-markering på grafen (kompakt)
                trade_annotations.append({
                    'abs_tick': tick_offset + len(py) - 1,  # Absolut tick-nummer
                    'y': float(price),
                    'text': f'+{total_mult:.1f}x',  # En rad
                    'color': 'white',
                    'bgcolor': 'green' if pos.side == "LONG" else 'darkred',
                    'size': 5  # Mindre för scale events
                })

def check_scale_out(price: Decimal):
    """Minska position när priset går åt fel håll (drawdown från high/low)."""
    if not PROGRESSIVE_SCALING or not SCALE_OUT_ENABLED:
        return
    if pos.side == "FLAT" or pos.entry is None or pos.initial_qty == 0:
        return
    if pos.high is None or pos.low is None:
        return
    
    # Beräkna drawdown från peak (viktigare än loss från entry!)
    if pos.side == "LONG":
        # För LONG: hur mycket har vi tappat från högsta punkten?
        drawdown_pct = (pos.high - price) / pos.high if pos.high > 0 else Decimal("0")
    else:
        # För SHORT: hur mycket har vi tappat från lägsta punkten?
        drawdown_pct = (price - pos.low) / pos.low if pos.low > 0 else Decimal("0")
    
    # Kolla varje scale-out nivå
    for i, level in enumerate(SCALE_OUT_LEVELS):
        if i in pos.scaled_out_levels:
            continue  # Redan triggad
        
        if drawdown_pct >= level:
            # Check att vi inte går under min
            current_mult = pos.qty / pos.initial_qty
            if current_mult <= MIN_SCALE_MULT:
                continue
            
            reduce_qty = (pos.qty * SCALE_OUT_MULT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            new_qty = pos.qty - reduce_qty
            
            # Begränsa till min
            if new_qty / pos.initial_qty < MIN_SCALE_MULT:
                new_qty = pos.initial_qty * MIN_SCALE_MULT
                reduce_qty = pos.qty - new_qty
            
            if reduce_qty > 0:
                if ORDER_TEST:
                    if pos.side == "LONG":
                        paper.market_sell(SYMBOL, reduce_qty, price)
                    else:
                        paper.market_buy(SYMBOL, reduce_qty, price)
                
                pos.qty = new_qty
                pos.scaled_out_levels.append(i)
                total_mult = pos.qty / pos.initial_qty
                print(f"➖ SCALE OUT (drawdown -{float(drawdown_pct)*100:.2f}%): Exit {reduce_qty} @ {price:.2f} | Remaining: {pos.qty} ({total_mult:.1f}x)")
                
                # Lägg till text-markering på grafen (kompakt)
                trade_annotations.append({
                    'abs_tick': tick_offset + len(py) - 1,  # Absolut tick-nummer
                    'y': float(price),
                    'text': f'−{total_mult:.1f}x',  # En rad
                    'color': 'black',
                    'bgcolor': 'yellow',
                    'size': 5  # Mindre för scale events
                })

# ----------------------- EXIT-logik ------------------------------------------
def do_exit(side: str, exit_price: Decimal, state_tag: str):
    """Stäng position, logga, re-arma L, och hantera TP-kedja/BE-vändning."""
    global L, block_long_until, block_short_until, loss_pause_state
    global consec_long_losses, consec_short_losses, last_long_rearm, last_short_rearm
    entry = pos.entry if pos.entry is not None else exit_price
    entry_price = entry
    entry_time = pos.entry_time
    price_high = pos.high if pos.high is not None else exit_price
    price_low = pos.low if pos.low is not None else exit_price
    if price_high is not None and price_low is not None and price_high < price_low:
        price_high, price_low = price_low, price_high

    # Logg + PnL (använd faktisk qty från positionen)
    qty = pos.qty if pos.qty > 0 else ORDER_QTY
    pnl_usd, pnl_pct = paper.log_exit(state_tag, side, SYMBOL, qty, exit_price, entry)
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
    mfe_abs: Decimal
    mae_abs: Decimal
    if side == "LONG":
        mfe_abs = (price_high - entry_price) if price_high >= entry_price else zero
        mae_abs = (entry_price - price_low) if price_low <= entry_price else zero
    else:
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

    # Re-arm: ny L = exitpris
    L = exit_price
    if side == "LONG":
        last_long_rearm = exit_price
    else:
        last_short_rearm = exit_price
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

    # BE: gå FLAT och invänta nytt brott
    if state_tag in ("LB", "SB"):
        pos.flat()
        pos.tp_chain_count = 0
        return

    # TP: antingen kedja eller gå FLAT
    if state_tag in ("LW", "SW"):
        if TP_CHAIN and pos.tp_chain_count < TP_CHAIN_MAX:
            pos.tp_chain_count += 1
            # Kedja: fortsätt i samma riktning – men kräv ett litet extra brott mot L (anti-återstuds)
            thr = chain_threshold(side, L)
            # Försök omedelbart om priset redan passerat tröskeln, annars invänta nästa korsning
            if side == "LONG":
                instant_ok = (
                    last_price_cache is not None
                    and last_price_cache >= thr
                    and (REENTRY_BREAK_PCT == 0 or last_price_cache >= last_long_rearm * (Decimal("1") + REENTRY_BREAK_PCT))
                    and time.time() >= block_long_until
                )
                if instant_ok:
                    enter_long(last_price_cache)
                else:
                    pos.side = "FLAT"  # tillfälligt; entry sker i maybe_enter() när brottet kommer
            else:
                instant_ok = (
                    last_price_cache is not None
                    and last_price_cache <= thr
                    and (REENTRY_BREAK_PCT == 0 or last_price_cache <= last_short_rearm * (Decimal("1") - REENTRY_BREAK_PCT))
                    and time.time() >= block_short_until
                )
                if instant_ok:
                    enter_short(last_price_cache)
                else:
                    pos.side = "FLAT"
            if COOLDOWN_SEC > 0:
                time.sleep(COOLDOWN_SEC)
            return
        else:
            pos.flat()
            return

# ----------------------- ENTRY/EXIT kontroller -------------------------------
def maybe_exit(price: Decimal):
    """Exit på TP eller L-korsning (dynamisk stop); re-arma L; hantera kedja samt pauslogik."""
    qty = pos.qty if pos.qty > 0 else ORDER_QTY
    
    if pos.side == "LONG" and pos.entry is not None:
        tp_level = pos.entry * (Decimal("1") + TP_PCT)
        # Exit om priset korsar UNDER L (använd L som hard stop loss)
        # Minimal marginal för att undvika falskt alarm vid tiny tick
        stop_level = L * (Decimal("1") - MIN_MOVE_PCT * Decimal("0.5"))
        
        if price >= tp_level:
            if ORDER_TEST:
                paper.market_sell(SYMBOL, qty, price)
            do_exit("LONG", price, "LW")
            refresh_lines(price)  # Uppdatera graf omedelbart
        elif price <= stop_level:
            # L-KORSNING: Stäng position omedelbart!
            if ORDER_TEST:
                paper.market_sell(SYMBOL, qty, price)
            do_exit("LONG", price, "LB")
            refresh_lines(price)  # Uppdatera graf omedelbart

    elif pos.side == "SHORT" and pos.entry is not None:
        tp_level = pos.entry * (Decimal("1") - TP_PCT)
        # Exit om priset korsar ÖVER L (använd L som hard stop loss)
        # Minimal marginal för att undvika falskt alarm vid tiny tick
        stop_level = L * (Decimal("1") + MIN_MOVE_PCT * Decimal("0.5"))
        
        if price <= tp_level:
            if ORDER_TEST:
                paper.market_buy(SYMBOL, qty, price)
            do_exit("SHORT", price, "SW")
            refresh_lines(price)  # Uppdatera graf omedelbart
        elif price >= stop_level:
            # L-KORSNING: Stäng position omedelbart!
            if ORDER_TEST:
                paper.market_buy(SYMBOL, qty, price)
            do_exit("SHORT", price, "SB")
            refresh_lines(price)  # Uppdatera graf omedelbart

def maybe_enter(price: Decimal):
    """Startband → första entry. I drift → entry på faktisk korsning med rearm-gap och min move."""
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

    # STARTFAS: bryt startbandet => direkt entry + sätt L = entry + dölj bandet
    if START_MODE:
        if price > L_upper:
            START_MODE = False
            L = price  # L följer entry direkt
            enter_long(price)
            return
        elif price < L_lower:
            START_MODE = False
            L = price
            enter_short(price)
            return
        else:
            return  # invänta brott

    # Drift: kräver faktisk korsning genom L med rearm-gap
    if pos.side == "FLAT":
        if VOL_FILTER and VOL_PERIOD > 1 and len(py) >= VOL_PERIOD:
            recent_prices = list(py)[-VOL_PERIOD:]
            local_max = max(recent_prices)
            local_min = min(recent_prices)
            if local_min > 0:
                span_pct = (Decimal(str(local_max)) - Decimal(str(local_min))) / Decimal(str(local_min))
            else:
                span_pct = Decimal("0")
            if span_pct < MIN_VOL:
                return

        reentry_long_ok = True
        reentry_short_ok = True
        if not START_MODE and REENTRY_BREAK_PCT > 0:
            reentry_long_ok = price >= last_long_rearm * (Decimal("1") + REENTRY_BREAK_PCT)
            reentry_short_ok = price <= last_short_rearm * (Decimal("1") - REENTRY_BREAK_PCT)

        if now_ts < block_long_until:
            reentry_long_ok = False
        if now_ts < block_short_until:
            reentry_short_ok = False

        up_ok   = price > L * (Decimal("1") + REARM_GAP_PCT)
        down_ok = price < L * (Decimal("1") - REARM_GAP_PCT)
        if up_ok and ((price - L) / L >= MIN_MOVE_PCT) and reentry_long_ok:
            enter_long(price)
        elif down_ok and ((L - price) / L >= MIN_MOVE_PCT) and reentry_short_ok:
            enter_short(price)

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

ax.set_title(f"{SYMBOL} – Markov Breakout (Paper)", fontsize=12, fontweight='bold')
ax.set_xlabel("Ticks")
ax.set_ylabel("Price")
ax.grid(True, alpha=0.3)

# Legend för textmarkeringar
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='green', edgecolor='black', label='L↑/S↓: Entry'),
    Patch(facecolor='green', edgecolor='black', label='+: Scale In'),
    Patch(facecolor='yellow', edgecolor='black', label='−: Scale Out'),
    Patch(facecolor='green', edgecolor='black', label='✓: Exit Vinst'),
    Patch(facecolor='darkred', edgecolor='black', label='✗: Exit Förlust'),
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

    # TP i drift (när position är aktiv) - BE används EJ längre (L är stop)
    if not START_MODE and pos.entry is not None and pos.side != "FLAT":
        if pos.side == "LONG":
            TP_val = float(pos.entry * (Decimal("1") + TP_PCT))
        else:
            TP_val = float(pos.entry * (Decimal("1") - TP_PCT))

        TP_line.set_data(xs, [TP_val]*len(xs))
        TP_line.set_visible(True)
        # Dölj BE-linje (vi använder L som stop istället)
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
        
        # Inkludera TP i zoom om position finns
        if not START_MODE and pos.entry is not None and pos.side != "FLAT":
            if pos.side == "LONG":
                TP_val = float(pos.entry * (Decimal("1") + TP_PCT))
                hi = max(hi, TP_val)
            else:
                TP_val = float(pos.entry * (Decimal("1") - TP_PCT))
                lo = min(lo, TP_val)
        
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
        
        # TP label (endast när position aktiv)
        if not START_MODE and pos.entry is not None and pos.side != "FLAT":
            if pos.side == "LONG":
                TP_val = float(pos.entry * (Decimal("1") + TP_PCT))
            else:
                TP_val = float(pos.entry * (Decimal("1") - TP_PCT))
            
            TP_text.set_position((x_pos, TP_val))
            TP_text.set_text(f' TP: {TP_val:.2f}')
            TP_text.set_visible(True)
        else:
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
    
    # Kompakt position info (höger överkant)
    if pos.side != "FLAT" and pos.entry is not None:
        pnl_pct = ((float(current_price) - float(pos.entry)) / float(pos.entry) * 100) if pos.side == "LONG" else ((float(pos.entry) - float(current_price)) / float(pos.entry) * 100)
        pos_info = f"{pos.side} @ {float(pos.entry):.2f} | PnL: {pnl_pct:+.2f}%"
    else:
        pos_info = f"FLAT | USDT: {float(paper.balances['USDT']):.2f}"
    pos_text.set_text(pos_info)

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
        print(f"💰 Sessionens resultat: {change:+.4f} USDT  ({pct:+.4f} %)")
        print(f"📊 Slutliga saldon: {paper.snapshot()}")
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
