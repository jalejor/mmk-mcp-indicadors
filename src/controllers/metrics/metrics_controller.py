from datetime import datetime, timezone
from typing import Dict, Any

from .market_data_service import MarketDataService
from .indicators_service import IndicatorsService
from .rules_service import RulesService


class MetricsController:
    """Controlador principal que coordina la descarga de datos, cálculo de indicadores
    y evaluación de reglas, devolviendo un payload estructurado listo para exponer vía API."""

    def __init__(self, exchange: str = "binance") -> None:
        self.exchange_name = exchange.lower()

    def process_symbol(self, symbol: str, timeframe: str = "1h", limit: int = 500) -> Dict[str, Any]:
        # 1. Datos de mercado
        market_service = MarketDataService(exchange_name=self.exchange_name)
        # Permite alias legibles para timeframe
        _aliases = {"daily": "1d", "diario": "1d", "weekly": "1w", "semanal": "1w", "monthly": "1M", "mensual": "1M"}
        tf_ccxt = _aliases.get(timeframe.lower(), timeframe)
        df = market_service.get_ohlcv(symbol=symbol, timeframe=tf_ccxt, limit=limit)

        # 2. Indicadores
        indicators = IndicatorsService(df).calculate_all()

        # 3. Reglas / señales
        rules = RulesService(symbol=symbol).evaluate(indicators)

        # 4. Construcción de payload
        payload = {
            "exchange": self.exchange_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "indicators": indicators,
            "signals": rules,
        }

        return payload
