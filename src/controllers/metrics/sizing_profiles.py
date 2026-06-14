"""Single source of truth for risk-profile based position sizing.

Both the live recommender (`MovementsService`) and the backtest engine
(`BacktestService`) derive their stop distance and target distance from the
same `risk_profile`. Keeping these tables in one module guarantees that a
backtest validates exactly what the live service recommends: same
symbol + ATR + equity + risk_profile -> same stop/target/quantity.

* ATR_PROFILES: (atr_mult_stop, r_multiple_target) used by the ATR sizing path.
* RISK_PROFILES: (target_pct, stop_pct) used by the legacy percent-based path
  (live only, when `use_atr_sizing=False`).
"""

from __future__ import annotations

from typing import Dict, Literal, Tuple

RiskProfile = Literal["low", "medium", "high"]

# ATR-based profiles: (atr_mult_stop, r_multiple_target).
# `medium` is the default and MUST stay at (1.5, 3.0) — it matches the
# historical fixed defaults of the backtest engine, so existing behaviour and
# golden numbers for `medium` are preserved.
ATR_PROFILES: Dict[RiskProfile, Tuple[float, float]] = {
    "low": (1.0, 2.0),
    "medium": (1.5, 3.0),
    "high": (2.0, 4.0),
}

# Legacy fixed-percentage profiles: (target_pct, stop_pct). Used only by the
# live service when ATR sizing is disabled; the backtest engine never uses them.
RISK_PROFILES: Dict[RiskProfile, Tuple[float, float]] = {
    "low": (2.5, 1.5),
    "medium": (5.0, 3.0),
    "high": (10.0, 5.0),
}


def atr_sizing_for(risk_profile: str) -> Tuple[float, float]:
    """Return `(atr_mult_stop, r_multiple_target)` for the given risk profile.

    Raises ``ValueError`` for unsupported profiles so callers fail loudly
    instead of silently defaulting.
    """
    try:
        return ATR_PROFILES[risk_profile]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(f"Risk profile no soportado: {risk_profile}") from exc


def pct_sizing_for(risk_profile: str) -> Tuple[float, float]:
    """Return `(target_pct, stop_pct)` for the given risk profile."""
    try:
        return RISK_PROFILES[risk_profile]  # type: ignore[index]
    except KeyError as exc:
        raise ValueError(f"Risk profile no soportado: {risk_profile}") from exc
