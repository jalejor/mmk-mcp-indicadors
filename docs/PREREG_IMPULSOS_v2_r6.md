# PRE-REGISTRATION — Impulsos v2 round 6: two ABLATIONS on the frozen `impulse-2.3.0` baseline (no new rule)

**Status: FROZEN. Committed BEFORE the first round-6 run.** Sections 1–9 may not
be edited after the first round-6 number exists; later edits are limited to §10
(result commit) and dated `AMENDMENT` blocks. Git order is the audit trail
(same pattern as `PREREG_IMPULSOS_v2_r2.md`, `_r4.md`, `_r5.md`).

* Date frozen: 2026-11-01 (after the round-5 result commit `d47a3c7`).
* Owner decisions of 2026-11-01 that bind this round (`docs/board.md` #26):
  **(a)** NO AO for the exit (slower): Konkorde stays the leader/exit on 1h;
  **(b/c)** snipper = scalper is ONLY 1h at 10x isolated and must be "súper
  pulido" before use — today the owner trades 5x cross and has done better with
  it; **(f)** the guardian ML RSI exit is new (71 % of the 4h exits in round 4b)
  and must be reviewed in depth, including measured with and without it.
* Engine under test: `impulse_sequential.SequentialMachine` with
  `r5_params(profile, entry_filter)` (`impulse-2.3.0`), ledger
  `impulse_backtest.PositionLedger`, harness `scripts/run_impulse_backtest_r6.py`,
  tests `tests/test_impulse_r6.py`. No new rule: every non-baseline run is an
  ablation labelled `impulse-2.3.0-r6`, never a rule proposal.
* Scope: **backtest only**. Nothing here produces an order, a deploy, a push, a
  Mongo write or a Telegram message. FEC/FEP stay archived; live containers
  `mmk-signals-*` untouched.

---

## 1. Finding made while preparing the round (declared before any run): E20

`impulse_backtest.run_sequential(..., mlrsi_gate=False)` forwarded its DEFAULT
as an override to `r4_params` / `r5_params`, which therefore ran with
`mlrsi_gate=False` although the 2.2.0 / 2.3.0 rule docs say `mlrsi_gate: true`
(verified in `r4_impulse_20261101T074719Z.json` → `params.mlrsi_gate = false`
and in the round-5 reasons: no `mlrsi_gate_*` reason ever appears). So rounds
4b and 5 measured the chain WITHOUT the trigger ML RSI entry/add gate; the
partial take (trigger regime) and the guardian ML RSI exit were active.

Consequences for this round: the harness default becomes `mlrsi_gate=None`
(= the rule doc's value); the as-run chain is reproduced with an explicit
`{"mlrsi_gate": False}` (`AS_RUN`). Round 6 runs BOTH readings and reports
them side by side; it does not re-open the round-4b / round-5 verdicts (no
cell would have passed with a stricter entry gate — fewer entries, same
signal), but every number of those rounds now carries the E20 caveat.

## 2. Hypotheses

> **H6-A (owner point f, guardian ML RSI exit).** Removing exit #3 of the 2.2.0
> chain (`exit_ctx_mlrsi_against`, guardian regime in the contrary colour) while
> keeping the entry block (`ctx_mlrsi_against` at ENTER; new knob
> `ctx_mlrsi_entry_block=True`) does NOT lower the net expectancy of the book
> on PRO 4h and SNIPPER 1h. Measured on the as-run chain (`A_on` vs
> `A_exit_off`) and on the rule doc as written (`A_spec_on` vs
> `A_spec_exit_off`); `A_both_off` (exit and entry block removed) is
> informational.

> **H6-B (owner points b/c, snipper book).** On SNIPPER 1h with the frozen chain
> (Konkorde leader/exit, no AO — point a), the 10x ISOLATED book (1700 USDT,
> mmr 0.56 %) and the "equivalent" 5x CROSS book (same 1700 USDT, same mmr, same
> machine, same sizing) differ ONLY through the liquidation mechanics: with
> RISK-based sizing (layer 1 = 2 % E0 at the invalidation, cap 1.5x E0, adds
> 0.5x, exposure cap 3x E0) the position sizes are identical, so 10x cannot
> "earn more in less time"; it can only lose the trades that get liquidated.
> With MARGIN-based sizing (the owner's habit: layer-1 margin 10 % E0 → notional
> = margin × leverage) 10x doubles both the P&L and the drawdown of 5x and adds
> the liquidation risk.

> **H0.** Removing the guardian ML RSI exit changes the expectancy by less than
> the noise (INCONCLUSIVE), and the 10x isolated book is never PREFERRED over
> 5x cross under §6 B.

## 3. Universe, data, split

BTC/USDT bitget spot OHLCV, closed candles, the cached frames of rounds 4b/5
(sha256 in the result JSON): 1h `87e7dbf8ecdb`, 4h `a9ec96296cf4`, 1d
`1fd23248b1c1`, 1w `3c483695e2db`. IS 2024-11-01 → 2025-12-31; OOS 2026-01-01 →
2026-10-31; a trade belongs to the block of its ENTER candle. **No new
IS-fitted parameter**; windows, costs (E16 + funding), books and exit chain
exactly as `PREREG_IMPULSOS_v2_r5.md` §4.

## 4. Runs (every run = one book long + short, one ledger)

Part A, profiles `pro` (4h / 1d) and `snipper` (1h / 4h), entry `base`:

| key | overrides on `r5_params(profile)` | meaning |
|---|---|---|
| `A_on` | `mlrsi_gate=False` | round-5 baseline AS RUN (must reproduce r5 `base` trade for trade) |
| `A_exit_off` | `mlrsi_gate=False, ctx_mlrsi_exit=False, ctx_mlrsi_entry_block=True` | pure exit ablation, same entries |
| `A_both_off` | `mlrsi_gate=False, ctx_mlrsi_exit=False` | exit AND entry block removed (informational) |
| `A_spec_on` | — | 2.2.0 / 2.3.0 as WRITTEN (trigger gate on) |
| `A_spec_exit_off` | `ctx_mlrsi_exit=False, ctx_mlrsi_entry_block=True` | pure exit ablation on the as-written chain |

Part B, profile `snipper`, as-run chain (`mlrsi_gate=False`, continuity with
the round-5 entry cells), books `iso10` (2.2.0 snipper book) and `cross5`
(`leverage=5, margin_mode="cross", maintenance_margin_rate=0.0056`):

| sizing | entries | runs |
|---|---|---|
| RISK (the model's, unchanged) | `base`, `bbwp_fresh_blue` (the only round-5 KEEP), `adx_turn` (best round-5 RUN, classifier DROP, informational) | 3 × 2 books |
| MARGIN (owner-style): `layer1_risk_pct=1000` (risk size disabled), `layer1_max_exposure_x = 0.10 × lev`, `max_exposure_x = 0.30 × lev`, `max_open_risk_pct=100` | `base`, `bbwp_fresh_blue` | 2 × 2 books |

The `iso10:base` run of Part B is the same book as `snipper:A_on`.

## 5. Metrics

Per cell (profile × variant × side): the round-4b table (n, expectancy net R,
CI95 cluster bootstrap, IS/OOS, PF, win, max DD USDT and % of start, net USDT)
with the unchanged `verdict_r4`; per book: equity final, return, max DD of the
equity curve, liquidations, avg layers, max exposure, layers sized down by the
leverage cap, funding / fees, exit mix.

**R per unit of time** (new, per book and per side): net R per 30 days of
window (`sum_r / window_days × 30`), net R per day HELD (`sum_r / Σ days
held`), trades per 30 days, median hold hours, % of the window in the market.

**Pairing (Part A)**: trades matched by ENTRY candle between the two runs of a
pair; reported: common entries, entries only in one run, mean and median ΔR
(off − on) on the common entries, how many common trades last longer without
the exit.

## 6. Verdicts (mechanical, pre-registered)

**6 A — guardian ML RSI exit (per profile, sides pooled, per pair).**
INCONCLUSIVE by construction when either run has `n < 30` in total or `n_oos <
10` (PRO 4h is expected INCONCLUSIVE; SNIPPER 1h decides). Otherwise **KEEP**
iff `exp_on > exp_off` on all, IS and OOS AND `liq_on <= liq_off`; **DROP** iff
`exp_off > exp_on` on all, IS and OOS AND `liq_off <= liq_on`; else
INCONCLUSIVE. The decision pair is `A_spec_on → A_spec_exit_off` (the rule as
written); `A_on → A_exit_off` is reported for continuity with rounds 4b/5. A
DROP means the exit is removed from the NEXT rule doc (a new pre-registration),
not that anything passes.

**6 B — snipper book (per sizing × entry).** `ISO10_PREFERRED` iff
`liquidations_iso == 0` AND `sum_r_iso >= sum_r_cross` AND `maxDD%_iso <=
maxDD%_cross` (book level); otherwise `CROSS5_SAFER`. The harness also reports
whether the two books produced IDENTICAL trades (same entries and net USDT per
trade). Neither label is a GO: the cells keep `verdict_r4`, and every snipper
cell was NO-GO in rounds 4b/5.

## 7. What will NOT be done

No change to any 2.2.0 / 2.3.0 parameter, window, cost or exit after seeing
the results; no stacking; no new filter; no leverage sweep beyond the two books;
no re-cutting by regime or sub-period; no looser GO. The E20 fix changes the
HARNESS default only; the rule docs are untouched. No exchange calls beyond
the cache (BTC frames are cached); the ML RSI audit (`scripts/audit_ml_rsi.py`,
separate report) fetches PUBLIC Binance OHLCV once as the owner's reference
exchange, read-only.

## 8. Expected outcome stated in advance

Part A: on the as-run chain, removing the guardian exit makes the trades
longer and moves the exits to the structural invalidation and the Jeisson
rule; gross stays ≈ 0 and the net is dominated by funding (longer holds) —
expected INCONCLUSIVE or DROP on snipper, INCONCLUSIVE on PRO (n 14). On the
as-written chain (trigger gate on) fewer entries, n likely < 30 on snipper →
INCONCLUSIVE. Part B, RISK sizing: identical trades except the ones liquidated
at 10x (round 4b: one, 2026-03-02) → `CROSS5_SAFER` with ≈ equal R; the owner's
"10x isolated would make more in less time" is NOT supported by risk-based
sizing (same notional, only the margin and the liquidation distance change).
MARGIN sizing: 10x ≈ 2× the USDT P&L and DD of 5x (R per trade similar, 1R
doubles), liquidation risk only at 10x → `CROSS5_SAFER` unless 10x has 0
liquidations and the book is not negative.

## 9. Command

```
docker compose --profile backtest run --rm -e TELEGRAM_BOT_TOKEN= backtest \
  python scripts/run_impulse_backtest_r6.py --md-out /app/docs/impulsos-v2-backtest-r6.md
docker compose --profile backtest run --rm backtest \
  python scripts/audit_ml_rsi.py --md-out /app/docs/impulsos-v2-ml-rsi-audit.md
```

## 10. Result commit

(filled after the run)
