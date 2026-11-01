#!/usr/bin/env python3
"""Fetch a LONG closed-candle history into a separate cache (impulsos-v2 round 3).

ML RSI thresholds are k-means centroids over the last `max_points` (3000)
values, so TV parity on 1d needs ~3000 daily candles: far more than the 300
warm-up bars of the backtest cache. This writes to its own cache dir so the
backtest frames (and their sha256 manifest) are untouched. Lab:

    docker compose --profile backtest run --rm backtest \
        python scripts/fetch_long_history.py --timeframe 1d --warmup-bars 3400
"""

from __future__ import annotations

import argparse
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from controllers.metrics.impulse_backtest import load_ohlcv  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol", default="BTC/USDT")
    ap.add_argument("--exchange", default="bitget")
    ap.add_argument("--timeframe", default="1d")
    ap.add_argument("--start", default="2024-11-01")
    ap.add_argument("--end", default="2026-10-31", help="inclusive date")
    ap.add_argument("--warmup-bars", type=int, default=3400)
    ap.add_argument("--cache-dir", default="/data/ohlcv_long")
    args = ap.parse_args()

    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc) + timedelta(days=1)
    df, info = load_ohlcv(args.symbol, args.timeframe, start, end, exchange=args.exchange,
                          cache_dir=args.cache_dir, warmup_bars=args.warmup_bars)
    print(info)
    print(f"rows={len(df)} first={df.index[0]} last={df.index[-1]} last_close={float(df['close'].iloc[-1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
