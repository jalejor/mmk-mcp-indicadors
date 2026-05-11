from __future__ import annotations

"""Service that produces actionable long/short trade plans.

Two sizing modes are supported:

* ATR-based (default in FASE 3): stops are placed `atr_mult_stop * ATR(14)`
  away from the entry, targets are `r_multiple * stop_distance` further out
  and quantities are derived from `risk_per_trade_pct` of the configured
  capital.  This mirrors the operative the user actually trades.
* Legacy percent (`use_atr_sizing=False`): keeps the original behaviour
  using fixed (target_pct, stop_pct) tuples per risk profile.  The output
  schema is unchanged in this mode so older API consumers keep working.
"""

from typing import Any, Dict, Literal, Tuple

import pandas as pd

from .indicators_service import IndicatorsService
from .market_data_service import MarketDataService
from .rules_service import RulesService

RiskProfile = Literal["low", "medium", "high"]
Side = Literal["long", "short", "both"]


class MovementsService:
    """Generates long/short trade recommendations."""

    # Legacy fixed-percentage profiles, kept for backwards compatibility
    # when `use_atr_sizing=False`.
    RISK_PROFILES: Dict[RiskProfile, Tuple[float, float]] = {
        # (target_pct, stop_pct)
        "low": (2.5, 1.5),
        "medium": (5.0, 3.0),
        "high": (10.0, 5.0),
    }

    # ATR-based profiles: (atr_mult_stop, r_multiple_target).
    ATR_PROFILES: Dict[RiskProfile, Tuple[float, float]] = {
        "low": (1.0, 2.0),
        "medium": (1.5, 3.0),
        "high": (2.0, 4.0),
    }

    def __init__(
        self,
        *,
        symbol: str,
        timeframe: str = "1h",
        exchange: str = "binance",
        capital: float = 1000.0,
        risk_profile: RiskProfile = "medium",
        side: Side = "both",
        candles_limit: int = 500,
        risk_per_trade_pct: float = 1.5,
        use_atr_sizing: bool = True,
    ) -> None:
        if risk_profile not in self.RISK_PROFILES:
            raise ValueError(f"Risk profile no soportado: {risk_profile}")

        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = exchange
        self.capital = float(capital)
        self.risk_profile: RiskProfile = risk_profile
        self.side = side
        self.candles_limit = candles_limit
        self.risk_per_trade_pct = float(risk_per_trade_pct)
        self.use_atr_sizing = use_atr_sizing

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def execute(self) -> Dict[str, Any]:
        df = self._load_market_data()
        last_close = float(df["close"].iloc[-1])

        indicators = IndicatorsService(df).calculate_all()
        rules = RulesService(symbol=self.symbol).evaluate(indicators)

        result: Dict[str, Any] = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "use_atr_sizing": self.use_atr_sizing,
        }

        if self.use_atr_sizing:
            atr_mult, r_mult = self.ATR_PROFILES[self.risk_profile]
            atr = float(indicators.get("atr") or 0.0)
            if atr <= 0:
                # Fallback to percent mode if ATR cannot be computed.
                target_pct, stop_pct = self.RISK_PROFILES[self.risk_profile]
                if self.side in ("long", "both"):
                    result["long"] = self._build_long_pct(last_close, target_pct, stop_pct, rules)
                if self.side in ("short", "both"):
                    result["short"] = self._build_short_pct(last_close, target_pct, stop_pct, rules)
                result["atr_fallback"] = True
                return result

            if self.side in ("long", "both"):
                result["long"] = self._build_long_atr(last_close, atr, atr_mult, r_mult, rules)
            if self.side in ("short", "both"):
                result["short"] = self._build_short_atr(last_close, atr, atr_mult, r_mult, rules)
        else:
            target_pct, stop_pct = self.RISK_PROFILES[self.risk_profile]
            if self.side in ("long", "both"):
                result["long"] = self._build_long_pct(last_close, target_pct, stop_pct, rules)
            if self.side in ("short", "both"):
                result["short"] = self._build_short_pct(last_close, target_pct, stop_pct, rules)

        return result

    # ------------------------------------------------------------------
    # ATR sizing (FASE 3)
    # ------------------------------------------------------------------
    def _build_long_atr(
        self,
        price: float,
        atr: float,
        atr_mult: float,
        r_mult: float,
        rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._build_atr_side(price, atr, atr_mult, r_mult, rules, side="long")

    def _build_short_atr(
        self,
        price: float,
        atr: float,
        atr_mult: float,
        r_mult: float,
        rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._build_atr_side(price, atr, atr_mult, r_mult, rules, side="short")

    def _build_atr_side(
        self,
        price: float,
        atr: float,
        atr_mult: float,
        r_mult: float,
        rules: Dict[str, Any],
        *,
        side: str,
    ) -> Dict[str, Any]:
        stop_distance = atr * atr_mult
        target_distance = stop_distance * r_mult
        position_size_usd = self.capital * (self.risk_per_trade_pct / 100.0)
        quantity = position_size_usd / stop_distance if stop_distance > 0 else 0.0
        dollar_risk = position_size_usd
        dollar_target = dollar_risk * r_mult

        if side == "long":
            stop_loss = price - stop_distance
            target_price = price + target_distance
            entry_votes = rules.get("entry_votes", 0)
            exit_votes = rules.get("exit_votes", 0)
            reasons = rules.get("explain_entry", [])
        else:
            stop_loss = price + stop_distance
            target_price = price - target_distance
            entry_votes = rules.get("exit_votes", 0)
            exit_votes = rules.get("entry_votes", 0)
            reasons = rules.get("explain_exit", [])

        confidence = self._confidence(entry_votes, exit_votes)
        stop_distance_pct = (stop_distance / price * 100.0) if price > 0 else 0.0

        return {
            "entry": round(price, 2),
            "stop_loss": round(stop_loss, 2),
            "target_price": round(target_price, 2),
            "atr": round(atr, 4),
            "stop_distance": round(stop_distance, 4),
            "stop_distance_pct": round(stop_distance_pct, 4),
            "r_multiple": r_mult,
            "position_size_quantity": round(quantity, 8),
            "position_size_usd": round(position_size_usd, 2),
            "dollar_risk": round(dollar_risk, 2),
            "dollar_target": round(dollar_target, 2),
            "risk_reward_ratio": r_mult,
            "confidence": confidence,
            "reasons": reasons,
        }

    # ------------------------------------------------------------------
    # Legacy percent sizing
    # ------------------------------------------------------------------
    def _build_long_pct(
        self,
        price: float,
        target_pct: float,
        stop_pct: float,
        rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        entry_votes = rules.get("entry_votes", 0)
        exit_votes = rules.get("exit_votes", 0)
        confidence = self._confidence(entry_votes, exit_votes)
        reasons = rules.get("explain_entry", [])
        target_price = round(price * (1 + target_pct / 100.0), 2)
        return {
            "entry": round(price, 2),
            "target_price": target_price,
            "target_pct": target_pct,
            "stop_loss": round(price * (1 - stop_pct / 100.0), 2),
            "confidence": confidence,
            "risk_reward_ratio": round(target_pct / stop_pct, 2),
            "reasons": reasons,
        }

    def _build_short_pct(
        self,
        price: float,
        target_pct: float,
        stop_pct: float,
        rules: Dict[str, Any],
    ) -> Dict[str, Any]:
        entry_votes = rules.get("exit_votes", 0)
        exit_votes = rules.get("entry_votes", 0)
        confidence = self._confidence(entry_votes, exit_votes)
        reasons = rules.get("explain_exit", [])
        target_price = round(price * (1 - target_pct / 100.0), 2)
        return {
            "entry": round(price, 2),
            "target_price": target_price,
            "target_pct": target_pct,
            "stop_loss": round(price * (1 + stop_pct / 100.0), 2),
            "confidence": confidence,
            "risk_reward_ratio": round(target_pct / stop_pct, 2),
            "reasons": reasons,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _confidence(entry_votes: int, exit_votes: int) -> float:
        total = max(entry_votes + exit_votes, 1)
        return round(entry_votes / total, 2)

    def _load_market_data(self) -> pd.DataFrame:
        svc = MarketDataService(exchange_name=self.exchange)
        return svc.get_ohlcv(symbol=self.symbol, timeframe=self.timeframe, limit=self.candles_limit)
