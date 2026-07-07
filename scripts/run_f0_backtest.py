#!/usr/bin/env python3
"""F0 gate runner — multi-TF setup backtest matrix (spec §C).

Runs the declarative setups (PB-1D / IMP-4H, longs + mirrored shorts) over
one or more symbols and prints the gate matrix with PASS/FAIL against the §C
thresholds. Always run inside Docker (never install deps on the host):

    docker build -f Dockerfile.test -t mmk-test-f0 .
    docker run --rm -v "$(pwd)":/app -w /app mmk-test-f0 \
        python scripts/run_f0_backtest.py \
        --symbols BTC/USDT ETH/USDT --start 2024-07-01 --end 2026-07-01

Smoke run (pipeline check, not the gate):

    docker run --rm -v "$(pwd)":/app -w /app mmk-test-f0 \
        python scripts/run_f0_backtest.py --symbols BTC/USDT --months 6 \
        --setups IMP-4H-LONG IMP-4H-SHORT

Fees/slippage are parameters (owner Q9 base model: bitget spot taker 0.10% +
0.05% slippage per side). Gate C runs must use the base model; margin/futures
re-runs are a flag change.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Cosmetic only: pandas-ta emits a giant FutureWarning (mfi dtype) per
# Konkorde computation that floods the gate report. The computation itself
# is untouched.
warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from controllers.metrics.setup_backtest_service import (  # noqa: E402
    DEFAULT_FEE_RATE_PER_SIDE,
    DEFAULT_SLIPPAGE_PER_SIDE,
    SetupBacktestService,
)
from controllers.metrics.setup_definitions import DEFAULT_SETUPS, SETUPS_BY_ID  # noqa: E402

# §C PASS / NO-PASS thresholds (analyst recommendation).
GATE_THRESHOLDS = {
    "n_trades_full_min": 30,  # combined per setup family+symbol (owner Q8)
    "n_trades_oos_min": 10,
    "expectancy_full_min": 0.15,
    "expectancy_oos_min": 0.10,
    "profit_factor_oos_min": 1.15,
    "max_drawdown_max": 20.0,
    "oos_vs_is_expectancy_ratio_min": 0.5,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F0 multi-TF setup backtest gate")
    parser.add_argument("--symbols", nargs="+", default=["BTC/USDT"], help="e.g. BTC/USDT ETH/USDT")
    parser.add_argument("--exchange", default="bitget")
    parser.add_argument("--start", help="ISO date (UTC). Overrides --months.")
    parser.add_argument("--end", help="ISO date (UTC), default: now")
    parser.add_argument("--months", type=int, default=24, help="lookback when --start is omitted")
    parser.add_argument(
        "--setups", nargs="+", default=[s.setup_id for s in DEFAULT_SETUPS],
        choices=sorted(SETUPS_BY_ID), help="setup ids to run",
    )
    parser.add_argument("--fee-rate", type=float, default=DEFAULT_FEE_RATE_PER_SIDE,
                        help="per-side taker fee (fraction, default 0.001)")
    parser.add_argument("--slippage", type=float, default=DEFAULT_SLIPPAGE_PER_SIDE,
                        help="per-side slippage (fraction, default 0.0005)")
    parser.add_argument("--capital", type=float, default=10000.0)
    parser.add_argument("--risk-pct", type=float, default=1.5)
    parser.add_argument("--risk-profile", default="medium", choices=["low", "medium", "high"])
    parser.add_argument("--json-out", help="write the full JSON report to this path")
    return parser.parse_args()


def _resolve_period(args: argparse.Namespace) -> tuple[datetime, datetime]:
    end = (
        datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
        if args.end
        else datetime.now(timezone.utc)
    )
    if args.start:
        start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    else:
        start = end - timedelta(days=30 * args.months)
    return start, end


def _fmt(value: Any, width: int = 8) -> str:
    if value is None:
        return "-".rjust(width)
    if isinstance(value, float):
        return f"{value:.3f}".rjust(width)
    return str(value).rjust(width)


def _print_setup_block(symbol: str, block: Dict[str, Any]) -> None:
    print(f"\n  {block['setup_id']} ({block['side']}, TFs {'/'.join(block['timeframes'])}) — {symbol}")
    header = f"    {'split':<14}{'n':>5}{'win%':>8}{'expR':>8}{'avgW':>8}{'avgL':>8}{'PF':>8}{'maxDD%':>8}{'dur':>7}"
    print(header)
    for split in ("full", "in_sample", "out_of_sample"):
        m = block[split]
        pf = m["profit_factor"]
        pf_str = f"{pf:.3f}" if isinstance(pf, float) and pf != float("inf") else str(pf)
        print(
            f"    {split:<14}{m['n_trades']:>5}{m['win_rate'] * 100:>8.1f}{m['expectancy_R']:>8.3f}"
            f"{m['avg_win_R']:>8.3f}{m['avg_loss_R']:>8.3f}{pf_str:>8}{m['max_drawdown_pct']:>8.2f}"
            f"{m['avg_trade_duration_bars']:>7.1f}"
        )
    vetoed = block["vetoed_signals"]
    print(
        f"    vetoed: {vetoed['count']} {vetoed['by_reason']} | counterfactual expR "
        f"{_fmt(vetoed['counterfactual_expectancy_R'])} vs accepted {_fmt(vetoed['accepted_expectancy_R'])}"
    )
    for window, stats in vetoed["window_comparison"].items():
        print(
            f"      veto window {window}: accepted n={stats['accepted_n']} expR {_fmt(stats['accepted_expectancy_R'])}"
            f" | vetoed n={stats['vetoed_n']} expR {_fmt(stats['vetoed_expectancy_R'])}"
        )
    grades = block["adx_turn_grades"]
    print(
        f"    adx_turn grade A: n={grades['A']['n_trades']} expR {_fmt(grades['A']['expectancy_R'])}"
        f" | grade B: n={grades['B']['n_trades']} expR {_fmt(grades['B']['expectancy_R'])}"
    )


def _gate_row(family: str, symbol: str, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate the §C thresholds for a setup family (long+short) on a symbol."""
    thresholds = GATE_THRESHOLDS
    n_full = sum(b["full"]["n_trades"] for b in blocks)
    n_oos = sum(b["out_of_sample"]["n_trades"] for b in blocks)

    def _weighted(metric: str, split: str) -> Optional[float]:
        total = sum(b[split]["n_trades"] for b in blocks)
        if total == 0:
            return None
        return sum(b[split][metric] * b[split]["n_trades"] for b in blocks) / total

    exp_full = _weighted("expectancy_R", "full")
    exp_is = _weighted("expectancy_R", "in_sample")
    exp_oos = _weighted("expectancy_R", "out_of_sample")
    pf_oos_values = [
        b["out_of_sample"]["profit_factor"]
        for b in blocks
        if b["out_of_sample"]["n_trades"] > 0
    ]
    pf_oos = min(pf_oos_values) if pf_oos_values else None
    max_dd = max(b["full"]["max_drawdown_pct"] for b in blocks) if blocks else 0.0

    checks = {
        "n_trades_full>=30": n_full >= thresholds["n_trades_full_min"],
        "n_trades_oos>=10": n_oos >= thresholds["n_trades_oos_min"],
        "expectancy_full>=0.15R": exp_full is not None and exp_full >= thresholds["expectancy_full_min"],
        "expectancy_oos>=0.10R": exp_oos is not None and exp_oos >= thresholds["expectancy_oos_min"],
        "profit_factor_oos>=1.15": pf_oos is not None and pf_oos >= thresholds["profit_factor_oos_min"],
        "max_drawdown<=20%": max_dd <= thresholds["max_drawdown_max"],
        "oos>=50%_of_is_expectancy": (
            exp_is is not None and exp_oos is not None and exp_is > 0
            and exp_oos >= thresholds["oos_vs_is_expectancy_ratio_min"] * exp_is
        ),
    }
    return {
        "family": family,
        "symbol": symbol,
        "n_full": n_full,
        "n_oos": n_oos,
        "expectancy_full": exp_full,
        "expectancy_oos": exp_oos,
        "profit_factor_oos": pf_oos,
        "max_drawdown_pct": max_dd,
        "checks": checks,
        "pass": all(checks.values()),
    }


def main() -> int:
    args = _parse_args()
    start, end = _resolve_period(args)
    setups = [SETUPS_BY_ID[sid] for sid in args.setups]

    print("F0 GATE BACKTEST — declarative multi-TF setups")
    print(f"  period   : {start.date()} -> {end.date()} (IS/OOS 70/30 chronological)")
    print(f"  exchange : {args.exchange}")
    print(f"  fees     : {args.fee_rate * 100:.3f}% + {args.slippage * 100:.3f}% slippage per side")
    print(f"  setups   : {', '.join(args.setups)}")
    print(f"  rule_ver : {setups[0].rule_version}")

    full_reports: Dict[str, Any] = {}
    gate_rows: List[Dict[str, Any]] = []

    for symbol in args.symbols:
        print(f"\n== {symbol} " + "=" * 50)
        # Symbols listed after --start have no data at the requested since:
        # retry with progressively later starts instead of aborting the run.
        report = None
        for attempt_start in _start_candidates(start, end):
            service = SetupBacktestService(
                symbol=symbol,
                exchange=args.exchange,
                start=attempt_start,
                end=end,
                setups=setups,
                initial_capital=args.capital,
                risk_per_trade_pct=args.risk_pct,
                risk_profile=args.risk_profile,
                fee_rate_per_side=args.fee_rate,
                slippage_per_side=args.slippage,
            )
            try:
                report = service.run()
                if attempt_start != start:
                    print(f"  (data starts late: effective start {attempt_start.date()})")
                break
            except ValueError as exc:
                print(f"  retry with later start ({attempt_start.date()}): {exc}")
        if report is None:
            print(f"  SKIPPED {symbol}: no OHLCV data in any attempted range")
            continue
        full_reports[symbol] = report

        families: Dict[str, List[Dict[str, Any]]] = {}
        for setup_id, block in report["setups"].items():
            _print_setup_block(symbol, block)
            family = setup_id.rsplit("-", 1)[0]
            families.setdefault(family, []).append(block)

        for family, blocks in sorted(families.items()):
            gate_rows.append(_gate_row(family, symbol, blocks))

    print("\n" + "=" * 66)
    print("GATE MATRIX (§C thresholds, per setup family x symbol, both sides)")
    print(f"{'family':<10}{'symbol':<12}{'n':>5}{'nOOS':>6}{'expR':>8}{'expOOS':>8}{'PFoos':>8}{'maxDD%':>8}  result")
    for row in gate_rows:
        print(
            f"{row['family']:<10}{row['symbol']:<12}{row['n_full']:>5}{row['n_oos']:>6}"
            f"{_fmt(row['expectancy_full'])}{_fmt(row['expectancy_oos'])}"
            f"{_fmt(row['profit_factor_oos'])}{row['max_drawdown_pct']:>8.2f}"
            f"  {'PASS' if row['pass'] else 'NO PASS'}"
        )
        failed = [name for name, ok in row["checks"].items() if not ok]
        if failed:
            print(f"{'':<22}failed: {', '.join(failed)}")

    if args.json_out:
        payload = {"gate": gate_rows, "reports": full_reports, "thresholds": GATE_THRESHOLDS}
        Path(args.json_out).write_text(json.dumps(payload, indent=2, default=str))
        print(f"\nJSON report written to {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
