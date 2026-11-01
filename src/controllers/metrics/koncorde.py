"""Koncorde (Blai5) — bar-exact port of the public TradingView Pine script.

Reference: Blai5 "Koncorde" v.09 (ProRealTime pseudocode, 2008) as ported to
Pine by the community (the open-source "Koncorde"/"MACD_Koncorde" scripts;
the closed-source "Konkorde 2.0" the owner reads on TradingView shares the
same lines — verified 2026-11-01 on BTC/USDT binance 1w: `media` and the
BBWP matched the owner's chart to 2 decimals, the owner's "yellow" area is
`verde`). Lines, in Pine:

    tprice  = ohlc4
    m       = 15                                   // EMA length of every average
    pvim    = ema(pvi, m);  oscp = (pvi - pvim) * 100 / (highest(pvim, 90) - lowest(pvim, 90))
    nvim    = ema(nvi, m);  azul = (nvi - nvim) * 100 / (highest(nvim, 90) - lowest(nvim, 90))
    xmf     = mfi(14)                              // standard MFI on hlc3 + volume
    basis   = sma(tprice, 25); dev = 2 * stdev(tprice, 25)
    OB1     = (upper + lower) / 2;  OB2 = upper - lower
    BollOsc = (tprice - OB1) / OB2 * 100           // == (tprice - basis) / (4 * stdev) * 100
    xrsi    = rsi(tprice, 14)
    stoc    = sma(100 * (tprice - lowest(low, 21)) / (highest(high, 21) - lowest(low, 21)), 3)
    marron  = (xrsi + xmf + BollOsc + stoc / 3) / 2   // brown mountain: trend
    verde   = marron + oscp                           // green: weak hands (PVI)
    media   = ema(marron, m)                          // red line: signal
    azul    = NVI oscillator                          // blue: strong hands

Reading (Blai5): `azul` > 0 strong hands accumulate, `verde` > 0 weak hands
buy; the canonical signal is `marron` crossing `media`. NOTE `marron` is NOT
centred on zero — RSI/MFI/stoch are 0-100 series — so in a flat market it
sits around +55 and only goes negative in strong sell-offs, exactly like the
TradingView plot.

Pine semantics replicated (float64, warmup NaN kept):

* `ta.ema` seeds with the first non-na source value, `ta.rma` (inside
  `ta.rsi`) seeds with the SMA of the first `length` values.
* `ta.pvi` / `ta.nvi` are multiplicative indices; the seed does not matter
  because both oscillators are invariant to affine rescaling of the index.
* `ta.highest/lowest`, `ta.sma`, `ta.stdev` need a full window (na before).
  `ta.stdev` is population (ddof=0).
* Division by zero is `na` in Pine: a zero 90-bar range (e.g. constant
  volume -> flat PVI) yields NaN oscillators, never +-inf.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_M = 15
DEFAULT_RANGE_LEN = 90
DEFAULT_MFI_LEN = 14
DEFAULT_RSI_LEN = 14
DEFAULT_BB_LEN = 25
DEFAULT_BB_MULT = 2.0
DEFAULT_STOCH_LEN = 21
DEFAULT_STOCH_SMOOTH = 3


def pine_ema(src: pd.Series, length: int) -> pd.Series:
    """Pine `ta.ema`: seeded with the first non-na value, then recursive."""
    values = src.to_numpy(dtype="float64")
    out = np.full(len(values), np.nan)
    alpha = 2.0 / (length + 1)
    prev = np.nan
    for i, x in enumerate(values):
        if np.isnan(x):
            continue
        prev = x if np.isnan(prev) else alpha * x + (1.0 - alpha) * prev
        out[i] = prev
    return pd.Series(out, index=src.index)


def pine_rma(src: pd.Series, length: int) -> pd.Series:
    """Pine `ta.rma`: seeded with the SMA of the first `length` valid values."""
    values = src.to_numpy(dtype="float64")
    out = np.full(len(values), np.nan)
    alpha = 1.0 / length
    valid = np.flatnonzero(~np.isnan(values))
    if len(valid) < length:
        return pd.Series(out, index=src.index)
    start = int(valid[0])
    seed_end = start + length  # the first `length` values must be contiguous
    if np.isnan(values[start:seed_end]).any():
        return pd.Series(out, index=src.index)
    prev = float(np.mean(values[start:seed_end]))
    out[seed_end - 1] = prev
    for i in range(seed_end, len(values)):
        prev = alpha * values[i] + (1.0 - alpha) * prev
        out[i] = prev
    return pd.Series(out, index=src.index)


def pine_rsi(src: pd.Series, length: int) -> pd.Series:
    """Pine `ta.rsi` (Wilder: RMA of gains / RMA of losses)."""
    diff = src.diff()
    up = pine_rma(diff.clip(lower=0.0), length)
    down = pine_rma((-diff).clip(lower=0.0), length)
    with np.errstate(divide="ignore", invalid="ignore"):
        rsi = 100.0 - 100.0 / (1.0 + up / down)
    # down == 0 -> rs = inf -> 100 (Pine special-cases it the same way).
    rsi = rsi.where(~((down == 0) & (up > 0)), 100.0)
    rsi = rsi.where(~((down == 0) & (up == 0)), 50.0)
    return rsi


def pine_mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, length: int) -> pd.Series:
    """Pine `ta.mfi` as written in the Koncorde port (hlc3, volume-weighted)."""
    hlc3 = (high + low + close) / 3.0
    change = hlc3.diff()
    # Bar 0 has no change: keep it na so the first `length` sums are na
    # (Pine's `na <= 0` quirk only touches the warmup, which marron never
    # reaches — its Bollinger leg starts later).
    flow_up = (volume * hlc3.where(change > 0, 0.0)).where(change.notna())
    flow_down = (volume * hlc3.where(change < 0, 0.0)).where(change.notna())
    upper = flow_up.rolling(length).sum()
    lower = flow_down.rolling(length).sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        mfi = 100.0 - 100.0 / (1.0 + upper / lower)
    mfi = mfi.where(~((lower == 0) & (upper > 0)), 100.0)
    mfi = mfi.where(~((lower == 0) & (upper == 0)), np.nan)
    # Keep the warmup NaN of the rolling sums (where() above would not add any).
    return mfi.where(upper.notna() & lower.notna())


def _na_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Series division with Pine semantics: x / 0 -> na."""
    with np.errstate(divide="ignore", invalid="ignore"):
        out = numerator / denominator.replace(0.0, np.nan)
    return out.replace([np.inf, -np.inf], np.nan)


def volume_indices(close: pd.Series, volume: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Pine `ta.pvi` / `ta.nvi` (multiplicative, seed 1.0 on the first bar)."""
    ratio = close / close.shift(1)
    ratio = ratio.replace([np.inf, -np.inf], np.nan).fillna(1.0)
    prev_volume = volume.shift(1)
    pvi_step = pd.Series(np.where(volume > prev_volume, ratio, 1.0), index=close.index)
    nvi_step = pd.Series(np.where(volume < prev_volume, ratio, 1.0), index=close.index)
    return pvi_step.cumprod(), nvi_step.cumprod()


def koncorde_series(
    df: pd.DataFrame,
    *,
    m: int = DEFAULT_M,
    range_len: int = DEFAULT_RANGE_LEN,
    mfi_len: int = DEFAULT_MFI_LEN,
    rsi_len: int = DEFAULT_RSI_LEN,
    bb_len: int = DEFAULT_BB_LEN,
    bb_mult: float = DEFAULT_BB_MULT,
    stoch_len: int = DEFAULT_STOCH_LEN,
    stoch_smooth: int = DEFAULT_STOCH_SMOOTH,
) -> pd.DataFrame:
    """Compute the Koncorde lines over an OHLCV frame.

    Pure function: `df` is never mutated. Returns a DataFrame aligned to
    `df.index` with the four plotted lines (`marron`, `verde`, `azul`,
    `media`) plus every component (`xrsi`, `xmf`, `bollosc`, `stoc`,
    `oscp`, `pvi`, `nvi`) so goldens can pin each piece.
    """
    if m < 1 or range_len < 1:
        raise ValueError("m and range_len must be >= 1")
    open_ = df["open"].astype("float64")
    high = df["high"].astype("float64")
    low = df["low"].astype("float64")
    close = df["close"].astype("float64")
    volume = df["volume"].astype("float64")
    tprice = (open_ + high + low + close) / 4.0

    # Volume indices and their oscillators (weak hands / strong hands).
    pvi, nvi = volume_indices(close, volume)
    pvim = pine_ema(pvi, m)
    nvim = pine_ema(nvi, m)
    oscp = _na_div((pvi - pvim) * 100.0, pvim.rolling(range_len).max() - pvim.rolling(range_len).min())
    azul = _na_div((nvi - nvim) * 100.0, nvim.rolling(range_len).max() - nvim.rolling(range_len).min())

    # Trend components.
    xmf = pine_mfi(high, low, close, volume, mfi_len)
    basis = tprice.rolling(bb_len).mean()
    dev = bb_mult * tprice.rolling(bb_len).std(ddof=0)
    upper, lower = basis + dev, basis - dev
    ob1 = (upper + lower) / 2.0
    ob2 = upper - lower
    bollosc = _na_div((tprice - ob1), ob2) * 100.0
    xrsi = pine_rsi(tprice, rsi_len)
    ll = low.rolling(stoch_len).min()
    hh = high.rolling(stoch_len).max()
    stoc = _na_div(100.0 * (tprice - ll), hh - ll).rolling(stoch_smooth).mean()

    marron = (xrsi + xmf + bollosc + stoc / 3.0) / 2.0
    verde = marron + oscp
    media = pine_ema(marron, m)

    return pd.DataFrame(
        {
            "marron": marron,
            "verde": verde,
            "azul": azul,
            "media": media,
            "xrsi": xrsi,
            "xmf": xmf,
            "bollosc": bollosc,
            "stoc": stoc,
            "oscp": oscp,
            "pvi": pvi,
            "nvi": nvi,
        },
        index=df.index,
    )
