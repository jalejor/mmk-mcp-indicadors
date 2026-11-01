#!/usr/bin/env python3
"""ML RSI [BackQuant] audit (owner point f, 2026-11-01): port vs Pine, closed-candle parity, regime statistics.

Lab (network needed once for the Binance reference series, cached afterwards):

    docker compose --profile backtest run --rm backtest \
        python scripts/audit_ml_rsi.py --md-out /app/docs/impulsos-v2-ml-rsi-audit.md

What it measures (read-only, no engine change):

1. Parity of the percentile port against the owner's TradingView reading (BINANCE BTC/USDT 1d,
   read on the FORMING candle of 2026-11-01: value 40.07, upper 59.74, lower 44.30) on the
   exchange he reads (binance) and on the lab's exchange (bitget), on the CLOSED 2026-10-31 candle
   and with the 2026-11-01 forming candle appended at several closes. Solves the forming close that
   reproduces 40.07 and checks it against the real 2026-11-01 intraday range: a forming-candle
   reading is reproducible only through that implied price.
2. Threshold method sensitivity: percentile linear interpolation (what the Pine uses) vs nearest
   rank vs the described k-means; with and without the forming value in the 3000-point window.
3. Regime statistics of the GUARDIAN series the engine uses (4h for snipper, 1d for pro, causal
   trailing window): share of bars per colour, flips per 30 days, median run length, share of
   flips that are colour -> contrary colour without passing through gray.
4. Lookahead / alignment: the causal value at bar j does not change when later bars are appended;
   the trigger -> guardian alignment (`searchsorted(close_ms, side='right') - 1`) only ever picks a
   guardian candle that CLOSED at or before the trigger close.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from controllers.metrics.impulse_backtest import TIMEFRAME_MS, fetch_ohlcv_forward, rows_to_frame  # noqa: E402
from controllers.metrics.ml_rsi import MlRsiParams, alma, kmeans3, ml_rsi_frame, regime_of, rsi  # noqa: E402

OWNER = {"ml_rsi": 40.07, "ml_rsi_upper": 59.74, "ml_rsi_lower": 44.30, "exchange": "binance", "symbol": "BTC/USDT",
         "timeframe": "1d", "read_on": "forming candle of 2026-11-01 (UTC day), morning Colombia"}
CLOSED_DAY = "2026-10-31"
FORMING_DAY = "2026-11-01"
PARAMS = MlRsiParams()  # rsi 19, ALMA 4 / sigma 1 / offset 0, percentile 25/75, 3000 points


def _load_cache(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    meta = json.loads(path.read_text())
    return rows_to_frame(meta["rows"])


def _save_cache(path: Path, df: pd.DataFrame, exchange: str, symbol: str, timeframe: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"exchange": exchange, "symbol": symbol, "timeframe": timeframe,
                                "fetched_at": datetime.now(timezone.utc).isoformat(),
                                "rows": df[["timestamp", "open", "high", "low", "close", "volume"]].values.tolist()}))


def fetch_public(exchange_name: str, symbol: str, timeframe: str, since: str, cache_dir: Path, *, refresh: bool) -> pd.DataFrame:
    """Public OHLCV via ccxt (no keys), forward paginated, cached under `cache_dir` (audit files, never the lab's)."""
    path = cache_dir / f"audit_{exchange_name}_{symbol.replace('/', '-')}_{timeframe}.json"
    cached = None if refresh else _load_cache(path)
    if cached is not None and len(cached):
        return cached
    import ccxt  # noqa: WPS433

    ex = getattr(ccxt, exchange_name)({"enableRateLimit": True})
    since_ms = int(pd.Timestamp(since, tz="UTC").timestamp() * 1000)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000) + TIMEFRAME_MS[timeframe]
    rows = fetch_ohlcv_forward(ex.fetch_ohlcv, symbol=symbol, timeframe=timeframe, since_ms=since_ms, end_ms=end_ms, limit=1000)
    df = rows_to_frame(rows)
    _save_cache(path, df, exchange_name, symbol, timeframe)
    return df


def last_closed(df: pd.DataFrame, day: str) -> pd.DataFrame:
    """Frame cut at the candle whose OPEN is `day` (inclusive) — the 1d candle of `day` is treated as closed."""
    cut = pd.Timestamp(day, tz="UTC") + pd.Timedelta(days=1)
    return df[df.index < cut]


def read_at(df: pd.DataFrame, params: MlRsiParams = PARAMS, *, mode: str = "causal") -> Dict[str, Any]:
    fr = ml_rsi_frame(df["close"], params, mode=mode)
    last = fr.iloc[-1]
    out = {k: round(float(last[k]), 3) for k in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower")}
    out["regime"] = last["ml_rsi_regime"]
    out["points"] = int(min(len(fr), params.max_points + 1))
    out["bar"] = fr.index[-1].isoformat()
    return out


def with_forming(df_closed: pd.DataFrame, close: float, day: str) -> pd.DataFrame:
    ts = int(pd.Timestamp(day, tz="UTC").timestamp() * 1000)
    row = pd.DataFrame([[ts, close, close, close, close, 0.0]], columns=["timestamp", "open", "high", "low", "close", "volume"])
    row["datetime"] = pd.to_datetime(row["timestamp"], unit="ms", utc=True)
    return pd.concat([df_closed, row.set_index("datetime")])


def implied_forming_close(df_closed: pd.DataFrame, target: float, day: str, lo: float, hi: float) -> Optional[float]:
    """Bisection on the forming close so the port's value equals `target` (the ML RSI is monotone in the close)."""
    def value(c: float) -> float:
        return float(ml_rsi_frame(with_forming(df_closed, c, day)["close"], PARAMS).iloc[-1]["ml_rsi"])
    f_lo, f_hi = value(lo) - target, value(hi) - target
    if f_lo * f_hi > 0:
        return None
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        f_mid = value(mid) - target
        if f_lo * f_mid <= 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return round(0.5 * (lo + hi), 2)


def threshold_methods(df: pd.DataFrame) -> Dict[str, Any]:
    smoothed = alma(rsi(df["close"], PARAMS.rsi_period), PARAMS.alma_window, PARAMS.alma_offset, PARAMS.alma_sigma).to_numpy()
    window = smoothed[-(PARAMS.max_points + 1):]
    values = window[np.isfinite(window)]
    out: Dict[str, Any] = {"points": int(len(values))}
    out["percentile_linear"] = [round(float(x), 3) for x in np.percentile(values, [25, 75])]
    out["percentile_nearest_rank"] = [round(float(x), 3) for x in np.percentile(values, [25, 75], method="inverted_cdf")]
    c = kmeans3(values, PARAMS.max_iter)
    out["kmeans_described"] = [round(float(c[0]), 3), round(float(c[2]), 3)]
    return out


def regime_stats(df: pd.DataFrame, timeframe: str, start: str, end: str) -> Dict[str, Any]:
    fr = ml_rsi_frame(df["close"], PARAMS, mode="causal")
    win = fr[(fr.index >= pd.Timestamp(start, tz="UTC")) & (fr.index < pd.Timestamp(end, tz="UTC"))]
    reg = win["ml_rsi_regime"].dropna().tolist()
    n = len(reg)
    if n == 0:
        return {"bars": 0}
    counts = {k: reg.count(k) for k in ("green", "red", "gray")}
    runs: List[tuple] = []
    cur, length = reg[0], 1
    for r in reg[1:]:
        if r == cur:
            length += 1
        else:
            runs.append((cur, length))
            cur, length = r, 1
    runs.append((cur, length))
    flips = len(runs) - 1
    direct = sum(1 for (a, _), (b, _) in zip(runs, runs[1:]) if {a, b} == {"green", "red"})
    days = (win.index[-1] - win.index[0]).total_seconds() / 86400.0
    colour_runs = [l for c, l in runs if c in ("green", "red")]
    return {
        "bars": n, "share_pct": {k: round(v / n * 100.0, 1) for k, v in counts.items()},
        "flips": flips, "flips_per_30d": round(flips / days * 30.0, 2) if days else None,
        "direct_colour_to_contrary_flips": direct,
        "median_run_candles": float(np.median([l for _, l in runs])),
        "median_colour_run_candles": float(np.median(colour_runs)) if colour_runs else None,
        "median_colour_run_hours": round(float(np.median(colour_runs)) * TIMEFRAME_MS[timeframe] / 3_600_000.0, 1) if colour_runs else None,
        "p25_colour_run_candles": float(np.percentile(colour_runs, 25)) if colour_runs else None,
    }


def lookahead_check(df: pd.DataFrame, samples: int = 40) -> Dict[str, Any]:
    full = ml_rsi_frame(df["close"], PARAMS, mode="causal")
    idx = np.linspace(max(PARAMS.rsi_period + PARAMS.alma_window + 10, 50), len(df) - 2, samples).astype(int)
    worst = 0.0
    for j in idx:
        part = ml_rsi_frame(df["close"].iloc[: j + 1], PARAMS, mode="causal").iloc[-1]
        for k in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower"):
            a, b = float(part[k]), float(full.iloc[j][k])
            if math.isfinite(a) and math.isfinite(b):
                worst = max(worst, abs(a - b))
    return {"samples": int(len(idx)), "max_abs_diff_truncated_vs_full": round(worst, 9), "causal": worst < 1e-9}


def alignment_check(trig: pd.DataFrame, trig_tf: str, ctx: pd.DataFrame, ctx_tf: str) -> Dict[str, Any]:
    t_close = trig["timestamp"].to_numpy(dtype="int64") + TIMEFRAME_MS[trig_tf]
    c_close = ctx["timestamp"].to_numpy(dtype="int64") + TIMEFRAME_MS[ctx_tf]
    idx = np.searchsorted(c_close, t_close, side="right") - 1
    ok = idx >= 0
    aligned_close = c_close[idx[ok]]
    nxt = np.where(idx[ok] + 1 < len(c_close), c_close[np.minimum(idx[ok] + 1, len(c_close) - 1)], np.iinfo("int64").max)
    return {
        "trigger_bars": int(len(t_close)), "unaligned": int((~ok).sum()),
        "all_aligned_closed_at_or_before_trigger_close": bool(np.all(aligned_close <= t_close[ok])),
        "next_guardian_closes_after_trigger_close": bool(np.all(nxt > t_close[ok])),
        "lag_hours_median": round(float(np.median((t_close[ok] - aligned_close) / 3_600_000.0)), 2),
        "lag_hours_max": round(float(np.max((t_close[ok] - aligned_close) / 3_600_000.0)), 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache-dir", default="/data/ohlcv")
    ap.add_argument("--long-cache-dir", default="/data/ohlcv_long")
    ap.add_argument("--audit-cache-dir", default="/data/ohlcv_audit")
    ap.add_argument("--reference-exchange", default="binance")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--out", default="/data/results/ml_rsi_audit.json")
    ap.add_argument("--md-out", default=None)
    args = ap.parse_args()
    audit_cache = Path(args.audit_cache_dir)
    report: Dict[str, Any] = {"owner": OWNER, "params": PARAMS.__dict__, "generated": datetime.now(timezone.utc).isoformat()}

    # 1. Parity -----------------------------------------------------------------
    bitget_1d = _load_cache(Path(args.long_cache_dir) / "bitget_BTC-USDT_1d.json")
    series: Dict[str, pd.DataFrame] = {}
    if bitget_1d is not None:
        series["bitget"] = bitget_1d
    ref_error = None
    try:
        series[args.reference_exchange] = fetch_public(args.reference_exchange, "BTC/USDT", "1d", "2017-08-01", audit_cache, refresh=args.refresh)
    except Exception as exc:  # network / geo
        ref_error = f"{type(exc).__name__}: {exc}"
    parity: Dict[str, Any] = {"reference_fetch_error": ref_error}
    for name, df in series.items():
        closed = last_closed(df, CLOSED_DAY)
        row: Dict[str, Any] = {"rows_total": int(len(df)), "last_open_in_cache": df.index[-1].isoformat(),
                               "closed_2026_10_31": read_at(closed), "closed_2026_10_31_tv_anchored": read_at(closed, mode="tv")}
        row["closed_diff_vs_owner"] = {k: round(abs(row["closed_2026_10_31"][k] - OWNER[k]), 3) for k in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower")}
        c31 = float(closed["close"].iloc[-1])
        row["close_2026_10_31"] = c31
        row["implied_forming_close_for_40_07"] = implied_forming_close(closed, OWNER["ml_rsi"], FORMING_DAY, c31 * 0.80, c31 * 1.20)
        actual = df[df.index == pd.Timestamp(FORMING_DAY, tz="UTC")]
        if len(actual):
            a = actual.iloc[0]
            row["forming_2026_11_01_in_cache"] = {"open": float(a["open"]), "high": float(a["high"]), "low": float(a["low"]), "close_or_last": float(a["close"])}
            row["read_with_forming_at_cache_close"] = read_at(with_forming(closed, float(a["close"]), FORMING_DAY))
            row["read_with_forming_at_low"] = read_at(with_forming(closed, float(a["low"]), FORMING_DAY))
            row["read_with_forming_at_high"] = read_at(with_forming(closed, float(a["high"]), FORMING_DAY))
            imp = row["implied_forming_close_for_40_07"]
            row["implied_inside_2026_11_01_range"] = bool(imp is not None and float(a["low"]) <= imp <= float(a["high"]))
        row["threshold_methods_closed"] = threshold_methods(closed)
        parity[name] = row
    # 1h intraday path of 2026-11-01 on the reference exchange (when the owner could have read 40.07)
    try:
        h1 = fetch_public(args.reference_exchange, "BTC/USDT", "1h", "2026-10-30", audit_cache, refresh=args.refresh)
        day = h1[(h1.index >= pd.Timestamp(FORMING_DAY, tz="UTC")) & (h1.index < pd.Timestamp(FORMING_DAY, tz="UTC") + pd.Timedelta(days=1))]
        parity["intraday_2026_11_01_reference"] = [{"open": r.name.isoformat(), "low": float(r["low"]), "high": float(r["high"]), "close": float(r["close"])}
                                                   for _, r in day.iterrows()]
        if args.reference_exchange in parity and parity[args.reference_exchange].get("implied_forming_close_for_40_07"):
            imp = parity[args.reference_exchange]["implied_forming_close_for_40_07"]
            hits = [r.name.isoformat() for _, r in day.iterrows() if float(r["low"]) <= imp <= float(r["high"])]
            parity["implied_price_hours_utc"] = hits
    except Exception as exc:
        parity["intraday_fetch_error"] = f"{type(exc).__name__}: {exc}"
    report["parity"] = parity

    # 3. Regime statistics on the lab guardians (bitget cache) --------------------------------
    stats: Dict[str, Any] = {}
    for tf in ("4h", "1d", "1h"):
        df = _load_cache(Path(args.cache_dir) / f"bitget_BTC-USDT_{tf}.json")
        if df is not None:
            stats[tf] = regime_stats(df, tf, "2024-11-01", "2026-11-01")
    report["regime_stats"] = stats

    # 4. Lookahead + alignment -----------------------------------------------------------
    checks: Dict[str, Any] = {}
    d4 = _load_cache(Path(args.cache_dir) / "bitget_BTC-USDT_4h.json")
    d1h = _load_cache(Path(args.cache_dir) / "bitget_BTC-USDT_1h.json")
    d1d = _load_cache(Path(args.cache_dir) / "bitget_BTC-USDT_1d.json")
    if d4 is not None:
        checks["lookahead_4h"] = lookahead_check(d4)
    if d1h is not None and d4 is not None:
        checks["alignment_1h_to_4h"] = alignment_check(d1h, "1h", d4, "4h")
    if d4 is not None and d1d is not None:
        checks["alignment_4h_to_1d"] = alignment_check(d4, "4h", d1d, "1d")
    report["checks"] = checks

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str))
    print(f"[out] {args.out}")

    if args.md_out:
        md: List[str] = ["# ML RSI [BackQuant] — audit of the port (2026-11-01, owner point f)", "",
                         f"Generated by `scripts/audit_ml_rsi.py` ({report['generated'][:16]}Z). Raw: `{Path(args.out).name}`. "
                         "Params: RSI 19 on close, ALMA 4 / sigma 1 / offset 0, percentiles 25 / 75 on the trailing 3001 values.", "",
                         "## 1. Parity vs the owner's TradingView reading", "",
                         f"Owner: {OWNER['exchange']} {OWNER['symbol']} {OWNER['timeframe']}, {OWNER['read_on']}: value {OWNER['ml_rsi']}, "
                         f"upper {OWNER['ml_rsi_upper']}, lower {OWNER['ml_rsi_lower']}.", "",
                         "| exchange | closed 2026-10-31: value / upper / lower (regime) | abs diff vs owner | TV-anchored window same bar | implied forming close for 40.07 | 2026-11-01 range (low / high) | implied inside range |",
                         "|---|---|---|---|---|---|---|"]
        for name, row in parity.items():
            if not isinstance(row, dict) or "closed_2026_10_31" not in row:
                continue
            c = row["closed_2026_10_31"]
            tv = row["closed_2026_10_31_tv_anchored"]
            rng = row.get("forming_2026_11_01_in_cache")
            md.append(f"| {name} | {c['ml_rsi']} / {c['ml_rsi_upper']} / {c['ml_rsi_lower']} ({c['regime']}) | "
                      f"{row['closed_diff_vs_owner']['ml_rsi']} / {row['closed_diff_vs_owner']['ml_rsi_upper']} / {row['closed_diff_vs_owner']['ml_rsi_lower']} | "
                      f"{tv['ml_rsi']} / {tv['ml_rsi_upper']} / {tv['ml_rsi_lower']} | {row['implied_forming_close_for_40_07']} | "
                      f"{(str(rng['low']) + ' / ' + str(rng['high'])) if rng else '—'} | {row.get('implied_inside_2026_11_01_range', '—')} |")
        if parity.get("reference_fetch_error"):
            md.append(f"\nReference exchange fetch failed: `{parity['reference_fetch_error']}`.")
        if parity.get("implied_price_hours_utc") is not None:
            md.append(f"\nHours (UTC, 1h candles of 2026-11-01 on {args.reference_exchange}) whose range contains the implied price: "
                      f"{', '.join(h[11:16] for h in parity['implied_price_hours_utc']) or 'none'}.")
        md += ["", "## 2. Threshold method sensitivity (closed 2026-10-31, same 3001 values)", "",
               "| exchange | percentile linear (Pine) | percentile nearest rank | k-means as described |", "|---|---|---|---|"]
        for name, row in parity.items():
            if isinstance(row, dict) and "threshold_methods_closed" in row:
                t = row["threshold_methods_closed"]
                md.append(f"| {name} | {t['percentile_linear']} | {t['percentile_nearest_rank']} | {t['kmeans_described']} |")
        md += ["", "## 3. Regime statistics of the guardian series (bitget BTC/USDT, causal window, 2024-11 -> 2026-10)", "",
               "| TF | bars | green / red / gray % | flips | flips / 30 d | colour -> contrary without gray | median run (candles) | median colour run (candles / hours) |",
               "|---|---|---|---|---|---|---|---|"]
        for tf, s in stats.items():
            if s.get("bars"):
                sh = s["share_pct"]
                md.append(f"| {tf} | {s['bars']} | {sh['green']} / {sh['red']} / {sh['gray']} | {s['flips']} | {s['flips_per_30d']} | "
                          f"{s['direct_colour_to_contrary_flips']} | {s['median_run_candles']} | {s['median_colour_run_candles']} / {s['median_colour_run_hours']} |")
        md += ["", "## 4. Lookahead and alignment checks", ""]
        for k, v in checks.items():
            md.append(f"* `{k}`: {json.dumps(v)}")
        Path(args.md_out).write_text("\n".join(md) + "\n")
        print(f"[out] {args.md_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
