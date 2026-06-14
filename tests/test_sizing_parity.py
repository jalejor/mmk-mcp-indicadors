"""Golden parity test: live (MovementsService) and backtest (BacktestService)
sizing must be numerically identical for the same
symbol + ATR + equity + risk_profile.

Before unification the two engines used different formulas (live derived
atr_mult/r_multiple from the risk_profile, backtest used fixed 1.5/3.0), so a
backtest only validated the live recommendation for risk_profile="medium".
They now share `sizing_profiles.ATR_PROFILES`, so for low/medium/high the
stop_distance, target_distance and position quantity match exactly.
"""

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from controllers.metrics import movements_service as ms_module
from controllers.metrics.movements_service import MovementsService
from controllers.metrics.backtest_service import BacktestService
from controllers.metrics.sizing_profiles import ATR_PROFILES

# Shared, deterministic inputs for both engines.
SYMBOL = "BTC/USDT"
EQUITY = 10000.0
RISK_PER_TRADE_PCT = 1.5
ATR = 800.0
ENTRY_PRICE = 30000.0


def _flat_df(price: float = ENTRY_PRICE, n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    base = price + rng.normal(0, price * 0.001, size=n)
    df = pd.DataFrame(
        {
            "open": base,
            "high": base * 1.001,
            "low": base * 0.999,
            "close": base,
            "volume": np.full(n, 1000.0),
        },
        index=pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC"),
    )
    df.index.name = "datetime"
    return df


def _live_sizing(monkeypatch, risk_profile: str) -> dict:
    """Run MovementsService with a forced ATR and a fixed entry price."""
    df = _flat_df()
    # Pin the last close so entry == ENTRY_PRICE for an exact comparison.
    df.iloc[-1, df.columns.get_loc("close")] = ENTRY_PRICE
    monkeypatch.setattr(MovementsService, "_load_market_data", lambda self: df)

    real_calc_all = ms_module.IndicatorsService.calculate_all
    monkeypatch.setattr(
        ms_module.IndicatorsService,
        "calculate_all",
        lambda self: {**real_calc_all(self), "atr": ATR},
    )

    svc = MovementsService(
        symbol=SYMBOL,
        capital=EQUITY,
        risk_per_trade_pct=RISK_PER_TRADE_PCT,
        risk_profile=risk_profile,
        side="long",
        use_atr_sizing=True,
    )
    plan = svc.execute()["long"]
    stop_distance = plan["entry"] - plan["stop_loss"]
    target_distance = plan["target_price"] - plan["entry"]
    return {
        "stop_distance": stop_distance,
        "target_distance": target_distance,
        "quantity": plan["position_size_quantity"],
    }


def _backtest_sizing(risk_profile: str) -> dict:
    """Drive BacktestService's sizing path directly with the same inputs."""
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=30)
    svc = BacktestService(
        symbol=SYMBOL,
        start=start,
        end=end,
        initial_capital=EQUITY,
        risk_per_trade_pct=RISK_PER_TRADE_PCT,
        risk_profile=risk_profile,
        side="long",
    )

    bar = pd.Series({"open": ENTRY_PRICE, "high": ENTRY_PRICE, "low": ENTRY_PRICE,
                     "close": ENTRY_PRICE, "volume": 1000.0})
    trade = svc._maybe_open_trade(
        signal="entry",
        rules={"support_entry": []},
        bar=bar,
        bar_time=start,
        atr=ATR,
        equity=EQUITY,
    )
    assert trade is not None, "backtest did not open a trade for signal=entry"
    stop_distance = trade.entry_price - trade.stop_price
    target_distance = trade.target_price - trade.entry_price
    return {
        "stop_distance": stop_distance,
        "target_distance": target_distance,
        "quantity": trade.size,
    }


@pytest.mark.parametrize("risk_profile", ["low", "medium", "high"])
def test_live_backtest_sizing_parity(monkeypatch, risk_profile):
    live = _live_sizing(monkeypatch, risk_profile)
    bt = _backtest_sizing(risk_profile)

    atr_mult, r_multiple = ATR_PROFILES[risk_profile]
    expected_stop = ATR * atr_mult

    # Stop distance: both engines == ATR * atr_mult for the profile.
    assert bt["stop_distance"] == pytest.approx(expected_stop, rel=1e-9)
    # Live rounds the plan to 2 decimals; compare with that tolerance.
    assert live["stop_distance"] == pytest.approx(bt["stop_distance"], abs=0.01)

    # Target distance: both == stop_distance * r_multiple.
    assert bt["target_distance"] == pytest.approx(expected_stop * r_multiple, rel=1e-9)
    assert live["target_distance"] == pytest.approx(bt["target_distance"], abs=0.01)

    # The target/stop ratio (R multiple) must be identical.
    assert (live["target_distance"] / live["stop_distance"]) == pytest.approx(
        bt["target_distance"] / bt["stop_distance"], rel=1e-3
    )

    # Quantity sizing: dollar_risk / stop_distance, same in both engines.
    assert bt["quantity"] == pytest.approx(live["quantity"], rel=1e-9)


def test_medium_profile_matches_legacy_fixed_defaults():
    """The default profile must reproduce the old fixed 1.5/3.0 sizing so
    nothing changes for existing `medium` callers."""
    bt = _backtest_sizing("medium")
    assert bt["stop_distance"] == pytest.approx(ATR * 1.5, rel=1e-9)
    assert bt["target_distance"] == pytest.approx(ATR * 1.5 * 3.0, rel=1e-9)
