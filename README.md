# Markov Adaptive Trading Strategy

🚀 **Intelligent hybrid trading bot** that automatically switches between BREAKOUT and MEAN REVERSION strategies based on real-time market analysis.

## 🎯 Features

### Adaptive Mode Selection
- **📈 BREAKOUT Mode**: Follows strong trends (trend strength > 0.55)
- **🔄 MEAN REVERSION Mode**: Bets on price returning to average (trend strength < 0.45)
- **⚡ Real-time monitoring**: Checks trend EVERY tick (0.5s) for fast reaction
- **🔄 Quick switch**: 5s cooldown between mode changes
- Automatic switching based on 6 different market metrics
- Hysteresis (0.45-0.55 buffer) prevents excessive flapping

### Advanced Trend Detection
Uses 6 robust metrics for accurate trend identification:
1. **Directional Consistency** (25%) - Consecutive moves in same direction
2. **Linear Regression R²** (20%) - How well price fits a line
3. **ADX-like Strength** (20%) - Directional movement dominance
4. **Trend Structure** (15%) - Higher highs / Lower lows pattern
5. **Moving Average Separation** (12%) - Short vs long MA distance
6. **Volatility Ratio** (8%) - Movement consistency

### Trading Features
- ✅ **Progressive Scaling**: Scale in/out based on position performance
- ✅ **Real-time Binance prices** (public API, no keys needed for paper trading)
- ✅ **Paper trading mode**: Test without risk
- ✅ **Visual graph**: Real-time chart with mode indicators
- ✅ **Detailed logging**: All trades logged to CSV

## 📁 Files

### Main Strategies
- **`Markov adaptive live paper.py`** - ⭐ Intelligent hybrid (RECOMMENDED)
- **`Markov breakout live paper smart.py`** - Breakout only (trend following)
- **`Markov reversion live paper.py`** - Mean reversion only

### Documentation
- **`QUICK_START.md`** - Quick start guide
- **`ADAPTIVE_STRATEGY_SUMMARY.md`** - Technical details
- **`ADAPTIVE_CONFIG_GUIDE.md`** - Parameter tuning guide

### Configuration
- **`config.json.example`** - Example configuration (rename to config.json)

## 🚀 Quick Start

### 1. Install Requirements
```bash
pip install requests matplotlib
```

### 2. Configure
Copy `config.json.example` to `config.json` and edit:
```json
{
  "base_symbol": "BTCUSDT",
  "order_test": true,
  "order_qty": 0.001,
  "paper_usdt": "10000",
  "tp_pct": 0.0010,
  ...
}
```

### 3. Run
```bash
python "Markov adaptive live paper.py"
```

### 4. Watch
- **Graph**: Shows price, L-line, and current mode
- **Info box**: Current mode with trend score
- **Console**: Real-time trade notifications

## 📊 Understanding the Output

### Graph Info Box
```
📈 BREAKOUT | LONG @ 43521.00 | PnL: +0.15%
Trend: 0.73
```
- Background color: **Orange** = BREAKOUT, **Cyan** = REVERSION
- Trend score: 0.0 (no trend) to 1.0 (strong trend)

### Console Output
```
📊 TREND CHECK: MODERATE TREND | Score: 0.624 | Mode: BREAKOUT
   └─ Pris: 43521.00 | Δ: +0.156% | Range: 45.20 | Max streak: 8

🔄 MODE SWITCH: MEAN_REVERSION → BREAKOUT
   Trend Strength: 0.623
```

## ⚙️ Configuration

### Key Parameters
```python
# In the code (line ~657):
trend_detector = TrendDetector(window_size=50)
mode_manager = StrategyModeManager(
    threshold=0.50,      # Mode switch point
    hysteresis=0.08      # Buffer zone
)
```

### Tuning for Different Markets
- **High volatility**: Increase hysteresis to 0.08, increase cooldown to 10s
- **Low volatility**: Decrease hysteresis to 0.03, decrease cooldown to 3s
- **More BREAKOUT**: Lower threshold to 0.40
- **More REVERSION**: Raise threshold to 0.60
- **Faster switching**: Decrease hysteresis (default: 0.05) and cooldown (default: 5s)
- **More stable**: Increase hysteresis and cooldown

See `ADAPTIVE_CONFIG_GUIDE.md` for detailed tuning options.

## 📈 Strategy Logic

### BREAKOUT Mode (Trending Market)
```
Entry: LONG on up-break, SHORT on down-break (follow trend)
Exit:  TP when momentum continues, Stop when reverses to L
L:     Follows entry price (trailing stop)
```

### MEAN REVERSION Mode (Ranging Market)
```
Entry: SHORT on up-break, LONG on down-break (bet on return)
Exit:  TP at L-line crossing, Stop when continues away
L:     Target level for mean reversion
```

## 🛡️ Risk Warning

⚠️ **This is experimental software for educational purposes.**

- Start with **paper trading** (`order_test: true`)
- Test for **days/weeks** before considering real money
- Never risk more than you can afford to lose
- Past performance does not guarantee future results

## 📝 Logs

All trades are logged to:
- `logs/orders_paper.csv` - Individual trade details
- `logs/session_summary.csv` - Session statistics

## 🔧 Troubleshooting

### Mode never switches
- Check trend score in info box (shown every 50 ticks)
- Market might be in hysteresis zone (0.42-0.58)
- Try adjusting threshold or hysteresis

### Too many mode switches
- Increase hysteresis to 0.10
- Increase cooldown to 45-60 seconds

### No entries happening
- Wait ~20 ticks for initialization
- Check console for error messages

## 📚 Documentation

For detailed information, see:
- `QUICK_START.md` - Getting started guide
- `ADAPTIVE_STRATEGY_SUMMARY.md` - Complete technical documentation
- `ADAPTIVE_CONFIG_GUIDE.md` - Parameter tuning and optimization

## 🤝 Contributing

This is a personal trading strategy. Feel free to fork and modify for your own use.

## ⚖️ License

Personal use only. No warranty provided.

---

**Good luck with adaptive trading! 🚀**

*Remember: Test thoroughly before risking real capital.*
