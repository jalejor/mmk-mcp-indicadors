#!/usr/bin/env python3
"""Impulsos-v2 ROUND 7 runner — multi-asset REPLICATION of the frozen 2.3.0 chain (no new rule).

Executes `docs/PREREG_IMPULSOS_v2_r7.md` on bitget spot frames of a FIXED universe of 9 assets
(pre-registered by open interest of the Bitget USDT perps, see the prereg §3). Lab:

    docker compose --profile backtest run --rm backtest \
        python scripts/run_impulse_backtest_r7.py --md-out /app/docs/impulsos-v2-backtest-r7.md

Owner decision 2026-11-01: the strategy is for ANY asset where it applies, not only BTC. Goal:
n above 30 per pooled cell and a replicable edge, or its absence, with the GO corrected for the
number of cells looked at. Per profile (`pro` 4h 5x cross 1300 USDT; `snipper` 1h, reference
book 5x cross and the 2.2.0 book 10x isolated, 1700 USDT), per entry (`base`, `adx_turn`,
`bbwp_fresh_blue`) and per trigger-gate reading (`spec` = rule doc as written, `asrun` = rounds
4b/5, E20) it runs one book per asset, same machine, same frozen exit chain, same costs.

Cells: pooled over the 8 NEW assets (primary family, Holm alpha 0.05), pooled over all 9
(secondary), per asset (Benjamini-Hochberg q 0.10), always long and short apart. Verdict per
cell = round-4 mechanical gate AND the corrected one-sided cluster-bootstrap p of the OOS
expectancy (`impulse_multi.verdict_r7`). BTC cells must reproduce round 6 trade for trade.
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

import pandas as pd  # noqa: E402

from controllers.metrics.impulse_backtest import BLOCK_IS, BLOCK_OOS, load_ohlcv, split_metrics  # noqa: E402
from controllers.metrics.impulse_multi import (  # noqa: E402
    ASSET_Q,
    PRIMARY_ALPHA,
    benjamini_hochberg,
    holm,
    leave_one_out,
    p_positive,
    per_symbol_breakdown,
    pooled_drawdown,
    symbol_of,
    verdict_r7,
)
from run_impulse_backtest_r4 import _date, _f, usdt_drawdown, verdict_r4  # noqa: E402
from run_impulse_backtest_r5 import BASE, run_variant  # noqa: E402

DEFAULT_EXCHANGE = "bitget"
DEFAULT_START = "2024-11-01"
DEFAULT_END = "2026-10-31"
DEFAULT_SPLIT = "2026-01-01"
RULE_VERSION = "impulse-2.3.0"
REPLICATION_VERSION = "impulse-2.3.0-r7"  # label of every run that is not the rule doc on its own book

# Prereg r7 §3 — FIXED universe: top 9 Bitget USDT-M perps by open interest (USDT) among crypto-native
# underlyings with bitget SPOT 1d candles before 2023-01-01 (public probe 2026-11-01 ~16:45Z, recorded there).
UNIVERSE: Sequence[str] = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT", "NEAR/USDT", "BNB/USDT", "LINK/USDT", "ADA/USDT")
SEEN: Sequence[str] = ("BTC/USDT",)  # used in rounds 1-6 to choose the filters -> not a replication asset
NEW_ASSETS: Sequence[str] = tuple(s for s in UNIVERSE if s not in SEEN)

ENTRIES: Sequence[str] = (BASE, "adx_turn", "bbwp_fresh_blue")
GATES: Dict[str, Dict[str, Any]] = {"spec": {}, "asrun": {"mlrsi_gate": False}}  # E20: rule doc vs rounds 4b/5
PRIMARY_GATE = "spec"
BOOKS: Dict[str, Dict[str, Dict[str, Any]]] = {
    "pro": {"pro5": {}},  # 1300 USDT, 5x cross (the rule doc's PRO book)
    "snipper": {
        "cross5": {"leverage": 5.0, "margin_mode": "cross", "maintenance_margin_rate": 0.0056},  # owner's book, GO reference (r6 §6 B)
        "iso10": {},  # the 2.2.0 snipper book: 1700 USDT, 10x isolated, mmr 0.56 %
    },
}
REFERENCE_BOOK = {"pro": "pro5", "snipper": "cross5"}
PROFILES: Sequence[str] = ("pro", "snipper")

# round-6 cells that the BTC-only trades of a round-7 run must reproduce (continuity, prereg §6 D)
R6_CONTINUITY: Dict[str, str] = {
    "pro:base:spec:pro5": "pro:A_spec_on",
    "pro:base:asrun:pro5": "pro:A_on",
    "snipper:base:spec:iso10": "snipper:A_spec_on",
    "snipper:base:asrun:iso10": "snipper:A_on",
    "snipper:base:asrun:cross5": "snipper:B_risk_cross5:base",
    "snipper:bbwp_fresh_blue:asrun:iso10": "snipper:B_risk_iso10:bbwp_fresh_blue",
    "snipper:bbwp_fresh_blue:asrun:cross5": "snipper:B_risk_cross5:bbwp_fresh_blue",
    "snipper:adx_turn:asrun:iso10": "snipper:B_risk_iso10:adx_turn",
    "snipper:adx_turn:asrun:cross5": "snipper:B_risk_cross5:adx_turn",
}


def run_key(profile: str, entry: str, gate: str, book: str) -> str:
    return f"{profile}:{entry}:{gate}:{book}"


def pooled_cell(run: Dict[str, Any], symbols: Sequence[str], side: str) -> Dict[str, Any]:
    """One pooled cell: trades of `symbols` on `side`; DD on the pooled start (one book per asset);
    liquidations = those of the family's books (both sides, as in round 4)."""
    trades = [t for t in run["_trades"] if t.side == side and symbol_of(t) in symbols]
    e0 = float(run["params"]["equity_usdt"])
    present = [s for s in symbols if s in run["per_symbol"]]
    liq = sum(int(run["per_symbol"][s]["liquidations"]) for s in present)
    m = split_metrics(trades)
    dd = pooled_drawdown(trades, e0 * len(present))
    oos = [t for t in trades if t.block == BLOCK_OOS]
    return {
        "symbols": list(present), "side": side, "metrics": m, "usdt": dd, "liquidations": liq,
        "verdict_r4": verdict_r4(m, dd, liq), "p_oos": p_positive(oos), "p_all": p_positive(trades),
        "by_symbol": per_symbol_breakdown(trades, BLOCK_OOS), "leave_one_out": leave_one_out(trades, BLOCK_OOS),
        "_trades": trades,
    }


def asset_cell(run: Dict[str, Any], symbol: str, side: str) -> Dict[str, Any]:
    trades = [t for t in run["_trades"] if t.side == side and symbol_of(t) == symbol]
    e0 = float(run["params"]["equity_usdt"])
    liq = int(run["per_symbol"][symbol]["liquidations"]) if symbol in run["per_symbol"] else 0
    m = split_metrics(trades)
    dd = usdt_drawdown(trades, e0)
    oos = [t for t in trades if t.block == BLOCK_OOS]
    return {"symbol": symbol, "side": side, "metrics": m, "usdt": dd, "liquidations": liq,
            "verdict_r4": verdict_r4(m, dd, liq), "p_oos": p_positive(oos), "_trades": trades}


def r6_reference(out_dir: Path) -> Dict[str, Any]:
    paths = sorted(glob.glob(str(out_dir / "r6_impulse_*.json")))
    if not paths:
        return {}
    data = json.loads(Path(paths[-1]).read_text())
    ref: Dict[str, Any] = {"file": Path(paths[-1]).name}
    for key, cell in data.get("cells", {}).items():
        ref[key] = {side: {"n": s["metrics"]["all"].get("n", 0), "pnl_net_usdt": s["usdt"]["pnl_net_usdt"]}
                    for side, s in cell["sides"].items()}
    return ref


def continuity(run: Dict[str, Any], ref_cell: Dict[str, Any], symbol: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"same": True}
    for side in ("long", "short"):
        st = [t for t in run["_trades"] if t.side == side and symbol_of(t) == symbol]
        got = {"n": len(st), "pnl_net_usdt": round(sum(t.pnl_net_usdt for t in st), 2)}
        out[side] = {"r7": got, "r6": ref_cell[side]}
        if got != {"n": ref_cell[side]["n"], "pnl_net_usdt": ref_cell[side]["pnl_net_usdt"]}:
            out["same"] = False
    return out


def _pf(trades: Sequence[Any]) -> str:
    gains = sum(float(t.r_net) for t in trades if t.r_net > 0)
    losses = -sum(float(t.r_net) for t in trades if t.r_net < 0)
    return f"{gains / losses:.2f}" if losses > 0 else ("inf" if gains > 0 else "—")


CELL_HEADER = [
    "| cell | side | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | win | max DD USDT (% start) | net USDT | liq | p OOS>0 | corrected | r4 gate | **r7 verdict** |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
]


def cell_row(label: str, c: Dict[str, Any], corrected: Optional[Dict[str, Any]], v7: Dict[str, Any]) -> str:
    a, i, o = c["metrics"]["all"], c["metrics"][BLOCK_IS], c["metrics"][BLOCK_OOS]
    r4 = c["verdict_r4"]["verdict"] + (f" ({'; '.join(c['verdict_r4']['failed'])})" if c["verdict_r4"]["failed"] else "")
    tag = f"**{v7['verdict']}**" + (f" ({'; '.join(v7['failed'])})" if v7["failed"] and v7["verdict"] != "INCONCLUSIVE" else "")
    if corrected is None:
        corr = "—"
    elif corrected.get("method") == "holm":
        corr = f"Holm p_adj {_f(corrected['p_adj'], 4)} (m={corrected['m']})"
    else:
        corr = f"BH q {_f(corrected['q_value'], 4)} (m={corrected['m']})"
    if not a.get("n"):
        return f"| {label} | {c['side']} | 0 (0/0) | — | — | — | — | — | — | — | — | {c['liquidations']} | — | {corr} | {r4} | {tag} |"
    ci = a["bootstrap"]["ci95_cluster"]
    return (f"| {label} | {c['side']} | {a['n']} ({i.get('n', 0)}/{o.get('n', 0)}) | {_f(a['expectancy_R'])} | [{ci[0]:.3f}, {ci[1]:.3f}] | "
            f"{_f(i.get('expectancy_R')) if i.get('n') else '—'} | {_f(o.get('expectancy_R')) if o.get('n') else '—'} | "
            f"{_f(a['profit_factor'], 2)} | {a['win_rate'] * 100:.0f}% | {c['usdt']['max_drawdown_usdt']} ({c['usdt']['max_drawdown_pct_initial']}%) | "
            f"{c['usdt']['pnl_net_usdt']} | {c['liquidations']} | {_f(c['p_oos'], 4)} | {corr} | {r4} | {tag} |")


def book_rows(key: str, run: Dict[str, Any]) -> List[str]:
    rows = []
    for sym, ps in run["per_symbol"].items():
        b = ps["book"]
        blocked = sum(v for k, v in ps["info_reasons"].items() if k.startswith("entry_filter_blocked"))
        rows.append(f"| {key} | {sym} | {b['n']} | {blocked} | {b['avg_layers']} | {b['equity_final']} | {b['return_pct']}% | "
                    f"{b['max_drawdown_equity_usdt']} ({b['max_drawdown_equity_pct']}%) | {b['liquidations']} | {b['funding_usdt']} / {b['cost_usdt']} | "
                    f"{b['exit_reasons']} | {ps['buy_and_hold_pct']}% | {ps['tf_status']} |")
    return rows


BOOK_HEADER = [
    "| run | symbol | trades | entries blocked by the filter | avg layers | equity final | return | max DD equity USDT (%) | liquidations | funding / fees USDT | exit mix | B&H | tf_status |",
    "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
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
    p.add_argument("--tag", default="r7_impulse", help="prefix of the JSON (smoke runs use another tag)")
    p.add_argument("--only-symbols", nargs="*", default=None, help="subset of the universe (smoke = BTC/USDT only)")
    p.add_argument("--only-profiles", nargs="*", default=None)
    p.add_argument("--only-gates", nargs="*", default=None, help="subset: spec asrun")
    args = p.parse_args()

    start, split = _date(args.start), _date(args.split)
    end = _date(args.end) + timedelta(days=1)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = [s for s in UNIVERSE if not args.only_symbols or s in args.only_symbols]
    new_assets = [s for s in NEW_ASSETS if s in symbols]
    profiles = [k for k in PROFILES if not args.only_profiles or k in args.only_profiles]
    gates = [g for g in GATES if not args.only_gates or g in args.only_gates]
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

    loaders = {sym: loader_for(sym) for sym in symbols}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs: Dict[str, Dict[str, Any]] = {}
    for profile in profiles:  # PRO first (owner's order), then SNIPPER
        for entry in ENTRIES:
            for gate in gates:
                for book, book_ov in BOOKS[profile].items():
                    ov: Dict[str, Any] = {**GATES[gate], **book_ov}
                    if gate != PRIMARY_GATE or book != REFERENCE_BOOK[profile] or book_ov:
                        ov["rule_version"] = REPLICATION_VERSION
                    key = run_key(profile, entry, gate, book)
                    print(f"[r7] {key} ...", flush=True)
                    runs[key] = run_variant(profile, entry, symbols, loaders, start, end, split, overrides=ov)

    # ---- cells ------------------------------------------------------------------------------------
    pooled: Dict[str, Dict[str, Any]] = {}  # "<run>|<family>|<side>"
    assets: Dict[str, Dict[str, Any]] = {}  # "<run>|<symbol>|<side>"
    for key, run in runs.items():
        for side in ("long", "short"):
            if new_assets:
                pooled[f"{key}|new8|{side}"] = pooled_cell(run, new_assets, side)
            pooled[f"{key}|all9|{side}"] = pooled_cell(run, symbols, side)
            for sym in symbols:
                assets[f"{key}|{sym}|{side}"] = asset_cell(run, sym, side)

    def is_reference(key: str) -> bool:
        profile, _entry, gate, book = key.split(":")
        return gate == PRIMARY_GATE and book == REFERENCE_BOOK[profile]

    primary_keys = [k for k in pooled if k.endswith(("|new8|long", "|new8|short")) and is_reference(k.split("|")[0])]
    primary_corr = holm({k: pooled[k]["p_oos"] for k in primary_keys}, alpha=PRIMARY_ALPHA)
    asset_keys = [k for k in assets if is_reference(k.split("|")[0]) and k.split("|")[1] in new_assets]
    asset_corr = benjamini_hochberg({k: assets[k]["p_oos"] for k in asset_keys}, q=ASSET_Q)
    # secondary pooled families: informational Holm inside each (never GO-eligible)
    secondary_groups: Dict[str, List[str]] = {}
    for k in pooled:
        if k in primary_corr:
            continue
        run_k, fam, _side = k.split("|")
        profile, _entry, gate, book = run_k.split(":")
        secondary_groups.setdefault(f"{fam}:{gate}:{book}", []).append(k)
    secondary_corr: Dict[str, Dict[str, Any]] = {}
    for grp, keys in secondary_groups.items():
        for k, v in holm({k: pooled[k]["p_oos"] for k in keys}, alpha=PRIMARY_ALPHA).items():
            secondary_corr[k] = {**v, "group": grp}

    verdicts: Dict[str, Dict[str, Any]] = {}
    for k, c in pooled.items():
        if k in primary_corr:
            verdicts[k] = verdict_r7(c["verdict_r4"], primary_corr[k], label="primary new8 (Holm)")
        else:
            verdicts[k] = {**verdict_r7(c["verdict_r4"], None, label="secondary"), "informational": True}
    for k, c in assets.items():
        verdicts[k] = verdict_r7(c["verdict_r4"], asset_corr.get(k), label="per-asset new8 (BH)") if k in asset_corr else \
            {**verdict_r7(c["verdict_r4"], None, label="per-asset informational"), "informational": True}

    ref = r6_reference(out_dir)
    cont = {k: continuity(runs[k], ref[r6k], "BTC/USDT") for k, r6k in R6_CONTINUITY.items() if k in runs and r6k in ref and "BTC/USDT" in symbols}

    # ---- report -----------------------------------------------------------------------------------
    def strip_cell(c: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in c.items() if k != "_trades"}

    def strip_run(c: Dict[str, Any]) -> Dict[str, Any]:
        c = dict(c)
        c.pop("_trades", None)
        c["per_symbol"] = {s: {k: v for k, v in ps.items() if k != "_res"} for s, ps in c["per_symbol"].items()}
        return c

    report = {
        "prereg": "docs/PREREG_IMPULSOS_v2_r7.md", "rule_version": RULE_VERSION, "replication_label": REPLICATION_VERSION,
        "exchange": args.exchange, "start": start.isoformat(), "end_exclusive": end.isoformat(), "split": split.isoformat(),
        "universe": list(symbols), "new_assets": list(new_assets), "seen": list(SEEN), "entries": list(ENTRIES), "gates": gates,
        "books": BOOKS, "reference_book": REFERENCE_BOOK, "manifest": manifest,
        "runs": {k: strip_run(c) for k, c in runs.items()},
        "pooled": {k: strip_cell(c) for k, c in pooled.items()}, "assets": {k: strip_cell(c) for k, c in assets.items()},
        "primary_family": primary_corr, "asset_family": asset_corr, "secondary_families": secondary_corr, "verdicts": verdicts,
        "r6_continuity": cont, "r6_reference_file": ref.get("file"),
        "go_cells": [k for k, v in verdicts.items() if v["verdict"] == "GO"],
        "cost_model": "E16 fee 0.10% + slip 0.05% per layer per side (also on partial takes); funding 0.01%/8h on total "
                      "notional; liquidation intrabar (wick): isolated on the position margin, cross on the wallet; mmr 0.56 % "
                      "in every snipper book; 1R = layer-1 risk USDT at the original qty; bitget SPOT candles as the perp price proxy",
    }
    out_path = out_dir / f"{args.tag}_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    md: List[str] = [
        "# Impulsos v2 — round 7 results (multi-asset replication of the frozen 2.3.0 chain, 9 Bitget perps)", "",
        f"Protocol: `docs/PREREG_IMPULSOS_v2_r7.md` (frozen before this run). Run {stamp} in the lab service `backtest`, "
        f"harness `scripts/run_impulse_backtest_r7.py`. Raw JSON (every trade, cell, family, p-values): `{out_path.name}`. "
        f"Window {args.start} -> {args.end}, IS/OOS split {args.split}. Universe: {', '.join(symbols)} "
        f"(new = replication assets: {', '.join(new_assets) or '—'}; seen in rounds 1-6: {', '.join(s for s in SEEN if s in symbols) or '—'}).", "",
        "## Data manifest", "", "| symbol @ TF | rows | first open | last open | gaps | sha256 (12) | source | s |", "|---|---|---|---|---|---|---|---|",
    ]
    for key, m in manifest.items():
        md.append(f"| {key} | {m['rows']} | {m['first_open'][:16]} | {m['last_open'][:16]} | {m['gaps']} | `{m['sha256'][:12]}` | {m['source']} | {m['seconds']} |")

    def section(title: str, keys: Sequence[str], corr: Dict[str, Dict[str, Any]], note: str) -> None:
        md.extend(["", title, "", note, ""] + CELL_HEADER)
        for k in keys:
            run_k, fam, side = k.split("|")
            md.append(cell_row(f"{run_k} [{fam}]", pooled[k], corr.get(k), verdicts[k]))

    section("## A. PRIMARY pooled cells — 8 new assets, trigger gate as written, reference books (Holm alpha 0.05, m = %d)" % len(primary_corr),
            primary_keys, primary_corr,
            "GO iff r4 gate (n >= 30, n_oos >= 10, exp OOS > 0, PF >= 1.2, liq 0, pooled DD < 35 % of the pooled start) AND Holm-adjusted one-sided "
            "cluster-bootstrap p of the OOS expectancy < 0.05. These are the only GO-eligible pooled cells.")
    sec_keys = [k for k in pooled if k not in primary_corr]
    section("## B. SECONDARY pooled cells — all 9 / as-run gate (E20) / 10x isolated book (informational, never GO-eligible)",
            sec_keys, secondary_corr, "Holm inside each (family, gate, book) group for reading only; the r7 verdict here is NO-GO or INCONCLUSIVE by construction.")

    md += ["", "## C. Per-asset cells — new assets, gate as written, reference books (Benjamini-Hochberg q 0.10, m = %d)" % len(asset_corr), "",
           "ASSET-GO = r4 gate on the asset's own book AND BH q-value < 0.10. An ASSET-GO is a replication candidate, not a paper gate: only a primary pooled GO moves anything.", ""] + CELL_HEADER
    for k in asset_keys:
        run_k, sym, side = k.split("|")
        md.append(cell_row(f"{run_k} · {sym}", assets[k], asset_corr.get(k), verdicts[k]))
    md += ["", "### C2. Per-asset cells, informational (BTC = seen asset; as-run gate; 10x isolated book)", ""] + CELL_HEADER
    for k in assets:
        if k in asset_corr:
            continue
        run_k, sym, side = k.split("|")
        md.append(cell_row(f"{run_k} · {sym}", assets[k], None, verdicts[k]))

    md += ["", "## D. Which assets add / subtract (primary pooled cells; `adds` = removing the asset lowers the pooled expectancy)", "",
           "| cell | side | asset | n (OOS) | sum R | exp. R | exp. OOS | net USDT | pooled exp. without it | pooled exp. OOS without it | verdict |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in primary_keys:
        run_k, _fam, side = k.split("|")
        c = pooled[k]
        for sym, b in c["by_symbol"].items():
            lo = c["leave_one_out"][sym]
            md.append(f"| {run_k} | {side} | {sym} | {b['n']} ({b['n_oos']}) | {b['sum_r']} | {_f(b['exp_r'])} | {_f(b['exp_oos'])} | {b['pnl_net_usdt']} | "
                      f"{_f(lo['exp_without'])} | {_f(lo['exp_oos_without'])} | {'adds' if lo['adds'] else 'subtracts' if lo['adds'] is not None else '—'} |")

    md += ["", "## E. Books (one ledger per run and asset, long + short; gate as written only — as-run books are in the JSON)", ""] + BOOK_HEADER
    for key, run in runs.items():
        if key.split(":")[2] == PRIMARY_GATE:
            md += book_rows(key, run)

    md += ["", "## F. Continuity with round 6 (BTC-only trades of the round-7 runs vs the round-6 cells)", ""]
    if not cont:
        md.append("* not checked (no r6 reference or BTC not in this run).")
    for k, c in cont.items():
        md.append(f"* `{k}` vs r6 `{R6_CONTINUITY[k]}`: **{'identical' if c['same'] else 'DIFFERENT'}** — " + "; ".join(
            f"{side} r7 n {c[side]['r7']['n']} / {c[side]['r7']['pnl_net_usdt']} USDT vs r6 n {c[side]['r6']['n']} / {c[side]['r6']['pnl_net_usdt']} USDT"
            for side in ("long", "short")))
    md += ["", "## G. Follower windows (frozen on BTC, rounds 2 / 4) and context status per asset", ""]
    for profile in profiles:
        run = next((r for k, r in runs.items() if k.startswith(f"{profile}:")), None)
        if run:
            md.append(f"* {profile}: {run['params']['confirm_window_bars']}; tf_status " + "; ".join(
                f"{sym} {ps['tf_status']}" for sym, ps in run["per_symbol"].items()))
    md += ["", f"GO cells: {report['go_cells'] or 'none'}."]
    text = "\n".join(md)
    print(text)
    if args.md_out:
        Path(args.md_out).write_text(text + "\n")
        print(f"[out] {args.md_out}")
    print(f"[out] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
