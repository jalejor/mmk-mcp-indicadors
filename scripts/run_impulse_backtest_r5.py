#!/usr/bin/env python3
"""Impulsos-v2 ROUND 5 backtest runner — `impulse-2.3.0`: ENTRY filters on the FROZEN 2.2.0 chain.

Executes `docs/PREREG_IMPULSOS_v2_r5.md` on the cached bitget frames (BTC 4h / 1h / 1d; ETH and
SOL 1d + contexts are fetched from the PUBLIC endpoint when not cached, no keys). Lab:

    docker compose --profile backtest run --rm backtest \
        python scripts/run_impulse_backtest_r5.py --md-out /app/docs/impulsos-v2-backtest-r5.md

Per profile (`pro` 4h and `snipper` 1h on BTC; `pro_1d` on BTC + ETH + SOL pooled) it runs the
BASELINE (`entry_filter=None` = the 2.2.0 entry under the 2.3.0 label) and ONE run per member of
`ENTRY_FILTERS`, same books, same exit chain, same costs. Verdict per cell = prereg r4 §6 unchanged
(`verdict_r4`). The classifier study (prereg r5 §6b) tags every BASELINE trade with the pass / fail
of each filter at its entry candle and compares passed vs rejected trades: KEEP / DROP / INCONCLUSIVE.
Pre-registered fallback: a SNIPPER cell that fails ONLY the liquidation leg is re-run at 7x isolated.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from controllers.metrics.impulse_backtest import (  # noqa: E402
    BLOCK_IS,
    BLOCK_OOS,
    TIMEFRAME_MS,
    ledger_metrics,
    load_ohlcv,
    run_sequential,
    split_metrics,
    trade_dicts,
    verdict,
)
from controllers.metrics.impulse_sequential import SequentialMachine, r5_params  # noqa: E402
from controllers.metrics.impulse_service import ENTRY_FILTERS  # noqa: E402
from run_impulse_backtest_r4 import (  # noqa: E402
    CELL_HEADER,
    OWNER_PRICE,
    OWNER_WINDOW,
    _date,
    _f,
    _ts,
    cell_row,
    equity_dd_usdt,
    usdt_drawdown,
    verdict_r4,
)

DEFAULT_EXCHANGE = "bitget"
DEFAULT_START = "2024-11-01"
DEFAULT_END = "2026-10-31"
DEFAULT_SPLIT = "2026-01-01"
RULE = "r5"
RULE_VERSION = "impulse-2.3.0"
BASE = "base"
VARIANTS: Sequence[str] = (BASE,) + tuple(ENTRY_FILTERS)
PROFILES: Dict[str, Sequence[str]] = {  # owner's order: PRO first, then SNIPPER, then the 1d pooled read
    "pro": ("BTC/USDT",),
    "snipper": ("BTC/USDT",),
    "pro_1d": ("BTC/USDT", "ETH/USDT", "SOL/USDT"),
}
FALLBACK_PROFILE = "snipper"
FALLBACK_LEVERAGE = 7.0  # highest leverage with 0 liquidations in round 4b
CLS_MIN_PASS = 10
CLS_MIN_BLOCK = 3


def _exp(m: Dict[str, Any], block: Optional[str] = None) -> Optional[float]:
    d = m[block] if block else m["all"]
    return float(d["expectancy_R"]) if d.get("n") else None


def run_variant(profile: str, variant: str, symbols: Sequence[str], loaders: Dict[str, Callable[[str], pd.DataFrame]],
                start: datetime, end: datetime, split: datetime, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One book per symbol (same params), trades POOLED for the cell metrics (cluster = symbol x month)."""
    ov: Dict[str, Any] = {"entry_filter": None if variant == BASE else variant, **(overrides or {})}
    t0 = time.time()
    per_symbol: Dict[str, Any] = {}
    trades: List[Any] = []
    liquidations = 0
    params: Dict[str, Any] = {}
    for sym in symbols:
        res = run_sequential(profile=profile, symbol=sym, start=start, end=end, split=split,
                             directions=("long", "short"), loader=loaders[sym], rule=RULE, overrides=ov)
        ledger = res["ledger"]
        book = ledger_metrics(ledger)
        book["max_drawdown_equity_usdt"] = equity_dd_usdt(ledger.equity_curve)
        liquidations += int(res["liquidations"])
        trades += list(res["trades"])
        params = res["params"]
        info: Dict[str, int] = {}
        for d in res["all_decisions"]:
            for r in d.reasons:
                if r.startswith("entry_filter_blocked") or r in ("info_phase_lost", "ctx_mlrsi_against", "mlrsi_gate_against", "mlrsi_gate_gray"):
                    info[r] = info.get(r, 0) + 1
        per_symbol[sym] = {
            "book": book, "decisions": res["decisions"], "info_reasons": info, "tf_status": res["tf_status"],
            "first_bar": res["first_bar"], "buy_and_hold_pct": res["buy_and_hold_pct"], "liquidations": res["liquidations"],
            "partial_takes": sum(len(t.partial_takes) for t in res["trades"]),
            "multi_layer_trades": sum(1 for t in res["trades"] if t.n_layers >= 2), "_res": res,
        }
    keep = ("trigger_tf", "confirm_tf", "equity_usdt", "leverage", "margin_mode", "maintenance_margin_rate",
            "rule_version", "entry_filter", "adx_origin_band", "confirm_window_bars")
    out: Dict[str, Any] = {
        "profile": profile, "variant": variant, "entry_filter": ov["entry_filter"], "symbols": list(symbols),
        "params": {k: params.get(k) for k in keep}, "liquidations": liquidations, "per_symbol": per_symbol,
        "sides": {}, "seconds": round(time.time() - t0, 1), "_trades": trades,
    }
    e0 = float(params["equity_usdt"])
    for side in ("long", "short"):
        st = [t for t in trades if t.side == side]
        m = split_metrics(st)
        dd = usdt_drawdown(st, e0)
        v = verdict_r4(m, dd, liquidations)
        v6 = verdict(m)
        if liquidations and v6["verdict"] == "PASS":
            v6 = {"verdict": "NO-PASS", "failed": ["liquidations > 0"]}
        out["sides"][side] = {"metrics": m, "usdt": dd, "verdict_r4": v, "verdict_r2": v6, "trades": trade_dicts(st)}
    out["go"] = all(s["verdict_r4"]["verdict"] == "GO" for s in out["sides"].values())
    verdicts = ", ".join(f"{s}: n {o['metrics']['all'].get('n', 0)} {o['verdict_r4']['verdict']}" for s, o in out["sides"].items())
    books = "; ".join(f"{sym} {ps['book']['return_pct']}% DD {ps['book']['max_drawdown_equity_pct']}%" for sym, ps in per_symbol.items())
    print(f"[run] {profile}:{variant}: {params['trigger_tf']} {params['leverage']:g}x {params['margin_mode']}, "
          f"{len(trades)} trades, liq {liquidations}, books {books}, {out['seconds']}s, {{{verdicts}}}", flush=True)
    return out


def classifier_study(base_run: Dict[str, Any]) -> Dict[str, Any]:
    """Prereg r5 §6b: baseline trades split by each filter's flag at ENTER (reasons `entry_filter:<name>=<0|1>`)."""
    trades = base_run["_trades"]
    out: Dict[str, Any] = {}
    for name in ENTRY_FILTERS:
        passed = [t for t in trades if f"entry_filter:{name}=1" in t.reasons]
        rejected = [t for t in trades if f"entry_filter:{name}=0" in t.reasons]
        mp, mr = split_metrics(passed), split_metrics(rejected)
        blocks: Dict[str, Any] = {}
        for blk in (BLOCK_IS, BLOCK_OOS):
            n_p, n_r = mp[blk].get("n", 0), mr[blk].get("n", 0)
            comparable = n_p >= CLS_MIN_BLOCK and n_r >= CLS_MIN_BLOCK
            e_p, e_r = _exp(mp, blk), _exp(mr, blk)
            blocks[blk] = {"n_pass": n_p, "n_rej": n_r, "exp_pass": e_p, "exp_rej": e_r, "comparable": comparable,
                           "pass_beats_rej": (e_p > e_r) if comparable else None}
        e_all_p, e_all_r = _exp(mp), _exp(mr)
        row: Dict[str, Any] = {
            "n_pass": len(passed), "n_rej": len(rejected), "untagged": len(trades) - len(passed) - len(rejected),
            "n_pass_by_side": {s: sum(1 for t in passed if t.side == s) for s in ("long", "short")},
            "pass": mp, "rej": mr, "blocks": blocks,
            "pass_rate": round(len(passed) / len(trades), 3) if trades else None,
        }
        if len(passed) < CLS_MIN_PASS or len(rejected) < CLS_MIN_BLOCK or not all(b["comparable"] for b in blocks.values()):
            why = []
            if len(passed) < CLS_MIN_PASS:
                why.append(f"n_pass={len(passed)} < {CLS_MIN_PASS}")
            if len(rejected) < CLS_MIN_BLOCK:
                why.append(f"n_rej={len(rejected)} < {CLS_MIN_BLOCK}")
            why += [f"{blk}: n_pass {b['n_pass']} / n_rej {b['n_rej']} < {CLS_MIN_BLOCK}" for blk, b in blocks.items() if not b["comparable"]]
            row.update({"verdict": "INCONCLUSIVE", "failed": why})
        else:
            legs = {
                "exp_pass_all > 0": (e_all_p or 0.0) > 0,
                "exp_pass_all > exp_rej_all": e_all_p > e_all_r,
                "exp_pass_is > exp_rej_is": bool(blocks[BLOCK_IS]["pass_beats_rej"]),
                "exp_pass_oos > exp_rej_oos": bool(blocks[BLOCK_OOS]["pass_beats_rej"]),
            }
            failed = [k for k, ok in legs.items() if not ok]
            row.update({"verdict": "KEEP" if not failed else "DROP", "failed": failed})
        out[name] = row
    return out


def owner_bar_study(profile: str, run: Dict[str, Any], sym: str) -> Dict[str, Any]:
    """Prereg r5 §2 H-owner: the filter ingredients on the owner's short candle (82450, Oct 2026)."""
    res = run["per_symbol"][sym]["_res"]
    params = r5_params(profile)
    tf = res["timeframes"]["trigger"]
    trig = res["frames"][tf]
    win = trig[(trig.index >= _ts(OWNER_WINDOW[0])) & (trig.index < _ts(OWNER_WINDOW[1]))]
    pos = int((win["close"] - OWNER_PRICE).abs().to_numpy().argmin())
    owner_time = win.index[pos]
    i = int(trig.index.get_loc(owner_time))
    m = SequentialMachine(params, res["frames"])  # derivation only; never stepped
    T = m.trig
    w_adx = m.windows["adx"]
    onsets = [j for j in range(max(0, i - w_adx), i + 1) if bool(T["ev_adx_turn_up_short"][j])]
    confirms: Dict[str, Any] = {"adx": {"side": -1, "bar": onsets[-1], "event": "adx_turn_up_short"}} if onsets else {}
    origin = None
    if onsets:
        b = onsets[-1]
        window = T["adx"][max(0, b - int(params.adx_turn_window)): b + 1]
        origin = float(np.nanmin(window)) if len(window) and np.isfinite(window).any() else None
    g = m.contexts.get(params.confirm_tf)
    gi = int(m.ctx_idx[params.confirm_tf][i]) if params.confirm_tf in m.ctx_idx else -1
    return {
        "trigger_tf": tf, "owner_bar": owner_time.isoformat(), "close": float(trig["close"].iloc[i]), "owner_price": OWNER_PRICE,
        "state_in_baseline": next((d.state for d in res["all_decisions"] if d.timestamp == int(owner_time.value // 10**6)), None),
        "adx_turn_short_onsets_in_window": [trig.index[j].isoformat() for j in onsets], "adx_window": w_adx,
        "adx_at_bar": float(T["adx"][i]) if np.isfinite(T["adx"][i]) else None, "adx_origin": origin,
        "bear_div_trigger": bool(T["bear_div"][i]), "bear_div_guardian": bool(g["bear_div"][gi]) if g is not None and gi >= 0 else None,
        "phase": str(T["phase"][i]), "bbwp": float(T["bbwp"][i]) if np.isfinite(T["bbwp"][i]) else None,
        "blue_recent": bool(T["blue_recent"][i]),
        "flags_if_it_were_an_entry": m.entry_filter_flags(i, -1, confirms),
    }


def r4b_reference(out_dir: Path) -> Dict[str, Any]:
    """Round-4b cells (newest r4_impulse_*.json) for the baseline continuity check (never retyped)."""
    paths = sorted(glob.glob(str(out_dir / "r4_impulse_*.json")))
    if not paths:
        return {}
    data = json.loads(Path(paths[-1]).read_text())
    ref: Dict[str, Any] = {"file": Path(paths[-1]).name}
    for key, cell in data.get("cells", {}).items():
        ref[cell["profile"]] = {side: {"n": s["metrics"]["all"].get("n", 0), "expectancy_R": s["metrics"]["all"].get("expectancy_R"),
                                       "pnl_net_usdt": s["usdt"]["pnl_net_usdt"], "verdict": s["verdict_r4"]["verdict"]}
                                for side, s in cell["sides"].items()}
        ref[cell["profile"]]["book"] = {"return_pct": cell["book"]["return_pct"], "liquidations": cell["liquidations"]}
    return ref


def continuity(base_run: Dict[str, Any], ref: Dict[str, Any], sym: str) -> Dict[str, Any]:
    r = ref.get(base_run["profile"])
    if not r:
        return {"checked": False}
    out: Dict[str, Any] = {"checked": True, "same": True}
    for side in ("long", "short"):
        st = [t for t in base_run["_trades"] if t.side == side]
        got = {"n": len(st), "pnl_net_usdt": round(sum(t.pnl_net_usdt for t in st), 2)}
        exp = {"n": r[side]["n"], "pnl_net_usdt": r[side]["pnl_net_usdt"]}
        out[side] = {"r5_base": got, "r4b": exp}
        if got != exp:
            out["same"] = False
    return out


def book_row(key: str, sym: str, c: Dict[str, Any]) -> str:
    ps = c["per_symbol"][sym]
    b, a = ps["book"], ps["decisions"]
    blocked = sum(v for k, v in ps["info_reasons"].items() if k.startswith("entry_filter_blocked"))
    return (f"| {key} | {sym} | {c['params']['trigger_tf']} | {c['params']['leverage']:g}x {c['params']['margin_mode']} | "
            f"{a.get('alert', 0)} / {a.get('enter', 0)} / {a.get('add_layer', 0)} / {a.get('reduce', 0)} / {a.get('exit', 0)} | {blocked} | "
            f"{b['n']} | {b['avg_layers']} | {ps['partial_takes']} | {b['equity_final']} | {b['return_pct']}% | "
            f"{b['max_drawdown_equity_usdt']} ({b['max_drawdown_equity_pct']}%) | {b['liquidations']} | {b['exit_reasons']} | "
            f"{ps['buy_and_hold_pct']}% |")


def cls_row(name: str, r: Dict[str, Any]) -> str:
    def e(m: Dict[str, Any], blk: Optional[str]) -> str:
        return _f(_exp(m, blk))
    bi, bo = r["blocks"][BLOCK_IS], r["blocks"][BLOCK_OOS]
    tag = r["verdict"] + (f" ({'; '.join(r['failed'])})" if r.get("failed") else "")
    pf_p = _f(r["pass"]["all"].get("profit_factor"), 2) if r["n_pass"] else "—"
    pf_r = _f(r["rej"]["all"].get("profit_factor"), 2) if r["n_rej"] else "—"
    ci = r["pass"]["all"].get("bootstrap", {}).get("ci95_cluster") if r["n_pass"] else None
    ci_s = f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "—"
    by_side = r["n_pass_by_side"]
    return (f"| `{name}` | {r['n_pass']} ({by_side['long']}L/{by_side['short']}S) / {r['n_rej']} ({r['pass_rate']}) | {e(r['pass'], None)} {ci_s} | {e(r['rej'], None)} | "
            f"{_f(bi['exp_pass'])} vs {_f(bi['exp_rej'])} ({bi['n_pass']}/{bi['n_rej']}) | {_f(bo['exp_pass'])} vs {_f(bo['exp_rej'])} "
            f"({bo['n_pass']}/{bo['n_rej']}) | {pf_p} / {pf_r} | **{tag}** |")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--exchange", default=DEFAULT_EXCHANGE)
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=DEFAULT_END, help="inclusive date")
    p.add_argument("--split", default=DEFAULT_SPLIT)
    p.add_argument("--cache-dir", default="/data/ohlcv")
    p.add_argument("--out-dir", default="/data/results")
    p.add_argument("--md-out", default=None)
    p.add_argument("--only-profiles", nargs="*", default=None, help="subset of profiles, e.g. pro snipper")
    p.add_argument("--only-variants", nargs="*", default=None, help="subset of variants, e.g. base adx_turn")
    p.add_argument("--no-fallback", action="store_true", help="skip the 7x fallback re-run")
    args = p.parse_args()

    start, split = _date(args.start), _date(args.split)
    end = _date(args.end) + timedelta(days=1)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {}
    frame_cache: Dict[str, pd.DataFrame] = {}

    def loader_for(sym: str) -> Callable[[str], pd.DataFrame]:
        def loader(tf: str) -> pd.DataFrame:
            key = f"{sym}@{tf}"
            if key in frame_cache:
                return frame_cache[key]
            t0 = time.time()
            df, info = load_ohlcv(sym, tf, start, end, exchange=args.exchange, cache_dir=args.cache_dir)
            manifest[key] = {**info.__dict__, "seconds": round(time.time() - t0, 1)}
            print(f"[data] {sym} {tf}: {info.rows} rows {info.first_open} -> {info.last_open} gaps={info.gaps} "
                  f"sha={info.sha256[:12]} ({info.source}, {manifest[key]['seconds']}s)", flush=True)
            frame_cache[key] = df
            return df
        return loader

    loaders = {sym: loader_for(sym) for syms in PROFILES.values() for sym in syms}
    profiles = [k for k in PROFILES if not args.only_profiles or k in args.only_profiles]
    variants = [v for v in VARIANTS if not args.only_variants or v in args.only_variants]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cells: Dict[str, Dict[str, Any]] = {}
    for profile in profiles:
        for variant in variants:
            cells[f"{profile}:{variant}"] = run_variant(profile, variant, PROFILES[profile], loaders, start, end, split)

    ref = r4b_reference(out_dir)
    classifier: Dict[str, Any] = {}
    owner: Dict[str, Any] = {}
    cont: Dict[str, Any] = {}
    for profile in profiles:
        base = cells.get(f"{profile}:{BASE}")
        if base is None:
            continue
        classifier[profile] = classifier_study(base)
        cont[profile] = continuity(base, ref, PROFILES[profile][0])
        if profile in ("pro", "snipper"):
            owner[profile] = owner_bar_study(profile, base, "BTC/USDT")

    fallback: Dict[str, Any] = {}
    if not args.no_fallback:
        for key, c in list(cells.items()):
            if c["profile"] != FALLBACK_PROFILE:
                continue
            only_liq = [s for s, o in c["sides"].items() if o["verdict_r4"]["verdict"] == "NO-GO" and o["verdict_r4"]["failed"] == ["liquidations == 0"]]
            if only_liq:
                fb = run_variant(c["profile"], c["variant"], PROFILES[c["profile"]], loaders, start, end, split, overrides={"leverage": FALLBACK_LEVERAGE})
                fb["triggered_by_sides"] = only_liq
                fallback[f"{key}@{FALLBACK_LEVERAGE:g}x"] = fb

    def strip(c: Dict[str, Any]) -> Dict[str, Any]:
        c = dict(c)
        c.pop("_trades", None)
        c["per_symbol"] = {s: {k: v for k, v in ps.items() if k != "_res"} for s, ps in c["per_symbol"].items()}
        return c

    report = {
        "prereg": "docs/PREREG_IMPULSOS_v2_r5.md", "rule_version": RULE_VERSION, "model": "sequential", "rule": RULE,
        "exchange": args.exchange, "start": start.isoformat(), "end_exclusive": end.isoformat(), "split": split.isoformat(),
        "profiles": {k: list(v) for k, v in PROFILES.items()}, "variants": list(variants), "manifest": manifest,
        "cells": {k: strip(c) for k, c in cells.items()}, "classifier": classifier, "owner_bar": owner,
        "r4b_continuity": cont, "r4b_reference_file": ref.get("file"), "fallback": {k: strip(c) for k, c in fallback.items()},
        "go_runs": [k for k, c in cells.items() if c["go"]],
        "cost_model": "E16 fee 0.10% + slip 0.05% per layer per side (also on partial takes); funding 0.01%/8h on total "
                      "notional; liquidation intrabar (wick) — cross on the wallet (pro), isolated on the position margin "
                      "at mmr 0.56% (snipper); 1R = layer-1 risk USDT at the original qty",
    }
    out_path = out_dir / f"r5_impulse_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    md: List[str] = [
        "# Impulsos v2 — round 5 backtest results (`impulse-2.3.0`: ENTRY filters on the frozen 2.2.0 chain)", "",
        f"Protocol: `docs/PREREG_IMPULSOS_v2_r5.md` (frozen before this run). Run {stamp} in the lab service `backtest`, "
        f"harness `scripts/run_impulse_backtest_r5.py`. Raw JSON (every trade, flags, classifier, owner bar): `{out_path.name}`.", "",
        "## Data manifest", "", "| symbol @ TF | rows | first open | last open | gaps | sha256 (12) | source |", "|---|---|---|---|---|---|---|",
    ]
    for key, m in manifest.items():
        md.append(f"| {key} | {m['rows']} | {m['first_open'][:16]} | {m['last_open'][:16]} | {m['gaps']} | `{m['sha256'][:12]}` | {m['source']} |")
    md += ["", "## Cells (1R = layer-1 risk = 2 % E0; IS 2024-11 -> 2025-12, OOS 2026-01 -> 2026-10; `base` = 2.2.0 entry)", "",
           "r4 verdict (unchanged from round 4b): GO iff n >= 30, n_oos >= 10, expectancy OOS > 0, PF >= 1.2, liquidations 0, "
           "max DD (cumulative net USDT of the cell) < 35 % of one book's start. `pro_1d` cells pool BTC + ETH + SOL "
           "(one book per symbol; DD % refers to one book's equity). r2 §6 = round-2 R-based verdict, for continuity.", ""]
    md += CELL_HEADER
    for key, c in cells.items():
        for side, s in c["sides"].items():
            label = f"{c['params']['trigger_tf']} {side} **{key}** ({c['params']['leverage']:g}x {c['params']['margin_mode']}, {c['params']['equity_usdt']:g} USDT"
            label += f", pooled {len(c['symbols'])} symbols)" if len(c["symbols"]) > 1 else ")"
            md.append(cell_row(label, s["metrics"], s["usdt"], s["verdict_r4"], s["verdict_r2"]))
    md += ["", "## Book level (one ledger per run and symbol, long + short)", "",
           "| run | symbol | tf | lev | decisions (alert / enter / add / reduce / exit) | entries blocked by the filter | trades | avg layers | partial takes | equity final | return | max DD equity USDT (%) | liquidations | exit mix | B&H |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, c in {**cells, **fallback}.items():
        for sym in c["symbols"]:
            md.append(book_row(key, sym, c))
    md += ["", "## Classifier study on the BASELINE trades (prereg §6b; flags at the entry candle, no re-run)", "",
           f"KEEP iff n_pass >= {CLS_MIN_PASS} AND expectancy of the passed trades > 0 AND passed > rejected on all, IS and OOS "
           f"(each block with >= {CLS_MIN_BLOCK} trades on both sides); DROP when comparable and any leg fails; INCONCLUSIVE when not comparable. "
           "Caveat: a filtered RUN changes the path (position occupancy), so this is a reading of the signal, not of the book.", ""]
    for profile, rows in classifier.items():
        base = cells[f"{profile}:{BASE}"]
        md += [f"### {profile} ({base['params']['trigger_tf']}, baseline n {len(base['_trades'])}, symbols {', '.join(base['symbols'])})", "",
               "| filter | n pass (long/short) / n rej (pass rate) | exp. R pass (CI95) | exp. R rej | IS pass vs rej (n) | OOS pass vs rej (n) | PF pass / rej | verdict |",
               "|---|---|---|---|---|---|---|---|"]
        md += [cls_row(name, r) for name, r in rows.items()]
        md.append("")
    if fallback:
        md += ["## Pre-registered fallback (SNIPPER cell failing ONLY the liquidation leg -> 7x isolated)", ""]
        for key, c in fallback.items():
            vs = ", ".join(f"{s}: {o['verdict_r4']['verdict']} {o['verdict_r4']['failed']}" for s, o in c["sides"].items())
            md.append(f"* `{key}` (triggered by {c['triggered_by_sides']}): liquidations {c['liquidations']}, {vs}.")
        md.append("")
    else:
        md += ["## Pre-registered fallback", "", "No SNIPPER cell failed only the liquidation leg; no 7x re-run.", ""]
    md += ["## Baseline continuity with round 4b (same data, same chain: the `base` cells must reproduce r4b)", ""]
    for profile, c in cont.items():
        if not c.get("checked"):
            md.append(f"* {profile}: no r4b reference found.")
            continue
        md.append(f"* {profile}: **{'identical' if c['same'] else 'DIFFERENT'}** — " + "; ".join(
            f"{side} r5 base n {c[side]['r5_base']['n']} / {c[side]['r5_base']['pnl_net_usdt']} USDT vs r4b n {c[side]['r4b']['n']} / {c[side]['r4b']['pnl_net_usdt']} USDT"
            for side in ("long", "short")))
    md += ["", "## H-owner — the owner's short candle (82450, Oct 2026) seen by the filters (informational)", ""]
    for profile, o in owner.items():
        flags = ", ".join(f"{k}={int(v)}" for k, v in o["flags_if_it_were_an_entry"].items())
        md.append(f"* **{profile}** ({o['trigger_tf']}) owner bar {o['owner_bar'][:16]} close {o['close']:.2f}, baseline state {o['state_in_baseline']}: "
                  f"phase {o['phase']} (bbwp {_f(o['bbwp'], 1)}, blue_recent {o['blue_recent']}); ADX {_f(o['adx_at_bar'], 1)}, short turn onsets in the "
                  f"last {o['adx_window']} candles {o['adx_turn_short_onsets_in_window'] or 'none'}, origin {_f(o['adx_origin'], 1)}; bear divergence "
                  f"trigger {o['bear_div_trigger']} / guardian {o['bear_div_guardian']}. Flags if it were an entry: {flags}.")
    md += ["", "## Follower windows used (IS fit, frozen since rounds 2 / 4)", ""]
    for profile in profiles:
        c = cells.get(f"{profile}:{BASE}")
        if c:
            md.append(f"* {profile}: {c['params']['confirm_window_bars']}, tf_status " + "; ".join(
                f"{sym} {ps['tf_status']}" for sym, ps in c["per_symbol"].items()))
    text = "\n".join(md)
    print(text)
    if args.md_out:
        Path(args.md_out).write_text(text + "\n")
        print(f"[out] {args.md_out}")
    print(f"[out] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
