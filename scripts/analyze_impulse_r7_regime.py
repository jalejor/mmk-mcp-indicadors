#!/usr/bin/env python3
"""Round-8 PRIOR analysis: split the round-7 trades by two PRE-DEFINED regime identifiers.

No re-optimisation, no new run: reads the round-7 result JSON (every trade of every run) and the
cached bitget 1d frames, labels each trade at its ENTRY (trigger candle close) with
`impulse_regime` (R1 own EMA200 1d, R2 BTC EMA200 1d) and tabulates, per primary cell and side,
how the expectancy splits by regime. Lab:

    docker compose --profile backtest run --rm backtest \
        python scripts/analyze_impulse_r7_regime.py --md-out /app/docs/impulsos-v2-r7-regime-split.md

Descriptive only (prereg r8 §2): it can neither GO nor NO-GO anything; it fixes the backtest's
PREDICTION for the three forward books (long-only, short-only, long/short by regime).
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from controllers.metrics.impulse_backtest import BLOCK_OOS, rows_to_frame  # noqa: E402
from controllers.metrics.impulse_multi import cluster_bootstrap_means, p_positive  # noqa: E402
from controllers.metrics.impulse_regime import IDENTIFIERS, RegimeSeries, book_of, label_signal, regime_series  # noqa: E402

PRIMARY_RUNS: Sequence[str] = (
    "snipper:base:spec:cross5", "snipper:adx_turn:spec:cross5", "snipper:bbwp_fresh_blue:spec:cross5",
    "pro:base:spec:pro5", "pro:adx_turn:spec:pro5", "pro:bbwp_fresh_blue:spec:pro5",
)
TRIGGER_TF = {"snipper": "1h", "pro": "4h"}
BOOKS = ("long_only", "short_only", "regime_own", "regime_btc")


class Trade:
    """Duck-typed trade for `impulse_multi` (r_net, cluster, block, pnl_net_usdt, entry_time)."""

    def __init__(self, d: Dict[str, Any], labels: Dict[str, Any]) -> None:
        self.side = d["side"]
        self.r_net = float(d["r_net"])
        self.cluster = d["cluster"]
        self.block = d["block"]
        self.pnl_net_usdt = float(d["pnl_net_usdt"])
        self.entry_time = d["entry_time"]
        self.exit_reason = d["exit_reason"]
        self.symbol = str(d["cluster"]).split("|", 1)[0]
        self.labels = labels
        self.books = book_of(self.side, labels)


def _f(x: Optional[float], nd: int = 3) -> str:
    return "—" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{nd}f}"


def stats(trades: Sequence[Trade]) -> Dict[str, Any]:
    rs = np.array([t.r_net for t in trades], dtype=float)
    if not len(rs):
        return {"n": 0}
    gains, losses = rs[rs > 0].sum(), -rs[rs < 0].sum()
    oos = [t for t in trades if t.block == BLOCK_OOS]
    out = {
        "n": int(len(rs)), "n_oos": len(oos), "sum_r": round(float(rs.sum()), 3), "exp_r": round(float(rs.mean()), 3),
        "exp_oos": round(float(np.mean([t.r_net for t in oos])), 3) if oos else None,
        "pf": round(float(gains / losses), 2) if losses > 0 else None, "win": round(float((rs > 0).mean()), 3),
        "pnl_net_usdt": round(float(sum(t.pnl_net_usdt for t in trades)), 2),
        "p_all": p_positive(trades),
    }
    if len({t.cluster for t in trades}) >= 2:
        boot = cluster_bootstrap_means(trades)
        out["ci95"] = [round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)]
    return out


def diff_ci(a: Sequence[Trade], b: Sequence[Trade]) -> Optional[Dict[str, Any]]:
    """Cluster-bootstrap CI95 of mean(a) - mean(b) (independent resampling of each group)."""
    if len({t.cluster for t in a}) < 2 or len({t.cluster for t in b}) < 2:
        return None
    da = cluster_bootstrap_means(a) - cluster_bootstrap_means(b, seed=43)
    return {"diff": round(float(np.mean([t.r_net for t in a]) - np.mean([t.r_net for t in b])), 3),
            "ci95": [round(float(np.percentile(da, 2.5)), 3), round(float(np.percentile(da, 97.5)), 3)],
            "p_diff_le_0": round(float((da <= 0).mean()), 4)}


def load_regimes(cache_dir: Path, exchange: str, symbols: Sequence[str]) -> Dict[str, RegimeSeries]:
    out: Dict[str, RegimeSeries] = {}
    for sym in symbols:
        path = cache_dir / f"{exchange}_{sym.replace('/', '-')}_1d.json"
        meta = json.loads(path.read_text())
        out[sym] = regime_series(rows_to_frame(meta["rows"]).reset_index(drop=True))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", default=None, help="round-7 result JSON (default: latest r7_impulse_*.json in --out-dir)")
    p.add_argument("--cache-dir", default="/data/ohlcv")
    p.add_argument("--out-dir", default="/data/results")
    p.add_argument("--md-out", default=None)
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    results = args.results or sorted(glob.glob(str(out_dir / "r7_impulse_*.json")))[-1]
    data = json.loads(Path(results).read_text())
    symbols: List[str] = list(data["universe"])
    regimes = load_regimes(Path(args.cache_dir), data["exchange"], symbols)
    btc = regimes["BTC/USDT"]
    start_ms = int(pd.Timestamp(data["start"]).timestamp() * 1000)
    end_ms = int(pd.Timestamp(data["end_exclusive"]).timestamp() * 1000)
    split_ms = int(pd.Timestamp(data["split"]).timestamp() * 1000)

    cells: Dict[str, Dict[str, Any]] = {}
    for run_key in PRIMARY_RUNS:
        run = data["runs"].get(run_key)
        if run is None:
            continue
        profile = run_key.split(":")[0]
        tf = TRIGGER_TF[profile]
        trades: List[Trade] = []
        for side in ("long", "short"):
            for d in run["sides"][side]["trades"]:
                open_ms = int(pd.Timestamp(d["entry_time"]).timestamp() * 1000)
                sym = str(d["cluster"]).split("|", 1)[0]
                trades.append(Trade(d, label_signal(open_ms, tf, regimes.get(sym), btc)))
        cell: Dict[str, Any] = {"trigger_tf": tf, "n": len(trades), "sides": {}, "books": {}}
        for side in ("long", "short"):
            st = [t for t in trades if t.side == side]
            s: Dict[str, Any] = {"all": stats(st)}
            for ident in IDENTIFIERS:
                up = [t for t in st if t.labels[f"regime_{ident}"] == "up"]
                down = [t for t in st if t.labels[f"regime_{ident}"] == "down"]
                s[ident] = {"up": stats(up), "down": stats(down), "up_minus_down": diff_ci(up, down)}
            cell["sides"][side] = s
        for book in BOOKS:
            cell["books"][book] = stats([t for t in trades if t.books[book]])
        cells[run_key] = cell

    regime_share = {
        sym: {"window": rs.share_up(start_ms, end_ms), "is": rs.share_up(start_ms, split_ms), "oos": rs.share_up(split_ms, end_ms)}
        for sym, rs in regimes.items()
    }
    report = {"source": Path(results).name, "identifiers": {
        "own": "asset close > EMA200 (pandas ewm span 200, adjust=True) on the last CLOSED 1d candle at the trigger candle close",
        "btc": "the same rule on BTC/USDT 1d, applied to every asset"},
        "cells": cells, "regime_share_up": regime_share, "books": list(BOOKS)}
    out_path = out_dir / f"r7_regime_split_{Path(results).stem.split('_')[-1]}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    md: List[str] = [
        "# Impulsos v2 — round-7 trades split by two PRE-DEFINED regime identifiers (prior analysis of round 8)", "",
        f"Source: `{Path(results).name}` (round 7, frozen 2.3.0 chain, 9 Bitget perps, window {data['start'][:10]} -> "
        f"{data['end_exclusive'][:10]}, IS/OOS split {data['split'][:10]}). Script `scripts/analyze_impulse_r7_regime.py`; "
        f"raw `{out_path.name}`. Identifiers fixed BEFORE this table existed (`docs/PREREG_IMPULSOS_v2_r8_shadow.md` §3):",
        "", "* **R1 `own`** — the asset's own daily trend: last CLOSED 1d candle at the trigger candle's close, "
        "`close > EMA200` (pandas ewm span 200, adjust=True) -> `up`, else `down`.",
        "* **R2 `btc`** — the same rule on BTC/USDT 1d applied to every asset (BTC as the regime leader).",
        "", "Descriptive only: no cell is GO/NO-GO here. `exp.` = mean net R; CI95 = cluster bootstrap (symbol x month); "
        "`up − down` = difference of the two means with its bootstrap CI95 and the share of resamples where the difference ≤ 0.",
        "", "## 1. Share of the window spent in `up` (per asset; the question is whether the window itself was one regime)", "",
        "| asset | window | IS | OOS |", "|---|---|---|---|",
    ]
    for sym, sh in regime_share.items():
        md.append(f"| {sym} | {_f(sh['window'], 2)} | {_f(sh['is'], 2)} | {_f(sh['oos'], 2)} |")

    md += ["", "## 2. Per primary cell: each side split by regime", "",
           "| cell | side | ident | regime | n (OOS) | exp. R | CI95 | exp. OOS | PF | win | net USDT | up − down [CI95] (p ≤ 0) |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, cell in cells.items():
        for side, s in cell["sides"].items():
            a = s["all"]
            ci = a.get("ci95")
            md.append(f"| {key} | {side} | — | all | {a['n']} ({a.get('n_oos', 0)}) | {_f(a.get('exp_r'))} | "
                      f"{'[%s, %s]' % tuple(ci) if ci else '—'} | {_f(a.get('exp_oos'))} | {_f(a.get('pf'), 2)} | "
                      f"{_f(a.get('win'), 2)} | {a.get('pnl_net_usdt', '—')} | |")
            for ident in IDENTIFIERS:
                d = s[ident]["up_minus_down"]
                dtxt = f"{_f(d['diff'])} [{d['ci95'][0]}, {d['ci95'][1]}] ({d['p_diff_le_0']})" if d else "—"
                for reg in ("up", "down"):
                    r = s[ident][reg]
                    ci = r.get("ci95")
                    md.append(f"| {key} | {side} | {ident} | {reg} | {r['n']} ({r.get('n_oos', 0)}) | {_f(r.get('exp_r'))} | "
                              f"{'[%s, %s]' % tuple(ci) if ci else '—'} | {_f(r.get('exp_oos'))} | {_f(r.get('pf'), 2)} | "
                              f"{_f(r.get('win'), 2)} | {r.get('pnl_net_usdt', '—')} | {dtxt if reg == 'up' else ''} |")

    md += ["", "## 3. The three round-8 books on the round-7 trades (what the backtest PREDICTS for the forward shadow)", "",
           "`regime_own` = longs entered in `up` + shorts entered in `down` by R1; `regime_btc` the same by R2 (informational).", "",
           "| cell | book | n (OOS) | exp. R | CI95 | exp. OOS | PF | win | net USDT | p(exp ≤ 0) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for key, cell in cells.items():
        for book, b in cell["books"].items():
            ci = b.get("ci95")
            md.append(f"| {key} | {book} | {b['n']} ({b.get('n_oos', 0)}) | {_f(b.get('exp_r'))} | "
                      f"{'[%s, %s]' % tuple(ci) if ci else '—'} | {_f(b.get('exp_oos'))} | {_f(b.get('pf'), 2)} | "
                      f"{_f(b.get('win'), 2)} | {b.get('pnl_net_usdt', '—')} | {_f(b.get('p_all'), 4)} |")
    text = "\n".join(md)
    print(text)
    if args.md_out:
        Path(args.md_out).write_text(text + "\n")
        print(f"[out] {args.md_out}")
    print(f"[out] {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
