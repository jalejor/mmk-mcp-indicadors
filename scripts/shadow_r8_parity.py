#!/usr/bin/env python3
"""Round 8 shadow PARITY harness: replay the recorded hourly runs on a COPY and compare bytes.

Reads a pristine copy of a live `shadow-r8` state dir (`events.jsonl`, `trades.jsonl`,
`state.json`, `runs.log`, `ohlcv/`) and re-runs every recorded run in order into an empty
work dir, serving the exchange from the pristine OHLCV cache (no network: `--network none`
is fine), with the clock each run really had (the `recorded_at` of its events, the state's
`last_run` for the final one, else the wrapper's `runs.log` time). At the end the work dir's
`events.jsonl` / `trades.jsonl` / `state.json` must be BYTE-identical to the pristine ones.

    python scripts/shadow_r8_parity.py --pristine /data/pristine --work /data/work            # incremental runner
    python scripts/shadow_r8_parity.py --pristine /data/pristine --work /data/work --full     # full replay every run
    python scripts/shadow_r8_parity.py ... --last-only                                        # one run, the final clock

`--full` is the pre-2026-11-02 behaviour (every run replays from the anchor) and works
against the old `impulse_shadow` too (mount the old `src`), which validates the harness itself.
Exit code 0 = identical, 1 = a difference (printed), 2 = usage.
"""

from __future__ import annotations

import argparse
import inspect
import json
import shutil
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore", category=FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from controllers.metrics import impulse_shadow as sh  # noqa: E402


def ms(value: str) -> int:
    return sh.ms_of(value)


def run_clocks(pristine: Path) -> List[int]:
    """One clock per recorded run, in order (see the module doc)."""
    lines = [ln for ln in (pristine / "runs.log").read_text().splitlines() if ln.strip()]
    events = sh.read_jsonl(pristine / sh.EVENTS_FILE) + sh.read_jsonl(pristine / sh.TRADES_FILE)
    stamps = sorted({e["recorded_at"] for e in events if e.get("recorded_at")})
    state = json.loads((pristine / sh.STATE_FILE).read_text()) if (pristine / sh.STATE_FILE).exists() else {}
    clocks: List[int] = []
    for n, ln in enumerate(lines):
        wrapper = ms(ln.split()[0])
        hour = sh.floor_hour_ms(wrapper)
        same_hour = [s for s in stamps if sh.floor_hour_ms(ms(s)) == hour]
        if same_hour:
            clocks.append(ms(same_hour[0]))
        elif n == len(lines) - 1 and state.get("last_run"):
            clocks.append(ms(state["last_run"]))
        else:
            clocks.append(wrapper)
    # Runs made without the wrapper (the activation session's manual one-shots) are not in
    # runs.log but count in state.counts.runs: replay them just before the first logged run,
    # where they recorded nothing (pre-activation) and only advance the counter.
    missing = int(state.get("counts", {}).get("runs", len(clocks))) - len(clocks)
    if missing > 0 and clocks:
        clocks = [clocks[0] - 60_000 * (missing - k) for k in range(missing)] + clocks
    return clocks


def masked_state(path: Path) -> str:
    """state.json with `counts.runs` neutralised (for --last-only, where only one run happens)."""
    if not path.exists():
        return ""
    state = json.loads(path.read_text())
    state.get("counts", {}).pop("runs", None)
    return json.dumps(state, indent=2, default=str)


def pristine_fetcher(ohlcv_dir: Path):
    rows_by: Dict[str, List[List[Any]]] = {}

    def fetch(symbol: str, timeframe: str, since: int, limit: int) -> List[List[Any]]:
        key = f"{symbol}@{timeframe}"
        if key not in rows_by:
            meta = json.loads(sh.cache_path(ohlcv_dir, symbol, timeframe).read_text())
            rows_by[key] = sorted(meta["rows"], key=lambda r: int(r[0]))
        return [r for r in rows_by[key] if int(r[0]) >= int(since)][: int(limit)]

    return fetch


def compare(pristine: Path, work: Path) -> List[str]:
    diffs: List[str] = []
    for name in (sh.EVENTS_FILE, sh.TRADES_FILE, sh.STATE_FILE):
        a = (pristine / name).read_bytes() if (pristine / name).exists() else b""
        b = (work / name).read_bytes() if (work / name).exists() else b""
        if a == b:
            continue
        al, bl = a.decode().splitlines(), b.decode().splitlines()
        first = next((i for i, (x, y) in enumerate(zip(al, bl)) if x != y), min(len(al), len(bl)))
        diffs.append(f"{name}: {len(a)} vs {len(b)} bytes, {len(al)} vs {len(bl)} lines, first difference at line {first + 1}:\n"
                     f"  pristine: {al[first] if first < len(al) else '<eof>'}\n  work:     {bl[first] if first < len(bl) else '<eof>'}")
    return diffs


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pristine", required=True)
    p.add_argument("--work", required=True)
    p.add_argument("--full", action="store_true", help="full replay every run (no machine snapshots)")
    p.add_argument("--last-only", action="store_true", help="a single run at the final clock (events differ only in recorded_at)")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    pristine, work = Path(args.pristine), Path(args.work)
    if not (pristine / "runs.log").exists():
        print(f"no runs.log in {pristine}", file=sys.stderr)
        return 2
    if work.exists() and any(work.iterdir()):
        print(f"work dir {work} is not empty", file=sys.stderr)
        return 2
    work.mkdir(parents=True, exist_ok=True)
    shutil.copytree(pristine / "ohlcv", work / "ohlcv")
    clocks = run_clocks(pristine)
    if args.last_only:
        clocks = clocks[-1:]
    fetch = pristine_fetcher(pristine / "ohlcv")
    supports_resume = "resume" in inspect.signature(sh.shadow_run).parameters
    log = (lambda _m: None) if args.quiet else print
    t_all = time.perf_counter()
    for n, now_ms in enumerate(clocks, 1):
        t0 = time.perf_counter()
        loaders = sh.make_loaders(sh.UNIVERSE, cache_dir=work / "ohlcv", anchor_ms=ms(sh.ANCHOR), end_ms=sh.floor_hour_ms(now_ms),
                                  now_ms=now_ms, fetch=fetch, fallback=None, log=lambda _m: None)
        kw = {"resume": not args.full} if supports_resume else {}
        summary = sh.shadow_run(state_dir=work, loaders=loaders, now_ms=now_ms, dry_run=False, notify=lambda _line: True,
                                log=lambda _m: None, **kw)
        perf = summary.get("perf", {})
        log(f"[parity] run {n}/{len(clocks)} now {sh.iso(now_ms)[:19]}Z events +{summary['events_new']} trades +{summary['trades_new']} "
            f"open {len(summary['open_positions'])} errors {len(summary['assets_failed'])} in {time.perf_counter() - t0:.1f}s"
            + (f" (resumed {perf.get('resumed')} rebuilt {perf.get('rebuilt')} bars {perf.get('bars_driven')})" if perf else ""))
    print(f"[parity] {len(clocks)} runs in {time.perf_counter() - t_all:.1f}s")
    if args.last_only:
        strip = lambda path: [json.dumps({k: v for k, v in e.items() if k != "recorded_at"}) for e in sh.read_jsonl(path)]  # noqa: E731
        diffs = []
        for name in (sh.EVENTS_FILE, sh.TRADES_FILE):
            if strip(pristine / name) != strip(work / name):
                diffs.append(f"{name}: differ beyond recorded_at")
        if masked_state(pristine / sh.STATE_FILE) != masked_state(work / sh.STATE_FILE):
            diffs.append(f"{sh.STATE_FILE}: differ beyond counts.runs")
    else:
        diffs = compare(pristine, work)
    if diffs:
        print("[parity] DIFFERENT:\n" + "\n".join(diffs))
        return 1
    print(f"[parity] IDENTICAL: {sh.EVENTS_FILE}, {sh.TRADES_FILE}, {sh.STATE_FILE}"
          + (" (events/trades modulo recorded_at, state modulo counts.runs)" if args.last_only else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
