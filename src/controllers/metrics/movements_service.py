from __future__ import annotations

"""Servicio para generar recomendaciones de posiciones *Long* y *Short* basadas
   en indicadores técnicos y reglas configurables.

   El algoritmo está pensado para ser sencillo pero extensible:
   - Para mejorar la lógica de cálculo de objetivo y stop-loss, ajustar
     `RISK_PROFILES`.
   - Para cambiar la lógica de confianza, ajustar `_confidence`.
"""

from datetime import datetime, timezone
from typing import Dict, Any, Literal, Tuple

import pandas as pd

from .market_data_service import MarketDataService
from .indicators_service import IndicatorsService
from .rules_service import RulesService

RiskProfile = Literal["low", "medium", "high"]
Side = Literal["long", "short", "both"]


class MovementsService:
    """Genera recomendaciones de trading para posiciones long y short."""

    RISK_PROFILES: Dict[RiskProfile, Tuple[float, float]] = {
        # (target_pct, stop_pct)
        "low": (2.0, 1.0),
        "medium": (4.0, 2.0),
        "high": (8.0, 4.0),
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
    ) -> None:
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = exchange
        self.capital = capital
        self.risk_profile = risk_profile
        self.side = side
        self.candles_limit = candles_limit

        if risk_profile not in self.RISK_PROFILES:
            raise ValueError(f"Risk profile no soportado: {risk_profile}")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def execute(self) -> Dict[str, Any]:
        df = self._load_market_data()
        last_close = float(df["close"].iloc[-1])

        indicators = IndicatorsService(df).calculate_all()
        rules = RulesService(symbol=self.symbol).evaluate(indicators)

        target_pct, stop_pct = self.RISK_PROFILES[self.risk_profile]

        result: Dict[str, Any] = {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
        }

        if self.side in ("long", "both"):
            result["long"] = self._build_long(last_close, target_pct, stop_pct, rules)
        if self.side in ("short", "both"):
            result["short"] = self._build_short(last_close, target_pct, stop_pct, rules)

        return result

    # ------------------------------------------------------------------
    # Sides builders (private)
    # ------------------------------------------------------------------
    def _build_long(self, price: float, target_pct: float, stop_pct: float, rules: Dict[str, Any]) -> Dict[str, Any]:
        entry_votes = rules.get("entry_votes", 0)
        exit_votes = rules.get("exit_votes", 0)
        confidence = self._confidence(entry_votes, exit_votes)
        reasons = rules.get("explain_entry", [])
        return {
            "entry": round(price, 2),
            "target_pct": target_pct,
            "stop_loss": round(price * (1 - stop_pct / 100.0), 2),
            "confidence": confidence,
            "reasons": reasons,
        }

    def _build_short(self, price: float, target_pct: float, stop_pct: float, rules: Dict[str, Any]) -> Dict[str, Any]:
        entry_votes = rules.get("exit_votes", 0)  # Enfoque inverso para cortos
        exit_votes = rules.get("entry_votes", 0)
        confidence = self._confidence(entry_votes, exit_votes)
        reasons = rules.get("explain_exit", [])
        return {
            "entry": round(price, 2),
            "target_pct": target_pct,
            "stop_loss": round(price * (1 + stop_pct / 100.0), 2),
            "confidence": confidence,
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
