import os
import json
import csv
import time
import threading
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
from collections import defaultdict

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException


# === Ladda config (tål UTF-8 BOM) ===
ROOT = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(ROOT, "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
    cfg = json.load(f)

API_KEY = cfg["api_key"]
API_SECRET = cfg["api_secret"]
SYMBOL = cfg.get("base_symbol", "BTCUSDT")
TESTNET = cfg.get("testnet", True)

# Strategiparametrar
TP_PCT = Decimal(str(cfg.get("tp_pct", 0.0010)))              # 0.10% take profit
TAKER_FEE_PCT = Decimal(str(cfg.get("taker_fee_pct", 0.0004))) # ungefärlig taker-fee
ORDER_QTY = Decimal(str(cfg.get("order_qty", 0.001)))         # kvantitet per affär

# Loggar
LOG_DIR = os.path.join(ROOT, "logs")
ORDERS_CSV = os.path.join(LOG_DIR, "orders.csv")
MARKOV_CSV = os.path.join(LOG_DIR, "markov.csv")
os.makedirs(LOG_DIR, exist_ok=True)


# === Hjälpfunktioner ===
def dquant(x: Decimal, step: Decimal) -> Decimal:
    if step == 0:
        return x
    decimals = abs(Decimal(str(step)).as_tuple().exponent)
    n = (x / step).to_integral_value(rounding=ROUND_DOWN)
    return (n * step).quantize(Decimal(10) ** -decimals, rounding=ROUND_DOWN)


def exchange_filters(client: Client, symbol: str):
    info = client.get_exchange_info()
    for s in info["symbols"]:
        if s["symbol"] == symbol:
            lot = next(f for f in s["filters"] if f["filterType"] == "LOT_SIZE")
            min_notional = next(f for f in s["filters"] if f["filterType"] in ("MIN_NOTIONAL", "NOTIONAL"))
            price_filter = next(f for f in s["filters"] if f["filterType"] == "PRICE_FILTER")
            return {
                "step_size": Decimal(lot["stepSize"]),
                "min_qty": Decimal(lot["minQty"]),
                "min_notional": Decimal(min_notional.get("minNotional", min_notional.get("notional", "0"))),
                "tick_size": Decimal(price_filter["tickSize"]),
            }
    raise ValueError(f"Hittar inte {symbol} i exchange_info")


def last_price(client: Client, symbol: str) -> Decimal:
    t = client.get_symbol_ticker(symbol=symbol)
    return Decimal(t["price"])


def avg_fill_price(resp: dict) -> Decimal:
    fills = resp.get("fills") or []
    if not fills:
        return Decimal(str(resp.get("price", "0") or "0"))
    notional = Decimal("0")
    qty = Decimal("0")
    for f in fills:
        p = Decimal(str(f["price"]))
        q = Decimal(str(f["qty"]))
        notional += p * q
        qty += q
    return (notional / qty) if qty > 0 else Decimal("0")


def log_order(row: list):
    """
    Loggar en order till CSV. Försöker igen om filen är låst (t.ex. öppen i Excel).
    """
    max_retries = 5
    retry_delay = 0.2
    
    for attempt in range(max_retries):
        try:
            create_header = not os.path.exists(ORDERS_CSV)
            with open(ORDERS_CSV, "a", newline="", encoding="utf-8") as fp:
                w = csv.writer(fp)
                if create_header:
                    w.writerow(["timestamp","symbol","side","qty","avg_price","notional","order_id","note"])
                w.writerow(row)
            return  # Lyckades, avsluta
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print(f"⚠️ Kan inte skriva till {ORDERS_CSV} - filen är låst (stäng Excel om den är öppen)")
        except Exception as e:
            print(f"⚠️ Loggningsfel: {e}")
            return


def load_markov_counts() -> dict:
    counts = defaultdict(int)
    if os.path.exists(MARKOV_CSV):
        with open(MARKOV_CSV, "r", encoding="utf-8") as fp:
            r = csv.reader(fp)
            _ = next(r, None)
            for row in r:
                a, b, c = row
                counts[(a, b)] = int(c)
    return counts


def save_markov_counts(counts: dict):
    with open(MARKOV_CSV, "w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["from_state", "to_state", "count"])
        for (a, b), c in sorted(counts.items()):
            w.writerow([a, b, c])


def stationary_distribution(counts: dict) -> dict:
    states = ["LW", "LB", "SW", "SB"]
    P = {s: {t: 0.0 for t in states} for s in states}
    for s in states:
        row_sum = sum(counts.get((s, t), 0) for t in states)
        if row_sum == 0:
            for t in states:
                P[s][t] = 1.0 / len(states)
        else:
            for t in states:
                P[s][t] = counts.get((s, t), 0) / row_sum
    pi = {s: 1.0 / len(states) for s in states}
    for _ in range(100):
        new = {t: 0.0 for t in states}
        for s in states:
            for t in states:
                new[t] += pi[s] * P[s][t]
        pi = new
    return pi


# === Strategi ===
class Strategy:
    def __init__(self, client: Client, symbol: str):
        self.client = client
        self.symbol = symbol
        self.filters = exchange_filters(client, symbol)

        self.level = last_price(client, symbol)  # L := senaste pris vid start
        self.position = None                     # None | "LONG" | "SHORT" (SHORT i spot = simulerad)
        self.entry_price = None
        self.entry_qty = Decimal("0")

        self.prev_state = None                   # "LW"/"LB"/"SW"/"SB"
        self.counts = load_markov_counts()

        print(f"🔧 Startnivå L={self.level} för {symbol}")

    def _legal_qty(self, wanted_qty: Decimal, ref_price: Decimal) -> Decimal:
        q = dquant(wanted_qty, self.filters["step_size"])
        min_not = self.filters["min_notional"]
        if q * ref_price < min_not:
            q_needed = (min_not * Decimal("1.02")) / ref_price
            q = dquant(q_needed, self.filters["step_size"])
        return q

    def _free_quote(self, asset="USDT") -> Decimal:
        acct = self.client.get_account()
        for b in acct["balances"]:
            if b["asset"] == asset:
                return Decimal(b["free"])
        return Decimal("0")

    def enter_long(self, px: Decimal):
        q = self._legal_qty(ORDER_QTY, px)
        need = q * px
        if self._free_quote() < need:
            print(f"⛔ Otillräckligt USDT ({need:.2f} krävs). Skip LONG.")
            return False

        resp = self.client.order_market_buy(symbol=self.symbol, quantity=float(q))
        avg_px = avg_fill_price(resp) or px
        self.position = "LONG"
        self.entry_price = avg_px
        self.entry_qty = Decimal(str(resp.get("executedQty", q)))
        self.level = avg_px
        log_order([datetime.now(timezone.utc).isoformat(timespec="seconds")+"Z", self.symbol, "BUY",
                   f"{self.entry_qty:.8f}", f"{avg_px:.8f}", f"{(self.entry_qty*avg_px):.8f}", resp["orderId"], "ENTER_LONG"])
        print(f"✅ ENTER LONG @ {avg_px} qty={self.entry_qty}")
        return True

    def enter_short(self, px: Decimal):
        # Spot kan inte gå "äkta" kort. Försöker sälja om bas-saldo finns (simulerad short).
        acct = self.client.get_account()
        base_asset = self.symbol.replace("USDT", "")
        base_free = Decimal(next((b["free"] for b in acct["balances"] if b["asset"] == base_asset), "0"))
        if base_free <= Decimal("0"):
            print("ℹ️ Inget bas-saldo – hoppar över SHORT i spot. (Futures rekommenderas för short.)")
            return False

        q = self._legal_qty(min(base_free, ORDER_QTY), px)
        resp = self.client.order_market_sell(symbol=self.symbol, quantity=float(q))
        avg_px = avg_fill_price(resp) or px
        self.position = "SHORT"
        self.entry_price = avg_px
        self.entry_qty = Decimal(str(resp.get("executedQty", q)))
        self.level = avg_px
        log_order([datetime.now(timezone.utc).isoformat(timespec="seconds")+"Z", self.symbol, "SELL",
                   f"{self.entry_qty:.8f}", f"{avg_px:.8f}", f"{(self.entry_qty*avg_px):.8f}", resp["orderId"], "ENTER_SHORT"])
        print(f"✅ ENTER SHORT @ {avg_px} qty={self.entry_qty}")
        return True

    def exit_position(self, px: Decimal, reason: str):
        if not self.position:
            return

        if self.position == "LONG":
            resp = self.client.order_market_sell(symbol=self.symbol, quantity=float(self.entry_qty))
            avg_px = avg_fill_price(resp) or px
            pnl_pct = (avg_px / self.entry_price - 1) - (2 * TAKER_FEE_PCT)
            state = "LW" if pnl_pct > 0 else "LB"
            side = "SELL"
        else:
            resp = self.client.order_market_buy(symbol=self.symbol, quantity=float(self.entry_qty))
            avg_px = avg_fill_price(resp) or px
            pnl_pct = (1 - (avg_px / self.entry_price)) - (2 * TAKER_FEE_PCT)
            state = "SW" if pnl_pct > 0 else "SB"
            side = "BUY"

        log_order([datetime.now(timezone.utc).isoformat(timespec="seconds")+"Z", self.symbol, side,
                   f"{self.entry_qty:.8f}", f"{avg_px:.8f}", f"{(self.entry_qty*avg_px):.8f}", resp["orderId"], f"EXIT_{reason}"])

        print(f"🔚 EXIT {self.position} @ {avg_px} (entry {self.entry_price})  ≈ PnL {pnl_pct*100:.3f}%  [{reason}]")

        if self.prev_state:
            self.counts[(self.prev_state, state)] += 1
        self.prev_state = state
        save_markov_counts(self.counts)
        pi = stationary_distribution(self.counts)
        print(f"🧮 Stationär ~ {{ {', '.join([f'{k}:{round(v,3)}' for k,v in pi.items()])} }}")

        self.level = avg_px  # ny nivå = utgångspris
        self.position = None
        self.entry_price = None
        self.entry_qty = Decimal("0")

    def on_tick(self, best_bid: Decimal, best_ask: Decimal):
        mid = (best_bid + best_ask) / 2

        if not self.position:
            if mid > self.level:
                self.enter_long(mid)
            elif mid < self.level:
                self.enter_short(mid)
        else:
            if self.position == "LONG":
                tp = self.entry_price * (1 + TP_PCT)
                be = self.entry_price
                if mid >= tp:
                    self.exit_position(mid, "TP")
                elif mid <= be:
                    self.exit_position(mid, "BE")
            elif self.position == "SHORT":
                tp = self.entry_price * (1 - TP_PCT)
                be = self.entry_price
                if mid <= tp:
                    self.exit_position(mid, "TP")
                elif mid >= be:
                    self.exit_position(mid, "BE")


# === REST API polling loop (mer tillförlitlig för testnet) ===
def start_polling_loop(strat: Strategy, symbol: str, interval: float = 0.5):
    """
    Pollar bokdjup via REST API istället för WebSocket.
    Mer tillförlitligt för testnet där WebSocket inte alltid fungerar.
    """
    print(f"📡 Startar polling för {symbol} (interval: {interval}s)")
    
    while True:
        try:
            # Hämta order book
            depth = strat.client.get_order_book(symbol=symbol, limit=5)
            
            if depth.get("bids") and depth.get("asks"):
                best_bid = Decimal(depth["bids"][0][0])
                best_ask = Decimal(depth["asks"][0][0])
                strat.on_tick(best_bid, best_ask)
            
            time.sleep(interval)
            
        except BinanceAPIException as e:
            print(f"⚠️ API-fel: {e}")
            time.sleep(3)
        except BinanceRequestException as e:
            print(f"⚠️ Nätverksfel: {e}")
            time.sleep(3)
        except Exception as err:
            print(f"⚠️ Polling-fel: {err}")
            time.sleep(3)


# === Körning ===
def main():
    print("🚀 Startar Binance Testnet live-strategi (REST API polling)...")
    client = Client(API_KEY, API_SECRET, testnet=TESTNET)
    strat = Strategy(client, SYMBOL)

    t = threading.Thread(target=start_polling_loop, args=(strat, SYMBOL, 0.5), daemon=True)
    t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Avslutar…")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("❌ Fel i huvudloopen:", e)