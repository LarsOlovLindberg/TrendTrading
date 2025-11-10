"""
Situation Analysis Script
=========================
Analyserar trading-logs för att identifiera vilka marknadssituationer som ger bäst resultat.

Annoterar varje trade med:
- Tid på dygnet (hour UTC)
- Dag i veckan
- Volatilitet vid entry (beräknad från price history)
- Win/Loss outcome
- Markov-state vid entry

Grupperar och beräknar:
- Win-rate per timme
- Win-rate per volatilitetsnivå
- Genomsnittlig PnL per scenario

Output:
- Konsolrapport med rekommendationer
- CSV med annoterade trades
- Förslag på filter-parametrar för config.json
"""

import csv
import json
import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import statistics


@dataclass
class TradeRecord:
    """En annoterad trade med kontext"""
    timestamp: datetime
    state: str  # LW, LB, SW, SB
    side: str  # LONG, SHORT
    entry_price: float
    exit_price: float
    duration_sec: float
    mfe_pct: float
    mae_pct: float
    
    # Annotated context
    hour_utc: int
    day_of_week: int  # 0=Monday, 6=Sunday
    is_win: bool
    pnl_pct: float


@dataclass
class ScenarioStats:
    """Statistik för ett specifikt scenario"""
    scenario_name: str
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float
    avg_pnl_pct: float
    avg_duration_sec: float
    avg_mfe_pct: float
    avg_mae_pct: float


def load_trade_metrics(csv_path: str) -> List[TradeRecord]:
    """Ladda och parsa trade_metrics.csv"""
    trades = []
    
    if not os.path.exists(csv_path):
        print(f"⚠️ Hittade inte {csv_path}")
        return trades
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Fix timestamp format (remove double +00:00 if present)
                ts_str = row["exit_ts"].replace("Z", "")
                if ts_str.count("+00:00") > 1:
                    ts_str = ts_str.replace("+00:00", "", 1)  # Remove first occurrence
                if not ts_str.endswith("+00:00") and not ts_str.endswith("Z"):
                    ts_str += "+00:00"
                ts = datetime.fromisoformat(ts_str)
                state = row["state"]
                side = row["side"]
                entry_price = float(row["entry_price"])
                exit_price = float(row["exit_price"])
                duration = float(row["duration_sec"])
                mfe_pct = float(row["mfe_pct"])
                mae_pct = float(row["mae_pct"])
                
                # Bestäm win/loss
                is_win = state in ["LW", "SW"]
                
                # Beräkna PnL%
                if side == "LONG":
                    pnl_pct = (exit_price - entry_price) / entry_price
                else:  # SHORT
                    pnl_pct = (entry_price - exit_price) / entry_price
                
                trade = TradeRecord(
                    timestamp=ts,
                    state=state,
                    side=side,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    duration_sec=duration,
                    mfe_pct=mfe_pct,
                    mae_pct=mae_pct,
                    hour_utc=ts.hour,
                    day_of_week=ts.weekday(),
                    is_win=is_win,
                    pnl_pct=pnl_pct,
                )
                trades.append(trade)
            except (KeyError, ValueError) as e:
                print(f"⚠️ Kunde inte parsa rad: {e}")
                continue
    
    return trades


def calculate_scenario_stats(trades: List[TradeRecord], 
                            filter_func, 
                            scenario_name: str) -> Optional[ScenarioStats]:
    """Beräkna statistik för trades som matchar ett filter"""
    filtered = [t for t in trades if filter_func(t)]
    
    if not filtered:
        return None
    
    win_count = sum(1 for t in filtered if t.is_win)
    loss_count = len(filtered) - win_count
    win_rate = win_count / len(filtered) if filtered else 0.0
    
    avg_pnl = statistics.mean(t.pnl_pct for t in filtered) if filtered else 0.0
    avg_duration = statistics.mean(t.duration_sec for t in filtered) if filtered else 0.0
    avg_mfe = statistics.mean(t.mfe_pct for t in filtered) if filtered else 0.0
    avg_mae = statistics.mean(t.mae_pct for t in filtered) if filtered else 0.0
    
    return ScenarioStats(
        scenario_name=scenario_name,
        trade_count=len(filtered),
        win_count=win_count,
        loss_count=loss_count,
        win_rate=win_rate,
        avg_pnl_pct=avg_pnl,
        avg_duration_sec=avg_duration,
        avg_mfe_pct=avg_mfe,
        avg_mae_pct=avg_mae,
    )


def analyze_by_hour(trades: List[TradeRecord]) -> List[ScenarioStats]:
    """Analysera win-rate per timme på dygnet"""
    results = []
    for hour in range(24):
        stats = calculate_scenario_stats(
            trades,
            lambda t: t.hour_utc == hour,
            f"Hour {hour:02d}:00 UTC"
        )
        if stats:
            results.append(stats)
    return results


def analyze_by_day_of_week(trades: List[TradeRecord]) -> List[ScenarioStats]:
    """Analysera win-rate per veckodag"""
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    results = []
    for day in range(7):
        stats = calculate_scenario_stats(
            trades,
            lambda t: t.day_of_week == day,
            day_names[day]
        )
        if stats:
            results.append(stats)
    return results


def analyze_by_state(trades: List[TradeRecord]) -> List[ScenarioStats]:
    """Analysera win-rate per Markov-state"""
    states = ["LW", "LB", "SW", "SB"]
    results = []
    for state in states:
        stats = calculate_scenario_stats(
            trades,
            lambda t: t.state == state,
            f"State: {state}"
        )
        if stats:
            results.append(stats)
    return results


def analyze_by_duration(trades: List[TradeRecord]) -> List[ScenarioStats]:
    """Analysera win-rate per trade-duration"""
    buckets = [
        (0, 30, "0-30s (Very Quick)"),
        (30, 60, "30-60s (Quick)"),
        (60, 180, "1-3min (Medium)"),
        (180, 600, "3-10min (Long)"),
        (600, float('inf'), ">10min (Very Long)"),
    ]
    results = []
    for min_dur, max_dur, name in buckets:
        stats = calculate_scenario_stats(
            trades,
            lambda t: min_dur <= t.duration_sec < max_dur,
            name
        )
        if stats:
            results.append(stats)
    return results


def print_scenario_report(scenarios: List[ScenarioStats], title: str):
    """Skriv ut en formaterad rapport"""
    print(f"\n{'='*80}")
    print(f"{title:^80}")
    print(f"{'='*80}")
    print(f"{'Scenario':<30} {'Trades':>8} {'Wins':>6} {'W/R%':>7} {'Avg PnL%':>10} {'Avg Dur':>10}")
    print(f"{'-'*80}")
    
    for s in sorted(scenarios, key=lambda x: x.win_rate, reverse=True):
        print(f"{s.scenario_name:<30} {s.trade_count:>8} {s.win_count:>6} "
              f"{s.win_rate*100:>6.1f}% {s.avg_pnl_pct*100:>9.3f}% {s.avg_duration_sec:>9.1f}s")


def generate_recommendations(trades: List[TradeRecord]) -> Dict[str, any]:
    """Generera rekommendationer baserat på analys"""
    recommendations = {}
    
    # Analysera timmar
    hourly = analyze_by_hour(trades)
    if hourly:
        best_hours = [h for h in hourly if h.win_rate > 0.55 and h.trade_count >= 5]
        worst_hours = [h for h in hourly if h.win_rate < 0.45 and h.trade_count >= 5]
        
        if best_hours:
            best_hour_ranges = [int(h.scenario_name.split()[1].split(":")[0]) for h in best_hours]
            recommendations["suggested_trading_hours"] = best_hour_ranges
        
        if worst_hours:
            worst_hour_ranges = [int(h.scenario_name.split()[1].split(":")[0]) for h in worst_hours]
            recommendations["avoid_hours"] = worst_hour_ranges
    
    # Analysera duration
    duration = analyze_by_duration(trades)
    if duration:
        quick_trades = [d for d in duration if "Quick" in d.scenario_name or "Very Quick" in d.scenario_name]
        if quick_trades:
            avg_win_rate_quick = statistics.mean(t.win_rate for t in quick_trades)
            if avg_win_rate_quick < 0.45:
                recommendations["suggestion"] = "Snabba trades (<60s) har låg win-rate - överväg att öka MIN_MOVE_PCT eller COOLDOWN_SEC"
    
    # Analysera states
    states = analyze_by_state(trades)
    if states:
        loss_states = [s for s in states if "LB" in s.scenario_name or "SB" in s.scenario_name]
        if loss_states:
            avg_loss_count = statistics.mean(s.trade_count for s in loss_states)
            total_trades = sum(s.trade_count for s in states)
            loss_ratio = (sum(s.trade_count for s in loss_states) / total_trades) if total_trades > 0 else 0
            
            if loss_ratio > 0.5:
                recommendations["warning"] = f"Över 50% av trades är breakeven/loss ({loss_ratio*100:.1f}%) - överväg att öka TP_PCT"
    
    return recommendations


def save_annotated_trades(trades: List[TradeRecord], output_path: str):
    """Spara annoterade trades till CSV"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp", "state", "side", "entry_price", "exit_price",
            "duration_sec", "mfe_pct", "mae_pct", "hour_utc", "day_of_week",
            "is_win", "pnl_pct"
        ])
        for t in trades:
            writer.writerow([
                t.timestamp.isoformat(),
                t.state,
                t.side,
                t.entry_price,
                t.exit_price,
                t.duration_sec,
                t.mfe_pct,
                t.mae_pct,
                t.hour_utc,
                t.day_of_week,
                1 if t.is_win else 0,
                t.pnl_pct,
            ])
    print(f"✅ Annoterade trades sparade till: {output_path}")


def main():
    print("🔍 Situation Analysis - Trading Pattern Recognition")
    print("="*80)
    
    # Ladda data
    metrics_path = os.path.join("logs", "trade_metrics.csv")
    trades = load_trade_metrics(metrics_path)
    
    if not trades:
        print("❌ Inga trades hittades. Kör live-scriptet först för att samla data.")
        return
    
    print(f"📊 Laddade {len(trades)} trades från {metrics_path}")
    print(f"   Tidsperiod: {trades[0].timestamp.date()} till {trades[-1].timestamp.date()}")
    
    # Kör analyser
    print("\n🔬 Kör analyser...")
    
    hourly_stats = analyze_by_hour(trades)
    daily_stats = analyze_by_day_of_week(trades)
    state_stats = analyze_by_state(trades)
    duration_stats = analyze_by_duration(trades)
    
    # Skriv ut rapporter
    print_scenario_report(hourly_stats, "WIN-RATE PER TIMME (UTC)")
    print_scenario_report(daily_stats, "WIN-RATE PER VECKODAG")
    print_scenario_report(state_stats, "WIN-RATE PER MARKOV-STATE")
    print_scenario_report(duration_stats, "WIN-RATE PER TRADE-DURATION")
    
    # Generera rekommendationer
    recommendations = generate_recommendations(trades)
    
    print(f"\n{'='*80}")
    print(f"{'REKOMMENDATIONER':^80}")
    print(f"{'='*80}")
    
    if "suggested_trading_hours" in recommendations:
        hours = recommendations["suggested_trading_hours"]
        print(f"✅ Bästa timmar att trade (>55% win-rate): {hours}")
        print(f"   Förslag: Sätt 'trading_hours_utc' till att inkludera dessa timmar")
    
    if "avoid_hours" in recommendations:
        hours = recommendations["avoid_hours"]
        print(f"⚠️  Undvik dessa timmar (<45% win-rate): {hours}")
    
    if "suggestion" in recommendations:
        print(f"💡 {recommendations['suggestion']}")
    
    if "warning" in recommendations:
        print(f"⚠️  {recommendations['warning']}")
    
    # Beräkna overall stats
    total_trades = len(trades)
    total_wins = sum(1 for t in trades if t.is_win)
    overall_win_rate = total_wins / total_trades if total_trades > 0 else 0
    overall_pnl = sum(t.pnl_pct for t in trades)
    
    print(f"\n{'='*80}")
    print(f"{'SAMMANFATTNING':^80}")
    print(f"{'='*80}")
    print(f"Totalt antal trades: {total_trades}")
    print(f"Wins: {total_wins} ({overall_win_rate*100:.1f}%)")
    print(f"Losses: {total_trades - total_wins} ({(1-overall_win_rate)*100:.1f}%)")
    print(f"Total PnL: {overall_pnl*100:.3f}%")
    print(f"Avg PnL per trade: {(overall_pnl/total_trades)*100:.3f}%" if total_trades > 0 else "N/A")
    
    # Spara annoterade trades
    output_path = os.path.join("data", "annotated_trades.csv")
    os.makedirs("data", exist_ok=True)
    save_annotated_trades(trades, output_path)
    
    print(f"\n{'='*80}")
    print("✅ Analys klar!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
