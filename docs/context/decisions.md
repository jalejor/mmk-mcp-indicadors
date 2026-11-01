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

## D6 — Konkorde lines re-centred on zero (bias fix) — SUPERSEDED by D18

> ⚠️ Superseded 2026-11-01: the "re-centring" fixed a symptom of an indicator
> that was not Koncorde at all (see D18). Kept for the history of the rules.

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

## D17 — R-FEP-CONT pre-registered, measured, REFUTED; FEC/FEP archived (2026-08-22)

The 2026-08-16 re-council allowed the FEC/FEP family **one** redesign on one
condition: backtest-first — a falsifiable hypothesis and the PB-1D listón
written down **before** any new shadow window, deadline 2026-09-30. This is
that redesign, and it failed.

**Hypothesis**: state `FALSE_ENTRY_PROBABLE` (AO zero-cross surviving 5
candles with no favourable ADX turn and no opposite re-cross) is a
**continuation** signal in the direction of the cross — the owner's §J.1
reading and the shape of the 19.8% contrary rate. Tested one-sided: a
negative edge refutes it and does not become a fade rule.

**Method** — all five re-council blockers, in order: an unconditional
`BASE-RATE` control arm; the committed resolver
(`SetupBacktestService._simulate_outcome`) with numeric goldens and an
`outcome_vara` stamp; the metric in **net R**; the threshold normalised as
1.5 x ATR14 of the trigger TF; the harness committed in-repo with a sha256
manifest. Universe (4 majors, binance, 8 years), split (at the listón's own
`2024-02-05T09:36Z`), statistics (cluster bootstrap, seed 20260822) and the
five gate legs were frozen in `docs/PREREG_FEP_CONT_v0.3.0.md` at commit
`0154a40` **before the first number existed**. 1.04 M signals resolved.

**Result** (primary cell 1h, OOS, n=2,451): expectancy **-0.2249 R**, CI
[-0.299, -0.150]; edge over the control **+0.0227 R**, CI [-0.045, +0.092],
Holm p 0.566; portfolio **-167.5 R/yr** against a listón of +1.644 R/yr.
**4 of 5 legs FAIL.** The rule also fails its own gate on 30m, 4h and 1d, so
the verdict is not an artifact of the primary cell. Root cause is not the
strategy being "almost there": the unconditional control is worth ~**+0.04 R
gross on every timeframe** and the entire net loss is the fee drag that §4 of
the pre-registration stated in advance.

**Decision**: **the FEC/FEP family is archived.** No v0.4.0. False-entry
alerts stay prohibited until evidence arrives from a different source.
R-TURN-IGNITION (D15) is recommended for archive as an alertable candidate on
the same acta — its own forward run was 22.4% with a *negative mean
excursion*, which no change of yardstick can rescue, and the nearest arm this
study measured (`CONFIRMED`, ignition anchored on the AO cross) is +0.0007 R
over the coin on 1h. Freed cycles go to widening PB-1D's universe.

**Alternative discarded**: promoting the 1d cell (+0.3119 R OOS, +6.94 R/yr).
It clears the economics and stability legs but both its confidence intervals
include zero and its Holm-adjusted p is 0.227 — and promoting a secondary
timeframe because the primary failed is precisely the post-hoc selection that
produced the irreproducible 0.70. Also discarded: re-cutting this sample by
regime, session or symbol (pre-registration §10).

**Left open on purpose (untested, NOT refuted)**: this study fixes one exit
model (1.5 x ATR stop / 3R target). The acta's finding that 76.5% of FEC
cases touched the contrary move intravela and gave it back is a hypothesis
about **exits**, not entries; it survives this verdict and would need its own
pre-registration.

**What it takes to reopen anything in this family**: a new pre-registration
plus a run of the committed harness — which now exists, so the price is an
afternoon, not a quarter.

## D18 — Koncorde ported bar-exact from Blai5's Pine; BBWP = the owner's chart (2026-11-01)

The Konkorde audit (commit `406b69c`) found that the old `_calc_konkorde` was
not Koncorde: EMA255 of PVI/NVI, `azul` = PVI, no stochastic, RSI on close,
Bollinger at 2σ, and the D6 "re-centring" (−50) that patched a symptom. It is
now a Pine-exact port in `koncorde.py`: `pine_ema`, Wilder RSI, MFI on hlc3,
BollOsc 25/2 over 4σ, stoch 21/3 on ohlc4,
`marron = (RSI + MFI + BollOsc + stoc/3) / 2`, `verde = marron + oscp`,
`azul` = NVI oscillator, `media = EMA15(marron)`. Reconciled live against the
owner's TradingView on 1w: media 79.03 / verde 86.00 / BBWP 47.27.

Consequences:

* `konkorde_marron` is a 0–100 series, **not** centred on zero. `marron > 0`
  is not a usable condition: `RulesService` now votes marron vs media. The
  zero-crossing lines are `azul`, `oscp` (verde − marron) and `edge`
  (marron − media, Blai5's own signal).
* The owner's "yellow area" is `verde`.
* `bbwp` defaults to the TradingView series (`bbwp_definition="tv"`,
  The_Caretaker SMA13/256) for `/v1/metrics` and `/v1/charts`. The versioned
  packs keep `RULE_PACK_BBWP_DEFINITION = "legacy"` because their goldens were
  pinned on it; moving them is a rule-input change (spec §0.4: bump + goldens).
* `1M` now drops the forming candle (`_month_candle_close_ms`).
* E3 (`konkorde_zero_cross`) was pending re-specification by the owner —
  done in D22 (line = `konkorde_verde`).
* D6 is superseded.

**Known fallout (open)**: `test_konkorde_golden.py::test_marron_is_a_0_100_style_average_not_centred_on_zero`
returns NaN (its fixture has a constant ohlc4, so BollOsc is `na` by Pine
semantics) and `test_v020_real_goldens.py::test_c1_g1_bear_confluence...`
fails on the 4h Konkorde leg (v0.2.x reads the marron sign). Both need an
owner/analyst call, not a code tweak. (C1-G1: resolved by D22, passes on
verde.)

**Status**: vigente.

## D19 — Impulse engine v2 (impulsos-v2), additive to the legacy vote (2026-11-01)

The owner trades impulses in both directions; the legacy `RulesService` vote
cannot short and cannot see turns. `impulse_service.py` implements
`docs/impulsos-v2.md` (`rule_version = impulse-2.0.0`, 14 goldens in
`tests/fixtures/impulse_golden_cases.json`, pinned by
`tests/test_impulse_golden.py`).

Design:

* **Columns in, decision out.** `ImpulseEngine.evaluate(frames, position=…)`
  reads indicator columns only (`close, high, low, bbwp, konkorde_*, adx14,
  plus_di, minus_di, ao, macd, macd_signal, atr14`), so analyst goldens run
  without OHLCV. Every row is a closed candle; context frames are cut at the
  trigger close (§0.2), or use their last row when they carry no timestamps.
* **All thresholds are data** (`ImpulseParams`, spec names accepted through
  `from_mapping`); `ImpulseParams.for_profile` binds TFs, ATR stop and time
  stop from `trade_profiles.TRADE_PROFILES` — the single source mmk-api must
  mirror. `confirm_tf` is the guardian (first context TF).
* **Vectorised + O(n) replay.** Phases, votes, crosses, E1 turns and E2
  divergences are precomputed causally over the whole frame; `replay` only
  iterates the position state machine (17.2k 4h decisions in a few seconds).
  E2 is a vectorised re-implementation of `setup_service.ao_divergence`
  (same pivots, lookback, ttl, invalidation) because calling it per bar is
  O(n²).
* **Bands enforced at runtime** (§0.3): below 4h Konkorde never votes or
  feeds context bias, and the Konkorde leg of the owner's exit becomes the AO
  zero-cross (`exit_ao_cross_against`).
* **Additive surface.** New route `GET /v1/impulse/evaluate`; `/v1/metrics/get`
  only adds the `impulse` key when `impulse_profile` is passed, so the
  watcher's payload and latency are unchanged (pinned by a key-snapshot test).

**Alternatives discarded**: extending `RulesService` (it is the watcher's
contract and long-only by construction); reusing `SetupService` (declarative
condition packs, no position state, no exit chain); per-bar
`IndicatorsService` recomputation in replay (O(n²), and the indicators are
already causal).

**Status**: implemented, NOT active. Paper-first gates in spec §h; backtest per
spec §g by the backtest harness (`impulse_backtest.py`).

## D20 — Round 2 sequential machine + ML RSI as what TradingView really plots (2026-11-01)

Owner decisions 1-4 (`docs/impulsos-v2.md`): the strategy is not a vote —
Konkorde (`konkorde_verde`, the TV yellow area) and BBWP LEAD, AO / ADX /
MACD / RSI CONFIRM; PRO with re-buys (1300 USDT, 5x cross); ML RSI
[BackQuant] as a regime filter. `impulse_sequential.py` implements §R2 as
`model="sequential"` of the same `ImpulseEngine` (`ImpulseParams.sequential`,
`rule_version impulse-2.1.0`); the round-1 vote path is untouched and stays
the code default (API contract, `/v1/impulse/evaluate`); the live path takes
`model=sequential` opt-in.

Design choices:

* **Machine driven bar by bar** (`SequentialMachine.step(i, equity)`) so the
  backtest ledger feeds realised equity for sizing and can `force_flat` on an
  intrabar liquidation; `force_enter` gives the anchored replay of the
  owner's trade. `run()` is the constant-equity replay; `evaluate()` on the
  live path replays the fetched history (the machine owns its state).
* **Follower windows are the only IS-fitted parameters**, computed per FAMILY
  by `impulse_lead_time.family_windows` (R2.b formula) and frozen in
  `FITTED_WINDOWS` before the backtest (4h ao 2 / adx 4 / macd 3 / rsi 2; 1d
  3 / 3 / 2 / 5).
* **ML RSI port = percentiles, not k-means.** Reading the public Pine
  (`PUB;5377b888…`): `array.new_float(3)` + `array.push` grows the working
  arrays to 6 / 9 elements, every value lands in "cluster 3" and
  `array.get(centroids, 0 | 2)` reads the slots that `array.set` refreshes
  each bar with the 25th / 75th percentiles. The percentile port reproduces
  the owner's chart (59.76 / 44.09 vs 59.74 / 44.30); the described k-means
  does not (68.3 / 39.2). `threshold_method="percentile"` is therefore the
  default and `"kmeans"` is kept only for the record. The engine uses the
  CAUSAL trailing window (3001 values ending at the decision candle); the
  TV-anchored window is only used to measure repaint (4h: regime label differs
  on 5.7 % of bars).
* **Layered ledger** (`PositionLedger`): E16 per layer per side, funding on
  total notional, cross-margin liquidation checked intrabar, 1R = layer-1
  risk in USDT (2 % E0). The engine computes notionals; the ledger scores.

**Alternatives discarded**: making `sequential` the code default (breaks the
round-1 endpoint tests and the watcher contract for no gain while nothing
passes); porting the Pine's k-means "as described" (does not match the
owner's chart); tuning the smoothing to hit the owner's 40.07 value (read on
the forming candle — a parameter fit to a non-reproducible reading).

**Status**: built, backtested (`PREREG_IMPULSOS_v2_r2.md`, results in
`docs/impulsos-v2-backtest-r2.md`): **no cell passes** (4h long NO-PASS
−0.403 R; the rest INCONCLUSIVE). NOT active; nothing in paper.

## D21 — Round 5: entry filters are an opt-in gate on the frozen 2.2.0 chain, read twice (run + classifier) (2026-11-01)

After four rounds that changed the side rule and the exit chain without any
cell passing, round 5 (`impulse-2.3.0`, `impulse_sequential.r5_params`) tests
the ENTRY side: ONE filter per rule doc (`ImpulseParams.entry_filter`, six
members of `ENTRY_FILTERS`: ADX turn / A-grade origin `[12, 20]`, AO
divergence trigger / any TF, BBWP fresh ignition / from blue), evaluated on the
entry candle AFTER every 2.2.0 gate. `R5_OVERRIDES = R4_OVERRIDES + version`:
exits, books, windows and costs are byte-identical to 2.2.0, so the baseline
run reproduces round 4b trade for trade (checked mechanically by the harness).

Design choices:

* **Every ENTER reports all six flags** (`context.entry_filters`, reasons
  `entry_filter:<name>=0|1`) whatever filter is active, so one baseline run
  doubles as a classifier study (prereg §6b: KEEP / DROP / INCONCLUSIVE on the
  passed-vs-rejected split, IS and OOS). This is what keeps a round readable
  when every filtered cell falls under n 30 — which happened.
* **A failed gate keeps the alert alive** until its ttl (same as the BBWP /
  guardian / ML RSI gates), so a late ADX confirmation can still open inside its
  fitted window; `force_enter` bypasses the filter (anchored replays).
* **The two readings are expected to disagree** and both are reported: a
  filtered RUN changes which trades a single-position book takes (snipper
  `adx_turn` run +32.7 % vs its classifier DROP). Neither decides alone; §6a
  decides GO, §6b decides what to study next.

**Alternatives discarded**: stacking filters (a stacked rule is a new
pre-registration); fitting the ADX band or the divergence parameters on IS
(they are the owner's / spec constants); widening the window or pooling ETH/SOL
on 1h/4h inside this round (universe change = replication round).

**Status**: built, tested (`tests/test_impulse_r5.py`, suite 409 passed, 2
xfailed), backtested (`PREREG_IMPULSOS_v2_r5.md`, results
`docs/impulsos-v2-backtest-r5.md`): **no cell GO**; classifier on snipper 1h:
`adx_turn` DROP, `bbwp_fresh` DROP, `bbwp_fresh_blue` weak KEEP (passed ≈ 0 R,
rejected −0.39 R) = candidate requiring replication. NOT active; nothing in paper.

## D22 — E3 re-specified: the rule packs read `konkorde_verde` (rule_version 0.1.1 / 0.2.2) (2026-11-01)

Owner decision (d) of 2026-11-01 ("re-especificar E3: GO") on the line he
validated in decision 3 of impulsos-v2: the "Konkorde crossing zero" of his
chart is the yellow area = `konkorde_verde` (`marron + oscp`). Pre-registered
in spec §0.4 + §E3 (docs commit) BEFORE the code changed.

* **One pack constant.** `setup_service.RULE_PACK_KONKORDE_LINE =
  "konkorde_verde"` next to `RULE_PACK_BBWP_DEFINITION` (same precedent);
  every Konkorde SIGN / zero-CROSS read goes through it: E3 state
  (`konkorde_positive/negative`) and event (`zero_cross_age`), the V1
  freshness events, the v0.2.x C1 high-band leg and the M1 turn-ignition 4h
  leg. Semantics, params and veto windows are unchanged — only the input line.
* **Fail closed.** `konkorde_line_series(df)` raises `KeyError` on a frame
  without verde (setups); the v0.2.x legs read it through `_series_last` /
  `_turn_tail` and report `false`. A frame without the line never votes.
* **Versioning.** `RULE_VERSION` 0.1.0 → 0.1.1 (new default), 0.2.2 added to
  the v0.2 pack. 0.1.0 / 0.2.0 / 0.2.1 stay selectable, run the SAME code and
  are echoed back verbatim; as shipped they read a re-centred marron (D6) that
  no longer exists, so they are not reproducible.
* **Unchanged on purpose.** `vol_turn` on `konkorde_marron` (E4, scale-free
  percentile zone), `RulesService` (marron vs media), the impulse engine.
* **API (additive).** `/v1/setups/evaluate` evidence gains `konkorde_verde`
  (`konkorde_marron` kept); a Konkorde condition's `value` now reports verde;
  the default `rule_version` reported is `0.1.1`.

**Declared limitation**: on bitget BTC/USDT 2024-11 → 2026-11 verde > 0 on
85.9 % of 4h and 88.4 % of 1d bars; 134/134 zero crosses on 4h, 18/19 on 1d
in two years. The STATE is a weak filter; the EVENT is what the owner
ratified (E3/E4 addendum 2026-07-11).

**Alternatives discarded**: `marron - media` (`edge`, Blai5's own signal) —
crosses zero but is not the line the owner validated as "crossing zero";
keeping marron (permanent bullish vote, E17); swapping the column silently
without a version bump (violates §0.4: same market, different adjudication,
same label).

**Status**: vigente. Tests: E3-G1..G6 (`test_setup_elements_golden.py`),
C1-G1 real-candle golden passes again on verde (xfail removed); suite 417
passed, 1 xfailed.
