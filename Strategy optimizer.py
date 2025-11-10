# -*- coding: utf-8 -*-
"""
Strategy Optimizer - Systematisk Parameteroptimering
----------------------------------------------------
Detta verktyg testar systematiskt olika kombinationer av strategi-parametrar
för att hitta den bästa konfigurationen.

Använder historisk data (eller live paper trading) för att mäta:
- Total PnL
- Win Rate
- Sharpe Ratio
- Max Drawdown
- Antal trades
- Genomsnittlig trade-duration

Kör:
    python strategy_optimizer.py
"""

import json
import csv
import itertools
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

@dataclass
class TradeResult:
    """Resultat från en enskild trade"""
    entry_time: str
    exit_time: str
    side: str  # "LONG" / "SHORT"
    entry_price: Decimal
    exit_price: Decimal
    qty: Decimal
    pnl_pct: float
    pnl_usd: float
    exit_reason: str  # "TP" / "BE" / "SL" / "TRAILING"
    duration_sec: float

@dataclass
class StrategyMetrics:
    """Prestanda-metrics för en strategi-konfiguration"""
    # Parametrar som testades
    params: Dict[str, Any]
    
    # Resultat
    total_trades: int
    long_trades: int
    short_trades: int
    
    wins: int
    losses: int
    win_rate: float
    
    total_pnl_usd: float
    total_pnl_pct: float
    avg_win: float
    avg_loss: float
    
    largest_win: float
    largest_loss: float
    
    max_drawdown_pct: float
    max_drawdown_usd: float
    
    sharpe_ratio: float
    profit_factor: float
    
    avg_trade_duration_sec: float
    
    start_capital: float
    end_capital: float
    roi_pct: float

class PerformanceTracker:
    """Spårar prestanda under backtest/live trading"""
    
    def __init__(self, start_capital: float):
        self.start_capital = start_capital
        self.current_capital = start_capital
        self.peak_capital = start_capital
        
        self.trades: List[TradeResult] = []
        self.equity_curve: List[float] = [start_capital]
        
    def add_trade(self, trade: TradeResult):
        """Lägg till en trade och uppdatera metrics"""
        self.trades.append(trade)
        
        # Uppdatera kapital
        self.current_capital += trade.pnl_usd
        self.equity_curve.append(self.current_capital)
        
        # Uppdatera peak för drawdown-beräkning
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
    
    def calculate_metrics(self, params: Dict[str, Any]) -> StrategyMetrics:
        """Beräkna alla performance metrics"""
        if not self.trades:
            return StrategyMetrics(
                params=params,
                total_trades=0, long_trades=0, short_trades=0,
                wins=0, losses=0, win_rate=0.0,
                total_pnl_usd=0.0, total_pnl_pct=0.0,
                avg_win=0.0, avg_loss=0.0,
                largest_win=0.0, largest_loss=0.0,
                max_drawdown_pct=0.0, max_drawdown_usd=0.0,
                sharpe_ratio=0.0, profit_factor=0.0,
                avg_trade_duration_sec=0.0,
                start_capital=self.start_capital,
                end_capital=self.current_capital,
                roi_pct=0.0
            )
        
        # Grundläggande counts
        total_trades = len(self.trades)
        long_trades = sum(1 for t in self.trades if t.side == "LONG")
        short_trades = sum(1 for t in self.trades if t.side == "SHORT")
        
        # Wins/Losses
        wins = sum(1 for t in self.trades if t.pnl_usd > 0)
        losses = sum(1 for t in self.trades if t.pnl_usd <= 0)
        win_rate = wins / total_trades if total_trades > 0 else 0.0
        
        # PnL
        total_pnl_usd = sum(t.pnl_usd for t in self.trades)
        total_pnl_pct = (self.current_capital / self.start_capital - 1) * 100
        
        winning_trades = [t for t in self.trades if t.pnl_usd > 0]
        losing_trades = [t for t in self.trades if t.pnl_usd <= 0]
        
        avg_win = sum(t.pnl_usd for t in winning_trades) / len(winning_trades) if winning_trades else 0.0
        avg_loss = sum(t.pnl_usd for t in losing_trades) / len(losing_trades) if losing_trades else 0.0
        
        largest_win = max((t.pnl_usd for t in self.trades), default=0.0)
        largest_loss = min((t.pnl_usd for t in self.trades), default=0.0)
        
        # Max Drawdown
        max_dd_usd = 0.0
        peak = self.start_capital
        for capital in self.equity_curve:
            if capital > peak:
                peak = capital
            dd = peak - capital
            if dd > max_dd_usd:
                max_dd_usd = dd
        
        max_dd_pct = (max_dd_usd / self.peak_capital * 100) if self.peak_capital > 0 else 0.0
        
        # Sharpe Ratio (simplified - använder trade returns)
        returns = [t.pnl_pct for t in self.trades]
        if len(returns) > 1:
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)) ** 0.5
            sharpe_ratio = (avg_return / std_return * (252 ** 0.5)) if std_return > 0 else 0.0
        else:
            sharpe_ratio = 0.0
        
        # Profit Factor
        total_wins = sum(t.pnl_usd for t in winning_trades)
        total_losses = abs(sum(t.pnl_usd for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Avg trade duration
        avg_duration = sum(t.duration_sec for t in self.trades) / len(self.trades)
        
        # ROI
        roi_pct = ((self.current_capital - self.start_capital) / self.start_capital) * 100
        
        return StrategyMetrics(
            params=params,
            total_trades=total_trades,
            long_trades=long_trades,
            short_trades=short_trades,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            total_pnl_usd=total_pnl_usd,
            total_pnl_pct=total_pnl_pct,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_usd=max_dd_usd,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            avg_trade_duration_sec=avg_duration,
            start_capital=self.start_capital,
            end_capital=self.current_capital,
            roi_pct=roi_pct
        )

class StrategyOptimizer:
    """Grid Search för strategi-parametrar"""
    
    def __init__(self, base_config_path: str):
        with open(base_config_path, 'r', encoding='utf-8-sig') as f:
            self.base_config = json.load(f)
    
    def grid_search(self, param_grid: Dict[str, List[Any]]) -> List[StrategyMetrics]:
        """
        Grid search över alla kombinationer av parametrar.
        
        param_grid exempel:
        {
            'tp_pct': [0.0005, 0.001, 0.0015, 0.002],
            'sl_pct': [None, 0.001, 0.002],
            'trailing_stop': [False, True]
        }
        """
        # Generera alla kombinationer
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        
        all_combinations = list(itertools.product(*param_values))
        total_tests = len(all_combinations)
        
        print(f"🔍 Grid Search: {total_tests} kombinationer att testa")
        print(f"📊 Parametrar: {param_names}\n")
        
        results = []
        
        for idx, combination in enumerate(all_combinations, 1):
            # Skapa config för denna kombination
            test_config = self.base_config.copy()
            test_params = dict(zip(param_names, combination))
            test_config.update(test_params)
            
            print(f"Test {idx}/{total_tests}: {test_params}")
            
            # Kör backtest med denna config
            metrics = self._run_backtest(test_config, test_params)
            results.append(metrics)
            
            print(f"  → Trades: {metrics.total_trades}, Win Rate: {metrics.win_rate:.1%}, "
                  f"PnL: ${metrics.total_pnl_usd:.2f}, Sharpe: {metrics.sharpe_ratio:.2f}\n")
        
        return results
    
    def _run_backtest(self, config: Dict, params: Dict) -> StrategyMetrics:
        """
        Kör backtest med given config.
        OBS: Detta är en placeholder - du måste implementera din egen backtest-logik
        eller integrera med live paper trading.
        """
        # TODO: Implementera faktisk backtest här
        # För nu returnerar vi mock data
        
        tracker = PerformanceTracker(start_capital=10000)
        
        # Mock: simulera några trades
        import random
        for _ in range(50):
            trade = TradeResult(
                entry_time=datetime.now(timezone.utc).isoformat(),
                exit_time=datetime.now(timezone.utc).isoformat(),
                side=random.choice(["LONG", "SHORT"]),
                entry_price=Decimal("103000"),
                exit_price=Decimal("103100"),
                qty=Decimal("0.001"),
                pnl_pct=random.uniform(-0.002, 0.003),
                pnl_usd=random.uniform(-2, 3),
                exit_reason=random.choice(["TP", "BE", "SL"]),
                duration_sec=random.uniform(30, 600)
            )
            tracker.add_trade(trade)
        
        return tracker.calculate_metrics(params)
    
    def save_results(self, results: List[StrategyMetrics], output_path: str):
        """Spara resultat till CSV"""
        if not results:
            print("Inga resultat att spara")
            return
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            # Få alla fält från första resultatet
            first_result = results[0]
            fieldnames = list(asdict(first_result).keys())
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                row = asdict(result)
                # Konvertera params dict till string
                row['params'] = json.dumps(row['params'])
                writer.writerow(row)
        
        print(f"✅ Resultat sparade i: {output_path}")
    
    def print_top_results(self, results: List[StrategyMetrics], top_n: int = 10, 
                         sort_by: str = 'sharpe_ratio'):
        """Visa de bästa resultaten"""
        sorted_results = sorted(results, key=lambda x: getattr(x, sort_by), reverse=True)
        
        print(f"\n🏆 TOP {top_n} RESULTAT (sorterat efter {sort_by}):\n")
        print(f"{'Rank':<6} {'Params':<50} {sort_by:<15} {'Win%':<8} {'PnL$':<10} {'Trades':<8}")
        print("-" * 100)
        
        for idx, result in enumerate(sorted_results[:top_n], 1):
            params_str = json.dumps(result.params)[:47] + "..."
            print(f"{idx:<6} {params_str:<50} {getattr(result, sort_by):<15.2f} "
                  f"{result.win_rate*100:<8.1f} ${result.total_pnl_usd:<10.2f} {result.total_trades:<8}")

def main():
    """Exempel på hur man använder optimizern"""
    
    # Skapa optimizer
    optimizer = StrategyOptimizer('config_advanced.json')
    
    # Definiera parametrar att testa
    param_grid = {
        'tp_pct': [0.0005, 0.001, 0.0015, 0.002, 0.003],
        'sl_pct': [None, 0.0005, 0.001, 0.002],
        'trailing_stop': [False, True],
        'min_movement_pct': [0.00005, 0.0001, 0.0002]
    }
    
    # Kör grid search
    results = optimizer.grid_search(param_grid)
    
    # Visa resultat
    optimizer.print_top_results(results, top_n=10, sort_by='sharpe_ratio')
    optimizer.print_top_results(results, top_n=10, sort_by='total_pnl_usd')
    optimizer.print_top_results(results, top_n=10, sort_by='win_rate')
    
    # Spara resultat
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"optimization_results_{timestamp}.csv"
    optimizer.save_results(results, output_path)
    
    print(f"\n✅ Optimering klar! Se {output_path} för fullständiga resultat.")

if __name__ == "__main__":
    main()