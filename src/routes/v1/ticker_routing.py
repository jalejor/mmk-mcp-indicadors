from controllers.metrics.market_data_service import DEFAULT_EXCHANGE
from fastapi import APIRouter, Query
from middlewares import has_errors

from controllers.metrics.ticker_service import TickerService

ticker_router = APIRouter()

tags = ["ticker"]


@ticker_router.get("", tags=tags)
@has_errors
async def get_ticker(
    symbol: str = Query(..., description="Par a consultar, ej: BTC/USDT o CL/USDT:USDT"),
    exchange: str = Query(DEFAULT_EXCHANGE, description="Exchange a usar"),
):
    """Fresh last/bid/ask via ccxt fetch_ticker (NO OHLCV cache)."""
    return TickerService(exchange=exchange).fetch(symbol)
