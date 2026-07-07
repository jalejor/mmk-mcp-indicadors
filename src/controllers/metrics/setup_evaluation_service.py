"""Live multi-TF setup evaluation for `GET /v1/setups/evaluate` (F0.5-API).

This service exposes the F0 engine over HTTP: it evaluates every declarative
setup (`setup_definitions.DEFAULT_SETUPS`) at the last CLOSED candle of each
timeframe (spec §0.1, `drop_forming=True`) and serialises the result with the
contract agreed with the frontend (symbol / rule_version / evaluated_at /
setups[] with per-condition breakdown, vetoes and evidence).

Design notes:
* The evaluation itself is `SetupService.evaluate_setup` — the exact same
  evaluator the F0 backtest replays. Nothing is re-implemented here; this
  module only loads data, aligns context frames (spec §0.2) and serialises.
* Raw candles are cached by `MarketDataService`'s TTL cache; the enriched
  (indicator-annotated) frame is additionally cached here keyed by
  `(exchange, symbol, timeframe, last_closed_candle_ts)` — the key is bound
  to the candle, so a cache hit can never serve a repainted value.
"""

from __future__ import annotations

import math
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

try:
    from cachetools import TTLCache
except Exception:  # pragma: no cover - cachetools is a hard runtime dep
    TTLCache = None  # type: ignore[assignment]

from .indicators_service import IndicatorsService
from .market_data_service import DEFAULT_EXCHANGE, MarketDataService
from .setup_definitions import Condition, SetupDefinition
from .setup_service import (
    TIMEFRAME_SECONDS,
    SetupEvaluation,
    SetupService,
    _EVENT_STALE_REASON,
)

# Same depth as /v1/metrics: enough warmup for sma200 and the Konkorde
# EMA(255)/rolling(90) stack while staying inside one ccxt page.
FETCH_LIMIT = 500


def _clean_float(value: Any) -> Optional[float]:
    """JSON-safe float: NaN/inf (invalid in strict JSON) become null."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _last(df: pd.DataFrame, column: str) -> Optional[float]:
    if column not in df:
        return None
    series = df[column].dropna()
    if series.empty:
        return None
    return _clean_float(series.iloc[-1])


class SetupEvaluationService:
    """Evaluates the declarative setups live and serialises the API contract."""

    # Enriched-frame cache. Keys embed the last closed candle timestamp, so
    # entries can never go stale — the TTL only bounds memory/eviction.
    _CACHE: Optional["TTLCache"] = (
        TTLCache(maxsize=64, ttl=4 * 60 * 60) if TTLCache is not None else None
    )
    _CACHE_LOCK = threading.Lock()

    def __init__(
        self,
        *,
        symbol: str,
        exchange: str = DEFAULT_EXCHANGE,
        setups: Optional[Sequence[SetupDefinition]] = None,
        limit: int = FETCH_LIMIT,
    ) -> None:
        self.symbol = symbol
        self.exchange = exchange.lower()
        self.limit = int(limit)
        # SetupService validates the rule documents at load (spec §0.3).
        self._setup_service = SetupService(setups=setups)

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------
    def evaluate(self) -> Dict[str, Any]:
        setups = self._setup_service.setups
        if not setups:
            raise ValueError("No setups configured")

        timeframes = sorted({tf for setup in setups for tf in setup.timeframes()})
        frames = {tf: self._enriched_frame(tf) for tf in timeframes}

        return {
            "symbol": self.symbol,
            "rule_version": setups[0].rule_version,
            "evaluated_at": datetime.now(tz=timezone.utc).isoformat(),
            "setups": [self._evaluate_one(setup, frames) for setup in setups],
        }

    # ------------------------------------------------------------------
    # Per-setup evaluation + serialisation
    # ------------------------------------------------------------------
    def _evaluate_one(
        self, setup: SetupDefinition, frames: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        trigger_tf = setup.trigger_timeframe
        trigger_df = frames[trigger_tf]
        if trigger_df.empty:
            raise ValueError(f"No closed {trigger_tf} candles for {self.symbol}")

        # Multi-TF alignment (spec §0.2): context frames are cut at the last
        # closed trigger candle's close time — never a not-yet-closed candle.
        trigger_close = trigger_df.index[-1] + pd.Timedelta(
            seconds=TIMEFRAME_SECONDS[trigger_tf]
        )
        sliced: Dict[str, pd.DataFrame] = {trigger_tf: trigger_df}
        for tf in setup.timeframes():
            if tf == trigger_tf:
                continue
            aligned = SetupService.align_context(frames[tf], trigger_close, tf)
            if aligned.empty:
                raise ValueError(
                    f"No closed {tf} context candles for {setup.setup_id}"
                )
            sliced[tf] = aligned

        evaluation = self._setup_service.evaluate_setup(setup, sliced)
        status = self._status(evaluation)
        vetoes_ran = status in ("triggered", "vetoed")

        return {
            "setup_id": setup.setup_id,
            "side": setup.side,
            "band": setup.timeframe_band,
            "context_tf": setup.context_timeframe,
            "trigger_tf": setup.trigger_timeframe,
            "status": status,
            "conditions": {
                "context": self._condition_entries(
                    setup.context_all_of + setup.context_any_of,
                    setup, setup.context_timeframe, sliced,
                ),
                "trigger": self._condition_entries(
                    setup.trigger_any_of + setup.trigger_all_of,
                    setup, setup.trigger_timeframe, sliced,
                ),
                "invalidation": self._condition_entries(
                    setup.invalidation_any_of,
                    setup, setup.context_timeframe, sliced,
                ),
            },
            "vetoes": self._veto_entries(setup, evaluation, vetoes_ran),
            "adx_turn_grade": evaluation.adx_turn_grade,
            "evidence": {
                "price": _last(trigger_df, "close"),
                "bbwp": _last(trigger_df, "bbwp"),
                "ao": _last(trigger_df, "ao"),
                "adx": _last(trigger_df, "adx14"),
                "konkorde_marron": _last(trigger_df, "konkorde_marron"),
            },
        }

    @staticmethod
    def _status(evaluation: SetupEvaluation) -> str:
        """Map the evaluation to the contract status (spec §B.0 order)."""
        if evaluation.invalidated:
            return "invalidated"
        if not evaluation.context_ok:
            return "no_context"
        if not evaluation.trigger_ok:
            return "context_ok"
        if evaluation.vetoed:
            return "vetoed"
        return "triggered"

    @staticmethod
    def _condition_entries(
        conditions: Sequence[Condition],
        setup: SetupDefinition,
        default_timeframe: str,
        frames: Dict[str, pd.DataFrame],
    ) -> List[Dict[str, Any]]:
        """Per-condition breakdown, re-using the canonical evaluator.

        Band-guarded conditions (Konkorde in low_tf) are omitted: per spec
        §0.3 they never vote and never appear in any support list.
        """
        entries: List[Dict[str, Any]] = []
        for cond in conditions:
            frame = frames[cond.timeframe or default_timeframe]
            passed, label = SetupService._eval_condition(
                cond, frame, setup.timeframe_band
            )
            if passed is None:
                continue  # band-guarded away (spec §0.3 runtime guard)
            entries.append(
                {
                    "name": label,
                    "passed": bool(passed),
                    "value": _condition_value(cond, frame),
                }
            )
        return entries

    @staticmethod
    def _veto_entries(
        setup: SetupDefinition, evaluation: SetupEvaluation, vetoes_ran: bool
    ) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        for veto in setup.vetoes:
            if veto.veto == "freshness":
                name = _EVENT_STALE_REASON[veto.event]
                detail = (
                    f"{veto.event} must be <= {veto.max_event_age} "
                    "closed candles old"
                )
            elif veto.veto == "adx_confirmation":
                name = "no_adx_turn_confirmation"
                detail = (
                    f"adx_turn:{veto.variant} must fire within "
                    f"{veto.confirm_window} closed candles"
                )
            else:  # pragma: no cover - unknown veto types fail at load time
                raise ValueError(f"Unknown veto type: {veto.veto}")
            if not vetoes_ran:
                detail += " (not evaluated: trigger did not fire)"
            entries.append(
                {
                    "name": name,
                    "hit": vetoes_ran and name in evaluation.veto_reasons,
                    "detail": detail,
                }
            )
        return entries

    # ------------------------------------------------------------------
    # Data loading (closed candles only + indicator enrichment)
    # ------------------------------------------------------------------
    def _enriched_frame(self, timeframe: str) -> pd.DataFrame:
        market = MarketDataService(exchange_name=self.exchange)
        raw = market.get_ohlcv(
            symbol=self.symbol,
            timeframe=timeframe,
            limit=self.limit,
            drop_forming=True,  # closed candles only (spec §0.1)
        )
        if raw.empty:
            raise ValueError(
                f"No closed candles for {self.symbol} {timeframe} "
                f"on {self.exchange}"
            )

        key = (self.exchange, self.symbol, timeframe, int(raw["timestamp"].iloc[-1]))
        cache = self._CACHE
        if cache is not None:
            with self._CACHE_LOCK:
                cached = cache.get(key)
            if cached is not None:
                return cached

        service = IndicatorsService(raw)
        service.calculate_all()
        enriched = service.df

        if cache is not None:
            with self._CACHE_LOCK:
                cache[key] = enriched
        return enriched


def _condition_value(cond: Condition, df: pd.DataFrame) -> Optional[float]:
    """Informational numeric value for a condition (last closed candle).

    Comparisons report the signed margin (positive = condition side); state
    and event conditions report the underlying series value.
    """
    element = cond.element
    try:
        if element in ("close_above_sma200", "close_below_sma200"):
            return _diff(df, "close", "sma200")
        if element in ("ema50_above_sma50", "ema50_below_sma50"):
            return _diff(df, "ema50", "sma50")
        if element in ("adx_level", "adx_turn"):
            return _last(df, "adx14")
        if element in ("konkorde_state", "konkorde_zero_cross"):
            return _last(df, "konkorde_marron")
        if element in ("ao_divergence", "ao_positive", "ao_negative", "ao_rising", "ao_falling"):
            return _last(df, "ao")
        if element == "bbwp_regime":
            return _last(df, "bbwp")
        if element == "vol_turn":
            return _last(df, cond.source or "bbwp")
        if element == "pullback_state":
            window = int(cond.params.get("pullback_window", 10))
            lows = df["low"].dropna().iloc[-window:]
            ema50 = _last(df, "ema50")
            if lows.empty or ema50 is None:
                return None
            return _clean_float(float(lows.min()) - ema50)
        if element == "rally_state":
            window = int(cond.params.get("pullback_window", 10))
            highs = df["high"].dropna().iloc[-window:]
            ema50 = _last(df, "ema50")
            if highs.empty or ema50 is None:
                return None
            return _clean_float(float(highs.max()) - ema50)
        if element == "close_breaks_prior_high":
            if len(df) < 2:
                return None
            close = _last(df, "close")
            prior_high = _clean_float(df["high"].iloc[-2])
            if close is None or prior_high is None:
                return None
            return _clean_float(close - prior_high)
        if element == "close_breaks_prior_low":
            if len(df) < 2:
                return None
            close = _last(df, "close")
            prior_low = _clean_float(df["low"].iloc[-2])
            if close is None or prior_low is None:
                return None
            return _clean_float(close - prior_low)
    except Exception:  # informational only: never break the evaluation
        return None
    return None


def _diff(df: pd.DataFrame, left: str, right: str) -> Optional[float]:
    a = _last(df, left)
    b = _last(df, right)
    if a is None or b is None:
        return None
    return _clean_float(a - b)
