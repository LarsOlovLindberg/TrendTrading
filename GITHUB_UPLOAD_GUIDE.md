# 🔐 SÄKER GitHub Upload Guide

## ⚠️ VIKTIGT - SÄKERHET FÖRST!

**BYT DITT GITHUB-LÖSENORD OMEDELBART!**
Du delade ditt lösenord i chatten - detta är ALDRIG säkert. Byt det här:
👉 https://github.com/settings/security

---

## 📋 Steg-för-steg Guide

### Steg 1: Skapa Repository på GitHub (manuellt)

1. Gå till: https://github.com/new
2. Logga in med ditt GitHub-konto (LarsOlovLindberg)
3. Fyll i:
   - **Repository name**: `markov-adaptive-trading`
   - **Description**: `Intelligent hybrid trading strategy with adaptive mode switching`
   - **Visibility**: 🔒 **Private** (REKOMMENDERAT för trading-strategier!)
   - ❌ **AVMARKERA** "Initialize with README" (vi har redan en!)
4. Klicka "Create repository"

### Steg 2: Koppla Lokal Git till GitHub

GitHub visar nu kommandon. Använd dessa i din terminal:

```powershell
cd C:\Users\lars-\Binance

# Lägg till GitHub som remote (byt URL till din faktiska repo-URL)
git remote add origin https://github.com/LarsOlovLindberg/markov-adaptive-trading.git

# Byt till main branch (GitHub's standard)
git branch -M main

# Pusha din kod
git push -u origin main
```

### Steg 3: Autentisering

GitHub kommer fråga om inloggning. **ANVÄND INTE LÖSENORD!** 

#### Alternativ A: Personal Access Token (REKOMMENDERAT)

1. Gå till: https://github.com/settings/tokens
2. Klicka "Generate new token (classic)"
3. Ge den ett namn: "Markov Trading Upload"
4. Välj scope: `repo` (full repository access)
5. Klicka "Generate token"
6. **KOPIERA TOKEN OMEDELBART** (visas bara en gång!)
7. När Git frågar om lösenord, klistra in TOKEN istället

#### Alternativ B: GitHub CLI (enklare)

```powershell
# Installera GitHub CLI
winget install --id GitHub.cli

# Logga in
gh auth login

# Följ instruktionerna (välj HTTPS, autentisera via browser)
```

---

## ✅ Verifiera Upload

Efter push, gå till:
```
https://github.com/LarsOlovLindberg/markov-adaptive-trading
```

Du borde se:
- ✅ README.md visas
- ✅ Alla Python-filer
- ✅ Dokumentation
- ❌ INGA logs/ filer (skyddade av .gitignore)
- ❌ INGEN config.json (endast config.json.example)

---

## 🔄 Framtida Uppdateringar

När du gör ändringar:

```powershell
cd C:\Users\lars-\Binance

# Se vilka filer som ändrats
git status

# Lägg till ändringar
git add .

# Skapa commit med beskrivning
git commit -m "Beskrivning av vad du ändrat"

# Pusha till GitHub
git push
```

---

## 🛡️ Säkerhetstips

### ✅ GÖR:
- Använd **Private repository** för trading-strategier
- Använd **Personal Access Token** istället för lösenord
- Kontrollera `.gitignore` innan varje push
- Håll `config.json` lokal (endast .example på GitHub)
- Pusha aldrig API-nycklar eller trading-logs

### ❌ GÖR INTE:
- Dela lösenord i chattar eller textfiler
- Pusha `config.json` med riktiga API-nycklar
- Gör repository Public om det innehåller känslig info
- Commit:a logs/ eller data/ mappar med faktiska trades

---

## 📊 Vad Finns i Repository?

### Main Strategies (pushade)
- ✅ `Markov adaptive live paper.py` - Hybrid strategy
- ✅ `Markov breakout live paper smart.py` - Breakout only
- ✅ `Markov reversion live paper.py` - Reversion only

### Documentation (pushad)
- ✅ `README.md` - Overview
- ✅ `QUICK_START.md` - Getting started
- ✅ `ADAPTIVE_STRATEGY_SUMMARY.md` - Technical details
- ✅ `ADAPTIVE_CONFIG_GUIDE.md` - Tuning guide

### Config (pushad)
- ✅ `config.json.example` - Example config
- ❌ `config.json` - SKYDDAD (i .gitignore)

### Logs (INTE pushade)
- ❌ `logs/*.csv` - SKYDDADE (i .gitignore)
- ❌ `*.log` - SKYDDADE (i .gitignore)

---

## 🆘 Troubleshooting

### "Permission denied"
➡️ Använd Personal Access Token istället för lösenord

### "Authentication failed"
➡️ Kontrollera att token har `repo` scope

### "Repository not found"
➡️ Dubbelkolla repository URL är korrekt

### "Files too large"
➡️ Kolla om du råkat inkludera logs:
```powershell
git rm --cached logs/*.csv
git commit -m "Remove large log files"
```

---

## 📱 Kommande: Klona på annan dator

När du vill ladda ner på en annan dator:

```powershell
# Klona repository
git clone https://github.com/LarsOlovLindberg/markov-adaptive-trading.git

# Gå in i mappen
cd markov-adaptive-trading

# Kopiera example config
cp config.json.example config.json

# Redigera config.json med dina inställningar
notepad config.json

# Kör strategin
python "Markov adaptive live paper.py"
```

---

## ✅ Checklista innan Push

- [ ] Kollat att config.json INTE är staged (`git status`)
- [ ] Kollat att inga logs/*.csv är staged
- [ ] Läst igenom vilka filer som ska pushas
- [ ] Säker på att inga API-nycklar finns i koden
- [ ] Repository är satt till Private (för trading-strategier)
- [ ] Använder Personal Access Token (INTE lösenord)

---

**🎉 Lycka till med GitHub-uppladdningen!**

*Kom ihåg: BYT DITT LÖSENORD FÖRST!*
