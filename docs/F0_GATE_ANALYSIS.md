# F0 Gate Analysis — Calibration Recommendations (rule_version 0.1.0)

**Inputs**: `f0_gate_report.json` (BTC/ETH/SOL, 2024-07→2026-07) and
`f0_gate_report_wide.json` (10 symbols, 2022-07→2026-07). Fee model: bitget
spot taker 0.10% + 0.05% slippage per side, both runs. Gate result: **0/6 and
0/20 rows PASS** — every row fails `n_trades_full >= 30`; 4 wide rows
(PB-1D on BTC/SOL/BNB, IMP-4H on SOL) fail **only** on sample size, with every
quality check green. Numbers below are pooled from the per-trade `r_net`
lists in the wide report unless noted.

## 1. Aggregate read by family (wide run, full period, cross-symbol pool)

| Setup | n | expectancy (R, net) | win rate | PF | worst per-symbol DD |
|---|---|---|---|---|---|
| PB-1D-LONG | 15 | **+0.55** | 40% | 1.89 | 4.6% (DOGE) |
| PB-1D-SHORT | 8 | **+1.15** | 62% | 3.97 | 3.1% (XRP) |
| IMP-4H-LONG | 57 | **−0.11** | 25% | 0.86 | 12.2% (XRP) |
| IMP-4H-SHORT | 31 | **+0.06** | 29% | 1.07 | 8.1% (BNB) |

IS/OOS (trade-weighted): PB-1D-LONG +0.62 IS → +0.27 OOS (n=3);
PB-1D-SHORT −1.03 IS (n=3) → +2.46 OOS (n=5) — sign flip on tiny n, unstable.
IMP-4H-LONG −0.05 IS → −0.39 OOS; IMP-4H-SHORT +0.15 IS → −0.04 OOS. IMP-4H
is negative-to-noise in aggregate and degrades OOS; it is stop-dominated
(43/57 long exits and 22/31 short exits are stops).

**Tier cut** — majors = {BTC, ETH, SOL, BNB}, rest = the other 6:

| Family × tier | n | exp (R) | WR | PF | OOS n / exp |
|---|---|---|---|---|---|
| PB-1D majors | 9 | **+2.44** | 89% | 21.2 | 5 / **+2.04** |
| PB-1D rest | 14 | **−0.32** | 21% | 0.61 | 3 / +0.96 |
| IMP-4H majors | 37 | −0.25 | 22% | 0.71 | 16 / −0.12 |
| IMP-4H rest | 51 | +0.09 | 29% | 1.12 | 10 / −0.29 |

PB-1D majors R is not single-symbol driven: BTC +10.6R, SOL +5.9R, BNB +5.4R
(ETH: 0 candidates in 4y — flag, see §6). IMP-4H shows **no** tier structure:
its positive symbols are ADA (+0.93, n=8) and LTC (+0.77, n=13) with BNB
(−1.11) and LINK (−1.08) also non-majors — per-symbol dispersion, not signal.

## 2. Verdict per setup

**PB-1D — KEEP, restrict watchlist to majors tier (provisional, not a PASS).**
The majors/rest split is the cleanest result in the data (+2.44R vs −0.32R,
consistent long and short: majors long n=6 +2.27, majors short n=3 +2.79).
But n=9 pooled is far below any honest bar — treat "majors-only" as a
**hypothesis to confirm with a longer-history run (§6)**, not a calibration to
ship. No parameter changes to PB-1D itself: nothing in this sample justifies
touching thresholds that already show quality.

**IMP-4H — PARK (do not calibrate yet).** Reasons: (a) pooled expectancy
−0.11/+0.06 with OOS negative on both sides; (b) no coherent symbol/tier
pattern to restrict to; (c) the veto counterfactual (§3) shows the failure is
**entry timing**, not regime filtering — vetoed (stale-cross) signals OUTperform
accepted (fresh-cross) ones on longs, i.e. the setup as specified chases fresh
AO crosses that fail. Tuning BBWP 50→60 or A-grade-only V2 (§4) does not
address that and would be curve-fitting on a negative-expectancy base. The
honest calibration path is a **redefinition of the trigger** — E6 `trend_speed`
(spec §E6) as mandatory impulse-strength confirmation is the designated
candidate — then a fresh F0 run for the new `rule_version`. Until then IMP-4H
does not advance to F1.

## 3. Veto analysis (window 3 vs 5, signal-level counterfactual replay)

Note: `window_comparison` replays candidates without position-overlap
sequencing, so its expectancies differ from the `full` block (e.g. BTC
PB-1D-LONG: 1.93R sequential vs 1.32R replay). Compare within the replay only.

| Setup | w3 acc n/exp | w3 veto n/exp | w5 acc n/exp | w5 veto n/exp |
|---|---|---|---|---|
| PB-1D-LONG | 13 / +0.49 | 12 / −0.04 | 18 / +0.51 | 7 / **−0.46** |
| PB-1D-SHORT | 4 / +2.47 | 13 / +0.16 | 10 / +1.11 | 7 / +0.11 |
| IMP-4H-LONG | 44 / −0.09 | 122 / +0.07 | 63 / −0.14 | 103 / **+0.13** |
| IMP-4H-SHORT | 17 / +0.31 | 85 / +0.02 | 32 / +0.15 | 70 / +0.04 |

- **PB-1D-LONG: veto saves money, and w5 > w3.** All PB-1D vetoes are V2
  (`no_adx_turn_confirmation`). At w5 the vetoed subset is clearly toxic
  (−0.46R); the 5 signals w3 vetoes but w5 accepts averaged ~+0.54R each —
  the owner's relax-to-5 (Q10) is empirically right here.
- **PB-1D-SHORT: veto costs a little (vetoed +0.11R) but accepted quality is
  far higher.** Keep w5; n too small to argue.
- **IMP-4H-LONG: veto INVERTED.** All IMP-4H vetoes are V1 (`stale_ao_cross`).
  Accepted −0.14R vs vetoed +0.13R at w5, inverted in 5/9 symbols with
  signals (BTC −0.02 vs +0.64; DOGE −1.08 vs +0.91). Freshness is filtering
  the wrong way on this setup — evidence for §2's park-and-redefine, not for
  a bigger window.
- **IMP-4H-SHORT: mildly justified** (w5: +0.15 vs +0.04); the narrow run
  disagrees (accepted +1.16 vs vetoed +1.45) — inconclusive.

**Recommendation**: make veto windows **per-setup parameters** in the rule
document (they already are conceptually — this confirms per-setup values will
diverge). For PB-1D lock `confirm_window = 5` (validated). For IMP-4H leave
V1/V2 untouched until the family is redefined; do not ship a "no-veto IMP-4H"
even though the counterfactual flatters it — +0.13R on vetoed signals is still
below the gate's +0.15R bar and pre-fee-sequencing.

## 4. adx_turn A/B grades — inconclusive, do NOT restrict V2 to A-grade

Pooled (wide): PB-1D-LONG A n=7 +0.10 vs **B n=8 +0.95** (B wins);
IMP-4H-LONG A n=33 −0.00 vs B n=24 −0.26 (A wins); IMP-4H-SHORT A n=15 +0.23
vs B n=16 −0.10 (A wins); PB-1D-SHORT B has n=1. The narrow run **contradicts**
the wide one on IMP-4H-LONG (A −1.10 vs B +0.59). A>B does not replicate
across runs or setups — this is n-noise, not a graded-quality signal, and on
longs the wide data points the *other* way. **Verdict: keep both grades
accepted, keep stratifying in every report; V2 A-grade-only (spec §E1
refinement) stays parked until one grade dominates with pooled n ≥ 30 per
grade and a consistent sign across runs.**

## 5. The gate's n problem — reformulate the unit, keep the bar

These setups produce ~2-6 signals/symbol/year on 1d and ~7/symbol/year on 4h;
`n >= 30` per family×symbol needs 10-25 years of data per symbol. The sample
requirement is right; the aggregation unit is wrong. Proposed gate v2 (§C):

1. **Pooling unit = family × side × declared tier** (tier fixed *before* the
   run, e.g. majors), pooled across the tier's symbols. `n_full >= 30` and
   `n_oos >= 10` apply to the pool. All quality thresholds (exp ≥ +0.15R full,
   ≥ +0.10R OOS, PF_oos ≥ 1.15, DD ≤ 20%, OOS ≥ 50% IS) unchanged, computed
   on the pool.
2. **Anti-concentration guards** (replace the old 2-symbol robustness row):
   expectancy > 0 on ≥ 60% of tier symbols with ≥ 1 trade, and no single
   symbol contributes > 50% of pooled net R.
3. **How to reach n**: longer history + more same-tier symbols (§6), never by
   lowering thresholds. F2 paper trading *accrues* to the pool with the same
   logging schema but cannot substitute the backtest n (at ~9 majors-PB
   trades/4y, waiting on paper alone means years).
4. Under gate v2, current status: PB-1D majors pool n=9 → **still NO PASS**
   (needs ~3-4× more data); IMP-4H → NO PASS on expectancy regardless of n.
   The gate stays honest: nothing passes today.

## 6. Next experiments (highest information per run)

1. **PB-1D majors, long history** — attacks the only open PASS path:
   `python scripts/run_f0_backtest.py --symbols BTC/USDT ETH/USDT SOL/USDT BNB/USDT --exchange binance --start 2018-01-01 --end 2026-07-01 --setups PB-1D-LONG PB-1D-SHORT --json-out f0_pb1d_majors_8y.json`
   (binance for depth of history — geo-block is cloud-only, run locally; fee
   defaults already model bitget. Fallback `--exchange bybit`). Expected pool
   n ≈ 30-45. Decision rule: gate-v2 PASS → PB-1D majors goes to F1 watcher;
   expectancy collapses pre-2022 → majors edge was regime-specific, stay F0.
2. **IMP-4H veto-inversion replication on the same 8y window** (before any E6
   work): `python scripts/run_f0_backtest.py --symbols BTC/USDT ETH/USDT SOL/USDT BNB/USDT XRP/USDT ADA/USDT DOGE/USDT LINK/USDT LTC/USDT --exchange binance --start 2018-01-01 --end 2026-07-01 --setups IMP-4H-LONG IMP-4H-SHORT --json-out f0_imp4h_9sym_8y.json`
   — if vetoed>accepted persists on longs with ~3× the replay sample, that is
   the spec for the E6-based trigger redesign; if it vanishes, 2022-2026 was
   noise and plain recalibration re-opens.

**Data-quality flags to fix first**: AVAX/USDT returned **0 candidates in all
4 setups** over 4y (likely fetch/listing gap — exclude or verify before it
silently dilutes tier stats); ETH/USDT produced 0 PB-1D candidates in 4y
(plausible but verify the 1d context alignment on ETH specifically).
