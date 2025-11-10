# Quick Configuration Guide - Markov Adaptive Strategy

## Tuning the Mode Selector

### Key Parameters in Code

```python
# Instantiation (line ~533)
trend_detector = TrendDetector(window_size=50)
mode_manager = StrategyModeManager(threshold=0.6, hysteresis=0.05)
```

### What Each Parameter Does

#### `window_size` (TrendDetector)
- **Default**: 50 ticks
- **What it does**: How many recent price ticks to analyze for trend
- **Smaller values** (20-30): More responsive, switches faster
- **Larger values** (70-100): More stable, switches slower
- **Recommendation**: Keep 50 for balanced responsiveness

#### `threshold` (StrategyModeManager)
- **Default**: 0.6
- **What it does**: The trend strength cutoff between modes
- **Range**: 0.0 - 1.0
- **Lower values** (0.4-0.5): Use BREAKOUT more often (more aggressive)
- **Higher values** (0.7-0.8): Use MEAN_REVERSION more often (more conservative)
- **Current logic**:
  - trend < 0.55: MEAN_REVERSION
  - trend > 0.65: BREAKOUT
  - 0.55-0.65: Stay in current mode

#### `hysteresis` (StrategyModeManager)
- **Default**: 0.05
- **What it does**: Buffer zone to prevent rapid mode switching
- **Smaller values** (0.02-0.03): More sensitive, switches easier
- **Larger values** (0.08-0.10): More stable, harder to switch
- **Recommendation**: Keep 0.05 for good balance

### Mode Switch Cooldown
```python
# In StrategyModeManager.__init__ (line ~167)
self.switch_cooldown_seconds: float = 30.0  # Wait 30s between switches
```
- **Default**: 30 seconds
- **What it does**: Minimum time between mode changes
- **Shorter** (10-20s): More frequent adaptation
- **Longer** (60-120s): More stable, fewer switches
- **Recommendation**: Start with 30s, adjust based on results

---

## Adjusting for Different Market Conditions

### For Very Volatile Markets (e.g., high volume crypto pumps)
```python
trend_detector = TrendDetector(window_size=30)        # More responsive
mode_manager = StrategyModeManager(threshold=0.5, hysteresis=0.03)
# Lower threshold = easier to trigger BREAKOUT mode
# Smaller hysteresis = adapt faster
```

### For Ranging/Choppy Markets (e.g., low volume sideways)
```python
trend_detector = TrendDetector(window_size=70)        # More stable
mode_manager = StrategyModeManager(threshold=0.7, hysteresis=0.08)
# Higher threshold = prefer MEAN_REVERSION mode
# Larger hysteresis = stay in mode longer
```

### For Balanced/Unknown Markets (Recommended Starting Point)
```python
trend_detector = TrendDetector(window_size=50)        # Current default
mode_manager = StrategyModeManager(threshold=0.6, hysteresis=0.05)
# Balanced: switches at moderate trends
```

---

## Understanding the Trend Strength Score

### Score Ranges and Interpretation

| Trend Strength | Market State | Recommended Mode | Description |
|---------------|--------------|------------------|-------------|
| 0.0 - 0.2 | STRONGLY RANGING | MEAN_REVERSION | Price oscillating with no direction |
| 0.2 - 0.4 | RANGING | MEAN_REVERSION | Some movement but no clear trend |
| 0.4 - 0.6 | TRANSITIONAL | Either (hysteresis) | Borderline: building or losing trend |
| 0.6 - 0.8 | TRENDING | BREAKOUT | Clear directional movement |
| 0.8 - 1.0 | STRONGLY TRENDING | BREAKOUT | Very strong momentum |

### Real-Time Monitoring
Watch the info box on the graph:
```
📈 BREAKOUT | LONG @ 43521.00 | PnL: +0.15%
Trend: 0.73
```
- **Trend < 0.55**: Expect cyan box (🔄 MEAN_REVERSION)
- **Trend > 0.65**: Expect orange box (📈 BREAKOUT)
- **Trend 0.55-0.65**: Current mode maintained (hysteresis)

---

## Fine-Tuning the Trend Metrics

If you want to change the **weight** of each metric in trend calculation:

```python
# In TrendDetector.calculate_trend_strength() (line ~129)
trend_strength = (
    directional_consistency * 0.5 +  # 50% weight
    slope_strength * 0.3 +            # 30% weight
    movement_efficiency * 0.2          # 20% weight
)
```

### Example Adjustments:

**Emphasize Directional Consistency** (more reactive to momentum):
```python
trend_strength = (
    directional_consistency * 0.6 +
    slope_strength * 0.2 +
    movement_efficiency * 0.2
)
```

**Emphasize Slope** (focus on linear trends):
```python
trend_strength = (
    directional_consistency * 0.3 +
    slope_strength * 0.5 +
    movement_efficiency * 0.2
)
```

**Emphasize Efficiency** (prefer clean trends over choppy):
```python
trend_strength = (
    directional_consistency * 0.4 +
    slope_strength * 0.3 +
    movement_efficiency * 0.3
)
```

---

## Testing Different Configurations

### Recommended Testing Process:

1. **Start with defaults** (50 ticks, 0.6 threshold, 0.05 hysteresis)
2. **Run for 4-8 hours** on live paper trading
3. **Observe**:
   - How often does mode switch?
   - Does it switch at appropriate times?
   - Are exits happening too early/late?
4. **Adjust ONE parameter at a time**
5. **Test again and compare results**

### What to Look For:

**Too Many Mode Switches** (>1 every 5 minutes):
- **Increase** hysteresis to 0.08-0.10
- **Increase** cooldown to 60-90 seconds
- **Increase** window_size to 70-80

**Too Few Mode Switches** (stuck in one mode):
- **Decrease** hysteresis to 0.03
- **Decrease** cooldown to 15-20 seconds
- **Decrease** window_size to 30-40
- **Adjust** threshold toward 0.5 (more balanced)

**Wrong Mode for Market** (BREAKOUT in ranging, REVERSION in trending):
- **Check threshold**: Is it too high/low for current market?
- **Check trend score**: Is calculation working correctly?
- **Adjust weights**: Maybe market needs different metric emphasis

---

## Common Scenarios and Solutions

### Scenario 1: "Strategy keeps switching back and forth"
**Problem**: Hysteresis too small or market truly borderline  
**Solution**: Increase hysteresis to 0.08 and cooldown to 45s

### Scenario 2: "Stuck in REVERSION mode during strong trend"
**Problem**: Threshold too high (0.7+) or window too large  
**Solution**: Lower threshold to 0.55 or reduce window to 40

### Scenario 3: "Stuck in BREAKOUT mode during ranging"
**Problem**: Threshold too low (0.4-) or window too small  
**Solution**: Raise threshold to 0.65 or increase window to 60

### Scenario 4: "Mode switches mid-position and ruins trade"
**Problem**: Normal behavior, but can add position protection  
**Solution**: Consider adding logic to close position before mode switch

---

## Advanced: Position Protection on Mode Switch

Currently the strategy continues the position with new exit rules when mode switches.

If you want to **close position before switching**:

```python
# In main loop after mode_changed (line ~1447)
if mode_changed and pos.side != "FLAT":
    print(f"⚠️ Mode switched - closing {pos.side} position for safety")
    if ORDER_TEST:
        if pos.side == "LONG":
            paper.market_sell(SYMBOL, pos.qty, price)
        else:
            paper.market_buy(SYMBOL, pos.qty, price)
    do_exit(pos.side, price, "MODE_SWITCH")
    pos.flat()
    L = price  # Reset L to current price
```

**Pros**: Cleaner mode transitions, no confusion  
**Cons**: May exit winning positions prematurely

---

## Configuration Quick Reference

| Use Case | window_size | threshold | hysteresis | cooldown |
|----------|-------------|-----------|------------|----------|
| **Default (Balanced)** | 50 | 0.6 | 0.05 | 30s |
| **Aggressive (More BREAKOUT)** | 40 | 0.5 | 0.03 | 20s |
| **Conservative (More REVERSION)** | 60 | 0.7 | 0.08 | 45s |
| **High Volatility** | 30 | 0.5 | 0.03 | 15s |
| **Low Volatility** | 70 | 0.65 | 0.07 | 60s |
| **Very Stable (Few Switches)** | 80 | 0.6 | 0.10 | 90s |

---

## Monitoring Performance

### Key Metrics to Track:

1. **Mode Distribution**: % of time in each mode
2. **Win Rate per Mode**: BREAKOUT wins vs REVERSION wins
3. **Switch Frequency**: Switches per hour
4. **Average Trade Duration**: Per mode
5. **PnL per Mode**: Which mode is more profitable?

### Logging Mode Changes:

All mode changes are logged in console:
```
🔄 MODE SWITCH: MEAN_REVERSION → BREAKOUT (trend=0.723)
```

You can add CSV logging for analysis:
```python
# After mode_changed in main loop
if mode_changed:
    with open("logs/mode_changes.csv", "a") as f:
        f.write(f"{datetime.now()},{current_mode},{trend_strength}\n")
```

---

## Summary

**Start with defaults** and adjust based on observation:
- Window size affects **responsiveness**
- Threshold affects **mode preference**
- Hysteresis affects **stability**
- Cooldown affects **switch frequency**

**Golden rule**: Change ONE thing at a time and test thoroughly!
