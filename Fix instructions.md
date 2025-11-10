# Lösning: Permission Denied och DeprecationWarning

## Problemet
Du fick två fel när du körde skriptet:

### 1. Permission denied (CSV-fil låst)
```
⚠️ Polling-fel: [Errno 13] Permission denied: 'C:\\Users\\lars-\\Binance\\logs\\orders.csv'
```

**Orsak:** CSV-filen är öppen i Excel eller ett annat program som låser filen.

### 2. DeprecationWarning
```
DeprecationWarning: datetime.datetime.utcnow() is deprecated
```

**Orsak:** `datetime.utcnow()` är föråldrad och kommer tas bort i framtida Python-versioner.

---

## Lösningar

### Steg 1: Stäng Excel
**VIKTIGT:** Stäng Excel eller vilket program som helst som har `orders.csv` eller `markov.csv` öppna i mappen `C:\Users\lars-\Binance\logs\`.

### Steg 2: Använd fixade filer
Jag har skapat uppdaterade versioner som löser båda problemen:

**Fixade filer:**
- `Markov breakout live polling.py` - Live trading-skript
- `binance_testnet_setup.py` - Setup-skript

### Steg 3: Ersätt dina filer
Ladda ner de fixade filerna och ersätt dina gamla filer i `C:\Users\lars-\Binance\`.

---

## Vad har ändrats?

### Fix 1: Retry-logik för låsta filer
```python
def log_order(row: list):
    """Försöker skriva till CSV flera gånger om filen är låst"""
    max_retries = 5
    retry_delay = 0.2
    
    for attempt in range(max_retries):
        try:
            # Försök skriva till fil
            with open(ORDERS_CSV, "a", newline="", encoding="utf-8") as fp:
                # ... skrivning ...
            return  # Lyckades!
        except PermissionError:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)  # Vänta och försök igen
            else:
                print("⚠️ Kan inte skriva - stäng Excel!")
```

**Fördelar:**
- Försöker automatiskt 5 gånger om filen är låst
- Visar tydligt felmeddelande om det fortfarande inte fungerar
- Crashar inte hela programmet

### Fix 2: Modern datetime-hantering
```python
# FÖRE (föråldrad)
from datetime import datetime
timestamp = datetime.utcnow().isoformat(timespec="seconds")

# EFTER (modern Python)
from datetime import datetime, timezone
timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
```

**Fördelar:**
- Inga deprecation warnings
- Framtidssäkert (fungerar i Python 3.12+)
- Korrekt timezone-hantering

---

## Testning

### 1. Se till att inga filer är öppna
```bash
# Stäng alla Excel-fönster
# Stäng alla text-editorer med CSV-filer
```

### 2. Kör skriptet
```bash
cd C:\Users\lars-\Binance
python "Markov breakout live polling.py"
```

### 3. Förväntat resultat
```
🚀 Startar Binance Testnet live-strategi (REST API polling)...
🔧 Startnivå L=103619.96 för BTCUSDT
📡 Startar polling för BTCUSDT (interval: 0.5s)
✅ ENTER LONG @ 103620.50 qty=0.00100000
```

**OBS:** Inga "Permission denied" eller "DeprecationWarning" ska visas!

---

## Vanliga problem och lösningar

### Problem: Fortfarande "Permission denied"
**Lösning:**
1. Öppna Task Manager (Ctrl+Shift+Esc)
2. Leta efter Excel i "Processes"
3. Högerklicka och välj "End task"
4. Kör skriptet igen

### Problem: CSV-filen finns inte
**Lösning:**
```bash
# Skapa logs-mappen manuellt
mkdir C:\Users\lars-\Binance\logs
```

### Problem: Kan inte se trades
**Lösning:**
- Öppna `C:\Users\lars-\Binance\logs\orders.csv` EFTER att skriptet har stoppats
- Eller använd ett program som tillåter delad läsning (inte Excel)

---

## Best Practices

### 1. Övervaka loggar i realtid (utan att låsa filen)
Använd Windows PowerShell:
```powershell
Get-Content "C:\Users\lars-\Binance\logs\orders.csv" -Wait
```

### 2. Analysera loggar efter trading
```bash
# Stoppa skriptet (Ctrl+C)
# Öppna SEDAN orders.csv i Excel
```

### 3. Backup av loggar
```bash
# Kopiera logs-mappen regelbundet
cp -r logs logs_backup_2025-11-05
```

---

## Tekniska detaljer

### Varför "Permission denied" händer
Windows låser filer när de är öppna i vissa program (Excel, LibreOffice). När Python försöker skriva till en låst fil får du `PermissionError`.

### Retry-logikens funktion
1. Försök öppna filen
2. Om låst: vänta 0.2 sekunder
3. Försök igen (max 5 gånger)
4. Om fortfarande låst: visa meddelande och fortsätt

Detta förhindrar att hela programmet crashar om du råkar ha Excel öppet.

### datetime.now(timezone.utc) vs datetime.utcnow()
- `utcnow()` skapar en "naive" datetime (utan timezone-info)
- `now(timezone.utc)` skapar en "aware" datetime (med UTC-info)
- Python 3.12+ rekommenderar strongly aware datetimes

---

## Sammanfattning

✅ **Fixat:**
- CSV Permission denied (retry-logik)
- datetime DeprecationWarning (modern syntax)
- Bättre felmeddelanden
- Robustare filhantering

⚠️ **Kom ihåg:**
- Stäng Excel innan du kör skriptet
- Eller använd PowerShell för att övervaka loggar i realtid

🚀 **Redo att köra:**
```bash
python "Markov breakout live polling.py"
```