# Trading Patterns Catalog — price structures the owner trades

> **Source of truth**: the LIVE, editable pattern catalog resides in **mmk-api** (`GET/PATCH /v1/patterns`, collection `patterns` in mmk-db) — that is what the owner feeds and what the journal validates tags against. This document is the **detection-engineering annex**: how each pattern maps to engine primitives and what it would take to detect it. Owner decision 2026-07-11.


| | |
|---|---|
| **catalog_version** | `0.1.0` |
| **Status** | Catalog + journal tagging. This document adds **no detector** to the engine — detectors graduate later, each behind its own `rule_version`, golden tests and F0-style backtest gate. |
| **Audience** | trading analyst (tagging discipline), `backend` (journal `pattern` field consumer, future detectors) |
| **Date** | 2026-07-11 (owner dictation, same night) |
| **Relationship to `STRATEGY_SETUPS_SPEC.md`** | The spec formalises **indicator-level elements** (E1–E7) and composite setups. This catalog names the **price-structure patterns** the owner reads on the chart. Where a pattern is already covered by an element (channels → E7, divergences → E2), this doc REFERENCES the spec and never redefines it. |

**Owner's words (verbatim, 2026-07-11)**: "me gustaría alimentar en algún
lado los principales patterns de trading que tradeamos: canal alcista,
bajista, hombro cabeza hombro también el invertido, divergencias,
convergencias".

## 0. Operating principle — patterns × impulse (owner, 2026-07-11 late)

**Owner's words (verbatim)**: "todos los patterns son cruzados con el
análisis de impulso — SOLO OPERAMOS IMPULSOS. Retrocesos es para saber, en
tendencia de semanal o 4hrs 1hr, salida de movimiento y cambio de
perspectiva para esperar el nuevo impulso."

This is the keystone that subordinates every section below:

1. **Patterns never trade alone.** A pattern (channel, H&S, divergence) is
   CONTEXT/quality — the only tradeable event is the **impulse** (E1
   `adx_turn` ignition confirmed with AO, the engine's trigger family).
   Every "Confluences" block in this catalog reads in that direction:
   pattern × impulse, never pattern → entry.
2. **Retracements are NEVER entries.** A retracement serves exactly three
   purposes: (a) locate position within the 1w / 4h / 1h trend; (b) signal
   **movement exit** — this is the §F guardian-ladder read (guardian TF
   retracement = leave); (c) **perspective reset**: after the exit, stand
   aside and WAIT for the next impulse (the M1 §B.3.1 watch state is the
   formalisation of that waiting).
3. Note for PB-1D naming: the "pullback" setup does NOT trade the pullback —
   it waits through the retracement and triggers on the **impulse being
   born at its end** (the E1 turn). Same doctrine, consistent.

---

**How to read each entry**: owner doctrine → proposed operable definition
(pivot-based, params **[calibrable]**) → applicable TFs → what it emits
(journal tag TODAY, detector candidate LATER) → confluences with E1–E7 →
detection risks. Shared primitive for everything pivot-based:
`fractal_pivots(series, strength, kind)`
(`src/controllers/metrics/setup_service.py:225`) — strict fractal min/max of
the `i−strength..i+strength` window, only **confirmed** `strength` closed
bars later, so nothing here repaints.

---

## 1. Canal alcista — `bull_channel`

**Owner doctrine**: hand-drawn channels ARE respected (verified live on BTC —
spec §E7 and its two addenda). Inside a bull channel: trade the bounces —
long at the floor while the channel holds; the ceiling is take-profit /
rejection territory. The BREAK of the channel is itself an event: it
projects a measured move ("saldo mínimo", spec E7 addendum — first objective
= channel width, full objective = traveled span).

**Owner addendum (2026-07-11 late) — the points ARE the pattern**: "los
puntos son lo importante: un canal alcista son puntos mínimos más seguido
con puntos de máximos menores, y con un impulso lo más cerca del canal, va
a la dirección del impulso."

* **Pivots are first-class**: the channel IS its touch points — validation
  reasons over pivots, not over the drawn lines.
* **Touch asymmetry** [interpretation]: in a bull channel the FLOOR
  (minimums) prints touches more often/consecutively than the ceiling
  ("máximos menores" read as FEWER ceiling touches — price rides the demand
  line). Alternative reading ("lower highs") would describe a wedge, not a
  channel — flagged under OQ1. Provisional expectation: floor touches ≥
  ceiling touches, exact ratio **[calibrable]**.
* **Entry rule**: when an impulse is born **nearest the channel line**, it
  goes in the direction of that impulse — proximity-to-line at impulse
  ignition is a QUALITY dimension (the further from the line the impulse
  starts, the worse the entry) **[calibrable: distance as ATR-fraction]**.
  This composes §0 (impulse is the trigger) with E1-at-the-touch and the M1
  false-bounce guard.

**Operable definition** (this is spec **§E7 CANDIDATE** — referenced, not
duplicated): fractal pivots (strength 2, closed bars) → linear regression
over pivot highs and over pivot lows → near-parallel lines (slope tolerance
**[calibrable]**) with `respect_count` = touches within an ATR-fraction
tolerance. Channel is VALID with ≥ 3 respected touches; ascending = both
regression slopes > 0. Additional channel attributes (`traveled_span`,
`width`, `break_direction`, `measured_targets[]`) are specified in the E7
addenda.

**TFs**: all operative TFs (`1h/4h/1d/1w`, spec §H) — channels nest
fractally (E7 addendum 2): you operate YOUR trade's TF channel, exit by the
guardian TF (§F ladder), and the MACRO channel caps direction conviction and
size.

**Emits**:
* **TODAY** — journal tag `bull_channel` (manual, at trade entry; see
  [Journal tagging](#journal-tagging)).
* **LATER** — detector = the E7 implementation itself, parked post-F0;
  low-TF leveraged channel scalps are backtest **variant D** (spec §E7) with
  its own gate. Nothing enters the engine via this catalog.

**Confluences (quality, never the trigger by itself)**:
* **E1**: `adx_turn_up_bullish` firing at/after the floor touch — the turn
  marks the bounce igniting (A-grade origin per §E refinement is the best
  read).
* **E2**: bullish AO divergence into the floor touch = reversal evidence at
  structure (this is PB-1D's own evidence pattern landing on a channel line).
* **E5**: BBWP low-zone ignition (`v_turn_low`/`w_turn_low`, E5 addendum
  2026-07-11) at the floor = expansion starting from compression.
* **M1 (§B.3.1)**: an entry off the floor whose AO cross sits in
  `FALSE_ENTRY_PROBABLE` is exactly the false bounce — do not take it.
* **E7 measured move**: on the break, targets project per the addendum;
  confluence when they land on the macro channel's opposite boundary.

**Detection risks**: channel fitting has many degrees of freedom (which
pivots enter the regression, tolerance width, lookback) — easy to "find" a
channel in noise; parallel-ness is rarely exact; a channel can be redrawn
wider after a fake break (hindsight bias). Mitigations when the detector
lands: confirmed pivots only, fixed lookback per TF, ≥ 3 touches hard
requirement, and manual journal tags as the labelled dataset to validate
against.

---

## 2. Canal bajista — `bear_channel`

Strict geometric mirror of `bull_channel` (both regression slopes < 0; trade
shorts off the ceiling while it holds; floor = cover/TP territory). Same
primitives, same params, same risks — everything in §1 applies mirrored,
including the 2026-07-11 points addendum (touch asymmetry on the CEILING;
impulse born nearest the ceiling goes in the impulse's direction).

**Owner-specific doctrine** (spec E7 addendum + addendum 2, from the live
BTC 15m case): a **counter-trend ascending channel INSIDE a bearish macro
channel** typically resolves with a DOWNSIDE break — trade it long while it
holds, but EXPECT the break in the macro's direction; after the break, price
tends to chop between the broken line (now resistance) and the next
structure (inter-channel transition zone = low-quality entries, expect
whipsaw). Hierarchy flips only when price breaks the macro boundary itself
(daily close beyond = regime change).

**Emits**: journal tag `bear_channel` today; detector = E7, same path as §1.

**Confluences**: mirrors of §1 (E1 `adx_turn_up_bearish` at the ceiling
touch, E2 bearish AO divergence into the ceiling, E5 ignition turns, M1 on
down-crosses). Konkorde state (`marron < 0`) as context on `high_tf` only
(§0.3 band rules).

---

## 3. Hombro-cabeza-hombro — `hs`

**Owner doctrine**: head-and-shoulders = reversal pattern after an uptrend;
the owner trades it as a top formation (dictation 2026-07-11 lists it among
the main patterns; no numeric parameters were dictated — everything below is
the analyst's proposed operationalisation, to confirm).

**Operable definition (proposed, all [calibrable])** — pivot geometry on the
trade TF, built on `fractal_pivots` (`setup_service.py:225`):

```
1. Prior trend: an UPTREND into the pattern is REQUIRED
   (e.g. close > sma50 and sma50 rising at the left shoulder) — without it,
   "three bumps" is not a reversal pattern.
2. Three consecutive CONFIRMED pivot highs P_L < P_H < P_R (indexes) with:
     high[P_H] > high[P_L]  AND  high[P_H] > high[P_R]      (head above both shoulders)
     |high[P_L] − high[P_R]| <= shoulder_tolerance          (shoulder symmetry)
3. Neckline = line through the two intervening CONFIRMED pivot lows T1, T2
   (T1 between P_L and P_H; T2 between P_H and P_R);
   neckline slope within neckline_slope_tol.
4. The pattern COMPLETES only on a closed candle BELOW the neckline
   (before that it is a "potential H&S", not an event — no signal value).
5. Measured target = neckline break level − (high[P_H] − neckline at P_H)
   (the head-to-neckline height projected down; same measured-move family
   as E7).
```

| Param | Provisional | Notes |
|---|---|---|
| `pivot_strength` | 3 | wider than E2's 2 — shoulders/head are larger structures **[calibrable]** |
| `shoulder_tolerance` | 25% of head-to-neckline height | symmetry bound **[calibrable]** — needs owner chart examples |
| `pattern_width` | 15–60 closed bars (P_L → P_R) | too narrow = noise, too wide = unrelated highs **[calibrable]** |
| `neckline_slope_tol` | ±0.15 × ATR14 per bar | near-horizontal neckline **[calibrable]** |

**Volume condition (Konkorde, `high_tf` only per §0.3)**: the classic H&S
volume signature — participation fades as the pattern completes — maps to
mmk's volume reading: Konkorde volume curves stretched at the **high mean
with a V/W turn around the head** (exactly the termination doctrine of the
E3/E4 addendum 2026-07-11), and weaker volume on the right shoulder than on
the left. On `low_tf` (1h) Konkorde is banned, so any volume condition there
is out — geometry only.

**TFs**: provisionally **4h and up** (see OQ2). The pattern needs room; on
1h it degrades to noise quickly and loses the Konkorde volume leg.

**Emits**:
* **TODAY** — journal tag `hs` (manual). Tag on the NECKLINE BREAK, not on
  the visual "it looks like a head is forming".
* **LATER** — detector candidate, **explicitly last in line**: catalog +
  manual tagging FIRST, detector only after the manual tags provide a
  labelled set to validate against, with its own goldens and gate.

**Confluences**: E2 bearish AO divergence between P_L/P_H (price higher high
at the head, AO lower high — the classic head signature and already an
implemented detector); E1 inverted-V (`adx_turn_down`, E1 addendum
2026-07-11 = "terminación") around the head; E3/E4 Konkorde high-mean turn;
M1: the neckline-break entry usually rides an AO down-cross — if M1
adjudicates it `FALSE_ENTRY_PROBABLE`, the break is suspect; E7: a neckline
is a structure line — breaks and measured targets follow the same rules.

**Detection risks — honest state of the art**: algorithmic H&S detection is
**notoriously false-positive-prone**. Pivot combinatorics produce endless
"three bumps"; symmetry/width tolerances are subjective; the prior-trend
requirement is essential and often omitted; academic evidence on H&S
profitability is mixed at best. This is WHY the status is catalog-first:
manual tags are cheap, reversible and build the evaluation dataset; a
premature detector would flood the watcher with junk alerts and poison the
journal.

---

## 4. HCH invertido — `hs_inverted`

Strict mirror of §3: DOWNTREND into the pattern required; three confirmed
pivot LOWS with the head below both shoulders; neckline through the two
intervening pivot highs; completes only on a closed candle ABOVE the
neckline; measured target = break level + head-to-neckline height. Signals
**bullish reversal**. Same params, same TF floor, same risks as §3.

Mirrored confluences: E2 bullish AO divergence at the head (PB-1D's own
reversal evidence), E1 V-turn (`adx_turn_up_bullish`, ideally A-grade origin
— strength reborn from a low), Konkorde volume: high-mean-turn doctrine
applies to the selling volume fading; on the break, `konkorde_zero_cross_up`
(E3) is natural confirmation on `high_tf`. M1 guards the break's AO
up-cross.

**Emits**: journal tag `hs_inverted` today (on neckline break); detector
same catalog-first path as §3.

---

## 5. Divergencias — `divergence`

**Already formalised — do NOT redefine.** The owner's divergences are spec
**§A E2** (`ao_divergence_bullish/bearish`): AO pivots as anchors, price
compared at the same bars, confirmation-delayed fractal pivots, TTL and
invalidation rules, golden cases E2-G1..G3. E2 is **implemented** in the F0
engine (`setup_service.py`) and already serves as PB-1D reversal evidence.

**Relation to the "visual price divergence" the owner sees on the chart**:
what the eye reads as "price makes a new extreme but the move is weaker" is
formalised from the OSCILLATOR side — the AO panel not confirming the price
extreme. Same phenomenon, one canonical definition: **a journal-tagged
`divergence` means an AO-vs-price divergence in E2's terms** (anchored at
AO pivots). Divergences read against other oscillators (RSI etc.) are NOT
formalised; if one is traded, tag `divergence` and note the oscillator in
the journal free-text — if that becomes frequent, extending E2 to other
sources is a `rule_version` decision, not an ad-hoc read.

**TFs**: both bands (E2). **Emits**: journal tag `divergence`; detector
ALREADY LIVE (the only pattern in this catalog with a shipped detector).
**Confluences**: divergence at a channel line (§1/§2) or at an H&S head
(§3/§4) is the highest-quality read — structure + oscillator agreeing.

---

## 6. Convergencias — `convergence`

Also **E2** (`ao_convergence_bullish/bearish` + the cheap per-candle
`ao_rising`/`ao_falling`): momentum CONFIRMS the move — price higher high
with AO higher high (mirror for bearish). Per the spec: **confirmation only,
never a standalone trigger** (IMP-4H uses the cheap variant in its trigger
logic as one condition among several).

**Emits**: journal tag `convergence` — expected mostly as a SECONDARY note
on trades whose primary pattern is something else (a channel bounce
confirmed by convergence). **TFs**: both bands.

---

## Summary — pattern → status

| Pattern | Slug | Status | Primitives today | Detector path |
|---|---|---|---|---|
| Bull channel | `bull_channel` | cataloged, **partial primitive** | `fractal_pivots` :225; E7 fully spec'd (candidate, parked post-F0) | E7 implementation + gate; variant D for low-TF scalps |
| Bear channel | `bear_channel` | cataloged, **partial primitive** | same as above + macro-hierarchy doctrine (E7 addendum 2) | same as above |
| Head & shoulders | `hs` | **cataloged only** | `fractal_pivots` as base; no geometry code | manual tags first → labelled set → detector behind own gate (LAST in line) |
| Inverted H&S | `hs_inverted` | **cataloged only** | same | same |
| Divergence | `divergence` | **formalised + implemented** (spec E2) | `ao_divergence_*` live in F0 engine | shipped; already PB-1D evidence |
| Convergence | `convergence` | **formalised + implemented** (spec E2) | `ao_convergence_*`, `ao_rising/ao_falling` | shipped; confirmation-only by doctrine |

---

## Journal tagging

Canonical slugs for the `pattern` field of the trade journal (mmk-api):

```
bull_channel | bear_channel | hs | hs_inverted | divergence | convergence | none
```

Rules:

1. **One primary pattern per trade** (the structure that motivated the
   entry); additional reads go in the journal's free-text note (see OQ3 for
   multi-tag). `none` is explicit and mandatory when no pattern was read —
   an empty field is not `none`.
2. Slugs are **lowercase snake_case, closed vocabulary**: adding/renaming a
   slug bumps `catalog_version` (same discipline as `rule_version` — tags
   are versioned data, journal entries record the catalog version they were
   tagged under).
3. Tag at ENTRY time with what you saw THEN (no hindsight retagging; a
   correction is a new annotation, never an overwrite — same immutability
   rule as backtest results).
4. **Why this matters**: manual tags are the labelled dataset that future
   detectors (channels, H&S) will be validated against, and the journal
   dimension that lets the backtest/paper review answer "which patterns
   actually pay?" per pattern × TF × profile (§H).

---

## Open questions (owner)

1. **OQ1 — channel validity** (PARTIALLY ANSWERED 2026-07-11 late: the
   POINTS are what matters, and asymmetric touch distribution is EXPECTED —
   more floor touches in a bull channel). Remaining to quantify: minimum
   touches per line for validity (e.g. ≥ 2 on the traded line + ≥ 1
   opposite?), the asymmetry ratio, and whether "máximos menores" means
   fewer ceiling touches (provisional reading) or shrinking highs (would be
   a wedge — different pattern).
2. **OQ2 — H&S timeframe floor**: catalog proposes H&S / inverted H&S on
   **4h and up only** (structure size + the Konkorde volume leg is banned
   below 4h per §0.3). Confirm, or should Snipper (1h, §H) also tag/trade
   them geometry-only?
3. **OQ3 — journal cardinality**: one primary `pattern` slug per trade
   (current rule) or multi-tag (e.g. `bull_channel` + `divergence` at the
   floor)? Proposal: keep single primary + free-text until the journal has
   ~30 tagged trades, then decide with data.
