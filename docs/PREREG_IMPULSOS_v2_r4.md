# PRE-REGISTRATION — Impulsos v2 round 4b: `impulse-2.2.0` exit chain (owner decision 6), PRO 5x cross + SNIPPER 1h 10x isolated

**Status: FROZEN. Committed BEFORE the first run of the 2.2.0 chain on the
backtest window.** Sections 1–10 may not be edited after the first round-4b
number exists; later edits are limited to §11 (result commit) and dated
`AMENDMENT` blocks. Git order is the audit trail (same pattern as
`PREREG_IMPULSOS_v2_r2.md`).

* Date frozen: 2026-11-01 (after owner decisions 5 and 6 in `docs/impulsos-v2.md`).
* Supersedes the round-4 draft that was cut on 2026-11-01 (stash
  `r4-snipper-parcial`): that draft still used `phase_lost` as an exit. Its
  reusable parts (isolated-margin ledger, partial take, snipper profile, 1h
  lead-time windows) are kept; its hypotheses are replaced by this file.
* Source of truth: `docs/impulsos-v2.md` §R2 (machine, re-buys, ML RSI) + §R4
  (this chain). Where this file and the spec differ, the spec wins and the
  difference is a bug here.
* Engine under test: `impulse_sequential.SequentialMachine` with
  `impulse_sequential.r4_params(profile)` (`rule_version impulse-2.2.0`), ledger
  `impulse_backtest.PositionLedger` (cross for PRO, isolated for SNIPPER,
  `reduce` for partial takes), harness `scripts/run_impulse_backtest_r4.py`
  (`rule="r4"`), tests `tests/test_impulse_r4.py` (rule-derived numbers).
* Scope: **backtest only**. A GO produces a proposal for paper (§R2.k gates),
  never an order, never a deploy, never a push.

---

## 1. Why round 4b (finding of round 2, not a tweak)

Round 2 (`impulse-2.1.0`): `exit_phase_lost` (BBWP <= 50 with verde against)
closed **36 of 57** PRO 4h trades; the owner's own exit rule fired 2 times. The
anchored replay of the owner's October short (82450) was closed by `phase_lost`
the next day at −0.18 R, while the owner held it to +5.9 %. Owner decision 6
(2026-11-01): `phase_lost` is removed as an EXIT (it stays as the informational
reason `info_phase_lost`). This is a new rule version, hence a new pre-registration.

## 2. Hypotheses

> **H4b-PRO.** With the 2.2.0 chain, PRO 4h (guardian 1d, 1300 USDT, 5x cross,
> re-buys, ML RSI gate) passes the §6 GO criterion for the long AND the short cell.
> PRO 1d (guardian 1w) is run as a second book (expected INCONCLUSIVE, n small).

> **H4b-SNIPPER (primary for leverage).** With the 2.2.0 chain, SNIPPER 1h
> (guardian 4h, 1d informational, 1700 USDT, **10x isolated**, re-buys, ML RSI
> gate, intrabar liquidation check with wicks at Bitget maintenance margin,
> funding) passes §6 for BOTH cells.

> **H-lev (pre-registered fallback).** If H4b-SNIPPER is NO-GO at 10x: the same
> run at 7x, 5x, 3x, 2x, 1x isolated (signals never change with leverage; only
> margin used and liquidation distance change). The proposal is the HIGHEST
> leverage of that ordered list whose BOTH cells are GO; if none, "no leverage
> passes".

> **H-cmp (informational).** 2.2.0 cells vs round 2-3 `pro:H2` (gated, 2.1.0)
> on the same window and costs, read from the newest `r2_sequential_*.json`;
> buy-and-hold of the window as context.

> **H-owner (informational, one trade).** §R2.g replay of the owner's short
> (layer 1 forced at the trigger candle whose close is nearest 82450 in
> 2026-10-08..16) with the 2.2.0 chain on 4h (PRO) and on 1h (SNIPPER): exit
> code + candle, or unrealized gross / net at 2026-10-31 in USDT and R.

> **H0.** Any mandatory cell fails a §6 leg or has n < 30 (INCONCLUSIVE).

## 3. Universe, data, split

BTC/USDT bitget spot OHLCV, closed candles, cached frames (sha256 in the result
JSON): 1h (17 820 rows, 2024-10-19 -> 2026-10-31), 4h `a9ec96296cf4…`, 1d
`1fd23248b1c1…`, 1w `3c483695e2db…`, 1M (NaN on bitget, informational).
Warm-up >= 300 trigger bars before the window (1h: exactly 300, the cache
starts 2024-10-19 12:00).

IS 2024-11-01 -> 2025-12-31; OOS 2026-01-01 -> 2026-10-31. A trade belongs to
the block of its ENTER candle (layer 1).

**The only IS-fitted parameters are the follower windows**, unchanged from
rounds 2 and 4-draft (`FITTED_WINDOWS`): pro 4h `ao 2 / adx 4 / macd 3 / rsi 2`
(ttl 4); pro 1d `3 / 3 / 2 / 5` (ttl 5); snipper 1h `2 / 5 / 3 / 3` (ttl 5,
from `docs/impulsos-v2-lead-time-1h.md`, 573 / 111 / 348 / 441 IS pairs; the
pre-declared "leaders lead" test is NOT supported on 1h either: leader median
lead 4.0 vs ao 5.0 / adx 2.5 / macd 5.0 / rsi 5.0; Konkorde base rate verde > 0
on 85.3 % of 1h bars, 319 + 319 zero crosses, no alarm).

## 4. The 2.2.0 exit chain (§R4, a priori; first match wins, on the closed trigger candle)

Entry side, machine, re-buys and the ML RSI entry gate are `impulse-2.1.0` §R2
unchanged (ML RSI = percentile 25/75 port, causal, as TradingView plots).

| # | Code | Rule | Fill |
|---|---|---|---|
| 0 | `liquidation` (ledger, must never happen) | intrabar at the adverse wick: PRO cross on the wallet; SNIPPER isolated on the position margin (Σ notional / leverage), `mmr = 0.0056` | liquidation price; isolated: the whole position margin is lost, the wallet outside is untouched |
| 1 | `exit_rule_jeisson` | `bbwp_red_turn` (BBWP[j−1] >= 90, one-candle drop >= 8) AND verde zero cross AGAINST, both in `[j−2, j]`, one on `j` — on the TRIGGER TF | `close[j]` |
| 2 | `exit_invalidation` + `exit_invalidation_ctx_close` (structural, WIDE) | `inv` fixed at ENTER = the WIDEST of {trigger range `a−9..e`, `close[e] ∓ 3 ATR`, **guardian swing** = min low / max high of the last 10 CLOSED guardian candles at entry (`invalidation_ctx_swing`)}; exit when a **guardian candle closed AFTER the entry CLOSES beyond `inv`** (never a trigger close, never a wick; `hold_beyond_invalidation_awaiting_ctx_close` meanwhile). Without a guardian frame: trigger close (reported as `_trigger_close_fallback`) | `close[j]` of the trigger candle on which that guardian close is known |
| 3 | `exit_ctx_mlrsi_against` | the GUARDIAN's ML RSI regime (causal percentiles on the guardian closes) is the contrary colour: short with guardian green, long with guardian red. Gray never exits. The same condition at ENTER blocks the entry (`ctx_mlrsi_against`) | `close[j]` |
| 4 | `exit_target_r` (optional target by levels) | `unrealized / 1R >= target_r`; **`target_r = None` in round 4b** (not exercised, kept as a parameter) | `close[j]` |
| — | `info_phase_lost` | BBWP <= 50 with verde against: **informational only**, no exit (owner decision 6) | — |
| — | time stop | **removed** (`time_stop_bars = None`): not in the owner's list of valid exits | — |

**Partial take (`partial_take_fraction = 0.5`)**, evaluated after the exit
chain when no exit fired, once per trade, never on the entry candle: on the
first candle `j` where the TRIGGER ML RSI regime seen on `j−1` was the
position's colour (short: red; long: green) and on `j` it is gray, close 50 %
of EVERY layer's qty at `close[j]` (E16 cost on the closed notional). 1R keeps
the ORIGINAL layer-1 qty; later adds scale from the ORIGINAL layer-1 notional
(0.5 × N1). Re-buys stay allowed afterwards under the §R2.c rules.

## 5. Books, execution and cost model

| Field | PRO | PRO-1d | SNIPPER |
|---|---|---|---|
| trigger / guardian / informational ctx | 4h / 1d / 1w | 1d / 1w / 1M | 1h / 4h / 1d |
| equity / leverage / margin | 1300 / 5x / cross | 1300 / 5x / cross | **1700 / 10x / isolated** |
| `maintenance_margin_rate` | 0.005 | 0.005 | **0.0056** = Bitget BTCUSDT tier-1 MMR 0.40 % (0–200 000 USDT, 125x tier table, in force since 2025-08-03) + 0.16 % clearance (taker 0.06 % + 0.10 % slip buffer); conservative = liquidates EARLIER |
| isolated liquidation (SNIPPER) | — | — | long `(q·avg − margin) / (q·(1 − mmr))`, short `(margin + q·avg) / (q·(1 + mmr))` ≈ avg × (1 ∓ (1/lev − mmr)): **~9.4 % adverse at 10x**, 13.7 % at 7x, 19.4 % at 5x, 32.8 % at 3x, 49.4 % at 2x, unreachable (long) at 1x |
| layer 1 / adds / caps | 2 % E0 to `inv`, cap 1.5 × E0; adds 0.5 × N1, max 3 layers, gap 3, in profit, phase ignition/expansion, guardian not against, open risk <= 6 % E0, notional <= 3 × E0, ML RSI regime == side | same | same (1R = 34 USDT at E0 = 1700 when the cap does not bind) |
| Konkorde on the trigger | leader (high band) | leader | **leader by owner order** (supersedes §0.3 for this profile; `model="vote"` still excludes it below 4h) |

Fills at the close of the decision candle (ENTER, add, partial take, exit);
costs E16 per layer per side: fee 0.10 % + slippage 0.05 % of the notional;
funding 0.01 % of the total open notional per 8 h held on every trade (after a
partial take, on the remaining notional); funding and the liquidation check run
on EVERY trigger candle (`PositionLedger.mark`, hours = 1 / 4 / 24). An ENTER
on the last candle is not filled; still open at the end -> `end_of_data` at the
last close. One book per run (long or short at a time, no flips); cells split
the book's trades by side.

## 6. Metrics and verdict (per cell: long, short; IS, OOS, total)

Reported: n, win rate, expectancy net R, median R, PF net, CI95 cluster
bootstrap (symbol, month; 10 000 resamples, seed 42), max DD in R, max DD in
USDT and in % of the start (cumulative net USDT of the cell's trades), net
USDT, avg layers, partial takes, exit mix, `info_phase_lost` candle count;
book level: equity final, return %, max DD of the equity curve (USDT and %),
max exposure, **number of liquidations**.

**GO** (owner's criterion, mechanical in `verdict_r4`) iff ALL:

* `n_total >= 30` (else **INCONCLUSIVE**, whatever the sign) AND `n_oos >= 10`;
* `expectancy_net_oos > 0`;
* `PF_net_total >= 1.2`;
* `liquidations == 0` in the book;
* `maxDD_usdt / start < 35 %` for the cell.

**NO-GO** otherwise. The round-2 §6 R-based verdict (expectancy >= +0.10 R,
CI95 lower > 0, IS > 0, PF >= 1.2, DD <= 10 R) is printed next to it for
continuity and does not decide round 4b.

**Profile verdict**: GO iff BOTH cells (long and short) are GO. One cell GO =
"GO parcial" (that side only may go to the paper gate). The H-lev proposal is a
PROPOSAL of leverage, not a pass of H4b-SNIPPER at 10x.

## 7. What will NOT be done

* No change of windows, `n_confirm`, caps, `inv` definition, exit order, the
  take fraction, `ctx_swing_back`, the MMR or the leverage list after seeing
  results; a change = `impulse-2.3.0` + new pre-registration.
* No re-cutting by regime or sub-period, no extra split, no best-cell or
  best-leverage selection beyond the ordered H-lev list (first GO wins).
* No looser GO threshold; INCONCLUSIVE stays INCONCLUSIVE.
* No exchange calls if the cache covers the window (it does); no Mongo, no
  Telegram, no deploy, no push.

## 8. Expected outcome stated in advance

Removing `phase_lost` and the time stop makes trades LONGER: more candles held,
more funding, more partial takes, and the exits move to the structural
invalidation (wide: a 10-candle guardian swing) and to the guardian ML RSI
flip. Expected: fewer trades than round 2 (n may fall under 30 on PRO 4h ->
INCONCLUSIVE), larger per-trade dispersion in USDT, expectancy sign not
established (round 2 showed no leader beats the chance rate, and the 1h study
repeats that). SNIPPER 10x: liquidations expected 0 (a 9.4 % intrabar move
against a 1h position whose guardian has not yet closed beyond a wide swing is
a flash-crash scenario) but NOT impossible with 3 layers; H4b-SNIPPER expected
NO-GO on at least one cell (PF < 1.2 or OOS <= 0); the sweep is expected to
change liquidations only, so "no leverage passes" is the most likely fallback
answer. Owner replay: with no `phase_lost` the anchored short should survive
2026-10-10; whether it survives to 2026-10-31 depends on the 1d / 4h ML RSI
and the structural level — reported, not predicted.

## 9. Sources for the Bitget margin figures

* Bitget tiered maintenance margin (BTCUSDT / ETHUSDT tiers, 2025-08-03):
  https://www.bitget.com/support/articles/12560603884259
* Bitget futures: tiered maintenance margin explained:
  https://www.bitget.cloud/asia/support/articles/12560603777225
* Bitget forced reductions and liquidations (MMR includes the clearance fee):
  https://www.bitget.com/academy/Forced-reductions-and-liquidations-on-Bitget

## 10. Runs (in the owner's order) and command

1. `pro:R4` (4h) and `pro_1d:R4` (1d) — 5x cross, 1300, re-buys.
2. `snipper:R4` (1h) — 10x isolated, 1700, re-buys, wick liquidation, funding;
   then the H-lev sweep 7x / 5x / 3x / 2x / 1x.
3. Owner replay on `pro:R4` (4h) and `snipper:R4` (1h).

```
docker compose --profile backtest run --rm -e TELEGRAM_BOT_TOKEN= backtest \
  python scripts/run_impulse_backtest_r4.py --md-out /app/docs/impulsos-v2-backtest-r4.md
```

## 11. Result commit

Run `20261101T074719Z` after this file was committed (`25071ba`). Results:
`docs/impulsos-v2-backtest-r4.md` (+ §"Round 4b results" of `docs/impulsos-v2.md`).
**No cell is GO.** PRO 4h: INCONCLUSIVE (long n 7, −0.140 R; short n 7,
−0.201 R; book −5.0 %, 0 liquidations). PRO 1d: INCONCLUSIVE (n 1 / 1).
SNIPPER 1h 10x isolated: NO-GO both cells (long n 31, OOS −0.097 R, PF 0.88;
short n 34, OOS −0.166 R, PF 0.70; book −25.7 %, max DD 33.7 %, **1
liquidation** on 2026-03-02 at 69 163 before the 4h close beyond the
invalidation). H-lev sweep: 0 liquidations from 7x down, every cell still
NO-GO -> **no leverage passes** (7x = highest with 0 liquidations, not a GO).
Owner replay: 4h anchored short cut next candle by the guardian ML RSI
(−0.10 R); 1h anchored short closed by the structural invalidation on
2026-10-21 at −2.84 R (3 layers). No amendment was made. Expected outcome
(§8) held except one detail: the liquidation at 10x that §8 called a
flash-crash scenario did happen once (a 9.4 % 2-day move inside the guardian's
wait). The only post-run change is a Python 3.10 f-string syntax fix in the
runner's progress line (`25071ba` -> result commit), no parameter touched.
