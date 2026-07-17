from fastapi import APIRouter, Query
from middlewares import has_errors

from controllers.metrics.market_data_service import DEFAULT_EXCHANGE
from controllers.metrics.setup_evaluation_service import SetupEvaluationService

setups_router = APIRouter()

tags = ["setups"]


@setups_router.get("/evaluate", tags=tags)
@has_errors
async def evaluate_setups(
    symbol: str = Query(..., description="Trading pair, e.g. BTC/USDT"),
    exchange: str = Query(DEFAULT_EXCHANGE, description="Exchange: binance, bitget"),
    rule_version: str | None = Query(
        None,
        description=(
            "Rule-version override for this evaluation (0.1.0 | 0.2.0). "
            "Default: RULE_VERSION env, itself defaulting to 0.1.0. The 0.2.0 "
            "pack is a CANDIDATE gated on the spec §I.6 replay — additive "
            "monitor blocks only, the setups contract is unchanged."
        ),
    ),
):
    """Evaluate every declarative setup at the last CLOSED candle.

    Runs the F0 multi-TF engine (PB-1D-LONG/SHORT, IMP-4H-LONG/SHORT) live:
    closed candles only (no repaint, spec §0.1), context frames aligned with
    the §0.2 no-lookahead rule, evaluation order invalidation -> context ->
    trigger -> vetoes (spec §B.0).

    Returns
    -------
    dict
        `{symbol, rule_version, evaluated_at, setups[]}` where each setup
        carries `status` (no_context | context_ok | triggered | vetoed |
        invalidated), the per-condition breakdown (context / trigger /
        invalidation), the veto states, the confirming `adx_turn_grade`
        (A | B | null) and last-closed-candle `evidence`.
    """
    service = SetupEvaluationService(
        symbol=symbol, exchange=exchange, rule_version=rule_version
    )
    return service.evaluate()
