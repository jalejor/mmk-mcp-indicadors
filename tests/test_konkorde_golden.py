"""Goldens for the Koncorde (Blai5) port — `controllers.metrics.koncorde`.

Four layers:

1. Parity of the vectorised port against a literal, naive bar-by-bar
   re-reading of the public Pine script (independent code on purpose) on
   synthetic AND real candles.
2. Pine semantics pinned on hand-checkable series: line algebra
   (verde = marron + oscp, media = EMA15(marron)), the 0-100 scale of marron
   (NOT centred on zero — the pre-2026-11-01 "re-centring" was the bug),
   azul = NVI (volume-DOWN bars only), verde = PVI, warmup NaN, division by
   zero -> na.
3. Numeric goldens on the immutable bitget fixtures (last closed candle of
   2026-07-13 16:00 UTC) so any drift in a component is visible.
4. Consumer contract: `IndicatorsService` keys, the deprecated alias, and
   `RulesService` voting on marron vs media (never on `marron > 0`).

Live reconciliation that motivated the port (not reproducible offline):
BTC/USDT binance 1w on 2026-11-01 05:00 UTC, forming candle included —
engine `media` 79.03 vs TradingView "Konkorde 2.0" 79.03, engine `verde`
86.00 vs the owner's "yellow area" 85.94, BBWP 47.27 vs 47.27. The previous
implementation printed marron 23.0 / azul 91.3 on the same candle and even
disagreed by sign between exchanges on 4h (binance -128 vs bitget +32).
"""

import json
import math
import pathlib

import numpy as np
import pandas as pd
import pytest

from controllers.metrics.indicators_service import IndicatorsService
from controllers.metrics.koncorde import (
    DEFAULT_M,
    DEFAULT_RANGE_LEN,
    koncorde_series,
    pine_ema,
    pine_rma,
    pine_rsi,
)
from controllers.metrics.rules_service import RulesService

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _fixture_ohlcv(timeframe: str) -> pd.DataFrame:
    raw = json.loads((FIXTURES / f"btc_usdt_bitget_{timeframe}_20260713T1600.json").read_text())
    frame = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    frame.index = pd.to_datetime(frame["timestamp"], unit="ms", utc=True)
    return frame


def _random_ohlcv(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2026-01-01", periods=n, freq="4h", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(0, 0.8, size=n))
    open_ = close + rng.normal(0, 0.3, size=n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.6, size=n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.6, size=n)
    volume = rng.uniform(500, 1500, size=n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume}, index=index
    )


def _naive_koncorde(df: pd.DataFrame, m: int = DEFAULT_M, rng_len: int = DEFAULT_RANGE_LEN) -> pd.DataFrame:
    """Literal bar-by-bar re-reading of the Pine, kept independent on purpose.

        tprice  = ohlc4
        pvim    = ema(pvi, m);  oscp = (pvi - pvim) * 100 / (highest(pvim, 90) - lowest(pvim, 90))
        nvim    = ema(nvi, m);  azul = (nvi - nvim) * 100 / (highest(nvim, 90) - lowest(nvim, 90))
        xmf     = mfi(14) on hlc3
        BollOsc = (tprice - OB1) / OB2 * 100   with OB1 = basis, OB2 = upper - lower (25, 2)
        xrsi    = rsi(tprice, 14)
        stoc    = sma(stoch(tprice, low, high, 21), 3)
        marron  = (xrsi + xmf + BollOsc + stoc / 3) / 2
        verde   = marron + oscp
        media   = ema(marron, m)
    """
    o, h, l, c, v = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close", "volume"))
    n = len(c)
    tp = (o + h + l + c) / 4.0
    hlc3 = (h + l + c) / 3.0

    def ema(values, length):
        out = [math.nan] * n
        alpha = 2.0 / (length + 1)
        prev = math.nan
        for i in range(n):
            if math.isnan(values[i]):
                continue
            prev = values[i] if math.isnan(prev) else alpha * values[i] + (1 - alpha) * prev
            out[i] = prev
        return out

    def rma(values, length):
        out = [math.nan] * n
        start = next((i for i in range(n) if not math.isnan(values[i])), None)
        if start is None or start + length > n:
            return out
        prev = sum(values[start:start + length]) / length
        out[start + length - 1] = prev
        for i in range(start + length, n):
            prev = (values[i] + (length - 1) * prev) / length
            out[i] = prev
        return out

    def window_fn(values, length, fn):
        out = [math.nan] * n
        for i in range(length - 1, n):
            chunk = values[i - length + 1: i + 1]
            if any(math.isnan(x) for x in chunk):
                continue
            out[i] = fn(chunk)
        return out

    def div(a, b):
        return math.nan if (math.isnan(a) or math.isnan(b) or b == 0) else a / b

    # PVI / NVI
    pvi, nvi = [1.0] * n, [1.0] * n
    for i in range(1, n):
        r = c[i] / c[i - 1]
        pvi[i] = pvi[i - 1] * (r if v[i] > v[i - 1] else 1.0)
        nvi[i] = nvi[i - 1] * (r if v[i] < v[i - 1] else 1.0)
    pvim, nvim = ema(pvi, m), ema(nvi, m)
    pvi_hi, pvi_lo = window_fn(pvim, rng_len, max), window_fn(pvim, rng_len, min)
    nvi_hi, nvi_lo = window_fn(nvim, rng_len, max), window_fn(nvim, rng_len, min)
    oscp = [div((pvi[i] - pvim[i]) * 100, pvi_hi[i] - pvi_lo[i]) if not math.isnan(pvi_hi[i]) else math.nan for i in range(n)]
    azul = [div((nvi[i] - nvim[i]) * 100, nvi_hi[i] - nvi_lo[i]) if not math.isnan(nvi_hi[i]) else math.nan for i in range(n)]

    # MFI(14) on hlc3
    up = [math.nan] + [v[i] * hlc3[i] if hlc3[i] > hlc3[i - 1] else 0.0 for i in range(1, n)]
    dn = [math.nan] + [v[i] * hlc3[i] if hlc3[i] < hlc3[i - 1] else 0.0 for i in range(1, n)]
    xmf = [math.nan] * n
    for i in range(14, n):
        su, sd = sum(up[i - 13: i + 1]), sum(dn[i - 13: i + 1])
        xmf[i] = 100.0 if sd == 0 else 100 - 100 / (1 + su / sd)

    # Bollinger oscillator (25, 2) on tprice
    bollosc = [math.nan] * n
    for i in range(24, n):
        chunk = tp[i - 24: i + 1]
        basis = chunk.mean()
        dev = 2.0 * chunk.std(ddof=0)
        bollosc[i] = div(tp[i] - basis, 4.0 * chunk.std(ddof=0)) * 100 if dev != 0 else math.nan

    # RSI(14) on tprice (Wilder)
    gains = [math.nan] + [max(tp[i] - tp[i - 1], 0.0) for i in range(1, n)]
    losses = [math.nan] + [max(tp[i - 1] - tp[i], 0.0) for i in range(1, n)]
    ag, al = rma(gains, 14), rma(losses, 14)
    xrsi = [math.nan] * n
    for i in range(n):
        if math.isnan(ag[i]):
            continue
        xrsi[i] = 100.0 if al[i] == 0 else 100 - 100 / (1 + ag[i] / al[i])

    # Stochastic (21, 3) of tprice against low/high extremes
    k = [math.nan] * n
    for i in range(20, n):
        ll, hh = l[i - 20: i + 1].min(), h[i - 20: i + 1].max()
        k[i] = div(100 * (tp[i] - ll), hh - ll)
    stoc = window_fn(k, 3, lambda chunk: sum(chunk) / 3)

    marron = [(xrsi[i] + xmf[i] + bollosc[i] + stoc[i] / 3) / 2 for i in range(n)]
    verde = [marron[i] + oscp[i] for i in range(n)]
    media = ema(marron, m)
    return pd.DataFrame(
        {"marron": marron, "verde": verde, "azul": azul, "media": media}, index=df.index, dtype="float64"
    )


def _assert_lines_equal(fast: pd.DataFrame, naive: pd.DataFrame):
    for line in ("marron", "verde", "azul", "media"):
        pd.testing.assert_series_equal(
            fast[line], naive[line], check_names=False, rtol=0, atol=1e-7, obj=line
        )


# ---------------------------------------------------------------------------
# 1. Fast port == naive Pine re-reading
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3])
def test_parity_fast_vs_naive_synthetic(seed):
    df = _random_ohlcv(400, seed)
    _assert_lines_equal(koncorde_series(df), _naive_koncorde(df))


@pytest.mark.parametrize("timeframe", ["4h", "1d"])
def test_parity_fast_vs_naive_real_candles(timeframe):
    df = _fixture_ohlcv(timeframe)
    _assert_lines_equal(koncorde_series(df), _naive_koncorde(df))


# ---------------------------------------------------------------------------
# 2. Pine semantics, hand-checkable
# ---------------------------------------------------------------------------

def test_pine_ema_seeds_with_first_value_and_rma_with_sma():
    src = pd.Series([math.nan, 2.0, 4.0, 6.0, 8.0, 10.0])
    ema = pine_ema(src, 3)
    assert math.isnan(ema.iloc[0])
    assert ema.iloc[1] == 2.0  # seed = first valid value
    assert ema.iloc[2] == pytest.approx(0.5 * 4.0 + 0.5 * 2.0)
    rma = pine_rma(src, 3)
    assert rma.iloc[:3].isna().all()
    assert rma.iloc[3] == pytest.approx((2.0 + 4.0 + 6.0) / 3)  # seed = SMA(3)
    assert rma.iloc[4] == pytest.approx(8.0 / 3 + (2.0 / 3) * 4.0)


def test_pine_rsi_extremes():
    rising = pd.Series(np.arange(1.0, 40.0))
    assert pine_rsi(rising, 14).iloc[-1] == 100.0
    falling = pd.Series(np.arange(40.0, 1.0, -1.0))
    assert pine_rsi(falling, 14).iloc[-1] == 0.0


def test_line_algebra_verde_is_marron_plus_oscp_and_media_is_ema15():
    df = _random_ohlcv(300, seed=7)
    lines = koncorde_series(df)
    pd.testing.assert_series_equal(lines["verde"], lines["marron"] + lines["oscp"], check_names=False)
    pd.testing.assert_series_equal(lines["media"], pine_ema(lines["marron"], DEFAULT_M), check_names=False)


def test_marron_is_a_0_100_style_average_not_centred_on_zero():
    """A flat zig-zag market scores marron ~ (50 + 50 + 0 + 50/3) / 2 ~ 58,
    like the TradingView plot — the old `-50` re-centring (D6) was wrong."""
    n = 200
    idx = pd.date_range("2025-01-01", periods=n, freq="h")
    osc = np.where(np.arange(n) % 2 == 0, 1.0, -1.0)
    close = 100.0 + osc * 0.5
    open_ = 100.0 - osc * 0.5
    df = pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 0.2,
            "low": np.minimum(open_, close) - 0.2,
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=idx,
    )
    lines = koncorde_series(df)
    marron = float(lines["marron"].iloc[-1])
    assert 45.0 < marron < 70.0
    assert abs(float(lines["media"].iloc[-1]) - marron) < 5.0
    # Constant volume: PVI/NVI never move -> zero 90-bar range -> na (Pine
    # division by zero), never +-inf.
    assert math.isnan(lines["oscp"].iloc[-1])
    assert math.isnan(lines["azul"].iloc[-1])
    assert not np.isinf(lines[["marron", "verde", "azul", "media"]].to_numpy(dtype=float)).any()


def test_azul_is_nvi_and_verde_is_pvi():
    """Only volume-DOWN bars move azul (NVI); only volume-UP bars move oscp
    (verde - marron). Before the port the roles were swapped (azul = PVI)."""
    df = _random_ohlcv(400, seed=11)
    lines = koncorde_series(df)
    volume = df["volume"]
    up_bars = (volume > volume.shift(1)).to_numpy()
    down_bars = (volume < volume.shift(1)).to_numpy()
    pvi, nvi = lines["pvi"].to_numpy(), lines["nvi"].to_numpy()
    # NVI is unchanged on volume-up bars, PVI unchanged on volume-down bars.
    assert np.allclose(nvi[1:][up_bars[1:]], nvi[:-1][up_bars[1:]])
    assert np.allclose(pvi[1:][down_bars[1:]], pvi[:-1][down_bars[1:]])
    assert not np.allclose(nvi[1:][down_bars[1:]], nvi[:-1][down_bars[1:]])
    assert not np.allclose(pvi[1:][up_bars[1:]], pvi[:-1][up_bars[1:]])


def test_warmup_nan_matches_pine_windows():
    df = _random_ohlcv(200, seed=5)
    lines = koncorde_series(df)
    first = {col: lines.index.get_loc(lines[col].first_valid_index()) for col in lines.columns}
    assert first["xrsi"] == 14      # rma(14) seeded on bar 14
    assert first["xmf"] == 14       # 14-bar sums of diffs (first diff on bar 1)
    assert first["bollosc"] == 24   # sma/stdev(25)
    assert first["stoc"] == 22      # lowest/highest(21) at bar 20, sma(3) at 22
    assert first["marron"] == 24
    assert first["media"] == 24
    assert first["oscp"] == first["azul"] == DEFAULT_RANGE_LEN - 1  # highest/lowest(90)
    assert first["verde"] == DEFAULT_RANGE_LEN - 1


# ---------------------------------------------------------------------------
# 3. Numeric goldens on the immutable bitget fixtures (closed candles only)
# ---------------------------------------------------------------------------

GOLDEN_LAST_CANDLE = {
    # tf: (marron, verde, azul, media)
    "4h": (9.717420, -7.623306, 10.323869, 60.051591),   # 2026-07-13 12:00 UTC
    "1d": (88.362136, 99.897836, -1.626068, 58.324544),  # 2026-07-12 00:00 UTC
    "1w": (27.122805, 11.672819, 19.715371, 30.237982),  # 2026-07-06 00:00 UTC
}


@pytest.mark.parametrize("timeframe", sorted(GOLDEN_LAST_CANDLE))
def test_golden_last_candle_on_fixtures(timeframe):
    lines = koncorde_series(_fixture_ohlcv(timeframe)).iloc[-1]
    marron, verde, azul, media = GOLDEN_LAST_CANDLE[timeframe]
    assert lines["marron"] == pytest.approx(marron, abs=1e-5)
    assert lines["verde"] == pytest.approx(verde, abs=1e-5)
    assert lines["azul"] == pytest.approx(azul, abs=1e-5)
    assert lines["media"] == pytest.approx(media, abs=1e-5)


def test_golden_components_4h_fixture():
    """The 4h golden decomposed: the bearish 2026-07-13 impulse."""
    last = koncorde_series(_fixture_ohlcv("4h")).iloc[-1]
    assert last["xrsi"] == pytest.approx(34.392513, abs=1e-5)
    assert last["xmf"] == pytest.approx(32.877348, abs=1e-5)
    assert last["bollosc"] == pytest.approx(-54.481659, abs=1e-5)
    assert last["stoc"] == pytest.approx(19.939915, abs=1e-5)
    assert last["oscp"] == pytest.approx(-17.340727, abs=1e-5)
    assert last["marron"] == pytest.approx((34.392513 + 32.877348 - 54.481659 + 19.939915 / 3) / 2, abs=1e-5)


# ---------------------------------------------------------------------------
# 4. Consumer contract — IndicatorsService keys and RulesService voting
# ---------------------------------------------------------------------------

def test_indicators_service_exposes_the_four_lines_and_alias():
    df = _fixture_ohlcv("4h")
    service = IndicatorsService(df)
    result = service.calculate_konkorde()
    marron, verde, azul, media = GOLDEN_LAST_CANDLE["4h"]
    assert result["konkorde_marron"] == pytest.approx(marron, abs=1e-5)
    assert result["konkorde_verde"] == pytest.approx(verde, abs=1e-5)
    assert result["konkorde_azul"] == pytest.approx(azul, abs=1e-5)
    assert result["konkorde_media"] == pytest.approx(media, abs=1e-5)
    assert result["konkorde_value"] == result["konkorde_marron"]  # deprecated alias
    assert result["konkorde_signal"] == "bearish_weak"  # marron < media, azul > 0
    for column in ("konkorde_marron", "konkorde_verde", "konkorde_azul", "konkorde_media"):
        assert column in service.df.columns


def test_rules_vote_on_marron_vs_media_never_on_marron_sign():
    """On the real indicator `marron > 0` is almost always true (0-100 inputs);
    the Blai5 signal is marron against its media. A positive marron BELOW
    its media must vote sell, not buy."""
    service = RulesService(symbol="BTC/USDT")
    below = service.evaluate({"konkorde_value": 40.0, "konkorde_media": 60.0})
    assert "konkorde_sell" in below["support_exit"]
    assert "konkorde_buy" not in below["support_entry"]

    above = service.evaluate({"konkorde_value": 70.0, "konkorde_media": 60.0})
    assert "konkorde_buy" in above["support_entry"]
    assert above["entry_score"] == pytest.approx(3.0, abs=1e-9)

    flat = service.evaluate({"konkorde_value": 60.0, "konkorde_media": 60.0})
    assert "konkorde_buy" not in flat["support_entry"]
    assert "konkorde_sell" not in flat["support_exit"]


def test_rules_legacy_payload_without_media_keeps_sign_reading():
    """Callers that only send `konkorde_value` (no media) keep the old contract."""
    rules = RulesService(symbol="BTC/USDT").evaluate({"konkorde_value": 42.0})
    assert rules["support_entry"] == ["konkorde_buy"]
    assert rules["entry_score"] == pytest.approx(3.0, abs=1e-9)


def test_konkorde_family_weight_is_three():
    assert RulesService.DEFAULT_WEIGHTS["konkorde"] == 3.0
