#!/usr/bin/env python3
"""Impulsos-v2 ROUND 4b backtest runner — `impulse-2.2.0` exit chain (owner decision 6).

Executes `docs/PREREG_IMPULSOS_v2_r4.md` on the cached bitget frames (no exchange
calls when the cache is complete). Lab:

    docker compose --profile backtest run --rm backtest \
        python scripts/run_impulse_backtest_r4.py --md-out /app/docs/impulsos-v2-backtest-r4.md

Runs, in the owner's order (one book each, long + short, `rule="r4"` =
`impulse_sequential.r4_params`: no phase_lost exit, no time stop, ML RSI gate,
50 % partial take, structural invalidation on the guardian close, guardian ML
RSI contrary = exit):

* `pro:R4`      — 4h, guardian 1d, 1300 USDT, 5x CROSS, re-buys
* `pro_1d:R4`   — 1d, guardian 1w (expected INCONCLUSIVE, n small)
* `snipper:R4`  — 1h, guardian 4h, 1d informational, 1700 USDT, 10x ISOLATED, re-buys,
                  intrabar (wick) liquidation at Bitget tier-1 MMR + clearance, funding
* leverage sweep of `snipper:R4` at 7x / 5x / 3x / 2x / 1x (pre-registered fallback)
* §R2.g owner-short replay (82450, 2026-10-09) with the NEW chain on 4h (pro) and 1h (snipper)

Verdict per cell (prereg §6, owner's criterion): GO iff n_total >= 30 AND
n_oos >= 10 AND expectancy_oos > 0 AND PF_total >= 1.2 AND liquidations == 0
AND max drawdown (cumulative net USDT of the cell, % of the start) < 35 %.
The round-2 §6 R-based verdict is printed next to it for continuity.
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
from typing import Any, Dict, List, Optional, Sequence

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from controllers.metrics.impulse_backtest import (  # noqa: E402
    BLOCK_IS,
    BLOCK_OOS,
    TIMEFRAME_MS,
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
RULE = "r4"
RULE_VERSION = "impulse-2.2.0"
RUNS: Dict[str, Dict[str, Any]] = {  # owner's order: PRO first, then SNIPPER
    "pro:R4": {"profile": "pro"},
    "pro_1d:R4": {"profile": "pro_1d"},
    "snipper:R4": {"profile": "snipper"},
}
PRIMARY_SWEEP = "snipper:R4"
LEVERAGE_SWEEP = (7.0, 5.0, 3.0, 2.0, 1.0)
GO_MIN_N = 30
GO_MIN_N_OOS = 10
GO_MIN_PF = 1.2
GO_MAX_DD_PCT = 35.0
OWNER_PRICE = 82450.0
OWNER_WINDOW = ("2026-10-08", "2026-10-16")


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


def usdt_drawdown(trades: Sequence[Any], initial: float) -> Dict[str, float]:
    """Max drawdown of the cumulative NET USDT PnL of these trades, absolute and % of `initial`."""
    eq = peak = dd = 0.0
    for t in sorted(trades, key=lambda t: t.entry_time):
        eq += t.pnl_net_usdt
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {"max_drawdown_usdt": round(dd, 2), "max_drawdown_pct_initial": round(dd / initial * 100.0, 2),
            "pnl_net_usdt": round(eq, 2)}


def verdict_r4(metrics: Dict[str, Any], dd: Dict[str, float], liquidations: int) -> Dict[str, Any]:
    """PREREG r4 §6 GO / NO-GO, mechanical."""
    total, oos = metrics["all"], metrics[BLOCK_OOS]
    n = total.get("n", 0)
    if n < GO_MIN_N:
        return {"verdict": "INCONCLUSIVE", "failed": [f"n_total={n} < {GO_MIN_N}"]}
    legs = {
        f"n_oos >= {GO_MIN_N_OOS}": oos.get("n", 0) >= GO_MIN_N_OOS,
        "expectancy_oos > 0": oos.get("n", 0) > 0 and oos["expectancy_R"] > 0,
        f"PF >= {GO_MIN_PF}": float(total["profit_factor"]) >= GO_MIN_PF,
        "liquidations == 0": liquidations == 0,
        f"maxDD < {GO_MAX_DD_PCT:.0f}% of start": dd["max_drawdown_pct_initial"] < GO_MAX_DD_PCT,
    }
    failed = [k for k, ok in legs.items() if not ok]
    return {"verdict": "GO" if not failed else "NO-GO", "failed": failed}


def equity_dd_usdt(curve: Sequence[Any]) -> float:
    peak, dd = None, 0.0
    for _, eq in curve:
        peak = eq if peak is None else max(peak, eq)
        dd = max(dd, peak - eq)
    return round(dd, 2)


CELL_HEADER = ["| Cell | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | win | max DD USDT (% start) | net USDT | **r4 verdict** | r2 §6 |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|"]


def cell_row(label: str, m: Dict[str, Any], dd: Dict[str, float], v: Dict[str, Any], v6: Dict[str, Any]) -> str:
    a, i, o = m["all"], m[BLOCK_IS], m[BLOCK_OOS]
    tag = v["verdict"] + (f" ({'; '.join(v['failed'])})" if v["failed"] else "")
    if not a.get("n"):
        return f"| {label} | 0 (0/0) | — | — | — | — | — | — | — | — | {tag} | {v6['verdict']} |"
    ci = a["bootstrap"]["ci95_cluster"]
    return (f"| {label} | {a['n']} ({i.get('n', 0)}/{o.get('n', 0)}) | {_f(a['expectancy_R'])} | "
            f"[{ci[0]:.3f}, {ci[1]:.3f}] | {_f(i.get('expectancy_R')) if i.get('n') else '—'} | "
            f"{_f(o.get('expectancy_R')) if o.get('n') else '—'} | {_f(a['profit_factor'], 2)} | "
            f"{a['win_rate'] * 100:.0f}% | {dd['max_drawdown_usdt']} ({dd['max_drawdown_pct_initial']}%) | "
            f"{dd['pnl_net_usdt']} | {tag} | {v6['verdict']} |")


def round2_reference(out_dir: Path) -> Dict[str, Any]:
    """Round 2-3 numbers (pro:H1 / pro:H2 4h and 1d) from the newest r2_sequential_*.json (never retyped)."""
    paths = sorted(glob.glob(str(out_dir / "r2_sequential_*.json")))
    if not paths:
        return {}
    data = json.loads(Path(paths[-1]).read_text())
    ref: Dict[str, Any] = {"file": Path(paths[-1]).name}
    for key, cell in data.get("cells", {}).items():
        book = cell["book"]
        ref[key] = {"book": {k: book.get(k) for k in ("n", "equity_final", "return_pct", "max_drawdown_equity_pct", "liquidations", "exit_reasons")},
                    "buy_and_hold_pct": cell.get("buy_and_hold_pct")}
        for side, s in cell["sides"].items():
            m = s["metrics"]
            ref[key][side] = {"n": m["all"].get("n", 0), "expectancy_R": m["all"].get("expectancy_R"),
                              "expectancy_oos": m[BLOCK_OOS].get("expectancy_R"), "n_oos": m[BLOCK_OOS].get("n", 0),
                              "profit_factor": m["all"].get("profit_factor"), "win_rate": m["all"].get("win_rate"),
                              "max_drawdown_R": m["all"].get("max_drawdown_R"), "verdict": s["verdict"]["verdict"]}
    return ref


def run_one(key: str, profile: str, overrides: Dict[str, Any], args: Any, loader: Any, start: datetime, end: datetime,
            split: datetime) -> Dict[str, Any]:
    t0 = time.time()
    res = run_sequential(profile=profile, symbol=args.symbol, start=start, end=end, split=split,
                         directions=("long", "short"), loader=loader, rule=RULE, overrides=overrides or None)
    ledger = res["ledger"]
    book = ledger_metrics(ledger)
    book["max_drawdown_equity_usdt"] = equity_dd_usdt(ledger.equity_curve)
    trades = res["trades"]
    reasons: Dict[str, int] = {}
    for d in res["all_decisions"]:
        for r in d.reasons:
            if r in ("info_phase_lost", "hold_beyond_invalidation_awaiting_ctx_close", "ctx_mlrsi_against"):
                reasons[r] = reasons.get(r, 0) + 1
    out: Dict[str, Any] = {
        "profile": profile, "book": book, "decisions": res["decisions"], "info_reasons": reasons, "tf_status": res["tf_status"],
        "params": res["params"], "first_bar": res["first_bar"], "buy_and_hold_pct": res["buy_and_hold_pct"],
        "liquidations": res["liquidations"], "multi_layer_trades": sum(1 for t in trades if t.n_layers >= 2),
        "partial_takes": sum(len(t.partial_takes) for t in trades), "sides": {}, "seconds": round(time.time() - t0, 1),
    }
    for side in ("long", "short"):
        st = [t for t in trades if t.side == side]
        metrics = split_metrics(st)
        dd = usdt_drawdown(st, float(res["params"]["equity_usdt"]))
        v = verdict_r4(metrics, dd, res["liquidations"])
        v6 = verdict(metrics)
        if res["liquidations"] and v6["verdict"] == "PASS":
            v6 = {"verdict": "NO-PASS", "failed": ["liquidations > 0"]}
        out["sides"][side] = {"metrics": metrics, "usdt": dd, "verdict_r4": v, "verdict_r2": v6, "trades": trade_dicts(st)}
    out["go"] = all(s["verdict_r4"]["verdict"] == "GO" for s in out["sides"].values())
    verdicts = ", ".join(f"{s}: {o['verdict_r4']['verdict']}" for s, o in out["sides"].items())
    print(f"[run] {key}: {res['params']['trigger_tf']} lev {res['params']['leverage']:g}x {res['params']['margin_mode']}, "
          f"{book['n']} trades, equity {book['equity_final']} ({book['return_pct']}%), DD {book['max_drawdown_equity_pct']}%, "
          f"liq {res['liquidations']}, partial {out['partial_takes']}, exits {book['exit_reasons']}, {out['seconds']}s, "
          f"verdicts {{{verdicts}}}", flush=True)
    out["_res"] = res
    return out


def decision_brief(d: Any) -> Dict[str, Any]:
    dd = d.to_dict()
    vals = dd["context"].get("values", {})
    return {"candle_close": dd["candle_close"], "action": dd["action"], "state": dd.get("state"), "side": dd["side"],
            "alert_side": dd.get("alert_side"), "confirmations": dd.get("confirmations"), "phase": dd["phase"],
            "bbwp": vals.get("bbwp"), "verde": vals.get("verde"), "close": vals.get("close"), "guardian_bias": dd["context_bias"],
            "mlrsi_regime": dd.get("mlrsi_regime"), "ctx_mlrsi_regime": dd["context"].get("ctx_mlrsi_regime"),
            "reasons": dd["reasons"], "invalidation": dd.get("invalidation_price"), "invalidation_source": dd.get("invalidation_source"),
            "notional": dd.get("notional"), "one_r_usdt": dd.get("one_r_usdt"), "liquidation_price": dd.get("liquidation_price")}


def owner_replay(profile: str, res: Dict[str, Any], symbol: str, split: datetime) -> Dict[str, Any]:
    """§R2.g with the NEW chain: owner_bar on the profile's trigger TF, machine state there,
    the model's own shorts in Sep-Oct 2026, and the anchored replay (layer 1 forced at owner_bar)."""
    tf = res["timeframes"]["trigger"]
    trig = res["frames"][tf]
    win = trig[(trig.index >= _ts(OWNER_WINDOW[0])) & (trig.index < _ts(OWNER_WINDOW[1]))]
    pos = int((win["close"] - OWNER_PRICE).abs().to_numpy().argmin())
    owner_time = win.index[pos]
    owner_bar = int(trig.index.get_loc(owner_time))
    hit = [d for d in res["all_decisions"] if d.timestamp == int(owner_time.value // 10**6)]
    lo, hi = int(_ts("2026-09-15").value // 10**6), int(_ts("2026-11-01").value // 10**6)
    shorts = [decision_brief(d) for d in res["all_decisions"]
              if d.timestamp is not None and lo <= d.timestamp < hi and d.action == "enter" and d.side == "short"]
    short_trades = [t for t in res["ledger"].trades if t.side == "short" and t.entry_time >= "2026-09-15"]
    anchored = run_anchored(profile=profile, frames=res["frames"], anchor_bar=owner_bar, side="short", symbol=symbol,
                            split=split, rule=RULE)
    decs = anchored["decisions"]
    events = [{"candle_close": d.candle_close, "action": d.action, "close": d.context.get("values", {}).get("close"),
               "reasons": [r for r in d.reasons if r.startswith(("add_", "exit_", "partial", "mlrsi_", "info_", "hold_beyond"))],
               "notional": d.notional}
              for d in decs[1:] if d.action in ("add_layer", "reduce", "exit") or any(r.startswith(("add_rejected", "info_phase")) for r in d.reasons)]
    out: Dict[str, Any] = {
        "trigger_tf": tf,
        "owner_bar": {"open": owner_time.isoformat(), "close_time": (owner_time + timedelta(milliseconds=TIMEFRAME_MS[tf])).isoformat(),
                      "close": float(trig["close"].iloc[owner_bar]), "owner_price": OWNER_PRICE},
        "state_at_owner_bar": decision_brief(hit[0]) if hit else None,
        "model_own_shorts": shorts[:6],
        "model_own_short_trades": [{"entry": t.entry_time, "exit": t.exit_time, "reason": t.exit_reason, "layers": t.n_layers,
                                    "r_net": t.r_net, "pnl_net_usdt": t.pnl_net_usdt} for t in short_trades[:8]],
        "anchored": {"entry": decision_brief(decs[0]), "events": events[:40], "liquidations": anchored["liquidations"]},
    }
    trades = anchored["trades"]
    if trades and trades[0].exit_reason != "end_of_data":
        t = trades[0]
        out["anchored"]["exit"] = {"code": t.exit_reason, "candle": t.exit_time, "price": t.exit_price, "pnl_net_usdt": t.pnl_net_usdt,
                                   "r_net": t.r_net, "n_layers": t.n_layers, "partial_takes": t.partial_takes}
    oe = anchored["open_at_end"]
    if oe is not None:
        r_unit = oe["r_unit_usdt"] or float("nan")
        out["anchored"]["still_open_at_end"] = {
            **{k: oe[k] for k in ("n_layers", "avg_price", "last_close", "unrealized_gross_usdt", "entry_costs_usdt", "funding_usdt",
                                  "exit_cost_estimate_usdt", "unrealized_net_usdt", "invalidation")},
            "r_unit_usdt": r_unit, "unrealized_net_r": round(oe["unrealized_net_usdt"] / r_unit, 3) if r_unit else None,
            "layer1_move_pct": round((OWNER_PRICE - oe["last_close"]) / OWNER_PRICE * 100.0, 2),
            "partial_takes": trades[0].partial_takes if trades else [],
        }
    return out


def owner_md(key: str, rep: Dict[str, Any]) -> List[str]:
    ob, s, a = rep["owner_bar"], rep["state_at_owner_bar"], rep["anchored"]
    md = [f"### {key} ({rep['trigger_tf']}) — `owner_bar` {ob['open'][:16]} close {ob['close']:.2f} (owner ~{ob['owner_price']:.0f})", ""]
    if s:
        md.append(f"* Machine there: state **{s['state']}**, alert {s['alert_side']}, phase {s['phase']}, bbwp {_f(s['bbwp'], 1)}, "
                  f"verde {_f(s['verde'], 2)}, guardian {s['guardian_bias']}, ML RSI trigger {s['mlrsi_regime']} / guardian "
                  f"{s['ctx_mlrsi_regime']}, reasons {', '.join(s['reasons'][:4])}.")
    if rep["model_own_short_trades"]:
        md.append("* Model's own shorts Sep-Oct 2026: " + "; ".join(
            f"{t['entry'][:16]} -> {t['exit'][:16]} {t['reason']} ({t['layers']} layers, {t['r_net']:.2f} R, {t['pnl_net_usdt']:.1f} USDT)"
            for t in rep["model_own_short_trades"]))
    else:
        md.append("* Model's own shorts Sep-Oct 2026: none.")
    e = a["entry"]
    line = (f"* **Anchored replay**: layer 1 {e['notional']} USDT at {e['close']}, invalidation {e['invalidation']} ({e['invalidation_source']}), "
            f"1R {e['one_r_usdt']} USDT, liq {_f(e['liquidation_price'], 0)}. Events: " + ("; ".join(
                f"{x['candle_close'][:16]} {x['action']} {','.join(x['reasons'][:3])}" for x in a["events"][:12]) or "none") + ".")
    if "exit" in a:
        x = a["exit"]
        line += (f" **EXIT {x['code']}** at {x['candle'][:16]} price {x['price']}: net {x['pnl_net_usdt']} USDT = **{x['r_net']:.2f} R** "
                 f"({x['n_layers']} layers, {len(x['partial_takes'])} partial takes).")
    if "still_open_at_end" in a:
        o = a["still_open_at_end"]
        line += (f" **Still open at {o['last_close']}**: {o['n_layers']} layer(s), avg {_f(o['avg_price'], 2)}, move on layer 1 "
                 f"{o['layer1_move_pct']}%, {len(o['partial_takes'])} partial take(s), unrealized gross {o['unrealized_gross_usdt']} USDT, "
                 f"net of costs/funding/exit estimate {o['unrealized_net_usdt']} USDT (**{_f(o['unrealized_net_r'], 2)} R**).")
    md += [line, ""]
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
    p.add_argument("--only", nargs="*", default=None, help="subset of runs, e.g. snipper:R4")
    p.add_argument("--no-sweep", action="store_true", help="skip the leverage sweep")
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
    cells: Dict[str, Any] = {}
    owner: Dict[str, Any] = {}
    repaint: Dict[str, Any] = {}
    for key, spec in RUNS.items():
        if args.only and key not in args.only:
            continue
        cells[key] = run_one(key, spec["profile"], {}, args, loader, start, end, split)
        res = cells[key].pop("_res")
        if spec["profile"] in ("pro", "snipper"):
            owner[key] = owner_replay(spec["profile"], res, args.symbol, split)
            tf = res["timeframes"]["trigger"]
            repaint[tf] = repaint_report(res["frames"][tf]["close"], MlRsiParams(), tail=3000 if tf == "1h" else 1500)
    sweep: Dict[str, Any] = {}
    if not args.no_sweep and PRIMARY_SWEEP in cells:
        for lev in LEVERAGE_SWEEP:
            key = f"{PRIMARY_SWEEP}@{lev:g}x"
            sweep[key] = run_one(key, RUNS[PRIMARY_SWEEP]["profile"], {"leverage": lev}, args, loader, start, end, split)
            sweep[key].pop("_res")
    ladder = {**({PRIMARY_SWEEP: cells[PRIMARY_SWEEP]} if PRIMARY_SWEEP in cells else {}), **sweep}
    passing = [k for k, c in ladder.items() if c["go"]]
    proposal = passing[0] if passing else None  # ordered: 10x first, then the sweep downwards

    ref = round2_reference(out_dir)
    report = {
        "prereg": "docs/PREREG_IMPULSOS_v2_r4.md", "rule_version": RULE_VERSION, "model": "sequential", "rule": RULE,
        "symbol": args.symbol, "exchange": args.exchange, "start": start.isoformat(), "end_exclusive": end.isoformat(),
        "split": split.isoformat(), "manifest": manifest, "cells": cells, "leverage_sweep": sweep, "go_runs": passing,
        "proposal": proposal, "round2_reference": ref, "owner_short": owner, "mlrsi_repaint": repaint,
        "cost_model": "E16 fee 0.10% + slip 0.05% per layer per side (also on partial takes); funding 0.01%/8h on total "
                      "notional; liquidation intrabar (wick) — cross on the wallet (pro), isolated on the position margin "
                      "at mmr 0.56% (snipper); 1R = layer-1 risk USDT at the original qty",
    }
    out_path = out_dir / f"r4_impulse_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    md: List[str] = [
        "# Impulsos v2 — round 4b backtest results (`impulse-2.2.0`: exits without phase_lost; PRO 5x cross + SNIPPER 10x isolated)", "",
        f"Protocol: `docs/PREREG_IMPULSOS_v2_r4.md` (frozen before this run). Run {stamp} in the lab service `backtest`, "
        f"harness `scripts/run_impulse_backtest_r4.py`. Raw JSON (every trade, partial takes, sweep, owner replay): `{out_path.name}`.", "",
        "## Data manifest", "", "| TF | rows | first open | last open | gaps | sha256 (12) | source |", "|---|---|---|---|---|---|---|",
    ]
    for tf, m in manifest.items():
        md.append(f"| {tf} | {m['rows']} | {m['first_open'][:16]} | {m['last_open'][:16]} | {m['gaps']} | `{m['sha256'][:12]}` | {m['source']} |")
    md += ["", "## Cells (1R = layer-1 risk = 2 % E0; IS 2024-11 -> 2025-12, OOS 2026-01 -> 2026-10)", "",
           f"r4 verdict: GO iff n >= {GO_MIN_N}, n_oos >= {GO_MIN_N_OOS}, expectancy OOS > 0, PF >= {GO_MIN_PF}, liquidations 0, "
           f"max DD (cumulative net USDT of the cell) < {GO_MAX_DD_PCT:.0f} % of the start. r2 §6 = round-2 R-based verdict, for continuity.", ""]
    md += CELL_HEADER
    for key, c in cells.items():
        for side, s in c["sides"].items():
            md.append(cell_row(f"{c['params']['trigger_tf']} {side} **{key}** ({c['params']['leverage']:g}x {c['params']['margin_mode']}, "
                               f"{c['params']['equity_usdt']:g} USDT)", s["metrics"], s["usdt"], s["verdict_r4"], s["verdict_r2"]))
    md += ["", "## Book level (one ledger per run, long + short)", "",
           "| run | tf | lev | decisions (alert / enter / add / reduce / exit) | trades | avg layers | >= 2 layers | partial takes | equity final | return | max DD equity USDT (%) | max exposure | liquidations | exit mix | info_phase_lost candles |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, c in {**cells, **sweep}.items():
        b, a = c["book"], c["decisions"]
        md.append(f"| {key} | {c['params']['trigger_tf']} | {c['params']['leverage']:g}x {c['params']['margin_mode']} | {a.get('alert', 0)} / "
                  f"{a.get('enter', 0)} / {a.get('add_layer', 0)} / {a.get('reduce', 0)} / {a.get('exit', 0)} | {b['n']} | {b['avg_layers']} | "
                  f"{c['multi_layer_trades']} | {c['partial_takes']} | {b['equity_final']} | {b['return_pct']}% | "
                  f"{b['max_drawdown_equity_usdt']} ({b['max_drawdown_equity_pct']}%) | {b['max_exposure_x']}x | {b['liquidations']} | "
                  f"{b['exit_reasons']} | {c['info_reasons'].get('info_phase_lost', 0)} |")
    bh = ", ".join(f"{k} {c['buy_and_hold_pct']}%" for k, c in cells.items())
    md += ["", f"Buy-and-hold over the window: {bh}."]
    if sweep:
        md += ["", "## Leverage sweep of `snipper:R4` (same signals; only margin and liquidation distance change)", "",
               "| run | liquidations | book return | max DD equity | long: n / exp OOS / PF / DD% / verdict | short: n / exp OOS / PF / DD% / verdict | GO |",
               "|---|---|---|---|---|---|---|"]
        for key, c in ladder.items():
            parts = []
            for side in ("long", "short"):
                s = c["sides"][side]
                parts.append(f"{s['metrics']['all'].get('n', 0)} / {_f(s['metrics'][BLOCK_OOS].get('expectancy_R'))} / "
                             f"{_f(s['metrics']['all'].get('profit_factor'), 2)} / {s['usdt']['max_drawdown_pct_initial']}% / {s['verdict_r4']['verdict']}")
            md.append(f"| {key} | {c['liquidations']} | {c['book']['return_pct']}% | {c['book']['max_drawdown_equity_pct']}% | "
                      f"{parts[0]} | {parts[1]} | {'**GO**' if c['go'] else 'no'} |")
        md += ["", f"**Pre-registered fallback**: highest leverage whose BOTH cells are GO: "
                   f"{'**' + proposal + '**' if proposal else '**none** (no leverage in {10x, 7x, 5x, 3x, 2x, 1x} passes)'}."]
    md += ["", "## Reference: round 2-3 (`impulse-2.1.0`, phase_lost exit, time stop; same window, same costs)", ""]
    if ref:
        md += ["| run | side | n (OOS) | exp. R net | exp. OOS | PF | win | max DD R | r2 verdict | book return | book DD | exit mix |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for key, r in ref.items():
            if key == "file":
                continue
            for side in ("long", "short"):
                s = r[side]
                md.append(f"| {key} | {side} | {s['n']} ({s['n_oos']}) | {_f(s['expectancy_R'])} | {_f(s['expectancy_oos'])} | {_f(s['profit_factor'], 2)} | "
                          f"{(s['win_rate'] or 0) * 100:.0f}% | {_f(s['max_drawdown_R'], 1)} | {s['verdict']} | {r['book']['return_pct']}% | "
                          f"{r['book']['max_drawdown_equity_pct']}% | {r['book']['exit_reasons']} |")
        md.append(f"\nSource: `{ref['file']}`.")
    else:
        md.append("No `r2_sequential_*.json` found in the results dir.")
    md += ["", "## Follower windows used (IS fit, frozen)", ""]
    for key, c in cells.items():
        md.append(f"* {key}: {c['params']['confirm_window_bars']} (ttl {max(c['params']['confirm_window_bars'].values())}), "
                  f"tf_status {c['tf_status']}, first decision {c['first_bar'][:16]}")
    md += ["", "## ML RSI repaint (causal vs TV-anchored window, percentile thresholds)", ""]
    for tf, r in repaint.items():
        md.append(f"* {tf}: {r['bars']} bars {r.get('first', '')[:10]} -> {r.get('last', '')[:10]}: upper mean |Δ| {r['upper_abs_diff_mean']} "
                  f"(max {r['upper_abs_diff_max']}), lower mean |Δ| {r['lower_abs_diff_mean']} (max {r['lower_abs_diff_max']}), "
                  f"regime disagreement {r['regime_disagreement_pct']}%, last bar identical {r['last_bar_identical']}.")
    if owner:
        md += ["", "## §R2.g — the owner's short (82450, 2026-10-09) replayed with the NEW chain (one trade; validates nothing)", ""]
        for key, rep in owner.items():
            md += owner_md(key, rep)
    text = "\n".join(md)
    print(text)
    if args.md_out:
        Path(args.md_out).write_text(text + "\n")
        print(f"[out] {args.md_out}")
    print(f"[out] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
