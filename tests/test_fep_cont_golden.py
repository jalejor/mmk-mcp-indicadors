"""Goldens for the R-FEP-CONT study engine (docs/PREREG_FEP_CONT_v0.3.0.md).

Re-council 2026-08-16, blocking condition #2: *"todo criterio pre-registrado
nace con el test que lo computa, verde sobre datos sinteticos, el dia que se
congela"*. This file is that test. It pins:

1. the net-R arithmetic of the committed outcome resolver (hand-computed
   numbers, fees included) — long, short and the stop-wins-intrabar rule;
2. the arm classification (FEP-CONT / CONFIRMED / WHIPSAW / BASE-RATE) on
   the spec's own M1 golden arrays;
3. the 300-bar trailing-window equivalence the study relies on for runtime,
   on committed real candles.

If any of these drift, the study's numbers are invalid.
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

import pandas as pd
import pytest

from controllers.metrics.fep_cont_backtest import (
    ARM_BASE_RATE,
    ARM_CONFIRMED,
    ARM_FEP_CONT,
    ARM_WHIPSAW,
    FepContBacktest,
    metrics_block,
    outcome_vara,
    portfolio_subset,
)
from controllers.metrics.setup_backtest_service import SetupBacktestService

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
START = datetime(2020, 1, 1, tzinfo=timezone.utc)
END = datetime(2030, 1, 1, tzinfo=timezone.utc)
BOUNDARY = datetime(2025, 1, 1, tzinfo=timezone.utc)


def _engine(**kwargs) -> FepContBacktest:
    params = dict(
        symbol="TEST/USDT", timeframe="1h", start=START, end=END,
        is_boundary=BOUNDARY, exchange="binance",
    )
    params.update(kwargs)
    return FepContBacktest(**params)  # type: ignore[arg-type]


def _frame(rows, *, ao=None, adx=None, pdi=None, mdi=None, atr=2.0):
    """Minimal enriched frame: OHLC + the columns the study reads."""
    idx = pd.date_range("2026-01-01", periods=len(rows), freq="1h", tz="UTC")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["timestamp"] = (df.index.astype("int64") // 1_000_000).astype("int64")
    df["volume"] = 1.0
    df["atr14"] = atr
    n = len(rows)
    df["ao"] = ao if ao is not None else [0.0] * n
    df["adx14"] = adx if adx is not None else [25.0] * n
    df["plus_di"] = pdi if pdi is not None else [28.0] * n
    df["minus_di"] = mdi if mdi is not None else [15.0] * n
    return df


# ---------------------------------------------------------------------------
# 1. Outcome resolver — hand-computed net R (the yardstick itself)
# ---------------------------------------------------------------------------
# entry 100, ATR 2 -> stop distance 1.5*2 = 3; medium profile target = 3R.
# cost_per_unit = (0.0010 + 0.0005) * (entry + exit)
#   long  target 109: (9 - 0.0015*209) / 3 = (9 - 0.3135)/3   = +2.895500
#   short target  91: (9 - 0.0015*191) / 3 = (9 - 0.2865)/3   = +2.904500
#   long  stop    97: (-3 - 0.0015*197)/3  = (-3 - 0.2955)/3  = -1.098500

def test_resolver_long_target_net_r():
    df = _frame([(100, 100, 100, 100), (100, 110, 99, 109), (109, 109, 109, 109)])
    eng = _engine()
    sig = eng.resolve_event(df, _event(ARM_BASE_RATE, 0, "long"))
    assert sig is not None
    assert sig.exit_reason == "target"
    assert sig.stop_price == pytest.approx(97.0)
    assert sig.target_price == pytest.approx(109.0)
    assert sig.r_net == pytest.approx(2.8955, abs=1e-6)


def test_resolver_short_target_net_r():
    df = _frame([(100, 100, 100, 100), (100, 101, 90, 91), (91, 91, 91, 91)])
    eng = _engine()
    sig = eng.resolve_event(df, _event(ARM_BASE_RATE, 0, "short"))
    assert sig is not None
    assert sig.exit_reason == "target"
    assert sig.stop_price == pytest.approx(103.0)
    assert sig.target_price == pytest.approx(91.0)
    assert sig.r_net == pytest.approx(2.9045, abs=1e-6)


def test_resolver_stop_wins_inside_the_same_bar():
    """Worst case: a bar that touches both must exit at the stop."""
    df = _frame([(100, 100, 100, 100), (100, 110, 96, 105), (105, 105, 105, 105)])
    eng = _engine()
    sig = eng.resolve_event(df, _event(ARM_BASE_RATE, 0, "long"))
    assert sig is not None
    assert sig.exit_reason == "stop"
    assert sig.r_net == pytest.approx(-1.0985, abs=1e-6)


def test_resolver_is_the_committed_one():
    """The study must not own a private copy of the resolver."""
    assert FepContBacktest.resolve_event.__module__.endswith("fep_cont_backtest")
    assert hasattr(SetupBacktestService, "_simulate_outcome")
    eng = _engine()
    assert eng._resolver_host.atr_stop_multiplier == 1.5
    assert eng._resolver_host.target_r_multiple == 3.0
    assert "resolver=setup_backtest_service._simulate_outcome" in eng.vara()


def test_time_stop_sensitivity_truncates_the_forward_frame():
    """S2 must be produced by the SAME resolver, on a truncated future."""
    flat = [(100, 100.5, 99.5, 100)] * 12
    df = _frame([(100, 100, 100, 100)] + flat)
    sig = _engine(time_stop_bars=5).resolve_event(df, _event(ARM_BASE_RATE, 0, "long"))
    assert sig is not None
    assert sig.exit_reason == "time_stop"
    assert sig.bars_held == 5


def test_next_open_entry_lets_the_next_bar_stop_the_trade():
    """S1 enters at the next open and that same bar can already resolve."""
    df = _frame([(100, 100, 100, 100), (101, 101, 95, 96), (96, 96, 96, 96)])
    sig = _engine(entry_mode="next_open").resolve_event(df, _event(ARM_BASE_RATE, 0, "long"))
    assert sig is not None
    assert sig.entry_price == pytest.approx(101.0)
    assert sig.stop_price == pytest.approx(98.0)  # 101 - 1.5*2
    assert sig.exit_reason == "stop"


def test_outcome_vara_is_stamped_and_stable():
    assert outcome_vara(
        atr_stop_multiplier=1.5, target_r_multiple=3.0,
        fee_rate_per_side=0.001, slippage_per_side=0.0005,
        entry_mode="close", time_stop_bars=None,
    ) == (
        "atr14x1.5_stop|3.0R_target|stop_first_intrabar|"
        "fee0.001+slip0.0005_per_side|"
        "resolver=setup_backtest_service._simulate_outcome|entry=close"
    )


# ---------------------------------------------------------------------------
# 2. Arm classification — the spec's own M1 goldens, wired to the study
# ---------------------------------------------------------------------------

def _event(arm, bar_index, side):
    from controllers.metrics.fep_cont_backtest import ArmEvent

    return ArmEvent(arm=arm, bar_index=bar_index, side=side,
                    direction="up" if side == "long" else "short")


def _state_arm_events(ao, adx, pdi, mdi):
    """Run the detector over a synthetic series with warm-up disabled."""
    n = len(ao)
    price = [(100, 100.2, 99.8, 100)] * n
    df = _frame(price, ao=ao, adx=adx, pdi=pdi, mdi=mdi)
    eng = _engine(warmup_bars=1, base_rate_stride=10_000)
    return [e for e in eng.detect_events(df) if e.arm != ARM_BASE_RATE]


def test_arm_fep_cont_fires_on_the_m1_g1_golden():
    """M1-G1: AO crosses up, ADX slope never turns -> FEP at age 5, long."""
    ao = [-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, 1.8, 2.0, 2.2]
    adx = [24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4]
    events = _state_arm_events(ao, adx, [28.0] * 9, [15.0] * 9)
    fep = [e for e in events if e.arm == ARM_FEP_CONT]
    assert len(fep) == 1
    assert fep[0].side == "long"
    assert fep[0].direction == "up"
    assert fep[0].event_age == 5  # the rule fires exactly on the 5th candle
    assert fep[0].bar_index == 6


def test_arm_fep_cont_bearish_mirror_is_a_short():
    ao = [0.5, -0.4, -0.8, -1.1, -1.3, -1.6, -1.8, -2.0, -2.2]
    adx = [24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4]
    events = _state_arm_events(ao, adx, [15.0] * 9, [28.0] * 9)
    fep = [e for e in events if e.arm == ARM_FEP_CONT]
    assert len(fep) == 1
    assert fep[0].side == "short"
    assert fep[0].direction == "down"


def test_confirmed_arm_is_not_the_fep_arm():
    """M1-G2 (spec §B.3.1): an igniting ADX turn inside the 5-candle window
    lands in CONFIRMED and must never be counted as the hypothesis arm."""
    ao = [-0.9, -0.8, -0.7, -0.6, -0.5, 0.4, 0.8, 1.1, 1.3, 1.5]
    adx = [18.0] * 6 + [18.5, 21.5, 24.5, 26.0]  # flat, then the 90-degree turn
    events = _state_arm_events(ao, adx, [28.0] * 10, [15.0] * 10)
    arms = {e.arm for e in events}
    assert ARM_CONFIRMED in arms
    assert ARM_FEP_CONT not in arms
    confirmed = [e for e in events if e.arm == ARM_CONFIRMED][0]
    assert confirmed.adx_turn_grade == "A"  # same grade the spec golden pins
    assert confirmed.bar_index == 8


def test_whipsaw_arm_on_an_early_recross():
    ao = [-0.5, 0.4, 0.8, -0.3, -0.7, -1.0]
    adx = [24.6, 24.7, 24.8, 24.9, 25.0, 25.1]
    events = _state_arm_events(ao, adx, [28.0] * 6, [15.0] * 6)
    assert ARM_WHIPSAW in {e.arm for e in events}


def test_base_rate_arm_is_unconditional_and_two_sided():
    df = _frame([(100, 100.5, 99.5, 100)] * 61, ao=[0.0] * 61)
    eng = _engine(warmup_bars=0, base_rate_stride=20)
    base = [e for e in eng.detect_events(df) if e.arm == ARM_BASE_RATE]
    assert [e.bar_index for e in base] == [0, 0, 20, 20, 40, 40]
    assert sorted({e.side for e in base}) == ["long", "short"]


def test_edge_detector_does_not_emit_the_inherited_state():
    """The state carried by the first evaluated bar is not a transition."""
    ao = [-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, 1.8, 2.0, 2.2]
    adx = [24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4]
    df = _frame([(100, 100.2, 99.8, 100)] * 9, ao=ao, adx=adx,
                pdi=[28.0] * 9, mdi=[15.0] * 9)
    # Warm-up starts AFTER the FEP state already holds -> nothing is emitted.
    eng = _engine(warmup_bars=7, base_rate_stride=10_000)
    assert [e for e in eng.detect_events(df) if e.arm != ARM_BASE_RATE] == []


# ---------------------------------------------------------------------------
# 3. Trailing-window equivalence (the runtime shortcut the study depends on)
# ---------------------------------------------------------------------------

def test_state_window_300_matches_the_full_series_on_real_candles():
    rows = json.loads((FIXTURES / "btc_usdt_bitget_1h_20260713T1600.json").read_text())
    raw = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    raw["datetime"] = pd.to_datetime(raw["timestamp"], unit="ms", utc=True)
    raw = raw.set_index("datetime")
    enriched = SetupBacktestService.enrich(raw)

    start = enriched.index[0].to_pydatetime()
    end = enriched.index[-1].to_pydatetime()
    common = dict(symbol="BTC/USDT", timeframe="1h", start=start, end=end,
                  is_boundary=start, exchange="bitget", warmup_bars=50,
                  base_rate_stride=10_000)
    windowed = _engine(state_window_bars=300, **common).detect_events(enriched)
    full = _engine(state_window_bars=0, **common).detect_events(enriched)

    assert [e for e in windowed if e.arm != ARM_BASE_RATE] == [
        e for e in full if e.arm != ARM_BASE_RATE
    ]
    assert any(e.arm == ARM_FEP_CONT for e in windowed)  # the fixture is not empty


# ---------------------------------------------------------------------------
# 4. Aggregation helpers used by the gate
# ---------------------------------------------------------------------------

def test_portfolio_subset_drops_overlapping_signals():
    """Same rule as `_execute_portfolio`: skip anything opening before the
    open position closes (a signal on the exit bar itself is NOT overlapping)."""
    df = _frame([(100, 100, 100, 100), (100, 100.5, 99.5, 100),
                 (100, 100.5, 99.5, 100), (100, 110, 99, 109),
                 (109, 109, 109, 109)])
    eng = _engine()
    a = eng.resolve_event(df, _event(ARM_FEP_CONT, 0, "long"))
    b = eng.resolve_event(df, _event(ARM_FEP_CONT, 1, "long"))
    assert a is not None and b is not None
    assert a.exit_reason == "target" and a.bars_held == 3
    kept = portfolio_subset([a, b])
    assert len(kept) == 1  # b opens while a is still open
    assert kept[0].entry_time == a.entry_time


def test_metrics_block_matches_hand_computed_expectancy():
    df = _frame([(100, 100, 100, 100), (100, 110, 99, 109), (109, 109, 109, 109)])
    df2 = _frame([(100, 100, 100, 100), (100, 110, 96, 105), (105, 105, 105, 105)])
    eng = _engine()
    win = eng.resolve_event(df, _event(ARM_FEP_CONT, 0, "long"))
    loss = eng.resolve_event(df2, _event(ARM_FEP_CONT, 0, "long"))
    block = metrics_block([win, loss])
    assert block["n"] == 2
    assert block["expectancy_R"] == pytest.approx((2.8955 - 1.0985) / 2, abs=1e-4)
    assert block["win_rate"] == 0.5
