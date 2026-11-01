# PRE-REGISTRATION — Impulsos v2 round 5: `impulse-2.3.0` ENTRY filters on the frozen 2.2.0 chain

**Status: FROZEN. Committed BEFORE the first run of any 2.3.0 filter on the
backtest window.** Sections 1–10 may not be edited after the first round-5
number exists; later edits are limited to §11 (result commit) and dated
`AMENDMENT` blocks. Git order is the audit trail (same pattern as
`PREREG_IMPULSOS_v2_r2.md` and `_r4.md`).

* Date frozen: 2026-11-01 (after the round-4b result commit `44fac0c`).
* Source of truth: `docs/impulsos-v2.md` §R2 (machine, re-buys, ML RSI), §R4
  (exit chain, books) and §R5 (this round). Where this file and the spec
  differ, the spec wins and the difference is a bug here.
* Engine under test: `impulse_sequential.SequentialMachine` with
  `impulse_sequential.r5_params(profile, entry_filter)` (`rule_version
  impulse-2.3.0`), ledger `impulse_backtest.PositionLedger` unchanged, harness
  `scripts/run_impulse_backtest_r5.py` (`rule="r5"`), tests
  `tests/test_impulse_r5.py` (rule-derived numbers).
* Scope: **backtest only**. A GO produces a proposal for paper (§R2.k gates),
  never an order, never a deploy, never a push. FEC/FEP stay archived; no
  broker, no execution, no Mongo, no Telegram.

---

## 1. Why round 5 is on the ENTRY side (finding of rounds 1–4b, not a tweak)

Rounds 1 (vote), 2–3 (sequential machine + ML RSI) and 4b (exits without
`phase_lost`) changed the SIDE rule and the EXIT chain three times; no cell
ever passed. Round 4b's reading: with the exits removed, gross PnL of both
books is near zero and the net is the cost of holding — the signal that OPENS
the trades shows no edge, whatever closes them. Rounds 2 and 4 also measured
that no leader beats the chance rate (lead-time study). The pre-registered
follow-up of `PREREG_IMPULSOS_v2_r4.md` §11 / `impulsos-v2.md` "Round 4b
results" is therefore an ENTRY-side hypothesis (`impulse-2.3.0`), **not another
exit**.

The candidate filters are the owner's own entry elements
(`mmk-strategy-setups-2026-07-06`, spec E1 / E2 / E5) that the machine does
not yet REQUIRE: the ADX 90° turn (born near 16), the AO divergence, and the
fresh BBWP ignition (the "spring" leaving the blue zone). Konkorde's zero cross
is already the leader and is not re-tested.

## 2. Hypotheses

> **H5-F (per filter F, per profile).** With the 2.2.0 chain and books FROZEN
> and the entry additionally gated by F, the PRO 4h and the SNIPPER 1h books
> pass the §6 GO criterion for the long AND the short cell.

> **H5-CLS (per filter F, per profile; classifier reading).** On the BASELINE
> run (2.2.0 entry, `entry_filter=None`), the trades whose entry candle PASSES
> F have higher net expectancy than the trades it REJECTS, on the whole window,
> in IS and in OOS (§6b). This reads the signal without changing the path.

> **H5-1d (informational).** `pro_1d` (1d trigger, 1w guardian) pooled over
> BTC + ETH + SOL: baseline and every filter. Expected INCONCLUSIVE (n small);
> run because it was the pre-registered universe extension for the 1d cells.

> **H-lev (pre-registered fallback).** A SNIPPER cell that is NO-GO ONLY
> because of the liquidation leg is re-run at **7x isolated** (the highest
> leverage with 0 liquidations in round 4b). A GO at 7x is a proposal of 7x,
> never a pass at 10x.

> **H-owner (informational, one candle).** On the owner's short candle
> (close nearest 82450 in 2026-10-08..16, 4h and 1h) report the filter
> ingredients and the pass / fail of each filter as if it were an entry.

> **H0.** Every mandatory cell fails a §6 leg or has n < 30 (INCONCLUSIVE),
> and no filter reaches KEEP in §6b on `snipper`.

## 3. Universe, data, split

BTC/USDT bitget spot OHLCV, closed candles, the cached frames of round 4b
(sha256 in the result JSON): 1h `87e7dbf8ecdb`, 4h `a9ec96296cf4`, 1d
`1fd23248b1c1`, 1w `3c483695e2db`, 1M (NaN on bitget, informational).
ETH/USDT and SOL/USDT 1d + 1w (+ 1M informational) are fetched from the PUBLIC
bitget endpoint into the same cache when missing (no keys); their sha256 and
row counts go to the manifest. Warm-up >= 300 trigger bars.

IS 2024-11-01 -> 2025-12-31; OOS 2026-01-01 -> 2026-10-31. A trade belongs to
the block of its ENTER candle (layer 1). Pooled cells (`pro_1d`) cluster by
(symbol, month) in the bootstrap, as the ledger already tags trades.

**No new IS-fitted parameter.** The follower windows stay `FITTED_WINDOWS` (pro
4h `ao 2 / adx 4 / macd 3 / rsi 2`; pro_1d `3 / 3 / 2 / 5`; snipper 1h `2 / 5 /
3 / 3`). The ADX origin band `[12, 20]` is the owner's A-grade band of
2026-07-06 (`STRATEGY_SETUPS_SPEC.md`, E1 refinement), not fitted here. Every
other filter threshold is a spec constant already in `ImpulseParams`
(`adx_turn_*`, `ao_*`, `bbwp_*`, `compression_lookback`, `breakout_ttl`).

## 4. What is FROZEN (copied from 2.2.0, not re-decided here)

Entry side, machine (FLAT -> ALERT -> IN_POSITION, `n_confirm 2`, windows,
ttl), re-buys, ML RSI gate (percentile 25/75, causal), exit chain #0–#4 of
`PREREG_IMPULSOS_v2_r4.md` §4 (liquidation / Jeisson / structural invalidation
on the guardian close / guardian ML RSI contrary / optional target off), partial
take 50 %, `info_phase_lost`, no time stop, books (PRO 1300 USDT 5x cross mmr
0.5 %; PRO-1d same; SNIPPER 1700 USDT 10x isolated mmr 0.56 %), cost model E16 +
funding, fills at the close of the decision candle.

**The owner's open points (a)–(f) of `docs/board.md` #26 do NOT touch this
round**, so no dual variant is needed: (a) exit below 4h with AO instead of
Konkorde — the exit chain is frozen as 2.2.0 and SNIPPER keeps Konkorde `verde`
as leader/exit by the owner's round-4 order; (b) scalper profile — not in the
round; (c) pro cross vs isolated, ancient 0x vs 1x — books frozen as round 4b
(pro cross); (d) E3 re-spec of the v0.1/v0.2 packs — legacy engine, not this
one; (f) guardian ML RSI as an exit — frozen ON as in 2.2.0. (e) is a parity
reading, not a rule.

## 5. The six entry filters (one per run; `entry_filter=None` = baseline)

All are evaluated on the ENTRY candle `j` (the candle on which the 2.2.0 entry
would fire: leader alert `a`, >= 2 same-side confirmations inside their
windows, BBWP in (50, 90), guardian not against, trigger ML RSI = side,
guardian ML RSI not contrary), AFTER every 2.2.0 gate. A failed filter emits
`entry_filter_blocked:<name>` and keeps the alert alive: the filter is
re-evaluated on every later candle until the alert's ttl (`alert_expired`). A
passed filter emits `entry_filter_ok:<name>`. Every ENTER (filtered or not)
reports the six flags as `entry_filter:<name>=0|1` in the decision reasons
(the ledger keeps them per trade → §6b).

| # | `entry_filter` | Rule (side `s` = ±1, alert bar `a`, entry candle `j`) | Owner element |
|---|---|---|---|
| F1 | `adx_turn` | The **ADX family is among the same-side confirmations** of the alert: an E1 turn onset (`adx_turn_up` state False -> True: `slope_recent >= 1.0` pt/bar over 3 bars, `slope_recent - slope_prior >= 1.5`, ADX >= 10) with the dominant DI on `s`, on a candle `b` in `[a, a + W_adx]`. Without it, AO / MACD / RSI alone cannot open. | "ADX con giro de 90 grados" |
| F1b | `adx_turn_origin` | F1 AND the turn is **A-grade**: `origin = min(ADX[b - 3 .. b]) in [12, 20]` (`adx_origin_band`). | "los mejores giros nacen en ~16; desde arriba = tarde" |
| F2 | `ao_divergence` | E2 AO divergence of the side ACTIVE on the trigger at `j`: `bull_div[j]` (long) / `bear_div[j]` (short) — fractal pivots strength 2, pair distance 5..40 inside a 60-bar lookback, both AO pivots on the same side of zero, price makes the new extreme and AO does not, pivot confirmed 2 bars later, signal lives 10 bars and dies if price breaks the second pivot. | "AO en divergencias" |
| F2b | `ao_divergence_any_tf` | F2 on the trigger **OR** the same divergence ACTIVE on the guardian's candle aligned to `j` = the last guardian candle CLOSED at or before the close of `j` (no lookahead; `ctx_idx`, covered by `tests/test_impulse_r5.py`). | the owner reads the divergence on 4h and 1d |
| F3 | `bbwp_fresh` | **Phase at `j` is `ignition`** (TV BBWP 13/256: crossed above 50 within the last `breakout_ttl = 3` candles, after a compression <= 30 inside the last 10). Expansion already running (> 50 for longer) does not open. | "volatilidad > 50" read as the 50-cross EVENT (green→yellow); the > 50 STATE is already the frozen 2.2.0 gate (50, 90) |
| F3b | `bbwp_fresh_blue` | F3 AND `blue_recent`: the compression came from the **blue zone** (min BBWP of the last 10 candles <= 20). | "azul→verde = ignición de la expansión, resorte disparando" (the only variant that encodes the owner's colour transition) |

Declared assumptions and exclusions (trading review before freezing, 2026-11-01):
F1 only counts an ADX turn that STARTS inside the alert's follower window
`[a, a + W_adx]` — the frozen machine's confirmation logic; the owner never
fixed the order "Konkorde first, then ADX", so a turn that precedes the
leader does not count here (reported as a limitation, not re-decided). AO
**convergence** (owner element 2, second half) is NOT tested in round 5. F3
measures the synchrony between the 50-cross and the entry, not the > 50
regime: a DROP of F3 does not refute the owner's "> 50" filter, which stays as
the 2.2.0 gate.

Reason codes added: `entry_filter_blocked:<name>`, `entry_filter_ok:<name>`,
`entry_filter:<name>=<0|1>`; decision `context.entry_filters` carries the six
booleans. Rule doc fields added: `entry_filter` (null | one of the six),
`adx_origin_band` = `[12, 20]`. Nothing else changes between 2.2.0 and 2.3.0.

## 6. Metrics and verdict

### 6a. Per cell (profile x filter x side; IS, OOS, total) — UNCHANGED from round 4b

Reported: n, win rate, expectancy net R, median R, PF net, CI95 cluster
bootstrap (symbol, month; 10 000 resamples, seed 42), max DD in USDT and in %
of one book's start (cumulative net USDT of the cell's trades), net USDT, avg
layers, partial takes, exit mix, entries blocked by the filter; book level per
symbol: equity final, return %, max DD of the equity curve, liquidations.

**GO** (owner's criterion, mechanical in `verdict_r4`) iff ALL: `n_total >= 30`
(else **INCONCLUSIVE**) AND `n_oos >= 10` AND `expectancy_net_oos > 0` AND
`PF_net_total >= 1.2` AND `liquidations == 0` AND `maxDD_usdt / start < 35 %`.
**NO-GO** otherwise. Profile verdict GO iff BOTH cells GO; one cell = "GO
parcial". The round-2 R-based verdict is printed for continuity only.

**Multiple comparisons, declared in advance**: 6 filters x 3 profiles x 2
sides = 36 cells plus 6 baseline cells. A GO of a single filter among the six
is reported as a **candidate requiring replication** (dedicated
pre-registration on new data — ETH/SOL on the trigger TFs — before any paper
proposal), never as a pass of the family.

### 6b. Classifier reading of each filter on the BASELINE trades (new, mechanical)

For each profile's baseline run and each filter F: split the baseline trades
by the flag `entry_filter:F` recorded at their ENTER candle into PASS and
REJECT; compute the §6a metrics of both subsets (whole window, IS, OOS).
**Sides are pooled per profile** (long + short together; `n_pass` per side is
reported as information only). PRO 4h (baseline 7 / 7 trades) cannot reach
`n_pass >= 10` and is INCONCLUSIVE in §6b by construction: the §6b decision
rests on `snipper` (1h) and, if n allows, on the pooled `pro_1d`.

* **INCONCLUSIVE** iff `n_pass < 10`, or `n_rej < 3`, or in IS or OOS either
  subset has fewer than 3 trades.
* Otherwise **KEEP** iff ALL: `expectancy_pass_all > 0` AND
  `expectancy_pass_all > expectancy_rej_all` AND `expectancy_pass_IS >
  expectancy_rej_IS` AND `expectancy_pass_OOS > expectancy_rej_OOS`; else
  **DROP**.

KEEP is NOT a GO: it only says the filter separates the baseline trades in the
right direction consistently in both blocks and is worth a dedicated round
with more data (ETH/SOL on the trigger TFs). DROP closes the filter for this
rule family. The caveat is stated in advance: a filtered RUN changes the path
(position occupancy), so §6a and §6b can disagree; §6a decides GO, §6b decides
what to study next.

## 7. What will NOT be done

* No change of any 2.2.0 parameter, window, book, cost or exit after seeing
  results; no stacking of filters after seeing results (a stacked rule = a new
  pre-registration); no change of the ADX band, the divergence parameters or
  the BBWP levels; no filter added or removed after the first number exists.
* No re-cutting by regime or sub-period, no extra split, no best-filter
  selection beyond reporting all six side by side; no looser GO; INCONCLUSIVE
  stays INCONCLUSIVE.
* No leverage sweep except the single pre-registered 7x fallback of §2.
* No exchange calls beyond the ETH/SOL 1d / 1w / 1M public fetch when the
  cache is missing; no Mongo, no Telegram, no deploy, no push, no live
  container touched.

## 8. Expected outcome stated in advance

Every filter REMOVES entries, so every filtered cell has n <= its baseline:
PRO 4h (baseline 7 / 7) stays INCONCLUSIVE under every filter; SNIPPER 1h
(baseline 31 / 34) most likely falls under 30 on at least one side for F2,
F2b, F3b (low base rates) and is INCONCLUSIVE there; F1 and F3 may keep n >= 30
on 1h and are the only cells that can say GO / NO-GO. Expected: NO-GO or
INCONCLUSIVE everywhere (H0) — the round-2 lead-time study found no family
beating the chance rate, and a stricter gate on a no-edge signal lowers costs
but does not create expectancy. The informative output is §6b on `snipper`
(the only profile whose baseline n allows a KEEP / DROP; PRO 4h is
INCONCLUSIVE there by construction, see §6b): a KEEP on snipper for a filter
whose pro_1d pooled reading is not contrary would be the first positive
entry-side signal of this family and would justify an ETH/SOL extension on
4h / 1h; the expectation is DROP or INCONCLUSIVE for all six. H-lev: expected not triggered (the only
round-4b liquidation came from a trade that F3 / F3b may remove; if a cell
fails only that leg, 7x is run). 1d pooled: INCONCLUSIVE. Owner candle: the
flags are reported, not predicted.

## 9. Sources

* Owner's elements: toolKit memory `mmk-strategy-setups-2026-07-06` (6-jul
  dictation: ADX 90°, AO divergences, Konkorde zero cross, W/V in volatility,
  BBWP > 50 and its colour transitions) and the E1 refinement of 2026-07-06
  late (`STRATEGY_SETUPS_SPEC.md`: origin ~16, A-grade band `[12, 20]`).
* E1 / E2 / E5 operationalisations: `STRATEGY_SETUPS_SPEC.md`; phases:
  `docs/impulsos-v2.md` §b; E2 code: `impulse_service._ao_divergence_active`.

## 10. Runs (in the owner's order) and command

1. `pro` (4h, guardian 1d, BTC): `base`, then F1, F1b, F2, F2b, F3, F3b.
2. `snipper` (1h, guardian 4h, BTC): the same seven runs; then the 7x fallback
   if §2 H-lev triggers.
3. `pro_1d` (1d, guardian 1w): the same seven runs on BTC, ETH, SOL, pooled.
4. §6b classifier on each profile's `base`; H-owner on `pro` and `snipper`;
   baseline continuity check against the newest `r4_impulse_*.json` (the `base`
   cells must reproduce round 4b trade for trade).

```
docker compose --profile backtest run --rm -e TELEGRAM_BOT_TOKEN= backtest \
  python scripts/run_impulse_backtest_r5.py --md-out /app/docs/impulsos-v2-backtest-r5.md
```

## 11. Result commit

Run `20261101T152827Z` after this file was committed (`978a246`). Results:
`docs/impulsos-v2-backtest-r5.md` (+ §"Round 5 results" of `docs/impulsos-v2.md`),
raw `r5_impulse_20261101T152827Z.json`. Baseline cells reproduce round 4b trade
for trade on `pro` and `snipper` (pro_1d differs only because it now pools
ETH + SOL; the BTC book is the same 2 trades). **No cell is GO.** Every filtered
cell is INCONCLUSIVE by n (largest: snipper `bbwp_fresh_blue` long 29, `adx_turn`
short 28); the baseline snipper cells stay NO-GO. H-lev not triggered (the
10x liquidation of 2026-03-02 survives `adx_turn`, `bbwp_fresh`, `bbwp_fresh_blue`,
but those cells fail by n, not by the liquidation leg alone). §6b on snipper
(n 65): `adx_turn` **DROP** (passed −0.677 R vs rejected +0.012, worse in IS and
OOS), `bbwp_fresh` **DROP** (passed beat rejected everywhere but
expectancy_pass_all = −0.053 <= 0), `bbwp_fresh_blue` **KEEP** (passed +0.021 R
PF 1.02 CI95 [−0.75, 0.85] vs rejected −0.394; IS +0.008 vs −0.355; OOS +0.032
vs −0.539; n 32 / 33) — a KEEP that says the rejected trades lose, not that the
passed ones win; `adx_turn_origin`, `ao_divergence`, `ao_divergence_any_tf`
INCONCLUSIVE (pass rates 14 %, 1.5 %, 7.7 %). pro and pro_1d: all INCONCLUSIVE
(n_pass <= 8). Pre-declared caveat observed in the data: the filtered RUN of
snipper `adx_turn` (53 trades, book +32.7 %, OOS +0.95 / +2.00 R, 1 liquidation)
disagrees with its §6b reading (DROP) because blocking entries changes which
trades the single-position book takes; neither is a GO. Owner candle: on 1h
the short passes `adx_turn` (onset 2026-10-12 14:00, origin 21.4 -> not A-grade)
and `ao_divergence` (bear divergence on the trigger), fails both BBWP filters
(phase expansion, bbwp 86.7); on 4h only `ao_divergence_any_tf` (1d bear
divergence). Expected outcome (§8) held: H0 except the single weak KEEP, which
§6a/§6b and the multiple-comparison rule classify as a candidate requiring
replication, not a signal. No amendment was made; no parameter touched after the
run.
