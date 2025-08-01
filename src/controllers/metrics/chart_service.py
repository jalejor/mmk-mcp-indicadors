from __future__ import annotations

"""Servicio para generar datos optimizados para gráficos de trading.

Este servicio determina automáticamente el mejor timeframe y configuración
para visualizar datos de trading basándose en el rango temporal solicitado.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Tuple, Optional
import pandas as pd

from .market_data_service import MarketDataService


class ChartService:
    """Genera datos optimizados para gráficos de trading con timeframes inteligentes."""

    # Mapeo de timeframes ccxt con prioridad (menor número = preferido)
    TIMEFRAMES = {
        "1m": {"seconds": 60, "priority": 1, "max_candles": 1000},
        "3m": {"seconds": 180, "priority": 2, "max_candles": 1000},
        "5m": {"seconds": 300, "priority": 3, "max_candles": 1000},
        "15m": {"seconds": 900, "priority": 4, "max_candles": 1000},
        "30m": {"seconds": 1800, "priority": 5, "max_candles": 1000},
        "1h": {"seconds": 3600, "priority": 6, "max_candles": 1000},
        "2h": {"seconds": 7200, "priority": 7, "max_candles": 1000},
        "4h": {"seconds": 14400, "priority": 8, "max_candles": 1000},
        "6h": {"seconds": 21600, "priority": 9, "max_candles": 1000},
        "8h": {"seconds": 28800, "priority": 10, "max_candles": 1000},
        "12h": {"seconds": 43200, "priority": 11, "max_candles": 1000},
        "1d": {"seconds": 86400, "priority": 12, "max_candles": 1000},
        "3d": {"seconds": 259200, "priority": 13, "max_candles": 1000},
        "1w": {"seconds": 604800, "priority": 14, "max_candles": 1000},
        "1M": {"seconds": 2592000, "priority": 15, "max_candles": 1000},
    }

    def __init__(
        self,
        *,
        symbol: str,
        exchange: str = "binance",
        start: datetime | None = None,
        end: datetime | None = None,
        span: str = "1d",
        max_points: int = 1000,
        preferred_timeframe: str | None = None,
    ) -> None:
        """
        Parameters
        ----------
        symbol : str
            Par de trading (ej: BTC/USDT)
        exchange : str
            Exchange a consultar
        start, end : datetime
            Rango específico o None para usar span
        span : str
            Rango retrospectivo desde ahora (ej: "24h", "7d", "1M")
        max_points : int
            Máximo número de puntos deseados en el gráfico
        preferred_timeframe : str
            Timeframe preferido, si None se determina automáticamente
        """
        self.symbol = symbol
        self.exchange = exchange
        self.max_points = max_points
        self.preferred_timeframe = preferred_timeframe

        # Calcular rango temporal
        now = datetime.now(tz=timezone.utc)
        if start is None and end is None:
            delta = self._span_to_timedelta(span)
            self.end = now
            self.start = now - delta
        elif start is not None and end is not None:
            self.start = start.astimezone(timezone.utc)
            self.end = end.astimezone(timezone.utc)
        else:
            raise ValueError("Debe proporcionar ambos start/end o ninguno (usar span)")

        self.duration_seconds = (self.end - self.start).total_seconds()

    def execute(self) -> Dict[str, Any]:
        """Genera los datos optimizados para gráfico."""
        # 1. Determinar el mejor timeframe
        optimal_timeframe = self._determine_optimal_timeframe()
        
        # 2. Obtener datos con fallback
        chart_data, actual_timeframe = self._fetch_chart_data(optimal_timeframe)
        
        # 3. Procesar datos para el gráfico
        processed_data = self._process_chart_data(chart_data)
        
        # 4. Calcular métricas del gráfico
        chart_metrics = self._calculate_chart_metrics(chart_data)
        
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timeframe": actual_timeframe,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_hours": round(self.duration_seconds / 3600, 1),
            "total_candles": len(chart_data),
            "chart_data": processed_data,
            "metrics": chart_metrics,
            "optimization": {
                "optimal_timeframe": optimal_timeframe,
                "reason": self._get_optimization_reason(optimal_timeframe, actual_timeframe),
                "data_density": self._calculate_data_density(len(chart_data)),
            }
        }

    def _determine_optimal_timeframe(self) -> str:
        """Determina el timeframe óptimo basado en la duración del rango."""
        if self.preferred_timeframe and self.preferred_timeframe in self.TIMEFRAMES:
            return self.preferred_timeframe

        # Calcular puntos ideales por timeframe
        best_timeframe = "1h"
        best_score = float('inf')
        
        for tf, config in self.TIMEFRAMES.items():
            candle_duration = config["seconds"]
            estimated_candles = self.duration_seconds / candle_duration
            max_candles = config["max_candles"]
            
            # Limitar por máximo del exchange
            actual_candles = min(estimated_candles, max_candles)
            
            # Penalizar si excede max_points o es muy poco denso
            if actual_candles > self.max_points:
                score = abs(actual_candles - self.max_points) + config["priority"] * 10
            elif actual_candles < 50:  # Muy pocos puntos
                score = abs(50 - actual_candles) + config["priority"] * 5
            else:
                score = config["priority"]  # Timeframe más granular es mejor
            
            if score < best_score:
                best_score = score
                best_timeframe = tf
                
        return best_timeframe

    def _fetch_chart_data(self, optimal_timeframe: str) -> Tuple[pd.DataFrame, str]:
        """Obtiene datos con fallback a timeframes alternativos."""
        market_service = MarketDataService(exchange_name=self.exchange)
        
        # Lista de timeframes a intentar (empezando por el óptimo)
        timeframes_to_try = [optimal_timeframe]
        
        # Agregar alternativas más granulares y menos granulares
        current_priority = self.TIMEFRAMES[optimal_timeframe]["priority"]
        for tf, config in sorted(self.TIMEFRAMES.items(), key=lambda x: abs(x[1]["priority"] - current_priority)):
            if tf not in timeframes_to_try:
                timeframes_to_try.append(tf)
        
        for timeframe in timeframes_to_try:
            try:
                max_candles = self.TIMEFRAMES[timeframe]["max_candles"]
                df = market_service.get_ohlcv(
                    symbol=self.symbol,
                    timeframe=timeframe,
                    limit=max_candles
                )
                
                # Filtrar por rango temporal
                df_filtered = df.loc[self.start:self.end]
                
                if len(df_filtered) >= 10:  # Mínimo 10 velas para ser útil
                    return df_filtered, timeframe
                    
            except Exception as e:
                continue
        
        # Si ningún timeframe funciona, usar el último disponible
        raise ValueError(f"No se pudieron obtener datos para {self.symbol} en {self.exchange}")

    def _process_chart_data(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Procesa el DataFrame para formato JSON optimizado para gráficos."""
        chart_points = []
        
        for idx, row in df.iterrows():
            point = {
                "timestamp": int(idx.timestamp() * 1000),  # Milliseconds para JS
                "datetime": idx.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            chart_points.append(point)
        
        return chart_points

    def _calculate_chart_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calcula métricas resumidas del gráfico."""
        if df.empty:
            return {}
        
        return {
            "price_range": {
                "highest": float(df["high"].max()),
                "lowest": float(df["low"].min()),
                "range_pct": round(((df["high"].max() - df["low"].min()) / df["low"].min()) * 100, 2)
            },
            "volume": {
                "total": float(df["volume"].sum()),
                "average": float(df["volume"].mean()),
                "max": float(df["volume"].max())
            },
            "price_change": {
                "start_price": float(df["close"].iloc[0]),
                "end_price": float(df["close"].iloc[-1]),
                "change_pct": round(((df["close"].iloc[-1] - df["close"].iloc[0]) / df["close"].iloc[0]) * 100, 2)
            },
            "volatility": {
                "daily_returns_std": round(df["close"].pct_change().std() * 100, 3),
                "price_volatility": round(((df["high"] - df["low"]) / df["close"]).mean() * 100, 2)
            }
        }

    def _get_optimization_reason(self, optimal: str, actual: str) -> str:
        """Explica por qué se eligió este timeframe."""
        if optimal == actual:
            return f"Timeframe óptimo {actual} seleccionado automáticamente"
        else:
            return f"Fallback de {optimal} a {actual} debido a disponibilidad de datos"

    def _calculate_data_density(self, num_candles: int) -> str:
        """Evalúa la densidad de datos."""
        if num_candles > self.max_points:
            return "alta"
        elif num_candles > self.max_points * 0.7:
            return "óptima"
        elif num_candles > 50:
            return "moderada"
        else:
            return "baja"

    @staticmethod
    def _span_to_timedelta(span: str) -> timedelta:
        """Convierte span string a timedelta."""
        import re
        match = re.fullmatch(r"(\d+)([hdwM])", span.strip().lower())
        if not match:
            raise ValueError("Formato de span inválido. Use ej: '24h', '7d', '1w', '1M'")

        qty = int(match.group(1))
        unit = match.group(2)
        
        if unit == "h":
            return timedelta(hours=qty)
        elif unit == "d":
            return timedelta(days=qty)
        elif unit == "w":
            return timedelta(days=qty * 7)
        elif unit == "M":
            return timedelta(days=qty * 30)
        else:
            raise ValueError("Unidad no soportada")

    def get_available_timeframes(self) -> List[Dict[str, Any]]:
        """Devuelve lista de timeframes disponibles con sus características."""
        duration_hours = self.duration_seconds / 3600
        
        timeframes_info = []
        for tf, config in self.TIMEFRAMES.items():
            candle_hours = config["seconds"] / 3600
            estimated_candles = duration_hours / candle_hours
            
            timeframes_info.append({
                "timeframe": tf,
                "candle_duration": f"{candle_hours}h" if candle_hours >= 1 else f"{int(config['seconds']/60)}m",
                "estimated_candles": min(int(estimated_candles), config["max_candles"]),
                "density": "óptima" if 50 <= estimated_candles <= self.max_points else "subóptima",
                "recommended": tf == self._determine_optimal_timeframe()
            })
        
        return sorted(timeframes_info, key=lambda x: self.TIMEFRAMES[x["timeframe"]]["priority"])