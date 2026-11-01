#!/usr/bin/env python3
"""Round-8 shadow report: signals and R per book (long_only / short_only / regime_own / regime_btc)
and per side x regime, from the JSONL state of `run_impulse_shadow_r8.py`. Read-only.

    docker compose --profile shadow run --rm -T shadow python scripts/shadow_r8_report.py [--json] [--md-out PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from controllers.metrics.impulse_shadow import report_markdown, shadow_report  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--state-dir", default="/data/shadow-r8")
    p.add_argument("--json", action="store_true")
    p.add_argument("--md-out", default=None)
    args = p.parse_args()
    rep = shadow_report(Path(args.state_dir))
    if args.json:
        print(json.dumps(rep, indent=2, default=str))
        return 0
    text = report_markdown(rep)
    print(text)
    if args.md_out:
        Path(args.md_out).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
