# RESULTS — R-FEP-CONT v0.3.0 (pre-registered study)

## VERDICT: **NO PASS** — the FEC/FEP family is archived

The hypothesis is **refuted**, and not narrowly: on the pre-registered
primary cell the rule is **-0.2249 R per signal out-of-sample** and its edge
over an unconditional entry is **+0.0227 R (95% CI [-0.045, +0.092])** — a
difference indistinguishable from zero on n=2,451. It fails 4 of the 5 gate
legs. Per the 2026-08-16 stopping rule (max 1 redesign, deadline 30-sep):
**no v0.4.0; false-entry alerts stay prohibited until evidence arrives from a
different source.**

The rule also fails its own gate on **every other timeframe**, so the verdict
is not an artifact of where the gate was aimed (§3.5).

* **Pre-registration**: `docs/PREREG_FEP_CONT_v0.3.0.md`, frozen at commit
  `0154a40f3d1a3c4577f9ddeccfaf4faee837e478` (2026-08-22 18:15:50 -05:00).
* **Harness**: commit `a1b5021`; sharding/merge `eedbfcc`.
* **Run artefact**: `fep_cont_v030.json` (committed, 124 KB, no trade lists).
  Trade-level dumps are reproducible with `--trades-out` (~285 MB, not
  committed).
* Every results commit is strictly later in the history than the
  pre-registration commit. That ordering is the audit trail.

---

## 1. What was run, exactly

```
# 4 shards, one per symbol, in Docker
python scripts/run_fep_cont_backtest.py --symbols <SYM>/USDT \
    --cache-dir <cache> --shard-out <shard>.jsonl
# pooled report + gate
python scripts/run_fep_cont_backtest.py \
    --aggregate-from BTC.jsonl ETH.jsonl SOL.jsonl BNB.jsonl \
    --json-out fep_cont_v030.json
```

4 arms x 4 timeframes x 4 majors, binance spot, 2018-07-01 -> 2026-07-01,
**1,047,000+ resolved signals**. IS/OOS split at **2024-02-05T09:36:00Z** —
the boundary already burned into `f0_gate_pb_majors_binance.json`, so the
candidate and the listón are split at the identical instant. Trade model and
resolver identical to the listón run (1.5 x ATR14 stop, 3R target, 0.10% fee
+ 0.05% slippage per side, stop wins intrabar). Cluster bootstrap by
`(symbol, calendar month)`, 10,000 resamples, seed 20260822.

**Sharding is execution mechanics, not a design change**: verified on the
full 1d cell, the sharded+merged report is byte-identical to the
single-process report for `cells` and `sensitivities`.

**Disclosed pre-run probes** (no outcome metric computed in any of them):
a runtime/event-count probe on BTC 1h 2018-06→2019-07 (justifying the 300-bar
trailing window); the structural fee-drag table; and the 1d pipeline
self-check above.

---

## 2. Data manifest

| TF | symbol | rows | first candle | last candle | events | sha256 (12) |
|---|---|---|---|---|---|---|
| 30m | BTC/USDT | 140,367 | 2018-06-24 | 2026-07-01 | 20,476 | `97ff04103916` |
| 30m | ETH/USDT | 140,367 | 2018-06-24 | 2026-07-01 | 20,363 | `a78cc28a81da` |
| 30m | SOL/USDT | 103,144 | 2020-08-11 | 2026-07-01 | 14,695 | `5b84702a9fdd` |
| 30m | BNB/USDT | 140,367 | 2018-06-24 | 2026-07-01 | 20,043 | `eb673fc47f22` |
| 1h | BTC/USDT | 70,341 | 2018-06-18 | 2026-07-01 | 10,189 | `dcb82b292fed` |
| 1h | ETH/USDT | 70,341 | 2018-06-18 | 2026-07-01 | 10,096 | `544ff0375549` |
| 1h | SOL/USDT | 51,575 | 2020-08-11 | 2026-07-01 | 7,365 | `0d7de5905b91` |
| 1h | BNB/USDT | 70,341 | 2018-06-18 | 2026-07-01 | 10,081 | `05218d8b2384` |
| 4h | BTC/USDT | 17,824 | 2018-05-12 | 2026-07-01 | 2,511 | `dd95184c0c64` |
| 4h | ETH/USDT | 17,824 | 2018-05-12 | 2026-07-01 | 2,505 | `a552c84e4d5a` |
| 4h | SOL/USDT | 12,900 | 2020-08-11 | 2026-07-01 | 1,804 | `5550680e2117` |
| 4h | BNB/USDT | 17,824 | 2018-05-12 | 2026-07-01 | 2,496 | `a4088eb00e38` |
| 1d | BTC/USDT | 3,223 | 2017-09-04 | 2026-07-01 | 414 | `fd15df6f3464` |
| 1d | ETH/USDT | 3,223 | 2017-09-04 | 2026-07-01 | 404 | `863d29a3c190` |
| 1d | SOL/USDT | 2,151 | 2020-08-11 | 2026-07-01 | 268 | `a38ef4e366f5` |
| 1d | BNB/USDT | 3,160 | 2017-11-06 | 2026-07-01 | 404 | `1f94762d64ea` |

SOL/USDT starts 2020-08-11 (listing); the other three cover the full window.
**Zero cells could not be computed.**

---

## 3. Results

### 3.1 Per-signal net R — every arm, every cell

| TF | arm | block | n | expectancy R | 95% CI (cluster) | WR | PF |
|---|---|---|---|---|---|---|---|
| 30m | **FEP-CONT** | IS | 10,715 | **-0.3172** | [-0.357, -0.277] | 0.259 | 0.68 |
| 30m | **FEP-CONT** | OOS | 4,910 | **-0.3579** | [-0.414, -0.302] | 0.266 | 0.66 |
| 30m | CONFIRMED | IS | 2,534 | -0.2079 | [-0.281, -0.135] | 0.278 | 0.78 |
| 30m | CONFIRMED | OOS | 1,174 | -0.2716 | [-0.363, -0.181] | 0.282 | 0.73 |
| 30m | BASE-RATE | IS | 35,478 | -0.3207 | [-0.348, -0.293] | 0.251 | 0.68 |
| 30m | BASE-RATE | OOS | 16,832 | -0.3744 | [-0.406, -0.342] | 0.256 | 0.64 |
| 30m | WHIPSAW | IS | 2,797 | -0.2788 | [-0.340, -0.217] | 0.269 | 0.72 |
| 30m | WHIPSAW | OOS | 1,137 | -0.3816 | [-0.479, -0.285] | 0.261 | 0.64 |
| **1h** | **FEP-CONT** | IS | 5,358 | **-0.2188** | [-0.266, -0.171] | 0.254 | 0.76 |
| **1h** | **FEP-CONT** | **OOS** | **2,451** | **-0.2249** | **[-0.299, -0.150]** | 0.264 | 0.76 |
| 1h | CONFIRMED | IS | 1,340 | -0.0662 | [-0.170, +0.037] | 0.290 | 0.92 |
| 1h | CONFIRMED | OOS | 598 | -0.2468 | [-0.374, -0.119] | 0.254 | 0.74 |
| 1h | BASE-RATE | IS | 17,730 | -0.2114 | [-0.236, -0.188] | 0.252 | 0.77 |
| 1h | BASE-RATE | OOS | 8,410 | -0.2475 | [-0.280, -0.214] | 0.255 | 0.74 |
| 1h | WHIPSAW | IS | 1,270 | -0.2762 | [-0.366, -0.186] | 0.246 | 0.71 |
| 1h | WHIPSAW | OOS | 574 | -0.2417 | [-0.365, -0.122] | 0.267 | 0.75 |
| 4h | **FEP-CONT** | IS | 1,237 | **-0.0726** | [-0.168, +0.027] | 0.258 | 0.91 |
| 4h | **FEP-CONT** | OOS | 628 | **+0.0086** | [-0.125, +0.146] | 0.285 | 1.01 |
| 4h | CONFIRMED | IS | 316 | -0.0182 | [-0.207, +0.173] | 0.272 | 0.98 |
| 4h | CONFIRMED | OOS | 162 | +0.3097 | [+0.023, +0.608] | 0.358 | 1.43 |
| 4h | BASE-RATE | IS | 4,418 | -0.0383 | [-0.080, +0.004] | 0.266 | 0.95 |
| 4h | BASE-RATE | OOS | 2,104 | -0.0846 | [-0.143, -0.025] | 0.261 | 0.90 |
| 4h | WHIPSAW | IS | 283 | -0.1838 | [-0.362, +0.001] | 0.233 | 0.79 |
| 4h | WHIPSAW | OOS | 168 | -0.1718 | [-0.424, +0.077] | 0.238 | 0.80 |
| 1d | **FEP-CONT** | IS | 187 | **+0.3504** | [+0.079, +0.641] | 0.348 | 1.52 |
| 1d | **FEP-CONT** | OOS | 103 | **+0.3119** | [-0.045, +0.684] | 0.340 | 1.45 |
| 1d | CONFIRMED | IS | 43 | +0.3524 | [-0.203, +0.955] | 0.349 | 1.52 |
| 1d | CONFIRMED | OOS | 20 | +0.3499 | [-0.451, +1.266] | 0.350 | 1.51 |
| 1d | BASE-RATE | IS | 710 | +0.0664 | [-0.038, +0.172] | 0.276 | 1.09 |
| 1d | BASE-RATE | OOS | 350 | -0.0188 | [-0.155, +0.118] | 0.257 | 0.97 |
| 1d | WHIPSAW | IS | 59 | -0.4304 | [-0.817, -0.010] | 0.152 | 0.51 |
| 1d | WHIPSAW | OOS | 18 | -0.6048 | [-1.054, +0.131] | 0.111 | 0.35 |

### 3.2 The edge over the control group — the number that decides

| TF | block | FEP-CONT − BASE-RATE | 95% CI (cluster) | p(diff<=0) |
|---|---|---|---|---|
| 30m | IS | +0.0035 | [-0.025, +0.032] | 0.406 |
| 30m | OOS | +0.0165 | [-0.031, +0.064] | 0.250 |
| **1h** | IS | -0.0074 | [-0.050, +0.036] | 0.637 |
| **1h** | **OOS** | **+0.0227** | **[-0.045, +0.092]** | **0.246** |
| 4h | IS | -0.0342 | [-0.127, +0.060] | 0.768 |
| 4h | OOS | +0.0933 | [-0.036, +0.224] | 0.080 |
| 1d | IS | +0.2840 | [+0.017, +0.559] | 0.018 |
| 1d | OOS | +0.3307 | [-0.006, +0.692] | 0.027 |

**Holm-adjusted p across the 4 TF cells (FEP-CONT vs control, OOS): 30m
0.566 · 1h 0.566 · 4h 0.377 · 1d 0.227.** Nothing survives correction —
including 1d.

### 3.3 The single biggest finding: cost, not signal

The unconditional control arm, converted back to gross with the fee drag
that was pre-stated in §4 of the pre-registration **before the run**:

| TF | control net R (OOS) | pre-stated fee drag | implied gross R |
|---|---|---|---|
| 30m | -0.3744 | 0.412 | **+0.038** |
| 1h | -0.2475 | 0.283 | **+0.036** |
| 4h | -0.0846 | 0.136 | **+0.051** |
| 1d | -0.0188 | 0.055 | **+0.036** |

An unconditional entry under this trade model is worth about **+0.04 R gross
on every timeframe** — and the entire net loss is the broker. FEP-CONT on 1h
sits **0.02 R** away from that. The rule is not being killed by costs after
proving an edge; it never had one on the timeframes where it fires most.

### 3.4 Portfolio basis (max 1 concurrent position per symbol)

| TF | arm | block | trades | total R | R / year | max DD (R) |
|---|---|---|---|---|---|---|
| 30m | FEP-CONT | OOS | 3,272 | -1,141.68 | **-476.02** | 1,163.84 |
| **1h** | **FEP-CONT** | **OOS** | **1,682** | **-401.66** | **-167.47** | 423.18 |
| 4h | FEP-CONT | OOS | 405 | -25.04 | -10.44 | 61.95 |
| 1d | FEP-CONT | OOS | 72 | +16.64 | +6.94 | 11.50 |
| — | **PB-1D (listón)** | **OOS** | **8** | **+10.60** | **+4.42** | — |

Traded as a portfolio on the primary timeframe, the rule loses **167 R per
year**. For scale: at the owner's 1.5%-of-equity risk per trade that is the
account, many times over.

### 3.5 The verdict is not an artifact of the primary cell

Counterfactual: the same five legs applied to every timeframe (only 1h is
the real gate — the rest are shown so that "but 1d would have passed" can
never be claimed).

| TF | L1 quality | L2 economics | L3 control | L4 sample | L5 stability | verdict |
|---|---|---|---|---|---|---|
| 30m | FAIL (-0.3579, CI[-0.414,-0.302]) | FAIL (-476.0 R/yr) | FAIL (+0.0165, CI[-0.031,+0.064]) | PASS (n=4,910) | FAIL (IS -0.3172) | **NO PASS** |
| **1h** | FAIL (-0.2249, CI[-0.299,-0.150]) | FAIL (-167.5 R/yr) | FAIL (+0.0227, CI[-0.045,+0.092]) | PASS (n=2,451) | FAIL (IS -0.2188) | **NO PASS** |
| 4h | FAIL (+0.0086, CI[-0.125,+0.146]) | FAIL (-10.4 R/yr) | FAIL (+0.0933, CI[-0.036,+0.224]) | PASS (n=628) | FAIL (IS -0.0726, 2/4 signs) | **NO PASS** |
| 1d | FAIL (+0.3119, **CI[-0.045,+0.684]**) | PASS (+6.94 R/yr) | FAIL (+0.3307, **CI[-0.006,+0.692]**) | PASS (n=103) | PASS (IS +0.3504, 3/4 signs) | **NO PASS** |

1d is the best cell and it still fails: its confidence intervals include
zero on both the absolute leg and the control leg, and its Holm-adjusted p
is 0.227. It clears the economics and stability legs — which is exactly the
shape of a promising-but-unproven idea, and exactly what the pre-registration
forbids acting on (§10.3).

### 3.6 Per symbol and per side (FEP-CONT, OOS)

| TF | BTC | ETH | SOL | BNB | long | short |
|---|---|---|---|---|---|---|
| 30m | n=1246 -0.490 | n=1230 -0.354 | n=1219 -0.218 | n=1215 -0.366 | n=2568 -0.345 | n=2342 -0.372 |
| 1h | n=602 -0.350 | n=621 -0.259 | n=613 -0.106 | n=615 -0.186 | n=1268 -0.155 | n=1183 -0.300 |
| 4h | n=159 +0.099 | n=153 -0.079 | n=162 +0.088 | n=154 -0.082 | n=347 +0.025 | n=281 -0.011 |
| 1d | n=27 -0.172 | n=22 +0.414 | n=23 +0.358 | n=31 +0.627 | n=50 +0.150 | n=53 +0.464 |

On the primary cell the loss is uniform: all 4 symbols negative, both sides
negative. There is no subgroup to rescue.

### 3.7 Sensitivities (FEP-CONT, OOS) — none change the verdict

| variant | 30m | 1h | 4h | 1d |
|---|---|---|---|---|
| primary (close entry, medium) | -0.3579 | **-0.2249** | +0.0086 | +0.3119 |
| S1 next-bar-open entry | -0.3579 | -0.2232 | +0.0086 | +0.3119 |
| S2 60-bar time stop | -0.3655 | -0.2281 | -0.0131 | +0.3496 |
| S3 profile low (1.0x / 2R) | -0.5677 | -0.3791 | -0.0956 | +0.2396 |
| S3 profile high (2.0x / 4R) | -0.2285 | -0.1224 | +0.0092 | +0.1983 |

Edge over control stays inside **+0.005 … +0.033 R** on 1h under every
variant. ⚠️ **S1 is nearly a no-op in 24/7 crypto** — it changes the entry on
~56% of bars but by ~0.003% of price, invisible next to a 1% stop. It is
reported because it was pre-registered, not because it is informative; the
real execution risk on this stack is the watcher's polling lag, which this
study does not model.

### 3.8 The negative control behaves (a validity check)

WHIPSAW — a resolved failure — should not pay, and does not: on 1d it is
**-0.6048 R** against a control of -0.0188 R (edge -0.586). So the state
machine *does* separate outcomes on 1d. On 1h, WHIPSAW (-0.2417) and
FEP-CONT (-0.2249) and the coin (-0.2475) are the same number. That is the
cleanest statement of the result: **on the timeframe where the monitor
actually fires, its three terminal states are informationally
indistinguishable.**

---

## 4. Gate verdict (the frozen §8 legs, primary cell)

| Leg | Requirement | Measured | Pass |
|---|---|---|---|
| **L1 quality** | OOS expectancy >= +0.15 R and CI lower bound > 0 | **-0.2249 R**, CI [-0.299, -0.150] | **FAIL** |
| **L2 economics** | >= +1.644 R/yr (portfolio) | **-167.47 R/yr** | **FAIL** |
| **L3 control** | >= +0.15 R over BASE-RATE, CI lower bound > 0 | **+0.0227 R**, CI [-0.045, +0.092] | **FAIL** |
| **L4 sample** | n >= 30 OOS | **2,451** | PASS |
| **L5 stability** | IS > 0, OOS >= 0.5 x IS, sign in >= 3/4 symbols | IS **-0.2188**, OOS -0.2249, 4/4 symbols (all negative) | **FAIL** |

**VERDICT: NO PASS.** Consequence, executed as pre-registered and as the
2026-08-16 acta dictated: **the FEC/FEP family is archived. No v0.4.0.**
False-entry alerts remain prohibited until evidence arrives from a different
source. The freed cycles go to widening PB-1D's universe — the only edge mmk
has actually proven (+0.6262 R pooled over 8 years, +1.644 R/yr).

### What is NOT concluded

* **Not** that the FEP state is meaningless. On 1d it separates from the coin
  by +0.33 R and its negative control separates by -0.59 R. What is concluded
  is that **the separation is not demonstrated to a pre-registered standard,
  is absent where the monitor fires, and does not survive multiple-comparison
  correction anywhere.**
* **Not** that a fade (contrary) version deserves a look. That was FEC; it was
  refuted on 2026-08-16, and §1 of the pre-registration forbids rescuing a
  refutation by flipping its sign.
* **Not** a licence to re-cut this sample. §10 stands: no filter, regime,
  session or symbol subset may be added now. Anything found in this data from
  here on is a hypothesis for a *new* pre-registration, never evidence.

---

## 5. TURN-IGNITION — recommended destiny: **archive as a candidate**

The re-council tied R-TURN-IGNITION's fate to this verdict. Recommendation:
**archive it as an alertable candidate; it does not get a shadow window and
does not get a v0.3.x.**

Grounds, in order of strength:

1. **Its own forward measurement already answered**: 22.4% favourable
   (19/85) with a **negative mean excursion in both directions**. The
   hit-rate came from the retired 0.5%/10-candle yardstick and is therefore
   suspect — but a negative *mean excursion* is threshold-independent. A
   different yardstick cannot rescue a signal whose average move is negative
   on both sides.
2. **The closest thing this study measured points the same way.** The
   `CONFIRMED` arm is ignition anchored on an AO cross (the E1 turn fires
   inside the 5-candle window). On 1h OOS it is **-0.2468 R**, edge over the
   coin **+0.0007 R**. It is not the same rule as the standalone E1 surface
   (D15), so this is corroboration, not a test — but it is corroboration in
   the direction of "no".
3. **It has never been measured in R at all**, which is now the project's
   entry price for any rule (§I.9d).

Two caveats stated plainly, because the council decides, not this document:

* The one cell in the whole study whose edge CI excludes zero is
  **CONFIRMED on 4h OOS: +0.3097 R, edge +0.3944 R, CI [+0.120, +0.691],
  p=0.0033** — with **no in-sample support** (IS +0.0202) and n=162. Under
  §10 this is **EXPLORATORY, not evidence**, and it is an unregistered
  secondary cell of a non-hypothesis arm. It is recorded because hiding it
  would be selective reporting. It must not become the seed of a fourth
  redesign without its own pre-registration.
* **Cost of keeping the shadow block running is ~0** (it is computed in the
  same pass as M1; turning it off saves no fetches). So "archive" here means
  *stop treating it as pending evidence and stop it blocking decisions*, not
  necessarily deleting the persistence. The council should decide explicitly;
  the default recommendation is to stop persisting what nobody will resolve
  (the same complaint the acta raised about C1 and M2 writing 1,039 outcomes
  that were never sealed).

**Reviving it later is now cheap and honest**: the harness in this repo can
measure a standalone E1-ignition arm in R with a control group in about
30 lines and one afternoon. That, plus a pre-registration, is the price.

---

## 6. What goes to the mmk-council

Nothing here opens or closes anything by itself. The council owns:

1. **Ratify the archive** of FEC/FEP (this verdict is the pre-registered
   consequence, but the acta requires a council to execute a phase change).
2. **Decide TURN-IGNITION's persistence**: stop writing it, or keep it at
   zero cost with an explicit expiry. Related, still open from the acta:
   `_track_shadow_outcomes` seals only M1-FE and TURN-IGNITION — C1 (861) and
   M2 (178) have been writing outcomes that are all `null`.
3. **Approve the PB-1D universe expansion** as the destination of the freed
   cycles (the acta's own instruction). The listón is +0.6262 R pooled over
   8 years but only **2.62 trades/year** — the bottleneck is sample, and the
   only honest way to raise it is more symbols on the same 8-year, fees, IS/OOS
   yardstick. The harness for that already exists
   (`scripts/run_f0_backtest.py`).
4. **Not** decide anything about the 4h CONFIRMED cell today. If anyone wants
   it, it starts as a new pre-registration.

**Snapshot deadline unchanged**: the shadow evidence in Mongo starts being
purged by the 180-day TTL from ~2026-01-08; if the FEC/FEP population is ever
to be reanalysed, it must be snapshotted in **December 2026**.

---

## 7. Limitations

1. **The shadow population was not re-used.** The 162 FEC/FEP forward
   adjudications live in production Mongo, sealed with the retired yardstick.
   This is an independent historical replay, not a confirmation of that
   sample.
2. **No live-execution effects**: no partial fills, no funding, no order
   book, no downtime; spot fees only; one instrument per position. The
   watcher's polling lag is not modelled.
3. **Survivorship**: the 4 majors were alive when they were picked in 2026.
   The listón carries the identical bias — which is why the *comparison* is
   fair even though the absolute levels are not.
4. **Overlap**: arm-A signals overlap heavily on low timeframes. The cluster
   bootstrap mitigates it; the portfolio basis is the overlap-free reading.
5. **Base-rate pairing**: the control fires long AND short on the same bar,
   so its legs are anti-correlated and its effective sample is below its n.
6. **binance history vs the live bitget feed**: production defaults to bitget
   (D1). This study uses binance for continuity with the listón. Any live
   deployment would have to re-verify on bitget candles.
7. **A single trade model.** Everything here is 1.5 x ATR stop / 3R target
   (plus the two profile sensitivities). A rule that only works with a
   different exit mechanism — for instance the acta's own observation that
   76.5% of FEC cases *touched* the target intravela and gave it back — is
   not tested by this study and is not refuted by it. That is a **different**
   hypothesis about **exits**, and it needs its own pre-registration.
