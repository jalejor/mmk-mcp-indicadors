"""Tests for the FASE 3 ATR-based sizing on MovementsService."""

import numpy as np
import pandas as pd
import pytest

from controllers.metrics import movements_service as ms_module
from controllers.metrics.movements_service import MovementsService


def _flat_df(price: float = 30000.0, n: int = 300) -> pd.DataFrame:
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


def _patch_market_data(monkeypatch, df: pd.DataFrame):
    monkeypatch.setattr(MovementsService, "_load_market_data", lambda self: df)


def test_atr_sizing_stop_distance(monkeypatch):
    """`stop_distance` must equal ATR * atr_mult_stop."""
    df = _flat_df()
    _patch_market_data(monkeypatch, df)

    captured: dict = {}
    real_calc_all = ms_module.IndicatorsService.calculate_all

    def fake_calc(self):
        out = real_calc_all(self)
        out["atr"] = 1000.0  # force a deterministic ATR
        captured["atr"] = out["atr"]
        return out

    monkeypatch.setattr(ms_module.IndicatorsService, "calculate_all", fake_calc)

    svc = MovementsService(
        symbol="BTC/USDT",
        capital=10000.0,
        risk_profile="medium",  # atr_mult=1.5
        side="long",
        use_atr_sizing=True,
    )
    result = svc.execute()
    assert result["long"]["stop_distance"] == pytest.approx(1500.0, rel=1e-6)


def test_atr_sizing_r_multiple(monkeypatch):
    """target_distance / stop_distance must equal r_multiple."""
    df = _flat_df()
    _patch_market_data(monkeypatch, df)

    real_calc_all = ms_module.IndicatorsService.calculate_all
    monkeypatch.setattr(
        ms_module.IndicatorsService,
        "calculate_all",
        lambda self: {**real_calc_all(self), "atr": 500.0},
    )
    svc = MovementsService(
        symbol="BTC/USDT",
        capital=10000.0,
        risk_profile="medium",  # r_multiple = 3
        side="long",
        use_atr_sizing=True,
    )
    result = svc.execute()
    long_plan = result["long"]
    target_distance = long_plan["target_price"] - long_plan["entry"]
    stop_distance = long_plan["entry"] - long_plan["stop_loss"]
    assert target_distance / stop_distance == pytest.approx(3.0, rel=1e-3)


def test_legacy_pct_mode(monkeypatch):
    """With use_atr_sizing=False the output must match the legacy behaviour."""
    df = _flat_df(price=30000.0)
    _patch_market_data(monkeypatch, df)
    svc = MovementsService(
        symbol="BTC/USDT",
        capital=1000.0,
        risk_profile="medium",  # 5% / 3%
        side="both",
        use_atr_sizing=False,
    )
    result = svc.execute()
    entry = result["long"]["entry"]
    expected_stop = round(entry * (1 - 0.03), 2)
    assert result["long"]["stop_loss"] == pytest.approx(expected_stop, abs=0.01)
    # The ATR-sizing-only fields must be absent in legacy mode.
    assert "position_size_quantity" not in result["long"]


def test_position_size_respects_risk(monkeypatch):
    """`dollar_risk` should equal capital * risk_per_trade_pct / 100."""
    df = _flat_df()
    _patch_market_data(monkeypatch, df)
    real_calc_all = ms_module.IndicatorsService.calculate_all
    monkeypatch.setattr(
        ms_module.IndicatorsService,
        "calculate_all",
        lambda self: {**real_calc_all(self), "atr": 800.0},
    )
    svc = MovementsService(
        symbol="BTC/USDT",
        capital=10000.0,
        risk_per_trade_pct=1.5,
        risk_profile="medium",
        side="long",
        use_atr_sizing=True,
    )
    result = svc.execute()
    assert result["long"]["dollar_risk"] == pytest.approx(150.0, abs=0.01)
