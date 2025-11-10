# Strategi-Optimering: Systematisk Guide 🎯📊

## Varför Optimera?

**Problem:** Gissa vilka parametrar som fungerar → Slumpmässiga resultat
**Lösning:** Systematisk testning → Data-driven beslut

---

## Viktiga Parametrar att Optimera

### 1. **Take Profit (tp_pct)** 🎯
**Vad:** Hur mycket vinst innan du säljer?

**Varför:** Mest kritisk parameter!
- För låg → Många små vinster, men missar stora rörelser
- För hög → Få stora vinster, men många BE/SL exits

**Testa:**
```json
"tp_pct": [0.0005, 0.001, 0.0015, 0.002, 0.0025, 0.003, 0.005]
```

**Exempel:**
- 0.0005 = 0.05% = $51.75 på 0.001 BTC @ $103,500
- 0.001 = 0.10% = $103.50
- 0.002 = 0.20% = $207.00
- 0.005 = 0.50% = $517.50

**Tumregel:** 
- Scalping: 0.0003-0.001
- Day trading: 0.001-0.003
- Swing: 0.003-0.01

---

### 2. **Stop Loss (sl_pct)** 🛑
**Vad:** Hur mycket förlust tolererar du?

**Varför:** Skyddar mot stora förluster
- null → Ingen SL, bara BE (nuvarande)
- För tight → Många SL-exits på naturlig volatilitet
- För wide → Stora förluster om fel

**Testa:**
```json
"sl_pct": [null, 0.0005, 0.001, 0.0015, 0.002, 0.003]
```

**Relation till TP:**
- TP/SL ratio = Risk/Reward
- TP=0.002, SL=0.001 → 2:1 ratio (bra!)
- TP=0.001, SL=0.002 → 1:2 ratio (dåligt!)

**Tumregel:** SL ska vara mindre eller lika med TP

---

### 3. **Breakeven Offset (be_offset_pct)** ⚖️
**Vad:** Hur snabbt flyttar du till breakeven?

**Varför:** Skyddar vinst utan att gå ur för tidigt
- För tight → Exit vid minsta retracement
- För wide → Riskerar att förlora vinst

**Testa:**
```json
"be_offset_pct": [0.0002, 0.0004, 0.0006, 0.0008, 0.001]
```

**Relation till avgifter:**
- Minimum: 2 × taker_fee (in + ut)
- Standard: taker_fee_pct (0.0004)
- Konservativ: 2 × taker_fee_pct (0.0008)

---

### 4. **Trailing Stop** 📈
**Vad:** Följer priset uppåt/neråt för att maximera vinst

**Varför:** Fångar stora moves
- false → Exit vid TP
- true → Fortsätter följa trenden

**Testa:**
```json
"trailing_stop": [false, true]
"trailing_offset_pct": [0.0003, 0.0005, 0.0008, 0.001]
```

**När använda:**
- Trending markets → true
- Range markets → false

---

### 5. **Min Movement (min_movement_pct)** 🔍
**Vad:** Minsta prisrörelse för att trigga entry

**Varför:** Filtrerar bort fladder
- För låg → Många false signals
- För hög → Missar entries

**Testa:**
```json
"min_movement_pct": [0, 0.00005, 0.0001, 0.0002, 0.0003]
```

**Bitcoin exempel @ $103,500:**
- 0.0001 = $10.35 rörelse krävs
- 0.0002 = $20.70 rörelse krävs

---

### 6. **Position Size** 💰
**Vad:** Hur mycket per trade?

**Varför:** Risk management
- Fast (order_qty): Samma storlek varje trade
- Dynamisk (position_size_pct): Procentbaserat

**Testa:**
```json
"order_qty": [0.0005, 0.001, 0.002],
"position_size_pct": [null, 0.05, 0.1, 0.15]
```

**Tumregel:** 
- Konservativ: 1-2% av kapital per trade
- Måttlig: 5-10%
- Aggressiv: 15-20% (riskabelt!)

---

### 7. **L Update Strategy** 🔄
**Vad:** När uppdatera breakout-nivån L?

**Varför:** Påverkar hur ofta nya entries triggas

**Testa:**
```json
"l_update_strategy": ["on_exit", "on_tp_only", "periodic"]
"l_update_interval": [60, 180, 300, 600]
```

**Strategier:**
- **on_exit**: Uppdatera vid varje exit (nuvarande)
- **on_tp_only**: Bara vid TP (ignorerar BE/SL)
- **periodic**: Var X sekunder oavsett trades

---

### 8. **Volatility Filter** 📊
**Vad:** Bara trade vid hög volatilitet

**Varför:** Breakouts fungerar bäst i volatila marknader

**Testa:**
```json
"volatility_filter": [false, true]
"min_volatility": [0.0005, 0.001, 0.0015, 0.002]
```

**När använda:**
- Range market → Aktivera
- Trending market → Inaktivera

---

### 9. **Time Filter** ⏰
**Vad:** Bara trade vissa tider

**Varför:** Vissa tider har bättre likviditet/volatilitet

**Testa:**
```json
"time_filter": [false, true]
"trading_hours_utc": [[0,24], [8,22], [13,21]]
```

**Vanliga strategier:**
- **[8,22]**: Undvik natt (låg volym)
- **[13,21]**: US market hours
- **[0,24]**: Alltid (crypto 24/7)

---

## Viktiga Metrics att Följa

### 1. **Sharpe Ratio** ⭐
**Vad:** Risk-justerad avkastning

**Formel:** (Avg Return - Risk Free Rate) / Std Dev of Returns

**Tolkning:**
- < 1.0: Dålig (risk väger inte upp avkastning)
- 1.0-2.0: OK
- 2.0-3.0: Bra
- > 3.0: Utmärkt

**Använd:** Primär metric för optimering

---

### 2. **Win Rate** 🎯
**Vad:** Procent vinster

**Formel:** Wins / Total Trades

**Tolkning:**
- < 40%: Problem med strategi
- 40-50%: OK om profit factor > 2
- 50-60%: Bra
- > 60%: Utmärkt (eller overfit!)

**Varning:** Hög win rate ≠ lönsam
- 90% win rate med små vinster + 10% stora förluster = förlust

---

### 3. **Profit Factor** 💵
**Vad:** Total vinst / Total förlust

**Formel:** Sum(Winning Trades) / Abs(Sum(Losing Trades))

**Tolkning:**
- < 1.0: Förlust (mer förluster än vinster)
- 1.0-1.5: Marginellt lönsam
- 1.5-2.0: Bra
- > 2.0: Utmärkt

**Minsta krav:** > 1.5 för live trading

---

### 4. **Max Drawdown** 📉
**Vad:** Största peak-to-trough förlust

**Formel:** (Peak Capital - Trough Capital) / Peak Capital

**Tolkning:**
- < 10%: Utmärkt
- 10-20%: OK
- 20-30%: Högrisk
- > 30%: Farligt

**Använd:** Riskbedömning
- Psykologisk: Klarar du av 30% förlust?
- Praktisk: Riskerar margin call?

---

### 5. **Average Trade Duration** ⏱️
**Vad:** Genomsnittlig tid i position

**Varför:** Påverkar risk och strategi-typ
- < 1 min: Scalping
- 1-30 min: Day trading
- 30 min - 4h: Intraday
- > 4h: Swing

**Användning:**
- Kortare → Behöver snabbare execution
- Längre → Tålamod krävs

---

### 6. **ROI (Return on Investment)** 📈
**Vad:** Total avkastning

**Formel:** (End Capital - Start Capital) / Start Capital × 100

**Tolkning:**
- Per dag: 0.5-1% = Bra
- Per vecka: 3-7% = Bra  
- Per månad: 10-30% = Utmärkt

**Realistiska mål:**
- Nybörjare: 10-20% per år
- Erfaren: 50-100% per år
- Professionell: 100-300% per år

---

## Optimeringsprocess (Steg-för-Steg)

### Steg 1: Definiera Hypotes 🤔
"Jag tror att en högre TP (0.002) och trailing stop kommer ge bättre Sharpe ratio"

### Steg 2: Välj Parametrar 🎯
```python
param_grid = {
    'tp_pct': [0.001, 0.0015, 0.002, 0.0025],
    'trailing_stop': [False, True],
    'trailing_offset_pct': [0.0005, 0.001]
}
```

### Steg 3: Kör Grid Search 🔍
```bash
python strategy_optimizer.py
```

### Steg 4: Analysera Resultat 📊
```
🏆 TOP 10 RESULTAT (sorterat efter sharpe_ratio):

Rank   Params                          Sharpe  Win%    PnL$      Trades
1      tp=0.002, trailing=True         2.84    58.3    $456.20   120
2      tp=0.0015, trailing=True        2.67    61.2    $398.50   145
3      tp=0.002, trailing=False        2.51    55.8    $423.10   110
```

### Steg 5: Validera På Ny Data ✅
Test bästa config på ny tidsperiod för att bekräfta

### Steg 6: Paper Trade 📝
Kör live paper trading i 1-2 veckor

### Steg 7: Small Live Test 💰
Om fortfarande bra → litet live kapital

---

## Vanliga Misstag att Undvika ⚠️

### 1. **Overfitting** 🎯🚫
**Problem:** Parametrar som fungerar perfekt på test-data men failar live

**Symptom:**
- Mycket hög win rate (>80%)
- Perfekt Sharpe (>5.0)
- För många parametrar optimerade

**Lösning:**
- Testa på out-of-sample data
- Håll parametrar enkla
- Prioritera robusthet över perfekt fit

### 2. **Not Enough Data** 📉
**Problem:** Optimerar på för få trades

**Minimum:**
- 100+ trades för meningsfulla metrics
- 1000+ trades för robust optimering

**Lösning:**
- Samla mer data
- Använd längre tidsperiod
- Eller börja med paper trading

### 3. **Ignoring Transaction Costs** 💸
**Problem:** Glömmer avgifter i backtest

**Effekt:**
- Ser lönsam ut i test
- Förlorar pengar live

**Lösning:**
- Inkludera ALLTID avgifter
- Lägg till slippage (0.01-0.05%)
- Räkna konservativt

### 4. **Optimizing for Win Rate** 🎯
**Problem:** Fokuserar bara på att vinna ofta

**Varför dåligt:**
- Kan vinna 90% av trades men förlora totalt
- 1 stor förlust raderar 100 små vinster

**Bättre:** Optimera för Sharpe eller Profit Factor

### 5. **Not Testing Both Sides** ⚖️
**Problem:** Optimerar bara LONG eller SHORT

**Varför dåligt:**
- Strategin kanske fungerar olika i olika riktningar
- Market har olika dynamik

**Lösning:**
- Testa båda separat
- Eller balansera start-kapital

---

## Rekommenderad Optimeringsordning

### Fas 1: Basics (Viktigast) ⭐⭐⭐
1. **tp_pct** - Mest kritisk parameter
2. **sl_pct** - Risk management
3. **be_offset_pct** - Skydd

**Exempel:**
```python
param_grid = {
    'tp_pct': [0.0005, 0.001, 0.0015, 0.002, 0.003],
    'sl_pct': [None, 0.0005, 0.001, 0.002],
    'be_offset_pct': [0.0002, 0.0004, 0.0006, 0.0008]
}
```

### Fas 2: Advanced (Efter basics fungerar) ⭐⭐
4. **trailing_stop** - Maximera vinster
5. **min_movement_pct** - Filtrera signals
6. **position_size_pct** - Risk sizing

### Fas 3: Filters (Sist) ⭐
7. **volatility_filter** - Market conditions
8. **time_filter** - Trading hours
9. **l_update_strategy** - Fine-tuning

---

## Praktiskt Exempel: Full Optimering

### Config att Testa:
```json
{
    "tp_pct": [0.001, 0.0015, 0.002],
    "sl_pct": [null, 0.001, 0.0015],
    "trailing_stop": [false, true],
    "min_movement_pct": [0.0001, 0.0002]
}
```

**Totalt:** 3 × 3 × 2 × 2 = 36 kombinationer

### Kör:
```bash
python strategy_optimizer.py
```

### Exempel Output:
```
🔍 Grid Search: 36 kombinationer att testa

Test 1/36: {'tp_pct': 0.001, 'sl_pct': None, 'trailing_stop': False, 'min_movement_pct': 0.0001}
  → Trades: 145, Win Rate: 54.5%, PnL: $23.45, Sharpe: 1.82

Test 2/36: {'tp_pct': 0.001, 'sl_pct': None, 'trailing_stop': False, 'min_movement_pct': 0.0002}
  → Trades: 98, Win Rate: 58.2%, PnL: $28.92, Sharpe: 2.15

...

Test 36/36: {'tp_pct': 0.002, 'sl_pct': 0.0015, 'trailing_stop': True, 'min_movement_pct': 0.0002}
  → Trades: 67, Win Rate: 62.7%, PnL: $45.20, Sharpe: 2.89

🏆 TOP 5 RESULTAT (sorterat efter sharpe_ratio):

Rank   Params                                                          Sharpe  Win%    PnL$      Trades
1      tp=0.002, sl=0.001, trail=True, min_mov=0.0002                 2.89    62.7    $45.20    67
2      tp=0.0015, sl=0.001, trail=True, min_mov=0.0001                2.67    59.3    $38.50    89
3      tp=0.002, sl=None, trail=True, min_mov=0.0002                  2.54    58.1    $42.10    72
4      tp=0.0015, sl=0.001, trail=False, min_mov=0.0002               2.45    61.2    $35.80    78
5      tp=0.001, sl=0.001, trail=True, min_mov=0.0002                 2.31    64.5    $28.40    112
```

### Slutsats:
**Bästa config:** tp=0.002, sl=0.001, trailing=True, min_movement=0.0002
- Sharpe: 2.89 (Utmärkt!)
- Win rate: 62.7% (Bra)
- 67 trades (Tillräckligt för statistisk signifikans)

**Nästa steg:** Testa på ny data för validering

---

## Verktyg & Filer

### 1. Config med Alla Parametrar
**Fil:** `config_advanced.json`
- Alla optimerbara parametrar
- Kommentarer om vad varje gör
- Förslag på värden att testa

### 2. Optimeringsverktyg
**Fil:** `strategy_optimizer.py`
- Grid search implementation
- Performance metrics
- Result ranking

### 3. Använd Så Här:
```bash
# 1. Redigera param_grid i strategy_optimizer.py
# 2. Kör
python strategy_optimizer.py

# 3. Analysera optimization_results_TIMESTAMP.csv
# 4. Uppdatera din config.json med bästa parametrar
# 5. Testa live med paper trading
```

---

## Sammanfattning

### Viktigast att Optimera (I Ordning):
1. ✅ **tp_pct** - Take profit
2. ✅ **sl_pct** - Stop loss
3. ✅ **be_offset_pct** - Breakeven
4. ✅ **trailing_stop** - Trailing
5. ⚙️ **min_movement_pct** - Filtrera
6. ⚙️ **position_size** - Risk

### Metrics att Fokusera På:
1. **Sharpe Ratio** - Primär (risk-adjusted return)
2. **Profit Factor** - Sekundär (win/loss ratio)
3. **Max Drawdown** - Risk check
4. **Win Rate** - Bara för kontext

### Process:
1. Definiera hypotes
2. Välj 2-4 parametrar
3. Kör grid search
4. Analysera top 5-10 results
5. Validera på ny data
6. Paper trade
7. Small live test

**Viktigast:** Optimera systematiskt, inte gissa! 🎯📊✅