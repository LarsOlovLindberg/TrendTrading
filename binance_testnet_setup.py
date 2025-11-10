import json
import os
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone
import csv

from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException


# === Ladda konfiguration (tål både UTF-8 och UTF-8 BOM) ===
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
    config = json.load(f)

API_KEY = config["api_key"]
API_SECRET = config["api_secret"]
TESTNET = config.get("testnet", True)
BASE_SYMBOL = config.get("base_symbol", "BTCUSDT")
ORDER_TEST = config.get("order_test", False)
ORDER_QTY = Decimal(str(config.get("order_qty", 0.001)))

# Loggfil
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_CSV = os.path.join(LOG_DIR, "orders.csv")
os.makedirs(LOG_DIR, exist_ok=True)


def dquant(x: Decimal, step: Decimal) -> Decimal:
    if step == 0:
        return x
    # antal decimaler i step
    decimals = abs(Decimal(str(step)).as_tuple().exponent)
    n = (x / step).to_integral_value(rounding=ROUND_DOWN)
    return (n * step).quantize(Decimal(10) ** -decimals, rounding=ROUND_DOWN)


def get_symbol_filters(client: Client, symbol: str):
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
    raise ValueError(f"Hittar inte symbolen {symbol}.")


def get_last_price(client: Client, symbol: str) -> Decimal:
    t = client.get_symbol_ticker(symbol=symbol)
    return Decimal(t["price"])


def print_balances(client: Client):
    account = client.get_account()
    balances = {b["asset"]: b["free"] for b in account["balances"] if float(b["free"]) > 0}
    print(f"Kontosaldo (ej noll): {balances}\n")


def avg_fill_price(order_resp: dict) -> Decimal:
    """
    Vägt snittpris från fills-listan (marketorder).
    """
    fills = order_resp.get("fills") or []
    if not fills:
        # fallback (kan ske på vissa testnet-svar)
        return Decimal(str(order_resp.get("price", "0") or "0"))
    notional = Decimal("0")
    qty = Decimal("0")
    for f in fills:
        p = Decimal(str(f["price"]))
        q = Decimal(str(f["qty"]))
        notional += p * q
        qty += q
    return (notional / qty) if qty > 0 else Decimal("0")


def log_order(side: str, symbol: str, qty: Decimal, avg_price: Decimal, notional: Decimal, order_id: int):
    """Loggar en order till CSV. Försöker igen om filen är låst (t.ex. öppen i Excel)."""
    import time
    max_retries = 5
    retry_delay = 0.2
    
    for attempt in range(max_retries):
        try:
            file_exists = os.path.isfile(LOG_CSV)
            with open(LOG_CSV, "a", newline="", encoding="utf-8") as fp:
                writer = csv.writer(fp)
                if not file_exists:
                    writer.writerow(["timestamp", "symbol", "side", "qty", "avg_price", "notional", "order_id"])
                writer.writerow([
                    datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
                    symbol,
                    side,
                    f"{qty:.8f}",
                    f"{avg_price:.8f}",
                    f"{notional:.8f}",
                    order_id,
                ])
            return  # Lyckades
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                print(f"⚠️ Kan inte skriva till {LOG_CSV} - filen är låst (stäng Excel)")
        except Exception as e:
            print(f"⚠️ Loggningsfel: {e}")
            return


def place_market_roundtrip(client: Client, symbol: str, wanted_qty: Decimal):
    filters = get_symbol_filters(client, symbol)
    price = get_last_price(client, symbol)

    adj_qty = dquant(wanted_qty, filters["step_size"])
    if adj_qty <= Decimal("0"):
        raise ValueError("Orderkvantiteten blev 0 efter LOT_SIZE. Höj 'order_qty' i config.json.")

    notional = adj_qty * price
    if notional < filters["min_notional"]:
        needed_qty = (filters["min_notional"] * Decimal("1.02")) / price
        adj_qty = dquant(needed_qty, filters["step_size"])
        notional = adj_qty * price

    # kolla USDT-saldo
    acct = client.get_account()
    usdt_free = Decimal(next((b["free"] for b in acct["balances"] if b["asset"] == "USDT"), "0"))
    if usdt_free < notional:
        raise ValueError(f"Otillräckligt USDT: behöver ~{notional:.2f}, har {usdt_free:.2f}.")

    print(f"➡️ MARKET BUY {symbol}: qty={adj_qty} (≈ {notional:.2f} USDT @ ~{price})")
    buy = client.order_market_buy(symbol=symbol, quantity=float(adj_qty))
    buy_qty = Decimal(str(buy.get("executedQty", adj_qty)))
    buy_px = avg_fill_price(buy)
    buy_notional = buy_qty * buy_px if buy_px > 0 else notional
    print(f"✅ BUY klar. orderId={buy['orderId']}, filledQty={buy_qty}, avg={buy_px}")

    log_order("BUY", symbol, buy_qty, buy_px, buy_notional, buy["orderId"])

    # Sälj tillbaka
    sell_qty = dquant(buy_qty, filters["step_size"])
    if sell_qty > Decimal("0"):
        print(f"⬅️ MARKET SELL {symbol}: qty={sell_qty}")
        sell = client.order_market_sell(symbol=symbol, quantity=float(sell_qty))
        sell_px = avg_fill_price(sell)
        sell_notional = sell_qty * sell_px if sell_px > 0 else sell_qty * get_last_price(client, symbol)
        print(f"✅ SELL klar. orderId={sell['orderId']}, filledQty={sell_qty}, avg={sell_px}")
        log_order("SELL", symbol, sell_qty, sell_px, sell_notional, sell["orderId"])
    else:
        print("⚠️ Hoppar över SELL: 0 efter avrundning.")


def main():
    print("🔄 Ansluter till Binance Testnet...")
    try:
        client = Client(API_KEY, API_SECRET, testnet=TESTNET)

        print("\n✅ Anslutning lyckades!")
        print_balances(client)

        price = get_last_price(client, BASE_SYMBOL)
        print(f"📈 Senaste pris för {BASE_SYMBOL}: {price} USDT\n")

        server_time = client.get_server_time()
        print(f"🕒 Serverns tid: {server_time['serverTime']}\n")

        if ORDER_TEST:
            print("🧪 Order-test är AKTIVERAT i config.json (order_test=true).")
            place_market_roundtrip(client, BASE_SYMBOL, ORDER_QTY)
            print("\n🔁 Saldon efter roundtrip:")
            print_balances(client)
            print(f"📝 Logg sparad i: {LOG_CSV}")
        else:
            print("ℹ️ Order-test är AV. Sätt \"order_test\": true i config.json för att prova en liten köp/sälj.")

    except BinanceAPIException as e:
        print(f"❌ Binance API-fel: {e}")
    except BinanceRequestException as e:
        print(f"⚠️ Nätverksfel: {e}")
    except Exception as e:
        print(f"⚠️ Ovänat fel: {e}")

    print("Klar ✅")


if __name__ == "__main__":
    main()