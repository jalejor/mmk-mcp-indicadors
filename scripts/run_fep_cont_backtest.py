#!/usr/bin/env python3
"""R-FEP-CONT v0.3.0 study runner — executes `docs/PREREG_FEP_CONT_v0.3.0.md`.

Runs the four pre-registered arms (FEP-CONT / CONFIRMED / BASE-RATE /
WHIPSAW) over the 4 majors x 4 timeframes, resolves every entry with the
committed outcome resolver, and evaluates the frozen gate (L1..L5) on the
primary cell only. Always in Docker (never install deps on the host):

    docker build -f Dockerfile.test -t mmk-test .
    docker run --rm -v "$(pwd)":/app -w /app mmk-test \
        python scripts/run_fep_cont_backtest.py --json-out /app/fep_cont_v030.json

Smoke run (pipeline check, NOT the study):

    ... python scripts/run_fep_cont_backtest.py --symbols BTC/USDT \
        --timeframes 1d --start 2022-01-01 --json-out /tmp/smoke.json

Nothing in this script may drift from the pre-registration. Parameters that
the pre-registration froze are defaults here and are echoed into the report.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Cosmetic only: pandas-ta floods the log with an mfi dtype FutureWarning.
warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from controllers.metrics.fep_cont_backtest import (  # noqa: E402
    ARM_BASE_RATE,
    ARM_FEP_CONT,
    ARMS,
    BOOTSTRAP_RESAMPLES,
    BOOTSTRAP_SEED,
    ENTRY_MODE_CLOSE,
    ENTRY_MODE_NEXT_OPEN,
    FepContBacktest,
    FepSignal,
    cluster_bootstrap_ci,
    cluster_bootstrap_difference,
    holm_adjust,
    metrics_block,
    portfolio_block,
    signal_dicts,
    welch_p_one_sided,
)

# ---- Pre-registered constants (§5, §8). Do not edit without an AMENDMENT.
PREREG_COMMIT = "0154a40f3d1a3c4577f9ddeccfaf4faee837e478"
PRIMARY_TIMEFRAME = "1h"
DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
DEFAULT_TIMEFRAMES = ["30m", "1h", "4h", "1d"]
DEFAULT_START = "2018-07-01"
DEFAULT_END = "2026-07-01"
IS_BOUNDARY = "2024-02-05T09:36:00"  # the liston's own in_sample_end

# §8 gate thresholds — taken from scripts/run_f0_backtest.py GATE_THRESHOLDS
# and the liston, never re-derived from this sample.
GATE = {
    "L1_expectancy_min_R": 0.15,
    "L2_r_per_year_min": 1.644,          # PB-1D pooled 8y annualised
    "L2_strong_r_per_year_min": 4.421,   # PB-1D same-window OOS annualised
    "L3_edge_over_control_min_R": 0.15,
    "L4_n_oos_min": 30,
    "L5_oos_vs_is_ratio_min": 0.5,
    "L5_symbols_with_sign_min": 3,
}
LISTON = {
    "source": "f0_gate_pb_majors_binance.json",
    "full_8y": {"n": 21, "expectancy_R": 0.6262, "win_rate": 0.429, "profit_factor": 2.054,
                "total_R": 13.15, "R_per_year": 1.644},
    "in_sample": {"n": 13, "expectancy_R": 0.1959, "total_R": 2.55, "R_per_year": 0.455},
    "out_of_sample": {"n": 8, "expectancy_R": 1.3255, "win_rate": 0.625, "profit_factor": 4.312,
                      "total_R": 10.60, "R_per_year": 4.421},
}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="R-FEP-CONT v0.3.0 pre-registered study")
    p.add_argument("--symbols", nargs="+", default=DEFAULT_SYMBOLS)
    p.add_argument("--timeframes", nargs="+", default=DEFAULT_TIMEFRAMES)
    p.add_argument("--exchange", default="binance")
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=DEFAULT_END)
    p.add_argument("--is-boundary", default=IS_BOUNDARY)
    p.add_argument("--cache-dir", default="", help="raw OHLCV cache (csv), avoids refetching")
    p.add_argument("--json-out", required=True)
    p.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES)
    p.add_argument("--no-sensitivities", action="store_true")
    p.add_argument("--trades-out", default="", help="optional full signal dump (jsonl)")
    p.add_argument("--shard-out", default="",
                   help="write this shard's signals+manifest as jsonl (parallel execution)")
    p.add_argument("--aggregate-from", nargs="*", default=[],
                   help="pool these shard files instead of running the backtest")
    return p.parse_args()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def _load_raw(args: argparse.Namespace, symbol: str, timeframe: str, engine: FepContBacktest):
    import pandas as pd

    cache_path: Optional[Path] = None
    if args.cache_dir:
        key = f"{args.exchange}_{symbol.replace('/', '')}_{timeframe}_{args.start}_{args.end}.csv"
        cache_path = Path(args.cache_dir) / key
        if cache_path.exists():
            df = pd.read_csv(cache_path, parse_dates=["datetime"], index_col="datetime")
            df.index = pd.to_datetime(df.index, utc=True)
            return df
    raw = FepContBacktest.fetch_ohlcv(
        symbol=symbol,
        timeframe=timeframe,
        start=engine.start - engine._warmup_delta(),
        end=engine.end,
        exchange=args.exchange,
    )
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        raw.to_csv(cache_path, index_label="datetime")
    return raw


def _years(a: datetime, b: datetime) -> float:
    return (b - a).days / 365.25


def _split(signals: List[FepSignal], arm: str, block: Optional[str] = None) -> List[FepSignal]:
    return [s for s in signals if s.arm == arm and (block is None or s.block == block)]


def _cell_report(signals: List[FepSignal], *, is_years: float, oos_years: float,
                 resamples: int) -> Dict[str, Any]:
    """Every arm x every block, per-signal and portfolio basis."""
    out: Dict[str, Any] = {}
    for arm in ARMS:
        arm_out: Dict[str, Any] = {}
        for block, years in (("in_sample", is_years), ("out_of_sample", oos_years), ("full", is_years + oos_years)):
            subset = _split(signals, arm, None if block == "full" else block)
            arm_out[block] = {
                "per_signal": metrics_block(subset),
                "portfolio": portfolio_block(subset, years=years),
            }
            if subset:
                arm_out[block]["bootstrap"] = cluster_bootstrap_ci(subset, resamples=resamples)
        # Edge over the control group, per block (re-council blocker #1).
        if arm != ARM_BASE_RATE:
            arm_out["edge_vs_control"] = {
                block: cluster_bootstrap_difference(
                    _split(signals, arm, block), _split(signals, ARM_BASE_RATE, block),
                    resamples=resamples,
                )
                for block in ("in_sample", "out_of_sample")
            }
            arm_out["welch_p_vs_control_oos"] = welch_p_one_sided(
                [s.r_net for s in _split(signals, arm, "out_of_sample")],
                [s.r_net for s in _split(signals, ARM_BASE_RATE, "out_of_sample")],
            )
        # §6 S4: per symbol and per side.
        arm_out["by_symbol_oos"] = {
            sym: metrics_block([s for s in _split(signals, arm, "out_of_sample") if s.symbol == sym])
            for sym in sorted({s.symbol for s in signals})
        }
        arm_out["by_side_oos"] = {
            side: metrics_block([s for s in _split(signals, arm, "out_of_sample") if s.side == side])
            for side in ("long", "short")
        }
        out[arm] = arm_out
    return out


def _evaluate_gate(cell: Dict[str, Any]) -> Dict[str, Any]:
    """The frozen §8 gate, on the PRIMARY cell only."""
    a = cell[ARM_FEP_CONT]
    oos = a["out_of_sample"]
    is_ = a["in_sample"]
    exp_oos = oos["per_signal"].get("expectancy_R")
    exp_is = is_["per_signal"].get("expectancy_R")
    n_oos = oos["per_signal"].get("n", 0)
    ci = oos.get("bootstrap", {}).get("ci95_cluster", [None, None])
    rpy = oos["portfolio"].get("R_per_year", 0.0)
    edge = a.get("edge_vs_control", {}).get("out_of_sample", {})
    edge_r = edge.get("difference_R")
    edge_ci = edge.get("ci95_cluster", [None, None])
    by_sym = a.get("by_symbol_oos", {})
    signs = sum(
        1 for m in by_sym.values()
        if m.get("n", 0) > 0 and (m.get("expectancy_R", 0) > 0) == ((exp_oos or 0) > 0)
    )

    legs = {
        "L1_quality": {
            "requirement": ">= +0.15 R OOS and cluster-CI lower bound > 0",
            "expectancy_R": exp_oos, "ci95_cluster": ci,
            "pass": bool(exp_oos is not None and exp_oos >= GATE["L1_expectancy_min_R"]
                         and ci[0] is not None and ci[0] > 0),
        },
        "L2_economics": {
            "requirement": f">= {GATE['L2_r_per_year_min']} R/yr (portfolio basis)",
            "R_per_year": rpy,
            "pass": bool(rpy >= GATE["L2_r_per_year_min"]),
            "L2_strong": bool(rpy >= GATE["L2_strong_r_per_year_min"]),
        },
        "L3_control": {
            "requirement": ">= +0.15 R over BASE-RATE, cluster-CI lower bound > 0",
            "difference_R": edge_r, "ci95_cluster": edge_ci,
            "pass": bool(edge_r is not None and edge_r >= GATE["L3_edge_over_control_min_R"]
                         and edge_ci[0] is not None and edge_ci[0] > 0),
        },
        "L4_sample": {
            "requirement": f"n >= {GATE['L4_n_oos_min']} OOS signals",
            "n_oos": n_oos, "pass": bool(n_oos >= GATE["L4_n_oos_min"]),
        },
        "L5_stability": {
            "requirement": "IS > 0, OOS >= 0.5 x IS, sign holds in >= 3 of 4 symbols",
            "expectancy_is_R": exp_is, "expectancy_oos_R": exp_oos,
            "symbols_with_matching_sign": signs,
            "pass": bool(
                exp_is is not None and exp_is > 0
                and exp_oos is not None and exp_oos >= GATE["L5_oos_vs_is_ratio_min"] * exp_is
                and signs >= GATE["L5_symbols_with_sign_min"]
            ),
        },
    }
    verdict = "PASS" if all(leg["pass"] for leg in legs.values()) else "NO PASS"
    return {
        "cell": f"{ARM_FEP_CONT} | {PRIMARY_TIMEFRAME} | 4 majors pooled | out_of_sample",
        "legs": legs,
        "verdict": verdict,
        "consequence": (
            "PASS -> write a shadow-window proposal for an mmk-council (the council decides)."
            if verdict == "PASS"
            else "NO PASS -> archive the FEC/FEP family per the 2026-08-16 stopping rule; no v0.4.0."
        ),
    }


def _dump_shard(path: str, manifest: List[Dict[str, Any]],
                primary: Dict[str, List[FepSignal]],
                sens: Dict[str, Dict[str, List[FepSignal]]]) -> None:
    """One shard = signals + manifest, as jsonl. Sharding is an EXECUTION
    detail: the pooled report is byte-identical to a single-process run
    (asserted by --self-check on a fast cell)."""
    with open(path, "w") as fh:
        for entry in manifest:
            fh.write(json.dumps({"_manifest": entry}, default=str) + "\n")
        for _tf, sigs in primary.items():
            for row in signal_dicts(sigs):
                fh.write(json.dumps({"variant": "primary", **row}, default=str) + "\n")
        for name, per_tf in sens.items():
            for _tf, sigs in per_tf.items():
                for row in signal_dicts(sigs):
                    fh.write(json.dumps({"variant": name, **row}, default=str) + "\n")


def _load_shards(paths: List[str]):
    """Rebuild pooled signals + manifest from shard files."""
    from controllers.metrics.fep_cont_backtest import FepSignal as _FS

    manifest: List[Dict[str, Any]] = []
    primary: Dict[str, List[FepSignal]] = {}
    sens: Dict[str, Dict[str, List[FepSignal]]] = {}
    fields = set(_FS.__dataclass_fields__)
    for path in paths:
        with open(path) as fh:
            for line in fh:
                row = json.loads(line)
                if "_manifest" in row:
                    manifest.append(row["_manifest"])
                    continue
                variant = row.pop("variant")
                sig = _FS(**{k: v for k, v in row.items() if k in fields})
                if variant == "primary":
                    primary.setdefault(sig.timeframe, []).append(sig)
                else:
                    sens.setdefault(variant, {}).setdefault(sig.timeframe, []).append(sig)
    return manifest, primary, sens


def main() -> int:
    args = _parse_args()
    start, end, boundary = _dt(args.start), _dt(args.end), _dt(args.is_boundary)
    is_years, oos_years = _years(start, boundary), _years(boundary, end)

    report: Dict[str, Any] = {
        "study": "R-FEP-CONT v0.3.0",
        "preregistration": {
            "document": "docs/PREREG_FEP_CONT_v0.3.0.md",
            "commit": PREREG_COMMIT,
            "primary_cell": f"{ARM_FEP_CONT} | {PRIMARY_TIMEFRAME} | 4 majors pooled | OOS",
        },
        "run": {
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "symbols": args.symbols, "timeframes": args.timeframes,
            "exchange": args.exchange,
            "period": {"start": start.isoformat(), "end": end.isoformat(),
                       "in_sample_end": boundary.isoformat(),
                       "in_sample_years": round(is_years, 2), "oos_years": round(oos_years, 2)},
            "bootstrap": {"resamples": args.resamples, "seed": BOOTSTRAP_SEED,
                          "cluster": "(symbol, calendar month)"},
        },
        "liston_PB_1D": LISTON,
        "gate_thresholds": GATE,
        "manifest": [],
        "cells": {},
        "sensitivities": {},
    }

    all_signals: Dict[str, List[FepSignal]] = {tf: [] for tf in args.timeframes}
    sens_signals: Dict[str, Dict[str, List[FepSignal]]] = {}

    if args.aggregate_from:
        report["manifest"], loaded, sens_signals = _load_shards(args.aggregate_from)
        report["run"]["sharded"] = args.aggregate_from
        # Only the cells the shards actually carry — never the CLI defaults,
        # or an empty primary cell would be scored as a failing gate.
        all_signals = {tf: sigs for tf, sigs in loaded.items() if sigs}
        args.timeframes = list(all_signals)
        report["run"]["timeframes"] = args.timeframes
        report["run"]["symbols"] = sorted({s.symbol for sigs in all_signals.values() for s in sigs})

    for timeframe in ([] if args.aggregate_from else args.timeframes):
        for symbol in args.symbols:
            t0 = time.time()
            engine = FepContBacktest(
                symbol=symbol, timeframe=timeframe, start=start, end=end,
                is_boundary=boundary, exchange=args.exchange,
            )
            raw = _load_raw(args, symbol, timeframe, engine)
            enriched = engine.load_frame(raw)
            events = engine.detect_events(enriched)
            signals = engine.collect(enriched, events=events)
            all_signals[timeframe].extend(signals)
            manifest = engine.manifest
            report["manifest"].append({
                **(manifest.__dict__ if manifest else {}),
                "enriched_rows": len(enriched),
                "events_detected": len(events),
                "signals_resolved": len(signals),
                "outcome_vara": engine.vara(),
                "seconds": round(time.time() - t0, 1),
            })
            print(f"[{timeframe} {symbol}] rows={len(enriched)} events={len(events)} "
                  f"signals={len(signals)} t={time.time() - t0:.0f}s", flush=True)

            if args.no_sensitivities:
                continue
            variants = {
                "S1_next_open": dict(entry_mode=ENTRY_MODE_NEXT_OPEN),
                "S2_time_stop_60": dict(time_stop_bars=60),
                "S3_profile_low": dict(risk_profile="low"),
                "S3_profile_high": dict(risk_profile="high"),
            }
            for name, kwargs in variants.items():
                alt = FepContBacktest(
                    symbol=symbol, timeframe=timeframe, start=start, end=end,
                    is_boundary=boundary, exchange=args.exchange,
                    entry_mode=kwargs.get("entry_mode", ENTRY_MODE_CLOSE),
                    time_stop_bars=kwargs.get("time_stop_bars"),
                    risk_profile=kwargs.get("risk_profile", "medium"),
                )
                # Only the two arms the sensitivity block reports are kept —
                # retaining every arm x variant would cost ~1 GB of RAM.
                sens_signals.setdefault(name, {}).setdefault(timeframe, []).extend(
                    s for s in alt.collect(enriched, events=events)
                    if s.arm in (ARM_FEP_CONT, ARM_BASE_RATE)
                )

    if args.shard_out:
        _dump_shard(args.shard_out, report["manifest"], all_signals, sens_signals)
        print(f"shard -> {args.shard_out}", flush=True)
        return 0

    for timeframe, signals in all_signals.items():
        report["cells"][timeframe] = _cell_report(
            signals, is_years=is_years, oos_years=oos_years, resamples=args.resamples
        )

    # Holm across the 4 TF cells for the secondary claims (§6).
    pvals = {
        tf: report["cells"][tf][ARM_FEP_CONT].get("welch_p_vs_control_oos")
        for tf in args.timeframes
    }
    report["holm_adjusted_p_vs_control_oos"] = holm_adjust(pvals)

    for name, per_tf in sens_signals.items():
        report["sensitivities"][name] = {
            tf: {
                "FEP-CONT_oos_per_signal": metrics_block(_split(sig, ARM_FEP_CONT, "out_of_sample")),
                "FEP-CONT_oos_portfolio": portfolio_block(
                    _split(sig, ARM_FEP_CONT, "out_of_sample"), years=oos_years),
                "BASE-RATE_oos_per_signal": metrics_block(_split(sig, ARM_BASE_RATE, "out_of_sample")),
            }
            for tf, sig in per_tf.items()
        }

    if PRIMARY_TIMEFRAME in report["cells"]:
        report["GATE"] = _evaluate_gate(report["cells"][PRIMARY_TIMEFRAME])
    else:
        report["GATE"] = {"verdict": "NOT EVALUATED",
                          "reason": f"primary timeframe {PRIMARY_TIMEFRAME} not in this run"}

    report["run"]["finished_utc"] = datetime.now(timezone.utc).isoformat()
    Path(args.json_out).write_text(json.dumps(report, indent=1, default=str))
    print(f"\nreport -> {args.json_out}")
    print(json.dumps(report.get("GATE", {}), indent=1, default=str))

    if args.trades_out:
        with open(args.trades_out, "w") as fh:
            for timeframe, signals in all_signals.items():
                for row in signal_dicts(signals):
                    fh.write(json.dumps(row, default=str) + "\n")
        print(f"signals -> {args.trades_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
