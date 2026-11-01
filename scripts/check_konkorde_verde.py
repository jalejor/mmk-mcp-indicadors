#!/usr/bin/env python3
"""Empirical check of the Konkorde zero line (impulse-2.1.0, owner decision 3).

How often does `konkorde_verde` cross 0 versus `marron - media` (the 2.0.0
"edge") on the cached bitget BTC/USDT candles? OFFLINE: reads the OHLCV cache
JSON directly, never the exchange, never Mongo. Run in the lab:

    docker compose --profile backtest run --rm backtest \
        python scripts/check_konkorde_verde.py
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from controllers.metrics.impulse_backtest import rows_to_frame  # noqa: E402
from controllers.metrics.indicators_service import IndicatorsService  # noqa: E402


STOP_BELOW_CROSSES_4H = 10  # task gate: fewer verde zero crosses on 4h in 2 years = stop


def describe(series: pd.Series) -> dict:
    s = series.dropna()
    return {
        "min": round(float(s.min()), 2),
        "p05": round(float(s.quantile(0.05)), 2),
        "median": round(float(s.median()), 2),
        "p95": round(float(s.quantile(0.95)), 2),
        "max": round(float(s.max()), 2),
        "pct_below_0": round(float((s < 0).mean() * 100), 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="/data/ohlcv")
    ap.add_argument("--start", default="2024-11-01")
    ap.add_argument("--end", default="2026-11-01", help="exclusive")
    ap.add_argument("--timeframes", nargs="+", default=["4h", "1d"])
    ap.add_argument("--out", default="/data/results/konkorde_verde_check.md")
    args = ap.parse_args()

    start, end = pd.Timestamp(args.start, tz="UTC"), pd.Timestamp(args.end, tz="UTC")
    lines = [
        "# Konkorde zero-line check (impulse-2.1.0)",
        "",
        f"bitget BTC/USDT cache, window {args.start} -> {args.end} (exclusive), "
        "closed candles, `IndicatorsService(bbwp_definition='tv').calculate_all()` "
        "on the full cached history (warm-up included), counts inside the window only.",
        "",
        "| TF | bars | line | crosses up | crosses down | total | min | p05 | median | p95 | max | % bars < 0 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    summary = {}
    for tf in args.timeframes:
        meta = json.loads((Path(args.cache_dir) / f"bitget_BTC-USDT_{tf}.json").read_text())
        svc = IndicatorsService(rows_to_frame(meta["rows"]), bbwp_definition="tv")
        svc.calculate_all()
        df = svc.df
        win = (df.index >= start) & (df.index < end)
        series = {
            "verde": df["konkorde_verde"],
            "marron - media": df["konkorde_marron"] - df["konkorde_media"],
            "verde - media": df["konkorde_verde"] - df["konkorde_media"],
            "marron": df["konkorde_marron"],
        }
        for name, s in series.items():
            # Cross at bar j uses j-1, so compute on the full series then cut.
            prev = s.shift(1)
            sw, pw = s[win], prev[win]
            up = int(((pw <= 0) & (sw > 0)).sum())
            down = int(((pw >= 0) & (sw < 0)).sum())
            d = describe(sw)
            summary[f"{tf}|{name}"] = {"up": up, "down": down, **d}
            lines.append(
                f"| {tf} | {int(win.sum())} | `{name}` | {up} | {down} | {up + down} | {d['min']} | "
                f"{d['p05']} | {d['median']} | {d['p95']} | {d['max']} | {d['pct_below_0']} |"
            )
    v4 = summary.get("4h|verde")
    if v4 is not None:
        total = v4["up"] + v4["down"]
        ok = total >= STOP_BELOW_CROSSES_4H
        lines += [
            "",
            f"**Gate**: `verde` crosses 0 {total} times on 4h "
            f"(threshold {STOP_BELOW_CROSSES_4H}) -> {'OK, usable as the zero line' if ok else 'STOP: report, do not tune the formula'}. "
            f"Note the asymmetry: verde sits above 0 on {round(100 - v4['pct_below_0'], 1)}% of 4h bars "
            "(marron is 0-100 based, ~+55 when flat), so a zero cross is a deep weak-hands sell-off event, "
            "not a symmetric oscillator cross like `marron - media`.",
        ]
    lines += [
        "",
        "`verde - media` = the green area against the TV green line (`media`), the",
        "proposed `konkorde_turn_*` leader event; `marron` shown for reference (0-100 inputs).",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
    ]
    text = "\n".join(lines) + "\n"
    Path(args.out).write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
