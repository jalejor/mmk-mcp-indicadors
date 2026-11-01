"""Impulse engine v2 (impulsos-v2) — spec: docs/impulsos-v2.md (impulse-2.0.0).

Additive to the legacy `RulesService` vote (decisions.md D19): nothing here
changes the `/v1/metrics/get` payload unless the caller opts in
(`impulse_profile`).

The engine reads indicator COLUMNS only, so the analyst goldens
(`tests/fixtures/impulse_golden_cases.json`) are evaluated directly:

    close, high, low, bbwp, konkorde_marron, konkorde_media, konkorde_azul,
    adx14, plus_di, minus_di, ao, macd, macd_signal, atr14

(`open` for gap fills and `timestamp` / a DatetimeIndex for multi-TF alignment
are optional). Every row is a CLOSED candle (spec §0.1); context frames are cut
to candles closed at or before the trigger close (spec §0.2).

One impulse cycle per trigger TF: compression -> ignition -> expansion ->
exhaustion -> contraction. Entry only on ignition with a resolved side that the
guardian TF does not oppose; exit chain: ATR stop -> owner's (Jeisson) rule ->
phase lost -> time stop. Every derived column is causal and vectorised; only
the position state machine iterates, so `replay` is O(n).
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .market_data_service import (
    DEFAULT_EXCHANGE,
    MarketDataService,
    _TIMEFRAME_TO_SECONDS,
    _month_candle_close_ms,
)
from .setup_service import LOW_TF_BAND
from .trade_profiles import DEFAULT_PROFILE, get_trade_profile, profile_timeframes

RULE_VERSION = "impulse-2.0.0"

KONKORDE_LINES = ("edge", "azul", "oscp")
SIDE_VALUES = {"long": 1, "short": -1}
SIDE_LABELS = {1: "long", -1: "short", 0: "none"}
PHASES = ("exhaustion", "ignition", "expansion", "compression", "contraction", "building", "unknown")

INDICATOR_COLUMNS = (
    "close", "high", "low", "bbwp", "konkorde_marron", "konkorde_media",
    "konkorde_verde", "konkorde_azul", "adx14", "plus_di", "minus_di", "ao",
    "macd", "macd_signal", "atr14",
)
COMPONENTS = ("konkorde", "adx", "ao", "macd")

# Spec parameter names (docs/impulsos-v2.md §h, golden "params") -> field names.
SPEC_PARAM_ALIASES = {
    "compression_max": "bbwp_compression_max",
    "blue_level": "bbwp_blue_level",
    "breakout_level": "bbwp_expansion_min",
    "exhaustion_level": "bbwp_red_zone",
    "red_drop_min": "bbwp_exit_drop_pts",
    "exit_window": "exit_window_candles",
    "stop_atr_mult": "atr_mult_stop",
}


# ---------------------------------------------------------------------------
# Parameters (rule data — any change bumps `rule_version`, spec §0.4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ImpulseParams:
    profile: str = DEFAULT_PROFILE
    trigger_tf: str = "4h"
    confirm_tf: str = "1d"  # guardian: the only context TF that can block
    context_tfs: Tuple[str, ...] = ("1d", "1w")

    # §b phases (BBWP, TV definition)
    bbwp_compression_max: float = 30.0
    bbwp_blue_level: float = 20.0
    compression_lookback: int = 10
    bbwp_expansion_min: float = 50.0  # breakout level (strict cross)
    breakout_ttl: int = 3  # breakout ages 0..ttl-1 are ignition
    bbwp_red_zone: float = 90.0
    bbwp_exit_drop_pts: float = 8.0  # one-candle drop from >= red zone
    exit_window_candles: int = 3

    # §c side
    konkorde_line: str = "edge"  # edge = marron - media (spec decision)
    weight_konkorde: float = 3.0
    weight_adx: float = 2.0
    weight_ao: float = 2.0
    weight_macd: float = 1.0
    adx_slope_window: int = 3
    adx_rising_slope: float = 0.5
    side_threshold_high: float = 0.5
    side_threshold_low: float = 0.6

    # E1 adx_turn (confidence only)
    adx_turn_window: int = 3
    adx_base_window: int = 5
    adx_turn_min_slope: float = 1.0
    adx_turn_min_delta_slope: float = 1.5
    adx_turn_floor: float = 10.0

    # E2 ao_divergence (defaults of setup_service.DivergenceParams)
    ao_pivot_strength: int = 2
    ao_divergence_lookback: int = 60
    ao_min_pivot_distance: int = 5
    ao_max_pivot_distance: int = 40
    ao_divergence_ttl: int = 10

    # §d confidence / §e context
    fresh_cross_bars: int = 5
    ctx_bias_threshold: float = 3.0

    # §d exit chain
    atr_mult_stop: float = 1.5
    phase_lost_level: float = 50.0
    time_stop_bars: Optional[int] = None
    time_stop_min_r: float = 0.5
    exit_rule_base_confidence: float = 0.6
    phase_lost_confidence: float = 0.6
    time_stop_confidence: float = 0.5
    stop_confidence: float = 1.0

    rule_version: str = RULE_VERSION

    def __post_init__(self) -> None:
        if self.konkorde_line not in KONKORDE_LINES:
            raise ValueError(f"Unknown konkorde_line: {self.konkorde_line!r} (use one of {KONKORDE_LINES})")
        for name in ("compression_lookback", "breakout_ttl", "exit_window_candles", "adx_slope_window",
                     "adx_turn_window", "adx_base_window", "ao_pivot_strength", "fresh_cross_bars"):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be >= 1")
        if self.bbwp_compression_max >= self.bbwp_expansion_min:
            raise ValueError("bbwp_compression_max must be below bbwp_expansion_min")
        object.__setattr__(self, "context_tfs", tuple(self.context_tfs))

    @classmethod
    def for_profile(cls, name: str, **overrides: Any) -> "ImpulseParams":
        """Params bound to a `TRADE_PROFILES` entry (TFs, ATR stop, time stop)."""
        profile = get_trade_profile(name)
        base: Dict[str, Any] = {
            "profile": name,
            "trigger_tf": profile["trigger_tf"],
            "confirm_tf": profile["confirm_tf"],
            "context_tfs": tuple(profile["context_tfs"]),
            "atr_mult_stop": float(profile["atr_mult_stop"]),
            "time_stop_bars": profile.get("time_stop_bars"),
        }
        base.update(overrides)
        return cls(**base)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ImpulseParams":
        """Build from a dict using field names or the spec's names; unknown keys ignored."""
        known = {f.name for f in fields(cls)}
        values: Dict[str, Any] = {}
        for key, value in data.items():
            key = SPEC_PARAM_ALIASES.get(key, key)
            if key in known:
                values[key] = value
        if "context_tfs" in values:
            values["context_tfs"] = tuple(values["context_tfs"])
        profile = values.pop("profile", None)
        if profile is not None:
            return cls.for_profile(profile, **values)
        return cls(**values)

    def context_order(self) -> Tuple[str, ...]:
        """Guardian first, then the other context TFs; never the trigger TF."""
        ordered: List[str] = []
        for tf in (self.confirm_tf, *self.context_tfs):
            if tf and tf != self.trigger_tf and tf not in ordered:
                ordered.append(tf)
        return tuple(ordered)

    def weights(self) -> Dict[str, float]:
        return {
            "konkorde": float(self.weight_konkorde),
            "adx": float(self.weight_adx),
            "ao": float(self.weight_ao),
            "macd": float(self.weight_macd),
        }


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------

@dataclass
class ImpulseDecision:
    timestamp: Optional[int]  # open ms of the CLOSED trigger candle
    timeframe: str
    profile: str
    side: str  # long | short | none
    phase: str  # see PHASES
    action: str  # enter | exit | hold | none
    reasons: List[str] = field(default_factory=list)
    confidence: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    rule_version: str = RULE_VERSION
    side_score: Optional[float] = None
    context_bias: Dict[str, Optional[int]] = field(default_factory=dict)
    stop_price: Optional[float] = None
    exit_price: Optional[float] = None
    candle_close: Optional[str] = None  # ISO close instant of the trigger candle

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "timeframe": self.timeframe,
            "trigger_tf": self.timeframe,
            "candle_close": self.candle_close,
            "profile": self.profile,
            "side": self.side,
            "phase": self.phase,
            "action": self.action,
            "reasons": list(self.reasons),
            "confidence": round(float(self.confidence), 4),
            "side_score": _clean(self.side_score),
            "context_bias": _clean(self.context_bias),
            "stop_price": _clean(self.stop_price),
            "exit_price": _clean(self.exit_price),
            "context": _clean(self.context),
            "rule_version": self.rule_version,
        }


def _clean(value: Any) -> Any:
    """JSON-safe copy: NaN/inf -> None, numpy scalars -> python."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        f = float(value)
        return round(f, 6) if math.isfinite(f) else None
    return value


# ---------------------------------------------------------------------------
# Vectorised derivation (causal: row i only uses rows <= i)
# ---------------------------------------------------------------------------

def is_low_band(timeframe: str) -> bool:
    """Spec §0.3: everything below 4h is low_tf (Konkorde forbidden)."""
    return timeframe in LOW_TF_BAND


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    if name in df.columns:
        return pd.to_numeric(df[name], errors="coerce").astype(float).reset_index(drop=True)
    if name == "konkorde_marron" and "konkorde_value" in df.columns:
        return _col(df, "konkorde_value")
    return pd.Series(np.nan, index=pd.RangeIndex(len(df)), dtype=float)


def _window(flag: pd.Series, window: int) -> pd.Series:
    """True when `flag` fired on any of the last `window` rows (current included)."""
    return flag.astype(float).rolling(window, min_periods=1).max().fillna(0.0) > 0


def _sign(series: pd.Series) -> pd.Series:
    out = pd.Series(0, index=series.index, dtype=int)
    out[series > 0] = 1
    out[series < 0] = -1
    return out


def _open_ms(df: pd.DataFrame) -> Optional[np.ndarray]:
    if "timestamp" in df.columns:
        ts = pd.to_numeric(df["timestamp"], errors="coerce")
        if len(ts) and ts.notna().all():
            return ts.to_numpy(dtype="int64")
    if isinstance(df.index, pd.DatetimeIndex) and len(df.index):
        idx = df.index if df.index.tz is not None else df.index.tz_localize("UTC")
        delta = (idx - pd.Timestamp(0, tz="UTC")) // pd.Timedelta(milliseconds=1)
        return np.asarray(delta, dtype="int64")
    return None


def _close_ms(open_ms: Optional[np.ndarray], timeframe: str) -> Optional[np.ndarray]:
    if open_ms is None:
        return None
    if timeframe == "1M":
        return np.array([_month_candle_close_ms(int(x)) for x in open_ms], dtype="int64")
    duration_s = _TIMEFRAME_TO_SECONDS.get(timeframe)
    if duration_s is None:
        raise ValueError(f"Unknown timeframe: {timeframe}")
    return open_ms + duration_s * 1000


def _konkorde_line(df: pd.DataFrame, kind: str) -> pd.Series:
    marron = _col(df, "konkorde_marron")
    if kind == "edge":
        media = _col(df, "konkorde_media")
        if media.isna().all() and marron.notna().any():
            media = marron.ewm(span=15, adjust=False).mean()  # D18: media = EMA15(marron)
        return marron - media
    if kind == "azul":
        return _col(df, "konkorde_azul")
    return _col(df, "konkorde_verde") - marron  # oscp


def _fractal_pivots(series: pd.Series, strength: int, kind: str) -> List[int]:
    """Vectorised `setup_service.fractal_pivots` (strict min/max of i±strength)."""
    n = len(series)
    if n < 2 * strength + 1:
        return []
    cond = pd.Series(True, index=series.index)
    for k in range(1, strength + 1):
        for other in (series.shift(k), series.shift(-k)):
            cond &= (series < other) if kind == "low" else (series > other)
    return [int(i) for i in np.flatnonzero(cond.to_numpy())]


def _ao_divergence_active(ao: pd.Series, price: pd.Series, side: str, p: ImpulseParams) -> np.ndarray:
    """E2 `ao_divergence` evaluated at every bar, causally.

    Same semantics as `setup_service.ao_divergence` on `series[:t+1]`: pivots
    are confirmed `strength` bars later, the pair must sit inside the
    lookback, the signal lives `ttl` bars and dies if price breaks the second
    pivot's extreme.
    """
    n = len(ao)
    out = np.zeros(n, dtype=bool)
    s = p.ao_pivot_strength
    kind = "low" if side == "bullish" else "high"
    pivots = _fractal_pivots(ao, s, kind)
    if len(pivots) < 2:
        return out
    aov = ao.to_numpy(dtype=float)
    prv = price.to_numpy(dtype=float)
    for t in range(n):
        hi = bisect_right(pivots, t - s)
        lo = bisect_left(pivots, t - p.ao_divergence_lookback + 1)
        if hi - lo < 2:
            continue
        p2 = pivots[hi - 1]
        if t - (p2 + s) > p.ao_divergence_ttl:
            continue
        p1 = None
        for k in range(hi - 2, lo - 1, -1):
            distance = p2 - pivots[k]
            if distance > p.ao_max_pivot_distance:
                break
            if distance >= p.ao_min_pivot_distance:
                p1 = pivots[k]
                break
        if p1 is None:
            continue
        ao1, ao2, pr1, pr2 = aov[p1], aov[p2], prv[p1], prv[p2]
        if side == "bullish":
            shape = ao2 > ao1 and pr2 < pr1 and ao1 < 0 and ao2 < 0
        else:
            shape = ao2 < ao1 and pr2 > pr1 and ao1 > 0 and ao2 > 0
        if not shape:
            continue
        post = prv[p2 + 1: t + 1]
        if len(post) and ((side == "bullish" and np.nanmin(post) < pr2) or (side == "bearish" and np.nanmax(post) > pr2)):
            continue
        out[t] = True
    return out


@dataclass
class _Derived:
    timeframe: str
    low_band: bool
    n: int
    arrays: Dict[str, np.ndarray]
    open_ms: Optional[np.ndarray]
    close_ms: Optional[np.ndarray]

    def __getitem__(self, key: str) -> np.ndarray:
        return self.arrays[key]


def _derive(df: pd.DataFrame, timeframe: str, p: ImpulseParams) -> _Derived:
    low_band = is_low_band(timeframe)
    close = _col(df, "close")
    high = _col(df, "high").fillna(close)
    low = _col(df, "low").fillna(close)
    open_ = _col(df, "open")
    bbwp = _col(df, "bbwp")
    edge = _konkorde_line(df, p.konkorde_line)
    azul = _col(df, "konkorde_azul")
    adx = _col(df, "adx14")
    plus_di = _col(df, "plus_di")
    minus_di = _col(df, "minus_di")
    ao = _col(df, "ao")
    macd = _col(df, "macd")
    macd_signal = _col(df, "macd_signal")
    atr = _col(df, "atr14")
    idx = pd.Series(np.arange(len(df), dtype=float))

    # -- §b phases -----------------------------------------------------------
    prev = bbwp.shift(1)
    window = p.exit_window_candles
    breakout_ev = (prev <= p.bbwp_expansion_min) & (bbwp > p.bbwp_expansion_min)
    last_breakout = idx.where(breakout_ev).ffill()
    breakout_age = idx - last_breakout
    compression_recent = bbwp.rolling(p.compression_lookback, min_periods=1).min() <= p.bbwp_compression_max
    blue_recent = bbwp.rolling(p.compression_lookback, min_periods=1).min() <= p.bbwp_blue_level
    zone_jump_ev = breakout_ev & (prev < p.bbwp_blue_level)
    zone_jump = zone_jump_ev.astype(float).where(breakout_ev).ffill().fillna(0.0) > 0

    drop = prev - bbwp
    red_drop_ev = (prev >= p.bbwp_red_zone) & (drop >= p.bbwp_exit_drop_pts)
    red_drop_win = _window(red_drop_ev, window)
    peak_win = bbwp.rolling(window, min_periods=1).max()
    above_before = prev.rolling(max(p.compression_lookback - 1, 1), min_periods=1).max() > p.bbwp_expansion_min

    ignition = (bbwp > p.bbwp_expansion_min) & (breakout_age <= p.breakout_ttl - 1) & compression_recent
    conditions = [
        bbwp.isna(),
        (bbwp >= p.bbwp_red_zone) | ((peak_win >= p.bbwp_red_zone) & red_drop_win),
        ignition,
        bbwp > p.bbwp_expansion_min,
        bbwp <= p.bbwp_compression_max,
        above_before,
    ]
    phase = np.select([c.to_numpy(dtype=bool) for c in conditions],
                      ["unknown", "exhaustion", "ignition", "expansion", "compression", "contraction"],
                      default="building")

    # -- §c side votes ---------------------------------------------------------
    edge_prev = edge.shift(1)
    k_vote = pd.Series(0, index=idx.index, dtype=int)
    k_vote[(edge > 0) & (edge > edge_prev)] = 1
    k_vote[(edge < 0) & (edge < edge_prev)] = -1

    w = p.adx_slope_window
    slope = (adx - adx.shift(w)) / w
    adx_rising = slope >= p.adx_rising_slope
    adx_vote = pd.Series(0, index=idx.index, dtype=int)
    adx_vote[(plus_di > minus_di) & adx_rising] = 1
    adx_vote[(minus_di > plus_di) & adx_rising] = -1

    bull_div = pd.Series(_ao_divergence_active(ao, low, "bullish", p))
    bear_div = pd.Series(_ao_divergence_active(ao, high, "bearish", p))
    ao_prev = ao.shift(1)
    ao_pos = ((ao > 0) & (ao > ao_prev)) | bull_div
    ao_neg = ((ao < 0) & (ao < ao_prev)) | bear_div
    ao_vote = pd.Series(0, index=idx.index, dtype=int)
    ao_vote[ao_pos & ~ao_neg] = 1
    ao_vote[ao_neg & ~ao_pos] = -1

    macd_vote = _sign(macd - macd_signal)

    weights = p.weights()
    if low_band:
        k_vote_used = pd.Series(0, index=idx.index, dtype=int)
        total_weight = weights["adx"] + weights["ao"] + weights["macd"]
    else:
        k_vote_used = k_vote
        total_weight = sum(weights.values())
    score = (weights["konkorde"] * k_vote_used + weights["adx"] * adx_vote
             + weights["ao"] * ao_vote + weights["macd"] * macd_vote) / total_weight
    di_sign = _sign(plus_di - minus_di)

    # -- E1 adx_turn_up (confidence) ------------------------------------------
    tw, bw = p.adx_turn_window, p.adx_base_window
    slope_recent = (adx - adx.shift(tw)) / tw
    slope_prior = (adx.shift(tw) - adx.shift(tw + bw)) / bw
    adx_turn_up = (
        (slope_recent >= p.adx_turn_min_slope)
        & ((slope_recent - slope_prior) >= p.adx_turn_min_delta_slope)
        & (adx >= p.adx_turn_floor)
    )

    # -- crosses -----------------------------------------------------------------
    fresh = p.fresh_cross_bars
    edge_cross_up = (edge_prev <= 0) & (edge > 0)
    edge_cross_down = (edge_prev >= 0) & (edge < 0)
    ao_cross_up = (ao_prev <= 0) & (ao > 0)
    ao_cross_down = (ao_prev >= 0) & (ao < 0)
    # Against-cross legs of the owner's exit (spec §d): edge on high_tf, AO below 4h.
    against_long = ao_cross_down if low_band else edge_cross_down
    against_short = ao_cross_up if low_band else edge_cross_up

    # -- §e context bias (as a context TF) -------------------------------------
    ctx_parts = {
        "konkorde": (3.0, edge),
        "di": (2.0, plus_di - minus_di),
        "ao": (2.0, ao),
        "macd": (1.0, macd - macd_signal),
    }
    if low_band:
        ctx_parts.pop("konkorde")  # spec §0.3: Konkorde never votes below 4h
    ctx_score = sum(weight * _sign(s.fillna(0.0)) for weight, s in ctx_parts.values())
    ctx_has_data = pd.concat([s.notna() for _, s in ctx_parts.values()], axis=1).any(axis=1)
    ctx_bias = pd.Series(0, index=idx.index, dtype=int)
    ctx_bias[ctx_score >= p.ctx_bias_threshold] = 1
    ctx_bias[ctx_score <= -p.ctx_bias_threshold] = -1

    open_ms = _open_ms(df)
    arrays = {
        "close": close, "high": high, "low": low, "open": open_, "bbwp": bbwp, "drop": drop,
        "edge": edge, "azul": azul, "atr": atr, "ao": ao,
        "phase": pd.Series(phase),
        "breakout_age": breakout_age,
        "compression_recent": compression_recent, "blue_recent": blue_recent, "zone_jump": zone_jump,
        "red_drop_ev": red_drop_ev,
        "k_vote": k_vote, "adx_vote": adx_vote, "ao_vote": ao_vote, "macd_vote": macd_vote,
        "score": score, "di_sign": di_sign,
        "adx_turn_up": adx_turn_up,
        "bull_div": bull_div, "bear_div": bear_div,
        "edge_cross_up_fresh": _window(edge_cross_up, fresh),
        "edge_cross_down_fresh": _window(edge_cross_down, fresh),
        "ao_cross_up_fresh": _window(ao_cross_up, fresh),
        "ao_cross_down_fresh": _window(ao_cross_down, fresh),
        "against_long_ev": against_long, "against_short_ev": against_short,
        "edge_cross_up_ev": edge_cross_up, "edge_cross_down_ev": edge_cross_down,
        "ctx_score": ctx_score, "ctx_bias": ctx_bias, "ctx_has_data": ctx_has_data,
    }
    return _Derived(
        timeframe=timeframe,
        low_band=low_band,
        n=len(df),
        arrays={k: v.to_numpy() for k, v in arrays.items()},
        open_ms=open_ms,
        close_ms=_close_ms(open_ms, timeframe),
    )


def _f(arr: np.ndarray, i: int) -> Optional[float]:
    value = float(arr[i])
    return value if math.isfinite(value) else None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ImpulseEngine:
    """Stateless evaluator; `replay` carries a virtual position across candles."""

    def __init__(self, params: ImpulseParams) -> None:
        self.params = params

    # -- public API ----------------------------------------------------------
    def evaluate(
        self,
        frames: Mapping[str, pd.DataFrame],
        *,
        position: Optional[str] = None,
        entry_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        bars_held: Optional[int] = None,
    ) -> ImpulseDecision:
        """Decide at the LAST row of the trigger frame (the last closed candle).

        Context frames are cut to candles closed at or before the trigger
        close (spec §0.2); frames without timestamps use their last row and
        the caller owns the alignment (goldens). With an open `position`,
        `stop_price` (initial stop; derived from `entry_price` and the current
        ATR when omitted) and `bars_held` enable the stop and time-stop exits.
        """
        position = self._check_position(position)
        trig, contexts = self._derive_all(frames)
        if trig.n == 0:
            raise ValueError(f"Empty trigger frame for {self.params.trigger_tf}")
        i = trig.n - 1
        ctx_pos = {tf: self._context_index(trig, d, i) for tf, d in contexts.items()}
        if position is not None and stop_price is None and entry_price is not None:
            stop_price = self._stop_from(position, float(entry_price), trig["atr"][i])
        return self._decide(trig, i, contexts, ctx_pos, position, entry_price, stop_price, bars_held)

    def replay(self, frames: Mapping[str, pd.DataFrame], *, warmup: int = 300) -> List[ImpulseDecision]:
        """One decision per closed trigger candle from `warmup` on.

        Keeps a virtual position (enter -> exit, no flips, spec §d). Row i only
        sees trigger rows <= i and context candles closed <= the trigger close.
        Every derived column is causal, so truncating the future never changes
        a past decision.
        """
        trig, contexts = self._derive_all(frames)
        if contexts and trig.close_ms is None:
            raise ValueError("replay needs timestamps on the trigger frame to align context frames")
        ctx_idx: Dict[str, np.ndarray] = {}
        for tf, d in contexts.items():
            if d.close_ms is None:
                raise ValueError(f"replay needs timestamps on the {tf} context frame")
            ctx_idx[tf] = np.searchsorted(d.close_ms, trig.close_ms, side="right") - 1

        decisions: List[ImpulseDecision] = []
        position: Optional[str] = None
        entry: Optional[float] = None
        stop: Optional[float] = None
        entry_bar = 0
        for i in range(max(int(warmup), 0), trig.n):
            ctx_pos = {tf: int(idx[i]) for tf, idx in ctx_idx.items()}
            held = i - entry_bar if position else None
            decision = self._decide(trig, i, contexts, ctx_pos, position, entry, stop, held)
            if decision.action == "enter":
                position, entry, stop, entry_bar = decision.side, float(trig["close"][i]), decision.stop_price, i
            elif decision.action == "exit":
                position, entry, stop = None, None, None
            decisions.append(decision)
        return decisions

    # -- internals -------------------------------------------------------------
    @staticmethod
    def _check_position(position: Optional[str]) -> Optional[str]:
        if position in (None, "", "flat", "none"):
            return None
        if position not in SIDE_VALUES:
            raise ValueError(f"Unknown position: {position!r} (use long | short)")
        return position

    def _stop_from(self, side: str, entry: float, atr: float) -> Optional[float]:
        if not math.isfinite(atr) or atr <= 0:
            return None
        distance = self.params.atr_mult_stop * atr
        return entry - distance if side == "long" else entry + distance

    def _derive_all(self, frames: Mapping[str, pd.DataFrame]) -> Tuple[_Derived, Dict[str, _Derived]]:
        p = self.params
        if frames.get(p.trigger_tf) is None:
            raise ValueError(f"Missing trigger frame {p.trigger_tf!r}")
        trig = _derive(frames[p.trigger_tf], p.trigger_tf, p)
        contexts: Dict[str, _Derived] = {}
        for tf in p.context_order():
            df = frames.get(tf)
            if df is not None and len(df):
                contexts[tf] = _derive(df, tf, p)
        return trig, contexts

    @staticmethod
    def _context_index(trig: _Derived, ctx: _Derived, i: int) -> int:
        if trig.close_ms is None or ctx.close_ms is None:
            return ctx.n - 1
        return int(np.searchsorted(ctx.close_ms, trig.close_ms[i], side="right")) - 1

    def _context(self, contexts, ctx_pos) -> Tuple[Dict[str, Any], Dict[str, Optional[int]]]:
        info: Dict[str, Any] = {}
        bias: Dict[str, Optional[int]] = {}
        for tf in self.params.context_order():
            d = contexts.get(tf)
            pos = ctx_pos.get(tf, -1)
            if d is None or pos < 0 or not bool(d["ctx_has_data"][pos]):
                info[tf] = {"available": False}
                bias[tf] = None
                continue
            bias[tf] = int(d["ctx_bias"][pos])
            info[tf] = {
                "available": True,
                "candle_ts": int(d.open_ms[pos]) if d.open_ms is not None else None,
                "bias": bias[tf],
                "score": _f(d["ctx_score"], pos),
                "phase": str(d["phase"][pos]),
                "bbwp": _f(d["bbwp"], pos),
                "edge": _f(d["edge"], pos),
            }
        return info, bias

    def _decide(self, trig, i, contexts, ctx_pos, position, entry_price, stop_price, bars_held) -> ImpulseDecision:
        p = self.params
        info, bias = self._context(contexts, ctx_pos)
        candle_close = None
        if trig.close_ms is not None:
            candle_close = datetime.fromtimestamp(int(trig.close_ms[i]) / 1000.0, tz=timezone.utc).isoformat()
        decision = ImpulseDecision(
            timestamp=int(trig.open_ms[i]) if trig.open_ms is not None else None,
            timeframe=trig.timeframe,
            profile=p.profile,
            side="none",
            phase=str(trig["phase"][i]),
            action="none",
            side_score=_f(trig["score"], i),
            context_bias=bias,
            candle_close=candle_close,
            rule_version=p.rule_version,
            context={
                "band": "low_tf" if trig.low_band else "high_tf",
                "guardian": p.confirm_tf,
                "votes": {
                    "konkorde": None if trig.low_band else int(trig["k_vote"][i]),
                    "adx": int(trig["adx_vote"][i]),
                    "ao": int(trig["ao_vote"][i]),
                    "macd": int(trig["macd_vote"][i]),
                },
                "values": {
                    "close": _f(trig["close"], i),
                    "bbwp": _f(trig["bbwp"], i),
                    "edge": _f(trig["edge"], i),
                    "atr14": _f(trig["atr"], i),
                },
                "timeframes": info,
            },
        )
        if position is None:
            self._decide_flat(trig, i, bias, decision)
        else:
            self._decide_open(trig, i, position, entry_price, stop_price, bars_held, decision)
        return decision

    # -- flat: entry (§c, §d, §e) ---------------------------------------------
    def _decide_flat(self, trig, i, bias, decision: ImpulseDecision) -> None:
        p = self.params
        reasons = decision.reasons
        if trig.low_band:
            reasons.append("band_konkorde_excluded")
        if not math.isfinite(float(trig["bbwp"][i])):
            reasons.append("insufficient_data")
            return
        if decision.phase != "ignition":
            reasons.append("no_compression_breakout")
            return

        score = float(trig["score"][i]) if math.isfinite(float(trig["score"][i])) else 0.0
        threshold = p.side_threshold_low if trig.low_band else p.side_threshold_high
        if score >= threshold:
            side = 1
        elif score <= -threshold:
            side = -1
        else:
            reasons.append("side_ambiguous")
            return
        if int(trig["di_sign"][i]) != side:
            reasons.append("di_against_side")
            return
        if not trig.low_band and int(trig["k_vote"][i]) == -side:
            reasons.append("konkorde_against_side")
            return

        guardian = bias.get(p.confirm_tf)
        if guardian is None:
            reasons.append("context_missing")
            return
        if guardian == -side:
            reasons.append("context_against")
            return

        label = SIDE_LABELS[side]
        bull = side == 1
        reasons += ["bbwp_compression_recent", "bbwp_breakout_from_compression"]
        zone_jump = bool(trig["zone_jump"][i])
        if zone_jump:
            reasons.append("bbwp_zone_jump")
        if not trig.low_band and int(trig["k_vote"][i]) == side:
            reasons.append("konkorde_edge_positive" if bull else "konkorde_edge_negative")
        if int(trig["adx_vote"][i]) == side:
            reasons.append("adx_di_bullish" if bull else "adx_di_bearish")
        if int(trig["ao_vote"][i]) == side:
            reasons.append("ao_bullish" if bull else "ao_bearish")
        if int(trig["macd_vote"][i]) == side:
            reasons.append("macd_bullish" if bull else "macd_bearish")

        adx_turn = bool(trig["adx_turn_up"][i])  # DI on the side is guaranteed by the hard check
        if adx_turn:
            reasons.append("adx_turn_up")
        if trig.low_band:
            fresh = bool(trig["ao_cross_up_fresh" if bull else "ao_cross_down_fresh"][i])
            if fresh:
                reasons.append("ao_zero_cross_up" if bull else "ao_zero_cross_down")
            strong = bool(trig["bull_div" if bull else "bear_div"][i])
        else:
            fresh = bool(trig["edge_cross_up_fresh" if bull else "edge_cross_down_fresh"][i])
            if fresh:
                reasons.append("konkorde_edge_cross_up" if bull else "konkorde_edge_cross_down")
            azul = float(trig["azul"][i])
            strong = math.isfinite(azul) and int(np.sign(azul)) == side
            if strong:
                reasons.append("konkorde_strong_hands_agree")
        if bool(trig["bull_div"][i]):
            reasons.append("ao_divergence_bullish")
        if bool(trig["bear_div"][i]):
            reasons.append("ao_divergence_bearish")
        reasons.append("context_aligned" if guardian == side else "context_neutral")

        with_data = [b for b in bias.values() if b is not None]
        ctx_frac = sum(1 for b in with_data if b == side) / len(with_data) if with_data else 0.0
        ignition_q = bool(trig["blue_recent"][i]) or zone_jump
        confidence = (0.35 * abs(score) + 0.20 * ctx_frac + 0.15 * ignition_q
                      + 0.10 * adx_turn + 0.10 * fresh + 0.10 * strong)

        decision.side = label
        decision.action = "enter"
        decision.confidence = float(min(max(confidence, 0.0), 1.0))
        decision.stop_price = self._stop_from(label, float(trig["close"][i]), float(trig["atr"][i]))

    # -- open position: exit chain (§d) ---------------------------------------
    def _jeisson(self, trig, i, side: int) -> Tuple[Optional[float], List[int], List[int]]:
        """Owner's exit: red_drop + against-cross inside the last `window`
        bars, order free, at least one leg on the last bar.

        Returns (confidence or None, drop bars, cross bars). Confidence =
        base + 0.2 x min(1, (drop - 8) / 12) + 0.2 x g, g = 1 / 0.5 / 0 for
        legs 0 / 1 / 2+ bars apart; the best pair wins.
        """
        p = self.params
        start = max(0, i - p.exit_window_candles + 1)
        drops = [j for j in range(start, i + 1) if bool(trig["red_drop_ev"][j])]
        crosses = [j for j in range(start, i + 1) if bool(trig["against_long_ev" if side == 1 else "against_short_ev"][j])]
        best: Optional[float] = None
        for d in drops:
            for c in crosses:
                if i not in (d, c):
                    continue
                size = float(trig["drop"][d])
                g = {0: 1.0, 1: 0.5}.get(abs(d - c), 0.0)
                conf = p.exit_rule_base_confidence + 0.2 * min(1.0, max(0.0, (size - p.bbwp_exit_drop_pts) / 12.0)) + 0.2 * g
                best = conf if best is None else max(best, conf)
        return best, drops, crosses

    def _decide_open(self, trig, i, position, entry_price, stop_price, bars_held, decision: ImpulseDecision) -> None:
        p = self.params
        side = SIDE_VALUES[position]
        decision.side = position
        decision.stop_price = stop_price
        decision.context.update({"entry_price": entry_price, "bars_held": bars_held})
        reasons = decision.reasons
        close = float(trig["close"][i])

        # 1. ATR stop (fill at the stop, or at the open if it gapped beyond)
        if stop_price is not None:
            low, high, open_ = float(trig["low"][i]), float(trig["high"][i]), float(trig["open"][i])
            if (side == 1 and low <= stop_price) or (side == -1 and high >= stop_price):
                fill = stop_price
                if math.isfinite(open_) and ((side == 1 and open_ < stop_price) or (side == -1 and open_ > stop_price)):
                    fill = open_
                reasons.append("exit_stop_atr")
                self._exit(decision, fill, p.stop_confidence)
                return

        # 2. Owner's (Jeisson) rule
        cross_code = "exit_ao_cross_against" if trig.low_band else "exit_konkorde_cross_against"
        conf, drops, crosses = self._jeisson(trig, i, side)
        if conf is not None:
            reasons += ["exit_rule_jeisson", "exit_bbwp_red_drop", cross_code]
            self._exit(decision, close, conf)
            return

        # 3. Phase lost: back to <= 50 with the trend line against
        line = float(trig["ao" if trig.low_band else "edge"][i])
        bbwp = float(trig["bbwp"][i])
        if math.isfinite(bbwp) and bbwp <= p.phase_lost_level and math.isfinite(line) and line * side < 0:
            reasons.append("exit_phase_lost")
            self._exit(decision, close, p.phase_lost_confidence)
            return

        # 4. Time stop
        if (p.time_stop_bars is not None and bars_held is not None and bars_held >= p.time_stop_bars
                and entry_price is not None and stop_price is not None):
            one_r = abs(float(entry_price) - float(stop_price))
            if one_r > 0 and (close - float(entry_price)) * side / one_r < p.time_stop_min_r:
                reasons.append("exit_time_stop")
                self._exit(decision, close, p.time_stop_confidence)
                return

        # Hold
        score = float(trig["score"][i]) if math.isfinite(float(trig["score"][i])) else 0.0
        s_dir = score * side
        healthy_phase = decision.phase in ("ignition", "expansion")
        if bool(drops) != bool(crosses):
            reasons.append("hold_exit_incomplete")
        elif healthy_phase and s_dir > 0:
            reasons.append("hold_expansion_healthy")
        else:
            reasons.append("hold_no_exit_condition")
        if drops:
            reasons.append("bbwp_red_drop")
        if crosses:
            if trig.low_band:
                reasons.append("ao_zero_cross_down" if side == 1 else "ao_zero_cross_up")
            else:
                reasons.append("konkorde_edge_cross_down" if side == 1 else "konkorde_edge_cross_up")
        decision.action = "hold"
        decision.confidence = 0.5 * max(0.0, s_dir) + 0.5 * float(healthy_phase)

    @staticmethod
    def _exit(decision: ImpulseDecision, price: float, confidence: float) -> None:
        decision.action = "exit"
        decision.exit_price = price
        decision.confidence = float(min(max(confidence, 0.0), 1.0))


# ---------------------------------------------------------------------------
# Live evaluation (market data -> indicators -> engine)
# ---------------------------------------------------------------------------

class ImpulseEvaluationService:
    """Loads the profile's TFs (closed candles), enriches them with the TV BBWP
    and evaluates the engine at the last closed trigger candle."""

    DEFAULT_LIMIT = 500  # TV BBWP needs 13 + 256 candles of warmup

    def __init__(
        self,
        *,
        symbol: str,
        profile: str = DEFAULT_PROFILE,
        exchange: str = DEFAULT_EXCHANGE,
        position: Optional[str] = None,
        entry_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        bars_held: Optional[int] = None,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self.symbol = symbol
        self.profile = profile
        self.exchange = exchange.lower()
        self.position = position
        self.entry_price = entry_price
        self.stop_price = stop_price
        self.bars_held = bars_held
        self.limit = int(limit)
        self.params = ImpulseParams.for_profile(profile)

    def _enriched_frame(self, timeframe: str) -> pd.DataFrame:
        from .indicators_service import IndicatorsService

        market = MarketDataService(exchange_name=self.exchange)
        raw = market.get_ohlcv(symbol=self.symbol, timeframe=timeframe, limit=self.limit, drop_forming=True)
        if raw.empty:
            raise ValueError(f"No closed candles for {self.symbol} {timeframe} on {self.exchange}")
        service = IndicatorsService(raw, bbwp_definition="tv")
        service.calculate_all()
        return service.df

    def load_frames(self) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str]]:
        frames: Dict[str, pd.DataFrame] = {}
        status: Dict[str, str] = {}
        for tf in profile_timeframes(self.profile):
            try:
                frames[tf] = self._enriched_frame(tf)
                status[tf] = "ok"
            except Exception as exc:  # context TFs (e.g. short 1M history) degrade to unavailable
                if tf == self.params.trigger_tf:
                    raise
                status[tf] = f"failed:{type(exc).__name__}"
        return frames, status

    def evaluate(self) -> Dict[str, Any]:
        frames, status = self.load_frames()
        decision = ImpulseEngine(self.params).evaluate(
            frames,
            position=self.position,
            entry_price=self.entry_price,
            stop_price=self.stop_price,
            bars_held=self.bars_held,
        )
        payload = decision.to_dict()
        payload.update(
            {
                "symbol": self.symbol,
                "exchange": self.exchange,
                "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
                "trade_profile": _clean(dict(get_trade_profile(self.profile))),
                "tf_status": status,
            }
        )
        return payload


__all__: Sequence[str] = (
    "RULE_VERSION",
    "ImpulseParams",
    "ImpulseDecision",
    "ImpulseEngine",
    "ImpulseEvaluationService",
    "is_low_band",
)
