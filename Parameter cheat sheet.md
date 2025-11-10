# Snabbreferens: Strategi-Parametrar 📋

## Parameter Cheat Sheet

| Parameter | Vad | Typiska Värden | Påverkar |
|-----------|-----|----------------|----------|
| **tp_pct** | Take profit % | 0.0005-0.005 | Vinst per trade |
| **sl_pct** | Stop loss % | null, 0.0005-0.003 | Max förlust |
| **be_offset_pct** | Breakeven trigger | 0.0002-0.001 | Riskskydd |
| **trailing_stop** | Följ trenden? | true/false | Max vinst |
| **trailing_offset_pct** | Trailing avstånd | 0.0003-0.001 | Trailing känsla |
| **min_movement_pct** | Min prisrörelse | 0-0.0003 | Signal filter |
| **order_qty** | Fix storlek | 0.0005-0.01 | Risk per trade |
| **position_size_pct** | % av kapital | null, 0.05-0.2 | Dynamisk risk |
| **volatility_filter** | Kräv volatilitet? | true/false | Antal trades |
| **min_volatility** | Min volatilitet | 0.0005-0.002 | Trade frekvens |
| **time_filter** | Trade vissa tider? | true/false | Trading hours |
| **trading_hours_utc** | Vilka timmar | [[8,22]], [[13,21]] | När trade |
| **l_update_strategy** | När uppdatera L? | on_exit/on_tp_only/periodic | Entry frekvens |

---

## Bitcoin @ $103,500: Dollarvärden

| tp_pct | $ per 0.001 BTC | tp_pct | $ per 0.001 BTC |
|--------|-----------------|--------|-----------------|
| 0.0003 | $31.05 | 0.002 | $207.00 |
| 0.0005 | $51.75 | 0.003 | $310.50 |
| 0.001 | $103.50 | 0.005 | $517.50 |
| 0.0015 | $155.25 | 0.01 | $1,035.00 |

---

## Risk/Reward Rekommendationer

### TP/SL Ratios

| Ratio | TP | SL | Win Rate Behövs | Kommentar |
|-------|----|----|-----------------|-----------|
| 1:1 | 0.001 | 0.001 | >50% | Breakeven vid 50% |
| 1.5:1 | 0.0015 | 0.001 | >40% | OK ratio |
| 2:1 | 0.002 | 0.001 | >33% | Bra ratio ⭐ |
| 3:1 | 0.003 | 0.001 | >25% | Utmärkt ratio ⭐⭐ |
| 1:2 | 0.001 | 0.002 | >67% | Dålig ratio ❌ |

**Tumregel:** TP bör vara MINST lika med SL, helst 2× eller mer

---

## Snabba Startkombinationer

### 🐢 Konservativ (Låg Risk)
```json
{
    "tp_pct": 0.001,
    "sl_pct": 0.0005,
    "be_offset_pct": 0.0004,
    "trailing_stop": false,
    "min_movement_pct": 0.0002,
    "position_size_pct": 0.05
}
```
**Förväntat:** Låg risk, 50-60% win rate, små vinster

---

### ⚖️ Balanserad (Måttlig Risk)
```json
{
    "tp_pct": 0.0015,
    "sl_pct": 0.001,
    "be_offset_pct": 0.0004,
    "trailing_stop": true,
    "trailing_offset_pct": 0.0005,
    "min_movement_pct": 0.0001,
    "position_size_pct": 0.1
}
```
**Förväntat:** Måttlig risk, 55-65% win rate, bra vinster ⭐

---

### 🚀 Aggressiv (Hög Risk)
```json
{
    "tp_pct": 0.003,
    "sl_pct": 0.0015,
    "be_offset_pct": 0.0006,
    "trailing_stop": true,
    "trailing_offset_pct": 0.001,
    "min_movement_pct": 0.00005,
    "position_size_pct": 0.15
}
```
**Förväntat:** Hög risk, 45-55% win rate, stora vinster/förluster

---

### 📈 Scalping (Många Små Trades)
```json
{
    "tp_pct": 0.0005,
    "sl_pct": 0.0003,
    "be_offset_pct": 0.0002,
    "trailing_stop": false,
    "min_movement_pct": 0.00005,
    "position_size_pct": 0.05
}
```
**Förväntat:** Många trades, 60-70% win rate, små vinster

---

### 📊 Swing (Färre Stora Trades)
```json
{
    "tp_pct": 0.005,
    "sl_pct": 0.002,
    "be_offset_pct": 0.0008,
    "trailing_stop": true,
    "trailing_offset_pct": 0.001,
    "min_movement_pct": 0.0003,
    "position_size_pct": 0.1
}
```
**Förväntat:** Få trades, 40-50% win rate, stora vinster

---

## Metrics Target Values

### Minimum för Live Trading ✅

| Metric | Minimum | Bra | Utmärkt |
|--------|---------|-----|---------|
| **Sharpe Ratio** | 1.0 | 2.0 | 3.0+ |
| **Win Rate** | 45% | 55% | 65%+ |
| **Profit Factor** | 1.3 | 1.8 | 2.5+ |
| **Max Drawdown** | <30% | <20% | <10% |
| **Total Trades** | 100+ | 500+ | 1000+ |
| **ROI/Month** | 5% | 15% | 30%+ |

**Om under minimum → Optimera mer eller ändra strategi!**

---

## Optimerings Quick Start ⚡

### 1. Första Testet (Basics)
```python
param_grid = {
    'tp_pct': [0.001, 0.0015, 0.002],
    'sl_pct': [None, 0.001, 0.0015]
}
```
**6 kombinationer** - Snabbt att köra

### 2. Andra Testet (Add Trailing)
```python
param_grid = {
    'tp_pct': [0.0015, 0.002, 0.0025],  # Justera baserat på Test 1
    'sl_pct': [0.001, 0.0015],           # Ta bort "None" om den var dålig
    'trailing_stop': [False, True],
    'trailing_offset_pct': [0.0005, 0.001]
}
```
**24 kombinationer** - Medelstort

### 3. Tredje Testet (Fine-tune)
```python
# Använd bästa värdena från Test 2, variera lite runt dem
param_grid = {
    'tp_pct': [0.0018, 0.002, 0.0022],        # Finjustera runt bästa
    'sl_pct': [0.0009, 0.001, 0.0011],
    'trailing_stop': [True],                   # Om True vann
    'trailing_offset_pct': [0.0008, 0.001, 0.0012],
    'min_movement_pct': [0.0001, 0.00015, 0.0002]
}
```
**27 kombinationer** - Detaljerad optimering

---

## Vanliga Problem & Lösningar

### Problem: Många Trades, Låg PnL
**Orsak:** TP för låg, avgifter äter vinster
**Lösning:** Öka tp_pct till minst 0.001

### Problem: Få Trades
**Orsak:** min_movement_pct för hög, eller TP/SL för tight
**Lösning:** Sänk min_movement_pct, eller öka TP

### Problem: Hög Win Rate Men Förlust
**Orsak:** Små vinster, stora förluster (dålig TP/SL ratio)
**Lösning:** Öka TP eller minska SL

### Problem: Låg Win Rate Men Vinst
**Orsak:** Stora vinster, små förluster (trailing stop fungerar)
**Resultat:** Detta är OK! Fortsätt

### Problem: Stora Drawdowns
**Orsak:** Ingen SL, eller för stor position size
**Lösning:** Lägg till SL, minska position_size_pct

---

## Test Checklist ☑️

Innan live trading:

- [ ] Testat minst 100 trades
- [ ] Sharpe Ratio > 1.5
- [ ] Profit Factor > 1.5
- [ ] Max Drawdown < 25%
- [ ] Validerat på out-of-sample data
- [ ] Paper traded i 1-2 veckor
- [ ] Förstår när strategi fungerar (bull/bear/range)
- [ ] Känslomässigt redo för drawdowns
- [ ] Har stop-loss plan (när avsluta strategin?)

---

## Nästa Steg

1. ✅ Läs OPTIMIZATION_GUIDE.md (fullständig guide)
2. ✅ Välj startkombination (Konservativ/Balanserad/Aggressiv)
3. ✅ Uppdatera config_advanced.json
4. ✅ Kör strategy_optimizer.py
5. ✅ Analysera resultat
6. ✅ Paper trade bästa config
7. ✅ Small live test

**Lycka till! 🚀📊**