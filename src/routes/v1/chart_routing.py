from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from devops_py_utils.web.middlewares import has_errors

from controllers.metrics.chart_service import ChartService

chart_router = APIRouter()

tags = ["charts"]


@chart_router.get("/", tags=tags)
@has_errors
async def get_chart_data(
    symbol: str = Query(..., description="Par de trading, ej: BTC/USDT"),
    exchange: str = Query("binance", description="Exchange a usar: binance, bitget"),
    start: datetime | None = Query(None, description="Fecha/hora inicial en formato ISO 8601"),
    end: datetime | None = Query(None, description="Fecha/hora final en formato ISO 8601"),
    span: str = Query("24h", description="Rango retrospectivo si no se provee start/end. Ej: 1h,24h,7d,30d,1M"),
    max_points: int = Query(1000, ge=50, le=5000, description="Máximo número de puntos para el gráfico"),
    timeframe: str | None = Query(None, description="Timeframe específico (opcional, se autoselecciona si se omite)"),
):
    """Obtiene datos optimizados para gráficos de trading.

    Este endpoint determina automáticamente el mejor timeframe basándose en:
    - Rango temporal solicitado
    - Número máximo de puntos deseados
    - Disponibilidad de datos en el exchange

    Parámetros
    ----------
    symbol : str
        Par de trading (BTC/USDT, ETH/USDT, etc.)
    exchange : str
        Exchange a consultar (binance, bitget)
    start, end : datetime, opcional
        Rango temporal específico. Si se omite, usa 'span'
    span : str
        Rango retrospectivo desde ahora:
        - Horas: 1h, 6h, 24h
        - Días: 7d, 30d
        - Semanas: 1w, 4w
        - Meses: 1M, 3M, 6M
    max_points : int
        Máximo número de velas/puntos para el gráfico (50-5000)
    timeframe : str, opcional
        Forzar timeframe específico: 1m, 5m, 15m, 1h, 4h, 1d, etc.

    Devuelve
    --------
    dict
        Datos del gráfico con timeframe optimizado, métricas y puntos OHLCV.

    Ejemplos
    --------
    # Gráfico automático de 24h
    GET /charts/?symbol=BTC/USDT&span=24h

    # Gráfico de 7 días con máximo 500 puntos
    GET /charts/?symbol=ETH/USDT&span=7d&max_points=500

    # Rango específico con timeframe forzado
    GET /charts/?symbol=BTC/USDT&start=2025-07-25T00:00:00Z&end=2025-07-31T23:59:59Z&timeframe=1h
    """
    svc = ChartService(
        symbol=symbol,
        exchange=exchange,
        start=start,
        end=end,
        span=span,
        max_points=max_points,
        preferred_timeframe=timeframe,
    )
    return svc.execute()


@chart_router.get("/timeframes", tags=tags)
@has_errors
async def get_available_timeframes(
    symbol: str = Query(..., description="Par de trading"),
    exchange: str = Query("binance", description="Exchange a consultar"),
    span: str = Query("24h", description="Rango temporal para evaluar timeframes"),
    max_points: int = Query(1000, description="Máximo puntos deseados"),
):
    """Lista timeframes disponibles con estimaciones de densidad de datos.

    Útil para mostrar opciones al usuario antes de generar el gráfico.

    Devuelve
    --------
    dict
        Lista de timeframes con características:
        - timeframe: código del timeframe
        - candle_duration: duración de cada vela
        - estimated_candles: número estimado de velas
        - density: densidad de datos (óptima, subóptima)
        - recommended: si es el timeframe recomendado
    """
    svc = ChartService(
        symbol=symbol,
        exchange=exchange,
        span=span,
        max_points=max_points,
    )
    
    timeframes = svc.get_available_timeframes()
    
    return {
        "symbol": symbol,
        "exchange": exchange,
        "span": span,
        "max_points": max_points,
        "available_timeframes": timeframes,
        "recommended_timeframe": next(
            (tf["timeframe"] for tf in timeframes if tf["recommended"]), 
            "1h"
        )
    }