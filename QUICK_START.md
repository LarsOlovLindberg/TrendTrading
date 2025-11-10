# Quick Start Guide - Markov Adaptive Strategy

## What Is This?

An intelligent trading bot that **automatically switches** between two opposite strategies:

### 📈 BREAKOUT Mode (Trending Markets)
- **When**: Strong trend detected (score ≥ 0.65)
- **Strategy**: Follow the trend
- **Entry**: LONG on up-break, SHORT on down-break
- **Exit**: TP when momentum continues, Stop when reverses

### 🔄 MEAN REVERSION Mode (Ranging Markets)
- **When**: Weak trend detected (score < 0.55)
- **Strategy**: Bet on price returning to average
- **Entry**: SHORT on up-break, LONG on down-break (opposite!)
- **Exit**: TP at L-line crossing, Stop when continues away

---

## How to Run

### Step 1: Check Requirements
```bash
# Make sure you have:
python --version  # Should be 3.11+
pip install requests matplotlib
```

### Step 2: Check Config
Open `config.json` and verify:
```json
{
  "base_symbol": "BTCUSDT",
  "order_test": true,         // Keep true for paper trading
  "order_qty": 0.001,         // Amount per trade
  "paper_usdt": "10000",      // Starting balance
  "tp_pct": 0.0010,           // 0.10% TP
  "taker_fee_pct": 0.0004,    // 0.04% fee
  ...
}
```

### Step 3: Run the Bot
```bash
python "Markov adaptive live paper.py"
```

### Step 4: Watch the Graph
A graph window will open showing:
- **Blue line**: Price
- **Orange dashed line**: L-line
- **Info box** (top right): Current mode with trend score
- **Orange/Cyan background**: Shows current mode
- **Markers**: Entries, exits, scale events, mode changes

---

## Understanding the Graph

### Info Box (Top Right Corner)
```
📈 BREAKOUT | LONG @ 43521.00 | PnL: +0.15%
Trend: 0.73
```

**What it means**:
- 📈 = Currently in BREAKOUT mode (or 🔄 for REVERSION)
- LONG = Position direction and entry price
- PnL = Current profit/loss
- Trend: 0.73 = Strong trend (0.0 = no trend, 1.0 = strongest)
- **Background color**: Orange = BREAKOUT, Cyan = REVERSION

### Graph Markers

| Marker | Color | Meaning |
|--------|-------|---------|
| L↑100 | Green | LONG entry at 100% position |
| S↓100 | Red | SHORT entry at 100% position |
| ↑X.Xx | Cyan | Scale IN (increase position) |
| ↓X.Xx | Yellow | Scale OUT (reduce position) |
| ✓+X.X% | Green | Exit with profit |
| ✗-X.X% | Dark Red | Exit with loss |
| 💀 | Red | Position withered to 0% |
| 📈BRK | Orange | Mode switch to BREAKOUT |
| 🔄REV | Cyan | Mode switch to REVERSION |

### Console Output

**Mode Switch**:
```
🔄 MODE SWITCH: MEAN_REVERSION → BREAKOUT (trend=0.723)
```

**Entry**:
```
📈 ENTER LONG @ 43521.00 qty=0.001 (100%)
🎯 START [BREAKOUT]: Priset över L (43500.00) → LONG (följ trend)
```

**Exit**:
```
✅ LONG EXIT [BREAKOUT]: TP nådd @ 43564.32 (target 43564.21)
🔚 EXIT LONG @ 43564.32 (entry 43521.00)  PnL: 0.100% ($0.4332) [LW]
```

**Scaling**:
```
➕ SCALE IN (recovery +0.04%): Enter 0.0002 @ 43540.00 | Total: 0.0012 (1.2x)
➖ SCALE OUT (loss -0.03%): Exit 0.0002 @ 43510.00 | Remaining: 0.0008 (0.8x)
```

---

## What to Expect

### During Trending Market (BTC pumping/dumping)
- **Mode**: BREAKOUT (orange info box)
- **Behavior**: Follows trend with LONG/SHORT
- **Exits**: Quick TPs as trend continues
- **Scaling**: Minimal (trend is consistent)
- **Performance**: Good if trend is strong and sustained

### During Ranging Market (BTC sideways)
- **Mode**: MEAN_REVERSION (cyan info box)
- **Behavior**: Bets against breakouts (SHORT up, LONG down)
- **Exits**: At L-line crossings
- **Scaling**: Active (position scales in/out with oscillations)
- **Performance**: Good if price oscillates around L

### During Transition (Market changing)
- **Mode**: May switch back and forth
- **Behavior**: Wait 30s between switches (cooldown)
- **Hysteresis**: Won't flip on small changes (0.55-0.65 buffer)
- **Performance**: May have some false switches

---

## First Run Checklist

### Before Starting
- [ ] `config.json` has `"order_test": true` (paper mode)
- [ ] Python 3.11+ installed
- [ ] `requests` and `matplotlib` libraries installed
- [ ] Good internet connection (fetches real Binance prices)

### During First 10 Minutes
- [ ] Graph opens and shows price line
- [ ] Info box shows current mode
- [ ] First position opens after ~20 ticks
- [ ] Console shows entries/exits
- [ ] Mode switches occur (or not, depending on market)

### Things to Watch
1. **Trend Score**: Should change gradually (0.0-1.0)
2. **Mode Switches**: Should be logical (not flapping rapidly)
3. **Entries**: Should follow mode logic (LONG/SHORT correct direction)
4. **Exits**: Should hit TP or Stop appropriately
5. **Scaling**: Should work in both modes

---

## Common Questions

### Q: Which mode is better?
**A**: Depends on market! BREAKOUT for trending, REVERSION for ranging. That's why it's adaptive!

### Q: How often should mode switch?
**A**: Ideally 2-5 times per hour. Too many = unstable, too few = not adaptive.

### Q: Can I force a specific mode?
**A**: Yes! Set threshold very high (0.9) for always REVERSION, or very low (0.1) for always BREAKOUT.

### Q: What if mode switches during a position?
**A**: Position continues with new exit rules. This is normal. See warning in console.

### Q: How do I know if it's working?
**A**: 
- Mode switches match market conditions (trend score makes sense)
- More wins in appropriate modes (BREAKOUT in trends, REVERSION in ranging)
- Overall PnL positive over time

### Q: Can I run multiple symbols?
**A**: Not currently. Run separate instances with different config files.

### Q: Is this safe for real money?
**A**: Start with paper trading (`order_test: true`). Test for days/weeks before considering real money.

---

## Performance Monitoring

### Files to Check

**`logs/orders_paper.csv`**:
- All trades with PnL
- Filter by state to see wins/losses

**`logs/session_summary.csv`**:
- Session-level stats
- Entry at startup, update on exit

**Console Output**:
- Real-time updates
- Mode switches
- Entry/exit notifications

### Key Metrics

After 24 hours, check:
1. **Total PnL**: Profitable or not?
2. **Win Rate**: % of winning trades
3. **Mode Distribution**: Time in each mode
4. **Switch Frequency**: Too many/few switches?
5. **Avg Trade Duration**: Reasonable for strategy?

---

## Quick Adjustments

### If Too Many Mode Switches
Edit line ~533 in the Python file:
```python
mode_manager = StrategyModeManager(threshold=0.6, hysteresis=0.08)  # Increase hysteresis
```

### If Stuck in One Mode
```python
mode_manager = StrategyModeManager(threshold=0.6, hysteresis=0.03)  # Decrease hysteresis
```

### If Want More BREAKOUT
```python
mode_manager = StrategyModeManager(threshold=0.5, hysteresis=0.05)  # Lower threshold
```

### If Want More REVERSION
```python
mode_manager = StrategyModeManager(threshold=0.7, hysteresis=0.05)  # Higher threshold
```

See `ADAPTIVE_CONFIG_GUIDE.md` for detailed tuning options.

---

## Stopping the Bot

### Clean Exit
1. Press `Ctrl+C` in the terminal
2. Bot will finish current operations
3. Session summary written to logs
4. Graph window closes

### Emergency Stop
1. Close graph window
2. Press `Ctrl+C` multiple times
3. Check `logs/` for any partial data

---

## Next Steps

1. **Run for a few hours** with defaults
2. **Observe mode switching** behavior
3. **Check results** in logs
4. **Adjust parameters** if needed (one at a time!)
5. **Test adjustments** for another few hours
6. **Repeat** until satisfied with performance

### Full Documentation
- `ADAPTIVE_STRATEGY_SUMMARY.md`: Complete technical details
- `ADAPTIVE_CONFIG_GUIDE.md`: Detailed parameter tuning
- `config.json`: All strategy settings

---

## Troubleshooting

### Graph doesn't open
- Check matplotlib installed: `pip install matplotlib`
- Try running with `python -i` to keep console open

### "requests saknas" error
- Install requests: `pip install requests`

### "No price data" errors
- Check internet connection
- Binance API might be down (rare)
- Try different symbol in config

### Mode never switches
- Check trend score in info box
- Market might be in hysteresis zone (0.55-0.65)
- Try smaller hysteresis or different threshold

### Entries not happening
- Check START_MODE completes (needs ~20 ticks)
- Verify L-line is set correctly
- Check cooldown hasn't locked entries

---

## Support

For questions about:
- **Strategy logic**: See `ADAPTIVE_STRATEGY_SUMMARY.md`
- **Parameter tuning**: See `ADAPTIVE_CONFIG_GUIDE.md`
- **Config settings**: Check `config.json`
- **Code details**: Read comments in `Markov adaptive live paper.py`

---

**Good luck with adaptive trading! 🚀**

Remember: Start small, test thoroughly, and never risk more than you can afford to lose.
