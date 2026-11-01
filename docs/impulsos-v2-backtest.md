# Impulsos v2 — backtest results (legacy vs `impulse-2.0.0`)

Protocol: `docs/impulsos-v2.md` §g, restated in `docs/PREREG_IMPULSOS_v2.md`
(frozen at commit `26404e4`, BEFORE the first new-engine run). Engine
`5d94bc9`, spec `6facf02`. Run 2026-11-01 in the lab service `backtest`
(`labs/mmk-signals`), harness `scripts/run_impulse_backtest.py`. Raw JSON
(every trade) in `labs/mmk-signals/data/results/`.

## Data manifest (bitget spot BTC/USDT, closed candles, gaps = 0)

| TF | rows | first open | last open | sha256 (12) |
|---|---|---|---|---|
| 1M | 100 | 2018-07-01 | 2026-10-01 | `2564ebf1f1c1` |
| 1w | 403 | 2019-02-04 | 2026-10-19 | `3c483695e2db` |
| 1d | 1030 | 2024-01-06 | 2026-10-31 | `1fd23248b1c1` |
| 4h | 4680 | 2024-09-12 | 2026-10-31 20:00 | `a9ec96296cf4` |
| 1h | 17820 | 2024-10-19 12:00 | 2026-10-31 23:00 | `87e7dbf8ecdb` |
| 15m | 70380 | 2024-10-28 21:00 | 2026-10-31 23:45 | `86bc57740b81` |

⚠️ ccxt 4.2.97 returns EMPTY bitget pages for ~25 days just before the
recent window on 1h/15m (1h 2026-08-13 -> 09-07, 600 candles; 15m a 164-candle
hole 2026-09-29 -> 10-01). The loader patches them from the raw
`history-candles` endpoint with `endTime`; without that, 1h silently ended
on 2026-08-13.

## Headline: old vs new per mandatory cell (§g verdict on the total)

Split: IS 2024-11-01 -> 2025-12-31, OOS 2026-01-01 -> 2026-10-31. Net R =
after fee 0.10% + slip 0.05% per side and funding (shorts, leveraged longs).
CI = 95% (symbol, month) cluster bootstrap, 10 000 resamples, seed 42.

| Cell | Engine | n (IS/OOS) | exp. R net total | CI95 | exp. IS | exp. OOS | PF | max DD R | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1d long | legacy medium 1.5/3R | 25 (17/8) | +0.215 | [-0.590, 1.101] | +0.111 | +0.437 | 1.30 | 9.0 | INCONCLUSIVE (n<30) |
| 1d long | legacy @ancient stop 2.0/3R | 18 (14/4) | +0.108 | [-0.767, 1.046] | +0.093 | +0.159 | 1.15 | 7.3 | INCONCLUSIVE (n<30) |
| 1d long | **new ancient** | 7 (6/1) | +0.220 | [-0.711, 1.560] | +0.327 | -0.421 | 1.52 | 2.7 | INCONCLUSIVE (n<30) |
| 1d short | legacy | N/A — legacy cannot emit shorts | | | | | | | N/A |
| 1d short | **new ancient** | 7 (5/2) | -0.363 | [-0.956, 0.304] | -0.440 | -0.169 | 0.42 | 3.2 | INCONCLUSIVE (n<30) |
| 4h long | legacy medium 1.5/3R (= pro stop) | 137 (81/56) | -0.141 | [-0.434, 0.161] | -0.073 | -0.238 | 0.84 | 31.1 | NO-PASS (all legs) |
| 4h long | **new pro** | 41 (22/19) | +0.146 | [-0.368, 0.834] | +0.615 | -0.397 | 1.25 | 8.0 | NO-PASS (CI lower <= 0; OOS <= 0) |
| 4h short | legacy | N/A — legacy cannot emit shorts | | | | | | | N/A |
| 4h short | **new pro** | 43 (20/23) | -0.374 | [-0.791, 0.188] | -0.576 | -0.199 | 0.55 | 16.2 | NO-PASS (all legs) |

Optional / informational (§g):

| Cell | Engine | n (IS/OOS) | exp. R net total | CI95 | exp. IS | exp. OOS | PF | max DD R | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1h long | **new snipper** | 140 (83/57) | -0.306 | [-0.783, 0.340] | -0.108 | -0.594 | 0.71 | 55.7 | NO-PASS (all legs) |
| 1h short | **new snipper** | 153 (91/62) | -0.284 | [-0.663, 0.225] | -0.457 | -0.029 | 0.72 | 45.8 | NO-PASS (all legs) |
| 1h long | legacy | not run: the legacy engine recomputes every indicator per bar (O(n²)), ~hours on 17.8k bars | | | | | | | — |

Context: buy-and-hold over the window +11.6% (1d), +11.8% (4h), +10.5% (1h).
Average cost+funding per trade: 1d ~0.06 R long / 0.08 R short, 4h ~0.21 R,
1h ~0.41-0.46 R (E16: the 1h hurdle eats most of the gross edge).

## Verdict (honest, against the pre-registration)

* **No mandatory cell PASSES.** `ancient` long/short: INCONCLUSIVE (7
  trades per direction in 2 years). `pro` long: NO-PASS — positive total
  (+0.146 R) but CI crosses 0 and the OOS half is negative (-0.397 R, CI
  [-0.776, -0.058]): the IS edge did not survive. `pro` short: NO-PASS on every leg.
* **H1-cmp (new > old, like for like long):** 1d: new +0.220 vs legacy
  +0.215 — indistinguishable at n=7 vs 25. 4h: new +0.146 R (n=41, max DD 8.0 R) vs legacy -0.141 R (n=137, max DD
  31.1 R) — the new engine trades 3x less and is better on every total
  metric, but its OOS half (-0.397 R) is WORSE than legacy's (-0.238 R). The
  improvement is not established; neither engine has an edge on 4h OOS.
* `snipper` (informational): NO-PASS both ways; max DD 46-56 R. Do not paper it.
* Pre-registered follow-up for INCONCLUSIVE 1d (§g): same rules on
  ETH/USDT + SOL/USDT pooled — NOT a looser threshold.
* Exit mix (new): `pro` long 24 phase_lost / 16 stop / 1 owner rule; `pro`
  short 26 stop / 17 phase_lost; `snipper` ~2/3 of exits are ATR stops. The
  owner's exit rule fired 3 times in 391 trades — the trades are decided by
  the stop and phase_lost, not by the owner's rule.

## Notes on the method

* Legacy = `BacktestService` (`/v1/backtest`) unmodified, `RulesService` with
  the branch default `bbwp_definition="tv"` (post-406b69c), long only,
  medium 1.5 x ATR / 3R target, fed the cached frame (its own 250-bar
  warm-up). Costs/funding/gap-fill applied on top (the engine charges none).
  `@ancient stop 2.0` = same engine with `atr_stop_multiplier=2.0`.
* Fact for the record: `BacktestService` DOES have a native short path
  (`side="short"`, `signal == "exit"` opens a short; the route default is
  `side="both"`). Per §g the headline shows N/A; the numbers are kept in
  the JSON as INFORMATIONAL only (1d medium short: n=15, +0.295 R,
  INCONCLUSIVE; 4h medium short: n=129, -0.145 R, NO-PASS).
* New engine trades come from the engine's own enter/exit pairs
  (`stop_price`, `exit_price` from `replay`), entry at the enter-bar close;
  the harness adds only costs and funding. One book: a long blocks shorts
  and vice versa.
