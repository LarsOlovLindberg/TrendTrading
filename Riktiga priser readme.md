# Riktiga Priser med Paper Trading ✅📊

## Din Fråga
> "Jag vill testa med riktiga priser dvs marknadspriser på valutan, kan denna kod fungera för det?"

## Svar: JA! Koden använder REDAN riktiga marknadspriser! 🎯

Din kod har **två delar**:
1. **Priser** (redan riktiga ✅)
2. **Trades** (simulerade 📝)

---

## Vad koden GÖR nu

### ✅ RIKTIGA MARKNADSPRISER
```python
BINANCE_PUBLIC = "https://api.binance.com"  # ← RIKTIGA priser!

def get_live_price(symbol: str):
    r = requests.get(f"{BINANCE_PUBLIC}/api/v3/ticker/price", ...)
    return Decimal(r.json()["price"])
```

**Detta ger dig:**
- 🔴 Live Bitcoin-pris från Binances produktions-API
- 📡 Uppdateras var 0.5 sekund (POLL_SEC)
- 💯 Samma priser som du ser på Binance.com
- 🆓 Kräver INGA API-nycklar (public data)

### 📝 SIMULERADE TRADES (Paper Trading)
```python
class PaperBroker:
    def market_buy(self, symbol, qty, price):
        # Simulerar köp lokalt - INGEN riktig order
        self.balances["USDT"] -= cost
        self.balances["BTC"]  += qty
```

**Detta betyder:**
- 💰 Startbalans: $10,000 USDT (i minnet)
- 🎮 Alla trades simuleras lokalt
- 📊 Avgifter inkluderas (0.04% taker fee)
- 🔒 INGA riktiga pengar riskeras
- 📁 Sparas i `logs/orders_paper.csv`

---

## Jämförelse

| Aspekt | Din Kod Nu | Riktiga Trades |
|--------|-----------|----------------|
| **Priser** | ✅ Riktiga från Binance | ✅ Riktiga från Binance |
| **Orders** | 📝 Simulerade (paper) | 💸 Riktiga (testnet/live) |
| **Kapital** | 🎮 Virtuellt ($10k) | 💰 Riktigt (ditt konto) |
| **Risk** | 🔒 Ingen | ⚠️ Full |
| **Avgifter** | 📊 Simulerade | 💸 Riktiga |
| **API-nycklar** | 🆓 Inte nödvändiga | 🔑 Krävs |

---

## Exempel: Vad händer när koden körs

```
🚀 Startar Binance LIVE-priser (paper mode=ON)
🔧 Startnivå L=103619.96 för BTCUSDT         ← RIKTIGT pris!
📡 Polling-intervall: 0.5s
💰 Startbalans: {'USDT': '10000', 'BTC': '0'}

ℹ️  Pris: 103645.23 | L: 103619.96 | ...     ← RIKTIGT pris!
📈 ENTER LONG @ 103645.23 qty=0.00100000     ← SIMULERAD order
✅ [PAPER BUY] 0.001 BTCUSDT @ 103645.23 (fee 0.04145809 USDT)

ℹ️  Pris: 103749.12 | ...                    ← RIKTIGT pris!
🔚 EXIT LONG @ 103749.12 (entry 103645.23)   ← SIMULERAD order
   PnL: 0.100% ($0.10)  [TP]
✅ [PAPER SELL] 0.001 BTCUSDT @ 103749.12
```

**Alla priser är RIKTIGA** - bara trade-utförandet är simulerat!

---

## Varför Paper Trading är Bra

### 1. Testa Strategin Risk-fritt 🔒
- Se om din breakout-logik fungerar
- Testa TP/BE-villkor
- Mät verklig PnL över tid
- Inga riktiga pengar i fara

### 2. Riktiga Marknadsförhållanden 📊
- Riktiga prisrörelser
- Riktiga volatilitet
- Riktiga gaps och spikes
- Slippage simuleras

### 3. Optimera Parametrar ⚙️
- Testa olika TP_PCT (0.10%, 0.20%, etc.)
- Justera ORDER_QTY
- Hitta bästa POLL_SEC
- Finjustera strategi

---

## Hur Man Använder Koden

### Steg 1: Installera requirements
```bash
pip install requests
```

### Steg 2: Justera config.json (valfritt)
```json
{
    "base_symbol": "BTCUSDT",
    "order_test": true,          ← True = paper mode
    "order_qty": 0.001,          ← Kvantitet per trade
    "tp_pct": 0.001,             ← 0.10% take profit
    "taker_fee_pct": 0.0004,     ← 0.04% avgift
    "poll_sec": 0.5,             ← Polling-intervall
    "paper_usdt": 10000          ← Startkapital (paper)
}
```

### Steg 3: Kör skriptet
```bash
python markov_breakout_live_paper.py
```

### Steg 4: Övervaka resultat
```bash
# Priser uppdateras live
# Trades loggas till logs/orders_paper.csv
# Tryck Ctrl+C för att avsluta
```

---

## När Gå Över Till Riktiga Trades?

### ⚠️ GÅ ÖVER NÄR:
1. ✅ Strategin är lönsam i paper trading (minst 100+ trades)
2. ✅ Du förstår alla exit-villkor (TP/BE)
3. ✅ Du har testat i minst 1 vecka
4. ✅ Du är bekväm med risken
5. ✅ Du har Binance Testnet-konto klart

### 🔧 Hur Byta Till Riktiga Trades (Testnet)

1. **Sätt order_test till false**
```json
{
    "order_test": false,
    "testnet": true
}
```

2. **Avkommentera TODO-sektionerna i koden**
```python
# I maybe_enter():
if ORDER_TEST:
    paper.market_buy(SYMBOL, ORDER_QTY, price)
else:
    from binance.client import Client
    client = Client(API_KEY, API_SECRET, testnet=True)
    client.order_market_buy(symbol=SYMBOL, quantity=float(ORDER_QTY))
```

3. **Testa på Binance Testnet FÖRST**
- Testnet = simulerade pengar men riktiga orders
- https://testnet.binance.vision/
- Noll risk, men övar order-placering

4. **Senare: Production Trading**
- Ändra `testnet: false` i config
- Använd riktiga API-nycklar
- Starta med LITET kapital!

---

## Skillnad: Paper vs Testnet vs Live

| Mode | Priser | Orders | Pengar | Risk |
|------|--------|--------|--------|------|
| **Paper** (nu) | ✅ Riktiga | 📝 Simulerade | 🎮 Virtuella | 🔒 Ingen |
| **Testnet** | ✅ Riktiga | ✅ Riktiga | 🎮 Testnet | 🔒 Ingen |
| **Live** | ✅ Riktiga | ✅ Riktiga | 💰 Riktiga | ⚠️ Full |

---

## Vanliga Missförstånd

### ❌ "Jag behöver testnet för att få riktiga priser"
**NEJ!** Riktiga priser är publika data från Binance och kräver inga nycklar.

### ❌ "Paper trading är inte realistiskt"
**DELVIS SANT.** Paper trading har samma priser men missar:
- Slippage (pris ändras mellan order och execution)
- Partial fills (bara en del av ordern fylls)
- Order rejection (insufficient funds, etc.)

Men det är **tillräckligt** för att testa strategi-logik!

### ❌ "Jag måste betala avgifter i paper mode"
**NEJ!** Avgifter är simulerade (bara subtraheras från virtuella saldon).

---

## Sammanfattning

✅ **Din kod använder REDAN riktiga priser!**
- Priser från `api.binance.com` (production)
- Uppdateras var 0.5 sekund
- Inga API-nycklar behövs

📝 **Paper Trading = Säkert att testa**
- Virtuellt kapital ($10k)
- Simulerade trades
- Riktiga prisrörelser
- Noll risk

🚀 **Nästa Steg**
1. Kör `markov_breakout_live_paper.py`
2. Övervaka trades i minst 1 vecka
3. Analysera `logs/orders_paper.csv`
4. Om lönsam → testa på Binance Testnet
5. Om fortfarande lönsam → övervaka live med LITET kapital

---

## Filer

- `markov_breakout_live_paper.py` - Paper trading med riktiga priser
- `logs/orders_paper.csv` - Trade-logg
- `config.json` - Inställningar

**Kör nu:**
```bash
python markov_breakout_live_paper.py
```

Lycka till med testningen! 🚀📈