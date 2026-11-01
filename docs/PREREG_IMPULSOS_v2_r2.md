# PRE-REGISTRATION — Impulsos v2 round 2 (`impulse-2.1.0`, sequential model) vs round 1 and legacy

**Status: FROZEN. Committed BEFORE the first run of the sequential machine on
the backtest window.** Sections 1–10 may not be edited after the first
sequential number exists; later edits are limited to §11 (result commit) and
dated `AMENDMENT` blocks. Git order is the audit trail (same pattern as
`PREREG_IMPULSOS_v2.md` and `PREREG_FEP_CONT_v0.3.0.md`).

* Date frozen: 2026-11-01 (night session, after owner decisions 1–4).
* Source of truth: `docs/impulsos-v2.md` §R2 (`f277c55`, `e94d4be`). Where
  this file and §R2 differ, §R2 wins and the difference is a bug here.
* Engine under test: `src/controllers/metrics/impulse_sequential.py`
  (`SequentialMachine`, `ImpulseParams.sequential`), ML RSI port
  `src/controllers/metrics/ml_rsi.py`, layered ledger
  `impulse_backtest.PositionLedger` + `drive_sequential`.
* Harness: `scripts/run_impulse_backtest_r2.py` (committed with this file).
* Scope: **backtest only**. A PASS produces a proposal for paper (§R2.k),
  never an order.

---

## 1. Hypotheses

> **H1 (sequential, no ML RSI gate).** For each mandatory cell, the
> leader -> follower machine with PRO re-buys has a **positive net expectancy
> in R** that clears the §g listón (section 6) on BTC/USDT bitget,
> 2024-11-01 -> 2026-10-31, in both halves of the split.

> **H2 (H1 + ML RSI regime gate, owner decision 4).** Same cells with the
> gate (green = longs only, red = shorts only, gray = no ENTER / no re-buy).

> **H-cmp (informational).** Like for like (4h, long): H1 and H2 net
> expectancy above round 1 `pro` (+0.146 R) and above legacy (-0.141 R);
> round 2 vs round 1 on the short side (-0.374 R); and H2 vs H1 on every cell.

> **H0.** Any mandatory cell fails a §g leg or has n < 30 (INCONCLUSIVE).

## 2. Universe and data

Identical to round 1 (`PREREG_IMPULSOS_v2.md` §2): BTC/USDT bitget spot
OHLCV, closed candles, cached frames with sha256 in the result JSON (4h
`a9ec96296cf4…`, 1d `1fd23248b1c1…`, 1w `3c483695e2db…`, 1M `2564ebf1f1c1…`),
>= 300 trigger bars of warm-up, gaps = 0.

## 3. Split

IS 2024-11-01 -> 2025-12-31; OOS 2026-01-01 -> 2026-10-31. A trade belongs to
the block of its ENTER candle (layer 1).

**The only IS-fitted parameters are the follower windows** (§R2.b formula,
lead-time study `docs/impulsos-v2-lead-time.md`, committed before this run):

| profile | trigger | `W_ao` | `W_adx` | `W_macd` | `W_rsi` | `alert_ttl_bars` | note |
|---|---|---|---|---|---|---|---|
| `pro` | 4h | 2 | 4 | 3 | 2 | 4 | all four fitted (136 / 24 / 91 / 98 IS pairs) |
| `pro_1d` | 1d | 3 | 3 | 2 | 5 | 5 | `adx` had 6 pairs < 10 -> default 3 |

Pre-declared "leaders lead" test (§R2.h): **NOT SUPPORTED** on 4h (leader
median lead 3.0 vs ao 5.0 / macd 5.0 / rsi 4.0 / adx 2.0) nor on 1d (4.0 vs
5.0 / 5.0 / 6.0 / 3.0). Reported as such; the machine runs unchanged.
Konkorde base rates (§R2.a): verde > 0 on 86.9 % of 4h IS bars, 76 + 76 zero
crosses (no alarm); 1d 86.9 %, 13 + 13.

## 4. Cells

| Cell | Profile | Trigger / guardian | Variant | Status |
|---|---|---|---|---|
| pro 4h long / short | `pro` | 4h / 1d (1w informational) | H1 and H2 | mandatory |
| pro 1d long / short | `pro_1d` | 1d / 1w (1M NaN on bitget, informational) | H1 and H2 | mandatory (expected INCONCLUSIVE, n small) |

One book per run (long or short, no flips); cells split the book's trades by
side, as in round 1.

## 5. Execution and cost model

* ENTER / `add_layer` at the **close** of the decision candle; all layers exit
  together at the close of the exit candle (§R2.d: Jeisson rule,
  invalidation ON CLOSE, `phase_lost` with verde against, time stop 60
  candles below +0.5 R). No ATR stop. An ENTER on the last candle is not
  filled.
* Sizing (§R2.c): E0 = realised equity at ENTER (starts 1300 USDT, compounds
  with realised net PnL); layer 1 risks 2 % E0 to the invalidation, capped
  at 1.5 x E0 notional; adds = 0.5 x layer-1 notional, max 3 layers, gap >= 3
  candles, only in profit, phase ignition/expansion, guardian not against,
  open risk <= 6 % E0, notional <= 3 x E0.
* Cross margin 5x, maintenance 0.5 %: liquidation checked INTRABAR on every
  candle at the adverse extreme (`PositionLedger.mark`). Any liquidation
  fails the cell regardless of R.
* Costs E16 per layer per side: fee 0.10 % + slippage 0.05 % of the layer
  notional. Funding 0.01 % of total notional per 8h held, charged on every
  trade (PRO is leveraged both ways).
* **R unit = layer-1 risk in USDT** (`qty_1 x |P_1 - inv|` = 26.00 USDT at
  E0 = 1300 when the cap does not bind). Trade R = net PnL (all layers,
  after costs and funding) / R unit. Reported alongside: USDT PnL, equity
  curve return %, max drawdown of equity %, avg layers, max exposure.

## 6. Metrics and verdict (per cell; IS, OOS, total)

As round 1 §6: n, win rate, expectancy net R, median R, PF net, max DD in R,
avg bars held, exit reasons, 95 % (symbol, month) cluster bootstrap CI (10 000
resamples, seed 42), confidence terciles (informational).

* **INCONCLUSIVE** if `n_total < 30`.
* **PASS** iff `n_total >= 30` AND `expectancy_net_total >= +0.10 R` AND CI95
  lower `> 0` AND `n_oos >= 10` with `expectancy_net_oos > 0` AND
  `expectancy_net_is > 0` AND `PF_net >= 1.2` AND `maxDD <= 10 R` AND
  `liquidations == 0`.
* **NO-PASS** otherwise. Computed mechanically (`impulse_backtest.verdict` +
  the liquidation check in the harness).

## 7. ML RSI (H2) — parity status recorded BEFORE the run

The §R2.e2 parity gate asked for value 40.07 / upper 59.74 / lower 44.30
(± 2) on the closed 2026-10-31 daily candle. Port result
(`scripts/check_ml_rsi_parity.py`, long 1d bitget cache 3022 candles):

* The public Pine builds its arrays with `array.new_float(3)` + `push`, so
  its k-means is dead code and **what TradingView plots is the 25th / 75th
  percentile of the last 3000 smoothed RSI values**. Percentile port: upper
  **59.76**, lower **44.09** (parity ✅ 0.02 / 0.21 pts). The k-means the
  script describes gives 68.3 / 39.2 (❌). The port runs the percentile
  method by default (`ml_rsi.py`), ALMA offset 0 as hard-coded in the Pine.
* Value: closed 2026-10-31 candle gives 42.37 (raw RSI19 39.69); the owner's
  40.07 was read on the FORMING 2026-11-01 candle. Value parity is
  **not established on the closed candle** (gap 2.3 > 2): recorded here, and
  H2 is run as pre-registered with the percentile port because the
  thresholds — the only part of the indicator that gates the engine — match
  the owner's chart. This is a reporting decision taken before any
  sequential number existed, not a parameter change.
* Thresholds are causal (trailing 3001 values ending at the decision
  candle; repaint vs the TV-anchored window is measured and reported).

## 8. Owner's open short (§R2.g) — informational, reported in full

`owner_bar` = 4h closed candle with close nearest 82450 in
[2026-10-08, 2026-10-16); machine state at that candle (4h H1/H2, 1d);
model's own first short in [2026-09-15, 2026-10-31] per run; anchored replay
(layer 1 forced at `owner_bar`, real re-buy and exit rules to 2026-10-31):
exit fired or unrealized gross / net in USDT and R. One trade, validates
nothing.

## 9. What will NOT be done

* No change of `n_confirm`, windows, caps, invalidation or exit parameters
  after seeing results; a change = `impulse-2.2.0` + new pre-registration.
* No re-cutting by regime or sub-period, no extra split, no best-cell
  selection post hoc: every mandatory cell is reported with its verdict.
* No looser threshold for INCONCLUSIVE 1d cells (follow-up = ETH + SOL
  pooled, same rules).
* The ML RSI value gap is not "fixed" by tuning the smoothing to hit 40.07.

## 10. Expected outcome stated in advance

Round 1 showed no 4h edge OOS for either engine and the lead-time study shows
no leader beating the chance rate. Expectation: pro 4h H1 NO-PASS (CI across
0); H2 trades less and may be INCONCLUSIVE; pro 1d INCONCLUSIVE (< 30
trades). Re-buys should raise the USDT PnL dispersion, not the sign of the
expectancy. Liquidations: 0 (an adverse move > 32 % from avg entry at max
notional would be needed).

## 11. Result commit

Run `20261101T071222Z` after this file was committed (`ecd603b`). Results:
`docs/impulsos-v2-backtest-r2.md` (+ §"Round 2 results" of `docs/impulsos-v2.md`).
**No mandatory cell PASSES.** pro 4h long H1: NO-PASS (n 30, −0.403 R, every
leg fails); pro 4h short H1: INCONCLUSIVE (n 27, +0.001 R); pro 4h H2:
INCONCLUSIVE (long n 12 +0.086 R, short n 26 +0.048 R); pro 1d: INCONCLUSIVE
(n 1–6). Liquidations 0. No amendment was made. Expected outcome (§10) held:
NO-PASS / INCONCLUSIVE, re-buys did not change the sign; H2 traded less.
