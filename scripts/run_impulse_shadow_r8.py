#!/usr/bin/env python3
"""Impulsos-v2 ROUND 8 one-shot: forward SHADOW of the frozen 2.3.0 snipper chain, long + short.

Protocol `docs/PREREG_IMPULSOS_v2_r8_shadow.md`. Evaluates the LAST CLOSED 1h candle of the 9
assets (replay from the fixed anchor, see `controllers/metrics/impulse_shadow.py`), appends the
new paper events / trades to JSONL under --state-dir and notifies entries / exits by ntfy
(NTFY_BASE / NTFY_TOPIC from the environment; the topic is never printed). Idempotent:
running it twice on the same candle records nothing the second time. Lab:

    docker compose --profile shadow run --rm -T shadow                       # real
    docker compose --profile shadow run --rm -T shadow python scripts/run_impulse_shadow_r8.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from controllers.metrics.impulse_shadow import (  # noqa: E402
    ACTIVATION,
    ANCHOR,
    UNIVERSE,
    floor_hour_ms,
    make_loaders,
    ms_of,
    shadow_run,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--state-dir", default="/data/shadow-r8")
    p.add_argument("--cache-dir", default=None, help="default: <state-dir>/ohlcv")
    p.add_argument("--dry-run", action="store_true", help="evaluate and print; write nothing, notify nothing")
    p.add_argument("--now", default=None, help="ISO clock override (tests / replays); default = wall clock")
    p.add_argument("--only-symbols", nargs="*", default=None)
    p.add_argument("--quiet", action="store_true", help="only the final one-line summary")
    args = p.parse_args()

    now_ms = ms_of(args.now) if args.now else int(time.time() * 1000)
    end_ms = floor_hour_ms(now_ms)  # last closed 1h candle = the one that closed at this hour
    state_dir = Path(args.state_dir)
    cache_dir = Path(args.cache_dir) if args.cache_dir else state_dir / "ohlcv"
    symbols = [s for s in UNIVERSE if not args.only_symbols or s in args.only_symbols]
    log = (lambda _msg: None) if args.quiet else print
    loaders = make_loaders(symbols, cache_dir=cache_dir, anchor_ms=ms_of(ANCHOR), end_ms=end_ms, now_ms=now_ms, log=log)
    summary = shadow_run(state_dir=state_dir, loaders=loaders, now_ms=now_ms, dry_run=args.dry_run,
                         anchor=ANCHOR, activation=ACTIVATION, symbols=symbols, log=print)
    if args.dry_run and not args.quiet:
        for sym, c in summary["last_candle"].items():
            print(f"[last candle] {sym}: {c}")
        for k, o in summary["open_positions"].items():
            print(f"[open] {k}: {o.get('side')} avg {o.get('avg_price')} layers {o.get('n_layers')} unrealized {o.get('unrealized_net_usdt')} USDT")
    return 1 if summary["assets_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
