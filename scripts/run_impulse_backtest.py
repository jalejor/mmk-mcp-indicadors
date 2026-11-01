#!/usr/bin/env python3
"""Impulsos-v2 backtest runner — legacy engine vs new impulse engine.

Executes `docs/PREREG_IMPULSOS_v2.md`. Always in Docker (lab service
`backtest`, see labs/mmk-signals/docker-compose.yml):

    flock /tmp/mmk-docker.lock docker compose --profile backtest run --rm backtest \
        python scripts/run_impulse_backtest.py --download
    ... python scripts/run_impulse_backtest.py --engine old --timeframes 1d 4h
    ... python scripts/run_impulse_backtest.py --engine new --profile pro

`--engine old` never imports the new engine, so it runs before it exists.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from controllers.metrics.impulse_backtest import (  # noqa: E402
    BLOCK_IS,
    BLOCK_OOS,
    load_ohlcv,
    run_legacy,
    run_new,
    buy_and_hold_pct,
    split_metrics,
    trade_dicts,
    verdict,
)

DEFAULT_SYMBOL = "BTC/USDT"
DEFAULT_EXCHANGE = "bitget"
DEFAULT_START = "2024-11-01"
DEFAULT_END = "2026-10-31"  # inclusive date -> exclusive 2026-11-01T00:00Z
DEFAULT_SPLIT = "2026-01-01"  # docs/impulsos-v2.md §g (IS 14 months / OOS 10 months)
DOWNLOAD_TFS = ["1M", "1w", "1d", "4h", "1h", "15m"]


def _date(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def _fmt(v: Any, nd: int = 3) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return "inf" if v == float("inf") else f"{v:.{nd}f}"
    return str(v)


def table_rows(label: str, metrics: Dict[str, Any]) -> List[str]:
    rows = []
    v = verdict(metrics)
    for block in ("all", BLOCK_IS, BLOCK_OOS):
        m = metrics[block]
        tag = f"{v['verdict']}" + (f" ({'; '.join(v['failed'])})" if v["failed"] else "") if block == "all" else ""
        if not m.get("n"):
            rows.append(f"| {label} | {block} | 0 | — | — | — | — | — | — | — | {tag} |")
            continue
        ci = m["bootstrap"]["ci95_cluster"]
        rows.append(
            f"| {label} | {block} | {m['n']} | {_fmt(m['expectancy_R'], 4)} | "
            f"[{ci[0]:.3f}, {ci[1]:.3f}] | {m['win_rate'] * 100:.1f}% | {_fmt(m['profit_factor'])} | "
            f"{_fmt(m['max_drawdown_R'])} | {_fmt(m['max_drawdown_pct'], 2)}% | "
            f"{_fmt(m['avg_cost_R'] + m['avg_funding_R'], 3)} | {tag} |"
        )
    return rows


TABLE_HEADER = [
    "| cell | split | n | expectancy R (net) | 95% CI (cluster, seed 42) | win rate | PF | max DD R | "
    "max DD % (1.5% risk) | avg cost+funding R | verdict §g |",
    "|---|---|---|---|---|---|---|---|---|---|---|",
]


def _profile_stops_by_tf() -> Dict[str, Any]:
    """trigger TF -> (profile, atr_mult_stop); empty if the new module is absent."""
    try:
        from controllers.metrics.trade_profiles import TRADE_PROFILES
    except ImportError:
        return {}
    return {cfg["trigger_tf"]: (name, float(cfg["atr_mult_stop"])) for name, cfg in TRADE_PROFILES.items()}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--engine", choices=["old", "new"], default="old")
    p.add_argument("--download", action="store_true", help="only fill the OHLCV cache")
    p.add_argument("--profile", default="pro", help="new engine trade profile")
    p.add_argument("--symbol", default=DEFAULT_SYMBOL)
    p.add_argument("--exchange", default=DEFAULT_EXCHANGE)
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=DEFAULT_END, help="inclusive date")
    p.add_argument("--split", default=DEFAULT_SPLIT)
    p.add_argument("--timeframes", nargs="+", default=None,
                   help="old engine: trigger TFs (default 1d 4h); download: TFs to cache")
    p.add_argument("--directions", nargs="+", default=["long", "short"], choices=["long", "short"])
    p.add_argument("--risk-profile", default="medium")
    p.add_argument("--cache-dir", default="/data/ohlcv")
    p.add_argument("--out-dir", default="/data/results")
    p.add_argument("--md-out", default=None, help="write the markdown table here")
    args = p.parse_args()

    start, split = _date(args.start), _date(args.split)
    end = _date(args.end) + timedelta(days=1)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Dict[str, Any]] = {}

    def loader(tf: str):
        t0 = time.time()
        df, info = load_ohlcv(args.symbol, tf, start, end, exchange=args.exchange,
                              cache_dir=args.cache_dir)
        manifest[tf] = {**info.__dict__, "seconds": round(time.time() - t0, 1)}
        print(f"[data] {tf}: {info.rows} rows {info.first_open} -> {info.last_open} "
              f"gaps={info.gaps} sha={info.sha256[:12]} ({info.source})", flush=True)
        return df

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.download:
        for tf in args.timeframes or DOWNLOAD_TFS:
            try:
                loader(tf)
            except Exception as exc:  # report and continue with the next TF
                print(f"[data] {tf}: FAILED {exc}", flush=True)
        (out_dir / f"manifest_{stamp}.json").write_text(json.dumps(manifest, indent=2))
        return 0

    cells: Dict[str, Any] = {}
    md: List[str] = []
    if args.engine == "old":
        stops = _profile_stops_by_tf()
        for tf in args.timeframes or ["1d", "4h"]:
            df = loader(tf)
            cells[f"buy_and_hold|{tf}"] = buy_and_hold_pct(df, start, end)
            # (label suffix, atr_stop_multiplier): the original medium 1.5/3R,
            # plus the same engine at the cell profile's stop (spec §f) if it differs.
            variants = [("medium 1.5/3R", None)]
            if tf in stops and stops[tf][1] != 1.5:
                variants.append((f"@{stops[tf][0]} stop {stops[tf][1]}/3R", stops[tf][1]))
            for suffix, mult in variants:
                for side in args.directions:
                    t0 = time.time()
                    trades = run_legacy(df, symbol=args.symbol, timeframe=tf, start=start, end=end,
                                        split=split, side=side, risk_profile=args.risk_profile,
                                        atr_stop_multiplier=mult)
                    key = f"legacy|{tf}|{suffix}|{side}"
                    metrics = split_metrics(trades)
                    cells[key] = {"metrics": metrics, "verdict": verdict(metrics),
                                  "trades": trade_dicts(trades), "seconds": round(time.time() - t0, 1)}
                    print(f"[legacy] {key}: {len(trades)} trades in {cells[key]['seconds']}s", flush=True)
                    label = f"legacy {tf} {suffix} {side}"
                    if side == "short":
                        label += " (native side=short path, INFORMATIONAL; §g headline = N/A)"
                    md.extend(table_rows(label, metrics))
    else:
        res = run_new(profile=args.profile, symbol=args.symbol, start=start, end=end, split=split,
                      directions=args.directions, loader=loader)
        tf = res["timeframes"]["trigger"]
        for side in args.directions:
            trades = [t for t in res["trades"] if t.side == side]
            key = f"new|{args.profile}|{tf}|{side}"
            metrics = split_metrics(trades)
            cells[key] = {"metrics": metrics, "verdict": verdict(metrics), "trades": trade_dicts(trades)}
            md.extend(table_rows(f"new {args.profile} {tf} {side}", metrics))
        cells["_engine"] = {k: v for k, v in res.items() if k != "trades"}

    report = {
        "engine": args.engine,
        "profile": args.profile if args.engine == "new" else f"legacy-{args.risk_profile}",
        "symbol": args.symbol,
        "exchange": args.exchange,
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "split": split.isoformat(),
        "cost_model": "fee0.001+slip0.0005_per_side|cost_R=(fee+slip)*(entry+exit)/stop_distance",
        "stop_model": "atr14 x atr_mult_stop, stop-first intrabar, entry at signal close",
        "manifest": manifest,
        "cells": cells,
    }
    name = f"{args.engine}_{args.profile if args.engine == 'new' else 'legacy'}_{stamp}.json"
    (out_dir / name).write_text(json.dumps(report, indent=2, default=str))
    table = "\n".join(TABLE_HEADER + md)
    print(table)
    if args.md_out:
        Path(args.md_out).write_text(table + "\n")
    print(f"[out] {out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
