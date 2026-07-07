"""Declarative, versioned setup documents (spec §B, rule_version 0.1.0).

Setups are DATA (frozen dataclasses of plain values — never env vars). Any
threshold/window/condition change bumps `rule_version` (spec §0.4). The two
owner setups are declared long-side; the short variants are generated as
strict mirrors (owner decision Q8: mirror shorts from F0).

Owner decisions applied on top of the §B drafts (spec §E, 2026-07-06):
* Q10 — veto windows relaxed to 5 (max_event_age=5, confirm_window=5). The
  backtest still replays 3 vs 5 counterfactually.
* Q8 — shorts mirrored from F0.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Tuple

from .setup_service import (
    HIGH_TF_BAND,
    LOW_TF_BAND,
    SetupValidationError,
    _is_konkorde_condition,
)

RULE_VERSION = "0.1.0"

# Owner decision Q10 (spec §E): both veto windows relaxed from 3 to 5.
MAX_EVENT_AGE = 5
CONFIRM_WINDOW = 5


@dataclass(frozen=True)
class Condition:
    element: str
    variant: str = ""
    timeframe: str = ""  # empty = the owning block's timeframe
    source: str = ""  # vol_turn source series (bbwp / konkorde_marron / ...)
    params: Mapping[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        parts = [self.element]
        if self.variant:
            parts.append(self.variant)
        if self.source and self.source != "bbwp":
            parts.append(self.source)
        return ":".join(parts)


@dataclass(frozen=True)
class VetoDefinition:
    veto: str  # "freshness" | "adx_confirmation"
    event: str = ""  # freshness: konkorde_zero_cross_up / ao_zero_cross_up / mirrors
    variant: str = ""  # adx_confirmation: adx_turn variant
    max_event_age: int = MAX_EVENT_AGE
    confirm_window: int = CONFIRM_WINDOW
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SetupDefinition:
    rule_version: str
    setup_id: str
    side: str  # "long" | "short"
    timeframe_band: str  # "low_tf" | "high_tf"
    context_timeframe: str
    trigger_timeframe: str
    context_all_of: Tuple[Condition, ...] = ()
    context_any_of: Tuple[Condition, ...] = ()
    trigger_any_of: Tuple[Condition, ...] = ()  # evidence: at least one
    trigger_all_of: Tuple[Condition, ...] = ()
    invalidation_any_of: Tuple[Condition, ...] = ()
    vetoes: Tuple[VetoDefinition, ...] = ()
    risk_profile: str = "medium"

    def timeframes(self) -> Tuple[str, ...]:
        tfs = {self.context_timeframe, self.trigger_timeframe}
        for cond in (
            self.context_all_of
            + self.context_any_of
            + self.trigger_any_of
            + self.trigger_all_of
            + self.invalidation_any_of
        ):
            if cond.timeframe:
                tfs.add(cond.timeframe)
        return tuple(sorted(tfs))


# ---------------------------------------------------------------------------
# Load-time validation (spec §0.3 enforcement #1)
# ---------------------------------------------------------------------------

def validate_setup(setup: SetupDefinition) -> None:
    if setup.side not in ("long", "short"):
        raise SetupValidationError(f"{setup.setup_id}: invalid side {setup.side!r}")
    if setup.timeframe_band not in ("low_tf", "high_tf"):
        raise SetupValidationError(f"{setup.setup_id}: invalid band {setup.timeframe_band!r}")

    allowed = LOW_TF_BAND if setup.timeframe_band == "low_tf" else HIGH_TF_BAND
    for tf in setup.timeframes():
        if tf not in allowed:
            raise SetupValidationError(
                f"{setup.setup_id}: timeframe {tf!r} does not belong to band {setup.timeframe_band!r}"
            )

    if setup.timeframe_band == "low_tf":
        conditions = (
            setup.context_all_of
            + setup.context_any_of
            + setup.trigger_any_of
            + setup.trigger_all_of
            + setup.invalidation_any_of
        )
        for cond in conditions:
            if _is_konkorde_condition(cond.element, cond.source):
                raise SetupValidationError(
                    f"{setup.setup_id}: Konkorde element {cond.label()!r} is forbidden in low_tf"
                )
        for veto in setup.vetoes:
            if veto.event.startswith("konkorde"):
                raise SetupValidationError(
                    f"{setup.setup_id}: Konkorde veto event {veto.event!r} is forbidden in low_tf"
                )


# ---------------------------------------------------------------------------
# Strict mirror (owner decision Q8)
# ---------------------------------------------------------------------------

_MIRROR_ELEMENT = {
    ("close_above_sma200", ""): ("close_below_sma200", ""),
    ("close_below_sma200", ""): ("close_above_sma200", ""),
    ("ema50_above_sma50", ""): ("ema50_below_sma50", ""),
    ("ema50_below_sma50", ""): ("ema50_above_sma50", ""),
    ("adx_level", "bullish"): ("adx_level", "bearish"),
    ("adx_level", "bearish"): ("adx_level", "bullish"),
    ("adx_turn", "up_bullish"): ("adx_turn", "up_bearish"),
    ("adx_turn", "up_bearish"): ("adx_turn", "up_bullish"),
    ("adx_turn", "down"): ("adx_turn", "down"),  # strength collapse is side-agnostic
    ("konkorde_state", "positive"): ("konkorde_state", "negative"),
    ("konkorde_state", "negative"): ("konkorde_state", "positive"),
    ("konkorde_zero_cross", "up"): ("konkorde_zero_cross", "down"),
    ("konkorde_zero_cross", "down"): ("konkorde_zero_cross", "up"),
    ("ao_divergence", "bullish"): ("ao_divergence", "bearish"),
    ("ao_divergence", "bearish"): ("ao_divergence", "bullish"),
    ("pullback_state", ""): ("rally_state", ""),
    ("rally_state", ""): ("pullback_state", ""),
    ("close_breaks_prior_high", ""): ("close_breaks_prior_low", ""),
    ("close_breaks_prior_low", ""): ("close_breaks_prior_high", ""),
    ("ao_positive", ""): ("ao_negative", ""),
    ("ao_negative", ""): ("ao_positive", ""),
    ("ao_rising", ""): ("ao_falling", ""),
    ("ao_falling", ""): ("ao_rising", ""),
    ("bbwp_regime", ""): ("bbwp_regime", ""),  # regime filter is side-agnostic
    ("vol_turn", "w_or_v_high"): ("vol_turn", "w_or_v_high"),  # exhaustion is side-agnostic
}

_MIRROR_EVENT = {
    "konkorde_zero_cross_up": "konkorde_zero_cross_down",
    "konkorde_zero_cross_down": "konkorde_zero_cross_up",
    "ao_zero_cross_up": "ao_zero_cross_down",
    "ao_zero_cross_down": "ao_zero_cross_up",
}


def _mirror_condition(cond: Condition) -> Condition:
    key = (cond.element, cond.variant)
    if key not in _MIRROR_ELEMENT:
        raise SetupValidationError(f"No mirror defined for condition {cond.label()!r}")
    element, variant = _MIRROR_ELEMENT[key]
    return replace(cond, element=element, variant=variant)


def _mirror_veto(veto: VetoDefinition) -> VetoDefinition:
    if veto.veto == "freshness":
        return replace(veto, event=_MIRROR_EVENT[veto.event])
    if veto.veto == "adx_confirmation":
        variant = {"up_bullish": "up_bearish", "up_bearish": "up_bullish"}[veto.variant]
        return replace(veto, variant=variant)
    raise SetupValidationError(f"No mirror defined for veto {veto.veto!r}")


def mirror_setup(setup: SetupDefinition) -> SetupDefinition:
    """Strict mirror of every condition/veto; LONG <-> SHORT in the id."""
    side = "short" if setup.side == "long" else "long"
    suffix = "-SHORT" if side == "short" else "-LONG"
    base_id = setup.setup_id.rsplit("-", 1)[0]
    return replace(
        setup,
        setup_id=base_id + suffix,
        side=side,
        context_all_of=tuple(_mirror_condition(c) for c in setup.context_all_of),
        context_any_of=tuple(_mirror_condition(c) for c in setup.context_any_of),
        trigger_any_of=tuple(_mirror_condition(c) for c in setup.trigger_any_of),
        trigger_all_of=tuple(_mirror_condition(c) for c in setup.trigger_all_of),
        invalidation_any_of=tuple(_mirror_condition(c) for c in setup.invalidation_any_of),
        vetoes=tuple(_mirror_veto(v) for v in setup.vetoes),
    )


# ---------------------------------------------------------------------------
# SETUP PB-1D-LONG — pullback within trend (spec §B.1)
# ---------------------------------------------------------------------------

PB_1D_LONG = SetupDefinition(
    rule_version=RULE_VERSION,
    setup_id="PB-1D-LONG",
    side="long",
    timeframe_band="high_tf",
    context_timeframe="1d",
    trigger_timeframe="1d",
    context_all_of=(
        Condition("close_above_sma200"),  # structural uptrend
        Condition("ema50_above_sma50"),
        Condition("konkorde_state", "positive"),  # E3 state
        Condition("pullback_state", params={"pullback_window": 10}),
    ),
    context_any_of=(
        Condition("adx_level", "bullish"),  # adx >= 25 AND +DI dominant
        Condition("adx_turn", "up_bullish", params={"fired_within": 1}),  # E1 igniting
    ),
    trigger_any_of=(  # reversal evidence
        Condition("konkorde_zero_cross", "up", params={"confirm_bars": 1, "max_event_age": MAX_EVENT_AGE}),
        Condition("ao_divergence", "bullish", params={"active_within": 5}),
    ),
    trigger_all_of=(  # resumption
        Condition("close_breaks_prior_high"),
    ),
    invalidation_any_of=(
        Condition("close_below_sma200", timeframe="1d"),
        Condition("adx_turn", "down", timeframe="1d", params={"fired_within": 1}),
        Condition("vol_turn", "w_or_v_high", timeframe="1d", source="konkorde_marron"),
    ),
    vetoes=(
        VetoDefinition("freshness", event="konkorde_zero_cross_up", max_event_age=MAX_EVENT_AGE),
        VetoDefinition("adx_confirmation", variant="up_bullish", confirm_window=CONFIRM_WINDOW),
    ),
    risk_profile="medium",
)

# ---------------------------------------------------------------------------
# SETUP IMP-4H-LONG — 4h impulse in high volatility (spec §B.2)
# ---------------------------------------------------------------------------

IMP_4H_LONG = SetupDefinition(
    rule_version=RULE_VERSION,
    setup_id="IMP-4H-LONG",
    side="long",
    timeframe_band="high_tf",
    context_timeframe="4h",
    trigger_timeframe="4h",
    context_all_of=(
        Condition("bbwp_regime", params={"bbwp_regime_min": 50.0}),  # E5
        # E1 on 4h: fired within the confirm window (subsumed by veto V2).
        Condition("adx_turn", "up_bullish", params={"fired_within": CONFIRM_WINDOW}),
        Condition("close_above_sma200", timeframe="1d"),  # 1d must not oppose
    ),
    trigger_all_of=(
        Condition("konkorde_zero_cross", "up", params={"confirm_bars": 1, "max_event_age": MAX_EVENT_AGE}),
        Condition("ao_positive"),
        Condition("ao_rising"),  # E2 cheap convergence
    ),
    invalidation_any_of=(
        Condition("vol_turn", "w_or_v_high", timeframe="4h", source="bbwp"),
        Condition("konkorde_zero_cross", "down", timeframe="4h", params={"confirm_bars": 1, "max_event_age": 0}),
        Condition("adx_turn", "down", timeframe="4h", params={"fired_within": 1}),
    ),
    vetoes=(
        VetoDefinition("freshness", event="konkorde_zero_cross_up", max_event_age=MAX_EVENT_AGE),
        VetoDefinition("freshness", event="ao_zero_cross_up", max_event_age=MAX_EVENT_AGE),
        VetoDefinition("adx_confirmation", variant="up_bullish", confirm_window=CONFIRM_WINDOW),
    ),
    risk_profile="medium",
)

PB_1D_SHORT = mirror_setup(PB_1D_LONG)
IMP_4H_SHORT = mirror_setup(IMP_4H_LONG)

DEFAULT_SETUPS: Tuple[SetupDefinition, ...] = (
    PB_1D_LONG,
    PB_1D_SHORT,
    IMP_4H_LONG,
    IMP_4H_SHORT,
)

SETUPS_BY_ID = {setup.setup_id: setup for setup in DEFAULT_SETUPS}
