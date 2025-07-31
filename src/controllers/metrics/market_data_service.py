import ccxt
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd


class MarketDataService:
    """Servicio encargado de obtener datos de mercado (OHLCV) de distintos exchanges
    mediante la librería ccxt. No requiere claves API para endpoints públicos."""

    SUPPORTED_EXCHANGES = {
        "binance": ccxt.binance,
        "bitget": ccxt.bitget,
        # Agregar más exchanges compatibles aquí
    }

    def __init__(self, exchange_name: str = "binance") -> None:
        exchange_name = exchange_name.lower()
        if exchange_name not in self.SUPPORTED_EXCHANGES:
            raise ValueError(f"Exchange no soportado: {exchange_name}")

        self.exchange = self.SUPPORTED_EXCHANGES[exchange_name]({
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot",
            },
        })

    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        """Descarga datos históricos OHLCV y los devuelve como DataFrame.

        Parameters
        ----------
        symbol : str
            Par de trading, p.e. "BTC/USDT".
        timeframe : str, optional
            Marco temporal (ccxt), por defecto "1h".
        limit : int, optional
            Número de velas a solicitar, por defecto 500.
        """
        # ccxt devuelve [ timestamp, open, high, low, close, volume ]
        raw_ohlcv: List[List[Any]] = self.exchange.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)

        df = pd.DataFrame(raw_ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("datetime", inplace=True)
        return df
