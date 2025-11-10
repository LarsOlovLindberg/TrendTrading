# Balanserad Start: USDT + BTC 💰🪙

## Din Konfiguration

Nu startar programmet med **BÅDE USDT OCH BTC** så att du kan använda både LONG och SHORT från början!

### Uppdaterad config.json

```json
{
    "base_symbol": "BTCUSDT",
    "order_test": true,
    "order_qty": 0.001,
    "tp_pct": 0.001,
    "taker_fee_pct": 0.0004,
    "poll_sec": 0.5,
    "paper_usdt": 5000,      // ← 5000 USDT för LONG trades
    "paper_btc": 0.05         // ← 0.05 BTC för SHORT trades
}
```

---

## Vad Detta Ger Dig

### 💰 Startbalans

**USDT: $5,000**
- Används för LONG trades (köpa BTC)
- Räcker för ~48 LONG trades (0.001 BTC/trade @ ~$103k)

**BTC: 0.05 BTC** 
- Används för SHORT trades (sälja BTC)
- Räcker för 50 SHORT trades (0.001 BTC/trade)
- Värde: ~$5,150 @ $103k/BTC

**Total Start Värde: ~$10,150**

---

## Hur Trades Fungerar Nu

### Scenario 1: Pris Bryter UPP (LONG)

```
Start: USDT=5000, BTC=0.05

Pris → 103500 (bryter upp genom L)
✅ Har USDT? JA (5000 USDT)
📈 ENTER LONG @ 103500
💰 Efter: USDT=4896, BTC=0.051

Pris → 103603.50 (TP)
🔚 EXIT LONG @ 103603.50
💰 Efter: USDT=4999.92, BTC=0.05
```

### Scenario 2: Pris Bryter NED (SHORT)

```
Start: USDT=5000, BTC=0.05

Pris → 103300 (bryter ned genom L)
✅ Har BTC? JA (0.05 BTC)
📉 ENTER SHORT @ 103300
💰 Efter: USDT=5103.26, BTC=0.049

Pris → 103196.70 (TP)
🔚 EXIT SHORT @ 103196.70
💰 Efter: USDT=4999.98, BTC=0.05
```

### Scenario 3: Båda Riktningar

```
Start: USDT=5000, BTC=0.05

1. LONG @ 103500 → Exit @ 103603.50 [TP]
   💰 USDT=4999.92, BTC=0.05

2. SHORT @ 103550 → Exit @ 103446.50 [TP]
   💰 USDT=5103.18, BTC=0.05

3. LONG @ 103600 → Exit @ 103703.60 [TP]
   💰 USDT=5103.10, BTC=0.05

4. SHORT @ 103650 → Exit @ 103546.35 [TP]
   💰 USDT=5206.26, BTC=0.05
```

**Efter 4 trades: +$106.26 vinst! (båda riktningar fungerar)**

---

## Fördelar med Balanserad Start

### ✅ Båda Riktningar Aktiva
- LONG fungerar direkt (har USDT)
- SHORT fungerar direkt (har BTC)
- Utnyttjar alla trading-möjligheter

### ✅ Mer Realistiskt
- Liknar verklig futures trading
- Både bull och bear markets
- Mer komplett test av strategin

### ✅ Mer Trades = Bättre Data
- Dubbelt så många trading-möjligheter
- Snabbare att samla statistik
- Bättre förståelse för strategin

### ✅ Jämnare Balans
- Håller alltid lite av båda
- Mindre risk att "fastna" i en riktning
- Mer flexibel

---

## Nackdelar (Att Vara Medveten Om)

### ⚠️ Mer Komplex
- Måste följa både USDT och BTC
- Två valutor att hantera
- Lite svårare att förstå PnL

### ⚠️ Exponering Mot BTC-Pris
- Om BTC-priset sjunker, förlorar du på BTC-innehav
- Om BTC-priset stiger, vinner du på BTC-innehav
- Men detta påverkar inte trading-resultatet

### ⚠️ Inte Exakt Som Spot Trading
- I riktig spot kan du inte ha permanent BTC-innehav för SHORT
- Detta liknar mer futures/margin
- Men perfekt för att testa strategin!

---

## Justera Balansen

Du kan ändra balansen i config.json efter dina preferenser:

### Mer LONG-Fokuserad
```json
{
    "paper_usdt": 7500,
    "paper_btc": 0.025
}
```
→ 75% för LONG, 25% för SHORT

### Mer SHORT-Fokuserad
```json
{
    "paper_usdt": 2500,
    "paper_btc": 0.075
}
```
→ 25% för LONG, 75% för SHORT

### Balanserad (Rekommenderad)
```json
{
    "paper_usdt": 5000,
    "paper_btc": 0.05
}
```
→ 50/50 split (~$5k vardera)

### Större Kapital
```json
{
    "paper_usdt": 10000,
    "paper_btc": 0.1
}
```
→ ~$20k total, mer trades möjliga

---

## Förväntat Output

När du kör programmet:

```
🔄 Hämtar startpris från Binance...
🚀 Startar Binance LIVE-priser (SMART LONG+SHORT mode)
🔧 Startnivå L=103445.94 för BTCUSDT
📡 Polling-intervall: 0.5s  TP=0.100%  Fee≈0.040%
💰 Startbalans: USDT=5000.00 BTC=0.05000000
💵 Total värde: $10172.30 ($5000.00 USDT + $5172.30 BTC)
📊 Strategin kollar automatiskt medel för både LONG och SHORT

▶️  Startar trading loop... (Ctrl+C för att avsluta)

ℹ️  Pris: 103500.00 | L: 103445.94 | Pos: FLAT | USDT=5000.00 BTC=0.05000000
📈 ENTER LONG @ 103500.00 qty=0.00100000
✅ [PAPER BUY] 0.00100000 BTCUSDT @ 103500.00 (fee 0.0414 USDT)

ℹ️  Pris: 103603.50 | L: 103445.94 | Pos: LONG | USDT=4896.46 BTC=0.05100000
🔚 EXIT LONG @ 103603.50 (entry 103500.00)  PnL: 0.100% ($0.10)  [TP]
✅ [PAPER SELL] 0.00100000 BTCUSDT @ 103603.50

ℹ️  Pris: 103550.00 | L: 103603.50 | Pos: FLAT | USDT=4999.92 BTC=0.05000000
📉 ENTER SHORT @ 103550.00 qty=0.00100000       ← FUNGERAR NU!
✅ [PAPER SELL] 0.00100000 BTCUSDT @ 103550.00

ℹ️  Pris: 103446.50 | L: 103603.50 | Pos: SHORT | USDT=5103.18 BTC=0.04900000
🔚 EXIT SHORT @ 103446.50 (entry 103550.00)  PnL: 0.100% ($0.10)  [TP]
✅ [PAPER BUY] 0.00100000 BTCUSDT @ 103446.50
```

**Ser du skillnaden? Både LONG och SHORT fungerar! 🎉**

---

## Kör Programmet

```powershell
python "markov breakout live paper SMART.py"
```

Med de uppdaterade filerna:
- [x] config.json (med paper_btc)
- [x] markov breakout live paper SMART.py (läser båda balanserna)

---

## Övervaka Resultaten

### Efter 1 Timme
```
📊 Resultat efter 1h:
- LONG trades: 5
- SHORT trades: 4
- Total PnL: +$0.45
- Balans: USDT=5045.23 BTC=0.05
```

### Efter 24 Timmar
```
📊 Resultat efter 24h:
- LONG trades: 48
- SHORT trades: 42
- Total PnL: +$4.52
- Balans: USDT=5226.78 BTC=0.05
```

### Analysera logs/orders_paper.csv
```csv
ts,side,symbol,qty,price,usdt_delta,btc_delta,note
2025-11-05T22:00:00Z,BUY,BTCUSDT,0.001,103500,-103.54,0.001,paper
2025-11-05T22:00:15Z,SELL,BTCUSDT,0.001,103603.50,103.50,-0.001,paper
2025-11-05T22:00:30Z,SELL,BTCUSDT,0.001,103550,103.46,-0.001,paper
2025-11-05T22:00:45Z,BUY,BTCUSDT,0.001,103446.50,-103.49,0.001,paper
...
```

---

## Sammanfattning

### Vad Du Får Nu:

✅ **Startbalans:**
- $5,000 USDT
- 0.05 BTC (~$5,150)
- Total: ~$10,150

✅ **Båda Riktningar:**
- LONG fungerar (har USDT)
- SHORT fungerar (har BTC)
- Inga skippade trades pga brist på medel

✅ **Realistiskt:**
- Testar strategin i båda riktningar
- Mer komplett data
- Bättre förberedelse för live trading

✅ **Enkelt att Konfigurera:**
- Justera i config.json
- paper_usdt och paper_btc
- Kör och testa!

### Nästa Steg:

1. ✅ Uppdatera config.json (redan gjort)
2. ✅ Kör SMART-versionen
3. 📊 Övervaka i 24-48 timmar
4. 📁 Analysera orders_paper.csv
5. ⚙️ Optimera parametrar om nödvändigt

**Nu har du perfekt balans för att testa både LONG och SHORT! 🚀📈📉**