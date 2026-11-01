"""Impulsos-v2 round 8: PRE-DEFINED regime identifiers for the long/short question.

Owner context (2026-11-01): he trades impulses in BOTH directions; round 7 showed longs
positive and shorts negative on 2024-11 -> 2026-10, which may be the regime of the
period rather than a property of the sides. Two identifiers are fixed here BEFORE any
regime split is looked at (docs/PREREG_IMPULSOS_v2_r8_shadow.md §3):

* R1 `own`: the asset's own daily trend — last CLOSED 1d candle at the trigger
  candle's close, `close > EMA200(1d)` -> ``up`` else ``down``.
* R2 `btc`: the same rule on BTC/USDT 1d, applied to every asset (BTC as the regime
  leader of the alts). Informational in round 8; R1 drives the long/short book.

EMA200 = ``pandas.Series.ewm(span=200, adjust=True).mean()`` (no seed bias on a
finite history; declared, not fitted). Nothing here reads anything after the
trigger candle's close: the label of a signal never changes afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

import numpy as np
import pandas as pd

from .impulse_backtest import TIMEFRAME_MS

EMA_SPAN = 200
REGIME_TF = "1d"
UP, DOWN = "up", "down"
IDENTIFIERS = ("own", "btc")
PRIMARY_IDENTIFIER = "own"


def ema(closes: pd.Series, span: int = EMA_SPAN) -> pd.Series:
    return closes.astype(float).ewm(span=span, adjust=True).mean()


@dataclass
class RegimeSeries:
    """Per CLOSED 1d candle: its close time (ms) and the regime it declares."""

    close_ms: np.ndarray
    regime: np.ndarray  # +1 up / -1 down
    ema: np.ndarray
    close: np.ndarray

    @property
    def n(self) -> int:
        return int(len(self.close_ms))

    def at(self, decision_ms: int) -> Optional[Dict[str, Any]]:
        """Regime of the last 1d candle CLOSED at or before `decision_ms` (None = no candle yet)."""
        j = int(np.searchsorted(self.close_ms, int(decision_ms), side="right")) - 1
        if j < 0:
            return None
        return {"regime": UP if self.regime[j] > 0 else DOWN, "candle_close": int(self.close_ms[j]),
                "close": float(self.close[j]), "ema200": float(self.ema[j])}

    def share_up(self, start_ms: Optional[int] = None, end_ms: Optional[int] = None) -> Optional[float]:
        m = np.ones(self.n, dtype=bool)
        if start_ms is not None:
            m &= self.close_ms >= int(start_ms)
        if end_ms is not None:
            m &= self.close_ms <= int(end_ms)
        return float((self.regime[m] > 0).mean()) if m.any() else None


def regime_series(df_1d: pd.DataFrame, timeframe: str = REGIME_TF) -> RegimeSeries:
    """`df_1d` = closed candles with a `timestamp` (open ms) and `close` column, ascending."""
    if "timestamp" in df_1d.columns:
        open_ms = df_1d["timestamp"].to_numpy(dtype="int64")
    else:
        open_ms = (df_1d.index.view("int64") // 1_000_000).astype("int64")
    closes = pd.Series(df_1d["close"].to_numpy(dtype=float))
    e = ema(closes).to_numpy(dtype=float)
    c = closes.to_numpy(dtype=float)
    reg = np.where(c > e, 1, -1).astype(int)
    return RegimeSeries(close_ms=open_ms + TIMEFRAME_MS[timeframe], regime=reg, ema=e, close=c)


def decision_ms(entry_open_ms: int, trigger_tf: str) -> int:
    """The machine decides at the CLOSE of the trigger candle that opened at `entry_open_ms`."""
    return int(entry_open_ms) + TIMEFRAME_MS[trigger_tf]


def label_signal(entry_open_ms: int, trigger_tf: str, own: Optional[RegimeSeries],
                 btc: Optional[RegimeSeries]) -> Dict[str, Any]:
    """Both identifiers at the trigger candle's close; `None` when a series is missing/too short."""
    at = decision_ms(entry_open_ms, trigger_tf)
    out: Dict[str, Any] = {"decision_ms": at}
    for name, series in (("own", own), ("btc", btc)):
        hit = series.at(at) if series is not None else None
        out[f"regime_{name}"] = hit["regime"] if hit else None
        out[f"regime_{name}_detail"] = hit
    return out


def side_matches(side: str, regime: Optional[str]) -> Optional[bool]:
    """The long/short book: long only in `up`, short only in `down`. None = unlabelled signal."""
    if regime is None:
        return None
    return (side == "long" and regime == UP) or (side == "short" and regime == DOWN)


def book_of(side: str, labels: Mapping[str, Any], identifier: str = PRIMARY_IDENTIFIER) -> Dict[str, bool]:
    """Membership of one signal in the three round-8 books (+ the informational R2 book)."""
    own_ok = side_matches(side, labels.get("regime_own"))
    btc_ok = side_matches(side, labels.get("regime_btc"))
    return {
        "long_only": side == "long",
        "short_only": side == "short",
        "regime_own": bool(own_ok),
        "regime_btc": bool(btc_ok),
        "regime": bool(own_ok if identifier == "own" else btc_ok),
    }
