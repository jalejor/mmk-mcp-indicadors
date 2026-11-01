#!/usr/bin/env python3
"""ML RSI [BackQuant] parity vs the owner's TradingView reading + repaint measure.

Owner (01-nov-2026, BINANCE BTC/USDT 1d, candle closed 2026-10-31): ML RSI
40.07, upper 59.74, lower 44.30 (red). Runs offline on the long 1d cache:

    docker compose --profile backtest run --rm backtest \
        python scripts/check_ml_rsi_parity.py --cache-dir /data/ohlcv_long

Prints the port's value for ALMA offset 0 (what the Pine hard-codes) and
0.85 (the owner's note), and the causal-vs-TV repaint report.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from controllers.metrics.impulse_backtest import rows_to_frame  # noqa: E402
from controllers.metrics.ml_rsi import MlRsiParams, ml_rsi_frame, repaint_report  # noqa: E402

OWNER = {"ml_rsi": 40.07, "ml_rsi_upper": 59.74, "ml_rsi_lower": 44.30}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache-dir", default="/data/ohlcv_long")
    ap.add_argument("--timeframe", default="1d")
    ap.add_argument("--out", default="/data/results/ml_rsi_parity.json")
    ap.add_argument("--fixture-out", default=None, help="write [timestamp, close] rows for the test fixture")
    args = ap.parse_args()

    meta = json.loads((Path(args.cache_dir) / f"bitget_BTC-USDT_{args.timeframe}.json").read_text())
    df = rows_to_frame(meta["rows"])
    print(f"rows={len(df)} first={df.index[0]} last={df.index[-1]} last_close={float(df['close'].iloc[-1])}")
    out = {"rows": len(df), "first": df.index[0].isoformat(), "last": df.index[-1].isoformat(), "owner": OWNER,
           "variants": {}}
    for offset in (0.0, 0.85):
        p = MlRsiParams(alma_offset=offset)
        fr = ml_rsi_frame(df["close"], p)
        last = fr.iloc[-1]
        row = {k: round(float(last[k]), 3) for k in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower")}
        row["ml_rsi_regime"] = last["ml_rsi_regime"]
        row["abs_diff_vs_owner"] = {k: round(abs(row[k] - OWNER[k]), 3) for k in OWNER}
        row["parity_2pts"] = all(v <= 2.0 for v in row["abs_diff_vs_owner"].values())
        row["repaint"] = repaint_report(df["close"], p)
        out["variants"][f"offset_{offset}"] = row
        print(f"offset={offset}: {row}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"[out] {args.out}")
    if args.fixture_out:
        rows = [[int(ts), float(c)] for ts, c in zip(df["timestamp"], df["close"])]
        Path(args.fixture_out).write_text(json.dumps({
            "source": "bitget spot BTC/USDT 1d closed candles (scripts/fetch_long_history.py)",
            "sha256_frame": meta.get("sha256"), "rows": rows}))
        print(f"[out] {args.fixture_out} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
