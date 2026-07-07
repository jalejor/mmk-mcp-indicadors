"""Tests for the multi-TF setup backtest engine (spec §C).

No network: frames are synthetic and injected by monkeypatching
`_load_enriched_frame`. Golden numbers cover the §0.2 alignment rule and the
net-fee math (bitget base model, owner Q9).
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.setup_backtest_service import (
    CandidateSignal,
    SetupBacktestService,
)
from controllers.metrics.setup_definitions import (
    Condition,
    SetupDefinition,
    VetoDefinition,
)
from controllers.metrics.setup_service import SetupService


# ---------------------------------------------------------------------------
# §0.2 multi-TF alignment (golden from the spec)
# ---------------------------------------------------------------------------

def test_alignment_spec_example_4h_trigger_1d_context():
    """Trigger 4h candle closing 2026-07-06 08:00 UTC -> use the 1d candle
    covering 2026-07-05 (closed 2026-07-06 00:00), never the in-progress one."""
    context = pd.DataFrame(
        {"close": range(6)},
        index=pd.date_range("2026-07-01", periods=6, freq="D", tz="UTC"),
    )
    trigger_close = pd.Timestamp("2026-07-06 08:00:00", tz="UTC")
    aligned = SetupService.align_context(context, trigger_close, "1d")
    assert aligned.index[-1] == pd.Timestamp("2026-07-05", tz="UTC")


def test_alignment_includes_candle_closing_exactly_at_trigger_close():
    context = pd.DataFrame(
        {"close": range(6)},
        index=pd.date_range("2026-07-01", periods=6, freq="D", tz="UTC"),
    )
    trigger_close = pd.Timestamp("2026-07-06 00:00:00", tz="UTC")
    aligned = SetupService.align_context(context, trigger_close, "1d")
    # The candle opened 2026-07-05 closes exactly at the trigger close: usable.
    assert aligned.index[-1] == pd.Timestamp("2026-07-05", tz="UTC")


def test_alignment_never_leaks_future_context():
    context = pd.DataFrame(
        {"close": range(30)},
        index=pd.date_range("2026-06-01", periods=30, freq="D", tz="UTC"),
    )
    day = pd.Timedelta(days=1)
    for hour in (4, 8, 12, 16, 20, 0):
        trigger_close = pd.Timestamp(f"2026-06-15 {hour:02d}:00:00", tz="UTC")
        aligned = SetupService.align_context(context, trigger_close, "1d")
        assert all(idx + day <= trigger_close for idx in aligned.index)


# ---------------------------------------------------------------------------
# Synthetic end-to-end run
# ---------------------------------------------------------------------------

def _test_setup() -> SetupDefinition:
    return SetupDefinition(
        rule_version="0.0.1-test",
        setup_id="TEST-4H-LONG",
        side="long",
        timeframe_band="high_tf",
        context_timeframe="1d",
        trigger_timeframe="4h",
        context_all_of=(Condition("bbwp_regime", timeframe="1d"),),
        trigger_all_of=(Condition("ao_positive"), Condition("ao_rising")),
        vetoes=(VetoDefinition("adx_confirmation", variant="up_bullish", confirm_window=5),),
    )


def _synthetic_frames():
    """70 days of 1d context + 4h trigger data with two engineered signals.

    Candidate 1 (accepted): AO turns positive with a fresh E1-G1-shaped ADX
    turn; the next bar prints high 110 -> target hit.
    Candidate 2 (vetoed): AO turns positive again but ADX stays flat ->
    no_adx_turn_confirmation; hypothetically stops out (low 96).
    """
    idx_1d = pd.date_range("2026-01-01", periods=70, freq="D", tz="UTC")
    frame_1d = pd.DataFrame(
        {
            "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0,
            "volume": 1000.0, "bbwp": 60.0,
        },
        index=idx_1d,
    )

    n4h = 70 * 6
    idx_4h = pd.date_range("2026-01-01", periods=n4h, freq="4h", tz="UTC")
    ao = np.full(n4h, -1.0)
    adx = np.full(n4h, 18.0)
    plus_di = np.full(n4h, 28.0)
    minus_di = np.full(n4h, 15.0)
    high = np.full(n4h, 100.5)
    low = np.full(n4h, 99.5)
    close = np.full(n4h, 100.0)

    # Candidate 1 at 2026-03-01 00:00 (bar index 59*6 = 354).
    c1 = 354
    ao[c1: c1 + 3] = [0.5, 0.7, 0.9]
    adx[c1 - 2: c1 + 1] = [18.5, 21.5, 24.5]  # E1-G1 shape ending at c1
    high[c1 + 1] = 110.0  # target (109.0) hit on the next bar

    # Candidate 2 at 2026-03-06 00:00 (bar index 64*6 = 384): flat ADX.
    c2 = 384
    ao[c2: c2 + 3] = [0.5, 0.7, 0.9]
    low[c2 + 1] = 96.0  # stop (97.0) hit on the next bar

    frame_4h = pd.DataFrame(
        {
            "open": close, "high": high, "low": low, "close": close,
            "volume": 1000.0, "ao": ao, "adx14": adx,
            "plus_di": plus_di, "minus_di": minus_di, "atr14": 2.0,
        },
        index=idx_4h,
    )
    return {"1d": frame_1d, "4h": frame_4h}


def _make_service(monkeypatch, **overrides) -> SetupBacktestService:
    frames = _synthetic_frames()
    defaults = dict(
        symbol="BTC/USDT",
        start=datetime(2026, 2, 25, tzinfo=timezone.utc),
        end=datetime(2026, 3, 11, tzinfo=timezone.utc),
        setups=[_test_setup()],
        initial_capital=10000.0,
        risk_per_trade_pct=1.5,
    )
    defaults.update(overrides)
    service = SetupBacktestService(**defaults)
    monkeypatch.setattr(service, "_load_enriched_frame", lambda tf: frames[tf])
    return service


def test_run_accepts_confirmed_and_vetoes_unconfirmed(monkeypatch):
    service = _make_service(monkeypatch)
    report = service.run()
    block = report["setups"]["TEST-4H-LONG"]

    assert block["candidates"] == 2
    assert block["full"]["n_trades"] == 1  # candidate 2 was vetoed
    assert block["vetoed_signals"]["count"] == 1
    assert block["vetoed_signals"]["by_reason"] == {"no_adx_turn_confirmation": 1}


def test_net_fee_math_golden(monkeypatch):
    """Target hit: gross +9.0 on stop distance 3.0 (medium profile, ATR 2.0).
    Net R = (9 - 0.0015 * (100 + 109)) / 3 = 2.8955."""
    service = _make_service(monkeypatch)
    report = service.run()
    trades = report["setups"]["TEST-4H-LONG"]["trades"]
    assert len(trades) == 1
    assert trades[0]["exit_reason"] == "target"
    assert trades[0]["r_net"] == pytest.approx(2.8955, abs=1e-4)

    # Vetoed counterfactual: stop-out -> (-3 - 0.0015 * (100 + 97)) / 3 = -1.0985.
    vetoed = report["setups"]["TEST-4H-LONG"]["vetoed_signals"]
    assert vetoed["counterfactual_expectancy_R"] == pytest.approx(-1.0985, abs=1e-4)
    assert vetoed["accepted_expectancy_R"] == pytest.approx(2.8955, abs=1e-4)


def test_grade_stratification_and_window_comparison(monkeypatch):
    service = _make_service(monkeypatch)
    report = service.run()
    block = report["setups"]["TEST-4H-LONG"]

    # The accepted trade was confirmed by a turn pivoting from 18 -> A-grade.
    assert block["adx_turn_grades"]["A"]["n_trades"] == 1
    assert block["adx_turn_grades"]["B"]["n_trades"] == 0

    # Q10 comparison: same decisions under windows 3 and 5 in this scenario.
    comparison = block["vetoed_signals"]["window_comparison"]
    for window in ("3", "5"):
        assert comparison[window]["accepted_n"] == 1
        assert comparison[window]["vetoed_n"] == 1


def test_is_oos_split_is_chronological(monkeypatch):
    service = _make_service(monkeypatch)
    report = service.run()
    block = report["setups"]["TEST-4H-LONG"]
    # Boundary = start + 0.7 * 14d = 2026-03-06 19:12; the accepted trade
    # (2026-03-01) falls in-sample.
    assert block["in_sample"]["n_trades"] == 1
    assert block["out_of_sample"]["n_trades"] == 0
    assert report["period"]["in_sample_fraction"] == 0.7


def test_zero_fees_recover_gross_r(monkeypatch):
    service = _make_service(monkeypatch, fee_rate_per_side=0.0, slippage_per_side=0.0)
    report = service.run()
    trades = report["setups"]["TEST-4H-LONG"]["trades"]
    assert trades[0]["r_net"] == pytest.approx(3.0, abs=1e-9)  # pure 3R target


def test_portfolio_skips_overlapping_candidates():
    service = SetupBacktestService(
        symbol="BTC/USDT",
        start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        setups=[_test_setup()],
    )
    first = CandidateSignal(
        setup_id="TEST-4H-LONG", side="long", bar_index=10,
        entry_time=datetime(2026, 1, 10, tzinfo=timezone.utc),
        entry_price=100.0, atr=2.0,
    )
    first.exit_time = datetime(2026, 1, 20, tzinfo=timezone.utc)
    first.exit_price = 109.0
    overlapping = CandidateSignal(
        setup_id="TEST-4H-LONG", side="long", bar_index=15,
        entry_time=datetime(2026, 1, 15, tzinfo=timezone.utc),
        entry_price=100.0, atr=2.0,
    )
    overlapping.exit_time = datetime(2026, 1, 25, tzinfo=timezone.utc)
    overlapping.exit_price = 109.0
    trades = service._execute_portfolio([first, overlapping])
    assert len(trades) == 1
    assert trades[0].candidate is first


def test_report_carries_fee_model_and_rule_version(monkeypatch):
    service = _make_service(monkeypatch)
    report = service.run()
    assert report["fee_model"] == {
        "fee_rate_per_side": 0.001, "slippage_per_side": 0.0005,
    }
    assert report["rule_version"] == "0.0.1-test"
    assert report["sizing"]["atr_stop_multiplier"] == 1.5  # medium profile parity
    assert report["sizing"]["target_r_multiple"] == 3.0
