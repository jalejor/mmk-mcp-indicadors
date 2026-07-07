# Strategy Setups Specification — Multi-TF Engine (Phase 0)

| | |
|---|---|
| **rule_version** | `0.1.0-draft` |
| **Status** | Draft for backend implementation — pending owner confirmation of [§D Open Questions](#d-open-questions-for-the-owner) |
| **Audience** | `backend` (implements `SetupService` + multi-TF backtest), reviewer: trading analyst |
| **Date** | 2026-07-06 (includes the owner's timeframe-band refinement of the same night) |
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
  "risk": { "risk_profile": "medium" } // sizing via sizing_profiles.atr_sizing_for → live/backtest parity preserved
}
```

Each condition is `{ "element": "<detector>", "variant": "...", "params": { ... } }`
referencing §A detectors, or a primitive comparison on existing series
(e.g. `close > sma200`). Evaluation: context checked at every closed trigger
candle using §0.2 alignment; trigger fires only on the candle where its logic
first becomes true while context holds; invalidation checked on every closed
trigger candle afterwards.

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
      { "element": "adx_turn", "variant": "up_bullish" },                     // E1 on 4h
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
  "risk": { "risk_profile": "medium" }
}
```

Short variants (`PB-1D-SHORT`, `IMP-4H-SHORT`) are strict mirrors of every
condition; whether they are enabled in the F0 backtest is Open Question **Q8**.

**Low-band note**: F0 ships no `low_tf` setup — both owner setups live in the
high band. The band machinery (§0.3) must ship in F0 anyway (validation +
runtime guard + B0 goldens), so that any future `low_tf` scalping rule set is
structurally limited to BBWP + AO + ADX from day one.

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
separately.

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
