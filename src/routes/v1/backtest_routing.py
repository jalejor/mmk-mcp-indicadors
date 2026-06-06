from controllers.metrics.market_data_service import DEFAULT_EXCHANGE
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from middlewares import has_errors
from security import BACKTEST_RATE_LIMIT, limiter

from controllers.metrics.backtest_service import BacktestService

backtest_router = APIRouter()

tags = ["backtest"]


class BacktestRequest(BaseModel):
    symbol: str = Field(..., description="Trading pair, e.g. BTC/USDT")
    timeframe: str = Field("1h", description="Candle timeframe (ccxt format)")
    exchange: str = Field(DEFAULT_EXCHANGE, description="Exchange identifier")
    start: datetime = Field(..., description="Inclusive start of the simulation window")
    end: datetime = Field(..., description="Exclusive end of the simulation window")
    initial_capital: float = Field(10000.0, gt=0)
    risk_per_trade_pct: float = Field(1.5, gt=0)
    atr_stop_multiplier: float = Field(1.5, gt=0)
    target_r_multiple: float = Field(3.0, gt=0)
    max_concurrent_positions: int = Field(1, ge=1)
    side: Literal["long", "short", "both"] = Field("both")
    warmup_bars: int = Field(250, ge=50)


def _maybe_limit(handler):
    if limiter is not None:
        return limiter.limit(BACKTEST_RATE_LIMIT)(handler)
    return handler


@backtest_router.post("/", tags=tags)
@_maybe_limit
@has_errors
async def run_backtest(request: Request, payload: BacktestRequest):
    """Replay the RulesService strategy on historical OHLCV.

    Returns aggregate metrics, the full equity curve and the executed trades
    so the caller can render charts or feed an MCP-driven analysis loop.
    """
    svc = BacktestService(
        symbol=payload.symbol,
        timeframe=payload.timeframe,
        exchange=payload.exchange,
        start=payload.start,
        end=payload.end,
        initial_capital=payload.initial_capital,
        risk_per_trade_pct=payload.risk_per_trade_pct,
        atr_stop_multiplier=payload.atr_stop_multiplier,
        target_r_multiple=payload.target_r_multiple,
        max_concurrent_positions=payload.max_concurrent_positions,
        side=payload.side,
        warmup_bars=payload.warmup_bars,
    )
    return svc.run()
