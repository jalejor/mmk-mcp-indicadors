# Decisions

Non-obvious design choices and the reasoning behind them, reconstructed from the
code, comments and git history (commit `58ee03e` "fases 1-5" and the four
follow-up fixes).

## D1 — Default exchange is `bitget`, not `binance`

`MarketDataService.DEFAULT_EXCHANGE = getenv("DEFAULT_EXCHANGE", "bitget")`.
Binance geo-blocks US IPs (HTTP 451) and every Cloud Run deployment lives in a
US region (`us-west1`), so binance would fail from production. `bitget` is the
safe code default; binance can still be selected per-request or via env.

> ⚠️ The API docs still say the default is `binance`. See
> [known-errors.md](known-errors.md#e1).

## D2 — In-process TTL cache instead of Redis

Public OHLCV calls are rate-limited and slow (hundreds of ms). Rather than add
Redis, market data is cached in a **class-level `cachetools.TTLCache`** shared
across instances, keyed by `(exchange, symbol, timeframe, limit)`, capped at 256
entries. TTL ≈ half the candle duration, so an in-flight candle is refreshed but
closed candles (immutable) are reused. A coarse `threading.Lock` guards the
cache because ccxt is synchronous. Cache hits return a defensive `.copy()`.

## D3 — Same compute for HTTP and MCP, so MCP must enforce the same auth

The MCP tools run the identical ccxt/indicator compute as the protected
`/v1/*` routes. Because Cloud Run is deployed `--allow-unauthenticated`, an
unauthenticated MCP mount would hand anonymous callers the full compute — this
was a real **P0** (fixed in `db4a0e8`). The fix passes
`AuthConfig(dependencies=[Depends(api_key_dependency)])` so the fork applies the
`X-API-Key` check to **both** MCP endpoints (SSE `GET` handshake and `POST
/messages/`). Guarded by the regression test `test_mcp_auth.py`.

## D4 — Auth disabled when `API_KEYS` is unset

`api_key_dependency` returns immediately if `API_KEYS` is empty/unset. This makes
local development and the offline test suite friction-free, while production
injects `API_KEYS` from Secret Manager (`cloudbuild.yaml`
`--set-secrets=API_KEYS=mmk-api-keys:latest`). The same "disabled in dev"
behaviour intentionally applies to the MCP transport.

## D5 — Fork of `fastapi-mcp` (am1ter)

The upstream `fastapi-mcp` mishandles FastAPI's `root_path` (upstream PR #163),
which breaks routing when served under a non-root prefix like `/v1`. The project
pins the `am1ter/fastapi_mcp` fork (`requirements.txt` pins a specific commit)
that fixes this and additionally applies auth to both MCP endpoints.

## D6 — Konkorde lines re-centred on zero (bias fix)

`_calc_konkorde` subtracts `50` from the RSI and MFI components before averaging
them with the already 0-centred oscillators (B1, OscP, OscN). Before this fix
(commit `65be83d`) the brown (`marron`) line floated at ~+25 in a flat market
(a 0–100 series averaged with 0-centred ones), which `RulesService` read as a
**permanent `konkorde_buy` vote at weight 3.0** — a structural bullish bias.
Now a neutral market scores ~0. Pinned by `test_konkorde_golden.py`. The rules
engine still keys off `konkorde_value`, kept as a **deprecated alias** of
`konkorde_marron` for backward compatibility.

## D7 — Weighted, regime-aware voting (not a simple vote count)

`RulesService` assigns a weight per indicator family (Konkorde 3.0, AO/ADX 2.0,
MACD 1.5, …) and detects a **market regime** (compression / exhaustion /
trending / ranging / transitional) from BBWP and ADX. The regime biases the
weights (e.g. `trending` ×1.5 ADX; `ranging` ×1.5 RSI/Stoch-RSI) and
**`compression` suppresses signals entirely** — a compressed market precedes a
breakout of unknown direction, so acting is unsafe. A signal fires only when the
winning side's score ≥ `max(4.0, 0.6 × total_score)` and beats the other side.

## D8 — ATR-based sizing is the default; percent is legacy

`MovementsService` defaults to `use_atr_sizing=True` (FASE 3): stops are
`atr_mult_stop × ATR(14)` from entry, targets are `r_multiple × stop_distance`,
and quantity is sized so a full stop-out loses exactly `risk_per_trade_pct` of
capital. This mirrors how the user actually trades. The older
fixed-`(target_pct, stop_pct)` path is retained (`use_atr_sizing=False`) so old
API consumers keep working — but note it returns a **different response schema**.
When ATR can't be computed the ATR path **falls back** to percent mode and sets
`atr_fallback: true`.

## D9 — Single source of truth for sizing (live == backtest)

`sizing_profiles.py` holds `ATR_PROFILES` and `RISK_PROFILES`, imported by both
`MovementsService` and `BacktestService` (commit `1237477`). Previously the two
engines used different formulas (live derived mult/R from the profile; backtest
used fixed 1.5/3.0), so a backtest only validated the live recommendation for
`risk_profile="medium"`. Now `low/medium/high` map to `(1.0,2.0)/(1.5,3.0)/
(2.0,4.0)` in both, so the same `symbol + ATR + equity + risk_profile` yields an
identical stop/target/quantity. Pinned by `test_sizing_parity.py`. `medium` MUST
stay `(1.5, 3.0)` to preserve historical golden numbers.

## D10 — Backtest realism choices

- **No peek-ahead**: at bar `i`, only `df.iloc[: i+1]` is passed to the indicator
  and rule services.
- **Open trades are managed before new entries** on the same bar, so a bar can't
  both open and close a position with look-ahead.
- **Stop-before-target tie-break**: if a single bar's range hits both the stop
  and the target, the **stop is assumed to fire first** (worst case).
- **Warm-up**: `warmup_bars` (≥50, default 250) of history are fetched before
  `start` and used only to prime indicators, never traded.
- Metrics are **pure Python** (no extra deps) so results are JSON-serialisable
  for the HTTP and MCP layers.

## D11 — Stateless, no database

There is no persistence layer. Every request recomputes from live/cached market
data. `pymongo`/`redis` appear in the generated `requirements.txt` but are not
imported anywhere — the service is intentionally stateless (see
[known-errors.md](known-errors.md)).

## D12 — Hardened container & least privilege

The `Dockerfile` runtime stage runs as a **non-root** user, ships only resolved
wheels + source, and defines a `HEALTHCHECK` on `/v1/healthy`. `docker-compose`
runs the container `read_only: true` with a `tmpfs` `/tmp`. CORS uses
`allow_credentials=False` because auth is a header (no cookies), which keeps the
wildcard-origin default valid.

## D13 — Richer `/healthy` that probes the exchange

`/liveness` returns immediately (process up). `/healthy` additionally probes the
default exchange's ticker with a bounded timeout (`HEALTH_EXCHANGE_TIMEOUT`, 3 s)
in a worker thread; on failure it downgrades `status` to `degraded` so the load
balancer can route away while the process keeps serving. Both are excluded from
the OpenAPI schema and from access-log noise.

## D14 — F0 multi-TF setup engine is a layer ABOVE RulesService (2026-07-07)

`setup_service.py` + `setup_definitions.py` + `setup_backtest_service.py`
implement STRATEGY_SETUPS_SPEC.md (rule_version 0.1.0): the owner's elements
E1–E5 as pure functions on closed-candle series, declarative versioned setups
(PB-1D / IMP-4H, longs + mirrored shorts), timeframe bands (low_tf < 4h without
Konkorde), V1/V2 false-entry vetoes (windows = 5, owner Q10), and a multi-TF
backtest with fees (bitget base 0.10% + 0.05% slippage per side), 70/30 IS/OOS
and counterfactual veto replay. RulesService and the legacy BacktestService are
deliberately untouched (they keep serving the existing `/v1` endpoints; E5
coexistence with the legacy 20/80 pends owner Q5). The live path now evaluates
CLOSED candles only: `get_ohlcv(drop_forming=True)` is the default; charts opt
out. Gate runner: `scripts/run_f0_backtest.py` (Docker-only). E6/E7 are parked
post-gate. Backtest indicators are precomputed once over the full series (all
causal), giving O(n) replays.
