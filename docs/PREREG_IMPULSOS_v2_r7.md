# PRE-REGISTRATION — Impulsos v2 round 7: multi-asset REPLICATION of the frozen `impulse-2.3.0` chain (no new rule)

**Status: FROZEN. Committed BEFORE the first round-7 run.** Sections 1–9 may not
be edited after the first round-7 number exists; later edits are limited to §10
(result commit) and dated `AMENDMENT` blocks. Git order is the audit trail
(same pattern as `PREREG_IMPULSOS_v2_r2.md`, `_r4.md`, `_r5.md`, `_r6.md`).

* Date frozen: 2026-11-01 (after the round-6 result commit `b02a907`).
* Owner decision of 2026-11-01 that binds this round (`docs/board.md` #26): **the
  strategy is for ANY asset where it applies, not only BTC.** Goal: bring n above
  30 per cell and see whether any ENTRY has a replicable edge — or show it does not.
* Engine under test: `impulse_sequential.SequentialMachine` with
  `r5_params(profile, entry_filter)` (`impulse-2.3.0`), ledger
  `impulse_backtest.PositionLedger`, harness `scripts/run_impulse_backtest_r7.py`,
  statistics `controllers/metrics/impulse_multi.py`, tests `tests/test_impulse_r7.py`.
  **No new rule, no new parameter**: every run is the 2.3.0 chain on another asset.
* Code state at freeze: E3 re-specified (`46a2d7d` + `6a263a9`, legacy packs v0.1.1 /
  v0.2.2 read `konkorde_verde`). It does not touch the impulse machine (which reads
  `konkorde_verde` since 2.1.0, `607f34f`); the BTC continuity check in §6 D is what
  proves it (BTC cells must reproduce round 6 trade for trade).
* Scope: **backtest only**. Nothing here produces an order, a deploy, a push, a
  Mongo write or a Telegram message. FEC/FEP stay archived; live containers
  `mmk-signals-*` untouched; no exchange keys (public OHLCV only).

---

## 1. What round 6 left open (declared before any run)

Five rounds on BTC alone: no cell GO; PRO 4h always INCONCLUSIVE (n 7–14); SNIPPER
1h n 31–65 per side but negative or ≈ 0 expectancy; round 5 classifier on BTC:
`adx_turn` DROP (but the best filtered RUN, +19 R, n 53), `bbwp_fresh_blue` weak
KEEP (≈ 0 R vs −0.39 R rejected). Round 6: guardian ML RSI exit kept; 5x cross is
the safer snipper book; E20 — the chain as WRITTEN (trigger ML RSI gate ON) had
never been run before round 6 and must be the baseline of any next round.

**Selection caveat, declared:** the three entries of this round (`base`,
`adx_turn`, `bbwp_fresh_blue`) were CHOSEN by looking at BTC. BTC is therefore
not a replication asset. The primary family of this round is the pool of the
**8 new assets**; BTC is reported (continuity + "all 9" pool) but cannot by
itself make or break a GO.

## 2. Hypotheses

> **H7 (owner).** The 2.3.0 chain is not a BTC artefact: pooled over 8 liquid
> perps it has never seen, at least one ENTRY (`base`, `adx_turn` or
> `bbwp_fresh_blue`) on PRO 4h or SNIPPER 1h has n ≥ 30, positive OOS expectancy
> net of costs and funding, PF ≥ 1.2, no liquidation, DD < 35 %, AND the OOS
> expectancy survives the multiple-comparison correction of §6.

> **H0.** Pooling raises n above 30 (making the GO decidable for the first time)
> and shows the expectancy at ≈ 0 or negative after costs; no primary cell passes
> both legs. Per-asset cells behave like independent draws around zero (no asset
> survives BH q 0.10).

## 3. Universe (FIXED, mechanical criterion, probed 2026-11-01 ~16:45Z, public endpoints, no keys)

Criterion, written before looking at any backtest number on these assets:

1. Instruments: Bitget **USDT-M perpetuals** (`/api/v2/mix/market/tickers?productType=USDT-FUTURES`),
   ranked by **open interest in USDT** (`holdingAmount × lastPr`) — more stable than
   a Sunday's 24 h volume, which is what the owner trades (perps) and where
   liquidity matters (fills, funding, liquidation distance).
2. Eligible underlying: crypto-native (exclude tokenized stocks / commodities /
   indices and stable or gold-backed tokens: XAU, XAG, CL, SOXL, GOOGL, MSTR, SNDK,
   CRCL, SPCX, XAUT, BZ, KORU, BTW …) **with Bitget SPOT 1d candles before
   2023-01-01** (≥ 22 months of history before the window start, mature market, the
   300-bar warm-up of every TF guaranteed; probed with
   `/api/v2/spot/market/history-candles?…&endTime=2023-01-01`).
3. Take the **top 9** (the owner's example size). No addition, removal or
   substitution after this commit, whatever the results.

Snapshot of the probe (OI in M USDT; "hist" = spot 1d candles exist before 2023-01-01):

| rank (eligible) | perp | OI M USDT | 24 h vol M | hist | decision |
|---|---|---|---|---|---|
| 1 | BTCUSDT | 2861.5 | 678.8 | yes | **in** (seen asset, rounds 1-6) |
| 2 | ETHUSDT | 1754.6 | 472.4 | yes | **in** |
| 3 | SOLUSDT | 402.8 | 78.4 | yes | **in** |
| 4 | XRPUSDT | 231.6 | 37.4 | yes | **in** |
| — | HYPEUSDT | 214.9 | 49.4 | no (2024 listing) | out |
| — | ZECUSDT | 121.6 | 66.8 | no | out |
| — | XAUUSDT / CLUSDT / SOXLUSDT / GOOGLUSDT | 93.2 / 92.5 / 69.0 / 64.6 | — | not crypto | out |
| 5 | DOGEUSDT | 92.1 | 5.6 | yes | **in** |
| 6 | NEARUSDT | 70.4 | 42.0 | yes (1d; 1h from 2022) | **in** |
| 7 | BNBUSDT | 64.0 | 9.5 | yes | **in** |
| — | SUIUSDT | 50.3 | 11.5 | no (2023 listing) | out |
| — | XAUTUSDT | 48.9 | 2.6 | gold-backed | out |
| 8 | LINKUSDT | 45.1 | 13.3 | yes | **in** |
| — | PEPEUSDT / ENAUSDT | 38.1 / 37.9 | 29.3 / 15.2 | no | out |
| 9 | ADAUSDT | 36.9 | 6.9 | yes (1d; 1h from 2022) | **in** |
| 10 | UNIUSDT | 29.5 | 14.4 | yes | first out |
| 11 | LTCUSDT | 28.6 | 2.9 | yes | out |
| 12 | AVAXUSDT | 24.7 | 10.9 | yes | out (the owner's example had it; the rule puts NEAR in instead) |

**Universe = BTC, ETH, SOL, XRP, DOGE, NEAR, BNB, LINK, ADA** (/USDT).
**New assets (primary family) = the 8 without BTC.**

Data: Bitget **spot** OHLCV (`ccxt` + raw `history-candles`, E13/E18 pagination),
closed candles, cached per (exchange, symbol, TF) with sha256 in the result
JSON — the same source as rounds 1-6 (the follower windows were fitted on spot
BTC; funding is modelled flat 0.01 %/8 h on the notional). Spot is a price
proxy for the perp: the basis on these majors is small and the same choice
was made for BTC in every previous round; declared as a limitation, not
changed mid-way. TFs per profile: PRO 4h (+ 1d guardian, 1w context), SNIPPER
1h (+ 4h guardian, 1d context). A context TF that fails to load degrades to
NaN bias exactly as in the live path (`tf_status` reported per asset).

Window IS 2024-11-01 → 2025-12-31; OOS 2026-01-01 → 2026-10-31; a trade belongs
to the block of its ENTER candle. **No new IS-fitted parameter**: follower
windows `FITTED_WINDOWS` (pro / snipper) frozen on BTC in rounds 2 / 4 are
applied unchanged to every asset (a per-asset re-fit would be a new rule).

## 4. Runs (every run = 9 books, one per asset, long + short, one ledger per book)

Per profile × entry × gate × book, `run_variant` of the round-5 harness
(`rule="r5"`, `entry_filter` = the entry or None for `base`), overrides below.
Costs: E16 fee 0.10 % + slip 0.05 % per layer per side (also on partial takes),
funding 0.01 %/8 h; liquidation intrabar (wick), isolated on the position
margin, cross on the wallet; mmr 0.56 % in every snipper book. Exit chain and
books exactly as `PREREG_IMPULSOS_v2_r6.md` (2.2.0 chain: Konkorde leader /
exit, no AO, guardian ML RSI exit ON, structural invalidation, 50 % partial
take; owner points a, f).

| axis | values | notes |
|---|---|---|
| profile | `pro` (4h, 1300 USDT) · `snipper` (1h, 1700 USDT) | the two profiles the owner trades |
| entry | `base` · `adx_turn` · `bbwp_fresh_blue` | the round-5 baseline + the two filters the owner asked to replicate |
| gate | `spec` = rule doc as written (`mlrsi_gate: true`) · `asrun` = `{"mlrsi_gate": False}` (rounds 4b/5, E20) | **`spec` is primary** (round 6, point 3); `asrun` only for continuity with the round-5 filter numbers |
| book | pro: `pro5` (5x cross) · snipper: `cross5` (`leverage=5, margin_mode="cross", mmr 0.0056`, **reference**, r6 §6 B) and `iso10` (10x isolated, the 2.2.0 book) | risk-based sizing only (the model's: layer 1 = 2 % E0 at the invalidation, cap 1.5x E0, adds 0.5x, exposure cap 3x E0); the owner-style margin sizing of round 6 is not repeated |

Runs: pro 3 × 2 × 1 = 6; snipper 3 × 2 × 2 = 12; 18 runs × 9 assets. Label
`impulse-2.3.0` for the rule doc on its own book (`spec`, `pro5`); every other
run `impulse-2.3.0-r7` (a replication variant, never a rule proposal).

## 5. Cells and metrics

Always long and short apart (the round-4 convention). Three cell levels:

* **Pooled "new8"** (primary): trades of the 8 new assets of one run and side.
* **Pooled "all9"** (secondary): the 9 assets.
* **Per asset**: one book, one side.

Per cell: the round-4 table (n, IS/OOS, expectancy net R, CI95 cluster
bootstrap — clusters = symbol × month —, PF, win, max DD USDT and %, net USDT,
liquidations), plus:

* **p OOS > 0**: one-sided cluster-bootstrap p-value of the OOS expectancy
  (share of 10 000 resampled cluster means ≤ 0, seed 42, floored at 1/10 000;
  None when fewer than 2 clusters). `impulse_multi.p_positive`.
* **Pooled DD**: max drawdown of the cumulative net USDT of the pooled cell as a
  % of the **pooled start** = n_assets × E0 (one book per asset). Per asset: DD %
  of its own book, as in round 4.
* **Liquidations** of a pooled cell = those of the family's books (both sides,
  as in round 4); per asset = its own book.
* **Contribution** (primary cells, descriptive): per asset n, sum R, expectancy
  (all / OOS), net USDT; leave-one-out pooled expectancy; `adds` iff removing the
  asset lowers the pooled expectancy.
* **Books**: per run and asset — equity final, return, DD, liquidations,
  funding / fees, exit mix, entries blocked by the filter, B&H, `tf_status`.

## 6. Verdicts (mechanical, pre-registered)

**6 A — round-4 gate, unchanged**, per cell: GO iff n ≥ 30 AND n_oos ≥ 10 AND
expectancy OOS > 0 AND PF ≥ 1.2 AND liquidations = 0 AND max DD < 35 % of the
start (pooled start for pooled cells); INCONCLUSIVE iff n < 30; else NO-GO.

**6 B — multiple comparisons, declared.** The round-4 gate's "expectancy OOS >
0" is a point estimate; with many cells some will be positive by chance.

* **Primary family** = pooled **new8** cells, gate `spec`, reference books
  (`pro5`, `cross5`): 2 profiles × 3 entries × 2 sides = **12 cells**.
  **Holm step-down, family-wise α = 0.05** on `p OOS > 0`. **GO iff 6 A GO AND
  Holm-adjusted p < 0.05** (`impulse_multi.verdict_r7`). An untestable cell
  (p None) counts in m and is never rejected.
* **Per-asset family** = per-asset cells of the 8 new assets, gate `spec`,
  reference books: 8 × 12 = **96 cells**. **Benjamini-Hochberg, q = 0.10**.
  **ASSET-GO iff 6 A GO on the asset's own book AND BH q-value < 0.10.** An
  ASSET-GO is a replication candidate to be named in the result, **not a paper
  gate**: only a primary pooled GO moves anything.
* **Secondary** (all9 pools; `asrun` gate; `iso10` book; BTC per-asset cells):
  reported with the 6 A gate and raw / within-group Holm p for reading;
  **never GO-eligible** (verdict NO-GO or INCONCLUSIVE by construction).

**6 C — snipper book.** `cross5` is the GO reference (round 6: 5x cross safer
in every comparison, identical trades under risk sizing); `iso10` is reported
with its liquidation count. A liquidation in `iso10` does not fail a `cross5`
cell and vice-versa.

**6 D — continuity.** The BTC-only trades of the round-7 runs must reproduce
the round-6 cells trade for trade (n and net USDT per side): `pro:base:spec:pro5`
↔ r6 `pro:A_spec_on`; `pro:base:asrun:pro5` ↔ `pro:A_on`;
`snipper:base:spec:iso10` ↔ `snipper:A_spec_on`; `snipper:base:asrun:iso10` ↔
`snipper:A_on`; `snipper:<entry>:asrun:{iso10,cross5}` ↔ `snipper:B_risk_*`.
A DIFFERENT here invalidates the run (harness bug), not the hypothesis.

**6 E — what a GO would license.** Nothing goes to paper from this round: a
primary GO (if any) opens a NEW pre-registration (forward paper window, the
cell's exact definition, the universe fixed here). A NO-GO on every primary
cell closes the three entries on 1h / 4h for this universe.

## 7. What will NOT be done

No change to any 2.2.0 / 2.3.0 parameter, window, cost, book or exit after
seeing the results; no per-asset re-fit of the follower windows; no new filter;
no leverage sweep; no re-cutting by regime, sub-period, volatility bucket or
"best N assets"; no removal of an asset that "does not fit"; no looser GO; no
switching the primary family to all9 or to `asrun` if new8 / `spec` fails. No
exchange calls beyond public OHLCV; no Mongo; no Telegram; no push.

## 8. Expected outcome stated in advance

Pooling 8 assets multiplies n by ~8: snipper pooled cells ≈ 200–450 trades per
side (gate `spec` fewer than `asrun`), pro pooled ≈ 40–100 → the GO becomes
DECIDABLE for the first time on both profiles. Expected: expectancy ≈ 0 to
negative net of costs on `base` and `bbwp_fresh_blue` (the BTC classifier said
≈ 0 R); `adx_turn` was DROP on the BTC classifier and its +19 R RUN is the kind
of result that does not replicate — expected to regress to ≈ 0 or negative on
the new assets. Per-asset cells: heterogeneous signs, none surviving BH q 0.10.
Liquidations: 0 on `cross5` and `pro5`; some on `iso10`. Likely verdict: **no
primary GO** (H0); if a cell passes 6 A on the point estimate, Holm m = 12 is
expected to stop it. Most likely value of the round: a decidable NO-GO that
closes the 1h/4h entry question for this universe, plus the per-asset map of
which assets add or subtract.

## 9. Commands (Docker, builds and runs in SERIES, flock on the lab)

```
# tests (network none)
flock /tmp/mmk-docker.lock docker compose --profile test run --rm test-indicadors \
  pytest -q -p no:cacheprovider tests/test_impulse_r7.py tests/test_impulse_r6.py tests/test_impulse_r5.py
# smoke = BTC only, must reproduce round 6 (no new number is produced)
flock /tmp/mmk-docker.lock docker compose --profile backtest run --rm backtest \
  python scripts/run_impulse_backtest_r7.py --only-symbols BTC/USDT --tag r7smoke
# the round
flock /tmp/mmk-docker.lock docker compose --profile backtest run --rm backtest \
  python scripts/run_impulse_backtest_r7.py --md-out /app/docs/impulsos-v2-backtest-r7.md
```

## 10. Result commit

(filled after the run; nothing above this line changes)
