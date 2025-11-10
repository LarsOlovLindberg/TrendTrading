import argparse
import csv
import os
import time
from datetime import datetime
from statistics import mean, quantiles
from typing import Any, Dict, Iterable, List, Optional

import requests

BINANCE_REST = "https://api.binance.com"


def _to_epoch_ms(dt: Optional[str]) -> Optional[int]:
    if not dt:
        return None
    try:
        parsed = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit(f"Kan inte tolka tidstämpel: {dt}") from None
    return int(parsed.timestamp() * 1000)


def fetch_klines(
    symbol: str,
    interval: str,
    max_candles: int,
    start_time: Optional[int],
    end_time: Optional[int],
) -> List[Dict[str, Any]]:
    remaining = max_candles
    klines: List[Dict[str, Any]] = []
    current_start = start_time
    session = requests.Session()
    while remaining > 0:
        limit = min(1000, remaining)
        params: Dict[str, Any] = {"symbol": symbol, "interval": interval, "limit": limit}
        if current_start is not None:
            params["startTime"] = current_start
        if end_time is not None:
            params["endTime"] = end_time
        resp = session.get(f"{BINANCE_REST}/api/v3/klines", params=params, timeout=10)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for raw in batch:
            kline = {
                "open_time": int(raw[0]),
                "open": float(raw[1]),
                "high": float(raw[2]),
                "low": float(raw[3]),
                "close": float(raw[4]),
                "volume": float(raw[5]),
                "close_time": int(raw[6]),
            }
            klines.append(kline)
        remaining -= len(batch)
        if len(batch) < limit:
            break
        current_start = int(batch[-1][6]) + 1
        time.sleep(0.2)
    return klines


def _quartiles(values: List[float]) -> List[float]:
    if not values:
        return [0.0, 0.0, 0.0]
    sorted_vals = sorted(values)
    while len(sorted_vals) < 4:
        sorted_vals.append(sorted_vals[-1])
    return quantiles(sorted_vals, n=4, method="inclusive")


def compute_forward_extremes(
    klines: List[Dict[str, Any]],
    lookahead: int,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    total = len(klines)
    for idx, kline in enumerate(klines):
        end_idx = min(total, idx + lookahead + 1)
        if end_idx <= idx + 1:
            continue
        future_slice = klines[idx + 1 : end_idx]
        if not future_slice:
            continue
        max_future = max(c["high"] for c in future_slice)
        min_future = min(c["low"] for c in future_slice)
        entry = kline["close"]
        mfe = max(0.0, max_future - entry)
        mae = max(0.0, entry - min_future)
        denom = entry if entry != 0 else 1.0
        results.append(
            {
                "open_time": kline["open_time"],
                "close": entry,
                "max_future": max_future,
                "min_future": min_future,
                "mfe_pct": mfe / denom,
                "mae_pct": mae / denom,
                "direction": "down" if kline["close"] < kline["open"] else "up",
            }
        )
    return results


def build_stats(
    rows: Iterable[Dict[str, Any]],
    loss_threshold: float,
) -> Dict[str, Any]:
    all_rows = list(rows)
    if not all_rows:
        return {"count": 0}
    mae_hits = [r for r in all_rows if r["mae_pct"] >= loss_threshold]
    mfe_vals = [r["mfe_pct"] for r in all_rows]
    mae_vals = [r["mae_pct"] for r in all_rows]
    stats: Dict[str, Any] = {
        "count": len(all_rows),
        "loss_hits": len(mae_hits),
        "loss_hit_ratio": len(mae_hits) / len(all_rows),
        "mfe_mean": mean(mfe_vals),
        "mae_mean": mean(mae_vals),
        "mfe_quantiles": _quartiles(mfe_vals),
        "mae_quantiles": _quartiles(mae_vals),
    }
    if mae_hits:
        after_loss = [r for r in mae_hits]
        stats["loss_mfe_mean"] = mean(r["mfe_pct"] for r in after_loss)
        stats["loss_mae_mean"] = mean(r["mae_pct"] for r in after_loss)
        stats["loss_mfe_quantiles"] = _quartiles([r["mfe_pct"] for r in after_loss])
        stats["loss_mae_quantiles"] = _quartiles([r["mae_pct"] for r in after_loss])
    return stats


def save_csv(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    rows = list(rows)
    if not rows:
        return
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as wf:
        writer = csv.DictWriter(wf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def fmt_pct(value: float) -> str:
    return f"{value * 100:.4f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analysera historiska Binance-klines för forward MFE/MAE.")
    parser.add_argument("symbol", nargs="?", default="BTCUSDT")
    parser.add_argument("interval", nargs="?", default="1m")
    parser.add_argument("lookahead", nargs="?", type=int, default=20)
    parser.add_argument("--max-candles", type=int, default=2000)
    parser.add_argument("--start", help="ISO8601 starttid, ex 2024-01-01T00:00:00Z")
    parser.add_argument("--end", help="ISO8601 sluttid")
    parser.add_argument("--loss-threshold", type=float, default=0.001, help="MAE-gräns (proportion) för att räknas som förlust")
    parser.add_argument("--csv", help="Spara rad-detaljer till CSV. Vid multipla lookahead, inkludera valfritt '{lookahead}' i filnamnet")
    parser.add_argument(
        "--lookahead-set",
        type=int,
        nargs="+",
        help="Anger en lista med lookahead-värden (överskriver positionella lookahead om satt)",
    )
    args = parser.parse_args()

    start_ms = _to_epoch_ms(args.start)
    end_ms = _to_epoch_ms(args.end)
    print(f"⬇️  Hämtar {args.max_candles} klines för {args.symbol} @ {args.interval}...")
    klines = fetch_klines(args.symbol, args.interval, args.max_candles, start_ms, end_ms)
    if not klines:
        print("Inga klines hämtade.")
        return
    print(f"✅ Hämtade {len(klines)} klines.")

    lookahead_values = args.lookahead_set if args.lookahead_set else [args.lookahead]

    def describe(label: str, stats: Dict[str, Any], lookahead: int) -> None:
        if not stats.get("count"):
            print(f"{label}: inga datapunkter")
            return
        loss_ratio = stats.get("loss_hit_ratio", 0.0)
        print(f"\n📊 {label} (lookahead={lookahead} candles)")
        print(f"  Antal: {stats['count']}")
        print(f"  Förlustträffar ≥ {fmt_pct(args.loss_threshold)}: {stats.get('loss_hits', 0)} ({fmt_pct(loss_ratio)})")
        print(f"  MFE medel: {fmt_pct(stats['mfe_mean'])} | MAE medel: {fmt_pct(stats['mae_mean'])}")
        q_mfe = stats['mfe_quantiles']
        q_mae = stats['mae_quantiles']
        print(f"  MFE kvartiler: {fmt_pct(q_mfe[0])} | {fmt_pct(q_mfe[1])} | {fmt_pct(q_mfe[2])}")
        print(f"  MAE kvartiler: {fmt_pct(q_mae[0])} | {fmt_pct(q_mae[1])} | {fmt_pct(q_mae[2])}")
        if 'loss_mfe_mean' in stats:
            print(f"  Efter förlust (>= threshold) MFE medel: {fmt_pct(stats['loss_mfe_mean'])}")
            print(f"  Efter förlust MAE medel: {fmt_pct(stats['loss_mae_mean'])}")

    for lookahead in lookahead_values:
        rows = compute_forward_extremes(klines, lookahead)
        if args.csv:
            if len(lookahead_values) == 1:
                csv_path = args.csv
            elif "{lookahead}" in args.csv:
                csv_path = args.csv.format(lookahead=lookahead)
            else:
                root, ext = os.path.splitext(args.csv)
                csv_path = f"{root}_L{lookahead}{ext or '.csv'}"
            save_csv(csv_path, rows)
            print(f"💾 Sparade rad-data till {csv_path}")

        stats_all = build_stats(rows, args.loss_threshold)
        stats_down = build_stats((r for r in rows if r["direction"] == "down"), args.loss_threshold)
        stats_up = build_stats((r for r in rows if r["direction"] == "up"), args.loss_threshold)

        describe("Totalt", stats_all, lookahead)
        describe("Ned-candles", stats_down, lookahead)
        describe("Upp-candles", stats_up, lookahead)


if __name__ == "__main__":
    main()
