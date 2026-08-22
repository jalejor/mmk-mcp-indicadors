# PRE-REGISTRATION — R-FEP-CONT (rule_version 0.3.0 candidate)

**Status: FROZEN. Written and committed BEFORE any outcome was computed.**
Nothing in sections 1–11 may be edited after the first result exists; the
only permitted later edit is section 12 (recording the result commit) and an
explicit, dated `AMENDMENT` block that states what was changed and why.

* Date frozen: 2026-08-22
* Author: `trading` agent (mmk), on the owner's order "terminarlo".
* Mandate: re-council 2026-08-16 (`mmk-recouncil-fec-2026-08-16`) —
  *"máximo 1 rediseño (v0.3.0) y solo backtest-first: hipótesis falsable
  escrita + listón PB-1D (8y, fees+slippage, IS/OOS) ANTES de abrir otra
  ventana shadow"*. Deadline 2026-09-30.
* Scope: **backtest only**. This document authorises NO alert, NO shadow
  window, NO order. A PASS produces a *proposal* for an mmk-council; the
  council alone can open a shadow window.

---

## 0. Why this rule, and what it must NOT inherit

The 2026-08-16 re-council killed the FEC yardstick (forward contrary
hit-rate 41.4%, n=162, against a pre-registered >= 0.60) but recorded one
effect that survived every recomputation: the **FEP subset resolved
*contrary* only 19.8% of the time (z ~ -9.2 under the base rate)** — i.e.
"probable false entry" behaves like *a real entry that is slow*, not like a
reversal. §J.1 of the spec has the owner's own words for the same idea
("la continuación de ese corto iría si horas no pasa el AO y hay un cambio
de ADX").

That prior is **motivation, never validation**: it comes from the very
sample that suggested it, and it was measured with a flat 0.5% / 10-candle
yardstick that the re-council retired. This pre-registration therefore

* states the hypothesis in **R** (expectancy with stop/target/fees), never
  as a binary hit-rate — re-council blocking condition #3;
* normalises the threshold by **ATR and timeframe** (stop = 1.5 x ATR14 of
  the trigger TF), never a flat percentage — blocking condition #4;
* defines an explicit **control group / base rate** — blocking condition #1;
* uses an **outcome resolver that is committed code with a golden test**,
  and stamps the yardstick (`outcome_vara`) into every record — blocking
  condition #2;
* runs from a **harness committed in this repo** with a data manifest —
  blocking condition #5.

Priors stay `not_established` (spec §I.9d). No `p_false` number is produced,
consumed or restored by this work.

---

## 1. Hypothesis (falsifiable)

> **H1 (directional).** On a closed candle, an AO zero-cross of direction
> `d` that has survived `confirm_candles = 5` closed candles **without** a
> favourable ADX turn and **without** an opposite re-cross (engine state
> `FALSE_ENTRY_PROBABLE`) is a **continuation** signal in direction `d`:
> entering in direction `d` at that candle, with the standard mmk ATR trade
> model and real costs, yields a **positive net expectancy in R** that is
> materially above the unconditional base rate of the same market, the same
> timeframe and the same trade model.

> **H0 (what would refute it).** FEP entries in direction `d` are worth no
> more than an unconditional entry: `E[R_net | FEP] - E[R_net | control] <= 0`,
> or `E[R_net | FEP] <= 0` outright.

H1 is directional (one-sided) and pre-committed: if the measured edge is
*negative* — i.e. FEP is a genuine fade signal — that is **not** a pass by
sign-flip. Taking the contrary side of FEP was never the hypothesis and is
explicitly out of scope for v0.3.0 (that was FEC, already refuted).

---

## 2. Signal definition (exact, code-level)

The signal is computed by the **existing, unmodified engine function**
`src/controllers/metrics/setup_service.py :: false_entry_state()` with
`FALSE_ENTRY_PARAMS = FalseEntryParams(confirm_candles=5,
early_warning_candles=2, confirm_bars=1, p_false_prior=None)` — the shipped
defaults. No parameter of that function is tuned by this study.

Per closed candle `i` (index into the trigger-TF frame) and per direction
`d in {up, down}`:

```
fe = false_entry_state(ao, adx14, plus_di, minus_di, direction=d)   # on bars [.. i]
```

* **Arm A entry (the hypothesis) — `FEP-CONT`**: fires on the **rising edge**
  of `fe.state == "FALSE_ENTRY_PROBABLE"` for direction `d` (the first bar
  on which that state holds after not holding on `i-1`). Side: `long` if
  `d == up`, `short` if `d == down`. One entry per cross event; a later
  same-direction cross that re-enters FEP is a new event.
* No other condition is added. No BBWP filter, no Konkorde, no regime, no
  session filter, no symbol selection. Adding any filter after seeing
  results is forbidden (§10).

Warm-up: bars with index < 300 in the enriched frame are skipped (same
`warmup_bars = 300` as the F0 harness that produced the listón).

**Windowing.** For runtime, `false_entry_state` is called on a trailing
window of the last 300 bars instead of the full history. Verified on
BTC/USDT 1h 2018-06→2019-07 (9,137 bars, 18,274 evaluations): rising-edge
state counts are **identical** to the full-series call
(`FALSE_ENTRY_PROBABLE` 280, `CONFIRMED` 75, `WATCHING` 418, `WHIPSAW` 73).
A golden test asserts this equivalence; if it ever fails the run is invalid.

---

## 3. Arms (the control group — blocking condition #1)

All four arms are resolved by the **same** resolver, on the **same** bars,
with the **same** costs. Only the entry rule differs.

| Arm | Id | Entry rule | Role |
|---|---|---|---|
| **A** | `FEP-CONT` | rising edge of `FALSE_ENTRY_PROBABLE`, side = cross direction | **the hypothesis** |
| **B** | `CONFIRMED` | rising edge of `CONFIRMED` (favourable ADX turn inside the 5-candle window), side = cross direction | doctrine arm — what the strategy already calls tradable |
| **C** | `BASE-RATE` | unconditional entry every **20th** bar, both sides, no condition at all | **the control group / base rate** |
| **D** | `WHIPSAW` | rising edge of `WHIPSAW`, side = cross direction | negative control (a resolved failure should not pay) |

Arm C is deterministic (fixed grid, no RNG) and is the reference for the
"edge over the coin" leg of the gate. Its stride (20 bars) is fixed here and
may not be changed after results.

---

## 4. Trade model and outcome resolver (blocking conditions #2, #3, #4)

Identical to the model that produced the PB-1D listón — this is what makes
the comparison legitimate.

* **Entry price**: close of the signal bar (primary). Sensitivity S1: open of
  the next bar, with the stop/target walk starting on that same bar.
* **Stop**: `1.5 x ATR14` of the trigger TF (risk profile `medium`, from
  `sizing_profiles.ATR_PROFILES` — the live/backtest parity table).
* **Target**: `3.0 R` (same table).
* **Exit**: first touch, walking forward bar by bar; **stop wins over target
  inside the same bar** (worst case). No time stop in the primary; open at
  the end of the sample -> exit at the last close, `exit_reason =
  end_of_data` (same convention as the listón; the count of such trades is
  reported separately).
* **Costs**: fee 0.10% + slippage 0.05% **per side** (owner Q9 base model),
  charged on notional; in R:
  `cost_R = (fee + slip) * (entry_price + exit_price) / stop_distance`.
* **Resolver**: `SetupBacktestService._simulate_outcome()` — the committed
  method, called directly (not re-implemented). Its behaviour is pinned by a
  numeric golden test added with this study.

**`outcome_vara` stamped on every record** (blocking condition #2):

```
atr14x1.5_stop|3.0R_target|stop_first_intrabar|fee0.0010+slip0.0005_per_side|
resolver=setup_backtest_service._simulate_outcome|entry=close_of_signal_bar
```

**Structural fee drag** (computed before the run, BTC/USDT 2024, median
`ATR14/close`): the cost of a round trip expressed in R is
`2 * 0.0015 / (1.5 * ATR/close)`:

| TF | median ATR14/close | stop distance | **fee drag per trade** |
|---|---|---|---|
| 30m | 0.485% | 0.728% | **0.412 R** |
| 1h | 0.707% | 1.061% | **0.283 R** |
| 4h | 1.468% | 2.202% | **0.136 R** |
| 1d | 3.619% | 5.429% | **0.055 R** |

This is stated in advance so no one can call it a surprise afterwards: on
the primary TF the rule must find **+0.43 R gross** just to show +0.15 R
net. If it fails only because of costs, that is still a failure — mmk pays
those costs.

---

## 5. Universe, period, split, data (blocking condition #5)

* **Symbols**: `BTC/USDT`, `ETH/USDT`, `SOL/USDT`, `BNB/USDT` — the exact 4
  majors of the 8-year F0 run that produced the listón.
* **Exchange / data source**: `binance` spot OHLCV via ccxt (same source as
  `f0_gate_pb_majors_binance.json`). Per symbol/TF the run records rows,
  first/last timestamp and a **sha256 of the raw OHLCV matrix** in the
  result manifest.
* **Timeframes**: `1h` (**PRIMARY**), plus `30m`, `4h`, `1d` (secondary).
  The primary cell is fixed *a priori* by two independent facts: the owner's
  R-CONT dictation names "horas" (spec §J.1), and 89% of the shadow FEP
  population that motivated the hypothesis lived in 30m+1h.
* **Period**: `2018-07-01T00:00:00Z` -> `2026-07-01T00:00:00Z` (identical to
  the listón run). Data after 2026-07-01 is **deliberately not touched** by
  this study and stays sealed as a future holdout.
* **IS / OOS split — fixed by date, not by fraction**:
  * **IS**: 2018-07-01T00:00:00Z -> **2024-02-05T09:36:00Z** (5.60 years)
  * **OOS**: **2024-02-05T09:36:00Z** -> 2026-07-01T00:00:00Z (2.40 years)
  * That instant is not chosen by us: it is the `in_sample_end` already
    burned into `f0_gate_pb_majors_binance.json` (70/30 of the same window),
    so listón and candidate are split at the identical moment.
  * A signal belongs to the block that contains its **entry** time.
* Symbols whose listing starts after 2018-07-01 (SOL/USDT) contribute only
  the history that exists; per-symbol coverage is reported.

---

## 6. Metrics and statistics

**Primary metric.** Per-signal **net expectancy in R** of arm A in the
primary cell (`1h`, 4 majors pooled, both directions), computed separately
for IS and OOS. Secondary blocks: win rate, profit factor, avg win/loss R,
median R, n, exit-reason mix, unresolved count.

**Portfolio (economic) basis.** Independently, arm A is also executed as a
portfolio with **max 1 concurrent position per symbol** (same rule as the
listón run), giving total R, R per year and trade-level max drawdown. This
basis — not the per-signal one — is what gets compared to PB-1D's R/year.

**Uncertainty.** FEP signals overlap heavily, so a naive i.i.d. bootstrap
would understate the error. Pre-registered method:

* **Cluster bootstrap**, cluster = `(symbol, calendar month)` of the entry,
  10,000 resamples, `numpy` seed **20260822**, percentile 95% CI.
* The naive i.i.d. CI is reported alongside for transparency, and is never
  the basis of a decision.
* Point estimate of the difference `A - C` with its own cluster-bootstrap CI
  (clusters resampled jointly so both arms move together).
* Welch t-test p-values are reported as a courtesy; the CI decides.

**Multiple comparisons.** The gate is decided **only** on the primary cell.
The three secondary TFs are reported with **Holm-adjusted** p-values across
the 4 TF cells and can never, on their own, produce a PASS (§10).

**Pre-registered sensitivities** (reported, never decisive):
S1 next-bar-open entry · S2 60-bar time stop (implemented by truncating the
forward frame, so the committed resolver is still the one deciding) ·
S3 risk profiles `low` (1.0x/2.0R) and `high` (2.0x/4.0R) · S4 per-symbol
and per-side (long/short) breakdown · S5 IS/OOS by calendar year.

---

## 7. The listón (PB-1D, 8 years, fees + slippage, IS/OOS)

Recomputed from the committed artefact `f0_gate_pb_majors_binance.json`
(4 majors, binance, 2018-07-01 -> 2026-07-01, fee 0.10% + slip 0.05% per
side, medium profile, IS end 2024-02-05T09:36:00Z), pooled over the 4
symbols, longs + mirrored shorts:

| Block | n | expectancy | win rate | PF | total R | R / year |
|---|---|---|---|---|---|---|
| **FULL 8y** | 21 | **+0.6262 R** | 42.9% | 2.054 | +13.15 R | **+1.644 R/yr** |
| IS (5.60y) | 13 | +0.1959 R | 30.8% | 1.275 | +2.55 R | +0.455 R/yr |
| **OOS (2.40y)** | 8 | **+1.3255 R** | 62.5% | 4.312 | +10.60 R | **+4.421 R/yr** |

Per symbol (full): BTC +5.53 R (n=9) · ETH +3.85 R (n=4) · SOL +3.89 R
(n=4) · BNB −0.12 R (n=4). By side: long +0.942 R (n=12), short +0.205 R
(n=9).

This is the only proven edge mmk owns, and it is also the alternative use of
the cycles (the re-council's instruction was to spend freed cycles widening
PB-1D's universe). Beating it is the point.

---

## 8. GATE — what counts as PASS, before seeing anything

Decided **only** on the **primary cell**: arm A, `1h`, 4 majors pooled, both
directions, **out-of-sample** block, primary entry mode, medium profile.

| Leg | Requirement |
|---|---|
| **L1 — quality** | OOS per-signal expectancy **>= +0.15 R** net **AND** the lower bound of the 95% cluster-bootstrap CI **> 0** |
| **L2 — economics** | OOS **portfolio** basis **>= +1.644 R/year** (PB-1D's stable 8-year rate). Flag `L2-strong` if it also clears **+4.421 R/year** (PB-1D's same-window OOS rate) |
| **L3 — control** | `E[R \| A] - E[R \| C]` in OOS **>= +0.15 R** with 95% cluster-bootstrap CI lower bound **> 0** |
| **L4 — sample** | **n >= 30** arm-A signals in the OOS primary cell |
| **L5 — stability** | IS expectancy **> 0**, OOS **>= 0.5 x** IS expectancy, **and** the sign of the expectancy holds in **>= 3 of the 4 symbols** in OOS |

* **PASS = L1 AND L2 AND L3 AND L4 AND L5.** Consequence: write a shadow-window
  proposal for an mmk-council. **The council decides; this document does not
  open anything.** Even a PASS does not authorise an audible alert.
* **NO PASS = any leg fails.** Consequence, per the re-council's stopping
  rule (max 1 redesign, deadline 2026-09-30): **archive the FEC/FEP family**.
  No v0.4.0. False-entry alerts stay prohibited until evidence arrives from a
  different source. Freed cycles go to widening PB-1D's universe.
* There is **no third branch.** "Almost" is NO PASS.

**TURN-IGNITION** (22.4%, n=85, negative mean excursion — NO-GO answered
early on 2026-08-16) is decided with this document, as the re-council
ordered: its destiny follows the same verdict. If FEP-CONT does not pass,
R-TURN-IGNITION's shadow block is archived too (persist-only stops being
written, or is kept only if its cost is exactly zero) — it is the same
family of "a monitor that fires and never proved it pays".

---

## 9. What we already know we cannot measure here

Stated in advance so it cannot be presented later as a finding:

1. **The shadow population is not re-used.** The 162 FEC / FEP forward
   adjudications live in the production Mongo of `mmk-api` and were sealed
   with the retired 0.5%/10-candle yardstick. This study does not read them:
   it is an independent historical replay. Consequence: it is **not** an
   out-of-sample confirmation *of the shadow sample*; it is a new test of
   the same hypothesis on 8 years of history.
2. **No live execution effects**: no partial fills, no funding, no order
   book, no exchange downtime, spot fees only, one instrument per position.
3. **Survivorship**: the 4 majors are alive today and were picked in 2026.
   The listón carries the identical bias, which is why the comparison is
   fair even though the absolute numbers are not.
4. **Overlap**: arm A signals overlap heavily on low TFs; the cluster
   bootstrap mitigates but does not eliminate this. The portfolio basis is
   the overlap-free reading and is why L2 exists.
5. **Binance history vs the live bitget feed**: the engine's default exchange
   in production is bitget (D1). This study uses binance for continuity with
   the listón. Any live deployment would have to re-verify on bitget candles.

---

## 10. Anti-p-hacking commitments

Frozen with this commit. Breaking any of these invalidates the run:

1. No parameter in §2, §3, §4, §5, §6 or §8 may change after the first
   result is computed. If a bug forces a change, it is recorded as a dated
   AMENDMENT with the diff and the run is redone in full.
2. No filter, sub-population, session, regime or symbol subset may be added
   after seeing results. Post-hoc subgroups may be *reported* as
   `EXPLORATORY — not evidence`, and may never move a gate leg.
3. A secondary TF that passes while the primary fails is **NOT a pass**. It
   is recorded as an exploratory note for the council.
4. The direction of the hypothesis is fixed (§1). A negative edge is a
   refutation, not a fade signal.
5. Thresholds are not re-derived from this sample. `0.15 R`, `n >= 30`, the
   `0.5x` IS/OOS ratio come from the existing F0 gate table
   (`scripts/run_f0_backtest.py :: GATE_THRESHOLDS`), not from this study.
6. The result document reports **every** pre-registered cell and
   sensitivity, including the unflattering ones, and states the count of
   cells that could not be computed.

---

## 11. Artefacts this study must produce

* `src/controllers/metrics/fep_cont_backtest.py` — arms + runner, a NEW
  module; it touches **no** live rule path (`rule_v020.py`,
  `monitors_v020.py`, `rules_service.py`, `setup_service.py` are read-only
  for this work).
* `scripts/run_fep_cont_backtest.py` — CLI, in Docker, writes one JSON with:
  manifest (data sha256, rows, ranges), config echo, `outcome_vara`, every
  cell, every sensitivity, and the full trade list per cell.
* `tests/test_fep_cont_golden.py` — numeric goldens: resolver R on a
  hand-built synthetic frame, arm classification, and the 300-bar windowing
  equivalence.
* `docs/FEP_CONT_V030_RESULTS.md` — results + verdict against §8.

---

## 12. Freeze record

* Pre-registration commit: **filled in by the commit that adds this file**
  (`git log --format=%H -1 -- docs/PREREG_FEP_CONT_v0.3.0.md`). Results
  commits are strictly later in the history; the ordering is the audit
  trail.
* Any AMENDMENT appends below with date, author, reason and diff summary.
