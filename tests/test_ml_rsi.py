"""ML RSI [BackQuant] port (impulsos-v2 round 3, owner decision 4) — offline."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_ta_classic as ta
import pytest

from controllers.metrics.ml_rsi import (
    MlRsiParams,
    alma,
    alma_weights,
    kmeans3,
    ml_rsi_frame,
    regime_of,
    regime_series,
    repaint_report,
    rsi,
    thresholds,
)

FIXTURE = Path(__file__).parent / "fixtures" / "btc_usdt_bitget_1d_closes_20261031.json"
# Owner's TradingView reading, BINANCE BTC/USDT 1d, 01-nov-2026 (ML RSI [BackQuant], RSI 19, ALMA 4 sigma 1).
OWNER_UPPER, OWNER_LOWER, OWNER_VALUE = 59.74, 44.30, 40.07


def _walk(n=600, seed=7):
    rng = np.random.default_rng(seed)
    return pd.Series(100.0 * np.exp(np.cumsum(rng.normal(0, 0.02, n))), index=pd.RangeIndex(n))


def _closes():
    rows = json.loads(FIXTURE.read_text())["rows"]
    idx = pd.to_datetime([r[0] for r in rows], unit="ms", utc=True)
    return pd.Series([r[1] for r in rows], index=idx, dtype=float)


# -- building blocks ---------------------------------------------------------

def test_alma_weights_offset0_put_the_heaviest_weight_on_the_oldest_sample():
    w = alma_weights(4, 0.0, 1.0)
    assert w[0] == pytest.approx(1.0)
    assert np.all(np.diff(w) < 0)
    assert w[3] == pytest.approx(np.exp(-9 / 32))


def test_alma_matches_the_pine_loop_on_a_small_series():
    s = pd.Series([1.0, 2.0, 4.0, 8.0, 16.0])
    w = alma_weights(4, 0.0, 1.0)
    # Pine: sum += series[length - i - 1] * weight[i]  -> i=0 is the oldest of the 4
    expected_last = (2.0 * w[0] + 4.0 * w[1] + 8.0 * w[2] + 16.0 * w[3]) / w.sum()
    out = alma(s, 4, 0.0, 1.0)
    assert np.isnan(out.iloc[2]) and out.iloc[-1] == pytest.approx(expected_last)


def test_wilder_rsi_matches_pandas_ta_after_the_seed_washes_out():
    """TV `ta.rsi` seeds the RMA with an SMA (this port); pandas_ta seeds with the
    first value. Both are Wilder RSI and converge geometrically (alpha = 1/19)."""
    close = _walk()
    mine = rsi(close, 19).to_numpy()
    ref = ta.rsi(close, length=19).to_numpy()
    ok = np.isfinite(ref) & np.isfinite(mine)
    assert ok.sum() > 500
    assert np.allclose(mine[-300:], ref[-300:], atol=1e-4)
    assert np.all(np.isfinite(mine[19:])) and np.isnan(mine[18])


def test_kmeans3_recovers_three_modes_and_ties_go_to_the_lowest_index():
    rng = np.random.default_rng(1)
    values = np.concatenate([rng.normal(20, 1, 200), rng.normal(50, 1, 200), rng.normal(80, 1, 200)])
    c = kmeans3(values)
    assert c[0] == pytest.approx(20, abs=0.5) and c[1] == pytest.approx(50, abs=0.5) and c[2] == pytest.approx(80, abs=0.5)
    assert np.isnan(kmeans3(np.array([1.0, 2.0, 3.0]))).all()  # Pine: size > 3 required


def test_thresholds_percentile_vs_kmeans_and_regime_labels():
    values = np.arange(1.0, 101.0)
    p = MlRsiParams()
    lo, hi = thresholds(values, p)
    assert (lo, hi) == (pytest.approx(25.75), pytest.approx(75.25))  # numpy linear = Pine percentile_linear_interpolation
    lo_k, hi_k = thresholds(values, MlRsiParams(threshold_method="kmeans"))
    assert lo_k < lo and hi_k > hi
    assert regime_of(80, 75, 25) == "green" and regime_of(10, 75, 25) == "red" and regime_of(50, 75, 25) == "gray"
    assert regime_of(75, 75, 25) == "gray" and regime_of(float("nan"), 75, 25) is None
    with pytest.raises(ValueError):
        MlRsiParams(threshold_method="median")


# -- lookahead / repaint -------------------------------------------------------

def test_causal_mode_never_uses_the_future():
    close = _walk(500)
    p = MlRsiParams(max_points=100)
    full = ml_rsi_frame(close, p)
    cut = ml_rsi_frame(close.iloc[:300], p)
    for col in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower"):
        a, b = full[col].iloc[:300].to_numpy(), cut[col].to_numpy()
        ok = np.isfinite(a) | np.isfinite(b)
        assert np.allclose(a[ok], b[ok], equal_nan=True)
    assert full["ml_rsi_regime"].iloc[:300].tolist() == cut["ml_rsi_regime"].tolist()
    reg = regime_series(full)
    assert set(reg.dropna().unique()) <= {-1.0, 0.0, 1.0}


def test_tv_mode_is_anchored_to_the_last_bar_and_agrees_on_it():
    close = _walk(500)
    p = MlRsiParams(max_points=100)
    causal, tv = ml_rsi_frame(close, p, mode="causal"), ml_rsi_frame(close, p, mode="tv")
    assert tv["ml_rsi_upper"].iloc[:399].isna().all()  # TV only collects the last 101 bars
    assert tv["ml_rsi_upper"].iloc[-1] == pytest.approx(causal["ml_rsi_upper"].iloc[-1])
    assert not np.allclose(tv["ml_rsi_upper"].iloc[400:450], causal["ml_rsi_upper"].iloc[400:450])
    rep = repaint_report(close, p, tail=50)
    assert rep["bars"] == 50 and rep["last_bar_identical"] and rep["upper_abs_diff_max"] > 0


# -- parity with the owner's TradingView reading (spec §R2.e2 gate) -----------

def test_owner_parity_thresholds_percentile_method():
    """What TV plots = 25/75 percentiles (array bug in the Pine): 59.76 / 44.09 vs owner 59.74 / 44.30."""
    last = ml_rsi_frame(_closes(), MlRsiParams()).iloc[-1]
    assert abs(float(last["ml_rsi_upper"]) - OWNER_UPPER) <= 2.0
    assert abs(float(last["ml_rsi_lower"]) - OWNER_LOWER) <= 2.0


def test_kmeans_method_does_not_reproduce_the_owner_thresholds():
    """Documents the finding: the k-means the script describes is dead code on TV."""
    last = ml_rsi_frame(_closes(), MlRsiParams(threshold_method="kmeans")).iloc[-1]
    assert abs(float(last["ml_rsi_upper"]) - OWNER_UPPER) > 5.0
    assert abs(float(last["ml_rsi_lower"]) - OWNER_LOWER) > 4.0


@pytest.mark.xfail(strict=True, reason="owner read the FORMING 2026-11-01 candle (~40.07); the closed 2026-10-31 "
                                       "candle gives 42.37 (raw RSI19 39.69). Value parity needs a same-candle reading.")
def test_owner_parity_value_on_the_closed_candle():
    last = ml_rsi_frame(_closes(), MlRsiParams()).iloc[-1]
    assert abs(float(last["ml_rsi"]) - OWNER_VALUE) <= 2.0


def test_fixture_is_the_closed_2026_10_31_daily_candle():
    closes = _closes()
    assert closes.index[-1] == pd.Timestamp("2026-10-31", tz="UTC")
    assert float(closes.iloc[-1]) == pytest.approx(77551.91)
    assert len(closes) >= 3001  # TV collects the last 3000 bars


def test_indicators_service_exposes_ml_rsi_additively():
    from controllers.metrics.indicators_service import IndicatorsService

    close = _walk(400)
    df = pd.DataFrame({"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1.0})
    svc = IndicatorsService(df)
    result = svc.calculate_all()
    for key in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower", "ml_rsi_regime", "ml_rsi_points"):
        assert key in result
    assert result["ml_rsi_regime"] in ("green", "red", "gray")
    assert result["ml_rsi_points"] > 300
    assert {"ml_rsi", "ml_rsi_upper", "ml_rsi_lower", "ml_rsi_regime"} <= set(svc.df.columns)
    assert "rsi14" in result and "bbwp" in result  # legacy keys intact
