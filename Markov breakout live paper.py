# -*- coding: utf-8 -*-
"""
Markov Breakout – LIVE PRICES + PAPER TRADING (SMART LONG+SHORT)
---------------------------------------------------------------------------
Detta skript läser live-priser från Binance och handlar BÅDE LONG och SHORT.
Kollar automatiskt om tillräckligt medel finns innan varje trade.

LONG: Kräver USDT för att köpa BTC
SHORT: Kräver BTC för att sälja

Kör:
    python "markov breakout live paper SMART.py"
"""

from __future__ import annotations
import os
import json
import time
import csv
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
from typing import Dict

# --- Säkra imports (requests behövs bara för pris-hämtning) -------------------
try:
    import requests  # pip install requests
except ImportError as e:
    raise SystemExit(
        "requests saknas. Kör:\n    pip install requests\n"
        "och starta sedan om skriptet."
    ) from e

# === Ladda config (tål UTF-8 BOM) ============================================
ROOT = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ROOT, "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
    cfg = json.load(f)

API_KEY     = cfg.get("api_key", "")
API_SECRET  = cfg.get("api_secret", "")
SYMBOL      = cfg.get("base_symbol", "BTCUSDT")
ORDER_TEST  = bool(cfg.get("order_test", True))   # True = PAPER MODE
ORDER_QTY   = Decimal(str(cfg.get("order_qty", 0.001))).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

# Strategiparametrar
TP_PCT          = Decimal(str(cfg.get("tp_pct", 0.0010)))        # t.ex. 0.0010 = 0.10%
TAKER_FEE_PCT   = Decimal(str(cfg.get("taker_fee_pct", 0.0004))) # 0.04% default
POLL_SEC        = float(cfg.get("poll_sec", 0.5))                 # polling-intervall sek

# Fil/loggar
LOG_DIR     = os.path.join(ROOT, "logs")
ORDERS_CSV  = os.path.join(LOG_DIR, "orders_paper.csv")
os.makedirs(LOG_DIR, exist_ok=True)

# === Hjälp: live-pris från Binance (kräver inga nycklar) =====================
BINANCE_PUBLIC = "https://api.binance.com"      # ✅ RIKTIGA MARKNADSPRISER!

def get_live_price(symbol: str) -> Decimal:
    """Hämtar det senaste priset från Binance (RIKTIGT marknadspris)"""
    r = requests.get(f"{BINANCE_PUBLIC}/api/v3/ticker/price",
                     params={"symbol": symbol},
                     timeout=5)
    r.raise_for_status()
    return Decimal(r.json()["price"])

# === PaperBroker: simulerar order-utförande lokalt ===========================
class PaperBroker:
    """
    Simulerar Binance-trades lokalt (PAPER TRADING).
    - Använder riktiga marknadspriser
    - Simulerar order-utförande och avgifter
    - Sparar balans i minnet (ingen riktig handel)
    """
    def __init__(self, starting_balances: Dict[str, str|float|Decimal] | None = None):
        self.balances: Dict[str, Decimal] = {"USDT": Decimal("10000"), "BTC": Decimal("0")}
        if starting_balances:
            for k, v in starting_balances.items():
                self.balances[k] = Decimal(str(v))
        
        # CSV-head
        if not os.path.exists(ORDERS_CSV):
            with open(ORDERS_CSV, "w", newline="", encoding="utf-8") as wf:
                cw = csv.writer(wf)
                cw.writerow(["ts","side","symbol","qty","price","usdt_delta","btc_delta","note"])

    def _write(self, side: str, symbol: str, qty: Decimal, price: Decimal, usdt_delta: Decimal, btc_delta: Decimal, note: str):
        """Skriv till logg med retry-logik för låsta filer"""
        max_retries = 5
        retry_delay = 0.2
        
        for attempt in range(max_retries):
            try:
                with open(ORDERS_CSV, "a", newline="", encoding="utf-8") as wf:
                    cw = csv.writer(wf)
                    cw.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds")+"Z",
                                 side, symbol, f"{qty}", f"{price}", f"{usdt_delta}", f"{btc_delta}", note])
                return  # Lyckades
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    print(f"⚠️ Kan inte skriva till {ORDERS_CSV} - stäng Excel om den är öppen")
            except Exception as e:
                print(f"⚠️ Loggningsfel: {e}")
                return

    def can_buy(self, qty: Decimal, price: Decimal) -> bool:
        """Kollar om tillräckligt USDT för att köpa"""
        cost = (price * qty).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        fee  = (cost * TAKER_FEE_PCT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        total = cost + fee
        return self.balances.get("USDT", Decimal("0")) >= total

    def can_sell(self, qty: Decimal) -> bool:
        """Kollar om tillräckligt BTC för att sälja"""
        return self.balances.get("BTC", Decimal("0")) >= qty

    def market_buy(self, symbol: str, qty: Decimal, price: Decimal):
        """Simulerar MARKET BUY med avgifter"""
        cost = (price * qty).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        fee  = (cost * TAKER_FEE_PCT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        total = cost + fee
        
        if self.balances["USDT"] < total:
            raise RuntimeError(f"PaperBroker: otillräckligt USDT (behöver {total}, har {self.balances['USDT']})")
        
        self.balances["USDT"] -= total
        self.balances["BTC"]  += qty
        print(f"✅ [PAPER BUY] {qty} {symbol} @ {price}  (fee {fee} USDT)")
        self._write("BUY", symbol, qty, price, -total, qty, "paper")

    def market_sell(self, symbol: str, qty: Decimal, price: Decimal):
        """Simulerar MARKET SELL med avgifter"""
        if self.balances["BTC"] < qty:
            raise RuntimeError(f"PaperBroker: otillräckligt BTC (behöver {qty}, har {self.balances['BTC']})")
        
        proceeds = (price * qty).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        fee  = (proceeds * TAKER_FEE_PCT).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        net  = proceeds - fee
        
        self.balances["BTC"]  -= qty
        self.balances["USDT"] += net
        print(f"✅ [PAPER SELL] {qty} {symbol} @ {price}  (fee {fee} USDT)")
        self._write("SELL", symbol, qty, price, net, -qty, "paper")

    def snapshot(self) -> Dict[str, str]:
        """Returnera nuvarande saldon"""
        return {k: str(v) for k,v in self.balances.items()}

# === Strategi-tillstånd ======================================================
class Position:
    def __init__(self):
        self.side: str = "FLAT"      # "LONG" / "SHORT" / "FLAT"
        self.entry: Decimal | None = None

    def flat(self):
        self.side = "FLAT"
        self.entry = None

# === Globalt tillstånd ========================================================
pos = Position()

# Läs startbalans från config
paper_usdt = str(cfg.get("paper_usdt", "5000"))
paper_btc = str(cfg.get("paper_btc", "0.05"))
paper = PaperBroker({"USDT": paper_usdt, "BTC": paper_btc})

# Startnivå L = senast kända pris
print("🔄 Hämtar startpris från Binance...")
L = get_live_price(SYMBOL)
print(f"🚀 Startar Binance LIVE-priser (SMART LONG+SHORT mode)")
print(f"🔧 Startnivå L={L:.2f} för {SYMBOL}")
print(f"📡 Polling-intervall: {POLL_SEC}s  TP={TP_PCT*100:.3f}%  Fee≈{TAKER_FEE_PCT*100:.3f}%")
print(f"💰 Startbalans: USDT={paper.balances['USDT']:.2f} BTC={paper.balances['BTC']:.8f}")
btc_value_usd = paper.balances['BTC'] * L
total_value = paper.balances['USDT'] + btc_value_usd
print(f"💵 Total värde: ${total_value:.2f} (${paper.balances['USDT']:.2f} USDT + ${btc_value_usd:.2f} BTC)")
print(f"📊 Strategin kollar automatiskt medel för både LONG och SHORT\n")

def maybe_enter(price: Decimal):
    """
    Brytlogik med SMART kontroll:
    - LONG: Kräver tillräckligt USDT
    - SHORT: Kräver tillräckligt BTC
    Skippar automatiskt om inte tillräckligt medel.
    """
    global L
    if pos.side == "FLAT":
        if price > L:
            # Försök ENTER LONG (kräver USDT)
            if ORDER_TEST:
                if paper.can_buy(ORDER_QTY, price):
                    pos.side  = "LONG"
                    pos.entry = price
                    paper.market_buy(SYMBOL, ORDER_QTY, price)
                    print(f"📈 ENTER LONG @ {price:.2f} qty={ORDER_QTY}")
                else:
                    usdt = paper.balances.get("USDT", Decimal("0"))
                    needed = ORDER_QTY * price * (Decimal("1") + TAKER_FEE_PCT)
                    print(f"⏭️  SKIP LONG @ {price:.2f} (otillräckligt USDT: har {usdt:.2f}, behöver {needed:.2f})")
            else:
                # TODO: Riktig order här
                pass
            
        elif price < L:
            # Försök ENTER SHORT (kräver BTC)
            if ORDER_TEST:
                if paper.can_sell(ORDER_QTY):
                    pos.side  = "SHORT"
                    pos.entry = price
                    paper.market_sell(SYMBOL, ORDER_QTY, price)
                    print(f"📉 ENTER SHORT @ {price:.2f} qty={ORDER_QTY}")
                else:
                    btc = paper.balances.get("BTC", Decimal("0"))
                    print(f"⏭️  SKIP SHORT @ {price:.2f} (otillräckligt BTC: har {btc:.8f}, behöver {ORDER_QTY})")
            else:
                # TODO: Riktig order här
                pass

def maybe_exit(price: Decimal):
    """Exit vid TP eller BE (breakeven minus avgift). Sätter ny L till exit-priset."""
    global L
    
    if pos.side == "LONG" and pos.entry is not None:
        move = (price - pos.entry) / pos.entry
        
        # TP eller BE-villkor
        if move >= TP_PCT:
            # Take Profit
            if ORDER_TEST:
                paper.market_sell(SYMBOL, ORDER_QTY, price)
            else:
                # TODO: riktig order här
                pass
            pnl_usd = (price - pos.entry) * ORDER_QTY
            print(f"🔚 EXIT LONG @ {price:.2f} (entry {pos.entry:.2f})  PnL: {move*100:.3f}% (${pnl_usd:.2f})  [TP]")
            L = price
            pos.flat()
            
        elif price <= pos.entry * (Decimal("1") - TAKER_FEE_PCT):
            # Breakeven (pris sjunker tillbaka)
            if ORDER_TEST:
                paper.market_sell(SYMBOL, ORDER_QTY, price)
            else:
                # TODO: riktig order här
                pass
            pnl_usd = (price - pos.entry) * ORDER_QTY
            print(f"🔚 EXIT LONG @ {price:.2f} (entry {pos.entry:.2f})  PnL: {move*100:.3f}% (${pnl_usd:.2f})  [BE]")
            L = price
            pos.flat()

    elif pos.side == "SHORT" and pos.entry is not None:
        move = (pos.entry - price) / pos.entry
        
        # TP eller BE-villkor
        if move >= TP_PCT:
            # Take Profit
            if ORDER_TEST:
                paper.market_buy(SYMBOL, ORDER_QTY, price)
            else:
                # TODO: riktig order här
                pass
            pnl_usd = (pos.entry - price) * ORDER_QTY
            print(f"🔚 EXIT SHORT @ {price:.2f} (entry {pos.entry:.2f})  PnL: {move*100:.3f}% (${pnl_usd:.2f})  [TP]")
            L = price
            pos.flat()
            
        elif price >= pos.entry * (Decimal("1") + TAKER_FEE_PCT):
            # Breakeven (pris stiger tillbaka)
            if ORDER_TEST:
                paper.market_buy(SYMBOL, ORDER_QTY, price)
            else:
                # TODO: riktig order här
                pass
            pnl_usd = (pos.entry - price) * ORDER_QTY
            print(f"🔚 EXIT SHORT @ {price:.2f} (entry {pos.entry:.2f})  PnL: {move*100:.3f}% (${pnl_usd:.2f})  [BE]")
            L = price
            pos.flat()

def main():
    last_price = None
    tick_count = 0
    
    print("▶️  Startar trading loop... (Ctrl+C för att avsluta)\n")
    
    while True:
        try:
            price = get_live_price(SYMBOL)
            tick_count += 1
            
            if last_price is None:
                last_price = price

            # 1) Exit-logik först (om position finns)
            maybe_exit(price)

            # 2) Entry-logik (cross genom L)
            #    Vi kräver faktisk korsning (inte bara > eller <) för att undvika "fladdrig" spam.
            crossed_up   = (last_price <= L) and (price > L)
            crossed_down = (last_price >= L) and (price < L)
            if pos.side == "FLAT" and (crossed_up or crossed_down):
                maybe_enter(price)

            # 3) Status-info var 20:e tick (10 sekunder med 0.5s polling)
            if tick_count % 20 == 0:
                print(f"ℹ️  Pris: {price:.2f} | L: {L:.2f} | Pos: {pos.side} | USDT={paper.balances['USDT']:.2f} BTC={paper.balances['BTC']:.8f}")
            
            last_price = price
            time.sleep(POLL_SEC)

        except KeyboardInterrupt:
            print("\n🛑 Avslutar...")
            print(f"📊 Slutliga saldon: {paper.snapshot()}")
            print(f"📁 Loggar sparade i: {ORDERS_CSV}")
            break
            
        except requests.exceptions.RequestException as ex:
            print(f"⚠️ Nätverksfel vid prishämtning: {ex}")
            time.sleep(2.0)
            
        except Exception as ex:
            print(f"❌ Fel i huvudloopen: {ex}")
            import traceback
            traceback.print_exc()
            time.sleep(1.0)

if __name__ == "__main__":
    main()