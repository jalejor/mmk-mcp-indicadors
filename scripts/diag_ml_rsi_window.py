#!/usr/bin/env python3
"""Diagnostic: which data window reproduces the owner's ML RSI thresholds?

The owner read upper 59.74 / lower 44.30 on TradingView (BINANCE BTC/USDT 1d,
01-nov-2026). The port on the last 3001 bitget daily values gives 68.3 / 39.2.
Centroids of a k-means depend on the data window, so this prints the centroids
at the last closed candle for trailing windows of several lengths, plus the
raw RSI(19) and both ALMA variants, to locate the discrepancy.

    docker compose --profile backtest run --rm backtest \
        python scripts/diag_ml_rsi_window.py --cache-dir /data/ohlcv_long
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
from controllers.metrics.ml_rsi import alma, kmeans3, rsi  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default="/data/ohlcv_long")
    ap.add_argument("--timeframe", default="1d")
    ap.add_argument("--windows", nargs="+", type=int, default=[100, 150, 200, 250, 300, 400, 500, 750, 1000, 1500, 2000, 2500, 3001])
    args = ap.parse_args()
    meta = json.loads((Path(args.cache_dir) / f"bitget_BTC-USDT_{args.timeframe}.json").read_text())
    df = rows_to_frame(meta["rows"])
    close = df["close"]
    raw = rsi(close, 19)
    print(f"last close {float(close.iloc[-1])} @ {df.index[-1]}  rsi19 raw={float(raw.iloc[-1]):.3f}")
    for offset in (0.0, 0.85):
        sm = alma(raw, 4, offset, 1.0)
        print(f"ALMA offset {offset}: last={float(sm.iloc[-1]):.3f} prev={float(sm.iloc[-2]):.3f}")
    sm = alma(raw, 4, 0.0, 1.0).to_numpy(dtype=float)
    print("window_bars | lower | mid | upper")
    for w in args.windows:
        vals = sm[-w:]
        c = kmeans3(vals)
        print(f"{w:>11} | {c[0]:6.2f} | {c[1]:6.2f} | {c[2]:6.2f}")
    # how many bars does the owner's chart need to hit 44.30 / 59.74 within 1 pt?
    best = None
    for w in range(60, len(sm) + 1):
        c = kmeans3(sm[-w:])
        err = abs(c[0] - 44.30) + abs(c[2] - 59.74)
        if best is None or err < best[0]:
            best = (err, w, c)
    print(f"closest trailing window: {best[1]} bars -> lower {best[2][0]:.2f} upper {best[2][2]:.2f} (sum abs err {best[0]:.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
