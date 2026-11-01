#!/usr/bin/env python3
"""Impulsos-v2 ROUND 6 runner — two pre-registered ABLATIONS on the frozen 2.3.0 baseline (no new rule).

Executes `docs/PREREG_IMPULSOS_v2_r6.md` on the cached bitget frames (BTC 4h / 1h). Lab:

    docker compose --profile backtest run --rm backtest \
        python scripts/run_impulse_backtest_r6.py --md-out /app/docs/impulsos-v2-backtest-r6.md

Part A (owner point f): the guardian ML RSI exit (#3 of the 2.2.0 chain) ON (= round-5 baseline,
must reproduce it trade for trade) vs OFF with the entry block kept (`ctx_mlrsi_entry_block=True`,
pure exit ablation) vs both OFF (informational). `pro` 4h and `snipper` 1h.

Part B (owner point b/c): SNIPPER 1h book 1700 USDT at 10x ISOLATED vs 5x CROSS (same mmr 0.56 %),
same machine, same exit chain (Konkorde leader/exit, no AO — owner point a), three entries: baseline,
`bbwp_fresh_blue` (the only round-5 KEEP) and `adx_turn` (best round-5 RUN, classifier DROP,
informational). Two sizing models: RISK-sized (the model's: layer 1 = 2 % E0 at the invalidation,
cap 1.5x E0) and MARGIN-sized (the owner's habit: layer-1 margin 10 % E0 -> notional = margin x
leverage, adds 0.5x, exposure cap 3x layer 1, risk cap off). Reports liquidations, DD, R per unit of
time. Verdict per cell = prereg r4 §6 unchanged (`verdict_r4`); comparison verdicts per prereg r6 §6.
"""

from __future__ import annotations

import argparse
import glob
import json
import statistics
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

from controllers.metrics.impulse_backtest import BLOCK_IS, BLOCK_OOS, load_ohlcv  # noqa: E402
from run_impulse_backtest_r4 import CELL_HEADER, _date, _f, cell_row  # noqa: E402
from run_impulse_backtest_r5 import BASE, run_variant  # noqa: E402

DEFAULT_EXCHANGE = "bitget"
DEFAULT_START = "2024-11-01"
DEFAULT_END = "2026-10-31"
DEFAULT_SPLIT = "2026-01-01"
RULE_VERSION = "impulse-2.3.0"
ABLATION_VERSION = "impulse-2.3.0-r6"  # label of every non-baseline run (ablation, not a rule proposal)
SYMBOL = "BTC/USDT"

# E20 (found while preparing this round): rounds 4b and 5 ran with the TRIGGER ML RSI gate OFF
# (`run_sequential(mlrsi_gate=False)` default forwarded as an override). `AS_RUN` reproduces those
# runs; `{}` is the 2.2.0 / 2.3.0 rule doc as written (`mlrsi_gate: true`).
AS_RUN: Dict[str, Any] = {"mlrsi_gate": False}

# Part A — guardian ML RSI exit ablation (variant key -> overrides), on `pro` 4h and `snipper` 1h
PART_A: Dict[str, Dict[str, Any]] = {
    "A_on": {**AS_RUN},  # round-5 baseline as run (continuity check against r5)
    "A_exit_off": {**AS_RUN, "ctx_mlrsi_exit": False, "ctx_mlrsi_entry_block": True, "rule_version": ABLATION_VERSION},
    "A_both_off": {**AS_RUN, "ctx_mlrsi_exit": False, "rule_version": ABLATION_VERSION},
    "A_spec_on": {"rule_version": ABLATION_VERSION},  # 2.2.0 as WRITTEN: trigger gate on, guardian exit on
    "A_spec_exit_off": {"ctx_mlrsi_exit": False, "ctx_mlrsi_entry_block": True, "rule_version": ABLATION_VERSION},
}
PART_A_PAIRS = (("A_on", "A_exit_off"), ("A_on", "A_both_off"), ("A_spec_on", "A_spec_exit_off"))
PART_A_PROFILES: Sequence[str] = ("pro", "snipper")

# Part B — snipper books (as-run chain, continuity with the round-5 entry cells)
BOOKS: Dict[str, Dict[str, Any]] = {
    "iso10": {**AS_RUN},  # the snipper book of 2.2.0: 1700 USDT, 10x isolated, mmr 0.56 %
    "cross5": {**AS_RUN, "leverage": 5.0, "margin_mode": "cross", "maintenance_margin_rate": 0.0056, "rule_version": ABLATION_VERSION},
}
RISK_ENTRIES: Sequence[str] = (BASE, "bbwp_fresh_blue", "adx_turn")
MARGIN_ENTRIES: Sequence[str] = (BASE, "bbwp_fresh_blue")
MARGIN_FRACTION = 0.10  # layer-1 margin = 10 % of E0 (owner-style sizing)


def margin_sized(leverage: float) -> Dict[str, Any]:
    """Owner-style sizing: layer-1 notional = MARGIN_FRACTION x E0 x leverage (the risk-based size is
    disabled by a huge risk % so the exposure cap binds), adds 0.5x layer 1 (unchanged), exposure cap
    3x layer 1, risk cap off (100 % E0)."""
    return {"layer1_risk_pct": 1000.0, "layer1_max_exposure_x": MARGIN_FRACTION * leverage,
            "max_exposure_x": 3.0 * MARGIN_FRACTION * leverage, "max_open_risk_pct": 100.0,
            "rule_version": ABLATION_VERSION}


def _hours(t: Any) -> float:
    a, b = pd.Timestamp(t.entry_time), pd.Timestamp(t.exit_time)
    return max(0.0, (b - a).total_seconds() / 3600.0)


def time_metrics(trades: Sequence[Any], window_days: float) -> Dict[str, Any]:
    """R per unit of time (prereg r6 §5): net R per 30 days of window, net R per day HELD, trades/month."""
    if not trades:
        return {"n": 0}
    r = [float(t.r_net) for t in trades]
    hours = [_hours(t) for t in trades]
    sum_r, sum_days = sum(r), sum(hours) / 24.0
    return {
        "n": len(trades), "sum_r_net": round(sum_r, 3), "sum_pnl_net_usdt": round(sum(t.pnl_net_usdt for t in trades), 2),
        "r_per_30d": round(sum_r / window_days * 30.0, 3), "usdt_per_30d": round(sum(t.pnl_net_usdt for t in trades) / window_days * 30.0, 2),
        "r_per_day_held": round(sum_r / sum_days, 4) if sum_days > 0 else None,
        "trades_per_30d": round(len(trades) / window_days * 30.0, 2),
        "median_hold_h": round(statistics.median(hours), 1), "mean_hold_h": round(statistics.mean(hours), 1),
        "pct_time_in_market": round(sum_days / window_days * 100.0, 1),
        "avg_layers": round(statistics.mean(t.n_layers for t in trades), 2),
        "max_exposure_x": round(max(t.exposure_max for t in trades), 3),
        "funding_usdt": round(sum(t.funding_usdt for t in trades), 2), "cost_usdt": round(sum(t.cost_usdt for t in trades), 2),
    }


def paired(on: Sequence[Any], off: Sequence[Any]) -> Dict[str, Any]:
    """Trades matched by ENTRY time (prereg r6 §5 A): same entries, different exits."""
    a = {t.entry_time: t for t in on}
    b = {t.entry_time: t for t in off}
    common = sorted(set(a) & set(b))
    diffs = [float(b[k].r_net) - float(a[k].r_net) for k in common]
    longer = sum(1 for k in common if _hours(b[k]) > _hours(a[k]))
    return {
        "n_on": len(on), "n_off": len(off), "n_common_entries": len(common),
        "only_on": len(set(a) - set(b)), "only_off": len(set(b) - set(a)),
        "mean_r_diff_off_minus_on": round(statistics.mean(diffs), 4) if diffs else None,
        "median_r_diff_off_minus_on": round(statistics.median(diffs), 4) if diffs else None,
        "common_entries_longer_without_exit": longer,
        "sum_r_common_on": round(sum(float(a[k].r_net) for k in common), 3),
        "sum_r_common_off": round(sum(float(b[k].r_net) for k in common), 3),
    }


def _exp(cell: Dict[str, Any], side: str, block: Optional[str] = None) -> Optional[float]:
    m = cell["sides"][side]["metrics"]
    d = m[block] if block else m["all"]
    return float(d["expectancy_R"]) if d.get("n") else None


def pooled_metrics(cell: Dict[str, Any], block: Optional[str] = None) -> Dict[str, Any]:
    trades = cell["_trades"]
    if block:
        trades = [t for t in trades if t.block == block]
    if not trades:
        return {"n": 0, "expectancy_R": None}
    return {"n": len(trades), "expectancy_R": round(sum(float(t.r_net) for t in trades) / len(trades), 4)}


def verdict_a(on: Dict[str, Any], off: Dict[str, Any]) -> Dict[str, Any]:
    """Prereg r6 §6 A (sides pooled): KEEP iff exp_on > exp_off on all, IS and OOS AND liq_on <= liq_off;
    DROP iff exp_off > exp_on on all, IS and OOS AND liq_off <= liq_on; else INCONCLUSIVE.
    INCONCLUSIVE by construction when either run has n < 30 in total or < 10 in OOS."""
    po, pf = pooled_metrics(on), pooled_metrics(off)
    blocks = {blk: (pooled_metrics(on, blk), pooled_metrics(off, blk)) for blk in (BLOCK_IS, BLOCK_OOS)}
    if po["n"] < 30 or pf["n"] < 30 or blocks[BLOCK_OOS][0]["n"] < 10 or blocks[BLOCK_OOS][1]["n"] < 10:
        return {"verdict": "INCONCLUSIVE", "why": f"n on/off {po['n']}/{pf['n']}, n_oos {blocks[BLOCK_OOS][0]['n']}/{blocks[BLOCK_OOS][1]['n']}"}
    on_better = all(x["expectancy_R"] > y["expectancy_R"] for x, y in ((po, pf), *blocks.values()))
    off_better = all(y["expectancy_R"] > x["expectancy_R"] for x, y in ((po, pf), *blocks.values()))
    if on_better and on["liquidations"] <= off["liquidations"]:
        return {"verdict": "KEEP", "why": "exit ON beats OFF on all, IS and OOS"}
    if off_better and off["liquidations"] <= on["liquidations"]:
        return {"verdict": "DROP", "why": "exit OFF beats ON on all, IS and OOS"}
    return {"verdict": "INCONCLUSIVE", "why": "blocks disagree"}


def verdict_b(iso: Dict[str, Any], cross: Dict[str, Any], window_days: float) -> Dict[str, Any]:
    """Prereg r6 §6 B: 10x isolated PREFERRED iff liquidations == 0 AND net R >= cross AND max DD % <= cross
    (sides pooled, book level); otherwise 5x cross is the safer equivalent. Neither is a GO."""
    ti, tc = time_metrics(iso["_trades"], window_days), time_metrics(cross["_trades"], window_days)
    bi, bc = iso["per_symbol"][SYMBOL]["book"], cross["per_symbol"][SYMBOL]["book"]
    legs = {
        "liquidations_iso == 0": iso["liquidations"] == 0,
        "sum_r_iso >= sum_r_cross": (ti.get("sum_r_net") or 0.0) >= (tc.get("sum_r_net") or 0.0),
        "maxDD%_iso <= maxDD%_cross": bi["max_drawdown_equity_pct"] <= bc["max_drawdown_equity_pct"],
    }
    failed = [k for k, ok in legs.items() if not ok]
    return {"verdict": "ISO10_PREFERRED" if not failed else "CROSS5_SAFER", "failed": failed,
            "identical_trades": [t.entry_time for t in iso["_trades"]] == [t.entry_time for t in cross["_trades"]]
            and all(abs(a.pnl_net_usdt - b.pnl_net_usdt) < 1e-6 for a, b in zip(iso["_trades"], cross["_trades"]))}


def r5_reference(out_dir: Path) -> Dict[str, Any]:
    paths = sorted(glob.glob(str(out_dir / "r5_impulse_*.json")))
    if not paths:
        return {}
    data = json.loads(Path(paths[-1]).read_text())
    ref: Dict[str, Any] = {"file": Path(paths[-1]).name}
    for key, cell in data.get("cells", {}).items():
        if cell["variant"] != BASE or cell["profile"] not in PART_A_PROFILES:
            continue
        ref[cell["profile"]] = {side: {"n": s["metrics"]["all"].get("n", 0), "pnl_net_usdt": s["usdt"]["pnl_net_usdt"]}
                                for side, s in cell["sides"].items()}
    return ref


def continuity(cell: Dict[str, Any], ref: Dict[str, Any]) -> Dict[str, Any]:
    r = ref.get(cell["profile"])
    if not r:
        return {"checked": False}
    out: Dict[str, Any] = {"checked": True, "same": True}
    for side in ("long", "short"):
        st = [t for t in cell["_trades"] if t.side == side]
        got = {"n": len(st), "pnl_net_usdt": round(sum(t.pnl_net_usdt for t in st), 2)}
        out[side] = {"r6": got, "r5": r[side]}
        if got != {"n": r[side]["n"], "pnl_net_usdt": r[side]["pnl_net_usdt"]}:
            out["same"] = False
    return out


def book_row(key: str, c: Dict[str, Any], window_days: float) -> str:
    ps = c["per_symbol"][SYMBOL]
    b = ps["book"]
    tm = time_metrics(c["_trades"], window_days)
    return (f"| {key} | {c['params']['trigger_tf']} | {c['params']['leverage']:g}x {c['params']['margin_mode']} | {b['n']} | "
            f"{tm.get('sum_r_net', 0)} | {tm.get('r_per_30d', '—')} | {tm.get('r_per_day_held', '—')} | {tm.get('trades_per_30d', '—')} | "
            f"{tm.get('median_hold_h', '—')} | {tm.get('pct_time_in_market', '—')}% | {b['avg_layers']} | {b['max_exposure_x']} | {b['skipped_layers']} | "
            f"{b['equity_final']} | {b['return_pct']}% | {b['max_drawdown_equity_usdt']} ({b['max_drawdown_equity_pct']}%) | "
            f"{b['liquidations']} | {b['funding_usdt']} / {b['cost_usdt']} | {b['exit_reasons']} |")


BOOK_HEADER = [
    "| run | tf | book | trades | net R | R / 30 d | R / day held | trades / 30 d | median hold h | time in market | avg layers | max exposure x | layers sized down | equity final | return | max DD equity USDT (%) | liquidations | funding / fees USDT | exit mix |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--exchange", default=DEFAULT_EXCHANGE)
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=DEFAULT_END, help="inclusive date")
    p.add_argument("--split", default=DEFAULT_SPLIT)
    p.add_argument("--cache-dir", default="/data/ohlcv")
    p.add_argument("--out-dir", default="/data/results")
    p.add_argument("--md-out", default=None)
    p.add_argument("--only-parts", nargs="*", default=None, help="subset: A B")
    args = p.parse_args()

    start, split = _date(args.start), _date(args.split)
    end = _date(args.end) + timedelta(days=1)
    window_days = (end - start).total_seconds() / 86400.0
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {}
    frame_cache: Dict[str, pd.DataFrame] = {}

    def loader(tf: str) -> pd.DataFrame:
        key = f"{SYMBOL}@{tf}"
        if key in frame_cache:
            return frame_cache[key]
        t0 = time.time()
        df, info = load_ohlcv(SYMBOL, tf, start, end, exchange=args.exchange, cache_dir=args.cache_dir)
        manifest[key] = {**info.__dict__, "seconds": round(time.time() - t0, 1)}
        print(f"[data] {SYMBOL} {tf}: {info.rows} rows {info.first_open} -> {info.last_open} gaps={info.gaps} "
              f"sha={info.sha256[:12]} ({info.source})", flush=True)
        frame_cache[key] = df
        return df

    loaders = {SYMBOL: loader}
    parts = set(args.only_parts or ("A", "B"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cells: Dict[str, Dict[str, Any]] = {}

    def run(key: str, profile: str, variant: str, overrides: Dict[str, Any]) -> Dict[str, Any]:
        if key not in cells:
            cells[key] = run_variant(profile, variant, (SYMBOL,), loaders, start, end, split, overrides=overrides)
        return cells[key]

    # Part A
    part_a: Dict[str, Any] = {}
    if "A" in parts:
        for profile in PART_A_PROFILES:
            runs = {k: run(f"{profile}:{k}", profile, BASE, ov) for k, ov in PART_A.items()}
            part_a[profile] = {
                "pairs": {f"{a}->{b}": {"verdict": verdict_a(runs[a], runs[b]), "paired": paired(runs[a]["_trades"], runs[b]["_trades"])}
                          for a, b in PART_A_PAIRS},
                "time": {k: time_metrics(c["_trades"], window_days) for k, c in runs.items()},
            }
    # Part B (snipper)
    part_b: Dict[str, Any] = {}
    if "B" in parts:
        for entry in RISK_ENTRIES:
            iso = run(f"snipper:B_risk_iso10:{entry}", "snipper", entry, BOOKS["iso10"])
            cross = run(f"snipper:B_risk_cross5:{entry}", "snipper", entry, BOOKS["cross5"])
            part_b[f"risk:{entry}"] = verdict_b(iso, cross, window_days)
        for entry in MARGIN_ENTRIES:
            iso = run(f"snipper:B_margin_iso10:{entry}", "snipper", entry, {**BOOKS["iso10"], **margin_sized(10.0)})
            cross = run(f"snipper:B_margin_cross5:{entry}", "snipper", entry, {**BOOKS["cross5"], **margin_sized(5.0)})
            part_b[f"margin:{entry}"] = verdict_b(iso, cross, window_days)

    ref = r5_reference(out_dir)
    cont = {profile: continuity(cells[f"{profile}:A_on"], ref) for profile in PART_A_PROFILES if f"{profile}:A_on" in cells}

    def strip(c: Dict[str, Any]) -> Dict[str, Any]:
        c = dict(c)
        c.pop("_trades", None)
        c["per_symbol"] = {s: {k: v for k, v in ps.items() if k != "_res"} for s, ps in c["per_symbol"].items()}
        return c

    report = {
        "prereg": "docs/PREREG_IMPULSOS_v2_r6.md", "rule_version": RULE_VERSION, "ablation_label": ABLATION_VERSION,
        "exchange": args.exchange, "start": start.isoformat(), "end_exclusive": end.isoformat(), "split": split.isoformat(),
        "window_days": round(window_days, 1), "manifest": manifest,
        "cells": {k: {**strip(c), "time": time_metrics(c["_trades"], window_days),
                      "time_by_side": {s: time_metrics([t for t in c["_trades"] if t.side == s], window_days) for s in ("long", "short")}}
                  for k, c in cells.items()},
        "part_a": part_a, "part_b": part_b, "r5_continuity": cont, "r5_reference_file": ref.get("file"),
        "cost_model": "E16 fee 0.10% + slip 0.05% per layer per side (also on partial takes); funding 0.01%/8h on total "
                      "notional; liquidation intrabar (wick): isolated on the position margin, cross on the wallet; mmr 0.56% "
                      "in every snipper book; 1R = layer-1 risk USDT at the original qty",
    }
    out_path = out_dir / f"r6_impulse_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    md: List[str] = [
        "# Impulsos v2 — round 6 results (ablations on the frozen 2.3.0 baseline: guardian ML RSI exit · snipper 10x isolated vs 5x cross)", "",
        f"Protocol: `docs/PREREG_IMPULSOS_v2_r6.md` (frozen before this run). Run {stamp} in the lab service `backtest`, "
        f"harness `scripts/run_impulse_backtest_r6.py`. Raw JSON (every trade, pairing, time metrics): `{out_path.name}`. "
        f"Window {args.start} -> {args.end} ({window_days:.0f} days), IS/OOS split {args.split}.", "",
        "## Data manifest", "", "| symbol @ TF | rows | first open | last open | gaps | sha256 (12) | source |", "|---|---|---|---|---|---|---|",
    ]
    for key, m in manifest.items():
        md.append(f"| {key} | {m['rows']} | {m['first_open'][:16]} | {m['last_open'][:16]} | {m['gaps']} | `{m['sha256'][:12]}` | {m['source']} |")
    md += ["", "## Cells (1R = layer-1 risk; r4 verdict unchanged: GO iff n >= 30, n_oos >= 10, exp OOS > 0, PF >= 1.2, liq 0, DD < 35 %)", ""]
    md += CELL_HEADER
    for key, c in cells.items():
        for side, s in c["sides"].items():
            label = f"{c['params']['trigger_tf']} {side} **{key}** ({c['params']['leverage']:g}x {c['params']['margin_mode']}, {c['params']['equity_usdt']:g} USDT)"
            md.append(cell_row(label, s["metrics"], s["usdt"], s["verdict_r4"], s["verdict_r2"]))
    md += ["", "## Books and R per unit of time (one ledger per run, long + short)", ""] + BOOK_HEADER
    for key, c in cells.items():
        md.append(book_row(key, c, window_days))
    if part_a:
        md += ["", "## Part A — guardian ML RSI exit: ON vs OFF (prereg r6 §6 A, sides pooled; `A_on` = as run in r4b/r5 with the trigger gate OFF, E20; `A_spec_*` = rule doc as written, trigger gate ON)", "",
               "| profile | pair | variant | n | exp. R all | exp. IS | exp. OOS | PF | liq | book return | max DD % | exit mix | common entries | mean ΔR (off − on) on common | longer without the exit | verdict |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for profile, a in part_a.items():
            for pair, res in a["pairs"].items():
                ka, kb = pair.split("->")
                pr, v = res["paired"], res["verdict"]
                for k in (ka, kb):
                    c = cells[f"{profile}:{k}"]
                    b = c["per_symbol"][SYMBOL]["book"]
                    pc = pooled_metrics(c)
                    pf = c["sides"]["long"]["metrics"]["all"].get("profit_factor")  # per side below; pooled PF from trades:
                    gains = sum(float(t.r_net) for t in c["_trades"] if t.r_net > 0)
                    losses = -sum(float(t.r_net) for t in c["_trades"] if t.r_net < 0)
                    pf = round(gains / losses, 2) if losses > 0 else "inf"
                    tail = "— | — | — | — |" if k == ka else (
                        f"{pr['n_common_entries']} (+{pr['only_off']} new / {pr['only_on']} lost) | {_f(pr['mean_r_diff_off_minus_on'])} | "
                        f"{pr['common_entries_longer_without_exit']} | **{v['verdict']}** ({v['why']}) |")
                    md.append(f"| {profile} | {pair} | {k} | {pc['n']} | {_f(pc['expectancy_R'])} | {_f(pooled_metrics(c, BLOCK_IS)['expectancy_R'])} | "
                              f"{_f(pooled_metrics(c, BLOCK_OOS)['expectancy_R'])} | {pf} | {c['liquidations']} | {b['return_pct']}% | {b['max_drawdown_equity_pct']}% | "
                              f"{b['exit_reasons']} | {tail}")
    if part_b:
        md += ["", "## Part B — SNIPPER 1h: 10x isolated vs 5x cross (prereg r6 §6 B; neither is a GO unless its cells are)", "",
               "| sizing | entry | book | n | net R | R / 30 d | R / day held | liq | return | max DD % | trades identical? | verdict |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for key, v in part_b.items():
            sizing, entry = key.split(":", 1)
            for book in ("iso10", "cross5"):
                c = cells[f"snipper:B_{sizing}_{book}:{entry}"]
                tm = time_metrics(c["_trades"], window_days)
                b = c["per_symbol"][SYMBOL]["book"]
                md.append(f"| {sizing} | {entry} | {c['params']['leverage']:g}x {c['params']['margin_mode']} | {tm.get('n', 0)} | {tm.get('sum_r_net', 0)} | "
                          f"{tm.get('r_per_30d', '—')} | {tm.get('r_per_day_held', '—')} | {c['liquidations']} | {b['return_pct']}% | {b['max_drawdown_equity_pct']}% | "
                          f"{'yes' if v['identical_trades'] else 'no'} | {'**' + v['verdict'] + '**' + (' (' + '; '.join(v['failed']) + ')' if v['failed'] else '') if book == 'iso10' else ''} |")
    md += ["", "## Baseline continuity with round 5 (the `A_on` cells must reproduce the r5 `base` cells)", ""]
    for profile, c in cont.items():
        if not c.get("checked"):
            md.append(f"* {profile}: no r5 reference found.")
            continue
        md.append(f"* {profile}: **{'identical' if c['same'] else 'DIFFERENT'}** — " + "; ".join(
            f"{side} r6 n {c[side]['r6']['n']} / {c[side]['r6']['pnl_net_usdt']} USDT vs r5 n {c[side]['r5']['n']} / {c[side]['r5']['pnl_net_usdt']} USDT"
            for side in ("long", "short")))
    text = "\n".join(md)
    print(text)
    if args.md_out:
        Path(args.md_out).write_text(text + "\n")
        print(f"[out] {args.md_out}")
    print(f"[out] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
