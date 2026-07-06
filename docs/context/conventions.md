# Conventions

Patterns observed across the codebase. Follow these when extending it.

## Language

- **Code, identifiers, and most docstrings**: mixed. Newer modules
  (`security.py`, `web_server.py`, `market_data_service.py`, `backtest_service.py`,
  `mcp_server.py`) are in **English**; older ones (`averages_service.py`,
  `chart_service.py`, `dominance_service.py`, docstrings in routes) are in
  **Spanish**.
- **User-facing signal explanations** (`RulesService._explanations`) and the
  `reasons` returned by `MovementsService` are **Spanish** — they are product
  copy shown to the trader.
- **API error messages** are Spanish (`"Exchange no soportado: ..."`,
  `"No hay suficientes velas ..."`).
- The two top-level READMEs and `docs/API_DOCUMENTATION.md` are English/Spanish
  respectively; `ENVIRONMENT_VARIABLES.md` is Spanish.
- **This `docs/context/` review is written in English** per the review task.

## Project layout

```
src/
  controllers/
    healthy_controller.py         # health/liveness/root helpers
    metrics/
      market_data_service.py      # ccxt OHLCV + TTL cache
      indicators_service.py       # all indicator math
      rules_service.py            # weighted, regime-aware voting
      metrics_controller.py       # orchestrates the metrics payload
      movements_service.py        # long/short trade plans (ATR / pct)
      backtest_service.py         # historical replay engine
      averages_service.py         # range averages + rebound
      chart_service.py            # chart-shaped OHLCV
      dominance_service.py        # CoinGecko dominance
      sizing_profiles.py          # shared risk-profile tables
  routes/
    healthy.py                    # public health routes
    v1/<feature>_routing.py       # one router per feature
  main.py                         # entry point
  web_server.py                   # FastAPI + logging + CORS
  mcp_server.py                   # MCP mount
  security.py                     # auth + rate limiting
  middlewares.py                  # @has_errors decorator
  log_conf.yaml                   # uvicorn logging config
```

### Adding a new feature endpoint

1. Add a `Service` class in `src/controllers/metrics/`. Constructor takes
   keyword-only args; a single `execute()` / `run()` / `process_*()` method
   returns a JSON-serialisable `dict`.
2. Add a router in `src/routes/v1/<feature>_routing.py`. Decorate the handler
   with `@has_errors`. Default `exchange` to `DEFAULT_EXCHANGE`.
3. Register it in `src/routes/v1/__init__.py` with an explicit `prefix`.

## Coding style

- **Formatter**: `autopep8`; **lint**: `flake8` with `max-line-length = 150`,
  `max-complexity = 10`, `ignore = E402` (module-level imports after code are
  common because routers import services lazily / after `noqa: E402`).
- **Typing**: modern (`X | None`, `from __future__ import annotations`) in newer
  modules. `Literal` types for enumerated params (`risk_profile`, `side`).
- **Keyword-only constructors**: services use `def __init__(self, *, ...)` so
  call sites are explicit and order-independent.
- **Defensive numeric handling**: indicator helpers fall back to `NaN`/`0.0`
  rather than raising when a series is too short (`IndicatorsService._safe_last`,
  `try/except` around every pandas-ta call). This keeps warmup/short-window
  requests from 500-ing.
- **DataFrame immutability**: `MarketDataService` returns `.copy()` of cached
  frames; `IndicatorsService` copies the input df. Never mutate a caller's df.
- **No-peek-ahead in backtest**: at bar `i` only `df.iloc[: i + 1]` is visible.

## Configuration

- All config comes from **environment variables** read with `os.getenv(...)` and
  a default; there is no settings object. See [workflow.md](workflow.md) and
  `docs/ENVIRONMENT_VARIABLES.md` for the list (note the drifts flagged in
  [known-errors.md](known-errors.md)).
- Env values are defensively parsed: `PREFIX_PATH`, `PORT`, `HOST` strip inline
  `#` comments and whitespace (`value.split("#", 1)[0].strip()`), because
  `.env.example` uses trailing `# comment` annotations.
- Indicator **thresholds** and **weights** are layered (lowest→highest priority):
  code defaults → global env (`RSI_OVERSOLD`) → per-symbol env
  (`BTC_USDT_RSI_OVERSOLD`) → constructor argument. Per-symbol keys are the
  symbol with `/` → `_`, upper-cased.

## HTTP / API conventions

- Feature endpoints are **`GET`** with query params, except **backtest** which is
  **`POST`** with a Pydantic `BacktestRequest` body (it has many params and is
  rate-limited separately).
- Responses are plain `dict`s serialised by FastAPI; errors are
  `{"error": "..."}` via `@has_errors` (note: 400/500 use the key `error`,
  while some legacy docs show `detail`).
- Timeframes accept human aliases in metrics/dominance (`daily`→`1d`,
  `weekly`→`1w`, `monthly`→`1M`).
- Retrospective ranges use a **`span`** string (e.g. `48h`, `7d`, `2w`, `1m`)
  when `start`/`end` are omitted. Beware: `span` unit letters differ between
  services (see [known-errors.md](known-errors.md)).

## Testing conventions

- `pytest`, offline. Tests **never hit a real exchange**: they monkeypatch
  `_load_market_data` / `_load_history` or swap `svc.exchange` for a fake, and
  feed **synthetic OHLCV** (seeded `numpy` RNG) so runs are deterministic.
- **Golden tests** pin numeric behaviour: `test_konkorde_golden.py` (neutral
  market must score ~0 / no buy vote) and `test_sizing_parity.py` (live vs
  backtest sizing must be identical).
- Security/regression guards: `test_mcp_auth.py` asserts the MCP transport
  carries the API-key dependency; `test_security.py` covers the auth dependency.
- Test deps live in `tests/requirements-test.txt` (a runtime subset, no private
  packages), used by `Dockerfile.test`.

## Commit conventions

Conventional Commits with scopes, e.g.
`fix(konkorde): re-centre RSI/MFI on zero to remove bullish bias`,
`ci(cloudbuild): add pytest gate`. History mixes English and Spanish messages.
