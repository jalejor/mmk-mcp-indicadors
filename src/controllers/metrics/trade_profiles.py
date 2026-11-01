"""Trade profiles for the impulse engine (impulsos-v2) — single source of truth.

A profile binds a trigger timeframe to its confirmation/context timeframes and
to the risk envelope it may trade with (spec §H, "the wider the zoom, the lower
the leverage"). mmk-api mirrors these numbers: change them here first.

* ``trigger_tf``   — the timeframe whose CLOSED candle fires enter/exit.
* ``confirm_tf``   — the next timeframe up; must not contradict the side.
* ``context_tfs``  — wider timeframes; must not contradict the side either.
* ``max_leverage`` — ceiling for simulated/real leverage (sizing only, never
  signal logic — spec §H).
* ``default_leverage`` — leverage used unless the caller asks for more.
* ``margin_mode``  — ``"isolated"`` | ``"cross"`` | ``None`` (spot).
* ``risk_pct``     — % of equity lost on a full ATR stop-out.
* ``atr_mult_stop``— protective stop distance in ATR(14) of the trigger TF.
* ``r_target``     — fixed R target, ``None`` = exits are rule-driven.
* ``time_stop_bars`` — exit after N trigger bars held below +0.5 R.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

# Numbers from docs/impulsos-v2.md §f. `confirm_tf` is the guardian (first
# context TF, spec §F ladder): the only TF allowed to block an entry.
TRADE_PROFILES: Dict[str, Dict[str, Any]] = {
    "scalper": {
        "trigger_tf": "15m",
        "confirm_tf": "1h",
        "context_tfs": ("1h", "4h"),
        "max_leverage": 10.0,
        "default_leverage": 10.0,
        "margin_mode": "isolated",
        "risk_pct": 0.25,
        "atr_mult_stop": 2.0,
        "r_target": None,
        "time_stop_bars": 32,
    },
    "snipper": {
        "trigger_tf": "1h",
        "confirm_tf": "4h",
        "context_tfs": ("4h", "1d"),
        "max_leverage": 10.0,
        "default_leverage": 10.0,
        "margin_mode": "isolated",
        "risk_pct": 0.5,
        "atr_mult_stop": 1.5,
        "r_target": None,
        "time_stop_bars": 48,
    },
    "pro": {
        "trigger_tf": "4h",
        "confirm_tf": "1d",
        "context_tfs": ("1d", "1w"),
        "max_leverage": 5.0,
        "default_leverage": 5.0,
        "margin_mode": "isolated",  # mmk-api runs cross today; spec recommends isolated in paper
        "risk_pct": 0.75,
        "atr_mult_stop": 1.5,
        "r_target": None,
        "time_stop_bars": 30,
    },
    "ancient": {
        "trigger_tf": "1d",
        "confirm_tf": "1w",
        "context_tfs": ("1w", "1M"),
        "max_leverage": 2.0,
        "default_leverage": 1.0,  # spot longs 1x; 2x only after the live-tiny gate
        "margin_mode": "isolated",
        "risk_pct": 1.0,
        "atr_mult_stop": 2.0,
        "r_target": None,
        "time_stop_bars": 30,
    },
}

DEFAULT_PROFILE = "pro"


def get_trade_profile(name: str) -> Mapping[str, Any]:
    """Return the profile dict, raising ``ValueError`` (HTTP 400) if unknown."""
    try:
        return TRADE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown trade profile: {name!r} (use one of {sorted(TRADE_PROFILES)})"
        ) from exc


def profile_timeframes(name: str) -> tuple:
    """Unique timeframes a profile needs, trigger first, in evaluation order."""
    profile = get_trade_profile(name)
    ordered = [profile["trigger_tf"], profile["confirm_tf"], *profile["context_tfs"]]
    seen: list = []
    for tf in ordered:
        if tf not in seen:
            seen.append(tf)
    return tuple(seen)
