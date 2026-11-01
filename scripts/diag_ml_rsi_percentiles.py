#!/usr/bin/env python3
"""Diagnostic 2: are the owner's ML RSI thresholds the raw 25/75 percentiles?

The BackQuant Pine builds `distances` / `new_centroids` with
`array.new_float(3)` (3 `na` slots) and then PUSHES, so the arrays grow to 6/9
elements and `array.get(centroids, 0|2)` can end up reading the percentile
slots that `array.set` refreshes every bar. If so, the plotted thresholds are
the 25th / 75th percentiles of the collected RSI values, not k-means
centroids. This prints p25/p50/p75 for several trailing windows.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from controllers.metrics.impulse_backtest import rows_to_frame  # noqa: E402
from controllers.metrics.ml_rsi import alma, rsi  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="/data/ohlcv_long")
    ap.add_argument("--timeframe", default="1d")
    args = ap.parse_args()
    meta = json.loads((Path(args.cache_dir) / f"bitget_BTC-USDT_{args.timeframe}.json").read_text())
    df = rows_to_frame(meta["rows"])
    raw = rsi(df["close"], 19)
    for label, series in (("raw rsi19", raw), ("alma off0", alma(raw, 4, 0.0, 1.0)), ("alma off0.85", alma(raw, 4, 0.85, 1.0))):
        v = series.to_numpy(dtype=float)
        print(f"== {label}: last={v[-1]:.3f}")
        for w in (250, 500, 1000, 2000, 3001, len(v)):
            vals = v[-w:]
            vals = vals[np.isfinite(vals)]
            p = np.percentile(vals, [25, 50, 75])
            print(f"  window {w:>5}: p25={p[0]:6.2f} p50={p[1]:6.2f} p75={p[2]:6.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
