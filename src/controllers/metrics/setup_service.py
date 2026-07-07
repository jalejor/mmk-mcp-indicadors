"""Multi-TF strategy elements (E1-E5) and declarative setup evaluation — F0.

This module is a layer ABOVE `RulesService` (which stays untouched and keeps
serving the legacy `/v1` endpoints). It implements the owner's five strategy
elements as **pure functions over pandas Series of closed candles**, plus:

* timeframe-band enforcement (low_tf / high_tf, spec §0.3),
* false-entry vetoes V1 (freshness) and V2 (ADX-turn confirmation, spec §B.3),
* the declarative setup evaluator (spec §B.0 evaluation order:
  invalidation → context → trigger → vetoes).

Spec: docs/STRATEGY_SETUPS_SPEC.md (rule_version 0.1.0). Every detector takes
series whose **last element is the evaluation candle** and every candle is
assumed CLOSED (the live path drops the forming candle in
`MarketDataService.get_ohlcv`, spec §0.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

# ---------------------------------------------------------------------------
# Timeframe bands (spec §0.3)
# ---------------------------------------------------------------------------

LOW_TF_BAND = ("1m", "5m", "15m", "30m", "1h", "2h")
HIGH_TF_BAND = ("4h", "6h", "8h", "12h", "1d", "3d", "1w")

TIMEFRAME_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 60 * 60,
    "2h": 2 * 60 * 60,
    "4h": 4 * 60 * 60,
    "6h": 6 * 60 * 60,
    "8h": 8 * 60 * 60,
    "12h": 12 * 60 * 60,
    "1d": 24 * 60 * 60,
    "3d": 3 * 24 * 60 * 60,
    "1w": 7 * 24 * 60 * 60,
}


def band_for_timeframe(timeframe: str) -> str:
    """Return the band ("low_tf" / "high_tf") a timeframe belongs to."""
    if timeframe in LOW_TF_BAND:
        return "low_tf"
    if timeframe in HIGH_TF_BAND:
        return "high_tf"
    raise ValueError(f"Unknown timeframe: {timeframe}")


class SetupValidationError(ValueError):
    """Raised when a rule document violates the band/structure constraints."""


# ---------------------------------------------------------------------------
# E1 — adx_turn: sharp ADX slope change ("90-degree turn")
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AdxTurnParams:
    turn_window: int = 3
    base_window: int = 5
    min_slope: float = 1.0
    min_delta_slope: float = 1.5
    adx_floor: float = 10.0
    # Origin-level quality grading (owner refinement, spec §E1 refinement):
    # A-grade turns pivot from a low-ADX origin inside [origin_low, origin_high]
    # (sweet spot centred at 16); everything else is B-grade.
    origin_low: float = 12.0
    origin_high: float = 20.0


ADX_TURN_DEFAULTS = AdxTurnParams()


@dataclass(frozen=True)
class AdxTurnResult:
    turn_up: bool = False
    turn_down: bool = False
    turn_up_bullish: bool = False
    turn_up_bearish: bool = False
    origin_level: Optional[float] = None
    grade: Optional[str] = None  # "A" | "B", only for up-turns (entry quality)


def adx_turn(
    adx: pd.Series,
    plus_di: Optional[pd.Series] = None,
    minus_di: Optional[pd.Series] = None,
    params: AdxTurnParams = ADX_TURN_DEFAULTS,
) -> AdxTurnResult:
    """Evaluate the E1 detector on the last closed candle of `adx`.

    origin_level is the ADX value at the start of the recent steep leg
    (`adx[-1 - turn_window]`) — the local level the turn pivots from.
    Grading applies to up-turns only: down-turns are invalidation events,
    not entries, so they carry no grade (implementation decision).
    """
    needed = params.turn_window + params.base_window + 1
    values = adx.dropna()
    if len(values) < needed:
        return AdxTurnResult()

    last = float(values.iloc[-1])
    leg_start = float(values.iloc[-1 - params.turn_window])
    base_start = float(values.iloc[-1 - params.turn_window - params.base_window])

    slope_recent = (last - leg_start) / params.turn_window
    slope_prior = (leg_start - base_start) / params.base_window

    turn_up = (
        slope_recent >= params.min_slope
        and (slope_recent - slope_prior) >= params.min_delta_slope
        and last >= params.adx_floor
    )
    turn_down = (
        slope_recent <= -params.min_slope
        and (slope_prior - slope_recent) >= params.min_delta_slope
    )

    turn_up_bullish = turn_up_bearish = False
    if turn_up and plus_di is not None and minus_di is not None:
        p = plus_di.dropna()
        m = minus_di.dropna()
        if len(p) and len(m):
            turn_up_bullish = float(p.iloc[-1]) > float(m.iloc[-1])
            turn_up_bearish = float(m.iloc[-1]) > float(p.iloc[-1])

    origin: Optional[float] = None
    grade: Optional[str] = None
    if turn_up or turn_down:
        origin = leg_start
    if turn_up:
        grade = "A" if params.origin_low <= origin <= params.origin_high else "B"

    return AdxTurnResult(
        turn_up=turn_up,
        turn_down=turn_down,
        turn_up_bullish=turn_up_bullish,
        turn_up_bearish=turn_up_bearish,
        origin_level=origin,
        grade=grade,
    )


@dataclass(frozen=True)
class AdxTurnFire:
    age: int  # closed candles since the turn fired (0 = fired on the last one)
    grade: Optional[str]
    origin_level: Optional[float]


def adx_turn_fired_within(
    adx: pd.Series,
    plus_di: Optional[pd.Series],
    minus_di: Optional[pd.Series],
    *,
    variant: str,
    window: int,
    params: AdxTurnParams = ADX_TURN_DEFAULTS,
) -> Optional[AdxTurnFire]:
    """Most recent `adx_turn` fire of `variant` within the last `window` candles.

    "Within the last N closed candles" includes the evaluation candle itself
    (age 0) up to age N-1 — i.e. the N most recent closed candles (spec §B.3
    V2: "the trigger candle itself counts, age 0").
    Variants: "up" | "down" | "up_bullish" | "up_bearish".
    """
    # Hot path in the backtest (called once per bar): trim every series to the
    # tail actually needed. Tail-slicing the ORIGINAL index keeps adx and the
    # DI series aligned on the same candles (their NaNs only live at the head).
    max_needed = params.turn_window + params.base_window + 1 + window
    if len(adx) > max_needed:
        adx = adx.iloc[-max_needed:]
        if plus_di is not None and len(plus_di) > max_needed:
            plus_di = plus_di.iloc[-max_needed:]
        if minus_di is not None and len(minus_di) > max_needed:
            minus_di = minus_di.iloc[-max_needed:]
    for age in range(0, window):
        end = len(adx) - age
        if end < params.turn_window + params.base_window + 1:
            break
        result = adx_turn(
            adx.iloc[:end],
            plus_di.iloc[:end] if plus_di is not None else None,
            minus_di.iloc[:end] if minus_di is not None else None,
            params,
        )
        fired = {
            "up": result.turn_up,
            "down": result.turn_down,
            "up_bullish": result.turn_up_bullish,
            "up_bearish": result.turn_up_bearish,
        }.get(variant)
        if fired is None:
            raise ValueError(f"Unknown adx_turn variant: {variant}")
        if fired:
            return AdxTurnFire(age=age, grade=result.grade, origin_level=result.origin_level)
    return None


# ---------------------------------------------------------------------------
# E2 — AO divergence / convergence + zero-cross events
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DivergenceParams:
    pivot_strength: int = 2
    divergence_lookback: int = 60
    min_pivot_distance: int = 5
    max_pivot_distance: int = 40
    divergence_ttl: int = 10


DIVERGENCE_DEFAULTS = DivergenceParams()


def fractal_pivots(series: pd.Series, strength: int, kind: str) -> List[int]:
    """Confirmed fractal pivot indexes (positional) of `kind` ("low"/"high").

    Bar i is a pivot iff series[i] is the strict min/max of the full window
    i-strength..i+strength; it is only CONFIRMED `strength` bars later, so
    i + strength must be <= the last closed bar.
    """
    values = series.to_numpy(dtype=float)
    n = len(values)
    pivots: List[int] = []
    for i in range(strength, n - strength):
        window = values[i - strength: i + strength + 1]
        center = values[i]
        others = [window[j] for j in range(len(window)) if j != strength]
        if kind == "low" and all(center < v for v in others):
            pivots.append(i)
        elif kind == "high" and all(center > v for v in others):
            pivots.append(i)
    return pivots


@dataclass(frozen=True)
class DivergenceResult:
    active: bool = False
    fired_age: Optional[int] = None  # closed candles since the firing bar
    pivot_1: Optional[int] = None
    pivot_2: Optional[int] = None


def ao_divergence(
    ao: pd.Series,
    low: Optional[pd.Series] = None,
    high: Optional[pd.Series] = None,
    *,
    side: str = "bullish",
    params: DivergenceParams = DIVERGENCE_DEFAULTS,
) -> DivergenceResult:
    """Regular AO divergence evaluated at the last closed candle.

    Bullish: AO pivot lows p1 < p2 (both confirmed, both AO < 0), AO higher
    low + price lower low. Fires at p2 + pivot_strength and stays active
    `divergence_ttl` closed bars unless price breaks the divergence low
    (any closed bar after p2 with low < low[p2] invalidates it).
    Pair selection: p2 is the most recent confirmed pivot; p1 is the most
    recent earlier pivot satisfying the distance constraint (implementation
    decision — the spec asks for "the two most recent confirmed pivots with
    min <= p2-p1 <= max").
    """
    if side not in ("bullish", "bearish"):
        raise ValueError(f"Unknown divergence side: {side}")
    price = low if side == "bullish" else high
    if price is None:
        raise ValueError("ao_divergence requires the price series (low/high)")

    last = len(ao) - 1
    kind = "low" if side == "bullish" else "high"
    window_start = max(0, last - params.divergence_lookback + 1)
    pivots = [p for p in fractal_pivots(ao, params.pivot_strength, kind) if p >= window_start]
    if len(pivots) < 2:
        return DivergenceResult()

    p2 = pivots[-1]
    p1 = next(
        (
            p
            for p in reversed(pivots[:-1])
            if params.min_pivot_distance <= (p2 - p) <= params.max_pivot_distance
        ),
        None,
    )
    if p1 is None:
        return DivergenceResult()

    ao1, ao2 = float(ao.iloc[p1]), float(ao.iloc[p2])
    pr1, pr2 = float(price.iloc[p1]), float(price.iloc[p2])

    if side == "bullish":
        shape_ok = ao2 > ao1 and pr2 < pr1 and ao1 < 0 and ao2 < 0
    else:
        shape_ok = ao2 < ao1 and pr2 > pr1 and ao1 > 0 and ao2 > 0
    if not shape_ok:
        return DivergenceResult()

    fired_at = p2 + params.pivot_strength
    if fired_at > last:
        return DivergenceResult()  # not confirmed yet
    age = last - fired_at
    if age > params.divergence_ttl:
        return DivergenceResult()

    # Invalidation: price breaks the divergence extreme after the second pivot.
    post = price.iloc[p2 + 1: last + 1]
    if len(post):
        if side == "bullish" and float(post.min()) < pr2:
            return DivergenceResult()
        if side == "bearish" and float(post.max()) > pr2:
            return DivergenceResult()

    return DivergenceResult(active=True, fired_age=age, pivot_1=p1, pivot_2=p2)


def ao_convergence(
    ao: pd.Series,
    low: Optional[pd.Series] = None,
    high: Optional[pd.Series] = None,
    *,
    side: str = "bullish",
    params: DivergenceParams = DIVERGENCE_DEFAULTS,
) -> bool:
    """AO confirms the trend at the last two confirmed pivots (confirmation only)."""
    if side == "bullish":
        if high is None:
            raise ValueError("bullish convergence requires the high series")
        pivots = fractal_pivots(ao, params.pivot_strength, "high")
        if len(pivots) < 2:
            return False
        p1, p2 = pivots[-2], pivots[-1]
        return float(high.iloc[p2]) > float(high.iloc[p1]) and float(ao.iloc[p2]) > float(ao.iloc[p1])
    if side == "bearish":
        if low is None:
            raise ValueError("bearish convergence requires the low series")
        pivots = fractal_pivots(ao, params.pivot_strength, "low")
        if len(pivots) < 2:
            return False
        p1, p2 = pivots[-2], pivots[-1]
        return float(low.iloc[p2]) < float(low.iloc[p1]) and float(ao.iloc[p2]) < float(ao.iloc[p1])
    raise ValueError(f"Unknown convergence side: {side}")


def ao_rising(ao: pd.Series) -> bool:
    return len(ao) >= 2 and float(ao.iloc[-1]) > float(ao.iloc[-2])


def ao_falling(ao: pd.Series) -> bool:
    return len(ao) >= 2 and float(ao.iloc[-1]) < float(ao.iloc[-2])


# ---------------------------------------------------------------------------
# Zero-cross events (E2 ao_zero_cross / E3 konkorde_zero_cross)
# ---------------------------------------------------------------------------

def zero_cross_age(
    series: pd.Series,
    *,
    direction: str = "up",
    confirm_bars: int = 1,
) -> Optional[int]:
    """Age (in closed candles) of the most recent confirmed zero cross.

    With confirm_bars = N the event fires at index f iff the N candles
    f-N+1..f are all on the new side of zero and the candle before the run
    (f-N) was at/on the old side. Age = last_index - f; None when no cross
    is found within the series.
    """
    if direction not in ("up", "down"):
        raise ValueError(f"Unknown cross direction: {direction}")
    values = series.dropna().to_numpy(dtype=float)
    n = len(values)
    for f in range(n - 1, confirm_bars - 1, -1):
        run = values[f - confirm_bars + 1: f + 1]
        before = values[f - confirm_bars]
        if direction == "up" and all(v > 0 for v in run) and before <= 0:
            return (n - 1) - f
        if direction == "down" and all(v < 0 for v in run) and before >= 0:
            return (n - 1) - f
    return None


def konkorde_positive(marron: pd.Series) -> bool:
    values = marron.dropna()
    return len(values) > 0 and float(values.iloc[-1]) > 0


def konkorde_negative(marron: pd.Series) -> bool:
    values = marron.dropna()
    return len(values) > 0 and float(values.iloc[-1]) < 0


# ---------------------------------------------------------------------------
# E4 — vol_turn: V / W turns in the high volatility zone
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VolTurnParams:
    high_zone_abs: float = 70.0  # BBWP source (0-100 by construction)
    min_drop: float = 5.0
    w_min_distance: int = 3
    w_window: int = 12
    peak_tolerance: float = 5.0
    min_trough_depth: float = 5.0
    pivot_strength: int = 1
    # Konkorde curves have no fixed scale -> high zone via rolling percentile.
    percentile_lookback: int = 100
    percentile_q: float = 80.0


VOL_TURN_DEFAULTS = VolTurnParams()


def _high_zone_series(x: pd.Series, source: str, params: VolTurnParams) -> pd.Series:
    """Per-bar high-zone threshold: absolute for BBWP, percentile for Konkorde."""
    if source == "bbwp":
        return pd.Series(params.high_zone_abs, index=x.index)
    # Konkorde curves: rolling percentile with a permissive min_periods so the
    # detector works on short golden series too (implementation decision).
    return x.rolling(params.percentile_lookback, min_periods=2).quantile(params.percentile_q / 100.0)


def v_turn_high(x: pd.Series, *, source: str = "bbwp", params: VolTurnParams = VOL_TURN_DEFAULTS) -> bool:
    """V-turn confirmed on the last closed candle (spec E4)."""
    values = x.dropna()
    if len(values) < 3:
        return False
    zone = _high_zone_series(values, source, params)
    peak = float(values.iloc[-2])
    zone_at_peak = float(zone.iloc[-2]) if not pd.isna(zone.iloc[-2]) else float("inf")
    return (
        peak > float(values.iloc[-3])
        and peak > float(values.iloc[-1])
        and peak >= zone_at_peak
        and (peak - float(values.iloc[-1])) >= params.min_drop
    )


def w_turn_high(x: pd.Series, *, source: str = "bbwp", params: VolTurnParams = VOL_TURN_DEFAULTS) -> bool:
    """W-turn (double test of the high zone) firing on the last closed candle.

    Fires on candle P2 + 1, so at evaluation time the second peak must sit on
    the second-to-last closed candle.
    """
    values = x.dropna()
    last = len(values) - 1
    if last < 4:
        return False
    zone = _high_zone_series(values, source, params)
    pivots = fractal_pivots(values, params.pivot_strength, "high")
    p2_candidates = [p for p in pivots if p + 1 == last]
    if not p2_candidates:
        return False
    p2 = p2_candidates[0]
    x2 = float(values.iloc[p2])
    zone_p2 = float(zone.iloc[p2]) if not pd.isna(zone.iloc[p2]) else float("inf")
    if x2 < zone_p2:
        return False
    for p1 in reversed([p for p in pivots if p < p2]):
        distance = p2 - p1
        if distance < params.w_min_distance or distance > params.w_window:
            continue
        x1 = float(values.iloc[p1])
        zone_p1 = float(zone.iloc[p1]) if not pd.isna(zone.iloc[p1]) else float("inf")
        if x1 < zone_p1:
            continue
        if abs(x2 - x1) > params.peak_tolerance:
            continue
        trough = float(values.iloc[p1 + 1: p2].min())
        if min(x1, x2) - trough >= params.min_trough_depth:
            return True
    return False


def vol_turn_high(x: pd.Series, *, source: str = "bbwp", params: VolTurnParams = VOL_TURN_DEFAULTS) -> bool:
    """Either V or W turn in the high zone (exhaustion evidence, never entry)."""
    return v_turn_high(x, source=source, params=params) or w_turn_high(x, source=source, params=params)


# ---------------------------------------------------------------------------
# E5 — bbwp_regime
# ---------------------------------------------------------------------------

def bbwp_regime_on(bbwp: pd.Series, *, minimum: float = 50.0) -> bool:
    """Volatility regime filter: strictly above `minimum` on the last candle."""
    values = bbwp.dropna()
    return len(values) > 0 and float(values.iloc[-1]) > minimum


# ---------------------------------------------------------------------------
# Setup evaluation (declarative documents — see setup_definitions.py)
# ---------------------------------------------------------------------------

# Condition elements that reference Konkorde and are therefore forbidden in
# the low_tf band (spec §0.3). vol_turn is Konkorde-family only when its
# source is a konkorde_* series.
_KONKORDE_ELEMENTS = {"konkorde_state", "konkorde_zero_cross"}
_KONKORDE_EVENTS = {"konkorde_zero_cross_up", "konkorde_zero_cross_down"}


def _is_konkorde_condition(element: str, source: str = "") -> bool:
    if element in _KONKORDE_ELEMENTS:
        return True
    return element == "vol_turn" and source.startswith("konkorde")


@dataclass
class SetupEvaluation:
    setup_id: str
    rule_version: str
    side: str
    fired: bool = False
    invalidated: bool = False
    context_ok: bool = False
    trigger_ok: bool = False
    vetoed: bool = False
    veto_reasons: List[str] = field(default_factory=list)
    support: List[str] = field(default_factory=list)
    adx_turn_grade: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class SetupService:
    """Evaluates declarative, versioned setups over closed-candle series.

    Callers pass one indicator-enriched DataFrame per timeframe (columns from
    `IndicatorsService.df` after `calculate_all()` + OHLCV). Each DataFrame
    must contain **closed candles only** and must already be aligned per spec
    §0.2 — use `align_context` to cut a context frame at the trigger close.
    """

    def __init__(self, setups: Optional[Sequence["SetupDefinition"]] = None) -> None:
        from .setup_definitions import DEFAULT_SETUPS, validate_setup

        self.setups = list(setups) if setups is not None else list(DEFAULT_SETUPS)
        for setup in self.setups:
            validate_setup(setup)

    # -- multi-TF alignment (spec §0.2) --------------------------------
    @staticmethod
    def align_context(context_df: pd.DataFrame, trigger_close_time: pd.Timestamp, context_timeframe: str) -> pd.DataFrame:
        """Slice `context_df` to candles whose CLOSE time is <= trigger close.

        The index holds candle OPEN times, so a candle is usable when
        open_time + context_duration <= trigger_close_time. This is the
        multi-TF no-lookahead rule.
        """
        duration = pd.Timedelta(seconds=TIMEFRAME_SECONDS[context_timeframe])
        cutoff = trigger_close_time - duration
        pos = context_df.index.searchsorted(cutoff, side="right")
        return context_df.iloc[:pos]

    # -- public API -----------------------------------------------------
    def evaluate_setup(self, setup: "SetupDefinition", frames: Mapping[str, pd.DataFrame]) -> SetupEvaluation:
        """Evaluate one setup at the last closed trigger candle of `frames`.

        `frames` maps timeframe -> enriched DataFrame (already aligned).
        Order (spec §B.0): invalidation -> context -> trigger -> vetoes.
        """
        evaluation = SetupEvaluation(
            setup_id=setup.setup_id, rule_version=setup.rule_version, side=setup.side
        )
        trigger_df = frames[setup.trigger_timeframe]

        # 1. Invalidation (ANY cancels the setup for this candle).
        for cond in setup.invalidation_any_of:
            frame = frames[cond.timeframe or setup.context_timeframe]
            ok, _label = self._eval_condition(cond, frame, setup.timeframe_band)
            if ok:
                evaluation.invalidated = True
                evaluation.details.setdefault("invalidation", []).append(cond.label())
        if evaluation.invalidated:
            return evaluation

        # 2. Context (ALL must hold; any_of group needs at least one).
        context_ok = True
        for cond in setup.context_all_of:
            frame = frames[cond.timeframe or setup.context_timeframe]
            ok, label = self._eval_condition(cond, frame, setup.timeframe_band)
            if ok is None:
                continue  # band-guarded: contributes nothing (spec §0.3)
            if ok:
                evaluation.support.append(label)
            else:
                context_ok = False
        if setup.context_any_of:
            any_hits = []
            for cond in setup.context_any_of:
                frame = frames[cond.timeframe or setup.context_timeframe]
                ok, label = self._eval_condition(cond, frame, setup.timeframe_band)
                if ok:
                    any_hits.append(label)
            if any_hits:
                evaluation.support.extend(any_hits)
            else:
                context_ok = False
        evaluation.context_ok = context_ok
        if not context_ok:
            return evaluation

        # 3. Trigger: any_of evidence (when declared) AND all all_of conditions.
        trigger_ok = True
        evidence: List[str] = []
        if setup.trigger_any_of:
            for cond in setup.trigger_any_of:
                frame = frames[cond.timeframe or setup.trigger_timeframe]
                ok, label = self._eval_condition(cond, frame, setup.timeframe_band)
                if ok:
                    evidence.append(label)
            if not evidence:
                trigger_ok = False
        for cond in setup.trigger_all_of:
            frame = frames[cond.timeframe or setup.trigger_timeframe]
            ok, label = self._eval_condition(cond, frame, setup.timeframe_band)
            if ok is None:
                continue
            if ok:
                evidence.append(label)
            else:
                trigger_ok = False
        evaluation.trigger_ok = trigger_ok
        if trigger_ok:
            evaluation.support.extend(evidence)
            evaluation.details["trigger_evidence"] = evidence
        else:
            return evaluation

        # 4. Vetoes (ANY match suppresses the entry signal).
        reasons, grade = evaluate_vetoes(
            setup.vetoes,
            trigger_df,
            band=setup.timeframe_band,
            satisfied_evidence=evidence,
            optional_evidence={c.label() for c in setup.trigger_any_of},
        )
        evaluation.veto_reasons = reasons
        evaluation.vetoed = bool(reasons)
        evaluation.adx_turn_grade = grade
        evaluation.fired = not evaluation.vetoed
        return evaluation

    def evaluate_all(self, frames_by_setup: Mapping[str, Mapping[str, pd.DataFrame]]) -> List[SetupEvaluation]:
        return [
            self.evaluate_setup(setup, frames_by_setup[setup.setup_id])
            for setup in self.setups
            if setup.setup_id in frames_by_setup
        ]

    # -- condition evaluator ---------------------------------------------
    @staticmethod
    def _eval_condition(cond: "Condition", df: pd.DataFrame, band: str) -> Tuple[Optional[bool], str]:
        """Evaluate one declarative condition on the last closed candle of `df`.

        Returns (result, label). result=None means the condition was
        band-guarded away (Konkorde in low_tf): it never votes, never joins
        support lists and contributes 0 (spec §0.3 runtime guard, B0-G2).
        """
        label = cond.label()
        if band == "low_tf" and _is_konkorde_condition(cond.element, cond.source):
            return None, label

        params = dict(cond.params)
        element = cond.element

        if element == "close_above_sma200":
            return _last(df, "close") > _last(df, "sma200"), label
        if element == "close_below_sma200":
            return _last(df, "close") < _last(df, "sma200"), label
        if element == "ema50_above_sma50":
            return _last(df, "ema50") > _last(df, "sma50"), label
        if element == "ema50_below_sma50":
            return _last(df, "ema50") < _last(df, "sma50"), label
        if element == "adx_level":
            adx = _last(df, "adx14")
            plus_di = _last(df, "plus_di")
            minus_di = _last(df, "minus_di")
            threshold = float(params.get("threshold", 25.0))
            if cond.variant == "bullish":
                return adx >= threshold and plus_di > minus_di, label
            if cond.variant == "bearish":
                return adx >= threshold and minus_di > plus_di, label
            raise ValueError(f"Unknown adx_level variant: {cond.variant}")
        if element == "adx_turn":
            window = int(params.get("fired_within", 1))
            turn_params = _adx_params_from(params)
            fire = adx_turn_fired_within(
                df["adx14"], df.get("plus_di"), df.get("minus_di"),
                variant=cond.variant, window=window, params=turn_params,
            )
            return fire is not None, label
        if element == "konkorde_state":
            if cond.variant == "positive":
                return konkorde_positive(df["konkorde_marron"]), label
            if cond.variant == "negative":
                return konkorde_negative(df["konkorde_marron"]), label
            raise ValueError(f"Unknown konkorde_state variant: {cond.variant}")
        if element == "konkorde_zero_cross":
            confirm_bars = int(params.get("confirm_bars", 1))
            max_age = int(params.get("max_event_age", 5))
            age = zero_cross_age(df["konkorde_marron"], direction=cond.variant, confirm_bars=confirm_bars)
            # As a trigger condition the cross is satisfied while fresh
            # (age <= max_event_age); V1 then re-checks freshness with its
            # own window. FE-G1 pins this: a cross of age 1 satisfies the
            # trigger even though it did not fire on the evaluation candle.
            return age is not None and age <= max_age, label
        if element == "ao_divergence":
            active_within = params.get("active_within")
            div_params = _divergence_params_from(params)
            result = ao_divergence(
                df["ao"], low=df.get("low"), high=df.get("high"),
                side=cond.variant, params=div_params,
            )
            if not result.active:
                return False, label
            if active_within is not None and result.fired_age is not None:
                return result.fired_age <= int(active_within), label
            return True, label
        if element == "pullback_state":
            window = int(params.get("pullback_window", 10))
            lows = df["low"].iloc[-window:]
            return len(lows) > 0 and float(lows.min()) <= _last(df, "ema50"), label
        if element == "rally_state":
            window = int(params.get("pullback_window", 10))
            highs = df["high"].iloc[-window:]
            return len(highs) > 0 and float(highs.max()) >= _last(df, "ema50"), label
        if element == "close_breaks_prior_high":
            return len(df) >= 2 and _last(df, "close") > float(df["high"].iloc[-2]), label
        if element == "close_breaks_prior_low":
            return len(df) >= 2 and _last(df, "close") < float(df["low"].iloc[-2]), label
        if element == "ao_positive":
            return _last(df, "ao") > 0, label
        if element == "ao_negative":
            return _last(df, "ao") < 0, label
        if element == "ao_rising":
            return ao_rising(df["ao"]), label
        if element == "ao_falling":
            return ao_falling(df["ao"]), label
        if element == "bbwp_regime":
            minimum = float(params.get("bbwp_regime_min", 50.0))
            return bbwp_regime_on(df["bbwp"], minimum=minimum), label
        if element == "vol_turn":
            source = cond.source or "bbwp"
            series = df[source] if source != "bbwp" else df["bbwp"]
            vt_params = _vol_turn_params_from(params)
            source_kind = "bbwp" if source == "bbwp" else "konkorde"
            if cond.variant in ("w_or_v_high", ""):
                return vol_turn_high(series, source=source_kind, params=vt_params), label
            if cond.variant == "v_high":
                return v_turn_high(series, source=source_kind, params=vt_params), label
            if cond.variant == "w_high":
                return w_turn_high(series, source=source_kind, params=vt_params), label
            raise ValueError(f"Unknown vol_turn variant: {cond.variant}")

        raise ValueError(f"Unknown condition element: {element}")


# ---------------------------------------------------------------------------
# False-entry vetoes (spec §B.3)
# ---------------------------------------------------------------------------

_EVENT_SERIES = {
    "konkorde_zero_cross_up": ("konkorde_marron", "up"),
    "konkorde_zero_cross_down": ("konkorde_marron", "down"),
    "ao_zero_cross_up": ("ao", "up"),
    "ao_zero_cross_down": ("ao", "down"),
}

_EVENT_STALE_REASON = {
    "konkorde_zero_cross_up": "stale_konkorde_cross",
    "konkorde_zero_cross_down": "stale_konkorde_cross",
    "ao_zero_cross_up": "stale_ao_cross",
    "ao_zero_cross_down": "stale_ao_cross",
}

# Trigger-condition label each veto event corresponds to, used to skip V1 when
# the event was an *optional* evidence path (trigger any_of) that was not the
# one satisfied — e.g. PB entered via ao_divergence keeps its own TTL and the
# konkorde-cross freshness veto must not fire (spec §B.3 veto table).
_EVENT_TRIGGER_LABEL = {
    "konkorde_zero_cross_up": "konkorde_zero_cross:up",
    "konkorde_zero_cross_down": "konkorde_zero_cross:down",
    "ao_zero_cross_up": "ao_zero_cross:up",
    "ao_zero_cross_down": "ao_zero_cross:down",
}


def evaluate_vetoes(
    vetoes: Sequence["VetoDefinition"],
    trigger_df: pd.DataFrame,
    *,
    band: str,
    satisfied_evidence: Optional[Sequence[str]] = None,
    optional_evidence: Optional[Sequence[str]] = None,
) -> Tuple[List[str], Optional[str]]:
    """Run the §B.3 vetoes on the trigger frame's last closed candle.

    Returns (veto_reasons, adx_turn_grade). The grade is the quality of the
    most recent confirming turn (V2), used by the backtest stratification.

    V1 (freshness) semantics: the veto fires when the event's most recent
    occurrence is older than `max_event_age`, or when the underlying state is
    on the event's side but no cross is found within the searchable window
    (the cross is then older than everything we can see — stale by
    definition). Konkorde events never veto in low_tf (spec §B.3 band note).
    """
    reasons: List[str] = []
    grade: Optional[str] = None
    optional = set(optional_evidence or ())
    satisfied = set(satisfied_evidence or ())
    for veto in vetoes:
        if veto.veto == "freshness":
            event = veto.event
            if band == "low_tf" and event in _KONKORDE_EVENTS:
                continue
            label = _EVENT_TRIGGER_LABEL.get(event, "")
            if label in optional and label not in satisfied:
                continue  # a different evidence path fired; V1 does not apply
            column, direction = _EVENT_SERIES[event]
            series = trigger_df[column]
            age = zero_cross_age(series, direction=direction, confirm_bars=1)
            if age is None:
                # No cross in-window: stale only if the state is already on
                # that side (the cross happened before our window).
                state_on = (
                    float(series.dropna().iloc[-1]) > 0
                    if direction == "up"
                    else float(series.dropna().iloc[-1]) < 0
                ) if len(series.dropna()) else False
                if state_on:
                    reasons.append(_EVENT_STALE_REASON[event])
            elif age > veto.max_event_age:
                reasons.append(_EVENT_STALE_REASON[event])
        elif veto.veto == "adx_confirmation":
            fire = adx_turn_fired_within(
                trigger_df["adx14"],
                trigger_df.get("plus_di"),
                trigger_df.get("minus_di"),
                variant=veto.variant,
                window=veto.confirm_window,
                params=_adx_params_from(dict(veto.params)),
            )
            if fire is None:
                reasons.append("no_adx_turn_confirmation")
            else:
                grade = fire.grade
        else:
            raise ValueError(f"Unknown veto type: {veto.veto}")
    return reasons, grade


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _last(df: pd.DataFrame, column: str) -> float:
    series = df[column].dropna()
    if series.empty:
        return float("nan")
    return float(series.iloc[-1])


def _adx_params_from(params: Mapping[str, Any]) -> AdxTurnParams:
    keys = {f.name for f in AdxTurnParams.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    overrides = {k: v for k, v in params.items() if k in keys}
    return AdxTurnParams(**{**ADX_TURN_DEFAULTS.__dict__, **overrides}) if overrides else ADX_TURN_DEFAULTS


def _divergence_params_from(params: Mapping[str, Any]) -> DivergenceParams:
    keys = {f.name for f in DivergenceParams.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    overrides = {k: v for k, v in params.items() if k in keys}
    return DivergenceParams(**{**DIVERGENCE_DEFAULTS.__dict__, **overrides}) if overrides else DIVERGENCE_DEFAULTS


def _vol_turn_params_from(params: Mapping[str, Any]) -> VolTurnParams:
    keys = {f.name for f in VolTurnParams.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    overrides = {k: v for k, v in params.items() if k in keys}
    return VolTurnParams(**{**VOL_TURN_DEFAULTS.__dict__, **overrides}) if overrides else VOL_TURN_DEFAULTS
