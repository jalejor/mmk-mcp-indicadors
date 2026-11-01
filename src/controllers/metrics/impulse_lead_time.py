"""Lead-time measurement for the impulsos-v2 round 2 leader -> follower model.

Owner decision 2 (docs/impulsos-v2.md, 2026-11-01): Konkorde and BBWP LEAD,
AO / ADX / MACD / RSI CONFIRM later. This module measures, offline, how many
closed candles each indicator event fires before the start of a price move,
and the lag between a leader and the followers that precede the same move.
The confirmation window of the engine (W_follower) is a fit on IS only.

Everything here reads indicator COLUMNS (as `IndicatorsService.calculate_all`
leaves them): close, atr14, bbwp (TV), konkorde_verde, konkorde_media, adx14,
plus_di, minus_di, ao, macd, macd_signal, rsi14. Events at bar j only use
rows <= j; MOVEMENT labels look ahead by design (they are the target, never an
engine input).

Definitions (defaults; the trading spec may override H/K/L via the CLI):

* move start m (long): max(close[m+1..m+H]) - close[m] >= K * atr14[m], with
  no other accepted long start in the H bars before (greedy dedupe); mirror for
  short. Needs a full horizon (m + H < n).
* lead of a directional event at j: m - j for the nearest same-side move start
  with min_lead <= m - j <= L (ties prefer m >= j); none -> miss. Side-less
  events (bbwp_ignition, bbwp_red_turn) use the nearest start of either side.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

LEADER = "leader"
FOLLOWER = "follower"


@dataclass(frozen=True)
class LeadTimeParams:
    horizon: int = 10  # H
    k_atr: float = 2.0  # K
    max_lead: int = 12  # L
    min_lead: int = -2
    # BBWP leaders
    compression_max: float = 30.0
    compression_lookback: int = 10  # bars j-9..j
    ignition_level: float = 50.0
    red_zone: float = 90.0
    red_drop: float = 8.0
    # RSI followers
    rsi_mid: float = 50.0
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    # E1 adx_turn_up (same defaults as ImpulseParams)
    adx_turn_window: int = 3
    adx_base_window: int = 5
    adx_turn_min_slope: float = 1.0
    adx_turn_min_delta_slope: float = 1.5
    adx_turn_floor: float = 10.0


@dataclass(frozen=True)
class EventSpec:
    name: str
    role: str  # leader | follower
    side: int  # 1 long, -1 short, 0 side-less


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name not in df.columns:
        return pd.Series(np.nan, index=pd.RangeIndex(len(df)), dtype=float)
    return pd.to_numeric(df[name], errors="coerce").astype(float).reset_index(drop=True)


def _cross_up(a: pd.Series, b: Any) -> pd.Series:
    """a[j-1] <= b[j-1] and a[j] > b[j] (b scalar or series)."""
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a.shift(1) <= b_prev) & (a > b)


def _cross_down(a: pd.Series, b: Any) -> pd.Series:
    b_prev = b.shift(1) if isinstance(b, pd.Series) else b
    return (a.shift(1) >= b_prev) & (a < b)


def _onset(flag: pd.Series) -> pd.Series:
    """First bar of a run of True (state -> event)."""
    flag = flag.fillna(False).astype(bool)
    return flag & ~flag.shift(1, fill_value=False)


def adx_turn_up(adx: pd.Series, p: LeadTimeParams) -> pd.Series:
    """E1 `adx_turn_up` state, vectorised (same formula as impulse_service._derive)."""
    tw, bw = p.adx_turn_window, p.adx_base_window
    slope_recent = (adx - adx.shift(tw)) / tw
    slope_prior = (adx.shift(tw) - adx.shift(tw + bw)) / bw
    return ((slope_recent >= p.adx_turn_min_slope)
            & ((slope_recent - slope_prior) >= p.adx_turn_min_delta_slope)
            & (adx >= p.adx_turn_floor))


EVENT_SPECS: Sequence[EventSpec] = (
    EventSpec("konkorde_zero_cross_up", LEADER, 1),
    EventSpec("konkorde_zero_cross_down", LEADER, -1),
    EventSpec("konkorde_turn_up", LEADER, 1),
    EventSpec("konkorde_turn_down", LEADER, -1),
    EventSpec("bbwp_ignition", LEADER, 0),
    EventSpec("bbwp_red_turn", LEADER, 0),
    EventSpec("ao_zero_cross_up", FOLLOWER, 1),
    EventSpec("ao_zero_cross_down", FOLLOWER, -1),
    EventSpec("ao_turn_up", FOLLOWER, 1),
    EventSpec("ao_turn_down", FOLLOWER, -1),
    EventSpec("adx_turn_up_long", FOLLOWER, 1),
    EventSpec("adx_turn_up_short", FOLLOWER, -1),
    EventSpec("macd_cross_up", FOLLOWER, 1),
    EventSpec("macd_cross_down", FOLLOWER, -1),
    EventSpec("rsi_cross_50_up", FOLLOWER, 1),
    EventSpec("rsi_cross_50_down", FOLLOWER, -1),
    EventSpec("rsi_exit_oversold", FOLLOWER, 1),
    EventSpec("rsi_exit_overbought", FOLLOWER, -1),
)
SPEC_BY_NAME = {s.name: s for s in EVENT_SPECS}


def detect_events(df: pd.DataFrame, p: LeadTimeParams = LeadTimeParams()) -> Dict[str, np.ndarray]:
    """Boolean event mask per `EVENT_SPECS` name (causal: bar j uses rows <= j)."""
    verde, media = _col(df, "konkorde_verde"), _col(df, "konkorde_media")
    bbwp = _col(df, "bbwp")
    ao = _col(df, "ao")
    adx, plus_di, minus_di = _col(df, "adx14"), _col(df, "plus_di"), _col(df, "minus_di")
    macd, macd_signal = _col(df, "macd"), _col(df, "macd_signal")
    rsi = _col(df, "rsi14")

    bb_prev = bbwp.shift(1)
    compression = bbwp.rolling(p.compression_lookback, min_periods=p.compression_lookback).min() <= p.compression_max
    ao_slope = ao.diff()
    ao_slope_prev = ao_slope.shift(1)
    turn = _onset(adx_turn_up(adx, p))

    events = {
        "konkorde_zero_cross_up": _cross_up(verde, 0.0),
        "konkorde_zero_cross_down": _cross_down(verde, 0.0),
        "konkorde_turn_up": _cross_up(verde, media),
        "konkorde_turn_down": _cross_down(verde, media),
        "bbwp_ignition": compression & (bb_prev <= p.ignition_level) & (bbwp > p.ignition_level),
        "bbwp_red_turn": (bb_prev >= p.red_zone) & ((bb_prev - bbwp) >= p.red_drop),
        "ao_zero_cross_up": _cross_up(ao, 0.0),
        "ao_zero_cross_down": _cross_down(ao, 0.0),
        "ao_turn_up": (ao_slope_prev < 0) & (ao_slope >= 0),
        "ao_turn_down": (ao_slope_prev > 0) & (ao_slope <= 0),
        "adx_turn_up_long": turn & (plus_di > minus_di),
        "adx_turn_up_short": turn & (minus_di > plus_di),
        "macd_cross_up": _cross_up(macd, macd_signal),
        "macd_cross_down": _cross_down(macd, macd_signal),
        "rsi_cross_50_up": _cross_up(rsi, p.rsi_mid),
        "rsi_cross_50_down": _cross_down(rsi, p.rsi_mid),
        "rsi_exit_oversold": (rsi.shift(1) < p.rsi_oversold) & (rsi >= p.rsi_oversold),
        "rsi_exit_overbought": (rsi.shift(1) > p.rsi_overbought) & (rsi <= p.rsi_overbought),
    }
    return {k: v.fillna(False).to_numpy(dtype=bool) for k, v in events.items()}


def movement_starts(df: pd.DataFrame, p: LeadTimeParams = LeadTimeParams()) -> Dict[int, np.ndarray]:
    """Bar indices of accepted move starts per side {1: long, -1: short} (look-ahead labels)."""
    close = _col(df, "close").to_numpy(float)
    atr = _col(df, "atr14").to_numpy(float)
    n, h = len(close), int(p.horizon)
    out: Dict[int, List[int]] = {1: [], -1: []}
    for m in range(n - h):
        a = atr[m]
        if not (math.isfinite(a) and a > 0 and math.isfinite(close[m])):
            continue
        fut = close[m + 1: m + h + 1]
        threshold = p.k_atr * a
        for side, move in ((1, np.nanmax(fut) - close[m]), (-1, close[m] - np.nanmin(fut))):
            if move >= threshold and (not out[side] or m - out[side][-1] > h):
                out[side].append(m)
    return {s: np.asarray(v, dtype=int) for s, v in out.items()}


def nearest_start(j: int, starts: np.ndarray, p: LeadTimeParams) -> Optional[int]:
    """Nearest start m with min_lead <= m - j <= max_lead (ties -> m >= j)."""
    if not len(starts):
        return None
    lo = np.searchsorted(starts, j + p.min_lead, side="left")
    hi = np.searchsorted(starts, j + p.max_lead, side="right")
    cand = starts[lo:hi]
    if not len(cand):
        return None
    leads = cand - j
    order = np.lexsort((leads < 0, np.abs(leads)))  # |lead| first, then prefer lead >= 0
    return int(cand[order[0]])


def _match(j: int, side: int, starts: Mapping[int, np.ndarray], p: LeadTimeParams):
    """(start index, start side) or (None, None)."""
    if side != 0:
        m = nearest_start(j, starts[side], p)
        return (m, side) if m is not None else (None, None)
    best = None
    for s in (1, -1):
        m = nearest_start(j, starts[s], p)
        if m is None:
            continue
        key = (abs(m - j), m - j < 0)
        if best is None or key < best[0]:
            best = (key, m, s)
    return (best[1], best[2]) if best else (None, None)


def _quantiles(values: Sequence[float]) -> Dict[str, Optional[float]]:
    if not len(values):
        return {"median": None, "p25": None, "p75": None, "mean": None}
    arr = np.asarray(values, dtype=float)
    return {
        "median": float(np.median(arr)),
        "p25": float(np.percentile(arr, 25)),
        "p75": float(np.percentile(arr, 75)),
        "mean": round(float(arr.mean()), 3),
    }


def base_rate(in_block: np.ndarray, side: int, starts: Mapping[int, np.ndarray], p: LeadTimeParams) -> float:
    """Share of ALL bars of the block that would 'hit' by chance (the bar on its own)."""
    idx = np.flatnonzero(in_block)
    if not len(idx):
        return 0.0
    hits = sum(1 for j in idx if _match(int(j), side, starts, p)[0] is not None)
    return round(hits / len(idx), 4)


def measure(
    df: pd.DataFrame,
    in_block: np.ndarray,
    p: LeadTimeParams = LeadTimeParams(),
) -> Dict[str, Any]:
    """Per-event lead-time stats and leader -> follower lag inside one block.

    `in_block` masks the bars where EVENTS are counted; movement labels use the
    whole frame, so a block-end event can still match a start just after it.
    """
    in_block = np.asarray(in_block, dtype=bool)
    events = detect_events(df, p)
    starts = movement_starts(df, p)

    per_event: Dict[str, Any] = {}
    # assignments[(name)] -> {(start, side): first event bar}
    assignments: Dict[str, Dict[tuple, int]] = {}
    for spec in EVENT_SPECS:
        bars = np.flatnonzero(events[spec.name] & in_block)
        leads: List[int] = []
        first_by_move: Dict[tuple, int] = {}
        for j in bars:
            m, s = _match(int(j), spec.side, starts, p)
            if m is None:
                continue
            leads.append(m - int(j))
            first_by_move.setdefault((m, s), int(j))
        assignments[spec.name] = first_by_move
        n = int(len(bars))
        per_event[spec.name] = {
            "role": spec.role,
            "side": spec.side,
            "n": n,
            "hits": len(leads),
            "hit_rate": round(len(leads) / n, 4) if n else None,
            "lead": _quantiles(leads),
            "moves_covered": len(first_by_move),
        }

    block_starts = {s: [int(m) for m in v if m < len(in_block) and in_block[m]] for s, v in starts.items()}
    rates = {"long": base_rate(in_block, 1, starts, p), "short": base_rate(in_block, -1, starts, p),
             "any": base_rate(in_block, 0, starts, p)}

    lags: Dict[str, Any] = {}
    leaders = [s for s in EVENT_SPECS if s.role == LEADER]
    followers = [s for s in EVENT_SPECS if s.role == FOLLOWER]
    for lead_spec in leaders:
        pooled: List[int] = []
        rows: Dict[str, Any] = {}
        for fol in followers:
            if lead_spec.side != 0 and fol.side != lead_spec.side:
                continue
            values = []
            for (m, s), lj in assignments[lead_spec.name].items():
                if fol.side != s:
                    continue
                fj = assignments[fol.name].get((m, s))
                if fj is not None:
                    values.append(fj - lj)
            if not values:
                continue
            pooled.extend(values)
            rows[fol.name] = {"n_pairs": len(values), **_quantiles(values),
                              "follower_first_pct": round(100 * sum(v < 0 for v in values) / len(values), 1)}
        lags[lead_spec.name] = {"followers": rows, "pooled": {"n_pairs": len(pooled), **_quantiles(pooled)}}

    return {
        "params": asdict(p),
        "bars": int(in_block.sum()),
        "move_starts": {"long": len(block_starts[1]), "short": len(block_starts[-1])},
        "base_rate": rates,
        "events": per_event,
        "lag_follower_minus_leader": lags,
    }


def follower_window(p75_lag: Optional[float], lo: int, hi: int) -> Optional[int]:
    """PROPOSAL (until the trading spec fixes it): clamp(ceil(p75(lag)), lo, hi)."""
    if p75_lag is None:
        return None
    return int(min(max(math.ceil(p75_lag), lo), hi))


WINDOW_BOUNDS = {"4h": (2, 8), "1d": (2, 6)}


__all__: Sequence[str] = (
    "LeadTimeParams", "EventSpec", "EVENT_SPECS", "detect_events", "movement_starts",
    "nearest_start", "measure", "follower_window", "WINDOW_BOUNDS",
)
