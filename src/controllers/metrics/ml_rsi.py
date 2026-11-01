"""ML RSI [BackQuant] — port of the public Pine script (docs/impulsos-v2.md §R2.e2).

Owner decision 4 (2026-11-01): ML RSI is a FOLLOWER / regime filter of the
impulse engine. Source read (read-only, supply-chain rule) from TradingView
`PUB;5377b8882cc843ce943725172b99b6b6` ("Machine Learning RSI [BackQuant]",
MPL-2.0, 2024-11-12). What the Pine actually computes:

* ``rsi = ta.rsi(src, rsiLength)`` (Wilder RMA), smoothed with the chosen MA;
  the owner uses ALMA: ``ta.alma(rsi, smoothP, 0, sigma)`` — **offset is
  hard-coded to 0** in the script (the owner's note says 0.85, TradingView's
  generic default; the parity test against the owner's reading decides which
  one this port runs with — see ``MlRsiParams.alma_offset``).
* ``rsi_values``: the smoothed RSI of every bar with
  ``last_bar_index - bar_index <= maxData`` (the LAST 3000 bars of the chart).
* Every bar: 3 centroids initialised at the 25 / 50 / 75 percentiles (linear
  interpolation) of the values collected so far, then plain 1-D k-means until
  the centroids stop changing (or ``maxIter``). ``long_S`` (upper threshold) =
  centroid 3, ``short_S`` (lower) = centroid 1. Colour: green above upper,
  red below lower, gray between.
* ``minThresh / maxThresh / step`` fill a ``factors`` array that is NEVER read
  afterwards, and ``perfAlpha`` ("Performance Memory") is declared and never
  used: both are dead inputs in this script. They are kept in ``MlRsiParams``
  so the rule doc can carry the owner's TV settings verbatim.

**What TradingView actually plots (verified 2026-11-01).** The Pine builds
``distances`` and ``new_centroids`` with ``array.new_float(3)`` (three ``na``
slots) and then ``array.push``es onto them, so the arrays grow to 6 / 9
elements: every value lands in "cluster 3", the k-means never updates slots
0-2 with real means, and ``array.get(centroids, 0 | 2)`` reads the slots that
``array.set`` refreshes each bar with the 25th / 75th percentiles. The
plotted thresholds are therefore the **25th / 75th percentiles of the
collected RSI values**, not k-means centroids. Checked against the owner's
reading (BINANCE BTC/USDT 1d, 01-nov-2026: upper 59.74, lower 44.30): the
percentile port on the last 3001 bitget daily values gives 59.76 / 44.09; the
true k-means gives 68.3 / 39.2 (`scripts/diag_ml_rsi_*.py`). Hence
``threshold_method="percentile"`` is the default (= what the owner sees and
validated); ``"kmeans"`` is the algorithm the script describes, kept for the
record.

Lookahead / repaint. On a historical bar the Pine clustering only sees values
up to that bar (causal), BUT the set of bars it collects is anchored to the
chart's LAST bar (``last_bar_index``): the early part of the plot was fitted
on a handful of points, and every new bar shifts the window. This module
offers both:

* ``mode="causal"`` (engine default): at bar j the window is the trailing
  ``max_points + 1`` bars ending at j. Nothing after j is used, and the value
  at j never changes when more bars arrive (tested).
* ``mode="tv"``: the Pine behaviour anchored to the last bar of the frame,
  used only to MEASURE the repaint against the causal series.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

REGIMES = ("green", "red", "gray")
MODES = ("causal", "tv")
THRESHOLD_METHODS = ("percentile", "kmeans")


@dataclass(frozen=True)
class MlRsiParams:
    rsi_period: int = 19
    alma_window: int = 4
    alma_sigma: float = 1.0
    alma_offset: float = 0.0  # Pine: ta.alma(rsi, smoothP, 0, sig)
    threshold_method: str = "percentile"  # what TV plots (see module doc); "kmeans" = the described algorithm
    lower_percentile: float = 25.0
    upper_percentile: float = 75.0
    range_min: int = 10  # dead input in the Pine (kept for the rule doc)
    range_max: int = 90
    range_step: int = 5
    memory: float = 10.0  # perfAlpha: dead input in the Pine
    max_points: int = 3000
    max_iter: int = 1000
    min_points: int = 4  # Pine: array.size(rsi_values) > 3

    def __post_init__(self) -> None:
        if self.rsi_period < 2 or self.alma_window < 1 or self.max_points < self.min_points:
            raise ValueError("invalid MlRsiParams")
        if self.alma_sigma <= 0:
            raise ValueError("alma_sigma must be > 0")
        if self.threshold_method not in THRESHOLD_METHODS:
            raise ValueError(f"threshold_method must be one of {THRESHOLD_METHODS}")


def alma_weights(window: int, offset: float, sigma: float) -> np.ndarray:
    """Pine `ta.alma`: weight i applies to the sample `window-1-i` bars back (i=0 oldest)."""
    m = offset * (window - 1)
    s = window / sigma
    i = np.arange(window, dtype=float)
    return np.exp(-((i - m) ** 2) / (2.0 * s * s))


def alma(series: pd.Series, window: int, offset: float, sigma: float) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").astype(float).to_numpy()
    w = alma_weights(window, offset, sigma)
    out = np.full(len(values), np.nan)
    if len(values) >= window:
        # sum_i values[j-(window-1)+i] * w[i]  (oldest sample gets w[0])
        out[window - 1:] = np.convolve(values, w[::-1], mode="valid") / w.sum()
    return pd.Series(out, index=series.index)


def rsi(series: pd.Series, period: int) -> pd.Series:
    """Wilder RSI (TradingView `ta.rsi`): RMA of gains / RMA of losses."""
    close = pd.to_numeric(series, errors="coerce").astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    # TV seeds the RMA with an SMA of the first `period` changes, then EMA(alpha=1/period).
    avg_gain = _rma(gain.to_numpy(), period)
    avg_loss = _rma(loss.to_numpy(), period)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
        out = np.where(avg_loss == 0, np.where(avg_gain == 0, np.nan, 100.0), 100.0 - 100.0 / (1.0 + rs))
    return pd.Series(out, index=series.index)


def _rma(values: np.ndarray, period: int) -> np.ndarray:
    out = np.full(len(values), np.nan)
    # first finite change is at index 1 (diff of index 0 is NaN)
    start = next((k for k in range(len(values)) if math.isfinite(values[k])), None)
    if start is None or len(values) - start < period:
        return out
    first = start + period - 1
    out[first] = float(np.mean(values[start: first + 1]))
    alpha = 1.0 / period
    for k in range(first + 1, len(values)):
        v = values[k]
        out[k] = out[k - 1] if not math.isfinite(v) else out[k - 1] + alpha * (v - out[k - 1])
    return out


def kmeans3(values: np.ndarray, max_iter: int = 1000) -> np.ndarray:
    """Pine clustering: percentile init (25/50/75), nearest-centroid assignment
    (ties -> lowest index, like `array.indexof(min)`), means, stop on equality.

    Returns the 3 centroids sorted as initialised (low, mid, high). An empty
    cluster keeps its previous centroid (Pine would push `na`; never seen with
    percentile initialisation on > 3 points)."""
    values = values[np.isfinite(values)]
    if len(values) < 4:
        return np.array([np.nan, np.nan, np.nan])
    centroids = np.percentile(values, [25.0, 50.0, 75.0])  # linear interpolation
    for _ in range(max_iter + 1):
        idx = np.abs(values[:, None] - centroids[None, :]).argmin(axis=1)
        new = centroids.copy()
        for k in range(3):
            members = values[idx == k]
            if len(members):
                new[k] = members.mean()
        if np.array_equal(new, centroids):
            break
        centroids = new
    return centroids


def thresholds(window: np.ndarray, p: MlRsiParams) -> Tuple[float, float]:
    """(lower, upper) of one data window per `p.threshold_method`; NaN if too few points."""
    values = window[np.isfinite(window)]
    if len(values) < p.min_points:
        return float("nan"), float("nan")
    if p.threshold_method == "kmeans":
        c = kmeans3(values, p.max_iter)
        return float(c[0]), float(c[2])
    lo, hi = np.percentile(values, [p.lower_percentile, p.upper_percentile])  # linear interpolation, as Pine
    return float(lo), float(hi)


def regime_of(value: float, upper: float, lower: float) -> Optional[str]:
    if not (math.isfinite(value) and math.isfinite(upper) and math.isfinite(lower)):
        return None
    if value > upper:
        return "green"
    if value < lower:
        return "red"
    return "gray"


def ml_rsi_frame(close: pd.Series, params: MlRsiParams = MlRsiParams(), *, mode: str = "causal") -> pd.DataFrame:
    """Columns `ml_rsi`, `ml_rsi_upper`, `ml_rsi_lower`, `ml_rsi_regime` aligned to `close`."""
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    p = params
    smoothed = alma(rsi(close, p.rsi_period), p.alma_window, p.alma_offset, p.alma_sigma)
    values = smoothed.to_numpy(dtype=float)
    n = len(values)
    upper = np.full(n, np.nan)
    lower = np.full(n, np.nan)
    last = n - 1
    for j in range(n):
        if mode == "causal":
            lo = max(0, j - p.max_points)
        else:  # tv: bars with last_bar_index - bar_index <= max_points
            lo = max(0, last - p.max_points)
            if j < lo:
                continue
        lower[j], upper[j] = thresholds(values[lo: j + 1], p)
    regime = [regime_of(v, u, lo_) for v, u, lo_ in zip(values, upper, lower)]
    return pd.DataFrame(
        {"ml_rsi": values, "ml_rsi_upper": upper, "ml_rsi_lower": lower, "ml_rsi_regime": regime},
        index=close.index,
    )


def regime_series(frame: pd.DataFrame) -> pd.Series:
    """`ml_rsi_regime` as +1 (green) / -1 (red) / 0 (gray) / NaN (unknown) for engines."""
    mapping = {"green": 1.0, "red": -1.0, "gray": 0.0}
    return frame["ml_rsi_regime"].map(lambda r: mapping.get(r, np.nan)).astype(float)


def repaint_report(close: pd.Series, params: MlRsiParams = MlRsiParams(), *, tail: int = 1000) -> Dict[str, Any]:
    """Causal vs TV-anchored thresholds over the last `tail` bars with both defined.

    The TV plot of a historical bar was fitted on the bars between the chart's
    (last_bar - max_points) and that bar; the causal series uses the trailing
    window. Reports mean / max absolute threshold differences and the share of
    bars whose regime label differs."""
    causal = ml_rsi_frame(close, params, mode="causal")
    tv = ml_rsi_frame(close, params, mode="tv")
    both = causal["ml_rsi_upper"].notna() & tv["ml_rsi_upper"].notna()
    c, t = causal[both].tail(tail), tv[both].tail(tail)
    if c.empty:
        return {"bars": 0}
    du = (c["ml_rsi_upper"] - t["ml_rsi_upper"]).abs()
    dl = (c["ml_rsi_lower"] - t["ml_rsi_lower"]).abs()
    regime_diff = (c["ml_rsi_regime"].fillna("na") != t["ml_rsi_regime"].fillna("na")).mean()
    return {
        "bars": int(len(c)),
        "first": c.index[0].isoformat() if hasattr(c.index[0], "isoformat") else str(c.index[0]),
        "last": c.index[-1].isoformat() if hasattr(c.index[-1], "isoformat") else str(c.index[-1]),
        "upper_abs_diff_mean": round(float(du.mean()), 3),
        "upper_abs_diff_max": round(float(du.max()), 3),
        "lower_abs_diff_mean": round(float(dl.mean()), 3),
        "lower_abs_diff_max": round(float(dl.max()), 3),
        "regime_disagreement_pct": round(float(regime_diff) * 100.0, 2),
        "last_bar_identical": bool(
            math.isclose(float(c["ml_rsi_upper"].iloc[-1]), float(t["ml_rsi_upper"].iloc[-1]), abs_tol=1e-9)
            and math.isclose(float(c["ml_rsi_lower"].iloc[-1]), float(t["ml_rsi_lower"].iloc[-1]), abs_tol=1e-9)
        ),
        "params": asdict(params),
    }


__all__: Sequence[str] = (
    "MlRsiParams", "REGIMES", "MODES", "THRESHOLD_METHODS", "alma", "alma_weights", "rsi", "kmeans3",
    "thresholds", "regime_of", "ml_rsi_frame", "regime_series", "repaint_report",
)
