# 🚀 Data-Driven Trading System - Quick Start Guide

## 📁 Vad du nu har

### 1. **situation_analysis.py** - Smart Analys
Analyserar alla dina trades och hittar mönster:
- Bästa/sämsta timmar att trade
- Win-rate per trade-duration
- Markov-state performance
- MFE/MAE-profiler

**Kör:**
```powershell
python situation_analysis.py
```

**Output:**
- Konsolrapport med rekommendationer
- `data/annotated_trades.csv` - Data för vidare analys

---

### 2. **performance_viz.ipynb** - Visualisering
Jupyter notebook med 6 interaktiva visualiseringar:
- Win-rate per timme (heatmap)
- Win-rate per duration (bar chart)
- Markov-state performance
- PnL distribution
- Cumulative PnL över tid
- MFE/MAE scatter plot

**Öppna i VS Code:**
1. Öppna `performance_viz.ipynb`
2. Kör cellerna från topp till botten
3. Se graferna och automatiska rekommendationer

---

### 3. **auto_tune.py** - Automatisk Optimering
Justerar automatiskt config.json baserat på senaste 100 trades:
- `TP_PCT` - baserat på MFE-profiler
- `MIN_MOVE_PCT` - baserat på quick-trade performance
- `COOLDOWN_SEC` - baserat på entry-frequency
- `trading_hours_utc` - baserat på hourly win-rate

**Kör:**
```powershell
python auto_tune.py
```

Svarar "y" för att applicera ändringar (skapar backup först).

---

## 🔄 Workflow (Rekommenderad)

### Steg 1: Samla Data (Första gången)
```powershell
# Starta live trading
python "Markov breakout live paper smart.py"

# Låt köra i 1-2 timmar (minst 50-100 trades)
# Stoppa med Ctrl+C
```

### Steg 2: Analysera
```powershell
# Kör analys
python situation_analysis.py
```

**Titta efter:**
- ⚠️ Vilka timmar har <45% win-rate? (undvik dessa)
- ⚠️ Har snabba trades (<60s) låg win-rate? (öka MIN_MOVE_PCT)
- ⚠️ Är BE-ratio >60%? (öka TP_PCT)

### Steg 3: Visualisera (Valfritt)
```powershell
# Öppna notebook i VS Code
code performance_viz.ipynb
```

Kör alla celler för att se graferna.

### Steg 4: Auto-Tune
```powershell
# Låt systemet föreslå optimeringar
python auto_tune.py

# Svarar 'y' om du godkänner förslagen
```

### Steg 5: Testa Nya Inställningar
```powershell
# Starta om med nya parametrar
python "Markov breakout live paper smart.py"

# Låt köra igen, upprepa från Steg 2
```

---

## ⚙️ Nuvarande Config (Data-Optimerad)

Baserat på din första analys (22 trades, 13.6% win-rate):

### ❌ Problem som hittades:
1. **86% BE-ratio** - för många breakeven-exits
2. **Snabba trades (<60s) hade 0% win-rate**
3. **Timmar 11-14 UTC hade 0-12.5% win-rate**

### ✅ Åtgärder som tagits:
```json
{
  "tp_pct": 0.0018,              // Ökat från 0.0012 → mer marginal
  "min_movement_pct": 0.00045,   // Ökat från 0.00015 → undviker fladder
  "cooldown_sec": 7.0,           // Ökat från 3.0 → mer tid mellan trades
  "time_filter": true,
  "trading_hours_utc": [[8,11], [15,20]], // Undviker 11-14 UTC
  "rearm_gap_pct": 0.0006,       // Ökat från 0.0004
  "loss_pause_count": 3,         // Kräver 3 förluster innan pause
  "pause_resume_pct": 0.001      // 0.10% tröskel för resume
}
```

---

## 📊 Förväntat Resultat

**Med gamla inställningar:**
- 22 trades på 2.5 timmar
- 13.6% win-rate
- 86% breakeven-ratio
- Många snabba (<60s) förlust-trades

**Med nya inställningar (förväntat):**
- Färre trades totalt (~5-10 per timme)
- Högre win-rate (mål: >40%)
- Lägre BE-ratio (<50%)
- Längre trade-duration (mer än 1 minut i snitt)

---

## 🎯 Iterativ Förbättring

Detta är en **kontinuerlig process**:

1. **Samla 100 trades** → kör auto-tune
2. **Upprepa varje vecka** eller när win-rate sjunker
3. **Jämför** resultat över tid (använd visualiseringarna)
4. **Finjustera** baserat på marknadförändringar

### Auto-Tune Schedule:
- **Efter första 100 trades** → grundkalibrering
- **Var 100:e trade därefter** → löpande justering
- **Vid stora förändringar** (t.ex. ny marknad, ny timeframe)

---

## 🛠️ Troubleshooting

### "Ingen data att analysera"
→ Kör live-scriptet först i minst 30 minuter

### "Auto-tune sänkte TP för mycket"
→ Manuellt sätt tillbaka i config.json och kör igen efter fler trades

### "Fortfarande låg win-rate efter tuning"
→ Överväg:
  - Aktivera `volatility_filter`
  - Öka `min_volatility` till 0.002
  - Testa andra lookahead-värden (10, 20, 30)
  - Överväg trailing stops

### "För få trades nu"
→ Filtren kan vara för strikta:
  - Minska `min_movement_pct` lite (t.ex. 0.0003)
  - Öka `trading_hours_utc` fönstret
  - Sänk `cooldown_sec` om win-rate är bra

---

## 📈 Nästa Steg (Avancerat)

När du har 500+ trades:

1. **Backtesting** - Testa parametrar på historiska klines
2. **ML-optimering** - Träna modell att predicera bra entry-timing
3. **Multi-symbol** - Testa på andra par (ETHUSDT, etc.)
4. **Live deployment** - Gå från paper till real trading (försiktigt!)

---

## 💡 Tips

- **Tålamod!** - Det tar 100-200 trades för att få tillförlitlig statistik
- **Dokumentera** - Spara kopior av config.json för varje iteration
- **Jämför** - Använd visualiseringarna för att se progress över tid
- **Var skeptisk** - Om något verkar för bra för att vara sant, testa mer!

---

**Lycka till! 🚀**
