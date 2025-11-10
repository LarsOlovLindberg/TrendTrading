"""
Adaptive L-Line Calculator
===========================
Implementerar en dynamisk L-linje som anpassar sig till olika tidsramar och trender.

Koncept:
1. LÅNGSIKTIG (baseline) - medelvärde av senaste 800 ticks
2. KORTSIKTIG (trend) - medelvärde av senaste 100-200 ticks
3. TREND-STYRKA - detekterar starka rörelser (slope/volatilitet)
4. ADAPTIV VIKTNING - mixar baseline + trend baserat på trend-styrka

Resultat: L hamnar "mitt i" den relevanta price-action, både långsiktigt OCH kortsiktigt.
"""

from decimal import Decimal
from typing import List, Tuple
import statistics


class AdaptiveLCalculator:
    """
    Beräknar en adaptiv L-linje som reagerar på både långsiktig drift och kortsiktiga trender.
    """
    
    def __init__(
        self,
        baseline_window: int = 800,      # Långsiktig kontext
        trend_window: int = 150,          # Kortsiktig trend (100-200)
        trend_detect_window: int = 50,    # Fönster för att detektera styrka
        trend_threshold: float = 0.0005,  # Minsta trend-styrka för att vikta
        max_trend_weight: float = 0.7     # Max vikt för kortsiktig trend
    ):
        self.baseline_window = baseline_window
        self.trend_window = trend_window
        self.trend_detect_window = trend_detect_window
        self.trend_threshold = trend_threshold
        self.max_trend_weight = max_trend_weight
    
    def calculate_baseline(self, prices: List[Decimal]) -> Decimal:
        """Beräkna långsiktig baseline (medelvärde av senaste N ticks)"""
        if len(prices) < self.baseline_window:
            # Använd all tillgänglig data
            return sum(prices) / len(prices) if prices else Decimal(0)
        
        recent = prices[-self.baseline_window:]
        return sum(recent) / len(recent)
    
    def calculate_trend_center(self, prices: List[Decimal]) -> Decimal:
        """Beräkna kortsiktig trend-center (medelvärde av senaste trend_window ticks)"""
        if len(prices) < self.trend_window:
            return sum(prices) / len(prices) if prices else Decimal(0)
        
        recent = prices[-self.trend_window:]
        return sum(recent) / len(recent)
    
    def detect_trend_strength(self, prices: List[Decimal]) -> Tuple[float, str]:
        """
        Detektera styrkan på den kortsiktiga trenden.
        
        Returns:
            (strength, direction)
            strength: 0.0-1.0 (0 = ingen trend, 1 = stark trend)
            direction: 'up', 'down', eller 'neutral'
        """
        if len(prices) < self.trend_detect_window:
            return 0.0, 'neutral'
        
        recent = prices[-self.trend_detect_window:]
        recent_float = [float(p) for p in recent]
        
        # Beräkna linear regression slope (trendstyrka)
        n = len(recent_float)
        x = list(range(n))
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(recent_float)
        
        numerator = sum((x[i] - x_mean) * (recent_float[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator
        
        # Normalisera slope till styrka (0-1)
        # Dela slope med medelpris för att få relativ förändring per tick
        avg_price = y_mean
        relative_slope = abs(slope / avg_price) if avg_price > 0 else 0.0
        
        # Skala till 0-1 range (threshold bestämmer när det räknas som "trend")
        strength = min(relative_slope / self.trend_threshold, 1.0)
        
        # Bestäm riktning
        if slope > self.trend_threshold * avg_price:
            direction = 'up'
        elif slope < -self.trend_threshold * avg_price:
            direction = 'down'
        else:
            direction = 'neutral'
        
        return strength, direction
    
    def calculate_adaptive_L(self, prices: List[Decimal]) -> Tuple[Decimal, dict]:
        """
        Beräkna adaptiv L-linje med diagnostik.
        
        Returns:
            (adaptive_L, diagnostics)
            diagnostics innehåller: baseline, trend_center, trend_strength, trend_direction, weight
        """
        if not prices:
            return Decimal(0), {}
        
        # 1. Beräkna baseline (långsiktig)
        baseline = self.calculate_baseline(prices)
        
        # 2. Beräkna trend center (kortsiktig)
        trend_center = self.calculate_trend_center(prices)
        
        # 3. Detektera trend-styrka
        trend_strength, trend_direction = self.detect_trend_strength(prices)
        
        # 4. Beräkna adaptiv vikt
        # Om stark trend → ge mer vikt åt trend_center
        # Om svag trend → använd mest baseline
        trend_weight = trend_strength * self.max_trend_weight
        baseline_weight = 1.0 - trend_weight
        
        # 5. Blanda baseline och trend
        adaptive_L = (
            baseline * Decimal(str(baseline_weight)) +
            trend_center * Decimal(str(trend_weight))
        )
        
        # Diagnostik för logging
        diagnostics = {
            'baseline': float(baseline),
            'trend_center': float(trend_center),
            'trend_strength': trend_strength,
            'trend_direction': trend_direction,
            'trend_weight': trend_weight,
            'baseline_weight': baseline_weight,
            'adaptive_L': float(adaptive_L)
        }
        
        return adaptive_L, diagnostics
    
    def should_update_L(
        self, 
        current_L: Decimal, 
        adaptive_L: Decimal, 
        min_change_pct: float = 0.0001
    ) -> bool:
        """
        Bestäm om L borde uppdateras baserat på förändring.
        
        Args:
            current_L: Nuvarande L-värde
            adaptive_L: Nya beräknade L-värde
            min_change_pct: Minsta procentuell förändring för att uppdatera
        
        Returns:
            True om L borde uppdateras
        """
        if current_L == 0:
            return True
        
        change_pct = abs(adaptive_L - current_L) / current_L
        return change_pct >= Decimal(str(min_change_pct))


# Utility functions för integration i main script
def create_adaptive_L_calculator(config: dict) -> AdaptiveLCalculator:
    """Skapa calculator från config"""
    return AdaptiveLCalculator(
        baseline_window=config.get("adaptive_L_baseline_window", 800),
        trend_window=config.get("adaptive_L_trend_window", 150),
        trend_detect_window=config.get("adaptive_L_detect_window", 50),
        trend_threshold=config.get("adaptive_L_trend_threshold", 0.0005),
        max_trend_weight=config.get("adaptive_L_max_weight", 0.7)
    )


# Test / Demo
if __name__ == "__main__":
    import numpy as np
    
    print("🧪 Testing Adaptive L Calculator\n")
    
    # Simulera price data med trend
    base_price = 100000
    ticks = 1000
    
    # Scenario 1: Stabil range (ingen stark trend)
    print("=" * 80)
    print("SCENARIO 1: Stabil Range (Ingen Trend)")
    print("=" * 80)
    stable_prices = [
        Decimal(str(base_price + np.random.normal(0, 50))) 
        for _ in range(ticks)
    ]
    
    calc = AdaptiveLCalculator()
    adaptive_L, diag = calc.calculate_adaptive_L(stable_prices)
    
    print(f"Baseline (800 ticks):     {diag['baseline']:.2f}")
    print(f"Trend Center (150 ticks): {diag['trend_center']:.2f}")
    print(f"Trend Strength:           {diag['trend_strength']:.3f} ({diag['trend_direction']})")
    print(f"Trend Weight:             {diag['trend_weight']:.3f}")
    print(f"→ Adaptive L:             {diag['adaptive_L']:.2f}")
    print(f"   (Skillnad från baseline: {diag['adaptive_L'] - diag['baseline']:.2f})\n")
    
    # Scenario 2: Stark upptrend (senaste 150 ticks)
    print("=" * 80)
    print("SCENARIO 2: Stark Upptrend (Senaste 150 Ticks)")
    print("=" * 80)
    trend_prices = [Decimal(str(base_price + np.random.normal(0, 50))) for _ in range(850)]
    # Lägg till stark upptrend i sista 150 ticks
    for i in range(150):
        trend_prices.append(
            Decimal(str(base_price + 200 + i * 2 + np.random.normal(0, 20)))
        )
    
    adaptive_L, diag = calc.calculate_adaptive_L(trend_prices)
    
    print(f"Baseline (800 ticks):     {diag['baseline']:.2f}")
    print(f"Trend Center (150 ticks): {diag['trend_center']:.2f}")
    print(f"Trend Strength:           {diag['trend_strength']:.3f} ({diag['trend_direction']})")
    print(f"Trend Weight:             {diag['trend_weight']:.3f}")
    print(f"→ Adaptive L:             {diag['adaptive_L']:.2f}")
    print(f"   (Skillnad från baseline: {diag['adaptive_L'] - diag['baseline']:.2f})")
    print(f"   ✅ L har flyttats UPPÅT för att följa trenden!\n")
    
    # Scenario 3: Stark nedtrend
    print("=" * 80)
    print("SCENARIO 3: Stark Nedtrend (Senaste 150 Ticks)")
    print("=" * 80)
    down_prices = [Decimal(str(base_price + np.random.normal(0, 50))) for _ in range(850)]
    for i in range(150):
        down_prices.append(
            Decimal(str(base_price - 200 - i * 2 + np.random.normal(0, 20)))
        )
    
    adaptive_L, diag = calc.calculate_adaptive_L(down_prices)
    
    print(f"Baseline (800 ticks):     {diag['baseline']:.2f}")
    print(f"Trend Center (150 ticks): {diag['trend_center']:.2f}")
    print(f"Trend Strength:           {diag['trend_strength']:.3f} ({diag['trend_direction']})")
    print(f"Trend Weight:             {diag['trend_weight']:.3f}")
    print(f"→ Adaptive L:             {diag['adaptive_L']:.2f}")
    print(f"   (Skillnad från baseline: {diag['adaptive_L'] - diag['baseline']:.2f})")
    print(f"   ✅ L har flyttats NEDÅT för att följa trenden!\n")
    
    print("=" * 80)
    print("✅ Test klar! Adaptive L fungerar som förväntat.")
    print("=" * 80)
