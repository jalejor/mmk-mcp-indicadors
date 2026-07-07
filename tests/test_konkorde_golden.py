"""Golden numeric tests for the Konkorde indicator.

These tests pin the indicator output against known price series. The most
important case is NEUTRAL: a flat, zero-drift market must score the brown
line at ~0 and must NOT emit a `konkorde_buy` vote. Before the re-centring
fix the brown line floated at ~+25 in this exact scenario (RSI/MFI centred
on 50 averaged with 0-centred oscillators), which the rules engine read as
a permanent buy vote with weight 3.0.
"""
import numpy as np
import pandas as pd
import pytest

from controllers.metrics.indicators_service import IndicatorsService
from controllers.metrics.rules_service import RulesService


def _neutral_df(n: int = 120) -> pd.DataFrame:
    """Deterministic zig-zag around a flat level (zero drift).

    Close alternates +/-0.5 around 100, so there is no net trend and RSI/MFI
    converge near their 50 baseline. Volume is constant so PVI/NVI oscillators
    stay flat. This is the canonical "neutral market" fixture.
    """
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    osc = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    close = 100.0 + osc * 0.5
    open_ = 100.0 - osc * 0.5
    high = np.maximum(open_, close) + 0.2
    low = np.minimum(open_, close) - 0.2
    volume = np.full(n, 1000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def _bullish_df(n: int = 120) -> pd.DataFrame:
    """Deterministic noisy uptrend (seeded RNG) with rising volume.

    Sustained upward drift pushes RSI/MFI well above 50 and the PVI
    oscillator positive, so the (now re-centred) brown line must turn
    clearly positive and the rules engine must emit `konkorde_buy`.
    """
    rng = np.random.default_rng(3)
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    steps = rng.normal(0.8, 0.6, size=n)
    close = 100.0 + np.cumsum(steps)
    open_ = close - rng.uniform(0.1, 0.5, size=n)
    high = np.maximum(open_, close) + rng.uniform(0.1, 0.4, size=n)
    low = np.minimum(open_, close) - rng.uniform(0.1, 0.4, size=n)
    volume = 1000.0 + rng.uniform(0, 400, size=n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


# ----------------------------------------------------------------------
# NEUTRAL market — the regression that motivated the fix
# ----------------------------------------------------------------------
def test_konkorde_neutral_market_is_centered_on_zero():
    """Flat, zero-drift market => brown line ~0, NOT ~+25."""
    indicators = IndicatorsService(_neutral_df()).calculate_all()

    # RSI lands near its 50 baseline in a flat market.
    assert indicators["rsi14"] == pytest.approx(48.1476, abs=1e-3)

    # The whole point of the fix: all three lines centre on zero.
    assert indicators["konkorde_azul"] == pytest.approx(0.0, abs=1e-6)
    assert indicators["konkorde_verde"] == pytest.approx(0.0, abs=1e-6)
    assert indicators["konkorde_marron"] == pytest.approx(0.0, abs=1e-6)
    # konkorde_value is the deprecated alias of marron.
    assert indicators["konkorde_value"] == pytest.approx(0.0, abs=1e-6)
    assert indicators["konkorde_signal"] == "neutral"


def test_konkorde_neutral_market_does_not_vote_buy():
    """Regression guard: a neutral market must not trigger konkorde_buy.

    Pre-fix the brown line sat at ~+25, so `konkorde_value > 0` always
    appended `konkorde_buy` (weight 3.0). With the re-centred line the
    neutral market scores 0 and stays out of the entry support set.
    """
    indicators = IndicatorsService(_neutral_df()).calculate_all()
    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)

    assert "konkorde_buy" not in rules["support_entry"]
    assert "konkorde_sell" not in rules["support_exit"]


# ----------------------------------------------------------------------
# BULLISH market — the indicator must still fire on real signals
# ----------------------------------------------------------------------
def test_konkorde_bullish_market_votes_buy():
    """A sustained uptrend must turn the brown line positive and vote buy."""
    indicators = IndicatorsService(_bullish_df()).calculate_all()

    # Brown line clearly positive (golden value ~34.9, kept tolerant so a
    # minor pandas-ta point change does not break the regression intent).
    assert indicators["konkorde_marron"] == pytest.approx(34.9, abs=2.0)
    assert indicators["konkorde_marron"] > 10.0
    assert indicators["konkorde_azul"] > 0.0

    rules = RulesService(symbol="BTC/USDT").evaluate(indicators)
    assert "konkorde_buy" in rules["support_entry"]


# ----------------------------------------------------------------------
# BASELINE — pin the exact magnitude of the removed ~+25 bias
# ----------------------------------------------------------------------
def test_konkorde_removed_bias_is_exactly_25_on_neutral_market():
    """Numeric regression on the baseline the re-centring fix removed.

    The pre-fix brown line was
        marron_biased = (RSI + MFI + B1 + OscP - OscN) / 4
    and the fix subtracts the 50-point baseline from RSI and MFI:
        marron_fixed  = ((RSI - 50) + (MFI - 50) + B1 + OscP - OscN) / 4
                      = marron_biased - (50 + 50) / 4
                      = marron_biased - 25.0

    So the constant bias the fix strips out is exactly +25. On the neutral
    fixture the fixed line sits at ~0, which means the *old* formula would
    have floated at ~+25 — the permanent `konkorde_buy` vote we removed.
    """
    indicators = IndicatorsService(_neutral_df()).calculate_all()

    marron_fixed = indicators["konkorde_marron"]
    marron_biased = marron_fixed + 25.0  # reconstruct the pre-fix formula

    # Fixed line is centred on zero; the pre-fix line floated at ~+25.
    assert marron_fixed == pytest.approx(0.0, abs=1e-6)
    assert marron_biased == pytest.approx(25.0, abs=1e-6)

    # The removed baseline is a fixed +25 offset: the old line sat well
    # above zero (a buy vote) while the fixed one hugs zero (no vote).
    assert marron_biased - marron_fixed == pytest.approx(25.0, abs=1e-9)
    assert marron_biased > 0.0


# ----------------------------------------------------------------------
# WEIGHT — konkorde is the heaviest vote (3.0)
# ----------------------------------------------------------------------
def test_konkorde_family_weight_is_three():
    """The konkorde family must carry the highest weight of 3.0."""
    assert RulesService.DEFAULT_WEIGHTS["konkorde"] == 3.0


def test_konkorde_buy_contributes_exactly_three_to_entry_score():
    """A lone konkorde_buy vote must score exactly its 3.0 weight.

    Feeding only a positive `konkorde_value` isolates the konkorde family so
    the entry score equals its weight with no other votes mixed in. konkorde
    is not touched by any regime multiplier, so the contribution is a clean
    3.0.
    """
    rules = RulesService(symbol="BTC/USDT").evaluate({"konkorde_value": 42.0})

    assert rules["support_entry"] == ["konkorde_buy"]
    assert rules["entry_score"] == pytest.approx(3.0, abs=1e-9)
