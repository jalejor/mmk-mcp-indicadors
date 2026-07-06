# Architecture

## Purpose

A stateless HTTP + MCP service that turns exchange OHLCV data into technical
indicators, trading signals, position-sizing recommendations and backtests. It
is a single Python process; there is **no database** and no background worker.

## High-level shape

```
                         ┌─────────────────────────────┐
   HTTP client  ───────► │        FastAPI app          │
   (curl / UI)           │  (src/web_server.py)        │
                         │                             │
   MCP client   ───────► │  fastapi-mcp mount (SSE)    │
   (Cursor via           │  (src/mcp_server.py)        │
    mcp-proxy)           └──────────────┬──────────────┘
                                        │
                       Routing layer (src/routes/**)
                                        │
                       Service layer (src/controllers/metrics/**)
                                        │
                 ┌──────────────────────┼───────────────────────┐
                 ▼                      ▼                        ▼
          ccxt exchanges        CoinGecko global API      in-process TTL cache
        (binance / bitget)      (market-cap dominance)   (cachetools, market data)
```

## Layers

The code is organised in three layers (see `docs/API_DOCUMENTATION.md`):

1. **Routing layer** — `src/routes/`. Declares FastAPI routers, parses/validates
   query and body parameters, wires auth and rate-limit dependencies. Thin: it
   only constructs a service and returns its result.
2. **Service layer** — `src/controllers/metrics/`. All business logic and math.
   Each service is a self-contained class instantiated per request.
3. **Data layer** — reached from the service layer: `MarketDataService` (ccxt),
   `DominanceService` (CoinGecko HTTP), and the shared in-process cache.

> Naming note: the top-level package is called `controllers/`, but the metrics
> classes inside it are really **services** (they end in `Service`). The only
> true "controller" is `MetricsController`, which orchestrates
> market-data → indicators → rules. See [conventions.md](conventions.md).

## Entry point & startup

`src/main.py` → `main()`:

1. `start_fastapi()` (`web_server.py`) — builds the `FastAPI` app: installs JSON
   logging (optional), CORS, security (rate limiting), the per-request log
   middleware, and includes the router tree.
2. `start_mcp(app)` (`mcp_server.py`) — mounts the MCP transport over the same
   app, guarded by the same API-key dependency.
3. `launch_asgi_server(app)` — runs uvicorn.

`root_path` and the docs/openapi URLs depend on `ASGI_ENV`: when `local` the app
serves at `/`; otherwise it is served under `PREFIX_PATH` (default `/v1`), which
matches how Cloud Run fronts the service.

## Routing tree

`src/routes/__init__.py` mounts:

- `healthy_router` — **public** (`/`, `/healthy`, `/liveness`), not in schema.
- `api_v1` under prefix `/v1`, with `Depends(api_key_dependency)` applied to the
  whole subtree.

`src/routes/v1/__init__.py` mounts the feature routers under `/v1`:

| Prefix | Router | Service | Verb |
| ------ | ------ | ------- | ---- |
| `/v1/metrics` | `metrics_routing` | `MetricsController` | `GET /get` |
| `/v1/dominance` | `dominance_routing` | `DominanceService` + `MetricsController` | `GET /` |
| `/v1/averages` | `averages_routing` | `AveragesService` | `GET /` |
| `/v1/movements` | `movements_routing` | `MovementsService` | `GET /` |
| `/v1/charts` | `chart_routing` | `ChartService` | `GET /`, `GET /timeframes` |
| `/v1/backtest` | `backtest_routing` | `BacktestService` | `POST /` |

## Services (src/controllers/metrics)

- **`MarketDataService`** — OHLCV fetcher over ccxt, backed by a shared,
  class-level `cachetools.TTLCache` keyed by `(exchange, symbol, timeframe,
  limit)`. TTL ≈ half the candle duration. Returns defensive copies of the
  DataFrame. Supports `binance` and `bitget` (spot). Default exchange is
  `bitget` (see [decisions.md](decisions.md)).
- **`IndicatorsService`** — computes the full indicator set on a price
  DataFrame (RSI, ADX/±DI, BBW/BBWP, AO, SMA/EMA 50/200, Konkorde, MACD,
  Stoch-RSI, ATR, realised volatility) and returns the latest-candle values.
- **`RulesService`** — turns the indicator dict into a weighted, regime-aware
  vote and emits an `entry` / `exit` / `neutral` signal plus human-readable
  explanations (Spanish).
- **`MetricsController`** — orchestrates market-data → indicators → rules into
  the `/v1/metrics/get` payload; also reused by `/v1/dominance`.
- **`MovementsService`** — long/short trade plan with ATR-based sizing (default)
  or legacy fixed-percentage sizing.
- **`BacktestService`** — event-loop replay of the `RulesService` strategy over
  historical OHLCV with strict no-peek-ahead and equity/metrics output. Shares
  the sizing table with `MovementsService`.
- **`AveragesService`** — indicator averages + biggest single-candle rebound in
  a range.
- **`ChartService`** — OHLCV shaped for charting with automatic timeframe
  selection and fallback.
- **`DominanceService`** — global market-cap dominance from CoinGecko.
- **`sizing_profiles`** — single source of truth for risk-profile → (ATR mult,
  R multiple) and legacy (target %, stop %) tables, shared by the live and
  backtest engines.

## Cross-cutting concerns

- **Auth** — `src/security.py`: `X-API-Key` header validated against the
  `API_KEYS` env var (comma-separated). Empty/unset ⇒ auth disabled (dev mode).
  Applied to the whole `/v1` subtree and to the MCP transport.
- **Rate limiting** — `slowapi`, default `60/minute` per client IP; backtest is
  `5/minute`. Gracefully degrades to a no-op if slowapi is unavailable.
- **Error handling** — `src/middlewares.py` `@has_errors` decorator wraps route
  handlers: `ValueError` → HTTP 400, any other exception → HTTP 500, both as
  `{"error": "..."}` JSON.
- **Logging** — one structured log line per request (`mmk.requests`), never
  logging headers/body (may contain API keys). Optional JSON formatter when
  `LOG_FORMAT=json`. uvicorn access noise for health/docs paths is filtered.
- **MCP** — `fastapi-mcp` (the `am1ter` fork, for a `root_path` fix) exposes the
  HTTP operations as MCP tools over SSE at `<prefix>/mcp`.

## External dependencies

- **ccxt** (`4.2.97`) — exchange OHLCV/ticker data (binance, bitget).
- **CoinGecko** `/api/v3/global` — market-cap dominance (no key, 10 s timeout).
- **pandas / pandas-ta-classic** — dataframe math and indicators.
- **fastapi-mcp** (am1ter fork) — MCP transport.
- **slowapi**, **cachetools**, **pyyaml**, **uvicorn**.

Note: `requirements.txt` (PDM-generated) also lists `pymongo`, `redis` and
`uuid`, but no code imports them — they are transitive/left-over and not used by
the service. See [known-errors.md](known-errors.md).

## Deployment topology

Containerised (multi-stage `Dockerfile`, non-root, `HEALTHCHECK` on
`/v1/healthy`). CI/CD via `cloudbuild.yaml`: **test → build (kaniko) → deploy**
to Google Cloud Run (`us-west1`, `--allow-unauthenticated`, `max-instances=2`,
`API_KEYS` injected from Secret Manager). Because Cloud Run is public, API-key
auth is the only access control — hence the emphasis on gating both HTTP and MCP.
