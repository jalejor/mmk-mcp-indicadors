from typing import Optional

from fastapi import APIRouter, Query
from middlewares import has_errors

from controllers.metrics.impulse_service import ImpulseEvaluationService
from controllers.metrics.market_data_service import DEFAULT_EXCHANGE
from controllers.metrics.trade_profiles import DEFAULT_PROFILE

impulse_router = APIRouter()

tags = ["impulse"]


@impulse_router.get("/evaluate", tags=tags)
@has_errors
async def evaluate_impulse(
    symbol: str = Query(..., description="Trading pair, e.g. BTC/USDT"),
    profile: str = Query(DEFAULT_PROFILE, description="Trade profile: scalper | snipper | pro | ancient"),
    exchange: str = Query(DEFAULT_EXCHANGE, description="Exchange: binance, bitget"),
    position: Optional[str] = Query(None, description="Open virtual position: long | short (empty = flat)"),
    entry_price: Optional[float] = Query(None, description="Entry price of the open position (ATR stop from current ATR)"),
    stop_price: Optional[float] = Query(None, description="Initial protective stop of the open position (defines 1R)"),
    bars_held: Optional[int] = Query(None, description="Closed trigger bars since entry (entry bar = 0); enables the time stop"),
):
    """Impulse engine v2 (impulsos-v2) at the last CLOSED trigger candle.

    Loads the profile's trigger, confirm and context timeframes (closed
    candles only), enriches them with the TV BBWP and returns the decision:
    `{timestamp, timeframe, trigger_tf, candle_close, profile, side, phase,
    action, reasons, confidence, side_score, context_bias, stop_price,
    exit_price, context, rule_version, symbol, exchange, evaluated_at,
    trade_profile, tf_status}` (spec docs/impulsos-v2.md). `action` is
    `enter | none` when flat and `exit | hold` when `position` is given.
    """
    service = ImpulseEvaluationService(
        symbol=symbol,
        profile=profile,
        exchange=exchange,
        position=position or None,
        entry_price=entry_price,
        stop_price=stop_price,
        bars_held=bars_held,
    )
    return service.evaluate()
