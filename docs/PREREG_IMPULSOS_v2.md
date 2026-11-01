# PRE-REGISTRATION — Impulsos v2 (`impulse-2.0.0`) vs the legacy engine

**Status: FROZEN. Committed BEFORE the first run of the new engine.**
Sections 1–9 may not be edited after the first new-engine number exists;
the only permitted later edits are §10 (result commit) and a dated
`AMENDMENT` block stating what changed and why. The order of commits in git
is the audit trail (same pattern as `PREREG_FEP_CONT_v0.3.0.md`, D17).

* Date frozen: 2026-11-01
* Source of truth: `docs/impulsos-v2.md` §g "Backtest protocol" (spec commit
  `6facf02`). This document restates it in executable terms for the harness;
  where they differ, §g wins and the difference is a bug in this document.
* Engine under test: `src/controllers/metrics/impulse_service.py`
  (`ImpulseEngine.replay`, commit `5d94bc9`), profiles from
  `trade_profiles.TRADE_PROFILES`.
* Harness: `src/controllers/metrics/impulse_backtest.py` +
  `scripts/run_impulse_backtest.py` (committed with this file).
* Scope: **backtest only**. A PASS produces a proposal for paper (spec §h),
  never an order.

---

## 1. Hypothesis

> **H1.** For each mandatory cell (profile x direction), the new impulse
> engine has a **positive net expectancy in R** that clears the §g listón
> (section 6) on BTC/USDT bitget spot, 2024-11-01 -> 2026-10-31, and does so
> in both halves of the split.

> **H1-cmp (comparison, informational).** Like for like (same TF, long),
> the new engine's net expectancy is above the legacy engine's.

> **H0.** Any mandatory cell fails a §g leg, or has n < 30 (INCONCLUSIVE —
> never read as a pass).

## 2. Universe and data

* BTC/USDT, **bitget spot**, public OHLCV via ccxt, closed candles only.
* Window **2024-11-01 00:00 UTC -> 2026-10-31 23:59 UTC**; >= 300 trigger
  bars of warm-up before it (1w from 2019, 1M from 2018-07).
* Pagination forward with `limit=200` (known-errors E13); holes in ccxt's
  pages are patched from bitget's raw `history-candles` endpoint and the
  frame must report `gaps=0`. Every frame is cached and stamped with its
  sha256 (`ohlcv_sha256`) in the result JSON.

## 3. Split

* **In-sample** 2024-11-01 -> 2025-12-31 (14 months).
* **Out-of-sample** 2026-01-01 -> 2026-10-31 (10 months).
* Nothing is fitted on IS: all parameters are the spec's a-priori values.
  A trade belongs to the block of its entry bar.

## 4. Cells

| Cell | Profile | Trigger TF | Stop (ATR14 x) | Status |
|---|---|---|---|---|
| ancient long / short | `ancient` | 1d | 2.0 | mandatory |
| pro long / short | `pro` | 4h | 1.5 | mandatory |
| snipper long / short | `snipper` | 1h | 1.5 | optional, informational |
| scalper long / short | `scalper` | 15m | 2.0 | optional, informational (expected NO-PASS on costs) |

Stop multipliers and time stops are read from `TRADE_PROFILES` at run time
and echoed into the result JSON; if they differ from this table the run is
invalid until reconciled.

## 5. Execution and cost model (identical for both engines)

* Entry at the **close** of the signal bar; R = |entry - initial stop|.
* New engine: exits are the engine's own (`replay` keeps the virtual
  position, one book long-or-short, no flips): ATR stop (fill at stop, or at
  the open if it gapped beyond), owner's rule, `phase_lost`, time stop. The
  harness uses the engine's `stop_price` / `exit_price` and does not
  re-implement exits. An open position at the last bar closes at the last
  close (`end_of_data`).
* Legacy engine: `BacktestService` (`/v1/backtest`) unmodified, on the same
  cached frame (trimmed to its own 250-bar warm-up), RulesService as on this
  branch (`IndicatorsService` default `bbwp_definition="tv"`), long only,
  `medium` = 1.5 x ATR stop / 3R target. Stops re-filled at a worse gapped
  open, as for the new engine. A second legacy reading uses the cell
  profile's stop (`atr_stop_multiplier` override, target still 3R).
* Costs (E16): fee 0.10% + slippage 0.05% per side,
  `cost_R = (fee + slip) * (entry + exit) / stop_distance`.
* Funding: 0.01% of notional per 8h held, charged regardless of sign, on
  every short (perp) and every leveraged long (`default_leverage > 1`:
  scalper, snipper, pro). Ancient longs (spot 1x) and legacy longs (spot)
  pay none.

## 6. Metrics and verdict (per cell; IS, OOS, total)

n, win rate, expectancy net R, median R, profit factor net, max drawdown in
R (cumulative R curve; also % at 1.5% risk per trade, informational), avg
bars held, exit reasons, 95% bootstrap CI of the expectancy — 10 000
resamples, seed 42, **(symbol, month) cluster** resampling (the
conservative variant of §g's bootstrap; `cluster_bootstrap_ci`), confidence
tercile breakdown (informational).

* **INCONCLUSIVE** if `n_total < 30`, whatever the sign.
* **PASS** iff `n_total >= 30` AND `expectancy_net_total >= +0.10 R` AND
  CI95 lower bound `> 0` AND `n_oos >= 10` with `expectancy_net_oos > 0`
  AND `expectancy_net_is > 0` AND `PF_net >= 1.2` AND `maxDD <= 10 R`.
* **NO-PASS** otherwise.

The verdict is computed mechanically by `impulse_backtest.verdict()`.

## 7. Old vs new reporting

* Like for like: legacy-long vs new-long per TF.
* Legacy-short cells print **`N/A — legacy cannot emit shorts`** in the
  headline table (never 0 trades / 0 R). Note: `BacktestService` does carry
  a native `side="short"` path (`signal == "exit"` opens a short); its
  numbers are kept in the JSON and shown only as a separate, labelled
  INFORMATIONAL line, never as the legacy short cell.
* New long+short combined vs legacy-long: separate informational line.
* Buy-and-hold % over the window, per TF, as context.

## 8. What will NOT be done

* No re-cutting by regime, sub-period or volatility bucket after seeing
  results; no extra split.
* No choosing the best profile, direction or TF post hoc: every mandatory
  cell is reported with its verdict.
* No parameter change after the first run; a change = new `rule_version` +
  new pre-registration.
* No looser threshold for a 1d cell that comes out INCONCLUSIVE: the
  pre-registered follow-up is the same rules on ETH/USDT + SOL/USDT pooled.

## 9. Expected outcome stated in advance

1d over two years will likely give < 30 trades per direction ->
INCONCLUSIVE. Legacy baseline already measured before this freeze (it does
not depend on the new engine): 1d medium long n=25, +0.215 R net,
INCONCLUSIVE.

## 10. Result commit

Run 2026-11-01 after this file was committed (`26404e4`). Results and
verdicts: `docs/impulsos-v2-backtest.md` (and §"Backtest results" of
`docs/impulsos-v2.md`). No mandatory cell PASSES: ancient long/short
INCONCLUSIVE, pro long/short NO-PASS. No amendment was made.
