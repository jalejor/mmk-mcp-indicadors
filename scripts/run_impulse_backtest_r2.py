#!/usr/bin/env python3
"""Impulsos-v2 ROUND 2 backtest runner — sequential machine (H1) and + ML RSI gate (H2).

Executes `docs/PREREG_IMPULSOS_v2_r2.md` on the cached bitget frames (no exchange
calls when the cache is complete). Lab:

    docker compose --profile backtest run --rm backtest \
        python scripts/run_impulse_backtest_r2.py --md-out /app/docs/impulsos-v2-backtest-r2.md

Cells: pro 4h long/short and pro_1d long/short, H1 and H2. Also writes the
§R2.g owner-short report and compares with the round-1 result JSONs found in
`--out-dir` (new_pro_*.json, old_legacy_*.json).
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
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from controllers.metrics.impulse_backtest import (  # noqa: E402
    BLOCK_IS,
    BLOCK_OOS,
    ledger_metrics,
    load_ohlcv,
    run_anchored,
    run_sequential,
    split_metrics,
    trade_dicts,
    verdict,
)
from controllers.metrics.ml_rsi import MlRsiParams, repaint_report  # noqa: E402

DEFAULT_SYMBOL = "BTC/USDT"
DEFAULT_EXCHANGE = "bitget"
DEFAULT_START = "2024-11-01"
DEFAULT_END = "2026-10-31"
DEFAULT_SPLIT = "2026-01-01"
OWNER_PRICE = 82450.0
OWNER_WINDOW = ("2026-10-08", "2026-10-16")
MODEL_SHORT_WINDOW = ("2026-09-15", "2026-11-01")
RUNS = [("pro", False), ("pro", True), ("pro_1d", False), ("pro_1d", True)]


def _date(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def _f(v: Any, nd: int = 3) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return "inf" if v == float("inf") else f"{v:.{nd}f}"
    return str(v)


def _ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


def cell_row(label: str, metrics: Dict[str, Any], liquidations: int) -> str:
    m, i, o = metrics["all"], metrics[BLOCK_IS], metrics[BLOCK_OOS]
    v = verdict(metrics)
    if liquidations and v["verdict"] == "PASS":
        v = {"verdict": "NO-PASS", "failed": ["liquidations > 0"]}
    tag = v["verdict"] + (f" ({'; '.join(v['failed'])})" if v["failed"] else "")
    if not m.get("n"):
        return f"| {label} | 0 (0/0) | — | — | — | — | — | — | — | {tag} |"
    ci = m["bootstrap"]["ci95_cluster"]
    return (f"| {label} | {m['n']} ({i.get('n', 0)}/{o.get('n', 0)}) | {_f(m['expectancy_R'], 3)} | "
            f"[{ci[0]:.3f}, {ci[1]:.3f}] | {_f(i.get('expectancy_R'), 3) if i.get('n') else '—'} | "
            f"{_f(o.get('expectancy_R'), 3) if o.get('n') else '—'} | {_f(m['profit_factor'], 2)} | "
            f"{_f(m['max_drawdown_R'], 1)} | {m['win_rate'] * 100:.0f}% | {tag} |")


CELL_HEADER = ["| Cell | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | max DD R | win | Verdict |",
               "|---|---|---|---|---|---|---|---|---|---|"]


def round1_reference(out_dir: Path) -> Dict[str, Any]:
    """Round-1 headline numbers from the result JSONs (never retyped by hand)."""
    ref: Dict[str, Any] = {}
    for path in sorted(glob.glob(str(out_dir / "new_pro_*.json"))):
        data = json.loads(Path(path).read_text())
        for key, cell in data.get("cells", {}).items():
            if key.startswith("new|pro|4h|"):
                ref[f"round1 {key.split('|')[-1]}"] = cell["metrics"]["all"].get("expectancy_R")
    for path in sorted(glob.glob(str(out_dir / "old_legacy_*.json"))):
        data = json.loads(Path(path).read_text())
        for key, cell in data.get("cells", {}).items():
            if key.startswith("legacy|4h|medium 1.5/3R|long"):
                ref["legacy 4h long"] = cell["metrics"]["all"].get("expectancy_R")
            if key.startswith("legacy|1d|medium 1.5/3R|long"):
                ref["legacy 1d long"] = cell["metrics"]["all"].get("expectancy_R")
    return ref


def decision_brief(d: Any) -> Dict[str, Any]:
    dd = d.to_dict()
    vals = dd["context"].get("values", {})
    return {
        "candle_open": dd["timestamp"], "candle_close": dd["candle_close"], "action": dd["action"], "state": dd.get("state"),
        "side": dd["side"], "alert_side": dd.get("alert_side"), "alert_age": dd.get("alert_age"),
        "confirmations": dd.get("confirmations"), "phase": dd["phase"], "bbwp": vals.get("bbwp"), "verde": vals.get("verde"),
        "media": vals.get("media"), "close": vals.get("close"), "guardian_bias": dd["context_bias"],
        "mlrsi_regime": dd.get("mlrsi_regime"), "reasons": dd["reasons"], "layers": dd.get("layers"),
        "invalidation": dd.get("invalidation_price"), "invalidation_source": dd.get("invalidation_source"),
        "notional": dd.get("notional"), "one_r_usdt": dd.get("one_r_usdt"), "equity_usdt": dd.get("equity_usdt"),
    }


def owner_report(results: Dict[str, Any], frames4h: Dict[str, pd.DataFrame], symbol: str, split: datetime) -> Dict[str, Any]:
    """§R2.g: owner_bar, machine states, model's own short, anchored replay."""
    trig = frames4h["4h"]
    win = trig[(trig.index >= _ts(OWNER_WINDOW[0])) & (trig.index < _ts(OWNER_WINDOW[1]))]
    pos = int((win["close"] - OWNER_PRICE).abs().to_numpy().argmin())
    owner_time = win.index[pos]
    owner_bar = int(trig.index.get_loc(owner_time))
    report: Dict[str, Any] = {
        "owner_bar": {"index": owner_bar, "open": owner_time.isoformat(), "close_time": (owner_time + timedelta(hours=4)).isoformat(),
                      "close": float(trig["close"].iloc[owner_bar]), "owner_price": OWNER_PRICE},
        "state_at_owner_bar": {}, "model_own_short": {}, "anchored": {},
    }
    owner_close_ms = int(owner_time.value // 10**6) + 4 * 3_600_000
    for key, res in results.items():
        decs = res["all_decisions"]
        if res["timeframes"]["trigger"] == "4h":
            hit = [d for d in decs if d.timestamp == int(owner_time.value // 10**6)]
        else:  # 1d candle closed at or before the owner 4h close
            hit = [d for d in decs if d.timestamp is not None and d.timestamp + 86_400_000 <= owner_close_ms]
            hit = hit[-1:] if hit else []
        report["state_at_owner_bar"][key] = decision_brief(hit[0]) if hit else None
        # model's own short
        lo, hi = int(_ts(MODEL_SHORT_WINDOW[0]).value // 10**6), int(_ts(MODEL_SHORT_WINDOW[1]).value // 10**6)
        in_win = [d for d in decs if d.timestamp is not None and lo <= d.timestamp < hi]
        entries = [d for d in in_win if d.action == "enter" and d.side == "short"]
        if entries:
            e = entries[0]
            follow: List[Dict[str, Any]] = []
            for d in decs:
                if d.timestamp is None or d.timestamp <= e.timestamp:
                    continue
                if d.action in ("add_layer", "exit") or any(r.startswith("add_rejected") for r in d.reasons):
                    follow.append({"candle_close": d.candle_close, "action": d.action, "close": d.context.get("values", {}).get("close"),
                                   "reasons": [r for r in d.reasons if r.startswith(("add_", "exit_", "hold_"))], "notional": d.notional})
                if d.action == "exit":
                    break
            report["model_own_short"][key] = {"entry": decision_brief(e), "follow_up": follow[:40]}
        else:
            last = in_win[-1] if in_win else None
            longs = [d for d in in_win if d.action == "enter" and d.side == "long"]
            report["model_own_short"][key] = {
                "entry": None, "note": "no short ENTER in the window",
                "long_entries_in_window": [decision_brief(d) for d in longs[:5]],
                "states_in_window": {s: sum(1 for d in in_win if d.state == s) for s in ("flat", "alert", "in_position")},
                "last_decision": decision_brief(last) if last else None,
                "last_reason_codes": sorted({r for d in in_win[-12:] for r in d.reasons}),
            }
    for variant, gate in (("H1", False), ("H2", True)):
        anchored = run_anchored(profile="pro", frames=frames4h, anchor_bar=owner_bar, side="short", symbol=symbol,
                                split=split, mlrsi_gate=gate)
        decs = anchored["decisions"]
        entry = decs[0]
        events = [{"candle_close": d.candle_close, "action": d.action, "close": d.context.get("values", {}).get("close"),
                   "reasons": [r for r in d.reasons if r.startswith(("add_", "exit_", "hold_", "mlrsi"))], "notional": d.notional}
                  for d in decs[1:] if d.action in ("add_layer", "exit") or any(r.startswith("add_rejected") for r in d.reasons)]
        trades = anchored["trades"]
        oe = anchored["open_at_end"]
        out: Dict[str, Any] = {"entry": decision_brief(entry), "events": events[:60], "liquidations": anchored["liquidations"]}
        if trades and trades[0].exit_reason != "end_of_data":
            t = trades[0]
            out["exit"] = {"code": t.exit_reason, "candle": t.exit_time, "price": t.exit_price, "pnl_net_usdt": t.pnl_net_usdt,
                           "r_net": t.r_net, "n_layers": t.n_layers}
        if oe is not None:
            r_unit = oe["r_unit_usdt"] or float("nan")
            out["still_open_at_2026_10_31"] = {
                **{k: oe[k] for k in ("n_layers", "avg_price", "last_close", "unrealized_gross_usdt", "entry_costs_usdt",
                                      "funding_usdt", "exit_cost_estimate_usdt", "unrealized_net_usdt", "invalidation")},
                "r_unit_usdt": r_unit, "unrealized_gross_r": round(oe["unrealized_gross_usdt"] / r_unit, 3) if r_unit else None,
                "unrealized_net_r": round(oe["unrealized_net_usdt"] / r_unit, 3) if r_unit else None,
                "layer1_move_pct": round((OWNER_PRICE - oe["last_close"]) / OWNER_PRICE * 100.0, 2),
            }
        report["anchored"][variant] = out
    return report


def owner_md(rep: Dict[str, Any]) -> List[str]:
    ob = rep["owner_bar"]
    md = ["## §R2.g — the owner's open short (October 2026), informational", "",
          f"`owner_bar`: 4h candle open {ob['open']} (close {ob['close_time']}), close **{ob['close']:.2f}** "
          f"(owner ~{ob['owner_price']:.0f}).", "", "### Machine state at `owner_bar`", "",
          "| run | state | alert side / age | confirmations | phase | bbwp | verde | media | guardian | ML RSI | last reasons |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, s in rep["state_at_owner_bar"].items():
        if s is None:
            md.append(f"| {key} | — | | | | | | | | | no decision at that candle |")
            continue
        md.append(f"| {key} | {s['state']} | {s['alert_side']} / {s['alert_age']} | {s['confirmations'] or '—'} | {s['phase']} | "
                  f"{_f(s['bbwp'], 1)} | {_f(s['verde'], 2)} | {_f(s['media'], 2)} | {s['guardian_bias']} | {s['mlrsi_regime']} | "
                  f"{', '.join(s['reasons'][:4])} |")
    md += ["", "### Model's own short between 2026-09-15 and 2026-10-31", ""]
    for key, m in rep["model_own_short"].items():
        if m["entry"]:
            e = m["entry"]
            md.append(f"* **{key}**: ENTER short at {e['candle_close']} close {e['close']}, invalidation {e['invalidation']} "
                      f"({e['invalidation_source']}), layer 1 {e['notional']} USDT (1R {e['one_r_usdt']}), "
                      f"confirmations {e['confirmations']}. Follow-up: " + "; ".join(
                          f"{f['candle_close'][:16]} {f['action']} {','.join(f['reasons'])}" for f in m["follow_up"][:12]))
        else:
            md.append(f"* **{key}**: no short ENTER. States in window {m['states_in_window']}; long entries "
                      f"{len(m['long_entries_in_window'])}; last reason codes: {', '.join(m['last_reason_codes'][:12])}.")
    md += ["", "### Anchored replay: layer 1 short forced at `owner_bar` (§R2.c sizing, §R2.d invalidation), real rules after", ""]
    for variant, a in rep["anchored"].items():
        e = a["entry"]
        line = (f"* **{variant}**: layer 1 {e['notional']} USDT at {e['close']}, invalidation {e['invalidation']} "
                f"({e['invalidation_source']}), 1R {e['one_r_usdt']} USDT. Events: " + ("; ".join(
                    f"{x['candle_close'][:16]} {x['action']} {','.join(x['reasons'])}" for x in a["events"][:10]) or "none") + ".")
        if "exit" in a:
            x = a["exit"]
            line += f" **EXIT {x['code']}** at {x['candle']} price {x['price']}: net {x['pnl_net_usdt']} USDT = {x['r_net']} R ({x['n_layers']} layers)."
        if "still_open_at_2026_10_31" in a:
            s = a["still_open_at_2026_10_31"]
            line += (f" **Still open at 77551.91**: {s['n_layers']} layer(s), avg {_f(s['avg_price'], 2)}, move on layer 1 "
                     f"{s['layer1_move_pct']}%, unrealized gross {s['unrealized_gross_usdt']} USDT ({s['unrealized_gross_r']} R), "
                     f"net of entry costs {s['entry_costs_usdt']} + funding {s['funding_usdt']} + exit estimate "
                     f"{s['exit_cost_estimate_usdt']}: {s['unrealized_net_usdt']} USDT ({s['unrealized_net_r']} R).")
        md.append(line)
    md += ["", "One trade; it validates nothing (§R2.g.5).", ""]
    return md


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbol", default=DEFAULT_SYMBOL)
    p.add_argument("--exchange", default=DEFAULT_EXCHANGE)
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=DEFAULT_END, help="inclusive date")
    p.add_argument("--split", default=DEFAULT_SPLIT)
    p.add_argument("--cache-dir", default="/data/ohlcv")
    p.add_argument("--out-dir", default="/data/results")
    p.add_argument("--md-out", default=None)
    p.add_argument("--only", nargs="*", default=None, help="subset of runs, e.g. pro:H1 pro_1d:H2")
    args = p.parse_args()

    start, split = _date(args.start), _date(args.split)
    end = _date(args.end) + timedelta(days=1)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {}
    frame_cache: Dict[str, pd.DataFrame] = {}

    def loader(tf: str) -> pd.DataFrame:
        if tf in frame_cache:
            return frame_cache[tf]
        t0 = time.time()
        df, info = load_ohlcv(args.symbol, tf, start, end, exchange=args.exchange, cache_dir=args.cache_dir)
        manifest[tf] = {**info.__dict__, "seconds": round(time.time() - t0, 1)}
        print(f"[data] {tf}: {info.rows} rows {info.first_open} -> {info.last_open} gaps={info.gaps} sha={info.sha256[:12]} ({info.source})", flush=True)
        frame_cache[tf] = df
        return df

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results: Dict[str, Any] = {}
    cells: Dict[str, Any] = {}
    md_cells: List[str] = []
    md_books: List[str] = ["| run | trigger | decisions (alert / enter / add / exit) | trades | avg layers | >= 2 layers | equity final | return | max DD equity | max exposure | liquidations | exit mix |",
                           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    frames4h: Optional[Dict[str, pd.DataFrame]] = None
    for profile, gate in RUNS:
        key = f"{profile}:{'H2' if gate else 'H1'}"
        if args.only and key not in args.only:
            continue
        t0 = time.time()
        res = run_sequential(profile=profile, symbol=args.symbol, start=start, end=end, split=split,
                             directions=("long", "short"), loader=loader, mlrsi_gate=gate)
        results[key] = res
        if profile == "pro":
            frames4h = res["frames"]
        ledger = res["ledger"]
        book = ledger_metrics(ledger)
        trades = res["trades"]
        multi = sum(1 for t in trades if t.n_layers >= 2)
        acts = res["decisions"]
        md_books.append(
            f"| {key} | {res['timeframes']['trigger']} | {acts.get('alert', 0)} / {acts.get('enter', 0)} / {acts.get('add_layer', 0)} / "
            f"{acts.get('exit', 0)} | {book['n']} | {book['avg_layers']} | {multi} | {book['equity_final']} | {book['return_pct']}% | "
            f"{book['max_drawdown_equity_pct']}% | {book['max_exposure_x']}x | {book['liquidations']} | {book['exit_reasons']} |")
        cells[key] = {"book": book, "decisions": acts, "tf_status": res["tf_status"], "params": res["params"],
                      "first_bar": res["first_bar"], "buy_and_hold_pct": res["buy_and_hold_pct"], "sides": {}}
        for side in ("long", "short"):
            st = [t for t in trades if t.side == side]
            metrics = split_metrics(st)
            v = verdict(metrics)
            if res["liquidations"] and v["verdict"] == "PASS":
                v = {"verdict": "NO-PASS", "failed": ["liquidations > 0"]}
            cells[key]["sides"][side] = {"metrics": metrics, "verdict": v, "trades": trade_dicts(st)}
            md_cells.append(cell_row(f"{res['timeframes']['trigger']} {side} **{key}**", metrics, res["liquidations"]))
        print(f"[run] {key}: {book['n']} trades, equity {book['equity_final']}, {round(time.time() - t0, 1)}s "
              f"actions={acts}", flush=True)

    ref = round1_reference(out_dir)
    owner = owner_report({k: v for k, v in results.items()}, frames4h, args.symbol, split) if frames4h is not None else {}
    repaint = {}
    if frames4h is not None:
        repaint["4h"] = repaint_report(frames4h["4h"]["close"], MlRsiParams(), tail=1500)
        if "1d" in frames4h:
            repaint["1d"] = repaint_report(frames4h["1d"]["close"], MlRsiParams(), tail=700)

    report = {
        "prereg": "docs/PREREG_IMPULSOS_v2_r2.md", "rule_version": "impulse-2.1.0", "model": "sequential",
        "symbol": args.symbol, "exchange": args.exchange, "start": start.isoformat(), "end_exclusive": end.isoformat(),
        "split": split.isoformat(), "manifest": manifest, "cells": cells, "round1_reference": ref,
        "owner_short": owner, "mlrsi_repaint": repaint,
        "cost_model": "E16 fee 0.10% + slip 0.05% per layer per side; funding 0.01%/8h on total notional; 1R = layer-1 risk USDT",
    }
    out_path = out_dir / f"r2_sequential_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    md: List[str] = [
        "# Impulsos v2 — round 2 backtest results (`impulse-2.1.0`, sequential, PRO re-buys)", "",
        f"Protocol: `docs/PREREG_IMPULSOS_v2_r2.md` (frozen before this run). Run {stamp} in the lab service `backtest`, "
        f"harness `scripts/run_impulse_backtest_r2.py`. Raw JSON (every trade, every decision count): `{out_path.name}`.", "",
        "## Data manifest", "", "| TF | rows | first open | last open | gaps | sha256 (12) | source |", "|---|---|---|---|---|---|---|",
    ]
    for tf, m in manifest.items():
        md.append(f"| {tf} | {m['rows']} | {m['first_open'][:16]} | {m['last_open'][:16]} | {m['gaps']} | `{m['sha256'][:12]}` | {m['source']} |")
    md += ["", "## Cells (§6 verdict on net R; 1R = layer-1 risk = 2% E0; IS 2024-11 -> 2025-12, OOS 2026-01 -> 2026-10)", ""]
    md += CELL_HEADER + md_cells
    ref_txt = ", ".join(f"{k} {_f(v, 3)} R" for k, v in ref.items()) or "n/a"
    bh_txt = ", ".join(f"{k} {c['buy_and_hold_pct']}%" for k, c in cells.items())
    md += ["", f"Round-1 reference (same window, costs E16): {ref_txt}. Buy-and-hold: {bh_txt}.", "",
           "## Book level (one ledger per run, 1300 USDT start, 5x cross)", ""]
    md += md_books
    md += ["", "## Follower windows used (fitted on IS, frozen)", ""]
    for key, c in cells.items():
        md.append(f"* {key}: {c['params']['confirm_window_bars']} (ttl {max(c['params']['confirm_window_bars'].values())}), "
                  f"tf_status {c['tf_status']}, first decision {c['first_bar'][:16]}")
    md += ["", "## ML RSI repaint (causal vs TV-anchored window, percentile thresholds)", ""]
    for tf, r in repaint.items():
        md.append(f"* {tf}: {r['bars']} bars {r.get('first', '')[:10]} -> {r.get('last', '')[:10]}: upper mean |Δ| {r['upper_abs_diff_mean']} "
                  f"(max {r['upper_abs_diff_max']}), lower mean |Δ| {r['lower_abs_diff_mean']} (max {r['lower_abs_diff_max']}), "
                  f"regime disagreement {r['regime_disagreement_pct']}%, last bar identical {r['last_bar_identical']}.")
    md += [""]
    if owner:
        md += owner_md(owner)
    text = "\n".join(md)
    print(text)
    if args.md_out:
        Path(args.md_out).write_text(text + "\n")
        print(f"[out] {args.md_out}")
    print(f"[out] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
