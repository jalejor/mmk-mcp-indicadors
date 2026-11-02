# PRE-REGISTRATION — Impulsos v2 round 8: FORWARD SHADOW, long + short, each signal labelled with a regime

**Status: FROZEN. Committed BEFORE the first shadow candle is recorded.** Sections 1–9 may
not be edited once the first forward signal exists; later edits are limited to §10 (result
commit) and dated `AMENDMENT` blocks. Git order is the audit trail (same pattern as
`PREREG_IMPULSOS_v2_r2.md` … `_r7.md`).

* Date frozen: 2026-11-01 (after the round-7 result commit `a13bb24` and the round-8 prior
  analysis commit `bd0673e`).
* Owner decision of 2026-11-01 that binds this round: **the forward shadow runs LONG and
  SHORT, with a regime identifier on every signal.** Context given by the owner: a while
  ago the longs stopped working (bear market) and he trades impulses in BOTH directions;
  round 7 gave longs positive and shorts negative on 2024-11 → 2026-10, which may be only
  the regime of that period. He wants the two strategies contrasted and to know WHEN a
  long is due and when a short is due.
* Engine under test: `impulse_sequential.SequentialMachine` with `r5_params("snipper",
  entry_filter)` (`impulse-2.3.0`), ledger `impulse_backtest.PositionLedger`, **frozen
  2.2.0/2.3.0 chain as in rounds 6/7** (Konkorde leader / exit, no AO, guardian ML RSI exit
  ON, structural invalidation on the guardian close, 50 % partial take, no target, trigger
  ML RSI gate ON = `spec`). Regime labels: `impulse_regime` (new, additive, never read by
  the machine). Runner: `scripts/run_impulse_shadow_r8.py` (module
  `controllers/metrics/impulse_shadow.py`), report `scripts/shadow_r8_report.py`, tests
  `tests/test_impulse_regime.py`, `tests/test_impulse_shadow.py`.
* Scope: **paper shadow in the local lab only.** Public spot OHLCV (bitget, ccxt, no keys);
  trades of paper in local JSONL; notices by ntfy to the lab's private topic, one line per
  entry / exit. Nothing produces an order, a Mongo write, a Telegram message, a push or a
  deploy. FEC/FEP stay archived; the live containers `mmk-signals-api` /
  `mmk-signals-indicadors` are not touched or restarted.

---

## 1. What round 7 left open (declared before any forward number)

Round 7 (`docs/impulsos-v2-backtest-r7.md`): on 9 Bitget perps the six LONG primary cells
pass the mechanical gate (PF ≈ 2, +0.43 … +1.39 R OOS) but not Holm (smallest raw p 0.107,
tails on NEAR / XRP); the six SHORT cells fail (expectancy ≤ 0 and/or PF < 1.2); 10x isolated
= 107 liquidations; verdict NO-GO on 12/12. The owner's reading: longs vs shorts may be the
regime of the window, not a property of the sides.

**Prior analysis of this round, committed BEFORE this file** (`bd0673e`,
`docs/impulsos-v2-r7-regime-split.md`, `scripts/analyze_impulse_r7_regime.py`): the round-7
trades were split by the two identifiers of §3, chosen before looking at any split. What it
showed (descriptive, no GO/NO-GO):

* The window was NOT one regime: share of 1d candles in `up` (own EMA200) per asset is
  0.28–0.57 over the window, 0.16–0.78 in IS and **0.04–0.46 in OOS** (2026 was mostly below
  the EMA200 on every asset but NEAR).
* **Longs did better in `down`, not in `up`:** snipper `base` long +0.03 R in `up` (n 105) vs
  +0.88 R in `down` (n 149); `adx_turn` +0.42 vs +1.33; only `bbwp_fresh_blue` is the other
  way (+1.24 vs +0.66). The 2.3.0 longs of round 7 are counter-trend bounces inside daily
  downtrends; the OOS long P&L lives in `down`.
* **Shorts are ≈ 0 in both regimes** (snipper `base` short −0.17 R in `up`, −0.02 in `down`;
  `adx_turn` −0.05 / +0.11; `bbwp_fresh_blue` −0.09 / −0.20). With BTC as the leader the
  shorts in BTC-`down` are mildly positive (`base` +0.12, `adx_turn` +0.29) and in BTC-`up`
  negative (−0.22 / −0.13), i.e. the only hint of "when a short is due" is R2, not R1.
* No `up − down` difference has a cluster-bootstrap CI95 that excludes zero on the snipper
  cells (the one that does, pro `adx_turn` short by R2, has n 21 / 21 and 2 OOS trades).
* **The long/short-by-regime book (R1) is predicted ≈ 0 R**: snipper `base` −0.003 R (n 298),
  `adx_turn` +0.23 (n 222), `bbwp_fresh_blue` +0.35 (n 234) — below `long_only` (+0.53 /
  +0.92 / +0.92) in every cell. By R2 (BTC): +0.33 / +0.47 / +0.61, still below `long_only`.

So the backtest's prediction for this round is **against** the owner's hypothesis: the simple
trend identifier does not tell when to go long; if anything it says the opposite (longs in
daily downtrends). The forward shadow is the test that does not depend on the window of
round 7.

**Overfitting risk, declared.** Two identifiers × two sides × three entries were looked at
once, with fixed thresholds (EMA 200, zero) and no fitting; the identifier that drives the
long/short book (R1) was fixed before the split was computed and is NOT changed now that R2
looks better on the shorts. Any "longs in down" or "shorts by BTC" rule suggested by the
prior analysis is a NEW hypothesis that would need its own pre-registration; it is reported
here only as the backtest's prediction (§8) and measured forward as the informational R2
book, never as a GO-eligible cell.

## 2. Hypotheses

> **H8 (owner).** Forward, the 2.3.0 snipper chain on the 9 perps has a positive expectancy on
> the LONG side when the asset is in a daily uptrend and on the SHORT side when it is in a
> daily downtrend, so the long/short-by-regime book beats both single-side books.

> **H0 (backtest prediction, §1).** Forward, `long_only` ≈ +0.5 R and `short_only` ≈ 0 R
> as in round 7, and the regime book is ≈ 0 R (longs lost in `up`, shorts ≈ 0 in `down`): the
> regime identifier separates nothing. No book passes the round-4 gate + Holm.

## 3. Regime identifiers (FIXED before the prior analysis, `impulse_regime.py`)

Candidates named by the owner: 1d / 1w trend (EMA 50/200 or price vs EMA200 1d), Konkorde
1d above / below zero, ADX / DI 1d, BTC as the regime leader of the alts. Two were chosen,
with this justification written before any split existed:

* **R1 `own` — the asset's own daily trend: close > EMA200 on the last CLOSED 1d candle at
  the trigger candle's close → `up`, else `down`.** EMA200 = `pandas ewm(span=200,
  adjust=True)` (no seed bias on a finite history). Chosen because it is the coarsest,
  least-parameterised candidate, it is the owner's own wording, and it is **independent of
  the chain**: the machine already reads Konkorde, DI, AO and MACD of the 4h guardian and the
  1d context (`context_aligned`, ctx bias ±3), so a Konkorde-1d or ADX/DI-1d identifier would
  largely re-label the chain's own gate; a moving average is not in the chain at all.
* **R2 `btc` — the same rule on BTC/USDT 1d, applied to every asset** (BTC as the regime
  leader). Chosen to test the owner's "BTC leads the alts" reading with zero extra
  parameters. **Informational in round 8**: it labels every signal and feeds a fourth book
  (`regime_btc`) that is reported but never GO-eligible.

Not chosen: EMA 50/200 cross (two parameters, slower), 1w trend (too few regime changes in
90 days to measure anything), Konkorde 1d / ADX-DI 1d (overlap with the chain, see above).
The identifiers are evaluated at the trigger candle's close with only CLOSED 1d candles; a
label never changes after the signal.

## 4. Universe, chain, books (all frozen from round 7)

* **Universe** = the round-7 universe, unchanged: BTC, ETH, SOL, XRP, DOGE, NEAR, BNB, LINK,
  ADA (/USDT), bitget spot OHLCV as the perp price proxy (same limitation as round 7).
* **Profile** = SNIPPER 1h (guardian 4h, context 1d), E0 1700 USDT, **book `cross5`**
  (`leverage 5, margin_mode cross, mmr 0.56 %`) — the round-6/7 reference; 10x isolated is
  not run (107 liquidations in round 7).
* **Entries** = `base`, `adx_turn`, `bbwp_fresh_blue` (the round-7 primary entries), gate
  `spec` (`mlrsi_gate: true`). Three machines per asset, one ledger each, long + short.
* **Costs** = E16 fee 0.10 % + slip 0.05 % per layer per side, funding 0.01 %/8 h, liquidation
  intrabar on the wallet (cross). Same `drive_sequential` as every backtest round.
* **Rule label** `impulse-2.3.0-r8` (a replication on another window, never a rule proposal).
* **Replay anchor.** The machine is causal and O(n): each hourly run replays every machine
  from the fixed anchor **2026-10-01T00:00Z** (ledger E0 at the anchor, indicator warm-up
  fetched before it: 3 300 bars of 1h and 4h so the ML RSI percentile window (3 000) is as
  full as in the backtest, 420 bars of 1d) up to the last CLOSED 1h candle. The replay is
  deterministic on closed candles, so a decision never changes once made; the state of the
  shadow IS the JSONL of recorded events and trades, deduplicated by key.
* **Activation** = decisions at or after **2026-11-01T18:00:00Z** (the first 1h close after
  this commit). Trades that entered before the activation are replayed for the machine state
  but excluded from every book (their exits are logged as `carried`).

## 5. Signals, books, metrics

Every ENTER decision is a **signal**, labelled with `regime_own`, `regime_btc` at its trigger
close. A closed trade carries the labels of its entry. Three books are measured, per entry
(3 × 3 = 9 primary cells) and pooled over the 9 assets:

| book | membership |
|---|---|
| `long_only` | every long trade |
| `short_only` | every short trade |
| `regime` (= `regime_own`) | long trades entered in `up` + short trades entered in `down`, by **R1** |
| `regime_btc` (informational) | the same by R2 |

Per cell: n, expectancy net R, CI95 cluster bootstrap (symbol × month), PF, win, net USDT,
max DD of the pooled cumulative USDT as % of the pooled start (9 × E0), liquidations, one-sided
cluster-bootstrap `p(exp ≤ 0)` (`impulse_multi.p_positive`, 10 000 resamples, seed 42). Per
side and regime: signal counts and expectancy (the "when is a long due" table). Every
forward trade is OOS by construction (ledger split = anchor); the IS/OOS legs of the round-4
gate are read on the whole forward sample with `n_oos = n`.

## 6. Closure and verdicts (mechanical, pre-registered)

**Closure**: the shadow closes when the `base` run has **≥ 60 signals on each side** (entries,
pooled over the 9 assets) **or 90 days** after the activation (2027-01-30T18:00Z), whichever
comes first; open positions at closure are closed at the last recorded 1h close
(`end_of_data`) and reported apart. Expected pace from round 7 (254 longs / 318 shorts in
24 months on `base`): ≈ 10 longs and 13 shorts per month → ≈ 30 / 40 in 90 days, i.e. the
60-per-side closure is NOT expected to trigger before the 90 days; the sample will be at the
edge of the gate's n ≥ 30.

**6 A — round-4 gate, unchanged**, per cell: GO iff n ≥ 30 AND n_oos ≥ 10 AND expectancy > 0
AND PF ≥ 1.2 AND liquidations = 0 AND max DD < 35 % of the pooled start; INCONCLUSIVE iff
n < 30; else NO-GO.

**6 B — multiple comparisons.** Primary family = the 9 cells of §5 (3 books × 3 entries).
**Holm step-down, α = 0.05** on `p(exp ≤ 0)`. **GO iff 6 A GO AND Holm-adjusted p < 0.05**
(`impulse_multi.verdict_r7`). `regime_btc` cells, per-asset cells and per-regime side cells
are informational (never GO-eligible).

**6 C — the owner's question** is answered by the forward table of §5 against §8: whether
`regime` beats `long_only` and `short_only` (H8) or not (H0), stated with the CI95 of the
difference, whatever the GO.

**6 D — what a GO would license.** Nothing goes to money or to an executor from this round.
A GO opens a new pre-registration (paper with the exact cell on a broker test account, or a
longer shadow). A NO-GO / INCONCLUSIVE at 90 days with the prediction of §8 confirmed
closes the "regime by daily trend" question for this chain.

## 7. What will NOT be done

No change to any 2.2.0 / 2.3.0 parameter, window, cost, book, exit or entry filter after
the activation; no change of the identifiers, their thresholds or which one drives the
regime book; no new identifier added mid-way (a better-looking R2 does not replace R1); no
asset added or removed; no re-cutting by sub-period or "best assets"; no early closure on a
good or bad streak; no second cadence. The runner is one-shot and idempotent: repeating an
hour appends nothing. No Telegram, no Mongo/Atlas, no exchange keys, no brokers, no push.

## 8. Expected outcome stated in advance (the backtest's prediction, from §1)

| cell (snipper, cross5, spec) | `long_only` | `short_only` | `regime` (R1) | `regime_btc` (R2) |
|---|---|---|---|---|
| `base` | +0.53 R (OOS +0.52), PF 1.7 | −0.08 R (OOS +0.14), PF 0.9 | **−0.00 R**, PF 1.0 | +0.33 R, PF 1.5 |
| `adx_turn` | +0.92 R (OOS +1.34), PF 2.2 | +0.05 R, PF 1.1 | +0.23 R, PF 1.3 | +0.47 R, PF 1.7 |
| `bbwp_fresh_blue` | +0.92 R (OOS +0.47), PF 2.3 | −0.16 R, PF 0.8 | +0.35 R, PF 1.5 | +0.61 R, PF 1.9 |

Expected forward: `long_only` positive on the point estimate but with n ≈ 30 and win rates
≈ 25 %, so INCONCLUSIVE or NO-GO after Holm (m = 9); `short_only` ≈ 0; `regime` below
`long_only` (H0). The regime of the forward window itself is unknown: if the alts spend the
90 days above their EMA200, the regime book collapses into `long_only` and the comparison
is uninformative — this is declared as the main limitation of a 90-day shadow. Liquidations:
0 (cross 5x). Most likely value of the round: the forward confirmation (or refutation) that
the chain's longs are counter-trend, measured on data nobody has seen.

## 9. Commands (Docker, in series, one at a time on this machine)

```
# tests (network none)
docker compose --profile test run --rm -T test-indicadors \
  pytest -q -p no:cacheprovider tests/test_impulse_regime.py tests/test_impulse_shadow.py
# dry run: evaluates the last closed 1h candle, prints what it would record/notify, writes nothing
docker compose --profile shadow run --rm -T shadow python scripts/run_impulse_shadow_r8.py --dry-run
# real one-shot (what the cron wrapper runs every hour)
~/Documents/suideaweb/labs/mmk-signals/shadow-r8.sh
# report
~/Documents/suideaweb/labs/mmk-signals/shadow-r8.sh --report
```

State: `~/Documents/suideaweb/labs/mmk-signals/data/shadow-r8/` (`events.jsonl`,
`trades.jsonl`, `state.json`, `runs.log`, `ohlcv/` incremental cache). Cron (hourly, minute
4, no agent): `4 * * * * ~/Documents/suideaweb/labs/mmk-signals/shadow-r8.sh`.

## 10. Result commit

(empty until the shadow closes)

### AMENDMENT 2026-11-01 — activation evidence (no change to §§1-9)

* Prereg commit `583108b`; runner commit `e6be68a` (`impulse_shadow.py`, `run_impulse_shadow_r8.py`,
  `shadow_r8_report.py`, `tests/test_impulse_shadow.py`). Tests in Docker, network none:
  `test_impulse_regime.py` + `test_impulse_shadow.py` + `test_impulse_r7.py` + `test_impulse_r6.py`
  = **29 passed**.
* Lab (`~/Documents/suideaweb/labs/mmk-signals`, not a git repo): service `shadow` (profile
  `shadow`, test image, only `NTFY_BASE` / `NTFY_TOPIC` interpolated from the `.env`, no
  `depends_on`), wrapper `shadow-r8.sh`, state `data/shadow-r8/`. Live containers untouched.
* Dry run 17:21Z: 9/9 assets, 27 machines, last closed candle 16:00Z open (closes 17:00Z),
  events +0 (activation is 18:00Z), **11 open paper SHORTS replayed from before the
  activation** (BTC ×3, SOL ×3, XRP ×2, ADA ×3; entries 2026-10-15 … 10-29) — their exits
  will be logged as `carried` and excluded from every book. Initial cache fetch ≈ 15 s per
  asset (4 061 × 1h, 3 490 × 4h, 451 × 1d rows).
* Real runs 17:24Z and 17:26Z (`docker compose --profile shadow run --rm -T shadow`, the
  wrapper's command): both `events +0 trades +0 open 11 ntfy sent 0 failed 0 ok`;
  `state.json` counts `runs 2, events 0, trades 0`; second run appended nothing (idempotent).
  First candle that can count: the 1h candle closing 2026-11-01T18:00Z.
* NOT done in this session: the hourly crontab line (§9) was not installed (the session could
  not run `crontab`); the wrapper itself was not executed here (`flock` blocked in the
  sandbox) — it runs the same compose command shown above. The owner installs the cron.

### AMENDMENT 2026-11-02 — incremental runner (no change to §§1-9; every recorded result identical)

* **Cause.** The cron (installed by the owner; `runs.log` hourly since 2026-11-01T17:29Z) heated
  the laptop to 90 °C every hour: each run replayed everything from the anchor — 81
  `IndicatorsService.calculate_all` (3 TFs × 9 assets × **3 entries**, the same frames three
  times) and 27 machines over ~790 candles. cProfile in Docker (99 s under the profiler, ≈ 70 s
  real, 100 % of one core at `cpus: 0.8`): `bbwp_legacy` (a per-bar `rank` over 252 rows that the
  machine never reads) 38 s, ML RSI percentile thresholds (3000-bar window, every bar) 22 s,
  **18 s of network** fetching the forming 4h / 1d candles that `closed_only` then drops, the
  machines ≈ 7 s.
* **Change** (`impulse_shadow.py`, same rule, same frames, same code paths for every number):
  OHLCV cache fetches only candles that can already be closed; each asset is enriched ONCE with
  `IndicatorsService.calculate_impulse()` (the columns the engines read, same functions and
  parameters as `calculate_all`; `bbwp_legacy`, moving averages and Trend Speed skipped); the
  3 entries share the derived arrays (`SequentialMachine(derived_from=)`); ML RSI thresholds
  cached per asset / TF and computed only for new candles (`ml_rsi_cached`, prefix reused only
  when its smoothed RSI is identical); machine + ledger saved per (entry, asset) at the candle
  BEFORE the last one (`<state-dir>/cache/machine_*.json`) and resumed when the sha256 of the raw
  candles they were built on (trigger and contexts) is unchanged — the last candle is always
  re-driven because an `enter` there is not filled (`entry_skipped_last_candle`); any mismatch =
  full replay from the anchor (same code: `SequentialDriver`, factored out of
  `drive_sequential`). `--full` forces the full replay; a dry run reads the caches, writes nothing.
* **Parity evidence (Docker, pristine COPY of the live state, never the live dir).**
  `scripts/shadow_r8_parity.py` replays the recorded runs in order with the clock each one had
  (the `recorded_at` of its events) serving the exchange from the pristine `ohlcv/` cache:
  **32 runs → `events.jsonl`, `trades.jsonl`, `state.json` BYTE-IDENTICAL** to the live files
  (15 events, 20 open paper positions, every float). Control with the pre-amendment code
  (`git archive HEAD`, `--full --last-only`): identical modulo `recorded_at`, `counts.runs` and
  the `entry_skipped_last_candle` marker of the run in which each entry candle was the last
  one — i.e. the harness reproduces the live data path. Tests in Docker, network none:
  **447 passed, 1 xfailed** (`test_impulse_shadow.py`: resume byte-identical to the full replay
  with an open position across the resume, snapshot rejected when a candle in its prefix
  changes, carried flag across a resume, `calculate_impulse` columns identical to
  `calculate_all`, ML RSI cache identical and only extending, no fetch of forming candles).
* **Time.** Before: ≈ 70 s wall per run at 100 % of one core (wrapper 04:00 → 05:0x in
  `runs.log`). After, in the parity replay (container, `cpus 0.8`, no network): **2.8–3.0 s per
  run**, cold run without cache 9.3 s. Live (cache swapped atomically into
  `data/shadow-r8/cache/` at 22:40Z after the parity, compose `cpus: 0.5`, wrapper now appends
  the runner's `[perf]` line to `runs.log`): see the `runs.log` lines from 2026-11-02T23:04Z.
