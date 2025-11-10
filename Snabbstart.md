# Snabbstart: Paper Trading med Riktiga Priser 🚀

## TL;DR - Svaret på din fråga

**"Kan koden fungera för att testa med riktiga priser?"**

✅ **JA! Koden använder REDAN riktiga marknadspriser från Binance!**

Det enda som är simulerat är trade-utförandet (paper trading = inga riktiga pengar används).

---

## Snabbstart (3 steg)

### 1. Installera requirements
```bash
pip install requests
```

### 2. Kör skriptet
```bash
python markov_breakout_live_paper.py
```

### 3. Se resultaten
```
🚀 Startar Binance LIVE-priser (paper mode=ON)
🔧 Startnivå L=103645.23 för BTCUSDT         ← RIKTIGT pris!
📡 Polling-intervall: 0.5s
💰 Startbalans: {'USDT': '10000', 'BTC': '0'}

ℹ️  Pris: 103749.12 | L: 103645.23 | Pos: FLAT | ...
📈 ENTER LONG @ 103749.12 qty=0.00100000
✅ [PAPER BUY] 0.001 BTCUSDT @ 103749.12 (fee 0.0415 USDT)

🔚 EXIT LONG @ 103853.25  PnL: 0.100% ($0.10)  [TP]
✅ [PAPER SELL] 0.001 BTCUSDT @ 103853.25
```

---

## Vad Koden Gör

| Komponent | Status | Beskrivning |
|-----------|--------|-------------|
| **Priser** | ✅ **RIKTIGA** | Hämtas från `api.binance.com` var 0.5s |
| **Trades** | 📝 Simulerade | Paper trading - inga riktiga pengar |
| **Avgifter** | 📊 Simulerade | 0.04% taker fee subtraheras |
| **Balans** | 🎮 Virtuell | Startar med $10,000 USDT |
| **Risk** | 🔒 Ingen | Noll ekonomisk risk |

---

## Parametrar (config.json)

```json
{
    "base_symbol": "BTCUSDT",    // Vilket par att tradea
    "order_test": true,          // true = paper mode, false = riktiga trades
    "order_qty": 0.001,          // Kvantitet per trade (0.001 BTC)
    "tp_pct": 0.001,             // 0.10% take profit
    "taker_fee_pct": 0.0004,     // 0.04% avgift
    "poll_sec": 0.5,             // Hämta pris var 0.5 sekund
    "paper_usdt": 10000          // Startkapital i paper mode
}
```

---

## Loggning

### Trades sparas i CSV
```
logs/orders_paper.csv
```

**Innehåll:**
```csv
ts,side,symbol,qty,price,usdt_delta,btc_delta,note
2025-11-05T21:30:00Z,BUY,BTCUSDT,0.001,103645.23,-103.69,0.001,paper
2025-11-05T21:30:15Z,SELL,BTCUSDT,0.001,103749.12,103.65,-0.001,paper
```

---

## Förstå Output

### När en trade händer:
```
📈 ENTER LONG @ 103645.23 qty=0.00100000
```
- Koden köper (simulerat) 0.001 BTC
- Vid RIKTIGT pris 103645.23 USDT
- Använder virtuella USDT från paper balance

```
✅ [PAPER BUY] 0.001 BTCUSDT @ 103645.23 (fee 0.04145809 USDT)
```
- Order "utförd" (lokalt)
- Avgift subtraherad från balans
- Ingen riktig order skickad till Binance

```
🔚 EXIT LONG @ 103749.12  PnL: 0.100% ($0.10)  [TP]
```
- Position stängd vid take profit
- PnL: 0.10% = $0.10 vinst
- Ny L-nivå satt till 103749.12

---

## Statusmeddelanden

### Var 10:e sekund (20 ticks):
```
ℹ️  Pris: 103645.23 | L: 103619.96 | Pos: LONG | Balans: USDT=9896.31 BTC=0.00100000
```

- **Pris**: Nuvarande marknadspris (RIKTIGT)
- **L**: Breakout-nivå (entry/exit-nivå)
- **Pos**: FLAT, LONG eller SHORT
- **Balans**: Virtuella saldon

---

## När Byta Till Riktiga Trades?

### ⚠️ Checklista INNAN du går live:

- [ ] Kört paper trading i minst 1 vecka
- [ ] Analyserat minst 100 trades
- [ ] Strategin är lönsam (positiv total PnL)
- [ ] Du förstår alla exit-villkor (TP/BE)
- [ ] Testat på Binance Testnet
- [ ] Bekväm med risken
- [ ] Startar med LITET kapital

### Steg för att gå live:

1. **Testnet först** (simulerade pengar, riktiga orders)
   ```json
   {
       "order_test": false,
       "testnet": true
   }
   ```

2. **Production senare** (riktiga pengar, riktiga orders)
   ```json
   {
       "order_test": false,
       "testnet": false
   }
   ```

---

## Vanliga Frågor

### F: Är priserna verkligen riktiga?
**S:** JA! Priserna hämtas från `https://api.binance.com/api/v3/ticker/price` - samma API som Binance.com använder.

### F: Behöver jag API-nycklar?
**S:** NEJ för paper trading! API-nycklar behövs bara för riktiga trades.

### F: Hur realistiskt är paper trading?
**S:** Mycket realistiskt för strategi-testning! Men det missar:
- Slippage (prisförändring under order-execution)
- Partial fills (bara en del fylls)
- Order rejection (insufficient funds, etc.)

### F: Kan jag förlora pengar i paper mode?
**S:** NEJ! Allt är virtuellt. Noll ekonomisk risk.

### F: Hur ändrar jag startkapital?
**S:** Ändra `"paper_usdt": 10000` i config.json.

### F: Kan jag testa på andra par?
**S:** JA! Ändra `"base_symbol": "ETHUSDT"` (eller vilket par som helst på Binance).

---

## Filer Du Behöver

1. **markov_breakout_live_paper.py** - Huvudskript
2. **config.json** - Inställningar
3. **logs/** - Skapas automatiskt för loggar

---

## Exempel: Full Session

```bash
$ python markov_breakout_live_paper.py

🔄 Hämtar startpris från Binance...
🚀 Startar Binance LIVE-priser (paper mode=ON)
🔧 Startnivå L=103619.96 för BTCUSDT
📡 Polling-intervall: 0.5s  TP=0.100%  Fee≈0.040%
💰 Startbalans: {'USDT': '10000', 'BTC': '0'}

▶️  Startar trading loop... (Ctrl+C för att avsluta)

ℹ️  Pris: 103645.23 | L: 103619.96 | Pos: FLAT | Balans: USDT=10000.00 BTC=0.00000000
📈 ENTER LONG @ 103645.23 qty=0.00100000
✅ [PAPER BUY] 0.001 BTCUSDT @ 103645.23 (fee 0.04145809 USDT)

ℹ️  Pris: 103749.12 | L: 103619.96 | Pos: LONG | Balans: USDT=9896.31 BTC=0.00100000
🔚 EXIT LONG @ 103749.12 (entry 103645.23)  PnL: 0.100% ($0.10)  [TP]
✅ [PAPER SELL] 0.001 BTCUSDT @ 103749.12 (fee 0.04149965 USDT)

ℹ️  Pris: 103620.50 | L: 103749.12 | Pos: FLAT | Balans: USDT=9999.93 BTC=0.00000000
📉 ENTER SHORT @ 103620.50 qty=0.00100000
✅ [PAPER SELL] 0.001 BTCUSDT @ 103620.50 (fee 0.04144820 USDT)

^C
🛑 Avslutar...
📊 Slutliga saldon: {'USDT': '9999.93', 'BTC': '0.00100000'}
📁 Loggar sparade i: logs/orders_paper.csv
```

---

## Nästa Steg

1. ✅ **Kör paper trading** - Testa strategin risk-fritt
2. 📊 **Analysera resultat** - Studera `logs/orders_paper.csv`
3. ⚙️ **Optimera parametrar** - Justera TP_PCT, ORDER_QTY, etc.
4. 🧪 **Testnet** - Prova riktiga orders med testnet-pengar
5. 🚀 **Live (försiktigt!)** - Börja med LITET kapital

---

## Sammanfattning

✅ **Riktiga priser**: api.binance.com (production)  
📝 **Simulerade trades**: Paper trading (noll risk)  
🎮 **Virtuellt kapital**: $10,000 USDT  
📊 **Riktiga avgifter**: 0.04% simulerade  
🔒 **Noll risk**: Inga riktiga pengar  

**Kör nu:**
```bash
python markov_breakout_live_paper.py
```

Lycka till! 🚀📈