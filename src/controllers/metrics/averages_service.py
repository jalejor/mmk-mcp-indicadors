from __future__ import annotations

"""Servicio para calcular promedios de indicadores técnicos y detectar el mayor rebote
(bullish o bearish) en un rango de fechas determinado.

Este módulo está pensado para ser extendido fácilmente añadiendo más indicadores o
cambiando el criterio de "rebote". Para añadir un nuevo indicador basta con:
1. Agregar el nombre en `SUPPORTED_INDICATORS`.
2. Implementar un método `_avg_<nombre>(df: pd.DataFrame) -> float` que calcule
   la serie correspondiente y devuelva el valor promedio.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Callable

import pandas as pd
import pandas_ta as ta
import re

from .market_data_service import MarketDataService


class AveragesService:
    """Calcula promedios de indicadores sobre un rango y detecta el mayor rebote."""

    #: Indicadores soportados.  Mapea nombre → función que calcula el promedio.
    SUPPORTED_INDICATORS: Dict[str, str] = {
        "close": "_avg_close",
        "volume": "_avg_volume",
        "rsi": "_avg_rsi",
        "adx": "_avg_adx",
        "highest_price": "_max_high",
        "lowest_price": "_min_low",
        "highest_prices": "_top_highs",
        "lowest_prices": "_top_lows",
        "avg_price": "_avg_price",
        "avg_high": "_avg_high",
        "avg_low": "_avg_low",
    }

    def __init__(
        self,
        *,
        symbol: str,
        timeframe: str = "1h",
        exchange: str = "binance",
        start: datetime | None = None,
        end: datetime | None = None,
        span: str = "1d",
        indicators: List[str] | None = None,
        top_n: int = 10,
        candles_limit: int = 1500,
    ) -> None:
        """Si `start` y `end` se omiten, se usará `span` para calcular un rango retrospectivo
        terminado en *ahora*.
        """
        self.symbol = symbol
        self.timeframe = timeframe
        self.exchange = exchange
        self.candles_limit = candles_limit
        self.top_n = max(1, top_n)

        now = datetime.now(tz=timezone.utc)

        if start is None and end is None:
            delta = self._span_to_timedelta(span)
            self.end = now
            self.start = now - delta
        elif start is not None and end is not None:
            self.start = start.astimezone(timezone.utc)
            self.end = end.astimezone(timezone.utc)
        else:
            raise ValueError("Debe proporcionar ambos parámetros start y end, o ninguno y usar span")

        self.indicators = indicators or list(self.SUPPORTED_INDICATORS.keys())

        unknown = set(self.indicators) - set(self.SUPPORTED_INDICATORS.keys())
        if unknown:
            raise ValueError(f"Indicadores no soportados solicitados: {', '.join(unknown)}")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def execute(self) -> Dict[str, Any]:
        """Calcula los promedios solicitados y el mayor rebote.

        Returns
        -------
        dict
            {
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "averages": { ... },
                "major_rebound": { ... },
            }
        """
        # 1. Obtener datos de mercado
        df = self._load_market_data()

        # 2. Filtrar por rango
        df_range = df.loc[self.start : self.end]
        if df_range.empty or len(df_range) < 2:
            raise ValueError("No hay suficientes velas en el rango para calcular promedios y rebotes")

        # 3. Calcular promedios
        averages: Dict[str, float | None] = {}
        for ind in self.indicators:
            method_name = self.SUPPORTED_INDICATORS[ind]
            method: Callable[[pd.DataFrame], float | None] = getattr(self, method_name)
            val = method(df_range)
            # Sanitizar NaN / Inf para valores escalares
            if isinstance(val, (float, int)):
                if val is not None and not pd.notna(val):
                    val = None
            averages[ind] = val

        # 4. Mayor rebote
        major_rebound = self._detect_major_rebound(df_range)

        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "averages": averages,
            "major_rebound": major_rebound,
        }

    # ------------------------------------------------------------------
    # Indicadores individuales (privados)
    # ------------------------------------------------------------------
    def _avg_close(self, df: pd.DataFrame) -> float | None:
        series = df["close"].dropna()
        return float(series.mean()) if not series.empty else None

    def _avg_volume(self, df: pd.DataFrame) -> float | None:
        series = df["volume"].dropna()
        return float(series.mean()) if not series.empty else None

    def _avg_rsi(self, df: pd.DataFrame) -> float | None:
        rsi_series = ta.rsi(df["close"], length=14).dropna()
        return float(rsi_series.mean()) if not rsi_series.empty else None

    def _avg_adx(self, df: pd.DataFrame) -> float | None:
        adx_series = ta.adx(df["high"], df["low"], df["close"], length=14)["ADX_14"].dropna()
        return float(adx_series.mean()) if not adx_series.empty else None

    def _max_high(self, df: pd.DataFrame) -> float | None:
        series = df["high"].dropna()
        return float(series.max()) if not series.empty else None

    def _min_low(self, df: pd.DataFrame) -> float | None:
        series = df["low"].dropna()
        return float(series.min()) if not series.empty else None

    def _top5_highs(self, df: pd.DataFrame):
        series = df["high"].dropna()
        return series.nlargest(5).tolist() if not series.empty else []

    def _avg_price(self, df: pd.DataFrame) -> float | None:
        mid = ((df["high"] + df["low"]) / 2).dropna()
        return float(mid.mean()) if not mid.empty else None

    def _top_highs(self, df: pd.DataFrame):
        series = df["high"].dropna()
        return series.nlargest(self.top_n).tolist() if not series.empty else []

    def _top_lows(self, df: pd.DataFrame):
        series = df["low"].dropna()
        return series.nsmallest(self.top_n).tolist() if not series.empty else []

    def _avg_high(self, df: pd.DataFrame) -> float | None:
        highs = df["high"].dropna().nlargest(self.top_n)
        return float(highs.mean()) if len(highs) else None

    def _avg_low(self, df: pd.DataFrame) -> float | None:
        lows = df["low"].dropna().nsmallest(self.top_n)
        return float(lows.mean()) if len(lows) else None

    def _top5_lows(self, df: pd.DataFrame):
        series = df["low"].dropna()
        return series.nsmallest(5).tolist() if not series.empty else []

    # ------------------------------------------------------------------
    # Rebote (private)
    # ------------------------------------------------------------------
    def _detect_major_rebound(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detecta el cambio porcentual más grande entre velas consecutivas.

        Consideramos como rebote el cambio porcentual entre cierres sucesivos.
        """
        pct = df["close"].pct_change().dropna() * 100.0
        if pct.empty:
            raise ValueError("No hay suficientes datos para calcular rebotes")

        idx_max = pct.abs().idxmax()
        move_pct = float(abs(pct.loc[idx_max]))
        reb_type = "bullish" if pct.loc[idx_max] > 0 else "bearish"

        return {
            "date": idx_max.isoformat(),
            "type": reb_type,
            "move_pct": round(move_pct, 2),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _span_to_timedelta(span: str) -> timedelta:
        """Convierte una cadena de rango (ej: '48h', '7d', '1w', '1m') en timedelta.

        w → semanas (7 días), m → meses (30 días aproximados).
        """
        match = re.fullmatch(r"(\d+)([hdwm])", span.strip().lower())
        if not match:
            raise ValueError("Formato de span inválido. Use p.e. '48h', '7d', '1w', '1m'")

        qty = int(match.group(1))
        unit = match.group(2)
        if unit == "h":
            return timedelta(hours=qty)
        if unit == "d":
            return timedelta(days=qty)
        if unit == "w":
            return timedelta(days=qty * 7)
        if unit == "m":
            return timedelta(days=qty * 30)
        # Should never reach here due to regex
        raise ValueError("Unidad de span no soportada")

    def _load_market_data(self) -> pd.DataFrame:
        svc = MarketDataService(exchange_name=self.exchange)
        # Traemos un número razonable de velas.  ccxt permite filtrar con "since",
        # pero para mantener compatibilidad con el MarketDataService actual,
        # descargamos un bloque más grande y filtramos localmente.
        df = svc.get_ohlcv(symbol=self.symbol, timeframe=self.timeframe, limit=self.candles_limit)
        return df
