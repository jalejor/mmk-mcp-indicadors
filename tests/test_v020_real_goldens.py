"""v0.2.0 real-candle goldens — BTC/USDT Bitget, 2026-07-13 16:00 UTC.

The case that motivated the v0.2.0 rules (owner, 2026-07-13): a REAL 1d
bearish impulse (−2.27%) that the low-TF monitors adjudicated as false while
the 4h confirmed it grade A. Candles are committed fixtures (see
tests/fixtures/README.md); indicators are recomputed here with the exact
production enrichment (IndicatorsService.calculate_all), so these tests pin
the whole pipeline — data -> indicators -> v1 states -> v0.2.0 hierarchy.

No network: fixtures are static JSON. Slowest tests of the suite (~4 full
enrichments) but the only ones exercising real market shapes.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from controllers.metrics.indicators_service import IndicatorsService
from controllers.metrics.rule_v020 import (
    FE_FALSE_ENTRY_CONFIRMED,
    confluence_alignment,
    evaluate_confluence,
    false_entry_state_v2,
    higher_confirmed_source,
)
from controllers.metrics.setup_service import (
    FE_CONFIRMED,
    FE_FALSE_ENTRY_PROBABLE,
    false_entry_state,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def frames():
    """Enriched frames at the golden instant (closed candles only)."""
    enriched = {}
    for tf in ("30m", "1h", "4h", "1d"):
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
        enriched[tf] = service.df
    return enriched


def _fe_v1(frame, direction="down"):
    return false_entry_state(
        frame["ao"], frame["adx14"], frame["plus_di"], frame["minus_di"],
        direction=direction,
    )


def _fe_v2(frame, direction="down"):
    return false_entry_state_v2(
        frame["ao"], frame["adx14"], frame["plus_di"], frame["minus_di"],
        direction=direction,
    )


# ---------------------------------------------------------------------------
# H1 golden — the 4h CONFIRMED must override the low-TF timeout verdicts
# ---------------------------------------------------------------------------

def test_v1_states_reproduce_the_2026_07_13_case(frames):
    # What prod (v0.1.0) said at 16:00 UTC — everything audible was "false"
    # while the impulse was real (the owner's complaint, verbatim).
    fe_30m = _fe_v1(frames["30m"])
    fe_1h = _fe_v1(frames["1h"])
    fe_4h = _fe_v1(frames["4h"])

    assert fe_30m.state == FE_FALSE_ENTRY_PROBABLE
    assert fe_30m.event_age == 34
    assert fe_1h.state == FE_FALSE_ENTRY_PROBABLE
    assert fe_1h.event_age == 17
    assert fe_4h.state == FE_CONFIRMED
    assert fe_4h.adx_turn == {"fired": True, "age": 0, "grade": "A"}


def test_h1_overrides_the_false_verdicts_with_the_4h_confirmation(frames):
    # v0.2.0: the same series feed the v2 machine; the 4h CONFIRMED down is
    # the H1 Rule-1 source for BOTH lower watches (ladder walk). On the real
    # candles the low-TF v2 verdicts are even STRONGER than the v1 timeout —
    # a genuine DI color flip adjudicated FALSE_ENTRY_CONFIRMED (0.80) on
    # both — which is exactly what Rule 1 exists to override ("this overrides
    # both the age-5 timeout AND the adjudicated_color flip", spec §I.3).
    assert _fe_v2(frames["4h"]).state == FE_CONFIRMED

    fe_30m = _fe_v2(frames["30m"])
    fe_1h = _fe_v2(frames["1h"])
    assert fe_30m.state == FE_FALSE_ENTRY_CONFIRMED
    assert fe_30m.color_flip_age == 3
    assert fe_1h.state == FE_FALSE_ENTRY_CONFIRMED
    assert fe_1h.color_flip_age == 2

    confirmed_map = {"4h": ("down",)}
    assert higher_confirmed_source("30m", "down", confirmed_map) == "4h"
    assert higher_confirmed_source("1h", "down", confirmed_map) == "4h"
    # The up direction is NOT protected (no false symmetric rescue).
    assert higher_confirmed_source("30m", "up", confirmed_map) is None


# ---------------------------------------------------------------------------
# C1 golden (C1-G1) — {30m,1h,4h} bear-aligned, 1d still retracing
# ---------------------------------------------------------------------------

def test_c1_g1_bear_confluence_fires_with_1d_in_retracement(frames):
    for tf, mode in (("30m", "low"), ("1h", "low"), ("4h", "high")):
        alignment = confluence_alignment(frames[tf], direction="bear", mode=mode)
        assert alignment["aligned"], (tf, alignment)
    # The 1d is retracing, not bear-aligned (the window's annotation).
    assert not confluence_alignment(frames["1d"], direction="bear", mode="high")["aligned"]

    entries = evaluate_confluence(frames)
    fired = {(e["window_id"], e["direction"]) for e in entries}
    assert ("30m-1h-4h", "bear") in fired
    entry = next(e for e in entries if e["window_id"] == "30m-1h-4h")
    assert entry["profiles"] == ["snipper", "pro"]
    assert entry["annotation"] == "1d probablemente en retroceso"
    # Bull never fires anywhere on this market, and the Ancient window
    # (needs 1w, absent) is skipped rather than mis-fired.
    assert all(e["direction"] == "bear" for e in entries)
