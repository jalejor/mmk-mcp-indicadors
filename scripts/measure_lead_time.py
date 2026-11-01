#!/usr/bin/env python3
"""Lead-time of leader / follower events before price moves (impulsos-v2 round 2).

OFFLINE: reads the OHLCV cache JSON directly (no exchange, no Mongo). Fit on
IS only; OOS is reported apart, labelled, as a stability check. Run in the lab:

    docker compose --profile backtest run --rm backtest \
        python scripts/measure_lead_time.py [--horizon 10 --k-atr 2.0 --max-lead 12]

Writes /data/results/lead_time_{tf}_{is,oos}.json and docs/impulsos-v2-lead-time.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from controllers.metrics.impulse_backtest import ohlcv_sha256, rows_to_frame  # noqa: E402
from controllers.metrics.impulse_lead_time import (  # noqa: E402
    EVENT_SPECS,
    WINDOW_BOUNDS,
    LeadTimeParams,
    follower_window,
    measure,
)
from controllers.metrics.indicators_service import IndicatorsService  # noqa: E402

BLOCKS = {"is": ("2024-11-01", "2026-01-01"), "oos": ("2026-01-01", "2026-11-01")}
SIDE = {1: "long", -1: "short", 0: "any"}


def _f(v: Any, nd: int = 1) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def enriched(cache_dir: str, tf: str) -> pd.DataFrame:
    meta = json.loads((Path(cache_dir) / f"bitget_BTC-USDT_{tf}.json").read_text())
    raw = rows_to_frame(meta["rows"])
    svc = IndicatorsService(raw, bbwp_definition="tv")
    svc.calculate_all()
    return svc.df


def event_table(tf: str, res: Dict[str, Dict[str, Any]]) -> List[str]:
    out = [
        f"### {tf} — lead time per event (lead = move start - event bar, in {tf} candles)",
        "",
        "| event | role | side | IS n | IS hit rate | IS base rate | IS lead median | IS p25 | IS p75 "
        "| OOS n | OOS hit rate | OOS base rate | OOS lead median | OOS p75 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for spec in EVENT_SPECS:
        e_is, e_oos = res["is"]["events"][spec.name], res["oos"]["events"][spec.name]
        side = SIDE[spec.side]
        br_is, br_oos = res["is"]["base_rate"][side], res["oos"]["base_rate"][side]
        out.append(
            f"| `{spec.name}` | {spec.role} | {side} | {e_is['n']} | {_f(e_is['hit_rate'], 2)} | {br_is:.2f} | "
            f"{_f(e_is['lead']['median'])} | {_f(e_is['lead']['p25'])} | {_f(e_is['lead']['p75'])} | "
            f"{e_oos['n']} | {_f(e_oos['hit_rate'], 2)} | {br_oos:.2f} | {_f(e_oos['lead']['median'])} | "
            f"{_f(e_oos['lead']['p75'])} |"
        )
    return out


EDGE_MIN_N = 20  # reading only: events with fewer IS occurrences are anecdotal
EDGE_MIN_LIFT = 0.10  # reading only: hit rate - base rate


def reading(tf: str, res: Dict[str, Dict[str, Any]]) -> List[str]:
    """Mechanical reading: which events beat the chance rate on IS AND OOS."""
    beats = []
    for spec in EVENT_SPECS:
        side = SIDE[spec.side]
        ok = True
        for block in ("is", "oos"):
            e = res[block]["events"][spec.name]
            if e["n"] < EDGE_MIN_N or e["hit_rate"] is None or e["hit_rate"] - res[block]["base_rate"][side] < EDGE_MIN_LIFT:
                ok = False
        if ok:
            beats.append(f"`{spec.name}`")
    return [
        f"**Reading ({tf})**: events with n >= {EDGE_MIN_N} AND hit rate >= base rate + {EDGE_MIN_LIFT:.2f} "
        f"on BOTH IS and OOS: {', '.join(beats) if beats else '**none**'}. "
        "A hit rate at the base rate means the event says nothing about WHEN a move starts.",
    ]


def lag_table(tf: str, res: Dict[str, Dict[str, Any]]) -> List[str]:
    lo, hi = WINDOW_BOUNDS.get(tf, (2, 8))
    out = [
        f"### {tf} — lag follower - leader (candles) for pairs preceding the SAME move",
        "",
        "Negative = the follower fired first. `W proposal` = clamp(ceil(IS pooled p75), "
        f"{lo}, {hi}) — **PROPOSAL, pending the trading spec**.",
        "",
        "| leader | follower | IS pairs | IS median | IS p75 | IS follower first % | OOS pairs | OOS median | OOS p75 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for leader, block in res["is"]["lag_follower_minus_leader"].items():
        oos_block = res["oos"]["lag_follower_minus_leader"][leader]
        for fol, row in block["followers"].items():
            o = oos_block["followers"].get(fol, {})
            out.append(
                f"| `{leader}` | `{fol}` | {row['n_pairs']} | {_f(row['median'])} | {_f(row['p75'])} | "
                f"{_f(row['follower_first_pct'])} | {o.get('n_pairs', 0)} | {_f(o.get('median'))} | {_f(o.get('p75'))} |"
            )
        pooled, opooled = block["pooled"], oos_block["pooled"]
        w = follower_window(pooled["p75"], lo, hi)
        out.append(
            f"| **`{leader}`** | **pooled** (W proposal = **{_f(w)}**) | {pooled['n_pairs']} | {_f(pooled['median'])} | "
            f"{_f(pooled['p75'])} | | {opooled['n_pairs']} | {_f(opooled['median'])} | {_f(opooled['p75'])} |"
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache-dir", default="/data/ohlcv")
    ap.add_argument("--out-dir", default="/data/results")
    ap.add_argument("--md-out", default="/app/docs/impulsos-v2-lead-time.md")
    ap.add_argument("--timeframes", nargs="+", default=["4h", "1d"])
    ap.add_argument("--horizon", type=int, default=10, help="H: bars ahead for a move")
    ap.add_argument("--k-atr", type=float, default=2.0, help="K: move size in ATR14")
    ap.add_argument("--max-lead", type=int, default=12, help="L: max bars from event to move start")
    ap.add_argument("--min-lead", type=int, default=-2)
    args = ap.parse_args()

    p = LeadTimeParams(horizon=args.horizon, k_atr=args.k_atr, max_lead=args.max_lead, min_lead=args.min_lead)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md: List[str] = [
        "# Impulsos v2 — lead-time of leaders vs followers (round 2 input)",
        "",
        "Generated by `scripts/measure_lead_time.py` (module `controllers/metrics/impulse_lead_time.py`),",
        "offline on the bitget BTC/USDT OHLCV cache, closed candles, indicators from",
        "`IndicatorsService(bbwp_definition='tv')`. Owner decision 2: Konkorde and BBWP lead,",
        "AO / ADX / MACD / RSI confirm.",
        "",
        "**Fit scope**: the follower window is fitted on **IS 2024-11-01 -> 2025-12-31 only**",
        "(declared fit). OOS 2026-01-01 -> 2026-10-31 is shown apart for stability, never fitted.",
        "",
        f"**Move** (look-ahead label): start m long if max(close[m+1..m+{p.horizon}]) - close[m] >= "
        f"{p.k_atr} x ATR14[m] and no accepted long start in the {p.horizon} bars before (mirror short).",
        f"**Lead** = m - j for the nearest same-side start with {p.min_lead} <= m - j <= {p.max_lead} "
        "(side-less `bbwp_*`: either side); none = miss. `base rate` = share of ALL bars of the block",
        "that would hit by the same rule — an event is informative only if its hit rate beats it.",
        "",
        "Events: leaders `konkorde_zero_cross_*` (verde crosses 0), `konkorde_turn_*` (verde crosses",
        "media), `bbwp_ignition` (min BBWP of the last 10 bars <= 30, BBWP crosses 50 up),",
        "`bbwp_red_turn` (BBWP[j-1] >= 90, one-bar drop >= 8, side-less). Followers: AO zero cross",
        "and slope turn, E1 `adx_turn_up` onset with the dominant DI as side, MACD/signal cross, RSI14",
        "cross 50, RSI exit 30 / 70.",
        "",
        "Caveat on the base rate: with this move definition a move starts every ~25 4h bars per",
        "side, so the [-2, L] window catches one by chance on ~half the bars. Hit rates near the base",
        "rate (most rows below) mean NO event, leader or follower, times move starts better than a",
        "random bar; the lag table then describes co-occurrence, not a proven lead.",
        "",
    ]
    manifest: Dict[str, Any] = {}
    for tf in args.timeframes:
        df = enriched(args.cache_dir, tf)
        manifest[tf] = {"rows": len(df), "first": df.index[0].isoformat(), "last": df.index[-1].isoformat(),
                        "sha256": ohlcv_sha256(df[["timestamp", "open", "high", "low", "close", "volume"]])}
        res: Dict[str, Dict[str, Any]] = {}
        for block, (a, b) in BLOCKS.items():
            mask = ((df.index >= pd.Timestamp(a, tz="UTC")) & (df.index < pd.Timestamp(b, tz="UTC")))
            r = measure(df, mask, p)
            r.update({"timeframe": tf, "block": block, "window": [a, b],
                      "label": "IS (fit)" if block == "is" else "OOS (stability only, not fitted)",
                      "data": manifest[tf]})
            res[block] = r
            path = out_dir / f"lead_time_{tf}_{block}.json"
            path.write_text(json.dumps(r, indent=2))
            print(f"[out] {path}", flush=True)
        md += [f"## {tf}", "",
               f"Bars IS {res['is']['bars']} / OOS {res['oos']['bars']}; move starts IS "
               f"{res['is']['move_starts']} / OOS {res['oos']['move_starts']}.", ""]
        md += event_table(tf, res) + [""] + reading(tf, res) + [""] + lag_table(tf, res) + [""]
    md += ["## Data", "", "```json", json.dumps(manifest, indent=2), "```", ""]
    Path(args.md_out).write_text("\n".join(md))
    print(f"[out] {args.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
