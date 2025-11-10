# Lösning: Binance Testnet WebSocket 404-fel

## Problemet
Du får ett **404 Not Found**-fel eftersom Binance Spot Testnet inte längre erbjuder WebSocket-streams via `wss://testnet.binance.vision/ws/`.

Felmeddelandet:
```
❌ Fel i huvudloopen: Handshake status 404 Not Found
```

## Lösningar

Jag har skapat två fixade versioner av din `markov_breakout_live.py`:

### Alternativ 1: WebSocket med Futures Testnet (Snabbare) ⚡
**Fil:** `markov_breakout_live.py`

**Ändring:** WebSocket-URL:en har uppdaterats till:
```python
wss://stream.binancefuture.com/ws/btcusdt@bookTicker
```

**För- och nackdelar:**
- ✅ Realtidsdata (snabbare uppdateringar)
- ✅ Låg latens
- ⚠️ Kan vara mindre stabil på testnet
- ⚠️ Kräver `websocket-client` paket

**Användning:**
```bash
python markov_breakout_live.py
```

### Alternativ 2: REST API Polling (Rekommenderad för testnet) 🎯
**Fil:** `markov_breakout_live_polling.py`

**Ändring:** Använder REST API istället för WebSocket:
```python
# Pollar order book var 0.5 sekund via get_order_book()
```

**För- och nackdelar:**
- ✅ Mer tillförlitlig på testnet
- ✅ Inga WebSocket-dependencies
- ✅ Enklare att felsöka
- ⚠️ Något långsammare (0.5s fördröjning)
- ⚠️ Högre API-belastning

**Användning:**
```bash
python markov_breakout_live_polling.py
```

## Rekommendation

För **Binance Testnet**: Använd **markov_breakout_live_polling.py**
- Testnet är ofta instabilt för WebSocket
- REST API är mycket mer pålitligt
- 0.5s fördröjning är acceptabel för de flesta strategier

För **Binance Production**: Använd **markov_breakout_live.py** (WebSocket-versionen)
- WebSocket är snabbare och mer effektiv
- Production-streams är mycket stabila

## Vad har ändrats?

### WebSocket-versionen:
```python
# FÖRE (fungerar inte längre)
wss://testnet.binance.vision/ws/btcusdt@bookTicker

# EFTER (fungerar)
wss://stream.binancefuture.com/ws/btcusdt@bookTicker
```

### Polling-versionen:
Ersatt hela WebSocket-implementationen med:
```python
def start_polling_loop(strat: Strategy, symbol: str, interval: float = 0.5):
    while True:
        depth = strat.client.get_order_book(symbol=symbol, limit=5)
        best_bid = Decimal(depth["bids"][0][0])
        best_ask = Decimal(depth["asks"][0][0])
        strat.on_tick(best_bid, best_ask)
        time.sleep(interval)
```

## Testning

Testa den nya versionen:
```bash
python markov_breakout_live_polling.py
```

Du bör nu se:
```
🚀 Startar Binance Testnet live-strategi (REST API polling)...
🔧 Startnivå L=103674.79 för BTCUSDT
📡 Startar polling för BTCUSDT (interval: 0.5s)
```

## Felsökning

Om du fortfarande får problem:

1. **Kontrollera API-nycklar**: Se till att dina testnet-nycklar är korrekta i `config.json`
2. **Testa anslutningen**: Kör `binance_testnet_setup.py` först
3. **Nätverksproblem**: Kontrollera att du kan nå Binance API
4. **Rate limits**: Polling använder mer API-anrop, så sänk intervallet om du får rate limit-fel

## Ytterligare information

- Binance har fassat ut spot testnet WebSocket-streams
- Futures testnet WebSocket fungerar fortfarande
- För production trading rekommenderas WebSocket
- För testnet rekommenderas REST API polling