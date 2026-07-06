# Known errors & documentation contradictions

Issues found during the 2026-07-05 read-only review: likely bugs, contradictions
between the code and the repo docs, and traps. **Nothing here was fixed** — this
is a findings log. Severity is the reviewer's estimate.

Legend: 🐞 likely bug · 📄 doc contradiction · ⚠️ trap / sharp edge.

---

<a id="e1"></a>
## E1 📄 Default exchange: docs say `binance`, code uses `bitget` — HIGH

`MarketDataService.DEFAULT_EXCHANGE = getenv("DEFAULT_EXCHANGE", "bitget")`
(`src/controllers/metrics/market_data_service.py:59`), and every route defaults
its `exchange` query param to this value. But `docs/API_DOCUMENTATION.md`
repeatedly states the default is `"binance"` (metrics, averages, movements,
dominance, charts). The code default is intentional (binance geo-blocks the US
Cloud Run region — see [decisions.md](decisions.md#d1)); the **docs are stale**.
A caller relying on the docs would get bitget data, not binance.

**Fix direction**: update `API_DOCUMENTATION.md` to state the default is
`bitget`.

---

<a id="e2"></a>
## E2 🐞 Chart `span` in months (`1M`/`3M`/`6M`) always fails — HIGH

`ChartService._span_to_timedelta` (`src/controllers/metrics/chart_service.py:249`)
does:

```python
match = re.fullmatch(r"(\d+)([hdwM])", span.strip().lower())
```

It **lower-cases the whole span first**, so any `M` (months) becomes `m`, which
is **not** in the character class `[hdwM]`. Every month span therefore raises
`"Formato de span inválido"`. Yet `1M`, `3M`, `6M` are explicitly advertised for
this endpoint in:

- the route docstring and `Query` description in `src/routes/v1/chart_routing.py`
  (`span` default group lists `1M, 3M, 6M`), and
- `docs/API_DOCUMENTATION.md` ("Meses: `1M`, `3M`, `6M`, `1y`").

`1y` is documented but supported by **no** regex either. Consequence: any
charts request using a month/year span 400s.

**Fix direction**: match case-sensitively (drop `.lower()` or normalise only the
digits), and decide the semantics of `m` vs `M` explicitly. Note `AveragesService`
uses lowercase `m` for months, so the two services disagree — see E7.

---

<a id="e3"></a>
## E3 📄 BBWP thresholds: docs say `4.0 / 1.5`, code uses `80 / 20` — MEDIUM

BBWP is now computed as a **0–100 percentile**
(`IndicatorsService._calc_bbwp`), so `RulesService.DEFAULT_THRESHOLDS` correctly
uses `bbwp_high = 80.0`, `bbwp_low = 20.0`. But the docs still reflect the old
raw-band-width scale:

- `docs/API_DOCUMENTATION.md` env section: `BBWP_HIGH=4.0`, `BBWP_LOW=1.5`.
- `docs/ENVIRONMENT_VARIABLES.md`: `BBWP_HIGH` default `4`, and `BBWP_LOW` is not
  listed at all.

Anyone setting `BBWP_HIGH=4` per the docs would put the "exhaustion" threshold at
a 4th-percentile reading, firing exhaustion almost constantly and breaking regime
detection.

**Fix direction**: update both docs to the percentile scale (80/20) and add
`BBWP_LOW`.

---

<a id="e4"></a>
## E4 📄 `konkorde_signal` example value never emitted — LOW

`IndicatorsService._classify_konkorde` only ever returns `bullish_strong`,
`bullish_weak`, `bearish_strong`, `bearish_weak`, or `neutral`. The
`docs/API_DOCUMENTATION.md` example response shows `"konkorde_signal":
"bullish"`, a value the code never produces. Consumers pattern-matching on the
documented string will never match.

**Fix direction**: update the doc example to one of the real values.

---

<a id="e5"></a>
## E5 📄 `ENVIRONMENT_VARIABLES.md` / `.env.example` badly out of sync — MEDIUM

Multiple mismatches between the env docs and what the code actually reads:

- **`PREFIX_PATH`**: docs default `/prefix`; code default `/v1`
  (`web_server.py:22`).
- **`PORT`**: docs default `8000`; code default `3000`
  (`web_server.py:157`). (Docker/compose set 8000, so prod is 8000, but the code
  default and doc disagree.)
- **`DD_SERVICE` / `DD_VERSION`**: documented and present in `.env.example`, but
  **no code reads them**. The code uses `APP_ID` and `APP_VERSION` instead
  (`web_server.py:20-21`, `healthy_controller.py:20-21`). There is no Datadog
  integration in the repo.
- **Undocumented but consumed**: `API_KEYS`, `RATE_LIMIT_DEFAULT`,
  `RATE_LIMIT_BACKTEST`, `DEFAULT_EXCHANGE`, `CORS_ORIGINS`, `LOG_FORMAT`,
  `LOG_CONFIG_PATH`, `APP_ID`, `APP_VERSION`, `HEALTH_EXCHANGE_TIMEOUT`,
  `BBWP_LOW`, per-symbol threshold overrides, and `<FAMILY>_WEIGHT` overrides.

**Fix direction**: regenerate the env docs from the actual `getenv` call sites
(see the table in [workflow.md](workflow.md)).

---

<a id="e6"></a>
## E6 ⚠️ `ASGI_ENV=development` silently prevents the server from starting — MEDIUM

`web_server.py` defines `_DEVELOPMENT_ENV = 'development'` and
`launch_asgi_server` guards the uvicorn call with
`if _ASGI_ENV != _DEVELOPMENT_ENV:`. So with `ASGI_ENV=development`, `main()`
builds the app and returns **without ever calling `uvicorn.run`** — the process
exits and nothing serves. Everywhere else the codebase uses `ASGI_ENV` values of
`local` / `docker` / `prod`, never `development`, so this branch is a latent
trap: a reasonable-looking value silently no-ops the server. (It also means
`start_fastapi`'s `local` vs non-`local` `root_path` logic and this
`development` gate key off the same var with different vocabularies.)

**Fix direction**: either remove the dead `development` gate or make the "don't
serve, just build" mode explicit (e.g. a dedicated `SERVE=false`), and align the
`ASGI_ENV` vocabulary.

---

<a id="e7"></a>
## E7 ⚠️ `span` unit letters differ between endpoints — MEDIUM

- `AveragesService._span_to_timedelta`: regex `[hdwm]`, where **`m` = months**
  (~30 days).
- `ChartService._span_to_timedelta`: regex `[hdwM]`, where **`M` = months** and
  lowercase `m` is unsupported (and, per E2, `M` is also broken by `.lower()`).

So `span=1m` means "1 month" on `/v1/averages` but is **invalid** on
`/v1/charts`, and `span=1M` is valid syntax only on charts (but then fails at
runtime). This is an easy caller mistake and there is no shared span parser.

**Fix direction**: extract one shared span parser with a single, documented unit
convention.

---

<a id="e8"></a>
## E8 ⚠️ Large `span` / long backfill silently truncated by candle limits — MEDIUM

`AveragesService._load_market_data` fetches at most `candles_limit` (default
**1500**) of the *most recent* candles and then filters
`df.loc[self.start:self.end]`. `ChartService._fetch_chart_data` caps each fetch
at the timeframe's `max_candles` (**1000**). If the requested range needs more
candles than the cap (e.g. `span=1m` on `15m` bars ≈ 2880 candles), the older
part of the window is silently missing — averages/rebound are computed on a
truncated range with no warning to the caller. (The dedicated `BacktestService`
avoids this by paginating with `since`; the read endpoints do not.)

**Fix direction**: paginate these fetches like the backtest engine, or return an
explicit "range truncated" indicator.

---

<a id="e9"></a>
## E9 ⚠️ Legacy percent sizing returns a different response schema — LOW

`MovementsService` returns ATR-shaped side dicts (`stop_distance`,
`position_size_usd`, `dollar_risk`, `r_multiple`, …) when `use_atr_sizing=True`
(default), but a different set (`target_pct`, `risk_reward_ratio`, no ATR fields)
when `use_atr_sizing=False` **or** when ATR can't be computed and the code falls
back to percent mode (`atr_fallback: true`). Clients must handle both shapes.
The `docs/API_DOCUMENTATION.md` movements example shows the **percent** schema
(`target_pct`, `risk_reward_ratio`), which is not the default response.

**Fix direction**: document both response shapes and the `atr_fallback` flag.

---

<a id="e10"></a>
## E10 📄 Top-level `README.md` / `README_ES.md` are the unmodified template — LOW

Both READMEs still describe the generic "DevOps FastAPI MCP Template": they show
a non-existent example endpoint (`/prefix/v1/codes/get/{code}`), a
`controllers/codes/` folder that does not exist, ports 3000/8000, and none of the
actual trading endpoints. The real API is documented only in
`docs/API_DOCUMENTATION.md`. New contributors reading the README get a misleading
picture of the service.

**Fix direction**: rewrite the READMEs for the indicators service (or point them
at `docs/API_DOCUMENTATION.md` and this `docs/context/` set).

---

<a id="e11"></a>
## E11 ⚠️ Unused heavy dependencies in `requirements.txt` — LOW

The PDM-generated `requirements.txt` pins `pymongo`, `redis` and `uuid`, but no
module imports any of them (the service is intentionally stateless — see
[decisions.md](decisions.md#d11)). They are dead weight in the runtime image (and
`uuid` is a very old PyPI backport that shadows the stdlib name).

**Fix direction**: confirm they are truly transitive-only and prune the direct
deps; drop the `uuid` pin.

---

<a id="e12"></a>
## E12 ⚠️ `@has_errors` returns 400/500 with key `error`, some docs show `detail` — LOW

The `@has_errors` decorator (`src/middlewares.py`) returns
`{"error": str(e)}` for both 400 and 500. `docs/API_DOCUMENTATION.md`'s "Ejemplo
de Error" shows `{"detail": "..."}` (FastAPI's native shape). Rate-limit 429s use
yet another shape `{"error": ..., "detail": ...}` (`security.py`). Error payloads
are therefore inconsistent across the surface.

**Fix direction**: standardise the error envelope and document it.

---

## Non-issues / verified-correct (for reassurance)

- **MCP auth**: the mounted MCP transport *does* enforce the API key on both
  endpoints (guarded by `test_mcp_auth.py`) — the prior P0 is fixed.
- **Live vs backtest sizing parity**: verified identical for low/medium/high via
  the shared `sizing_profiles` table (`test_sizing_parity.py`).
- **Konkorde neutral bias**: re-centred; a flat market scores ~0 and emits no
  buy vote (`test_konkorde_golden.py`).
- **Backtest no-peek-ahead**: at bar `i` only `df.iloc[: i+1]` is visible;
  open trades are settled before new entries; stop-before-target worst-case
  tie-break.
