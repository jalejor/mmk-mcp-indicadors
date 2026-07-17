"""Rule pack v0.2.x — CANDIDATE rules behind the RULE_VERSION gate (spec §I).

Pure functions over pandas Series/DataFrames of CLOSED candles implementing:

* M1.1 `color_flip` early false-entry adjudication (spec §I.1): extends the
  §B.3.1 machine with the `FALSE_ENTRY_CONFIRMED` terminal state (p_false 0.70).
* M2 `contrary_impulse` (spec §I.2): the contrary move a false entry predicts.
  Evidence only, NO call-grade (council 2026-07-17, spec §I.2 v0.2.1 note).
* H1 hierarchy (spec §I.3 + addendum B.3.3): Rule 1 `CONFIRMED_BY_HIGHER_TF`
  override (freshness-bounded, see monitors_v020) and Rule 2 `vol_turn_rounded`
  p_false boost (addends ZEROED pending Q19 — see `VT_ROUNDED_ADDEND`).
* E4.1 `vol_turn_rounded` (spec §I.4): rounded volatility rollover, V and W.
* C1 3-TF full-alignment confluence (spec §I.5 + addendum B.4.1 micro window).
  Evidence only under v0.2.1: entry-call OFF, exit degraded (spec §I.5 note).
* M1m ADX-anchored false-ignition monitor for the micro band (addendum B.3.5).

NOTHING in this module runs unless the engine is instantiated with
rule_version "0.2.0" or "0.2.1" (`RULE_VERSION` env, default "0.1.0") — the
v0.1.0 behaviour stays byte-identical. Both 0.2.x labels execute this SAME
code: 0.2.1 = 0.2.0 + the H1 freshness fix (P0) + the measured priors below;
0.2.0-as-shipped is obsolete and kept only as a replay label (spec §I.9).

Every parameter default below is the versioned rule data of 0.2.1 (checked
into the repo, never env vars — spec §0.4); changing any of them is a
rule_version bump. Priors are MEASURED data as of the 120d replay of
2026-07-16 (BTC/ETH/SOL/BNB, immutable manifest) — provenance is noted on
each value.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

import pandas as pd

from .setup_service import (
    FE_CONFIRMED,
    FE_FALSE_ENTRY_PROBABLE,
    FE_WATCHING,
    FE_WHIPSAW,
    _FE_DIRECTION,
    _ao_consecutive_run_after,
    AdxTurnFire,
    adx_turn_fired_between,
    adx_turn_fired_within,
    fractal_pivots,
    zero_cross_age,
)

# ---------------------------------------------------------------------------
# Shared v0.2.0 vocabulary
# ---------------------------------------------------------------------------

# Operative TF ladder for v0.2.0 (spec §I preamble + addendum 0.3.1): 15m
# formally joins as Snipper sub-structure (monitor input only, never pushed).
LADDER_V020 = ("15m", "30m", "1h", "4h", "1d", "1w")

# One-band-up map (spec §I.2 band_up_map + addendum B.3.3 downward extension).
BAND_UP_MAP = {"15m": "30m", "30m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}

# §H profiles: alert priority / call grade per operating TF.
PROFILE_BY_TF = {
    "15m": "snipper", "30m": "snipper", "1h": "snipper",
    "4h": "pro", "1d": "ancient", "1w": "ancient",
}

# New terminal states layered onto the §B.3.1 machine.
FE_FALSE_ENTRY_CONFIRMED = "FALSE_ENTRY_CONFIRMED"          # M1.1 (spec §I.1)
FE_CONFIRMED_BY_HIGHER_TF = "CONFIRMED_BY_HIGHER_TF"        # H1 Rule 1 (spec §I.3)

# DI color aligned with a cross direction (spec §I.1 directional table).
_ALIGNED_COLOR = {"up": "bullish", "down": "bearish"}
_FLIP_COLOR = {"up": "bearish", "down": "bullish"}


def di_color_at(
    plus_di: Optional[pd.Series], minus_di: Optional[pd.Series], *, age: int = 0
) -> Optional[str]:
    """The §I.1 DI-color primitive at `age` closed candles from the end.

    "bullish" iff plus_di > minus_di, "bearish" iff minus_di > plus_di,
    None on tie/NaN/missing data (a tie never counts as a flip). Assumes the
    NaNs of both series live at the head only (warmup), like every other
    right-aligned age computation in setup_service.
    """
    if plus_di is None or minus_di is None:
        return None
    p = plus_di.dropna()
    m = minus_di.dropna()
    if len(p) <= age or len(m) <= age:
        return None
    pv = float(p.iloc[-1 - age])
    mv = float(m.iloc[-1 - age])
    if pv > mv:
        return "bullish"
    if mv > pv:
        return "bearish"
    return None


# ---------------------------------------------------------------------------
# M1.1 — color_flip adjudication (spec §I.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FalseEntryV2Params:
    """§B.3.1 params + the §I.1 color-flip extension."""

    confirm_candles: int = 5
    early_warning_candles: int = 2
    # MEASURED (replay 120d 2026-07-16, n=648 timeout adjudications): contrary
    # hit-rate of the timeout subset is 38%, and 73% of timeouts sat on a real
    # >= 1 ATR impulse — the owner prior 0.70 did not survive. v0.2.1 data.
    p_false_prior: float = 0.40
    confirm_bars: int = 1
    resolution_horizon: int = 10
    color_min_age: int = 2       # earliest post-cross age a flip adjudicates
    color_max_age: int = 4       # latest; above this the age-5 timeout governs
    # MEASURED (replay 120d 2026-07-16, n=243 FEC adjudications): contrary
    # hit-rate 70.0% (IS 71.6% / OOS 64.2%), replacing the owner prior 0.80.
    p_false_color: float = 0.70


FALSE_ENTRY_V2_DEFAULTS = FalseEntryV2Params()


@dataclass(frozen=True)
class FalseEntryStateV2:
    state: Optional[str]
    direction: str
    early_warning: bool
    event_age: Optional[int]
    consecutive_ao_candles: int
    adx_turn: Optional[Dict[str, Any]]
    whipsaw_age: Optional[int]
    p_false: Optional[float]
    color_flip_age: Optional[int]  # post-cross age the flip adjudicated at


def _color_flip_age(
    adx14: Optional[pd.Series],
    plus_di: Optional[pd.Series],
    minus_di: Optional[pd.Series],
    *,
    cross_age: int,
    direction: str,
    adx_variant: str,
    params: FalseEntryV2Params,
) -> Optional[int]:
    """Earliest post-cross age in [color_min_age, color_max_age] where the DI
    color flipped against the cross with no favorable turn in [t0, t0+a].

    Returns None when the color was already contrary at the cross candle t0
    (never aligned — no "flip" semantics, spec §I.1) or no qualifying flip.
    """
    flip = _FLIP_COLOR[direction]
    if di_color_at(plus_di, minus_di, age=cross_age) == flip:
        return None
    upper = min(params.color_max_age, cross_age)
    for post_age in range(params.color_min_age, upper + 1):
        age = cross_age - post_age
        if di_color_at(plus_di, minus_di, age=age) != flip:
            continue
        turn = None
        if adx14 is not None:
            turn = adx_turn_fired_between(
                adx14, plus_di, minus_di,
                variant=adx_variant, age_lo=age, age_hi=cross_age,
            )
        if turn is None:
            return post_age
    return None


def false_entry_state_v2(
    ao: pd.Series,
    adx14: Optional[pd.Series] = None,
    plus_di: Optional[pd.Series] = None,
    minus_di: Optional[pd.Series] = None,
    *,
    direction: str = "up",
    params: FalseEntryV2Params = FALSE_ENTRY_V2_DEFAULTS,
) -> FalseEntryStateV2:
    """§B.3.1 machine + the §I.1 color-flip terminal state, stateless.

    Precedence (spec §I.1): a favorable turn in [t0, t0+confirm_candles]
    still wins (CONFIRMED); else the earlier of {AO re-cross, color flip}
    resolves the watch — a re-cross BEFORE the flip is a WHIPSAW, a flip
    first adjudicates FALSE_ENTRY_CONFIRMED (a later re-cross is then the
    fulfilled prediction, not a whipsaw). Tie (same candle) -> WHIPSAW
    (implementation decision: the AO is already back across zero, the watch
    resolved itself). Then the ordinary age-5 timeout, then WATCHING.
    """
    if direction not in _FE_DIRECTION:
        raise ValueError(f"Unknown false_entry direction: {direction}")
    cross_dir, opposite_dir, adx_variant, ao_kind = _FE_DIRECTION[direction]

    ao_clean = ao.dropna()
    cross_age = zero_cross_age(ao_clean, direction=cross_dir, confirm_bars=params.confirm_bars)
    if cross_age is None:
        return FalseEntryStateV2(
            state=None, direction=direction, early_warning=False, event_age=None,
            consecutive_ao_candles=0, adx_turn=None, whipsaw_age=None,
            p_false=None, color_flip_age=None,
        )

    turn: Optional[AdxTurnFire] = None
    if adx14 is not None:
        turn = adx_turn_fired_between(
            adx14, plus_di, minus_di,
            variant=adx_variant,
            age_lo=cross_age - params.confirm_candles,
            age_hi=cross_age,
        )
    adx_turn_payload = (
        {"fired": True, "age": turn.age, "grade": turn.grade} if turn is not None else None
    )

    opposite_age = zero_cross_age(ao_clean, direction=opposite_dir, confirm_bars=params.confirm_bars)
    recrossed = opposite_age is not None and opposite_age < cross_age
    whipsaw_age = opposite_age if recrossed else None
    recross_post_age = (cross_age - opposite_age) if recrossed else None

    flip_age: Optional[int] = None
    if turn is None:
        flip_age = _color_flip_age(
            adx14, plus_di, minus_di,
            cross_age=cross_age, direction=direction,
            adx_variant=adx_variant, params=params,
        )

    run = _ao_consecutive_run_after(ao_clean, cross_age, kind=ao_kind)
    state, early, p_false = _resolve_v2_state(
        turn=turn, flip_age=flip_age, recross_post_age=recross_post_age,
        cross_age=cross_age, run=run, params=params,
    )
    if state != FE_FALSE_ENTRY_CONFIRMED:
        flip_age = None  # the flip only adjudicated if it won the race

    return FalseEntryStateV2(
        state=state,
        direction=direction,
        early_warning=early,
        event_age=cross_age,
        consecutive_ao_candles=run,
        adx_turn=adx_turn_payload,
        whipsaw_age=whipsaw_age,
        p_false=p_false,
        color_flip_age=flip_age,
    )


def _resolve_v2_state(
    *,
    turn: Optional[AdxTurnFire],
    flip_age: Optional[int],
    recross_post_age: Optional[int],
    cross_age: int,
    run: int,
    params: FalseEntryV2Params,
) -> tuple:
    if turn is not None:
        return FE_CONFIRMED, False, None
    flip_wins = flip_age is not None and (
        recross_post_age is None or flip_age < recross_post_age
    )
    if flip_wins:
        return FE_FALSE_ENTRY_CONFIRMED, False, params.p_false_color
    if recross_post_age is not None and recross_post_age < params.confirm_candles:
        return FE_WHIPSAW, False, None
    if cross_age >= params.confirm_candles:
        return FE_FALSE_ENTRY_PROBABLE, False, params.p_false_prior
    return FE_WATCHING, run >= params.early_warning_candles, None


# ---------------------------------------------------------------------------
# E4.1 — vol_turn_rounded (spec §I.4)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VolTurnRoundedParams:
    window: int = 8              # trailing closed bars scanned for the peak
    high_zone: float = 70.0      # gated on Q19 (engine BBWP, BB20/252, Bitget)
    min_drop_cum: float = 10.0   # cumulative BBWP points off the window max
    w_window: int = 12           # max bars spanning the two zone tests
    w_separation_min: int = 3
    tolerance: float = 5.0       # 2nd test may not exceed the 1st by more
    min_trough_depth: float = 5.0  # inherited from §E4 W geometry (spec silent)


VOL_TURN_ROUNDED_DEFAULTS = VolTurnRoundedParams()


def v_turn_rounded_high(
    x: pd.Series, *, params: VolTurnRoundedParams = VOL_TURN_ROUNDED_DEFAULTS
) -> bool:
    """Rounded (domed) rollover from the high zone, V variant (spec §I.4).

    Drop is cumulative from the trailing-window max (not a single-candle
    fall off an exact peak), so the real 90 -> ... -> 49 domes fire.
    """
    values = x.dropna()
    if len(values) < 3:
        return False
    window = values.iloc[-params.window:]
    peak = float(window.max())
    last = float(values.iloc[-1])
    prev = float(values.iloc[-2])
    prev2 = float(values.iloc[-3])
    peaked_high = peak >= params.high_zone
    dropped = (peak - last) >= params.min_drop_cum
    falling = last < prev < prev2
    return peaked_high and dropped and falling


def w_turn_rounded_high(
    x: pd.Series, *, params: VolTurnRoundedParams = VOL_TURN_ROUNDED_DEFAULTS
) -> bool:
    """Rounded double test of the high zone, W variant (spec §I.4).

    Implementation decisions (the spec defines the W variant loosely):
    pivot highs (strength 1, confirmed) stand in for the "zone tests"; the
    second test must not exceed the first by more than `tolerance` but MAY
    sit well below it (that IS the rounded rollover); a real trough of
    `min_trough_depth` (inherited from §E4) must separate the tests; and the
    last close must be falling (the turn is in progress).
    """
    values = x.dropna()
    last = len(values) - 1
    if last < 4 or not float(values.iloc[-1]) < float(values.iloc[-2]):
        return False
    window_start = max(0, last - params.w_window)
    pivots = [p for p in fractal_pivots(values, 1, "high") if p >= window_start]
    for p2 in reversed(pivots):
        x2 = float(values.iloc[p2])
        if x2 < params.high_zone:
            continue
        for p1 in reversed([p for p in pivots if p < p2]):
            distance = p2 - p1
            if distance < params.w_separation_min or distance > params.w_window:
                continue
            x1 = float(values.iloc[p1])
            if x1 < params.high_zone or (x2 - x1) > params.tolerance:
                continue
            trough = float(values.iloc[p1 + 1: p2].min())
            if min(x1, x2) - trough >= params.min_trough_depth:
                return True
    return False


def vol_turn_rounded_variant(
    x: pd.Series, *, params: VolTurnRoundedParams = VOL_TURN_ROUNDED_DEFAULTS
) -> Optional[str]:
    """"v" / "w" when a rounded high-zone rollover is active, else None."""
    if v_turn_rounded_high(x, params=params):
        return "v"
    if w_turn_rounded_high(x, params=params):
        return "w"
    return None


# ---------------------------------------------------------------------------
# H1 — hierarchy override + p_false boost (spec §I.3, addendum B.3.3)
# ---------------------------------------------------------------------------

P_FALSE_CAP = 0.90

# Rule-2 addends per vol_turn_rounded TF. The 1h row (addendum B.3.3) boosts
# micro-band watches only; the >=4h rows apply to every lower-TF watch.
# ZEROED for v0.2.1 (council 2026-07-17): the engine BBWP is uncalibrated vs
# the owner's TradingView read (Q19, two load-bearing cases), so the boosts
# are suspended — the wiring still emits boost entries (addend 0.0) and E4.1
# keeps emitting as evidence (it was never alertable). Recalibration pending
# on `bbwp_owner` post-Q19; the 0.2.0 constants are preserved here for it:
# {"1h": 0.05, "4h": 0.10, "1d": 0.15, "1w": 0.20}.
VT_ROUNDED_ADDEND = {"1h": 0.0, "4h": 0.0, "1d": 0.0, "1w": 0.0}
_VT_1H_BOOST_TARGETS = ("15m", "30m")


def higher_confirmed_source(
    timeframe: str,
    direction: str,
    confirmed_dirs_by_tf: Mapping[str, Sequence[str]],
) -> Optional[str]:
    """H1 Rule 1: nearest TF above `timeframe` with a same-direction CONFIRMED.

    Implementation decision: the whole ladder above is consulted (nearest
    confirming TF wins), which subsumes the spec's one-band-up wording and the
    addendum's "30m OR 1h" rule for 15m — e.g. a 30m watch is protected by a
    4h CONFIRMED even when the 1h watch itself timed out (the 2026-07-13
    golden: 30m AND 1h must both resolve CONFIRMED_BY_HIGHER_TF off the 4h).
    """
    if timeframe not in LADDER_V020:
        return None
    idx = LADDER_V020.index(timeframe)
    for tf in LADDER_V020[idx + 1:]:
        if direction in confirmed_dirs_by_tf.get(tf, ()):
            return tf
    return None


def p_false_boosts(
    timeframe: str,
    direction: str,
    vol_turn_moves: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """H1 Rule 2 addends for one adjudicated watch.

    `vol_turn_moves` maps TF -> move direction ("up"/"down", from the DI color
    on that TF) for TFs with an ACTIVE `vol_turn_rounded`. A rollover implies
    a retracement of that TF's move, so it boosts p_false on LOWER-TF watches
    whose direction EQUALS the move (they oppose the implied retracement).
    Never a standalone vote; never overrides Rule 1 (enforced by the caller
    applying Rule 1 first).
    """
    if timeframe not in LADDER_V020:
        return []
    idx = LADDER_V020.index(timeframe)
    boosts: List[Dict[str, Any]] = []
    for tf in LADDER_V020[idx + 1:]:
        move = vol_turn_moves.get(tf)
        if move is None or move != direction:
            continue
        addend = VT_ROUNDED_ADDEND.get(tf)
        if addend is None:
            continue
        if tf == "1h" and timeframe not in _VT_1H_BOOST_TARGETS:
            continue
        boosts.append({"source_tf": tf, "addend": addend})
    return boosts


def boosted_p_false(base: float, boosts: Sequence[Mapping[str, Any]]) -> float:
    """Apply Rule-2 addends to a base p_false, capped at P_FALSE_CAP.

    Rounded to 4 decimals so the API never emits float-noise (0.7999999...).
    """
    if not boosts:
        return base
    total = base + sum(float(b["addend"]) for b in boosts)
    return round(min(P_FALSE_CAP, total), 4)


# ---------------------------------------------------------------------------
# M2 — contrary_impulse (spec §I.2)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContraryImpulseParams:
    k_contrary: int = 5  # closed candles after the adjudication


CONTRARY_IMPULSE_DEFAULTS = ContraryImpulseParams()


@dataclass(frozen=True)
class ContraryImpulse:
    trigger: str            # "contrary_adx_turn" | "higher_tf_confirmed" | "ao_recross_color"
    confirmation_age: int   # closed candles since the confirming event
    detail: Dict[str, Any]


def contrary_impulse(
    ao: Optional[pd.Series],
    adx14: Optional[pd.Series],
    plus_di: Optional[pd.Series],
    minus_di: Optional[pd.Series],
    *,
    direction: str,
    adjudication_age: int,
    higher_confirmed_ages: Optional[Mapping[str, Optional[int]]] = None,
    params: ContraryImpulseParams = CONTRARY_IMPULSE_DEFAULTS,
) -> Optional[ContraryImpulse]:
    """Contrary-impulse confirmation within k candles of a FALSE_* adjudication.

    `direction` is the ADJUDICATED cross direction; the predicted contrary
    move is its opposite. `higher_confirmed_ages` maps source TF (same TF or
    one band up, spec trigger b) -> the age its contrary CONFIRMED fired at.
    The window is inclusive of the adjudication candle itself.
    """
    contrary_dir = "down" if direction == "up" else "up"
    contrary_variant = "up_bearish" if contrary_dir == "down" else "up_bullish"
    age_lo = max(0, adjudication_age - params.k_contrary)

    if adx14 is not None:  # (a) contrary adx_turn, same TF
        turn = adx_turn_fired_between(
            adx14, plus_di, minus_di,
            variant=contrary_variant, age_lo=age_lo, age_hi=adjudication_age,
        )
        if turn is not None:
            return ContraryImpulse("contrary_adx_turn", turn.age, {"grade": turn.grade})

    for source_tf, age in (higher_confirmed_ages or {}).items():  # (b)
        if age is not None and age_lo <= age <= adjudication_age:
            return ContraryImpulse("higher_tf_confirmed", age, {"source_tf": source_tf})

    if ao is not None:  # (c) AO re-cross with the DI color already contrary
        recross_age = zero_cross_age(ao.dropna(), direction=contrary_dir, confirm_bars=1)
        if recross_age is not None and age_lo <= recross_age <= adjudication_age:
            if di_color_at(plus_di, minus_di, age=recross_age) == _ALIGNED_COLOR[contrary_dir]:
                return ContraryImpulse("ao_recross_color", recross_age, {})
    return None


# ---------------------------------------------------------------------------
# M1m — ADX-anchored false-ignition monitor (addendum B.3.5, micro band)
# ---------------------------------------------------------------------------

FI_WATCHING = "WATCHING"
FI_CONFIRMED = "CONFIRMED"
FI_FALSE_IGNITION_PROBABLE = "FALSE_IGNITION_PROBABLE"
FI_WHIPSAW = "WHIPSAW"


@dataclass(frozen=True)
class FalseIgnitionParams:
    confirm_candles: int = 8       # 15m default (2h wall clock); 6 on 30m shadow
    # MEASURED (replay 120d 2026-07-16, n=57 FI-probable, interpool): price
    # hit-rate 42.1%, replacing the 0.65 provisional prior (Q21). NOTE: n=57
    # gives a WIDE confidence interval — recalibrate as forward data accrues.
    p_false_ignition: float = 0.42
    bbwp_rising_closes: int = 3
    scan_window: int = 14          # t0 lookback: confirm_candles + terminal visibility


FALSE_IGNITION_15M = FalseIgnitionParams()
FALSE_IGNITION_30M_SHADOW = FalseIgnitionParams(confirm_candles=6, scan_window=12)

_FI_VARIANT = {"up": "up_bullish", "down": "up_bearish"}


@dataclass(frozen=True)
class FalseIgnitionState:
    state: Optional[str]
    direction: str
    t0_age: Optional[int]
    adx_turn: Optional[Dict[str, Any]]
    confirmed_by: Optional[str]    # "ao_cross" | "bbwp_di"
    follow_age: Optional[int]      # closed candles AFTER t0 the body arrived
    whipsaw_age: Optional[int]
    p_false_ignition: Optional[float]


def _ao_follow_age(ao: Optional[pd.Series], *, direction: str, t0_age: int, confirm: int) -> Optional[int]:
    """Age of an AO zero-cross in `direction` inside [t0, t0+confirm]."""
    if ao is None:
        return None
    cross_age = zero_cross_age(ao.dropna(), direction=direction, confirm_bars=1)
    if cross_age is None or cross_age > t0_age or (t0_age - cross_age) > confirm:
        return None
    return cross_age


def _bbwp_di_follow_age(
    bbwp: Optional[pd.Series],
    plus_di: Optional[pd.Series],
    minus_di: Optional[pd.Series],
    *,
    direction: str,
    t0_age: int,
    params: FalseIgnitionParams,
) -> Optional[int]:
    """Age of the earliest post-t0 candle closing a run of `bbwp_rising_closes`
    strictly rising BBWP closes with the DI color = direction throughout."""
    if bbwp is None:
        return None
    values = bbwp.dropna()
    color = _ALIGNED_COLOR[direction]
    lo = max(0, t0_age - params.confirm_candles)
    for age in range(t0_age - 1, lo - 1, -1):  # earliest post-t0 candle first
        span = params.bbwp_rising_closes
        if len(values) <= age + span - 1:
            continue
        closes = [float(values.iloc[-1 - age - k]) for k in range(span)]  # newest first
        if not all(closes[k] > closes[k + 1] for k in range(span - 1)):
            continue
        if all(di_color_at(plus_di, minus_di, age=age + k) == color for k in range(span)):
            return age
    return None


def _fi_whipsaw_age(
    adx14: Optional[pd.Series],
    plus_di: Optional[pd.Series],
    minus_di: Optional[pd.Series],
    *,
    direction: str,
    t0_age: int,
    params: FalseIgnitionParams,
) -> Optional[int]:
    """Age of an opposite E1 turn or DI color flip against `direction`, post-t0."""
    opposite = "down" if direction == "up" else "up"
    lo = max(0, t0_age - params.confirm_candles)
    if adx14 is not None and t0_age > 0:
        turn = adx_turn_fired_between(
            adx14, plus_di, minus_di,
            variant=_FI_VARIANT[opposite], age_lo=lo, age_hi=t0_age - 1,
        )
        if turn is not None:
            return turn.age
    flip = _FLIP_COLOR[direction]
    for age in range(t0_age - 1, lo - 1, -1):
        if di_color_at(plus_di, minus_di, age=age) == flip:
            return age
    return None


def false_ignition_state(
    ao: Optional[pd.Series],
    adx14: pd.Series,
    plus_di: Optional[pd.Series] = None,
    minus_di: Optional[pd.Series] = None,
    bbwp: Optional[pd.Series] = None,
    *,
    direction: str = "up",
    params: FalseIgnitionParams = FALSE_IGNITION_15M,
) -> FalseIgnitionState:
    """M1m: strength ignited (E1 turn = t0) — does the move get body behind it?

    CONFIRMED: within `confirm_candles` after t0, AO crosses zero in the turn
    direction OR BBWP rises `bbwp_rising_closes` consecutive closes with the
    DI color matching throughout. WHIPSAW: opposite E1 turn or DI color flip
    against the direction before adjudication. FALSE_IGNITION_PROBABLE: the
    window elapses with neither. Confirmation wins over a whipsaw (mirror of
    the M1 precedence: a real impulse overrides).
    """
    if direction not in _FI_VARIANT:
        raise ValueError(f"Unknown false_ignition direction: {direction}")
    fire = adx_turn_fired_within(
        adx14, plus_di, minus_di,
        variant=_FI_VARIANT[direction], window=params.scan_window,
    )
    if fire is None:
        return FalseIgnitionState(
            state=None, direction=direction, t0_age=None, adx_turn=None,
            confirmed_by=None, follow_age=None, whipsaw_age=None, p_false_ignition=None,
        )
    t0_age = fire.age
    turn_payload = {"fired": True, "age": t0_age, "grade": fire.grade,
                    "origin_level": fire.origin_level}

    ao_age = _ao_follow_age(ao, direction=direction, t0_age=t0_age,
                            confirm=params.confirm_candles)
    bbwp_age = None
    if ao_age is None:
        bbwp_age = _bbwp_di_follow_age(
            bbwp, plus_di, minus_di, direction=direction, t0_age=t0_age, params=params,
        )
    whipsaw_age = _fi_whipsaw_age(
        adx14, plus_di, minus_di, direction=direction, t0_age=t0_age, params=params,
    )

    if ao_age is not None or bbwp_age is not None:
        event_age = ao_age if ao_age is not None else bbwp_age
        follow_age = t0_age - event_age  # candles after t0 (spec M1m-G1)
        confirmed_by = "ao_cross" if ao_age is not None else "bbwp_di"
        state: Optional[str] = FI_CONFIRMED
        p_false = None
    elif whipsaw_age is not None:
        follow_age, confirmed_by, state, p_false = None, None, FI_WHIPSAW, None
    elif t0_age >= params.confirm_candles:
        follow_age, confirmed_by = None, None
        state, p_false = FI_FALSE_IGNITION_PROBABLE, params.p_false_ignition
    else:
        follow_age, confirmed_by, state, p_false = None, None, FI_WATCHING, None

    return FalseIgnitionState(
        state=state, direction=direction, t0_age=t0_age, adx_turn=turn_payload,
        confirmed_by=confirmed_by, follow_age=follow_age,
        whipsaw_age=whipsaw_age if state == FI_WHIPSAW else None,
        p_false_ignition=p_false,
    )


# ---------------------------------------------------------------------------
# C1 — 3-TF full-alignment confluence (spec §I.5, addendum B.4.1)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConfluenceParams:
    adx_fresh_max_age: int = 5     # E1 turn freshness (event_age <= 5)
    bbwp_expansion_bars: int = 2   # rising-BBWP alternative to > 50
    bbwp_regime_min: float = 50.0
    exit_priority: int = 5         # "SALIDA por confluencia contraria"
    enable_mid_window: bool = False  # Q18 {1h,4h,1d} — owner decision, OFF


CONFLUENCE_DEFAULTS = ConfluenceParams()

# direction -> (favorable E1 variant, DI color, sign)
_C1_DIRECTION = {"bull": ("up_bullish", "bullish", 1.0), "bear": ("up_bearish", "bearish", -1.0)}

# Micro-band within-TF validity weights (addendum 0.3.1): ADX 45 / VOL 40 / AO 15.
_MICRO_WEIGHTS = {"adx": 45, "bbwp": 40, "ao": 15}

# The v0.2.0 confluence windows. Per-TF alignment mode: "micro" (ADX+BBWP
# mandatory, AO bonus), "low" (3/3 incl. AO), "high" (4/4 incl. Konkorde).
# Annotations are product copy (Spanish, like RulesService explanations).
CONFLUENCE_WINDOWS = (
    {
        "window_id": "15m-30m-1h",
        "timeframes": ("15m", "30m", "1h"),
        "modes": {"15m": "micro", "30m": "micro", "1h": "low"},
        "profiles": ("snipper",),
        "annotation": "4h probablemente en retroceso",
        "companion_tf": "4h",
        "q18": False,
    },
    {
        "window_id": "30m-1h-4h",
        "timeframes": ("30m", "1h", "4h"),
        "modes": {"30m": "low", "1h": "low", "4h": "high"},
        "profiles": ("snipper", "pro"),
        "annotation": "1d probablemente en retroceso",
        "companion_tf": None,
        "q18": False,
    },
    {
        "window_id": "1h-4h-1d",
        "timeframes": ("1h", "4h", "1d"),
        "modes": {"1h": "low", "4h": "high", "1d": "high"},
        "profiles": ("snipper", "pro", "ancient"),
        "annotation": "1w probablemente en retroceso",
        "companion_tf": None,
        "q18": True,  # default OFF (Q18)
    },
    {
        "window_id": "4h-1d-1w",
        "timeframes": ("4h", "1d", "1w"),
        "modes": {"4h": "high", "1d": "high", "1w": "high"},
        "profiles": ("ancient",),
        "annotation": "1w probablemente en retroceso",
        "companion_tf": None,
        "q18": False,
    },
)


def _series_last(frame: pd.DataFrame, column: str) -> Optional[float]:
    if column not in frame:
        return None
    series = frame[column].dropna()
    if series.empty:
        return None
    return float(series.iloc[-1])


def _adx_component(frame: pd.DataFrame, *, variant: str, color: str, params: ConfluenceParams) -> bool:
    """Favorable E1 turn fresh (age <= adx_fresh_max_age) OR ADX rising with
    the DI color matching (strength building, §I.1 color)."""
    adx = frame.get("adx14")
    if adx is None:
        return False
    fire = adx_turn_fired_within(
        adx, frame.get("plus_di"), frame.get("minus_di"),
        variant=variant, window=params.adx_fresh_max_age + 1,
    )
    if fire is not None:
        return True
    values = adx.dropna()
    rising = len(values) >= 2 and float(values.iloc[-1]) > float(values.iloc[-2])
    return rising and di_color_at(frame.get("plus_di"), frame.get("minus_di")) == color


def _bbwp_component(frame: pd.DataFrame, *, params: ConfluenceParams) -> bool:
    """BBWP regime ON (> 50) OR rising `bbwp_expansion_bars` closed candles."""
    bbwp = frame.get("bbwp")
    if bbwp is None:
        return False
    values = bbwp.dropna()
    if values.empty:
        return False
    if float(values.iloc[-1]) > params.bbwp_regime_min:
        return True
    bars = params.bbwp_expansion_bars
    if len(values) < bars + 1:
        return False
    closes = [float(values.iloc[-1 - k]) for k in range(bars + 1)]  # newest first
    return all(closes[k] > closes[k + 1] for k in range(bars))


def confluence_alignment(
    frame: pd.DataFrame,
    *,
    direction: str,
    mode: str,
    params: ConfluenceParams = CONFLUENCE_DEFAULTS,
) -> Dict[str, Any]:
    """Per-TF alignment score for C1 (spec §I.5 / addendum B.4.1).

    mode "low": AO + ADX + BBWP all required (3/3). mode "high": + Konkorde
    (4/4). mode "micro": ADX + BBWP mandatory, AO is a validity bonus that
    never gates (score = 45/40/15 weights).
    """
    if direction not in _C1_DIRECTION:
        raise ValueError(f"Unknown confluence direction: {direction}")
    if mode not in ("micro", "low", "high"):
        raise ValueError(f"Unknown confluence mode: {mode}")
    variant, color, sign = _C1_DIRECTION[direction]

    ao_value = _series_last(frame, "ao")
    ao_ok = ao_value is not None and sign * ao_value > 0
    adx_ok = _adx_component(frame, variant=variant, color=color, params=params)
    bbwp_ok = _bbwp_component(frame, params=params)

    components: Dict[str, bool] = {"ao": ao_ok, "adx": adx_ok, "bbwp": bbwp_ok}
    score: Optional[int] = None
    if mode == "high":
        marron = _series_last(frame, "konkorde_marron")
        components["konkorde"] = marron is not None and sign * marron > 0
        aligned = all(components.values())
    elif mode == "low":
        aligned = ao_ok and adx_ok and bbwp_ok
    else:  # micro
        aligned = adx_ok and bbwp_ok
        score = sum(_MICRO_WEIGHTS[key] for key, ok in components.items() if ok)
    return {"aligned": aligned, "components": components, "score": score}


def evaluate_confluence(
    frames: Mapping[str, pd.DataFrame],
    *,
    params: ConfluenceParams = CONFLUENCE_DEFAULTS,
) -> List[Dict[str, Any]]:
    """Evaluate every enabled C1 window on the given per-TF frames.

    Emits one entry per (window, direction) fully aligned. Under v0.2.1 every
    entry is `evidence_only` (council 2026-07-17): the replay failed C1 as an
    entry-call (full alignment arrives late = exhaustion marker) and did not
    validate the P5 exit — the consumer (mmk-api journal) must not treat these
    as calls of any grade until the owner signs off (spec §I.5 v0.2.1 note).
    """
    entries: List[Dict[str, Any]] = []
    for window in CONFLUENCE_WINDOWS:
        if window["q18"] and not params.enable_mid_window:
            continue
        if any(tf not in frames for tf in window["timeframes"]):
            continue
        for direction in ("bull", "bear"):
            alignment = {
                tf: confluence_alignment(
                    frames[tf], direction=direction,
                    mode=window["modes"][tf], params=params,
                )
                for tf in window["timeframes"]
            }
            if not all(entry["aligned"] for entry in alignment.values()):
                continue
            companion_ok = None
            companion_tf = window["companion_tf"]
            if companion_tf is not None and companion_tf in frames:
                sign = _C1_DIRECTION[direction][2]
                companion_ao = _series_last(frames[companion_tf], "ao")
                companion_ok = companion_ao is not None and sign * companion_ao > 0
            entries.append(
                {
                    "window": list(window["timeframes"]),
                    "window_id": window["window_id"],
                    "direction": direction,
                    "profiles": list(window["profiles"]),
                    "annotation": window["annotation"],
                    "exit_priority": params.exit_priority,
                    "companion_ok": companion_ok,
                    "alignment": alignment,
                    # v0.2.1 (council 2026-07-17): C1 entry-call is OFF and the
                    # P5 exit is degraded to evidence (owner sign-off PENDING).
                    # The block keeps computing to gather forward evidence for
                    # the pre-registered v0.3.0 C1-FADE hypothesis (spec §I.9).
                    "evidence_only": True,
                }
            )
    return entries
