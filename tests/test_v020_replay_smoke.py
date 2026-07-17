"""v0.2.x aggregate replay-smoke invariants on frozen fixtures (adversarial net).

Walks the committed BTC/USDT Bitget fixtures (2026-07-13 16:00 window) candle
by candle — a miniature of the §I.6 replay harness — and asserts AGGREGATE
distribution invariants that no single-instant golden can see:

* FALSE adjudications MUST exist (> 0). The shipped-0.2.0 P0 (H1 Rule-1
  granting rescues off STALE confirms) suppressed every FALSE verdict on BTC
  in the 120d replay (0 FALSE, monitor dead, M2 without sources) while every
  point-in-time golden stayed green. This is the net that would have caught it.
* CONFIRMED_BY_HIGHER_TF occurs (the 2026-07-13 golden rescue closes this very
  window) but stays a MINORITY of terminal adjudications — the stale-rescue
  bug made it dominate (239/325 finals on BTC).

Episodes are tracked at the STATE level through the H1 finalization path
(`_tf_snapshots` -> `_confirmed_directions` -> `_finalized_m1_records`), the
replay's adjudication semantics — the emission gate (`_should_emit_fe`) hides
late rescues by design, so the public `false_entry_watch` cannot see them.

No network: fixtures are static JSON, enriched once with the production
pipeline; per-step frames are row-slices of the enriched frames (all
indicators are causal, so slicing the tail is equivalent to a causal replay).
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from controllers.metrics.indicators_service import IndicatorsService
from controllers.metrics.monitors_v020 import (
    _candle_close_ts,
    _confirmed_directions,
    _finalized_m1_records,
    _tf_snapshots,
)
from controllers.metrics.setup_service import TIMEFRAME_SECONDS

FIXTURES = Path(__file__).parent / "fixtures"
# The FULL M1 operative ladder. The 1w matters adversarially: a weekly
# CONFIRMED lingers for months, so without the freshness grant condition it
# rescues everything below in its direction — with only the sub-weekly TFs
# the shipped bug barely changes this window's aggregates (measured while
# building this net: buggy-vs-fixed differed by ONE episode without the 1w;
# with it, buggy collapses to 0 FALSE / CBHT-dominant on EVERY 120d window).
FIXTURE_TFS = ("30m", "1h", "4h", "1d", "1w")

# Slide over the last N closed 30m candles of the fixture window (5 days —
# enough episodes for the invariants while keeping the suite fast).
REPLAY_STEPS = 240

TERMINAL_STATES = {
    "CONFIRMED", "WHIPSAW", "FALSE_ENTRY_PROBABLE",
    "FALSE_ENTRY_CONFIRMED", "CONFIRMED_BY_HIGHER_TF",
}
FALSE_STATES = {"FALSE_ENTRY_PROBABLE", "FALSE_ENTRY_CONFIRMED"}


@pytest.fixture(scope="module")
def enriched():
    frames = {}
    for tf in FIXTURE_TFS:
        rows = json.loads(
            (FIXTURES / f"btc_usdt_bitget_{tf}_20260713T1600.json").read_text()
        )
        df = pd.DataFrame(
            rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("datetime")
        service = IndicatorsService(df)
        service.calculate_all()
        frames[tf] = service.df
    return frames


def _final_states(enriched_frames):
    """Last observed state per (tf, direction, cross) episode over the walk.

    An episode's final state is the state it held the last time the machine
    computed it — either the walk's end or the step before a newer cross
    superseded it (the same convention the §I.6 replay harness adjudicates
    with; a lapsed rescue therefore reverts, per the freshness semantics)."""
    base = enriched_frames["30m"]
    step_closes = [
        open_ts + pd.Timedelta(seconds=TIMEFRAME_SECONDS["30m"])
        for open_ts in base.index[-REPLAY_STEPS:]
    ]
    episodes = {}
    for now in step_closes:
        sliced = {
            tf: frame[
                frame.index + pd.Timedelta(seconds=TIMEFRAME_SECONDS[tf]) <= now
            ]
            for tf, frame in enriched_frames.items()
        }
        tf_status = {}
        snapshots = _tf_snapshots(sliced, tf_status)
        assert all(status.startswith("failed") is False for status in tf_status.values())
        confirmed_map = _confirmed_directions(snapshots)
        vol_moves = {
            tf: snap["move"]
            for tf, snap in snapshots.items()
            if snap["vol_turn"] is not None and snap["move"] is not None
        }
        for record in _finalized_m1_records(snapshots, confirmed_map, vol_moves):
            tf = record["timeframe"]
            cross_ts = _candle_close_ts(sliced[tf], tf, record["raw"].event_age)
            episodes[(tf, record["direction"], cross_ts)] = record["state"]
    return episodes


def test_replay_smoke_invariants_false_exists_and_cbht_in_band(enriched):
    episodes = _final_states(enriched)
    finals = list(episodes.values())
    assert all(s in TERMINAL_STATES | {"WATCHING"} for s in finals)

    adjudicated = [s for s in finals if s in TERMINAL_STATES]
    false_finals = [s for s in finals if s in FALSE_STATES]
    cbht_finals = [s for s in finals if s == "CONFIRMED_BY_HIGHER_TF"]

    # The smoke must have signal at all before its invariants mean anything.
    assert len(adjudicated) >= 10, finals

    # THE P0 NET: false verdicts must exist. Stale rescues drove this to 0.
    assert len(false_finals) > 0, f"monitor dead: {finals}"

    # CBHT happens (the 2026-07-13 golden rescue closes this window) but must
    # remain a minority — stale rescues made it dominate (239/325 on BTC).
    assert len(cbht_finals) >= 1, finals
    cbht_share = len(cbht_finals) / len(adjudicated)
    assert cbht_share <= 0.5, f"CBHT dominates ({cbht_share:.2f}): {finals}"
