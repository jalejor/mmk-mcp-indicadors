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

## D15 — R-TURN-IGNITION: E1's standalone persist-only surface (2026-07-25)

`monitors_v020.py` emits an additive `turn_ignition` block (rule_version
0.2.x): the E1 grade-A "90-degree" ADX turn finally speaks on its own instead
of only as confirmation of a fresh AO zero-cross (diagnosis 2026-07-25: the
real 2026-07-23 BTC turn produced ZERO audible signals because the AO cross was
20 candles old). Pre-registered spec — do not widen ad hoc, changes invalidate
the forward gate: TFs 1h/4h; variants `up_bullish`/`up_bearish` grade A only
(origin in [12, 20]; `down` = strength collapse, excluded); confluence 2-of-3
read on the FIRE candle (AO side-or-|AO|-expanding>=2 / BBWP>50-or-rising>=2 /
Konkorde marron side, the Konkorde leg 4h-only). Emission discipline mirrors
the other monitors: terminal freshness <= 6 candles, identity = fire candle
close ts (consumer dedups one-shot per candle), `shadow: true, alertable:
false` — the watcher persists, NEVER pushes. Ignition gate (pre-registered):
n >= 30 forward events, favorable >= 0.60 (SHADOW_OUTCOME_* yardstick, mmk-api),
>= 30 days shadow -> re-council. Goldens pinned in
`tests/test_turn_ignition_monitor.py`.

## D16 — p_false priors are `not_established`, not reverted (2026-08-16)

The §I.9d pre-registered ignition gate ran and **FAILED**: forward FEC contrary
hit-rate 41.4% (n=162) vs the required >= 0.60. Its written consequence was
"revert the priors to 0.80 / 0.70 / 0.65", and the re-council **declined** to
execute it: those are owner priors that were never measured, so reverting
trades one unsupported number for another. The 0.2.1 replay values (0.70 /
0.40 / 0.42) could not be defended either — ~70% of that replay used a
different yardstick and its harness was never committed, so they are
irreproducible.

**Decision**: `p_false_prior`, `p_false_color` and `p_false_ignition` are
`Optional[float] = None` in `rule_v020.py`. The state machines are untouched —
an adjudication still fires, it just carries no probability; `state` and
`color_flip_age` carry the distinctions `p_false` used to encode. Consumers
render a missing value as unknown, never as `0`. Historical alert docs in
Mongo keep their old `p_false` (a record of what was emitted).

**Alternative discarded**: reverting to the owner priors — see above. Also
discarded: leaving the replay values in place with a caveat, since an
irreproducible number in versioned rule data is indistinguishable from a
measured one to every consumer.

**Re-opening it** requires all five §I.9d gates on the next yardstick:
versioning+goldens resolved, a control group, the metric expressed in **R**,
the threshold normalized by ATR and timeframe, and the harness committed
in-repo with its manifest.

**Extended to v0.1.0 the same day** (owner-approved, second PR): the pending
item this entry left open — `setup_service.FalseEntryParams.p_false_prior =
0.70` — is now `Optional[float] = None` too. It was the same never-measured
owner prior (Q17), and v0.1.0 is the pack behind the AUDIBLE surface
(`RULE_VERSION` defaults to `0.1.0`), so the only number a trader actually
heard was the only unmeasured one left. **No `p_false` in this repo carries a
number under any rule_version now.**

The "v0.1.0 stays byte-identical" objection was resolved, not waived: the
amendment REMOVES rule data instead of substituting a different value, so
nothing recomputes — `FALSE_ENTRY_PROBABLE` still adjudicates at
`event_age == confirm_candles`, only the probability field goes unset. The
`rule_version` labels stay put and the change is registered in the spec §0.4
amendment table; whether a *returning* number needs a bump is deferred to
§I.9d requirement #1 (resolve rule versioning + goldens), which must be
answered before the next measurement runs.

**Status**: vigente, closed end-to-end (both packs).
