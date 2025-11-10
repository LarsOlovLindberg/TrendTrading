"""
Auto-Tune System
================
Automatisk parameterjustering baserat på recent performance.

Analyserar senaste N trades och justerar:
- TP_PCT baserat på MFE/MAE-profiler
- MIN_MOVE_PCT baserat på quick-trade performance
- COOLDOWN_SEC baserat på trade-frequency patterns
- Trading hours baserat på hourly win-rate

Kör detta script regelbundet (t.ex. var 100:e trade) för att hålla strategin optimerad.
"""

import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import statistics


class AutoTuner:
    def __init__(self, config_path: str = "config.json", metrics_path: str = "logs/trade_metrics.csv"):
        self.config_path = config_path
        self.metrics_path = metrics_path
        self.config = self._load_config()
        self.trades = self._load_recent_trades(lookback_trades=100)
        
    def _load_config(self) -> dict:
        """Ladda nuvarande config"""
        with open(self.config_path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    
    def _load_recent_trades(self, lookback_trades: int = 100) -> List[dict]:
        """Ladda senaste N trades"""
        trades = []
        
        if not os.path.exists(self.metrics_path):
            print(f"⚠️ Hittade inte {self.metrics_path}")
            return trades
        
        with open(self.metrics_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            all_trades = list(reader)
            
        # Ta senaste N trades
        recent = all_trades[-lookback_trades:] if len(all_trades) > lookback_trades else all_trades
        
        for row in recent:
            try:
                # Fix timestamp
                ts_str = row["exit_ts"].replace("Z", "")
                if ts_str.count("+00:00") > 1:
                    ts_str = ts_str.replace("+00:00", "", 1)
                if not ts_str.endswith("+00:00"):
                    ts_str += "+00:00"
                
                trade = {
                    "timestamp": datetime.fromisoformat(ts_str),
                    "state": row["state"],
                    "side": row["side"],
                    "entry_price": float(row["entry_price"]),
                    "exit_price": float(row["exit_price"]),
                    "duration_sec": float(row["duration_sec"]),
                    "mfe_pct": float(row["mfe_pct"]),
                    "mae_pct": float(row["mae_pct"]),
                }
                trades.append(trade)
            except (KeyError, ValueError) as e:
                continue
        
        return trades
    
    def calculate_win_rate(self) -> float:
        """Beräkna win-rate för senaste trades"""
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t["state"] in ["LW", "SW"])
        return wins / len(self.trades)
    
    def calculate_be_ratio(self) -> float:
        """Beräkna breakeven-ratio"""
        if not self.trades:
            return 0.0
        be_trades = sum(1 for t in self.trades if t["state"] in ["LB", "SB"])
        return be_trades / len(self.trades)
    
    def analyze_quick_trades(self) -> Tuple[int, float]:
        """Analysera snabba trades (<60s)"""
        quick = [t for t in self.trades if t["duration_sec"] < 60]
        if not quick:
            return 0, 0.0
        wins = sum(1 for t in quick if t["state"] in ["LW", "SW"])
        return len(quick), wins / len(quick)
    
    def analyze_hourly_performance(self) -> Dict[int, float]:
        """Analysera win-rate per timme"""
        hourly_trades = defaultdict(list)
        for t in self.trades:
            hour = t["timestamp"].hour
            is_win = t["state"] in ["LW", "SW"]
            hourly_trades[hour].append(is_win)
        
        hourly_wr = {}
        for hour, wins in hourly_trades.items():
            if len(wins) >= 3:  # Minst 3 trades för att vara relevant
                hourly_wr[hour] = sum(wins) / len(wins)
        
        return hourly_wr
    
    def suggest_tp_pct(self) -> float:
        """Föreslå ny TP_PCT baserat på MFE-profil"""
        if not self.trades:
            return self.config.get("tp_pct", 0.001)
        
        # Beräkna 75:e percentilen av MFE för vinnande trades
        wins = [t for t in self.trades if t["state"] in ["LW", "SW"]]
        if not wins:
            # Inga wins → öka TP för att ge mer rum
            current_tp = self.config.get("tp_pct", 0.001)
            return min(current_tp * 1.2, 0.003)  # Öka 20%, max 0.3%
        
        mfe_75 = statistics.quantiles([t["mfe_pct"] for t in wins], n=4)[2]  # 75th percentile
        
        # TP borde vara lite under 75:e percentilen av MFE
        suggested_tp = mfe_75 * 0.85
        
        # Clamp till rimliga värden
        return max(0.0008, min(suggested_tp, 0.003))
    
    def suggest_min_move_pct(self) -> float:
        """Föreslå ny MIN_MOVE_PCT baserat på quick-trade performance"""
        quick_count, quick_wr = self.analyze_quick_trades()
        current_min_move = self.config.get("min_movement_pct", 0.00015)
        
        if quick_count < 5:
            return current_min_move  # Inte tillräckligt med data
        
        if quick_wr < 0.3:
            # Dålig quick-trade performance → öka MIN_MOVE
            return min(current_min_move * 1.5, 0.0005)
        elif quick_wr > 0.6:
            # Bra quick-trade performance → kan minska lite
            return max(current_min_move * 0.9, 0.0001)
        
        return current_min_move
    
    def suggest_cooldown_sec(self) -> float:
        """Föreslå ny COOLDOWN_SEC"""
        quick_count, quick_wr = self.analyze_quick_trades()
        current_cooldown = self.config.get("cooldown_sec", 3.0)
        
        if quick_count < 5:
            return current_cooldown
        
        if quick_wr < 0.3:
            # Snabba trades förlorar → längre cooldown
            return min(current_cooldown + 2.0, 10.0)
        elif quick_wr > 0.6:
            # Snabba trades vinner → kan minska cooldown
            return max(current_cooldown - 1.0, 1.0)
        
        return current_cooldown
    
    def suggest_trading_hours(self) -> List[List[int]]:
        """Föreslå trading hours baserat på hourly performance"""
        hourly_wr = self.analyze_hourly_performance()
        
        if not hourly_wr:
            return self.config.get("trading_hours_utc", [[8, 22]])
        
        # Identifiera bra timmar (>45% win-rate)
        good_hours = sorted([h for h, wr in hourly_wr.items() if wr > 0.45])
        
        if not good_hours:
            # Inga bra timmar → behåll current
            return self.config.get("trading_hours_utc", [[8, 22]])
        
        # Gruppera consecutiva timmar till ranges
        ranges = []
        start = good_hours[0]
        prev = start
        
        for hour in good_hours[1:]:
            if hour != prev + 1:
                # Gap → ny range
                ranges.append([start, prev + 1])
                start = hour
            prev = hour
        
        ranges.append([start, prev + 1])
        
        return ranges
    
    def generate_recommendations(self) -> Dict[str, any]:
        """Generera alla rekommendationer"""
        if not self.trades:
            return {"error": "Ingen data tillgänglig"}
        
        win_rate = self.calculate_win_rate()
        be_ratio = self.calculate_be_ratio()
        quick_count, quick_wr = self.analyze_quick_trades()
        
        recommendations = {
            "current_performance": {
                "trades_analyzed": len(self.trades),
                "win_rate": f"{win_rate*100:.1f}%",
                "be_ratio": f"{be_ratio*100:.1f}%",
                "quick_trades": quick_count,
                "quick_win_rate": f"{quick_wr*100:.1f}%" if quick_count > 0 else "N/A"
            },
            "suggested_changes": {},
            "reasoning": []
        }
        
        # TP_PCT
        current_tp = self.config.get("tp_pct", 0.001)
        suggested_tp = self.suggest_tp_pct()
        if abs(suggested_tp - current_tp) > 0.0001:
            recommendations["suggested_changes"]["tp_pct"] = round(suggested_tp, 5)
            recommendations["reasoning"].append(
                f"TP: {current_tp} → {suggested_tp:.5f} (baserat på MFE-profil)"
            )
        
        # MIN_MOVE_PCT
        current_min_move = self.config.get("min_movement_pct", 0.00015)
        suggested_min_move = self.suggest_min_move_pct()
        if abs(suggested_min_move - current_min_move) > 0.00005:
            recommendations["suggested_changes"]["min_movement_pct"] = round(suggested_min_move, 5)
            recommendations["reasoning"].append(
                f"MIN_MOVE: {current_min_move} → {suggested_min_move:.5f} (quick-trade wr: {quick_wr*100:.1f}%)"
            )
        
        # COOLDOWN_SEC
        current_cooldown = self.config.get("cooldown_sec", 3.0)
        suggested_cooldown = self.suggest_cooldown_sec()
        if abs(suggested_cooldown - current_cooldown) > 0.5:
            recommendations["suggested_changes"]["cooldown_sec"] = round(suggested_cooldown, 1)
            recommendations["reasoning"].append(
                f"COOLDOWN: {current_cooldown}s → {suggested_cooldown:.1f}s"
            )
        
        # Trading hours
        current_hours = self.config.get("trading_hours_utc", [[8, 22]])
        suggested_hours = self.suggest_trading_hours()
        if suggested_hours != current_hours:
            recommendations["suggested_changes"]["trading_hours_utc"] = suggested_hours
            recommendations["reasoning"].append(
                f"HOURS: {current_hours} → {suggested_hours} (baserat på hourly win-rate)"
            )
        
        # BE ratio warning
        if be_ratio > 0.6:
            recommendations["reasoning"].append(
                f"⚠️ Hög BE-ratio ({be_ratio*100:.1f}%) → överväg att öka TP_PCT ytterligare"
            )
        
        return recommendations
    
    def apply_recommendations(self, recommendations: dict, backup: bool = True):
        """Tillämpa rekommendationerna på config.json"""
        if "suggested_changes" not in recommendations or not recommendations["suggested_changes"]:
            print("✅ Inga ändringar behövs!")
            return
        
        # Backup
        if backup:
            backup_path = self.config_path.replace(".json", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
            print(f"📁 Backup sparad: {backup_path}")
        
        # Uppdatera config
        for key, value in recommendations["suggested_changes"].items():
            self.config[key] = value
        
        # Spara
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)
        
        print(f"✅ Config uppdaterad: {self.config_path}")


def main():
    print("🤖 Auto-Tune System - Automatic Strategy Optimization")
    print("="*80)
    
    tuner = AutoTuner()
    
    if not tuner.trades:
        print("❌ Ingen data att analysera. Kör live-scriptet först!")
        return
    
    print(f"📊 Analyserar senaste {len(tuner.trades)} trades...\n")
    
    recommendations = tuner.generate_recommendations()
    
    # Visa current performance
    perf = recommendations["current_performance"]
    print("CURRENT PERFORMANCE:")
    print(f"  Trades analyzed: {perf['trades_analyzed']}")
    print(f"  Win-rate: {perf['win_rate']}")
    print(f"  BE-ratio: {perf['be_ratio']}")
    print(f"  Quick trades (<60s): {perf['quick_trades']} (WR: {perf['quick_win_rate']})")
    
    # Visa recommendations
    if recommendations.get("suggested_changes"):
        print("\n" + "="*80)
        print("RECOMMENDED CHANGES:")
        print("="*80)
        
        for reason in recommendations["reasoning"]:
            print(f"  • {reason}")
        
        print("\n" + "="*80)
        print("APPLY CHANGES? (y/n): ", end="")
        response = input().strip().lower()
        
        if response == "y":
            tuner.apply_recommendations(recommendations, backup=True)
            print("\n✅ Auto-tune complete! Restart your trading script to use new settings.")
        else:
            print("\n⏸️ Changes not applied. Run again when ready.")
    else:
        print("\n✅ Current settings are optimal! No changes recommended.")
    
    print("="*80)


if __name__ == "__main__":
    main()
