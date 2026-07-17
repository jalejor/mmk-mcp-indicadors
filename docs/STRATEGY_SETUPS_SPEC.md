# Strategy Setups Specification — Multi-TF Engine (Phase 0)

| | |
|---|---|
| **rule_version** | `0.1.0-draft` |
| **Status** | Draft for backend implementation — pending owner confirmation of [§D Open Questions](#d-open-questions-for-the-owner) |
| **Audience** | `backend` (implements `SetupService` + multi-TF backtest), reviewer: trading analyst |
| **Date** | 2026-07-06 (includes the owner's same-night refinements: timeframe bands §0.3 and false-entry vetoes §B.3); owner addenda 2026-07-07 (§G, E5 zones) and 2026-07-11 (M1 monitor §B.3.1, E1/E3-E4/E5 addenda, investor profiles §H, Q13-Q17) |
| **Council decision** | F0→F3 roadmap: setups are **declarative, versioned rules with numeric golden cases**. Paper-first: nothing trades real money without a passing multi-TF backtest AND audited paper trading. |

This document specifies, in implementable numeric terms, the owner's 5 strategy
elements and the 2 composite setups. Names are aligned to the **existing series
produced by `IndicatorsService`** (`src/controllers/metrics/indicators_service.py`):
`adx14`, `plus_di`, `minus_di`, `ao`, `konkorde_azul`, `konkorde_verde`,
`konkorde_marron` (re-centred, see `docs/context/decisions.md#D6`), `bbwp`,
`bbw`, `atr14`, `rsi14`, `sma50/200`, `ema50/200`.

Every parameter marked **[calibrable]** is a provisional number chosen by the
analyst; it must live in the versioned rule document (not env vars) and may only
change with a `rule_version` bump.

---

## 0. Engine conventions (hard requirements)

### 0.1 Closed candles only

A candle is **closed** iff `candle_open_time + timeframe_duration <= now_utc`.

* ccxt's `fetch_ohlcv` returns the **forming** candle as the last row, and
  `MarketDataService.get_ohlcv` does **not** drop it
  (`market_data_service.py:133-143`). Today every live evaluation reads that
  forming candle (repaint risk).
* **Requirement**: `SetupService` MUST drop the last row whenever it is not
  closed, before computing indicators. All series notation below —
  `x[-1]`, `x[-2]`, … — indexes **closed candles only** (`x[-1]` = most recent
  closed candle).
* The backtest replay (`BacktestService`) already acts on bar closes, so it is
  closed-candle by construction; the fix is required for the live path.

### 0.2 Multi-TF alignment (no cross-TF lookahead)

When a setup combines a context TF and a trigger TF, for a trigger candle
closing at time `T` the engine uses the **last context candle whose close time
is `<= T`**. Example: trigger 4h candle closing 2026-07-06 08:00 UTC with
context 1d → use the 1d candle closed 2026-07-06 00:00 UTC (i.e. the candle
covering 2026-07-05), never the in-progress daily candle. This rule applies
identically in live and backtest — it is the multi-TF equivalent of the
existing no-peek-ahead guarantee (`test_backtest_service.py::test_backtest_no_peek_ahead`).

### 0.3 Timeframe bands (owner refinement, 2026-07-06)

Rules are defined **per timeframe band**. This is a first-class dimension of
every rule document:

| Band | Timeframes | Allowed elements |
|------|-----------|------------------|
| `low_tf` | `1m, 5m, 15m, 30m, 1h, 2h` (everything **below 4h**) | **Only** E1 (ADX turn), E2 (AO divergence/convergence), E4-on-BBWP, E5 (BBWP regime). **Konkorde (E3) and Konkorde-curve variants of E4 are forbidden.** |
| `high_tf` | `4h, 6h, 8h, 12h, 1d, 3d, 1w` (4h and above) | Full strategy: E1–E5, including Konkorde. |

Enforcement (both are mandatory):

1. **Load-time validation**: loading a rule document whose `timeframe_band` is
   `low_tf` but that references `konkorde_*` (or `vol_turn` with
   `source: konkorde_*`) MUST raise a validation error. Same if any declared
   `timeframe` does not belong to the declared band.
2. **Runtime guard**: in `low_tf` evaluations, Konkorde conditions never vote,
   never appear in `support_*` lists, and contribute 0 to any score — even if
   an indicator payload happens to contain `konkorde_marron`.

Boundary interpretation chosen (provisional — see Open Question **Q6**): "below
4h" = low, "4h and up" = high; `6h/8h/12h/3d` are treated as high band.

### 0.4 Rules as versioned data (`rule_version`)

* Setups and element parameters are **data documents** (JSON/YAML checked into
  the repo, e.g. `rules/`, or a Mongo collection later) — never loose env vars.
* `rule_version` is semver. **Any** change to a threshold, window, condition
  set or band mapping bumps it (patch: doc-only; minor: parameter change;
  major: condition/structure change).
* Every emitted signal, every backtest run and every paper/live order records
  the `rule_version` that produced it. Historical results are immutable —
  re-running with a new version is a new result, never an overwrite.
* Each `rule_version` ships with its golden tests (pattern:
  `tests/test_konkorde_golden.py`). A version with failing goldens cannot be
  activated.

---

## A. The five strategy elements

Each element defines: operational definition → detection algorithm → parameters
→ applicable TFs → deterministic golden cases (arrays of **closed-candle**
values → expected boolean), ready to convert into pytest.

---

### E1 — `adx_turn`: sharp ADX slope change ("90-degree turn")

**Owner's words**: "ADX con giro de 90 grados" — a sudden bend in the ADX line
(trend strength accelerating or collapsing), not merely its level.

**Operationalisation chosen**: a visual "90°" depends on chart aspect ratio, so
it cannot be an angle. We translate it to a **slope delta in ADX points per
bar**: the recent slope must be steep AND much steeper than the slope before
it. ADX is bounded 0–100, so points/bar is scale-free and comparable across
symbols and TFs — no price normalisation needed. (Alternatives considered:
normalised angle — rejected, aspect-ratio dependent; slope ratio — rejected,
unstable when prior slope ≈ 0, which is exactly the flat-then-turn case we
want to catch.)

**Inputs**: `adx14`, `plus_di`, `minus_di` (existing columns).

**Algorithm** (all on closed candles):

```
slope_recent = (adx14[-1] - adx14[-1 - turn_window]) / turn_window
slope_prior  = (adx14[-1 - turn_window] - adx14[-1 - turn_window - base_window]) / base_window

adx_turn_up   = slope_recent >= min_slope
                AND (slope_recent - slope_prior) >= min_delta_slope
                AND adx14[-1] >= adx_floor

adx_turn_down = slope_recent <= -min_slope
                AND (slope_prior - slope_recent) >= min_delta_slope

Directional variants (ADX is direction-agnostic, pair with DI on the same candle):
adx_turn_up_bullish = adx_turn_up AND plus_di[-1] > minus_di[-1]
adx_turn_up_bearish = adx_turn_up AND minus_di[-1] > plus_di[-1]
```

**Parameters**:

| Param | Default | Notes |
|---|---|---|
| `turn_window` | 3 | closed bars for the recent slope **[calibrable]** |
| `base_window` | 5 | closed bars for the prior slope **[calibrable]** |
| `min_slope` | 1.0 | ADX pts/bar; recent leg must be steep **[calibrable]** |
| `min_delta_slope` | 1.5 | ADX pts/bar of bend; the "90°" quantifier **[calibrable]** |
| `adx_floor` | 10.0 | ignore noise at dead-flat ADX **[calibrable]** |

Note: deliberately **no** `adx >= 25` requirement — the point of the turn is to
catch strength igniting *before* the level condition (`adx_trend_bullish`,
`rules_service.py:152-156`) fires. The level condition remains a separate,
complementary context condition.

**TFs**: both bands (E1 is allowed in `low_tf`).

**Golden cases** (input: `adx14` array = closed candles, oldest→newest; defaults above):

| # | `adx14` | `plus_di[-1]`/`minus_di[-1]` | Expected | Why |
|---|---|---|---|---|
| E1-G1 | `[18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5]` | 28 / 15 | `adx_turn_up_bullish = true` | slope_recent=(24.5−18)/3=**2.167**≥1.0; slope_prior=(18−18)/5=**0**; delta=**2.167**≥1.5; 24.5≥10; +DI dominant |
| E1-G2 | `[16, 17.2, 18.4, 19.6, 20.8, 22, 23.2, 24.4, 25.6]` | 28 / 15 | `adx_turn_up = false` | constant slope 1.2: slope_recent=1.2, slope_prior=1.2, delta=**0**<1.5 — a steady rise is NOT a turn |
| E1-G3 | `[15, 15, 15, 15, 15, 15, 15.3, 15.6, 16.2]` | 20 / 18 | `adx_turn_up = false` | slope_recent=(16.2−15)/3=**0.4**<1.0 — bend too weak |
| E1-G4 | `[32, 31.5, 31, 30.5, 30, 29.5, 28, 25, 22]` | 15 / 28 | `adx_turn_down = true` | slope_recent=(22−29.5)/3=**−2.5**≤−1.0; slope_prior=(29.5−32)/5=**−0.5**; delta=(−0.5)−(−2.5)=**2.0**≥1.5 |

#### E1 addendum (2026-07-11) — turn taxonomy: minor V / inverted V vs major turns

**Owner's words**: ADX reads **impulses and retracements**. 90-degree turns
that are **MINOR with a V shape** = start of an impulse; **inverted V** (Λ) =
termination of the impulse. **MAJOR turns** = trend continuation, OR a false
breakout when the ADX sits around **~20 points**.

Interpretation (analyst — confirm via Q13):

* **V shape** = ADX pivot low + sharp rise → maps to `adx_turn_up`; the
  pivot is the `origin_level` already graded A/B by the 2026-07-06
  refinement (§E).
* **Inverted V** = ADX peak + sharp fall → maps to `adx_turn_down` = impulse
  termination. Already used by the setups' invalidations; this addendum
  names it doctrine ("terminación"), not just a cancel condition.
* **MINOR vs MAJOR** is provisionally read as **turn amplitude** (ADX points
  travelled around the pivot): minor = a small, sharp bend after a shallow
  dip (strength briefly resets, then a new impulse leg is born); major = a
  deep, long bend. Alternative readings — duration in bars, or origin
  level — are plausible; the classifier dimension is Q13 and no detector
  changes until it is quantified.
* **The ~20-point ambiguity**: a MAJOR turn originating around 20 does not
  disambiguate continuation from false breakout by itself — require
  confluence before trusting it (E5 regime ON, Konkorde state agreeing, M1
  §B.3.1 not in `FALSE_ENTRY_PROBABLE` on the same TF).
* **Tension flagged**: the A-grade origin band is `[12, 20]` (sweet spot 16,
  §E 2026-07-06), while this dictation marks ~20 as the ambiguous zone. If
  Q13 lands on amplitude+origin classes, the A-grade upper edge may need
  tightening (e.g. `[12, 18]`) — a `rule_version` bump with its own backtest
  A/B, not a change now (the A/B-grade stratification is currently
  inconclusive anyway, `docs/F0_GATE_ANALYSIS.md` §4).

No change to the `adx_turn` detector in this addendum — it already fires on
both shapes; what is missing is the **minor/major classification dimension**,
parked until Q13 quantifies it.

---

### E2 — `ao_divergence` / `ao_convergence`: AO vs price

**Owner's words**: divergence = price makes a new extreme, AO does not confirm
it; convergence = AO confirms the move (used as confirmation, not trigger).

**Inputs**: `ao` (existing column), `high`, `low` from OHLCV.

**Pivot definition** (fractal, confirmation-delayed so it never repaints):
bar `i` is an **AO pivot low** iff `ao[i]` is the strict minimum of
`ao[i-pivot_strength .. i+pivot_strength]`; pivot high analogous with strict
maximum. A pivot is only **confirmed** `pivot_strength` closed bars after `i` —
detectors may only use confirmed pivots.

**Algorithm — regular bullish divergence** (bearish is the mirror):

```
1. Within the last `divergence_lookback` closed bars, find the two most recent
   CONFIRMED AO pivot lows p1 < p2 with
   min_pivot_distance <= (p2 - p1) <= max_pivot_distance.
2. Anchor prices at the same bar indexes (AO pivots are the anchors —
   standard oscillator-divergence practice).
3. ao_divergence_bullish = ao[p2] > ao[p1]          (AO higher low)
                           AND low[p2] < low[p1]     (price lower low)
                           AND ao[p1] < 0 AND ao[p2] < 0   (regular bullish: both below zero)
4. The event FIRES on the closed bar that confirms p2 (bar p2 + pivot_strength)
   and stays active for `divergence_ttl` closed bars, unless invalidated
   earlier by low[-1] < low[p2] (price breaks the divergence low).
```

Regular **bearish**: AO pivot highs, `ao[p2] < ao[p1]`, `high[p2] > high[p1]`,
both AO pivots `> 0`.

**Convergence** (confirmation only, never a standalone trigger):
`ao_convergence_bullish` = price higher high AND AO higher high at the last two
confirmed pivot highs (momentum confirms trend continuation). Mirror for
bearish. A cheap per-candle variant for trigger conditions:
`ao_rising = ao[-1] > ao[-2]` (and `ao_falling` mirror).

**Zero-cross events on AO** (used by the false-entry vetoes, §B.3 — same event
semantics as E3):

```
ao_zero_cross_up   = ao[-2] <= 0 AND ao[-1] > 0      (fires on candle -1)
ao_zero_cross_down = ao[-2] >= 0 AND ao[-1] < 0
event_age(e)       = index(last closed candle) - index(candle where e fired)   // fired candle -> age 0
```

Golden: `ao = [-0.4, 0.3, 0.9, 1.4, 1.8, 2.1, 2.3]` → `ao_zero_cross_up` fired
at index 1; evaluated at the last closed candle (index 6), `event_age = 5`.

**Parameters**:

| Param | Default | Notes |
|---|---|---|
| `pivot_strength` | 2 | fractal half-width; pivot confirmed 2 bars later **[calibrable]** |
| `divergence_lookback` | 60 | closed bars scanned **[calibrable]** |
| `min_pivot_distance` | 5 | bars between p1 and p2 **[calibrable]** |
| `max_pivot_distance` | 40 | **[calibrable]** |
| `divergence_ttl` | 10 | closed bars the fired event stays valid **[calibrable]** |

**TFs**: both bands.

**Golden cases** (12 closed bars, index 0..11, `pivot_strength=2`):

**E2-G1 — bullish divergence = true**

```
low = [10.0, 9.5, 9.0, 9.5, 10.0, 10.5, 10.2, 9.4, 8.8, 9.2, 9.8, 10.1]
ao  = [-1.0, -1.5, -2.0, -1.6, -1.1, -0.8, -1.0, -1.3, -1.5, -1.2, -0.9, -0.5]
```
AO pivot lows: i=2 (−2.0 strict min of −1.0,−1.5,−2.0,−1.6,−1.1) and i=8 (−1.5
strict min of −1.0,−1.3,−1.5,−1.2,−0.9); both confirmed (i+2 ≤ 11). Distance
8−2=6 ∈ [5,40]. AO: −1.5 > −2.0 (higher low), both < 0. Price: low[8]=8.8 <
low[2]=9.0 (lower low). → **fires at bar 10**, active at bar 11
(`ao_divergence_bullish = true` when evaluating with last closed bar 10 or 11).

**E2-G2 — no divergence (AO confirms the low) = false**

```
low = same as E2-G1
ao  = [-1.0, -1.5, -2.0, -1.6, -1.1, -0.8, -1.2, -1.8, -2.6, -2.0, -1.4, -1.0]
```
Same pivot bars (i=2: −2.0; i=8: −2.6), but ao[8]=−2.6 < ao[2]=−2.0 → AO made a
**lower** low → `ao_divergence_bullish = false`.

**E2-G3 — bearish divergence = true**

```
high = [100.0, 100.5, 101.0, 100.5, 100.0, 99.5, 99.8, 100.6, 101.2, 100.8, 100.2, 99.9]
ao   = [1.0, 1.5, 2.0, 1.6, 1.1, 0.8, 1.0, 1.3, 1.5, 1.2, 0.9, 0.5]
```
AO pivot highs i=2 (2.0) and i=8 (1.5), both > 0; price higher high
(101.2 > 101.0), AO lower high (1.5 < 2.0) → `ao_divergence_bearish = true`,
fires at bar 10.

---

### E3 — `konkorde_zero_cross`: trend continuation on the zero cross

**Owner's words**: Konkorde crossing the zero point = trend continuation; up =
buy, down = sell.

**Current code behaviour (documented, NOT the same thing)**: `RulesService`
votes `konkorde_buy` whenever `konkorde_value > 0` and `konkorde_sell` whenever
`< 0` (`rules_service.py:160-165`) — a **level/state** check on the latest
candle. Since the re-centring fix (`65be83d`, decisions.md#D6) the level is
unbiased, but a positive `marron` votes buy on *every* bar, not only at the
cross. The owner's element is an **event**. The spec therefore defines both:

```
State (context use):
konkorde_positive = konkorde_marron[-1] > 0
konkorde_negative = konkorde_marron[-1] < 0

Event (trigger use), with confirm_bars = N:
konkorde_zero_cross_up   = konkorde_marron[-1-N .. -1] all > 0        (N most recent closed candles positive)
                           AND konkorde_marron[-1-N] <= 0             (the candle before the run was at/below zero)
konkorde_zero_cross_down = mirror with < 0 / >= 0
```

With the default `confirm_bars = 1` this reduces to the plain cross:
`marron[-2] <= 0 AND marron[-1] > 0`.

**Parameters**:

| Param | Default | Notes |
|---|---|---|
| `confirm_bars` | 1 | 1 = plain cross on the closing candle; 2 = require the next close to hold the sign (fires one candle later, fewer whipsaws) **[calibrable]** |
| `strong_hands_filter` | off | optional extra condition `konkorde_verde[-1] > konkorde_azul[-1]` (strong hands dominate). OFF by default to match the owner's plain rule **[calibrable]** — see Q3 |

**TFs**: **`high_tf` band only** (4h and above). Forbidden in `low_tf` (§0.3).

**Golden cases** (input: `konkorde_marron` closed series, `confirm_bars=1`):

| # | `konkorde_marron` | Expected | Why |
|---|---|---|---|
| E3-G1 | `[-5.0, -2.0, -0.5, 1.2]` | `konkorde_zero_cross_up = true` | marron[-2]=−0.5 ≤ 0, marron[-1]=1.2 > 0 |
| E3-G2 | `[-5.0, -2.0, 0.5, 1.2]` | `cross_up = false`, `konkorde_positive = true` | the cross happened one candle earlier (event ≠ state) |
| E3-G3 | `[3.0, 2.0, 1.0, -0.8]` | `konkorde_zero_cross_down = true` | 1.0 ≥ 0 → −0.8 < 0 |
| E3-G4 | `[-2.0, 0.5, 1.2]` with `confirm_bars=2` | `cross_up = true` | last 2 closes > 0 and the candle before the run (−2.0) ≤ 0 — fires one candle later than G1-style |

---

### E4 — `vol_turn`: volatility turn in the high zone, V and W shapes

**Owner's words**: volatility turning over in its upper region; shapes V
(single sharp turn) and W (double turn / double test). The same pattern applies
to the Konkorde curves.

**Sources**: primary `bbwp` (0–100 by construction); secondary
`konkorde_marron` and `konkorde_verde` (unbounded → high zone via rolling
percentile).

**High zone**:

* BBWP: `x >= high_zone_abs` with `high_zone_abs = 70` **[calibrable]** — note
  this is stricter than the E5 regime threshold (50): >50 means "tradeable
  volatility", ≥70 is "upper region where exhaustion turns matter" (see Q4).
* Konkorde curves: `x >= rolling_percentile(x, percentile_lookback=100, q=80)`
  **[calibrable]** — percentile because the curves have no fixed scale.

**V-turn** (single-bar reversal, confirmed by one closed candle):

```
v_turn_high = x[-2] > x[-3]                  (was rising into the peak)
              AND x[-2] > x[-1]              (peak confirmed by the close of the next candle)
              AND x[-2] >= high_zone
              AND (x[-2] - x[-1]) >= min_drop
Fires on candle -1 (the confirming closed candle).
```

**W-turn** (double test of the high zone; on a volatility curve at highs this
is the two-peak "M/W family" shape the owner draws):

```
1. Find pivot highs P1 < P2 with pivot_strength = 1 (x[P] strict max of its
   1-bar neighbours), both CONFIRMED (P+1 closed).
2. w_turn_high = both x[P1], x[P2] >= high_zone
                 AND 3 <= (P2 - P1) <= w_window
                 AND |x[P2] - x[P1]| <= peak_tolerance        (second test fails to expand meaningfully)
                 AND min(peaks) - min(x[P1+1 .. P2-1]) >= min_trough_depth   (a real trough between the tests)
   Fires on candle P2 + 1 (the candle confirming the second peak).
```

**Parameters** (BBWP source; Konkorde sources reuse windows, zone per above):

| Param | Default | Notes |
|---|---|---|
| `high_zone_abs` (BBWP) | 70 | **[calibrable]**, see Q4 |
| `min_drop` | 5.0 | BBWP points from peak to confirming close **[calibrable]** |
| `w_window` | 12 | max bars between the two peaks **[calibrable]** |
| `peak_tolerance` | 5.0 | BBWP points **[calibrable]** |
| `min_trough_depth` | 5.0 | BBWP points **[calibrable]** |
| `percentile_lookback` / `q` (Konkorde) | 100 / 80 | **[calibrable]** |

**Semantics in setups**: a vol turn at highs is **exhaustion evidence** — used
for invalidation / no-new-entries / tighten-stops, never as an entry trigger.

**TFs**: BBWP source — both bands. Konkorde sources — `high_tf` only (§0.3).

**Golden cases** (input: `bbwp` closed series, defaults above):

| # | `bbwp` | Expected | Why |
|---|---|---|---|
| E4-G1 | `[55, 62, 74, 86, 71]` | `v_turn_high = true` | 86>74 rising, 86>71 confirmed, 86≥70, drop 86−71=**15**≥5 |
| E4-G2 | `[55, 62, 74, 86, 88]` | `v_turn_high = false` | still rising (86 < 88 fails `x[-2] > x[-1]`) |
| E4-G3 | `[60, 72, 84, 76, 70, 75, 83, 72]` | `w_turn_high = true` | pivots P1=idx2 (84), P2=idx6 (83), both ≥70; distance 4 ∈ [3,12]; \|83−84\|=1 ≤ 5; trough min(76,70,75)=70, depth min(84,83)−70=**13** ≥ 5; fires idx 7 |
| E4-G4 | `[60, 72, 84, 76, 70, 80, 95, 90]` | `w_turn_high = false` | \|95−84\|=11 > 5 — second peak is fresh expansion, not a double test |

#### E3/E4 addendum (2026-07-11) — Konkorde volume doctrine: enter near zero, exit on high-mean turns

**Owner's words (2026-07-11)**: "Cruce de 0 = empezar compras (arriba) /
ventas (abajo). Volumen en media ALTA con giros V/W = terminación del
impulso. Salida de la media con giros abruptos desde volumen; entrada al
punto 0 o cerca."

1. **Zero cross RATIFIED (E3 unchanged)**: crossing 0 upward = start
   building buys; downward = start building sells. "Empezar compras"
   confirms E3's **event** (campaign-start) semantics over the legacy
   level/state vote.
2. **Impulse termination = volume at HIGH MEAN + V/W turn (E4-on-Konkorde,
   refined)**: the Konkorde volume curves riding HIGH relative to their own
   average and printing a V/W turn = the impulse is terminating. This is the
   E4 Konkorde-source variant already specified (high zone = rolling
   percentile q=80 / lookback 100) — but the owner's "media alta" suggests a
   MEAN-relative zone (e.g. `x >= k · rolling_mean(x, n)`) instead of, or
   besides, the percentile. Formulation = **Q15**; the percentile stays the
   provisional default.
3. **Entries at/near the zero point** (interpretation, marked): the best
   entries occur while the volume curves sit at or near zero — the crowd has
   not piled in yet, the impulse is being born; by the time volume is
   stretched at the high mean, entering is late and exiting is the topic.
   Candidate QUALITY dimension for triggers (like the `adx_turn` A/B grade):
   `konkorde_near_zero` = `|konkorde_verde[-1]| <= near_zero_band` with
   `near_zero_band = rolling_percentile(|verde|, 100, q=30)` **[calibrable]**
   → quality bonus at trigger time; stretched-at-high-mean at trigger →
   quality penalty. PARKED as backtest stratification first — never a hard
   gate in v0.1.x.
4. **"Salida de la media con giros abruptos"** (interpretation, marked): an
   abrupt turn that LEAVES the high-mean region — the confirming close of
   the E4 V-turn on the volume curve — is the exit/termination trigger. This
   reinforces E4-on-Konkorde as invalidation evidence on `high_tf` (already
   wired in PB-1D's invalidations: `vol_turn` on `konkorde_marron`); no new
   detector needed.

Applies on the `high_tf` band only (Konkorde ban below 4h, §0.3, unchanged).

---

### E5 — `bbwp_regime`: volatility above 50

**Owner's words**: "volatilidad mayor a 50 puntos" as the regime filter — only
trade impulse when volatility is actually present.

```
bbwp_regime_on = bbwp[-1] > 50.0        (strict; on the closed candle of the setup's regime TF)
```

| Param | Default | Notes |
|---|---|---|
| `bbwp_regime_min` | 50.0 | **[calibrable]** |

**Coexistence with the current 20/80** (`rules_service.py:21-27`, regime at
`110-123`): they answer different questions and **coexist in F0**:

* The legacy scorer keeps `bbwp_low=20` / `bbwp_high=80` (compression blocks
  signals; exhaustion regime) — untouched in F0.
* The declarative setups **never** use 20/80; inside a setup document the only
  volatility-regime condition is E5 (plus E4 turns for invalidation).
* **Flagged contradiction** (needs owner ruling, Q5): the legacy scorer counts
  `vol_low` (BBWP < 20) as **entry support** (`rules_service.py:143-144`) —
  a compression-breakout-anticipation idea — while the owner's doctrine for
  the impulse setup requires BBWP > 50. These cannot both gate the same trade.
  F0 resolution: setups are self-contained and E5 governs; the legacy scorer
  remains for the existing `/v1` endpoints only.

**TFs**: both bands.

**Golden cases**: `bbwp[-1] = 50.0` → `false` (strict). `bbwp[-1] = 50.1` →
`true`. `bbwp[-1] = 49.9` → `false`.

#### E5 addendum (2026-07-11) — abrupt color change, the 50% cross, low-zone ignition turns

Extends the 2026-07-07 color-zone + zone-jump addenda (end of §G). Owner
doctrine, 2026-07-11: an **ABRUPT (brusco) color change = high volatility**
("tenemos que tener claros los colores"); **crossing 50% = high volatility /
trend termination with V or M turns**; **volatility-ignition turns in short
ranges with V/W shapes**.

1. **Abrupt color change**: the zone taxonomy (blue/green/yellow/red) is
   first-class — detectors must reason in zones, not only in raw BBWP. The
   existing `zone_jump` event (skip ≥ 2 zones in one closed candle) is the
   provisional quantifier of "abrupt"; whether a fast 1-zone change also
   qualifies is **Q14**.
2. **The 50% cross** (the green↔yellow boundary, already emitted as a
   `bbwp_zone_change`): crossing 50 marks high volatility, and it is
   **trend-termination evidence when accompanied by V or M turns** (M = the
   two-peak M/W family of E4). Interpretation (marked): the termination
   reading applies to the cross in the CONTEXT of a high-zone turn —
   typically the DOWNWARD 50-cross after `v_turn_high`/`w_turn_high` fired
   (volatility rolled over from the top and is leaving the tradeable regime:
   the red→yellow→green collapse path), while the plain UPWARD cross remains
   E5 regime ignition. Composite event for setups (invalidation-grade, like
   E4): `bbwp_50_cross_down` within `turn_confluence_window = 5` closed
   candles **[calibrable]** of a high-zone V/W turn.
3. **Low-zone ignition turns (`v_turn_low` / `w_turn_low`) — NEW detector
   variants**: "giros de inicio de volatilidad en rangos cortos con formas
   V/W" — V/W turns in the LOW zone ("rangos cortos" read as short/tight
   price ranges = compressed BBWP [interpretation]) marking the START of
   volatility. Strict mirrors of E4's high-zone geometry, flipped:

   ```
   v_turn_low = x[-2] < x[-3]                  (was falling into the trough)
                AND x[-2] < x[-1]              (trough confirmed by the next close)
                AND x[-2] <= low_zone_abs
                AND (x[-1] - x[-2]) >= min_rise
   w_turn_low = double test of the low zone (mirror of w_turn_high: pivot
                LOWS, both <= low_zone_abs, a real bump between the tests)
   ```

   | Param | Default | Notes |
   |---|---|---|
   | `low_zone_abs` (BBWP) | 30 | blue + lower green **[calibrable]** |
   | `min_rise` | 5.0 | BBWP points, mirror of `min_drop` **[calibrable]** |

   Semantics: **expansion-ignition evidence** — a context/quality component
   for impulse setups (natural confluence with the blue→green `zone_change`
   and §G's "awakening after compression" trigger candidate), NEVER an entry
   trigger by itself. Source: `bbwp` only; both bands.

   Golden cases: `bbwp = [45, 30, 18, 12, 24]` → `v_turn_low = true`
   (12 < 18 falling, 12 < 24 confirmed, 12 ≤ 30, rise 24−12 = **12** ≥ 5).
   `bbwp = [45, 30, 18, 12, 14]` → `false` (rise 2 < 5). `w_turn_low`
   goldens land with the implementation (pattern: E4-G3/G4 mirrored).

---

### E6 — `trend_speed`: wave-speed impulse strength — **CANDIDATE (parked, post-F0 gate)**

> **Status: NOT part of F0.** Explicit recommendation: F0 ships the 5 owner
> elements + timeframe bands + false-entry vetoes and nothing else. E6 enters
> the rule set only if the F0 backtest shows the impulse confirmation is
> lacking — concretely, if the §C counterfactual replay shows V2 (`adx_turn`)
> rejecting too many profitable entries or passing too many false ones. Adding
> it later is a `rule_version` bump with its own golden tests and its own
> backtest A/B (with-vs-without E6).

**Source concept**: "Trend Speed Analyzer" by Zeiierman (TradingView, Pine v6).
Concept only — **no code was copied**.

> **License note**: the original indicator is published under
> **CC BY-NC-SA 4.0** (non-commercial, share-alike). Using the *concept* in a
> personal, non-commercial strategy is fine for the owner's current use. If
> mmk ever becomes commercial (multi-account phase of the roadmap), this
> element must be reviewed: reimplement from an independent formulation or
> obtain permission — flag it in that phase's gate checklist.

**Operational definition (mmk terms, pandas)**:

```
# Per closed candle; RMA = Wilder's smoothing (pandas-ta-classic: ta.rma)
body_speed[i] = RMA(close, 10)[i] - RMA(open, 10)[i]

# Cumulative speed within the current trend segment:
speed_acc[i] = speed_acc[i-1] + body_speed[i]

# Segment reset ("trend turn"): when close crosses the adaptive trend EMA.
# mmk approximation of the dynamic-length EMA [calibrable]: KAMA(10), or plain
# EMA(20) as the simplest first cut. On reset: close the current "wave" and
# restart speed_acc at 0.
```

**Wave statistics** (over `wave_lookback` = last 50 completed waves **[calibrable]**):

```
wave_height       = extreme |speed_acc| reached during the segment (signed by side)
avg_bull, max_bull = mean / max of bull wave heights in the lookback   (mirror for bear)
ratio_avg         = |current_wave| / avg_same_side      # > 1 -> stronger than the historical average
ratio_max         = |current_wave| / max_same_side      # > 1 -> strongest move in the lookback
dominance         = avg_bull - |avg_bear|               # > 0 -> bull waves structurally larger
```

**Intended role — confirmation of "impulso bien marcado" in the vetoes**: E6
would extend veto V2 (§B.3) as a complement/alternative to the ADX turn:

```
V2' (post-F0 candidate) = adx_turn fired within confirm_window
                          OR (current wave started <= max_event_age candles ago     # aligns with V1 freshness
                              AND ratio_avg >= speed_ratio_min)                      # default 1.0 [calibrable] — see Q12
```

**Golden cases (conceptual — deterministic once the adaptive EMA choice is
fixed; inputs are the wave-level values, not raw OHLCV)**:

| # | Wave history (bull side) | Current wave | Expected | Why |
|---|---|---|---|---|
| E6-G1 | heights `[10, 12, 8, 10]` → `avg_bull = 10`, `max_bull = 12` | `speed_acc` peak `15` | `ratio_avg = 1.5`, `ratio_max = 1.25` → impulse confirmation **true** | current move stronger than both the average and the historical max |
| E6-G2 | same history | `speed_acc` peak `6` | `ratio_avg = 0.6`, `ratio_max = 0.5` → confirmation **false** | weaker-than-average move; if `adx_turn` is also absent, the V2' veto stands |

**TFs**: both bands (no Konkorde dependency).

---

## B. Composite setups (declarative, versioned)

### B.0 Rule document schema

```jsonc
{
  "rule_version": "0.1.0",            // semver, bumped on ANY change (§0.4)
  "setup_id": "PB-1D-LONG",           // stable identifier
  "side": "long",                      // long | short
  "timeframe_band": "high_tf",        // low_tf | high_tf  (§0.3, validated at load)
  "context":  { "timeframe": "1d",  "conditions": [ /* ALL must hold on last closed context candle */ ] },
  "trigger":  { "timeframe": "1d",  "conditions": [ /* see per-setup logic */ ] },
  "invalidation": { "conditions": [ /* ANY cancels pending setup / flags open trade */ ] },
  "vetoes": [ /* false-entry filters, §B.3 — ANY match suppresses the entry signal */ ],
  "risk": { "risk_profile": "medium" } // sizing via sizing_profiles.atr_sizing_for → live/backtest parity preserved
}
```

Each condition is `{ "element": "<detector>", "variant": "...", "params": { ... } }`
referencing §A detectors, or a primitive comparison on existing series
(e.g. `close > sma200`). **Evaluation order at every closed trigger candle**
(§0.2 alignment for context TFs):

1. **Invalidation** — cancels an armed setup / flags an open trade.
2. **Context** — all context conditions must hold.
3. **Trigger logic** — fires on the candle where it first becomes true.
4. **Vetoes (§B.3)** — a vetoed trigger emits **no** signal; it is logged with
   `veto_reasons[]` + `rule_version` and counted by the backtest (§C).

Band gating golden cases (must be pytest-ed):

* **B0-G1**: loading a document with `"timeframe_band": "low_tf"` and any
  `konkorde_*` condition → **validation error**.
* **B0-G2**: runtime, `low_tf` evaluation on 1h with indicator payload
  containing `konkorde_marron = +35.0` (strongly positive) → no `konkorde_*`
  entry in any support list, score contribution 0; the same payload evaluated
  under a `high_tf` 4h rule set → `konkorde_positive = true` votes.

### B.1 SETUP `PB-1D-LONG` — Pullback within trend (weekly/daily context)

The owner's pullback: weekly/daily uptrend, price retraces, enter on evidence
the retracement is ending. `high_tf` band. Long variant specified; short is the
strict mirror (gated by Q8).

```jsonc
{
  "rule_version": "0.1.0",
  "setup_id": "PB-1D-LONG",
  "side": "long",
  "timeframe_band": "high_tf",
  "context": {
    "timeframe": "1d",
    "conditions": [
      { "expr": "close > sma200" },                                   // structural uptrend
      { "expr": "ema50 > sma50" },                                    // existing ma_cross condition
      { "any_of": [
          { "element": "adx_level", "expr": "adx14 >= 25 AND plus_di > minus_di" },  // = adx_trend_bullish today
          { "element": "adx_turn", "variant": "up_bullish" }                          // E1: strength igniting
      ]},
      { "element": "konkorde_state", "variant": "positive" },          // E3 state: marron > 0
      { "element": "pullback_state", "params": { "pullback_window": 10 } }
      // pullback_state := min(low[-pullback_window..-1]) <= ema50 on the context TF
      //                   (price actually retraced to the dynamic mean) [calibrable]
    ],
    "optional": [
      { "timeframe": "1w", "element": "konkorde_state", "variant": "positive" }  // weekly agreement; OFF in v0.1.0 [calibrable]
    ]
  },
  "trigger": {
    "timeframe": "1d",                                                 // see Q7 (4h alternative)
    "logic": "reversal_evidence AND resumption",
    "conditions": {
      "reversal_evidence_any_of": [
        { "element": "konkorde_zero_cross", "variant": "up", "params": { "confirm_bars": 1 } },   // E3 event
        { "element": "ao_divergence", "variant": "bullish", "params": { "active_within": 5 } }     // E2, fired ≤5 closed bars ago
      ],
      "resumption_all_of": [
        { "expr": "close[-1] > high[-2]" }                             // price resumes: close above prior candle's high
      ]
    }
  },
  "invalidation": {
    "conditions": [
      { "expr": "close < sma200", "timeframe": "1d" },
      { "element": "adx_turn", "variant": "down", "timeframe": "1d" },              // E1: trend strength collapsing
      { "element": "vol_turn", "variant": "w_or_v_high", "source": "konkorde_marron", "timeframe": "1d" }  // E4: strong-hands distribution
    ]
  },
  "vetoes": [                                                                       // §B.3
    { "veto": "freshness", "event": "konkorde_zero_cross_up", "max_event_age": 3 },
    { "veto": "adx_confirmation", "variant": "up_bullish", "confirm_window": 3 }
  ],
  "risk": { "risk_profile": "medium" }   // stop = entry − 1.5·atr14, target = 3R (sizing_profiles parity)
}
```

### B.2 SETUP `IMP-4H-LONG` — 4h impulse in high volatility

The owner's impulse: 4h, volatility regime ON (>50), trend strength igniting,
enter with the flow. 4h belongs to `high_tf`, so the full strategy (including
Konkorde) applies.

```jsonc
{
  "rule_version": "0.1.0",
  "setup_id": "IMP-4H-LONG",
  "side": "long",
  "timeframe_band": "high_tf",
  "context": {
    "timeframe": "4h",
    "conditions": [
      { "element": "bbwp_regime", "params": { "bbwp_regime_min": 50.0 } },   // E5 — the owner's >50 filter
      { "element": "adx_turn", "variant": "up_bullish", "fired_within": 3 },  // E1 on 4h — subsumed by veto V2 (§B.3): fired within confirm_window, not necessarily on the trigger candle
      { "expr": "close > sma200", "timeframe": "1d" }                         // 1d must not oppose [calibrable]
    ]
  },
  "trigger": {
    "timeframe": "4h",
    "logic": "all_of",
    "conditions": [
      { "element": "konkorde_zero_cross", "variant": "up", "params": { "confirm_bars": 1 } },  // E3 continuation
      { "expr": "ao > 0" },                                                   // existing ao_positive condition
      { "expr": "ao[-1] > ao[-2]" }                                           // E2 cheap convergence: momentum rising
    ]
  },
  "invalidation": {
    "conditions": [
      { "element": "vol_turn", "variant": "w_or_v_high", "source": "bbwp", "timeframe": "4h" },  // E4: expansion exhausting → no new entries, tighten open ones
      { "element": "konkorde_zero_cross", "variant": "down", "timeframe": "4h" },
      { "element": "adx_turn", "variant": "down", "timeframe": "4h" }
    ]
  },
  "vetoes": [                                                                       // §B.3
    { "veto": "freshness", "event": "konkorde_zero_cross_up", "max_event_age": 3 },
    { "veto": "freshness", "event": "ao_zero_cross_up", "max_event_age": 3 },
    { "veto": "adx_confirmation", "variant": "up_bullish", "confirm_window": 3 }
  ],
  "risk": { "risk_profile": "medium" }
}
```

Short variants (`PB-1D-SHORT`, `IMP-4H-SHORT`) are strict mirrors of every
condition; whether they are enabled in the F0 backtest is Open Question **Q8**.

**Low-band note**: F0 ships no `low_tf` setup — both owner setups live in the
high band. The band machinery (§0.3) must ship in F0 anyway (validation +
runtime guard + B0 goldens), so that any future `low_tf` scalping rule set is
structurally limited to BBWP + AO + ADX from day one.

### B.3 False-entry veto filters (owner refinement, 2026-07-06)

**Owner's example (verbatim)**: "el AO pasó de su punto 0 hace varias líneas
[velas] y el ADX no hizo un cambio de 90 grados para señalar un impulso o un
retroceso bien marcado" → the signal is **INVALID**.

Generalisation: an entry trigger is only tradable when its evidence is
**fresh** (V1) and the move is **confirmed as "well marked"** by an ADX turn
(V2). Vetoes run at step 4 of the §B.0 evaluation order — after the trigger
logic is satisfied — and **any** matching veto suppresses the entry signal.
Vetoes never close open trades and never cancel an armed setup; that is
invalidation's job (step 1). Both mechanisms can match on the same candle;
they are independent. Every vetoed signal MUST be logged with `veto_reasons[]`
and `rule_version`, and counted by the backtest (§C).

**V1 — FRESHNESS (event age)**

```
event_age(e) = index(last closed candle) - index(candle where e fired)   // fired on the trigger candle -> 0
veto_stale(e) = event_age(e) > max_event_age
```

| Param | Default | Notes |
|---|---|---|
| `max_event_age` | 3 | closed candles **[calibrable]** — see Q10 |

Applies to **cross events** used as trigger/evidence: `konkorde_zero_cross_up/down`
(E3) and `ao_zero_cross_up/down` (E2). A cross older than `max_event_age`
closed candles is stale — the impulse it announced is already several candles
old and the entry would chase it. Structural events keep their own persistence
windows unchanged (E2 divergence: `divergence_ttl = 10` — a divergence is a
structure, not a cross, so V1 does not apply to it).

**V2 — REQUIRED ADX CONFIRMATION ("bien marcado")**

```
veto_unconfirmed = no adx_turn event (E1, direction matching the setup side)
                   fired within the last confirm_window closed candles
                   (the trigger candle itself counts, age 0)
```

| Param | Default | Notes |
|---|---|---|
| `confirm_window` | 3 | closed candles **[calibrable]** — see Q10 |

The E1 turn is what marks an impulse or a well-defined retracement ending;
an AO/Konkorde zero-cross without the ADX bend is treated as noise and vetoed.
Two deliberate consequences (both match the owner's example):

* A **steady rise** in ADX (E1-G2: constant slope, no bend) does **not**
  satisfy V2 — sustained strength is not a turn.
* A **high ADX level** (≥ 25, dominant DI) without a recent turn does **not**
  satisfy V2 either. Whether the level may substitute for the turn is Q10.

A parked candidate alternative/complement for this confirmation —
`trend_speed` wave ratios (E6, Zeiierman concept) — is specified in §E6 and is
**post-F0 only** (V2' formulation there).

**Veto table per setup** (shorts: mirror variants):

| Setup | Veto | Rule | Default |
|---|---|---|---|
| `PB-1D-LONG` | V1 | `konkorde_zero_cross_up` used as reversal evidence must have `event_age <= max_event_age` (the `ao_divergence_bullish` path keeps its own `divergence_ttl`, V1 not applied) | 3 |
| `PB-1D-LONG` | V2 | `adx_turn_up_bullish` must have fired within `confirm_window` closed candles of the trigger | 3 |
| `IMP-4H-LONG` | V1 | `konkorde_zero_cross_up` age ≤ `max_event_age` **AND** `ao_zero_cross_up` age ≤ `max_event_age` — AO positive but stale-crossed is exactly the owner's false entry | 3 |
| `IMP-4H-LONG` | V2 | `adx_turn_up_bullish` fired within `confirm_window` — this **subsumes** the context `adx_turn` condition, which now reads "fired within `confirm_window`" instead of "true on the last closed candle" | 3 |

Interaction with existing invalidations: unchanged. Invalidation (e.g.
`vol_turn` W/V at highs, `konkorde_zero_cross_down`, `adx_turn_down`) still
cancels armed setups and flags open positions; vetoes only gate the entry at
trigger time. A candle can simultaneously produce a trigger, a veto and an
invalidation — invalidation wins (evaluated first), then the veto suppresses
whatever trigger survived.

**Band applicability**: V1 + V2 apply in **both** bands. In `low_tf` they act
on `ao_zero_cross_*` and `adx_turn` only (Konkorde does not exist there, §0.3).
Provisional — see Q11.

**Golden cases** (defaults: `max_event_age = 3`, `confirm_window = 3`; E1
defaults from §A):

**FE-G1 — the owner's exact case → VETO (stale AO cross + flat ADX)**

Evaluated at the last closed 4h candle, `IMP-4H-LONG`:

```
ao              = [-0.4, 0.3, 0.9, 1.4, 1.8, 2.1, 2.3]
adx14           = [24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4]   (plus_di > minus_di on every candle)
konkorde_marron = [-1.0, 0.8, 1.5]
```

* `ao_zero_cross_up` fired at index 1 → `event_age = 5` > 3 → **stale** (the
  owner's "pasó de su punto 0 hace varias líneas").
* `adx14` slope is a constant 0.1 pts/bar → `slope_recent − slope_prior = 0`
  on every candle → **no `adx_turn_up` ever fired** ("no hizo un cambio de 90
  grados"). Note ADX **level** is 25.4 ≥ 25 — still vetoed: level ≠ turn.
* `konkorde_zero_cross_up` fired at index 1 of 3 → age 1 ≤ 3 (fresh), `ao > 0`,
  `ao_rising` → the trigger logic itself is satisfied.

Expected: **no entry signal**;
`veto_reasons = ["stale_ao_cross", "no_adx_turn_confirmation"]`.

**FE-G2 — fresh + confirmed → NO veto (entry fires)**

```
ao              = [-1.2, -0.6, -0.1, 0.5, 1.1]
adx14           = [18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5]   (plus_di = 28, minus_di = 15)
konkorde_marron = [-0.5, 0.7, 1.3]
```

* `ao_zero_cross_up` at index 3 → age 1 ≤ 3 ✓; `ao_rising` ✓.
* `adx14` = E1-G1 → `adx_turn_up_bullish` fires on the last closed candle
  (age 0 ≤ 3) ✓.
* `konkorde_zero_cross_up` at index 1 of 3 → age 1 ≤ 3 ✓.

Expected: **entry signal fires**, `veto_reasons = []`.

**FE-G3 — fresh crosses but steady ADX → VETO (isolates V2)**

```
ao              = [-0.6, 0.4, 1.0]
adx14           = [16, 17.2, 18.4, 19.6, 20.8, 22.0, 23.2, 24.4, 25.6]   (plus_di > minus_di)
konkorde_marron = [-0.3, 0.9]
```

* `ao_zero_cross_up` age 1 ✓ fresh; `konkorde_zero_cross_up` age 0 ✓ fresh.
* `adx14` = E1-G2 (constant slope 1.2 pts/bar, bend = 0) → no turn ever fires.

Expected: **no entry signal**; `veto_reasons = ["no_adx_turn_confirmation"]` —
freshness alone is not enough, the move must be "bien marcado".

### B.3.1 — M1 `false_entry_watch`: AO×ADX false-entry monitor (owner addendum, 2026-07-11)

**Owner's words (verbatim, 2026-07-11)**: "El AO pasa de su punto 0; si no
hay giro condicionado de ADX para confirmar impulso, confirma falsa entrada.
Le damos 5 velas de giro: si cambió y el ADX no giró favorable confirmando,
le damos ~70% de probabilidades de impulso contrario y de vuelta a pasar el
punto cero. O sea: viene y pasó 0 alcista pero el ADX no tuvo 90 grados de
giro; si el AO sigue con velas verdes y no gira apenas complete las primeras
2 velas seguidas, lo más seguro es que el giro sería para impulso bajista y
fue falsa. **Es lo que más monitoreamos.** Esto podemos orientarlo."

**What this is**: the V2 doctrine (an AO zero-cross not confirmed by an ADX
turn is not tradable) promoted from a passive entry veto to an **active,
alertable monitor**. V1/V2 only speak when a setup trigger fires; M1 watches
EVERY AO zero-cross on the monitored TFs and adjudicates it. This is the
owner's primary chart-watching activity, so it is a first-class **F1 watcher
requirement** — same tier as guardian-retracement alerts (§F).

**Evidence context (F0 gate, 2026-07-11 — `docs/F0_GATE_ANALYSIS.md` §3)**:
the ADX-confirmation doctrine (V2) is the veto the PB-1D counterfactual
VALIDATED (w5 vetoed subset −0.46R vs accepted +0.51R). The freshness veto
(V1) INVERTED on IMP-4H — chasing fresh AO crosses is that family's failure
mode. M1 formalises exactly the doctrine with evidence behind it, and its
per-TF false-entry rates are the calibration data Q17 asks for.

**Inputs** (per symbol × TF × direction; closed candles only): `ao`, `adx14`,
`plus_di`, `minus_di`. Every state is derivable **statelessly** from the
series at evaluation time — no persisted watch state, matching the engine's
recompute pattern.

**Definitions** (bullish case; bearish is the strict mirror):

* **cross** — `ao_zero_cross_up` fired at closed candle `t0`
  (`zero_cross_age(ao, direction="up", confirm_bars=1)`, §E2 semantics).
* **favorable turn** — `adx_turn_up_bullish` (E1, grade A or B) firing on any
  closed candle `c` with `t0 <= c <= t0 + confirm_candles`. Note the window
  runs FORWARD from the cross; V2's `confirm_window` runs backward from the
  trigger candle — related but distinct checks.
* **AO green candle** — `ao_rising` on that closed candle (`ao[i] > ao[i-1]`)
  [interpretation: TradingView paints the AO bar green when it rises, which
  is the color the owner reads]. Post-cross candles only — the cross candle
  itself does not count toward the 2-candle checkpoint [interpretation].

**State machine** (evaluated at every closed candle):

| State | Condition | Emits |
|---|---|---|
| `WATCHING` | cross fired, `event_age < confirm_candles`, no favorable turn yet, AO has not re-crossed zero | — |
| `WATCHING` + `early_warning` | the first `early_warning_candles = 2` **consecutive** green AO closed candles post-cross complete (earliest at age 2) AND still no favorable turn — the owner's "apenas complete las primeras 2 velas seguidas": momentum keeps printing but strength is not igniting | `false_entry_watch` alert, severity `early` |
| `CONFIRMED` (terminal) | favorable turn fired within the window | info event; V2 is simultaneously satisfied for any setup trigger |
| `FALSE_ENTRY_PROBABLE` (terminal for the watch; opens outcome tracking) | `event_age == confirm_candles` (5) reached with no favorable turn | `false_entry_watch` alert, severity `adjudicated`, `p_false = 0.70` — expected outcome: contrary impulse and AO re-cross of zero |
| `WHIPSAW` (terminal) | AO re-crossed zero (opposite direction) at age `< confirm_candles`, before adjudication | counted only — a de-facto false entry that already resolved; no prediction value |

Outcome tracking after `FALSE_ENTRY_PROBABLE` (backtest/calibration only —
no live alerts):

| Resolution | Condition (within `resolution_horizon` closed candles) | Meaning |
|---|---|---|
| `RESOLVED_FALSE` | AO re-crosses zero | prediction HIT |
| `RESOLVED_LATE_CONFIRM` | favorable turn fires late | prediction MISS (late impulse) |
| `EXPIRED` | horizon elapses, neither happened | prediction MISS (chop, no contrary impulse) |

**Directional table**:

| Cross | Favorable turn (confirmation) | Contrary prediction on failure |
|---|---|---|
| `ao_zero_cross_up` | `adx_turn_up_bullish` | bearish impulse, AO re-cross down |
| `ao_zero_cross_down` | `adx_turn_up_bearish` | bullish impulse, AO re-cross up |

(For a bearish cross the confirmation is ADX **igniting** with −DI dominant —
`adx_turn_up_bearish`. `adx_turn_down` is strength collapsing and never
confirms anything.)

**Parameters**:

| Param | Default | Notes |
|---|---|---|
| `confirm_candles` | 5 | owner-fixed ("le damos 5 velas de giro"). Deliberately equal to V2 `confirm_window = 5` (§E Q10) — keep the two coupled unless the backtest shows they should diverge **[calibrable]** |
| `early_warning_candles` | 2 | owner ("las primeras 2 velas seguidas"); consecutive same-direction AO candles post-cross |
| `p_false_prior` | 0.70 | owner PRIOR, not a measured statistic — see Q17 |
| `resolution_horizon` | 10 | closed candles; analyst provisional, outcome resolution only **[calibrable]** |
| `confirm_bars` (cross) | 1 | same zero-cross event semantics as E2/E3 |

**TF scope**: provisionally ALL four operative TFs (`1h/4h/1d/1w`, §H). AO
and ADX are both-band elements (§0.3), so the band table permits M1
everywhere. See Q16.

**Emissions**:

1. **As veto — nothing new**: V2 already encodes the passive side. A setup
   trigger landing while M1 has no favorable turn is vetoed by V2 exactly as
   before; M1 adds no second veto (no double counting in `veto_reasons[]`).
2. **As alert (F1 watcher)** — event `false_entry_watch` on transitions to
   `early_warning`, `FALSE_ENTRY_PROBABLE` and `CONFIRMED`. Payload:
   `{symbol, timeframe, direction, state, severity, cross_ts, event_age,
   consecutive_ao_candles, adx_turn: {fired, age, grade} | null, p_false,
   rule_version}`.
3. **Candidate orientation ("esto podemos orientarlo")**: an adjudicated
   `FALSE_ENTRY_PROBABLE` is candidate *evidence* for an OPPOSITE-side setup
   (contrary impulse expected, p≈0.70). PARKED: never a standalone trigger;
   requires its own backtest gate like every other rule.

**Mapping to existing primitives** (`src/controllers/metrics/setup_service.py`):

| Need | Primitive | Status |
|---|---|---|
| cross detection + age (the watch clock) | `zero_cross_age(series, direction, confirm_bars)` :366 | exists |
| favorable turn + A/B grade | `adx_turn_fired_within(...)` :160 | exists, but its window is measured BACKWARD from the evaluation candle; M1 needs the forward-from-cross variant (turn fired at `c ∈ [t0, t0+5]`) — small extension |
| AO candle color | `ao_rising` :354 / `ao_falling` :358 | exists; needs an "n consecutive post-cross" counter on top |
| state derivation | — | missing: `false_entry_state(ao, adx14, plus_di, minus_di, direction, params) -> state + payload`, a pure function of closed series |
| alert plumbing | — | missing: the F1 watcher does not exist yet; M1 is a primary requirement for it |
| calibration counters | — | missing in `BacktestService`: per-state counts + realized false-entry rate (`RESOLVED_FALSE` / adjudicated) vs `p_false_prior`, stratified by TF and setup family (Q17) |

**Golden cases** (defaults above; `adx14` series have `plus_di > minus_di`
throughout; all series end on the same closed candle):

**M1-G1 — the owner's canonical case → FALSE_ENTRY_PROBABLE**

```
ao    = [-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, 1.8]
adx14 = [24.6, 24.7, 24.8, 24.9, 25.0, 25.1, 25.2, 25.3, 25.4]
```

* Cross up at index 1; evaluated at index 6 → `event_age = 5`.
* ADX constant slope 0.1 pts/bar → bend 0 → no turn ever fires (level 25.4
  is irrelevant: level ≠ turn, FE-G1 doctrine).
* `early_warning` fired at index 3 (indexes 2 and 3 both rising = the first
  2 consecutive green candles post-cross, age 2).
* At age 5: **state = `FALSE_ENTRY_PROBABLE`**, `p_false = 0.70` → alert.

**M1-G2 — confirmed impulse → CONFIRMED**

```
ao    = [-0.5, 0.4, 0.8, 1.1, 1.3]
adx14 = [18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5]   (plus_di 28 / minus_di 15)
```

* Cross up at index 1 (age 3 at evaluation); `adx_turn_up_bullish` (= E1-G1)
  fires on the last closed candle = 3 candles after the cross ≤ 5.
* **State = `CONFIRMED`** — info event only; a setup trigger here would pass V2.

**M1-G3 — fast whipsaw → WHIPSAW**

```
ao = [-0.5, 0.3, 0.1, -0.2, -0.6]
```

* Cross up at index 1; re-cross down at index 3 (age 2 < 5) → **state =
  `WHIPSAW`** — counted as de-facto false entry, no adjudication alert.

**M1-G4 — early warning isolate (watch still open)**

```
ao    = [-0.5, 0.4, 0.9, 1.5]
adx14 = [20, 20, 20, 20, 20, 20, 20, 20, 20]
```

* Cross at index 1; at index 3 the first 2 consecutive green candles
  complete (age 2 < 5), no turn yet → **state = `WATCHING`,
  `early_warning = true`** — `severity: early` alert fired, adjudication
  still pending.

---

## C. Phase-0 gate: what the multi-TF backtest must report

Run matrix per `rule_version`: each setup × its TFs × symbols `BTC/USDT` and
`ETH/USDT` (bitget, per D1) × ≥ 3 years of history for 1d context (≥ 18 months
for 4h).

**Required additions to the current `BacktestService`** (today it scores
`RulesService` on a single TF and models **zero fees**):

1. Setup-driven entries (SetupService) with §0.2 multi-TF alignment.
2. **Fee/slippage model** — expectancy MUST be net:
   `fee_rate_per_side = 0.1 %` (bitget spot taker) and
   `slippage_per_side = 0.05 %` **[calibrable]**, both recorded in the result.
3. Chronological in/out-of-sample split `70/30`. Calibration of any
   **[calibrable]** parameter may only use the in-sample segment; OOS is run
   once per `rule_version`.

**Report per run** (extends the existing `_summarise` output): `rule_version`,
`setup_id`, symbol, TFs, `n_trades`, `win_rate`, `expectancy_R` (net),
`avg_win_R` / `avg_loss_R`, `profit_factor`, `max_drawdown_pct`,
`avg_trade_duration_bars`, fee/slippage assumptions, IS and OOS blocks
separately. Additionally, per §B.3: `vetoed_signals` (count + breakdown by
`veto_reason`), and — recommended report, not a PASS threshold in F0 — a
**counterfactual replay** of the vetoed entries as hypothetical trades: the
veto is empirically justified when vetoed-entry expectancy is materially below
accepted-entry expectancy; report both numbers side by side.

**PASS / NO-PASS thresholds (analyst recommendation)**:

| Metric | Threshold |
|---|---|
| `n_trades` (full period, per setup+symbol) | ≥ 30 — below this, **NO PASS regardless of results** (insufficient sample) |
| `n_trades` OOS | ≥ 10 |
| `expectancy_R` net, full period | ≥ +0.15 R |
| `expectancy_R` net, OOS | ≥ +0.10 R |
| `profit_factor` OOS | ≥ 1.15 |
| `max_drawdown_pct` | ≤ 20 % |
| Overfit check | OOS expectancy ≥ 50 % of IS expectancy |
| Multi-symbol robustness | expectancy net > 0 on the primary symbol AND ≥ −0.05 R on the second (a setup that only works on one asset is suspect) |

A setup passes the F0 gate only if **every** row passes. Passing F0 unlocks
F1 (alerts/watcher on closed candles) — never live orders, which sit behind the
paper-trading gate per the roadmap.

---

## D. Open questions for the owner

Provisional decisions taken by the analyst that the owner must confirm or
correct (each maps to a **[calibrable]** default above):

1. **ADX "90°" quantification (E1)**: implemented as slope-delta —
   recent slope over 3 closed bars ≥ 1.0 ADX-pts/bar AND bend
   (recent − prior slope over 5 bars) ≥ 1.5 pts/bar, ADX floor 10. Confirm the
   windows/thresholds, or provide 2–3 chart examples of the turn to calibrate
   against.
2. **AO divergence pivots (E2)**: fractal strength 2 (confirmed 2 bars late),
   pivots 5–40 bars apart, and the "regular divergence" requirement that both
   AO pivots sit on the same side of zero. OK?
3. **Konkorde cross (E3)**: plain zero-cross of `marron` with 1-candle
   confirmation, no extra filter. Should the `verde > azul` (strong hands)
   filter be ON?
4. **Vol "high zone" (E4)**: turns are only meaningful at BBWP ≥ 70, while > 50
   is just the tradeable-regime filter. Or do you want turns detected from 50
   up?
5. **BBWP > 50 vs current 20/80 (E5)**: in F0 it only governs the new setups
   and the legacy scorer keeps 20/80 (including `vol_low < 20` as *entry*
   support, which contradicts the > 50 doctrine). Should the legacy scorer be
   retired/aligned in F1?
6. **Band cut (§0.3)**: low = everything **below 4h** (1m–2h), high = 4h and
   up (4h/6h/8h/12h/1d/3d/1w). Confirm that 1h and 2h are definitively "low",
   and that 6h/8h/12h/3d count as "high".
7. **Pullback trigger TF (B.1)**: specified at 1d. Drop the trigger to 4h for
   finer entries (context stays 1d/1w)?
8. **Shorts in F0**: backtest long-only first, or mirror shorts from the start?
9. **Fees (C)**: net expectancy assumes bitget spot taker 0.1 % + 0.05 %
   slippage per side. Confirm the actual fee tier / market type (spot vs
   futures) to lock the numbers.
10. **False-entry vetoes (B.3)**: `max_event_age = 3` closed candles for the
    AO/Konkorde zero-cross freshness (V1) and `confirm_window = 3` for the
    ADX-turn confirmation (V2). Confirm both numbers, and whether a strong ADX
    **level** (≥ 25 with dominant DI) may substitute for the turn in V2 — the
    spec says no: the turn is always mandatory, level alone still vetoes
    (FE-G1).
11. **Vetoes in `low_tf` band (B.3)**: the spec applies V1 + V2 in both bands
    (in `low_tf` they act on the AO cross and the ADX turn, the only trigger
    events available there). Confirm this also holds for any future low-band
    scalping setup.
12. **E6 `trend_speed` threshold (post-F0 candidate)**: if E6 is ever
    activated, should the impulse-strength gate compare the current wave
    against the **average** wave (`ratio_avg >= 1.0`, more sensitive — the
    spec's provisional choice) or against the **maximum** wave (`ratio_max`,
    more conservative)? And confirm the adaptive-EMA approximation for wave
    resets (provisional: KAMA(10); simplest alternative EMA(20)).

### D.2 — Open questions added 2026-07-11

13. **Minor vs major ADX turn (E1 addendum 2026-07-11)**: quantify "giro
    menor con forma V" vs "giro mayor" — amplitude in ADX points around the
    pivot, duration in bars, origin level, or a combination? And does the
    ~20-point ambiguity zone (continuation vs false breakout) tighten the
    A-grade origin band `[12, 20]` (e.g. to `[12, 18]`)? 2-3 chart examples
    of each class would let us calibrate.
14. **"Abrupt" BBWP color change threshold (E5 addendum 2026-07-11)**: is
    `zone_jump` (≥ 2 zones in ONE closed candle) the right quantifier of
    "brusco", or does a fast 1-zone change (e.g. within ≤ 2 candles) or a
    points-per-candle rate (e.g. ≥ 25 BBWP pts/candle) also count?
15. **Konkorde volume "media alta" (E3/E4 addendum 2026-07-11)**: define the
    high-mean zone — current rolling percentile (q=80, lookback 100) vs
    mean-relative (`x >= k · rolling_mean(x, n)`, e.g. k=1.5, n=50) vs a
    fixed level on the re-centred scale. Which matches your chart read?
16. **M1 monitor TF scope (§B.3.1)**: does `false_entry_watch` run on all
    four operative TFs (1h/4h/1d/1w, §H) or only the lower ones (1h/4h)
    where false AO crosses are most frequent? Provisional: all four, alert
    severity weighted by TF.
17. **The 70% (§B.3.1)**: is `p_false_prior = 0.70` fixed doctrine or a
    prior to CALIBRATE? Analyst recommendation: treat it as an owner prior —
    the F0 backtest measures the realized false-entry rate per TF and setup
    family (`RESOLVED_FALSE` / adjudicated watches) and reports it next to
    0.70; replace the prior only with n ≥ 30 adjudications per TF.

---

## E. OWNER DECISIONS — 2026-07-06 (answers to Section D)

Recorded from the owner's answers; these override the provisional defaults
above. Remaining questions (1-5, 7, 11, 12) keep their provisional defaults
until answered.

- **Q6 (band cut): CONFIRMED** — low band = everything below 4h (1m-2h, only
  BBWP+AO+ADX); high band = 4h and up (4h/6h/8h/12h/1d/3d/1w, full strategy).
- **Q8 (shorts): MIRROR SHORTS FROM F0** — the backtest validates long AND
  short mirrored setups from the start. Gate C metrics are reported per side;
  n >= 30 applies to the combined set with per-side breakdown. NOTE: real
  short execution requires margin/futures (spot cannot short) — that is an
  F3 execution decision, the backtest simulates symmetric entries.
- **Q9 (market/fees): UNDER REVIEW** — owner is evaluating spot, margin and
  futures. Implementation: fee/slippage are CONFIG PARAMETERS of the backtest
  (per-side taker fee, per-side slippage, optional funding rate for
  perpetuals). Base/reference model until decided: bitget spot taker 0.10% +
  0.05% slippage per side (conservative). Gate C must be reported with the
  base model; re-runs with margin/futures params are one config change.
- **Q10 (veto windows): RELAXED TO 5** — `max_event_age = 5` closed candles
  (V1 freshness) and `confirm_window = 5` (V2 ADX-turn confirmation). Both
  stay calibrable; the counterfactual veto replay in the backtest should
  compare 3 vs 5 to validate the choice with evidence. The sub-rule stands:
  ADX level alone (>= 25, dominant DI) does NOT substitute the turn — no
  adx_turn within window = veto (FE-G1 unchanged).

### E1 refinement — ADX turn origin level (owner, 2026-07-06 late)

The BEST entry turns are those where the ADX pivots **from ~16 on the scale**:
a low-ADX turn means the previous trend's strength has fully reset and a new
move is being born; a turn starting from an already-high ADX is late.

Implementation: `adx_turn` gains an origin-level quality dimension:
- `origin_level` = ADX value at the pivot (the local low where the turn starts).
- **A-grade turn**: `origin_level` inside `[origin_low, origin_high]` =
  `[12, 20]` (sweet spot centered at 16) [calibrable].
- **B-grade turn**: any other origin that still satisfies the slope/bend rule.
- Setups and the V2 veto accept both grades in F0, but the backtest MUST
  stratify results by grade (A vs B) — if A-grade entries dominate expectancy,
  F1 restricts V2 confirmation to A-grade turns (rule_version bump).
- Golden case to add with implementation: ADX series pivoting at 16.2 with
  slope/bend passing → A-grade; same shape pivoting at 31 → B-grade.

### Owner proposal — 2026-07-06 late: 1h full-strategy variant with E6

Owner hypothesis: on 1h the FULL strategy could be traded (not just the low
band subset) IF E6 trend_speed acts as mandatory additional confirmation
(compensating Konkorde noise at 1h). To validate, the backtest adds a
**variant C**: `1h-full+E6` (all elements + E6 wave-ratio gate on 1h) to be
A/B-compared against the band-pure setups after the F0 gate. Not part of F0
scope; requires E6 implementation first. If variant C beats IMP-4H on net
expectancy with n>=30, the band table gains a 1h exception (rule_version bump).

## F. POSITION MANAGEMENT — TF LADDER MODEL (owner, 2026-07-06 late)

Owner's management doctrine, verbatim concept: enter/hold while the entry
band is aligned; the EXIT is decided by the next timeframe up (the
"guardian"); after a guardian retracement, re-evaluate the opposite side;
conviction cascades up the ladder.

- **Alignment entry**: a low-band trade requires 15m/30m/1h aligned in the
  same impulse direction (low-band elements: BBWP+AO+ADX). Setup entries
  (4h/1d) require their own band alignment per §0.2.
- **Guardian TF** (= exit authority, one band up):
  | Trade managed on | Guardian |
  |---|---|
  | 15m-1h (low band) | 4h |
  | 4h | 1d |
  | 1d | 1w |
- **Exit rule**: close the position when the GUARDIAN fires a retracement
  against it: directional `adx_turn` against the position + AO rollover/cross
  against, OR `vol_turn` V/W in high zone on the guardian TF. Lower-TF noise
  (e.g. 15m flipping bearish) does NOT exit a trade whose guardian (4h) has
  not fired.
- **Flip evaluation**: after a guardian retracement exit, when the guardian's
  new cycle starts, evaluate the OPPOSITE side as a fresh setup — full rules
  + vetoes apply; never an automatic flip.
- **Conviction cascade**: 4h + 1d + 1w impulses aligned = full-size tier;
  partial alignment = reduced tier (ties into sizing_profiles; exact tiers =
  open question for calibration).
- F1 implication: the watcher must alert GUARDIAN RETRACEMENT events for open
  positions, not only entry signals.

### E7 CANDIDATE — channel/structure confluence (owner, 2026-07-06 late)

Owner observation: hand-drawn bearish/bullish CHANNELS are respected — the
channel floor coincided with the actual bounce lows, retracements on 15m
respect intermediate lines, and the ceiling is a rejection candidate.

Concept (implementable, parked post-F0 like E6):
- Detect channels programmatically: fractal pivots (strength 2, closed bars)
  -> linear regression over pivot highs and pivot lows -> parallel-ish lines
  with `respect_count` = touches within tolerance (ATR fraction). A channel is
  VALID with >= 3 respected touches.
- Use as CONFLUENCE, never as trigger: (a) strategy long signal AT the channel
  floor = quality bonus; (b) rejection candidates at the ceiling only WITH a
  fresh opposite trigger + adx_turn (vetoes apply unchanged); (c) TP
  projection = opposite channel boundary (geometric target).
- **Variant D (backtest, post-F0): low-TF channel scalps at high leverage** —
  owner idea: on 15m/1h, channel structure gives the tight structural stop
  (just beyond the floor/ceiling) and geometric TP that high leverage (10x)
  needs. The backtest must model fees+slippage at scalp frequency and report
  liquidation-adjusted risk; variant D is approved ONLY if net expectancy
  survives those costs. Until then, high leverage stays confined to paper.

### E7 addendum — measured move & inter-channel transition (owner, 2026-07-06 late)

Owner doctrine, from live BTC 15m example (two channels: ascending 15m channel
inside the macro descending channel):
1. A counter-trend ascending channel INSIDE a bearish macro structure
   typically resolves with a DOWNSIDE break (short) — trade the channel long
   while it holds, expect the break.
2. **Measured move ("saldo minimo")**: after the break, the minimum projected
   move equals the span the channel already traveled (break level minus the
   channel's traveled range; first objective = channel WIDTH, full objective =
   traveled span). Projection targets gain confluence when they land on the
   macro channel's opposite boundary.
3. **Transition chop**: while exiting, price tends to BOUNCE BETWEEN the
   broken channel line (now resistance) and the next structure below — the
   inter-channel zone is chop, not trend; entries there are low quality
   (vetoes apply, expect whipsaw).
Implementation: extends E7 channel objects with `traveled_span`, `width`,
`break_direction`, `measured_targets[]`; signals inside the inter-channel
transition zone get a quality penalty. Backtest variant D covers it.

### E7 addendum 2 — fractal nesting & which-channel-governs (owner, 2026-07-06 late)

Channels NEST fractally: e.g. 15m channels alternate (ascending flag -> break
-> descending channel -> measured target lands on macro boundary -> new
ascending channel) INSIDE a daily ascending channel, itself inside the
weekly/daily descending macro channel. Verified live on BTC (owner charts):
the late-June descending 15m channel completed its measured move exactly on
the macro floor (~58k) before the current ascending sequence.

Governance rule (ties into §F TF ladder):
- You OPERATE the channel of your trade's timeframe.
- You EXIT by the guardian timeframe's channel/retracement.
- The MACRO channel caps direction conviction and size: a counter-trend
  channel inside a bearish macro is traded long while it holds but is
  EXPECTED to resolve in the macro's direction — UNLESS price breaks the
  macro boundary itself (daily close beyond) = regime change, hierarchy flips.

## G. APPROVED BRAINSTORM — event-driven rotation + scalp mode (owner, 2026-07-07)

Owner-approved direction (brainstorm level — NOT in F0/F1 scope until promoted):

1. **Volatility screener + rotation scanner (one component, priority 1 — natural F1 fit).**
   Triggers: guardian-TF candle close (existing cron), TRADE CLOSED (TP/SL hit),
   FIGURE COMPLETED (E7 channel break), RETRACEMENT DETECTED. On trigger, run the
   F0 evaluator across the whole watchlist and rank assets by setup-readiness
   (context alignment + trigger freshness + BBWP regime + ATR% of the target
   band). Output: top-N "where is the next move" with reasons (owner's case:
   stopped out on BTC -> scanner points at the asset actually retracing today).
2. **SCALP-5M setup family (priority 2 — backtest-gated).** Constant quick trades
   targeting +1.5-1.8%. Low-band rules only (BBWP+AO+ADX per §0.3) + E7 channel
   structure for tight stops. Eligibility screen: only assets where 1.8% is a
   3-6x ATR(5m) move (screener above). Fees are the killer: taker round-trip +
   slippage ~0.25-0.3% (~17% of target) — model REAL fees, prefer maker entries,
   thin-spread pairs only. Backtest variants: fixed TP 1.5% / 1.8% vs
   channel-projected TP; 60-90 days of 5m data. Approved ONLY if net expectancy
   survives (same gate discipline as §C).
3. **Multi-market data layer (phase 2).** Owner watches non-crypto too (OIL, gold,
   SP500). Signals require a second data provider (ccxt is crypto-only);
   execution on those markets is out of scope. Design as a DataProvider
   abstraction when promoted.

Context note: the 2y/3-symbol gate run showed the 4h/1d setups are ultra-selective
(~25 trades, mostly positive expectancy, n far below gate) — rotation across a
wider watchlist and a scalp family are the frequency fillers, each behind its
own gate.

### E5 addendum — BBWP color zones & zone-change events (owner, 2026-07-07)

BBWP analysis must also consider its COLOR (zone) and COLOR CHANGES (zone
transitions), mirroring the TradingView rendering the owner reads:

| Zone | Range [calibrable] | Meaning |
|------|--------------------|---------|
| blue | [0, 20) | extreme compression (spring loading) |
| green | [20, 50) | building |
| yellow | [50, 80) | tradeable regime (E5 >50 lives here) |
| red | [80, 100] | extreme volatility (exhaustion watch, E4 territory) |

Events (closed candles): `bbwp_zone_change(from, to)`. Notable transitions:
- **blue->green**: expansion ignition — the "spring firing" signal (candidate
  trigger component for IMP-4H's awakening after compression).
- **yellow->red**: entering extreme — arm E4 V/W turn detection.
- **red->yellow**: volatility rollover — corroborates E4 turns (exhaustion
  confirmed); candidate exit/invalidation signal.
Golden cases to add with implementation: series crossing 19->21 emits
blue->green; 81->79 emits red->yellow; no event while staying in-zone.

**Zone JUMPS (owner, same day):** when volatility rises fast the color can SKIP
a zone in a single closed candle (e.g. blue->yellow without green). A skip
(`zone_jump`, |to - from| >= 2 zones) means a HIGH-magnitude volatility burst —
stronger than a normal one-step transition: treat blue->yellow/red as explosive
expansion ignition (top-grade awakening signal), and yellow/red->blue collapse
as regime death. Golden case: 15 -> 62 in one candle emits zone_jump
blue->yellow (not two sequential changes).

---

## H. ORCHESTRATOR — INVESTOR PROFILES (owner, 2026-07-11)

mmk is an **orchestrator of trading**: one strategy engine (this spec),
multiple brokers, multiple investor **profiles**. A profile binds a leverage
tier to a timeframe zoom. Owner's rule, verbatim: "entre más grande el zoom,
menos apalancamiento" — the wider the timeframe, the lower the leverage.

| Profile | Leverage | Operating TF | Horizon | Guardian TF (§F) |
|---|---|---|---|---|
| **Ancient** | 0x (spot) | 1d / 1w | long | 1w (for 1d trades) |
| **Pro** | 5x | 4h | medium | 1d |
| **Snipper** | 10x | 1h | short | 4h |

* **Operative TF set = `{1h, 4h, 1d, 1w}`.** 1h formally ENTERS the
  operative set (until now only 4h/1d carried setups). This settles the
  operational side of Q6: 1h IS operated — but the band rules (§0.3) are
  UNCHANGED: on 1h only low-band elements apply (BBWP + AO + ADX, no
  Konkorde) unless the 1h-full+E6 variant C (§E, 2026-07-06 late) later
  validates through its own gate. Snipper therefore requires a `low_tf` 1h
  rule set to be specified and gated — the first real consumer of the band
  machinery shipped in F0. No such family exists yet.
* **Brokers**: Bitget + Bitunix. The broker × asset availability/fee matrix
  is being assembled by devops → `docs/BROKER_MATRIX.md` (pending; reference
  it, do not duplicate it here). The backtest fee/slippage configs (§E Q9)
  must pick up per-broker numbers from that matrix when it lands.
* **Universe**: BTC, ETH, SOL, gold, silver, SP500, USD/COP, oil. Crypto
  flows through ccxt; the non-crypto assets REQUIRE the multi-market
  DataProvider abstraction (§G item 3) — promoted from "phase-2 idea" to a
  structural dependency of this section. Execution on non-crypto markets
  stays out of scope until a broker in the matrix covers it.
* **Gates UNCHANGED (hard rule)**: the council's F0→F3 gates apply per
  profile AND per setup family. **Any leverage > 0x is an F3+ decision
  behind the live-tiny gate**: Pro/Snipper run F0 backtest → F1 alerts → F2
  paper with SIMULATED leverage (funding and liquidation modelled — §E7
  variant D discipline) before any real margin. Ancient (0x spot) is the
  only profile that can reach live first. Leverage never changes signal
  logic — same rules, same vetoes — it only changes sizing/risk via
  `sizing_profiles` (live↔backtest parity preserved).
* **Status vs gates (2026-07-11)**: PB-1D majors (Ancient territory) is the
  only family with a ratified path to F1 (modified gate,
  `docs/F0_GATE_ANALYSIS.md`). Nothing Pro or Snipper would trade has passed
  any gate (IMP-4H parked pending trigger redesign; no 1h family specified).
  **The profile table is a target topology, not a green light.**

---

## I. RULE SPEC v0.2.0 — IMPLEMENTED (GATED)

| | |
|---|---|
| **rule_version (target)** | `0.2.1` (supersedes `0.2.0`-as-shipped — OBSOLETE, see §I.9) |
| **Status** | **IMPLEMENTED — GATED, INACTIVE BY DEFAULT — REPLAY RUN (120d, 2026-07-16), 0.2.1 PACKAGE APPLIED PER COUNCIL 2026-07-17** |
| **Dictated** | 2026-07-13 (owner) |
| **Designed** | 2026-07-14 (trading analysis) |
| **Implemented** | 2026-07-16 — `rule_v020.py` (pure detectors/state machines) + `monitors_v020.py` (additive monitor assembly), behind the `RULE_VERSION` gate (default `0.1.0`). See §I.8 for the module map and the ambiguities the implementation had to resolve. |
| **Revised** | 2026-07-17 — v0.2.1: H1 freshness fix (P0), measured priors, Rule-2 addends zeroed, M2/C1 degraded to evidence, pre-registrations. See §I.9 and the v0.2.1 notes inline in §I.1–§I.5. |
| **Scope** | Additive to v0.1.0: two new monitor states/machines (M1.1, M2), one hierarchy override (H1), one new detector (E4.1), one new composite setup (C1), plus the v0.2.0-b micro band (15m, M1m, C1-micro). **Nothing here activates until `/mmk-council` gates the `rule_version` bump.** |

> **HARD GATE.** Everything in §I is **implemented but INACTIVE by default**:
> the code ships in the engine yet only runs when `rule_version` is explicitly
> `0.2.0` or `0.2.1` (env `RULE_VERSION`, or the `rule_version` query param on
> `/v1/setups/evaluate` — added so the §I.6 replay can run the versions on
> identical code; both 0.2.x labels execute the SAME corrected module, §I.9).
> With the default `0.1.0` the engine's behaviour is
> byte-identical to pre-v0.2.0 (pinned by `tests/test_v010_no_regression.py`).
> It does not vote, does not alert, does not veto and does not trade in prod
> until: (1) the §I.6 validation replay shows the required improvements, AND
> (2) the council explicitly ratifies the `rule_version` 0.2.0 bump (§0.4).
> Section labels below (B.3.2, B.3.2b, B.3.3, E4.1, B.4) mark where each rule
> would slot into the active numbering **on promotion**; they are not active
> section numbers today.
>
> **Operative TF set for v0.2.0 = `{30m, 1h, 4h, 1d, 1w}`** — 30m formally
> joins the monitor set (5 TFs; §H had 4). Band rules (§0.3) are unchanged:
> 30m/1h are `low_tf` (BBWP+AO+ADX only, no Konkorde); 4h/1d/1w are `high_tf`.

---

### I.1 — (B.3.2) M1.1 `color_flip` adjudication — early false-entry confirmation by DI color

**Owner's words (2026-07-13)**: the AO can keep printing green after the cross,
but if the **DI color flips** against the cross before the ADX ever turns
favorable, the false entry is already confirmed — you do not need to wait the
full 5 candles. Reading the colors early is the point ("tener claros los
colores", §E5 addendum 2026-07-11).

**What this is**: a **stronger, earlier** terminal verdict layered onto the M1
`false_entry_watch` machine (§B.3.1). M1 adjudicates `FALSE_ENTRY_PROBABLE`
(`p_false = 0.70`) only at timeout (`event_age == confirm_candles = 5`). M1.1
adjudicates `FALSE_ENTRY_CONFIRMED` (`p_false = 0.80`) as soon as the DI color
flips against the cross inside a tight early window, still with no favorable
ADX turn. Higher confidence, earlier — because a color flip is affirmative
contrary evidence, not just absence of confirmation.

**DI color** (the single new primitive; closed candle only):

```
di_color(t) = "bearish"  iff  minus_di[t] > plus_di[t]
            = "bullish"  iff  plus_di[t]  > minus_di[t]     (tie -> unchanged/neutral, no flip)
```

* **color aligned with the cross**: `bullish` for an `ao_zero_cross_up`,
  `bearish` for an `ao_zero_cross_down`.
* **color flip against the cross**: at post-cross age `a` the color has become
  the OPPOSITE of the cross direction, having been aligned (or neutral) at the
  cross candle `t0`.

**Additional state** (extends the §B.3.1 machine; bullish case, bearish mirror):

| State | Condition | Emits |
|---|---|---|
| `FALSE_ENTRY_CONFIRMED` (terminal; supersedes a would-be `FALSE_ENTRY_PROBABLE`) | DI color flips against the cross at post-cross age `a ∈ [color_min_age, color_max_age] = [2, 4]` AND no favorable `adx_turn` (E1, grade A/B) fired in `[t0, t0+a]` | `false_entry_watch` alert, severity `adjudicated_color`, `p_false = 0.80` |

Precedence inside the machine: `CONFIRMED` (favorable turn) still wins if the
turn fires — a real impulse overrides the color flip. A flip **before**
`color_min_age = 2` does NOT adjudicate (too early — that is the WATCHING
window, see M11-G2); a flip **after** `color_max_age = 4` falls through to the
ordinary age-5 timeout adjudication (`FALSE_ENTRY_PROBABLE`, 0.70). Whipsaw
(AO re-cross) still short-circuits to `WHIPSAW` if it happens first.

**Parameters** (extend §B.3.1):

| Param | Default | Notes |
|---|---|---|
| `color_min_age` | 2 | closed candles post-cross; earliest a flip adjudicates. Below this the flip is noise inside the WATCHING window **[calibrable]** |
| `color_max_age` | 4 | closed candles post-cross; latest a flip adjudicates as `adjudicated_color`. Above this the age-5 timeout path (0.70) governs **[calibrable]** |
| `p_false_color` | 0.80 | owner PRIOR (stronger than the 0.70 no-turn timeout because the flip is affirmative contrary evidence) — CALIBRATE like `p_false_prior`, see Q17 |

> **v0.2.1 — priors are now MEASURED data (replay 120d 2026-07-16, council
> 2026-07-17).** The Q17 calibration happened; the priors above are superseded
> by the measured values shipped as versioned rule data in `rule_v020.py`:
>
> * `p_false_color = 0.70` — contrary hit-rate of the FEC subset: 70.0%
>   (n=243; IS 71.6% / OOS 64.2%). The flip is the best available
>   discriminator, not a perfect one (43.9% of FEC sit on a real >= 1 ATR
>   impulse — H1-fresh corrects part of that).
> * `p_false_prior = 0.40` (timeout) — contrary hit-rate of the timeout
>   subset: 38% (n=648), and 73% of timeouts sat on a real >= 1 ATR impulse.
>   The 0.70 owner prior did NOT survive measurement.
> * M1m `p_false_ignition = 0.42` — price hit-rate 42.1% (n=57, interpool);
>   **wide confidence interval** — recalibrate as forward data accrues.
>
> Reverting these priors is part of the pre-registered failure path (§I.9d).

**Directional table** (color aligned vs flip):

| Cross | Aligned color | Flip color (adjudicates) | Contrary prediction |
|---|---|---|---|
| `ao_zero_cross_up` | `plus_di > minus_di` | `minus_di > plus_di` | bearish impulse, AO re-cross down |
| `ao_zero_cross_down` | `minus_di > plus_di` | `plus_di > minus_di` | bullish impulse, AO re-cross up |

**Golden cases** (defaults above; `confirm_candles = 5`; all series end on the
same closed candle):

**M11-G1 — color flip at age 2 → `FALSE_ENTRY_CONFIRMED` (p_false 0.80)**

```
ao       = [-0.5, 0.4, 0.9, 0.7]
plus_di  = [ 26,  27,  24,  19 ]
minus_di = [ 16,  17,  22,  25 ]
```

* `ao_zero_cross_up` at index 1 = `t0`; evaluated at index 3 → post-cross
  age `a = 2`.
* DI color: bullish at `t0` (27 > 17, aligned) → at index 3 bearish
  (25 > 19) → **flip against the cross** at age 2.
* No favorable `adx_turn_up_bullish` in `[1, 3]`.
* age 2 ∈ [2, 4] → **state = `FALSE_ENTRY_CONFIRMED`**, severity
  `adjudicated_color`, `p_false = 0.80` → alert. (Contrast M1-G1, which would
  only reach `FALSE_ENTRY_PROBABLE` 0.70 at age 5.)

**M11-G2 — flip at age 1 < `color_min_age` → still `WATCHING`**

```
ao       = [-0.5, 0.4, 0.7]
plus_di  = [ 26,  27,  19 ]
minus_di = [ 16,  17,  24 ]
```

* Cross up at index 1; evaluated at index 2 → age `a = 1`.
* DI color flips bearish at index 2 (24 > 19), but `a = 1 < color_min_age = 2`.
* Too early to adjudicate → **state = `WATCHING`** (no `adjudicated_color`
  alert yet); the flip must persist to age 2 to confirm.

---

### I.2 — (B.3.2b) M2 `CONTRARY_IMPULSE` — the contrary move a false entry predicts

**Owner's words (2026-07-13)**: a confirmed false entry is a prediction — the
impulse goes the OTHER way and the AO comes back to re-cross zero (§B.3.1
"orientarlo"). M2 turns that parked candidate into a first-class **contrary
signal** — evidence only, never an auto-trade.

**Trigger**: after **any** `FALSE_ENTRY_*` adjudication on a TF (M1
`FALSE_ENTRY_PROBABLE` 0.70 or M1.1 `FALSE_ENTRY_CONFIRMED` 0.80), watch for a
contrary-impulse confirmation within `k_contrary = 5` closed candles of the
adjudication. The predicted contrary direction is the OPPOSITE of the
adjudicated cross (up-cross adjudicated false → bearish contrary, and mirror).

Confirmation = **any of**:

* **(a) contrary `adx_turn` same TF** — an `adx_turn` (E1, grade A/B) igniting
  in the contrary direction on the same TF (`adx_turn_up_bearish` after a
  false up-cross; `adx_turn_up_bullish` after a false down-cross).
* **(b) M1 `CONFIRMED` contrary, same TF or one band up** — a §B.3.1 `CONFIRMED`
  state for the contrary direction, either on the same TF or one operative band
  up the ladder: `30m→1h`, `1h→4h`, `4h→1d`, `1d→1w` (the higher TF confirming
  the contrary impulse is the strongest corroboration).
* **(c) AO re-cross with DI color already contrary** — the AO re-crosses zero
  in the contrary direction (`ao_zero_cross_down` after a false up-cross) AND
  `di_color` is already the contrary color on the re-cross candle (the §I.1
  color primitive) — momentum and strength-direction agree.

**Emission**: `contrary_impulse` signal, **call-grade for the TF's profile**
(§H: 30m/1h → Snipper, 4h → Pro, 1d/1w → Ancient) — i.e. the alert priority /
sizing tier is the profile that operates that TF. **Alert + evidence only (F1);
never auto-trade** — same discipline as the §B.3.1 "orientarlo" candidate and
every other rule (its own gate before it can inform a real order).

> **v0.2.1 (council 2026-07-17) — NO call-grade: evidence only.** The replay
> failed M2 as a graded call. Trigger (c) `ao_recross_color` (n=249) scored a
> 100% "contrary materialized" hit-rate that is **tautological by
> construction** — the trigger IS the re-cross having already happened — and
> its net forward economics are NEGATIVE (−0.18% k5 / −0.29% k10). Trigger (a)
> n=46 is flat; trigger (b) n=10 (< 30, no conclusion). The §H call-grade
> mapping is SUSPENDED: the engine still emits `contrary_impulse` entries
> (with the informational `profile` field), but consumers must treat them as
> evidence with NO alert priority / sizing tier until a non-tautological
> trigger definition passes its own gate (RECALIBRATE).

**Parameters**:

| Param | Default | Notes |
|---|---|---|
| `k_contrary` | 5 | closed candles after the adjudication in which a contrary confirmation counts **[calibrable]** |
| `band_up_map` | `{30m:1h, 1h:4h, 4h:1d, 1d:1w}` | the "one band up" ladder for trigger (b), aligned with the §F guardian ladder |

**Golden case**:

**M2-G1 — contrary ADX bend within `k` → `CONTRARY_IMPULSE` (trigger = a)**

* Start from an adjudicated false UP-cross (e.g. M11-G1 → `FALSE_ENTRY_CONFIRMED`
  at index 3); predicted contrary = **bearish**.
* Within `k_contrary = 5` closed candles the same-TF `adx14` bends up with
  `minus_di` dominant → `adx_turn_up_bearish` (E1, grade A/B) fires, e.g.
  `adx14 = [.., 18, 18, 18.5, 21.5, 24.5]` with `minus_di > plus_di` on the
  turn candle.
* → **`contrary_impulse` signal, trigger = (a)**, call-grade = the TF's
  profile. (Alert only.)

---

### I.3 — (B.3.3) H1 hierarchy override on M1/M1.1 verdicts

**Owner's words (2026-07-13)**: the higher timeframe governs — a low-TF "false
entry" is not false if the timeframe above already confirmed the same impulse.
This is the §F TF-ladder doctrine applied to the false-entry monitor.

**What this is**: a precedence layer that can **override** an M1/M1.1
false-entry verdict using the state one band up the ladder (§F,
`band_up_map`). Three ranked rules; higher rank always wins.

**Rule 1 (highest) — higher-TF confirmation blocks the timeout false verdict.**
If the SAME direction is M1 `CONFIRMED` **one band up** (`30m→1h`, `1h→4h`,
`4h→1d`, `1d→1w`), the low-TF watch **must NOT** adjudicate `FALSE_ENTRY_*` by
timeout. New terminal state **`CONFIRMED_BY_HIGHER_TF`** (alertable): the
impulse is real on the governing TF, the low-TF ADX simply has not printed its
turn yet. This overrides both the §B.3.1 age-5 timeout AND the §I.1
`adjudicated_color` flip.

> **v0.2.1 (council 2026-07-17) — freshness `<= 6` closed candles is a
> CONDITION OF GRANTING, not just emission gating.** A higher-TF `CONFIRMED`
> is a Rule-1 source only while its confirming event (the E1 turn for M1, the
> AO/BBWP body for M1m) is at most 6 closed candles old — the same
> `_fresh_confirmed` bound the emission gate and `ignition_from_below` use.
> Measured on the 120d replay (2026-07-16): WITHOUT the bound, a stale
> `CONFIRMED` (sticky until the next cross — weeks on 1d/1w) rescued
> everything: 409 CBHT finals (BTC: 239/325), **ZERO FALSE adjudications**
> (the M1 monitor dies and M2 loses its sources), and the stale rescues were
> BAD (59–79% price precision). WITH the bound: 34 CBHT finals at 84–93%
> precision, monitor alive. This was the shipped-0.2.0 P0 (§I.9).
>
> **CBHT stickiness is DEFERRED to the mmk-api journal.** 31 of 65 rescues
> lapsed when the source confirm's freshness expired and the episode reverted
> to FALSE ("rescate que caduca"). Sticky-per-episode CBHT CANNOT live in
> this engine — it is stateless and recomputes every state from candles on
> each call, with no episode memory. If the council wants CBHT sticky once
> granted, that semantics belongs to the stateful consumer (the mmk-api
> journal), which already dedups by `cross_candle_ts` — council dictamen
> 2026-07-17.

**Rule 2 — `vol_turn_rounded` on TF ≥ 4h boosts p_false against a retracement.**
An E4.1 `vol_turn_rounded` (§I.4) firing on a `high_tf` candle marks a
volatility rollover = a probable retracement of the move on that TF. For any
lower-TF watch **opposing the implied retracement** it adds to `p_false`
(cap **0.90**), and **boosts the M2 contrary score equally**:

| `vol_turn_rounded` TF | `p_false` addend |
|---|---|
| 4h | +0.10 |
| 1d | +0.15 |
| 1w | +0.20 |

> **v0.2.1 (council 2026-07-17) — addends ZEROED** (`{1h: 0, 4h: 0, 1d: 0,
> 1w: 0}`): Q19 is unresolved and now carries TWO load-bearing cases (the
> inverted-V of 2026-07-13 and the 2026-07-16 golden (c), where the engine
> BBWP said "no expansion" while the owner saw expansion in TradingView).
> Until Rule 2 is recalibrated on `bbwp_owner` post-Q19, the boosts carry no
> weight; the wiring still emits boost entries (`addend: 0.0`) as evidence,
> and E4.1 keeps emitting (it was never alertable). The 0.2.0 constants above
> are preserved (here and in the `VT_ROUNDED_ADDEND` comment) for that
> recalibration.

Constraints (both mandatory): it **never overrides Rule 1** (a higher-TF
`CONFIRMED` same-direction still wins — a rollover on an even higher TF does
not resurrect a false verdict against a confirmed impulse), and it **never
votes as a separate standalone condition** — it only re-weights an existing
watch/M2 score. This avoids double-counting volatility with `bbwp_regime` (E5),
which already reasons about the same BBWP series.

**Rule 3 (lowest) — local timeout only when 1–2 are silent.** The ordinary
§B.3.1 local 5-candle timeout adjudication (and the §I.1 color flip) apply
**only** when neither Rule 1 nor Rule 2 has spoken for that watch. In other
words the higher-TF hierarchy is consulted first; the local monitor is the
fallback.

**Parameters**:

| Param | Default | Notes |
|---|---|---|
| `p_false_cap` | 0.90 | ceiling after Rule-2 addends **[calibrable]** |
| `vt_rounded_addend` | `{4h:0.10, 1d:0.15, 1w:0.20}` | Rule-2 weights — **gated on Q19** (BBWP calibration) before they can be trusted |

> **Q19 prerequisite (calibration, blocks Rule 2 weights):** the engine's BBWP
> is `BB20 / lookback 252` on **Bitget** data; the owner reads TradingView
> BBWP as `BB13 / lookback 256 / MA5` on **Binance** data. The per-TF
> hierarchy weights (and the E4.1 `high_zone`/drop thresholds) are meaningless
> until the two BBWP definitions are reconciled or a mapping is measured. **Do
> not trust the Rule-2 addends, nor the E4.1 zone constants, until Q19 is
> resolved.** See §I.7.

---

### I.4 — (E4.1) `vol_turn_rounded` — rounded volatility rollover (V and W)

**Motivation**: the v0.1.0 `v_turn_high` (§E4) requires a ≥ `min_drop = 5` BBWP
drop on the **single** candle immediately after an **exact** peak. That geometry
**missed the real rounded rollovers of 2026-07-13**: BBWP `90 → 49` on 1h and
`91 → 56` on 30m rolled over gradually (a domed top), so no single
post-peak candle dropped 5 points off an exact fractal peak, yet the volatility
plainly turned over from the top. E4.1 detects the **cumulative, rounded** turn.

**Source**: `bbwp` (0–100). Both bands (like E4-on-BBWP). *(Konkorde-source
variant deferred — Konkorde stays `high_tf`, §0.3.)*

**V variant — rounded rollover from the high zone** (closed candle):

```
Over the trailing window win = bbwp[-window .. -1] (window = 8):
vol_turn_rounded_high =
      max(win) >= high_zone                          (peaked in the upper region; high_zone = 70)
  AND (max(win) - bbwp[-1]) >= min_drop_cum          (cumulative fall off that peak; min_drop_cum = 10)
  AND bbwp[-1] < bbwp[-2] < bbwp[-3]                 (last 2 closes STRICTLY falling — the turn is in progress)
Fires on the closed candle -1. ONE fire per peak (a peak already fired against
does not re-fire until a new max in a fresh window exceeds it).
```

Unlike `v_turn_high`, the drop is measured from the **window max** (not an
exact single-candle peak) and accumulated over up to `window` bars, so a domed
`90 → … → 49` top fires.

**W variant — double test of the high zone** (rounded): two zone tests within
`w_window = 12` closed candles, separated by `>= 3` bars, both `>= high_zone`,
with the second test failing to exceed the first by more than `tolerance = 5`
BBWP points (mirrors the §E4 W geometry but on the rounded/window definition).

**Parameters**:

| Param | Default | Notes |
|---|---|---|
| `window` (V) | 8 | trailing closed bars scanned for the peak **[calibrable]** |
| `high_zone` | 70 | BBWP upper region (same constant as E4) — **gated on Q19** |
| `min_drop_cum` | 10 | cumulative BBWP points off the window max **[calibrable]** — chose to catch 90→49 / 91→56 |
| `w_window` | 12 | max bars spanning the two zone tests **[calibrable]** |
| `w_separation_min` | 3 | min bars between the two tests **[calibrable]** |
| `tolerance` | 5 | BBWP points the 2nd test may exceed the 1st **[calibrable]** |

**Semantics**: same as E4 — **exhaustion / rollover evidence** on the TF, used
for invalidation, no-new-entries, and (on TF ≥ 4h) the H1 Rule-2 `p_false`
boost (§I.3). **Never an entry trigger.**

**Golden cases** (defaults above):

**VT-G1 — rounded dome rollover → fires**

```
bbwp = [60, 68, 75, 82, 88, 90, 88, 85, 81, 72]
```

* window = last 8: `[75, 82, 88, 90, 88, 85, 81, 72]`; `max = 90 >= 70` ✓.
* `max - bbwp[-1] = 90 - 72 = 18 >= 10` ✓.
* last 2 strictly falling: `72 < 81 < 85` ✓.
* → **`vol_turn_rounded_high = true`** (the shape v0.1.0's `v_turn_high`
  would have missed — no single 5-pt drop off an exact peak).

**VT-G2 — last candle rising → no fire**

```
bbwp = [60, 68, 75, 82, 88, 90, 88, 85, 81, 84]
```

* Same domed peak, but the final close rises `81 → 84`, so
  `bbwp[-1] < bbwp[-2]` fails (the strict-falling last-2 condition breaks) →
  **`vol_turn_rounded_high = false`**. The turn is not yet in progress.

---

### I.5 — (B.4) SETUP `C1` — 3-TF full-alignment confluence ("5/5")

**Owner's words (2026-07-13)**: when the operative timeframes stack in the same
direction it is a full alignment ("5/5"); and the contrary-confluence read is
**the** way to know when to get out ("**es la forma de identificar cuando
salirse**"). C1 is one detector with two uses: ENTRY and — primarily — EXIT.

**Per-TF alignment score** (direction `d ∈ {bull, bear}`; closed candles;
respects the §0.3 band ban on Konkorde below 4h):

* **Low band (30m, 1h) — 3/3**:
  1. `ao_sign = d` (AO positive for bull, negative for bear).
  2. **ADX component** — favorable E1 turn fresh (`adx_turn` grade A/B in
     direction `d`, `event_age <= 5`) **OR** ADX rising with `di_color = d`
     (strength building, §I.1 color).
  3. **BBWP expansion** — `bbwp[-1] > 50` (E5 regime) **OR** BBWP rising 2
     closed candles.
* **High band (4h, 1d, 1w) — 4/4**: the three above **+** `sign(konkorde_marron) = d`
  (E3 state; permitted on `high_tf` only).

A TF is **aligned for `d`** when it scores full (3/3 low, 4/4 high). C1 fires
when a defined **3-TF window** is fully aligned for the same `d`:

| 3-TF window | Fires for | Annotation |
|---|---|---|
| `{30m, 1h, 4h}` | ENTRY, **Snipper / Pro** profiles | "1d likely in retracement" |
| `{4h, 1d, 1w}` | **Ancient** profile | "1w in retracement" |
| `{1h, 4h, 1d}` | **Q18 — owner decision, default OFF** | — |

**Two uses, one detector:**

* **ENTRY** — when there is **no opposing open trade**, a full-alignment window
  for `d` is an entry-grade confluence for the window's profile(s).
* **EXIT (the PRIMARY exit mechanism of the strategy)** — when an OPEN journal
  trade's side **opposes** the confluence direction, C1 emits a **priority-5**
  call: **`"SALIDA por confluencia contraria"`**. This is the owner's designated
  way to identify exits — it is *not* a stop. **SL / TP remain protection-only**
  (disaster floor / target), while contrary-confluence is the discretionary
  exit signal. Exit use has priority over entry use on the same evaluation.

> **v0.2.1 (council 2026-07-17) — ENTRY-CALL OFF, EXIT DEGRADED TO EVIDENCE.**
> Every emitted confluence entry now carries **`evidence_only: true`**; the
> block keeps computing (forward evidence collection for the pre-registered
> v0.3.0 C1-FADE hypothesis, §I.9e), but no consumer may treat it as a call
> of any grade:
>
> * **ENTRY: FAIL, unequivocal.** Forward returns are net NEGATIVE in every
>   window on the 120d replay: micro bear k5 −0.35% (pos-rate 21.6%),
>   `30m-1h-4h` bull k5 −0.65% (pos-rate **12.9%**), down to −0.95% at k20.
>   Full alignment arrives LATE — it marks exhaustion, not entry (coherent
>   with the owner's E4 / vol-turn doctrine). Also: strict simultaneity
>   misses staggered 15m→30m→1h ignitions (2026-07-16 golden (c)).
> * **EXIT (P5): NOT VALIDATED.** On the replay's hypothetical-trade
>   population, exiting on contrary confluence did not save money vs a
>   hold-20-candles baseline (mean P&L saved: high −2.12%, low −0.09%,
>   micro −0.03%). Caveats: that population is not profitable per se and has
>   no SL/TP — re-test against the owner's REAL journal before any P5 use.
>   **Owner sign-off is PENDING on C1's designated primary-exit role.**

**Real golden case (C1-G1)** — the case that motivated the rule:
2026-07-13 **16:00–20:00 UTC**, BTC: `30m / 1h / 4h` all **bear-aligned** while
`1d` was **retracing** (not yet bear-aligned). The `{30m,1h,4h}` window fired
bear; a long journal trade open at the time → priority-5
`"SALIDA por confluencia contraria"`, annotation "1d likely in retracement".
Backtest must reproduce the alignment on stored candles for those four TFs.

**Parameters**:

| Param | Default | Notes |
|---|---|---|
| `adx_fresh_max_age` | 5 | E1 turn freshness for the ADX component **[calibrable]** |
| `bbwp_expansion_bars` | 2 | rising-BBWP closed candles alternative to `>50` **[calibrable]** |
| `windows_enabled` | `{30m,1h,4h}`, `{4h,1d,1w}` ON; `{1h,4h,1d}` OFF | the middle window is **Q18** |
| `exit_priority` | 5 | call priority of `"SALIDA por confluencia contraria"` |

---

### I.6 — v0.2.0 VALIDATION PLAN (the F0 replay gate for §I)

Nothing in §I activates until this replay is run and passes, then `/mmk-council`
ratifies the `rule_version` 0.2.0 bump (§0.4).

**Replay matrix**: **120 days** of history × symbols **BTC / ETH / SOL / BNB** ×
the **5 operative TFs** (`30m / 1h / 4h / 1d / 1w`), run **v0.1.0 vs v0.2.0**
side by side on identical candles (immutable per §0.4).

**Required outcomes (per family × band, `n >= 30` adjudications/signals):**

1. **M1.1 color-flip** — the **false-on-real-impulse rate MUST DROP** v0.2.0 vs
   v0.1.0 (the color flip must not confirm-false moves that were actually real
   impulses; measured as `RESOLVED_LATE_CONFIRM` / adjudicated on the
   `adjudicated_color` subset vs the 0.70 timeout subset).
2. **M2 contrary-impulse** — realized **hit-rate vs the priors** `0.70`
   (`FALSE_ENTRY_PROBABLE`) and `0.80` (`FALSE_ENTRY_CONFIRMED`): the contrary
   move + AO re-cross materialized at a rate consistent with the prior it was
   adjudicated under, per trigger (a)/(b)/(c).
3. **C1 confluence** — signal **count**, **forward returns** after each fired
   window, and — in EXIT mode — the **P&L saved** (open-trade P&L at the
   `"SALIDA por confluencia contraria"` call vs holding to SL/TP).

**Method**: temporal **IS/OOS 70/30** split with **fees** modelled (§C:
0.10% taker + 0.05% slippage per side; IS-only calibration of any
**[calibrable]** param, OOS run once). `n >= 30` per **family-band** or that
row is **NO PASS** regardless of results (§C discipline).

**Gate**: on all outcomes met → **`/mmk-council`** gate; only a passing council
decision authorizes deploying `rule_version` 0.2.0. Prerequisite **Q19**
(§I.7) must be resolved before the per-TF hierarchy weights (H1 Rule 2) and the
E4.1 zone constants are trusted in the replay.

---

### I.7 — Open questions added with v0.2.0 (extend §D)

18. **C1 middle window `{1h, 4h, 1d}` (§I.5)**: enable this third
    full-alignment window, or keep it OFF? It straddles Snipper/Pro/Ancient
    (a cross-profile confluence) — owner decision. Provisional: **OFF** until
    the replay shows it adds non-redundant signals over the two enabled windows.
19. **BBWP calibration engine vs TradingView (blocks §I.3 Rule 2, §I.4 zones)**:
    the engine computes BBWP as **BB20 / lookback 252** on **Bitget** data; the
    owner reads TradingView **BB13 / lookback 256 / MA5** on **Binance** data.
    Reconcile the two definitions (or measure a mapping) before the per-TF
    hierarchy weights (`+0.10/+0.15/+0.20`, cap 0.90) and the E4.1
    `high_zone = 70` / `min_drop_cum = 10` constants can be trusted. **This is a
    prerequisite of the §I.6 replay.**

---

### I.8 — Implementation notes (2026-07-16, backend)

**Gate mechanics.** `RULE_VERSION` env (default `0.1.0`) or the additive
`rule_version` query param select the pack per evaluation;
`SetupEvaluationService` rejects unknown versions (400). Under `0.2.0` or
`0.2.1` (same code, §I.9a) the top-level `rule_version` echoes the requested
label and `monitors` gains the blocks
`false_ignition_watch`, `contrary_impulse`, `confluence` and
`vol_turn_rounded`; `false_entry_watch` entries gain `color_flip_age`,
`p_false_boosts`, `higher_tf` and `ignition_from_below`. The `setups` block
(the 0.1.0 documents) is identical under both versions. The v0.1.0 monitor
path is untouched code.

**Module map.** Pure detectors/state machines:
`src/controllers/metrics/rule_v020.py` (M1.1 `false_entry_state_v2`, E4.1
`v/w_turn_rounded_high`, H1 `higher_confirmed_source`/`p_false_boosts`, M2
`contrary_impulse`, M1m `false_ignition_state`, C1
`confluence_alignment`/`evaluate_confluence`). Additive assembly:
`src/controllers/metrics/monitors_v020.py` (`build_monitors_v020`). Goldens:
`tests/test_rule_v020_golden.py`, assembly/H1:
`tests/test_monitors_v020_assembly.py`, HTTP contract:
`tests/test_evaluate_v020_endpoint.py`, no-regression:
`tests/test_v010_no_regression.py`, real-candle goldens (2026-07-13, Bitget
fixtures): `tests/test_v020_real_goldens.py` + `tests/fixtures/`.

**Ambiguities resolved by the implementation** (all revisitable at the gate):

1. **H1 Rule 1 walks the whole ladder above** the watch (nearest confirming
   TF wins, recorded in `higher_tf.source_tf`), subsuming the one-band-up
   wording and the addendum's "30m OR 1h" for 15m. Required by the real
   2026-07-13 golden: 30m AND 1h must both resolve `CONFIRMED_BY_HIGHER_TF`
   off the 4h even though the 1h itself adjudicated false.
2. **M1.1 race semantics**: an AO re-cross BEFORE the flip adjudication age
   is a `WHIPSAW`; a re-cross AFTER a flip adjudication is the fulfilled
   contrary prediction (state stays `FALSE_ENTRY_CONFIRMED`). Tie on the
   same candle -> `WHIPSAW`.
3. **H1 Rule 2 "move direction"** of the rollover TF = the §I.1 `di_color`
   of its last closed candle (tie -> no boost). A lower-TF watch "opposes
   the implied retracement" when its direction equals that move. Addends
   from multiple rollover TFs stack, capped at 0.90. Boosts also apply to
   M1m `p_false_ignition`.
4. **E4.1 W variant** (spec loose): pivot highs (strength 1, confirmed)
   stand in for the zone tests; second test may not exceed the first by more
   than `tolerance`; a trough of `min_trough_depth = 5` (inherited from §E4)
   must separate the tests; last close must be falling. V wins the variant
   label when both fire.
5. **H1-G3 anchor**: the golden was written pre-B.3.5 with an AO-anchored
   15m watch; since 15m runs M1m only, the implemented golden asserts the
   M1m timeout override (`CONFIRMED_BY_HIGHER_TF`, source 30m).
6. **M1m-G1 spec erratum**: the dictated ADX series (`..., 19.2, 21.0`)
   does NOT fire E1 with the v0.1.0 defaults (bend 1.467 < 1.5); the golden
   ships with `21.0 -> 21.5` (bend 1.633). Owner should confirm the series
   or the E1 defaults.
7. **C1 annotations** are product copy in Spanish
   (`"<tf> probablemente en retroceso"`), consistent with `RulesService`
   explanations; the engine emits confluence events with direction only —
   ENTRY vs EXIT (`"SALIDA por confluencia contraria"`, priority 5) is the
   journal owner's call (mmk-api).
8. **C1 ADX freshness** `event_age <= 5` scans ages 0..5 (window 6) —
   deliberately one candle wider than V2's `confirm_window = 5` (ages 0..4).
9. **15m/30m emission discipline** is made explicit in the payload:
   `false_ignition_watch` entries carry `shadow` (30m) and `alertable:
   false`; the F1 watcher must not push any of them (15m states are
   H1/C1/M2 inputs only).
10. **Micro-band enrichment** still uses the full `calculate_all()`
    (ENG-15M's oscillator-only enrichment is a deferred optimisation, not a
    correctness requirement).

---

### I.9 — v0.2.1 (2026-07-17, council post-replay) — P0 fix, measured priors, pre-registrations

The 120d replay (§I.6; BTC/ETH/SOL/BNB, immutable manifest, 2026-07-16) ran
three sides: **A** = v0.1.0, **B** = 0.2.0-as-shipped, **B2** = 0.2.0 with the
H1 freshness fix. The council of 2026-07-17 dictated the v0.2.1 package from
those results. Everything below is IMPLEMENTED on the same gated branch;
activation still requires the council's F1 gate.

**a) Version semantics — no code fork.** `SUPPORTED_RULE_VERSIONS = (0.1.0,
0.2.0, 0.2.1)`. The labels `0.2.0` and `0.2.1` execute the SAME corrected
module (`rule_v020.py` + `monitors_v020.py`); the API echoes back the label
the caller asked for. **`0.2.0`-as-shipped (branch `e864db2`, no freshness
bound, owner priors) is OBSOLETE**: it kills the M1 monitor (P0 below) and
must not be deployed or replayed as a reference — replay comparisons are
against **B2**, not B. The `0.2.0` label survives only so the harness can
tag A/B runs.

**b) P0 — H1 Rule-1 freshness (the fix).**
`monitors_v020._confirmed_directions` now grants Rule-1 sources through
`_fresh_confirmed` (confirm event age `<= 6` closed candles) for BOTH
branches — M1 `CONFIRMED` and M1m `CONFIRMED`. Numbers and the deferred
sticky-CBHT decision: §I.3 v0.2.1 note.

**c) Measured priors as rule data.** `p_false_color 0.80 -> 0.70` (n=243),
`p_false_prior 0.70 -> 0.40` (n=648), `p_false_ignition 0.65 -> 0.42` (n=57,
wide CI). Provenance comments live on each value in `rule_v020.py`; details
in the §I.1 v0.2.1 note. H1 Rule-2 addends are ZEROED pending Q19 (§I.3
note); M2 loses its call-grade (§I.2 note); C1 is `evidence_only` (§I.5
note; E4.1 keeps emitting as evidence — it was never alertable).

**d) PRE-REGISTERED criterion for turning the FEC/CBHT audible push ON**
(frozen 2026-07-17, BEFORE any forward data — it cannot be moved after
seeing it). The FEC (M1.1 flip) and CBHT alerts become audible only if,
after a forward-shadow period of **at least 30 days**, EITHER:

* **>= 60 forward FEC adjudications** with contrary hit-rate **>= 0.60**,
  AND metric-1 (late-confirm rate, §I.6.1) of the FEC subset **strictly
  below** the FEP subset's, AND pooled metric-1 **<= 12.6%** (the A-side
  baseline of the 120d replay); OR
* **p < 0.05** on the combined replay + forward test of the same hypotheses.

A **re-council is MANDATORY** to flip the switch even when the criterion is
met. If ANY leg fails at the end of the shadow period: **revert the priors**
to the pre-0.2.1 values (0.80 / 0.70 / 0.65) **and re-council** — the
measured priors are only as good as the forward data that confirms them.

**e) C1-FADE — pre-registered CANDIDATE for v0.3.0, definition FROZEN
2026-07-17.** Hypothesis: **fade the 5/5** — take the CONTRARY side of a
fully-aligned C1 window (full alignment marks exhaustion, §I.5 v0.2.1 note).
Evidence that SUGGESTED it (usable only as motivation, NEVER as validation):
replay pos-rates 12.9–33% and net magnitudes −0.65% / −0.95% on the aligned
side. Testable ONLY on a re-instrumented alignment computed with
`bbwp_owner` (post-Q19) plus its own forward window and its own §I.6-style
gate; it can never be activated from the sample that suggested it.

**f) Regression net shipped with the fix** (the tests the P0 lacked):
staleness negatives (a stale M1/M1m CONFIRMED must NOT rescue —
`tests/test_monitors_v020_assembly.py`) and an aggregate replay-smoke on
frozen fixtures (`tests/test_v020_replay_smoke.py`, 5-TF ladder including
the adversarial 1w) asserting FALSE adjudications `> 0` and CBHT a minority
of terminals — the invariant pair the shipped bug violates (verified
red/green against the buggy body while building it).

---

## ADDENDUM v0.2.0-b — Sub-1h band: polishing the 1h profile (owner, 2026-07-14)

Owner verbatim: "La idea es PULIR EL DE 1HR — necesitas temporalidades mas bajas."
+ precision: "Ahi la estrategia yo haria MAS GIROS DE VOLATILIDAD (BBWP) y tambien
GIROS DE ADX, porque el AO PUEDE TARDAR."

### 0.3.1 — Band table extension: `micro` band (15m/30m)
| Band | TFs | Component mix |
|---|---|---|
| micro (NEW) | 15m, 30m | ADX turns (E1) + BBWP turns/expansion (E4.1) carry the weight; AO = late confirmation, NEVER a requirement. Konkorde: not evaluable (unchanged, <4h rule) |
| low | 1h | unchanged: BBWP + AO + ADX, all required (operated TF — the entry needs AO) |
| high | 4h/1d/1w | unchanged |

Within-TF validity weights (alignment.py), micro band only: ADX 45 / VOL 40 / AO 15
(vs 60/40 ADX/AO elsewhere). TF weight for 15m = 5 (ladder: 1w 30 / 1d 25 / 4h 20 /
1h 15 / 30m 10 / 15m 5; renormalization rule unchanged).

TF selection decision: 15m IN (exact fit with */15 watcher cadence — 15m candles
close ON every tick; completes the mirror 15m->30m->1h; warmup fits FETCH_LIMIT=500).
5m OUT/parked (scalping territory — SCALP-5M stays a separate parked family with its
own fees gate; AO(34) on 5m spans 2.8h = permanent whipsaw; */15 cadence would
evaluate 2 of 3 5m candles late; extra ccxt pressure on the P0 cache path). Operative
set becomes 6 TFs: 15m/30m/1h/4h/1d/1w. 15m is NOT a new profile — Snipper
sub-structure. Emission discipline: 15m M1 states are H1/C1/M2 INPUTS only — the F1
watcher does NOT persist M1-FE alert docs for 15m and never pushes them.

### B.3.3 (extension) — H1 ladder below 1h
Ladder extends downward 15m->30m->1h(->4h), same precedence: (1) M1/M1m CONFIRMED on
30m OR 1h same direction -> a 15m watch must NOT adjudicate false by timeout -> state
CONFIRMED_BY_HIGHER_TF. (2) vol_turn_rounded on 1h implies retracement of the 1h move
-> p_false += 0.05 on 15m/30m watches only that oppose it (4h +0.10 / 1d +0.15 /
1w +0.20 rows unchanged). Never overrides rule 1. M2 ladder trigger (b) extends:
contrary CONFIRMED on same TF or one band up = 15m -> 30m. Downward ignition flag:
a 1h watch in WATCHING with BOTH 15m and 30m M1 CONFIRMED same direction (fresh,
terminal age <= 6) gains `ignition_from_below: true` in payload — flag only, does NOT
auto-confirm the 1h; replay (Q21) decides any upgrade.

**Golden H1-G3 — 15m timeout suppressed by 30m confirmation**:
15m: ao = [-0.4, 0.5, 0.8, 1.0, 1.2, 1.4, 1.5] (cross idx1, age 5 at last), adx14
slope 0.1 (no turn; series len >= 9), plus_di > minus_di. 30m (same last close):
state CONFIRMED, adx_turn {age 1, grade A}, dir up. -> 15m state =
CONFIRMED_BY_HIGHER_TF (NOT FALSE_ENTRY_PROBABLE), source_tf=30m.

### B.3.5 — M1m: ADX-anchored false-ignition monitor (micro band)
Rationale: in 15m/30m the AO arrives late, so the AO zero-cross is the wrong watch
anchor — t0 moves to the E1 ADX turn. The watch inverts M1's question: strength
ignited — does the move get body behind it?
* t0 = adx_turn_up_<dir> fire (grade A or B) on a closed candle.
* CONFIRMED: within m1m_confirm_candles closed candles after t0, AO crosses zero in
  dir OR (bbwp rising >= 3 consecutive closes AND DI color = dir throughout).
* FALSE_IGNITION_PROBABLE (terminal): window elapses with neither ->
  p_false_ignition = 0.65 [analyst provisional; calibrable Q21].
* WHIPSAW: opposite E1 turn (or DI color flip against dir) before adjudication.
* M2 unchanged: FALSE_IGNITION feeds the same contrary orientation (k_contrary=5,
  ladder rule (b) included).

Anchors per TF: 15m -> AO-anchored M1 OFF / M1m ON. 30m -> M1 ON (unchanged) / M1m
SHADOW (computed + logged, never alerted). >=1h -> M1 ON / M1m OFF. The replay
compares false-adjudication rates of both anchors on 30m; v0.3.0 decides which owns
30m. Timeouts: AO-anchored confirm_candles=5 stays on 30m/1h; m1m_confirm_candles=8
on 15m (=2h wall-clock; 5x15m=75min too short for AO follow-through) and 6 on
30m-shadow [calibrable 6-12]. H1 ladder, not longer timeouts, protects slow ignitions.

**Golden M1m-G1 — ignition confirmed** (evaluate at last candle):
adx14 = [15.8, 15.9, 16.0, 16.1, 16.2, 16.3, 17.5, 19.2, 21.0] (plus_di > minus_di);
ao = [-1.2, -1.0, -0.8, -0.5, -0.2, 0.3]. E1 up_bullish fires at adx idx 8 (slope
1.75, base 0.1, delta 1.65, origin 16.3 -> grade A); AO crosses up 5 closed candles
later (5 <= 8). -> state = CONFIRMED, ao_followed = true, follow_age = 5.
**Golden M1m-G2 — ignition without body**: same adx14;
ao = [-1.2, -1.1, -1.15, -1.1, -1.12, -1.1, -1.13, -1.1, -1.12] (never crosses);
bbwp = [31, 30, 31, 30, 31, 30, 31, 30, 31] (never 3 rising). At t0+8:
FALSE_IGNITION_PROBABLE, p_false_ignition = 0.65.

### B.4.1 — C1 micro window {15m, 30m, 1h} -> Snipper entry
* Micro-TF alignment(d) (15m/30m): adx_component(d) AND bbwp_expansion both
  MANDATORY; ao_component(d) is a BONUS (adds its 15% to validity, never gates).
* 1h alignment(d): full 3/3 including AO (unchanged — operated TF needs entry-grade).
* Fire: 15m aligned + 30m aligned + 1h full, same d, same run -> SNIPPER entry call
  + annotation "4h probablemente en retroceso"; if 4h AO carries same sign, tag
  companion_ok and raise validity. EXIT use inherited from B.4 (confluence against an
  open trade = primary exit; SL/TP remain protection).
* Consolidation: overlaps IMPULSE_WINDOWS SNIPPER (30m+1h confirmed + 4h AO) — both
  run during calibration; dedup max one Snipper entry call per symbol+direction per
  1h candle (finer window wins; coarser absorbed as escalation evidence). Q20: does
  the owner want {30m,1h,4h} as an additional PRO-polish window? Default OFF.

**Golden C1micro-G1**: 15m: E1 turn fresh (age 2) + bbwp 58 rising, ao -0.2 (bonus
missing) -> aligned (2/2 mandatory, score 85/100). 30m: adx rising + DI color d +
bbwp 61>50 + ao +0.1 bonus -> aligned 100. 1h: 3/3 full. -> C1-SNIPPER fires dir d.

### ENG-15M — engineering notes + gate impact
1. `_M1_OPERATIVE_TFS` += "15m" (setup_evaluation_service.py); verify
   setup_service.TIMEFRAME_SECONDS has "15m". FETCH_LIMIT=500 sufficient.
2. Monitor-only TFs (15m/30m/1h) only need calculate_oscillators()+bbwp (no
   Konkorde/MFI) — cheaper enrichment.
3. Per-band params live in this rule document (versioned data, not env vars).
4. PRECONDITION dura: the P0 TTLCache fix (market_data_service.py:90-104) lands
   BEFORE or WITH 15m — otherwise the micro band inherits hours-stale candles and
   this addendum is dead on arrival. Post-fix TTL for 15m = 7.5 min.
5. Notification: 15m NEVER pushes (micro band = journal/brain/alerts collection
   only). mmk-api indicators_client._SPAN_BY_TF: add "15m": "2d".
6. Replay/gate: matrix 120d x {BTC,ETH,SOL,BNB} x 6 TFs (15m history MUST paginate —
   use the F0 backtest fetcher path, never legacy E13); stratified outputs: 15m
   adjudication accuracy, confirm_candles sweep {5,6,8} on 15m/30m (Q21), C1-micro
   vs IMPULSE_WINDOWS overlap/precision, simulated 15m alert volume/day, one-off 5m
   exploratory replay (offline) to close the 5m question with data. Same gate rules
   (n>=30 per band-family, IS/OOS 70/30, fees); ships in the SAME rule_version 0.2.0.

### Open questions (owner)
* Q20: additional PRO-polish window {30m,1h,4h}? (default OFF)
* Q21: owner prior for p_false_ignition (0.65 provisional) + confirm_candles per-TF
* Q22: confirm 15m never pushes even with an open trade (current spec: input-only)

---

## J. CANDIDATES — 2026-07-16 (TV-parity port; NOT implemented as rules)

Status: **CANDIDATE** — nothing in this section is wired into `setups`,
monitors or alerts. It records (a) a rule dictated by the owner pending his
answers, (b) a new indicator component now available to the engine, and
(c) a quantified cost golden. Implementing any of it is a `rule_version`
bump gated by its own replay.

### J.0 Context — TV-parity indicators landed (2026-07-16)

The owner delivered the Pine sources of the 3 indicators on his chart. The
engine now computes, per candle and exposed on `/v1/metrics` +
`/v1/charts` (additive fields, comparison-only):

* `bbwp_owner` / `bbwp_owner_ma5` — exact port of The_Caretaker's `f_bbwp`
  with the owner's settings (basis SMA 13, lookback 256, SMA 5; extremes
  98/2). **This closes the Q19 calibration prerequisite mechanically**: the
  engine's legacy `bbwp` (basis 20/2 bands, pct-rank including the current
  bar, min_periods=1 over 252) is a materially different series — on real
  BTC/USDT candles (2026-07-16): 4h last closed candle engine 65.1 vs owner
  20.3 (|gap| 44.8; mean |gap| last-100 20.1, max 65.2); the owner's 4h
  "inverted V" (peak 88.3 on 15-jul 12:00 UTC → 4.3 on 16-jul 12:00 UTC)
  simply does not exist in the legacy series (flat 66→69 over the same
  span). Rule 2 / E4.1 constants gated on Q19 must be recalibrated against
  `bbwp_owner`, not against the legacy `bbwp` (which stays untouched for
  the recorded history and the active rules).
* `ao_diff` / `ao_color` / `ao_color_change` — the exact colour the owner
  reads: sign of `diff = ao - ao[1]`, tie paints RED (`diff <= 0`), colour
  change = cross of `diff` with 0. Engine AO itself verified bit-equal to
  the Pine built-in `sma(hl2,5) - sma(hl2,34)`. Known divergence kept as-is:
  the rules helpers `ao_rising`/`ao_falling` use strict comparisons (a flat
  AO bar is neither), and `_ao_consecutive_run_after(kind="falling")`
  breaks a run on a flat bar that the owner's chart still paints red.
* `trend_speed` (+ `tsa_*` series and wave stats) — full port of
  Zeiierman's Trend Speed Analyzer (CC BY-NC-SA 4.0, attribution in
  `src/controllers/metrics/trend_speed.py`; private repo, personal use).

Validation protocol: the owner compares the dashboard panels against his
TradingView side-by-side (visual parity = final acceptance).

### J.1 R-CONT — continuation of the short (owner, 2026-07-16, verbatim)

> "la continuación de ese corto iría si horas no pasa el ao y hay un
> cambio de adx, pero por ejemplo en este momento no ha producido"

Default interpretation (to validate with the owner before any
implementation): after the micro-band short entry (C1-micro), the
CONTINUATION is confirmed while, on the 1h timeframe, the AO does NOT
cross above zero (stays < 0) AND an ADX change fires in favour of the
short (DI dominance flip to bearish, or an E1-grade bearish turn). Pairs
with the 2026-07-14 "symmetry" reading (30m ADX turning with red DI within
<= 5 candles → bearish continuation).

Open questions (owner):

* **Q23**: "horas" = the 1h timeframe exactly, or any hourly-band TF
  (1h/2h)?
* **Q24**: "no pasa el AO" = AO does not cross above 0 (`zero_cross`), or
  the AO colour does not flip to green (`ao_color` stays red)? These are
  different events — the port now exposes both.
* **Q25**: "cambio de ADX" = DI dominance flip (minus_di > plus_di), or an
  E1 90-degree ADX slope turn (grade A/B)? Or either?

### J.2 E6 / TSA — component available for the IMP-4H redesign (PARKED)

The F0 verdict (2026-07-11) sent IMP-4H to redesign as E6. The Trend Speed
Analyzer port is the candidate raw material: adaptive trend line
(`tsa_dyn_ema`), per-wave impulse magnitude (`speed`, HMA'd as
`trend_speed`) and per-side wave statistics (avg/max wave, current-wave
ratio, dominance) — i.e. a native "impulse vs its own history" measure per
TF. PARKED until its own gate: any E6 draft must specify thresholds as
versioned data and pass the standard replay (n>=30, IS/OOS 70/30, fees)
before entering any window logic.

### J.3 Cost golden — the missed C1-micro short (owner, 2026-07-16, verbatim)

> "si hubiéramos hecho el corto estaríamos 2,47% de caída a 10x = 25% de
> lo que se tiene"

The micro-band short that mmk never alerted (C1-micro not yet deployed)
would have returned ≈ +24.7% of capital at 10x (Snipper profile): a 2.47%
drop, entry per the owner's live reading on 2026-07-16. Recorded as the
quantified opportunity cost of the C1-micro deployment delay — input for
the council gate that prioritises the v0.2.0-b micro band. This is a COST
golden (evidence for prioritisation), not a backtest golden: it does not
validate the rule by itself.
