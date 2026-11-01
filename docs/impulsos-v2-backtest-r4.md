# Impulsos v2 — round 4b backtest results (`impulse-2.2.0`: exits without phase_lost; PRO 5x cross + SNIPPER 10x isolated)

Protocol: `docs/PREREG_IMPULSOS_v2_r4.md` (frozen before this run). Run 20261101T074719Z in the lab service `backtest`, harness `scripts/run_impulse_backtest_r4.py`. Raw JSON (every trade, partial takes, sweep, owner replay): `r4_impulse_20261101T074719Z.json`.

## Data manifest

| TF | rows | first open | last open | gaps | sha256 (12) | source |
|---|---|---|---|---|---|---|
| 4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `a9ec96296cf4` | cache |
| 1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `1fd23248b1c1` | cache |
| 1w | 403 | 2019-02-04T00:00 | 2026-10-19T00:00 | 0 | `3c483695e2db` | cache |
| 1M | 100 | 2018-07-01T00:00 | 2026-10-01T00:00 | 0 | `2564ebf1f1c1` | cache |
| 1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `87e7dbf8ecdb` | cache |

## Cells (1R = layer-1 risk = 2 % E0; IS 2024-11 -> 2025-12, OOS 2026-01 -> 2026-10)

r4 verdict: GO iff n >= 30, n_oos >= 10, expectancy OOS > 0, PF >= 1.2, liquidations 0, max DD (cumulative net USDT of the cell) < 35 % of the start. r2 §6 = round-2 R-based verdict, for continuity.

| Cell | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | win | max DD USDT (% start) | net USDT | **r4 verdict** | r2 §6 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4h long **pro:R4** (5x cross, 1300 USDT) | 7 (4/3) | -0.140 | [-0.858, 0.645] | 0.187 | -0.577 | 0.73 | 29% | 77.22 (5.94%) | -26.65 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 4h short **pro:R4** (5x cross, 1300 USDT) | 7 (5/2) | -0.201 | [-1.028, 0.808] | -0.526 | 0.612 | 0.69 | 29% | 84.86 (6.53%) | -38.57 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 1d long **pro_1d:R4** (5x cross, 1300 USDT) | 1 (1/0) | 1.056 | [1.056, 1.056] | 1.056 | — | inf | 100% | 0.0 (0.0%) | 27.46 | INCONCLUSIVE (n_total=1 < 30) | INCONCLUSIVE |
| 1d short **pro_1d:R4** (5x cross, 1300 USDT) | 1 (0/1) | 0.069 | [0.069, 0.069] | — | 0.069 | inf | 100% | 0.0 (0.0%) | 1.82 | INCONCLUSIVE (n_total=1 < 30) | INCONCLUSIVE |
| 1h long **snipper:R4** (10x isolated, 1700 USDT) | 31 (20/11) | -0.099 | [-0.684, 0.566] | -0.100 | -0.097 | 0.88 | 29% | 325.6 (19.15%) | -127.72 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | NO-PASS |
| 1h short **snipper:R4** (10x isolated, 1700 USDT) | 34 (21/13) | -0.273 | [-0.837, 0.412] | -0.338 | -0.166 | 0.70 | 24% | 320.69 (18.86%) | -308.44 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | NO-PASS |

## Book level (one ledger per run, long + short)

| run | tf | lev | decisions (alert / enter / add / reduce / exit) | trades | avg layers | >= 2 layers | partial takes | equity final | return | max DD equity USDT (%) | max exposure | liquidations | exit mix | info_phase_lost candles |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:R4 | 4h | 5x cross | 381 / 14 / 16 / 11 / 14 | 14 | 2.14 | 9 | 11 | 1234.78 | -5.02% | 204.79 (14.34%) | 0.776x | 0 | {'exit_ctx_mlrsi_against': 10, 'exit_invalidation': 2, 'exit_rule_jeisson': 2} | 1054 |
| pro_1d:R4 | 1d | 5x cross | 175 / 2 / 2 / 2 / 2 | 2 | 2.0 | 1 | 2 | 1329.28 | 2.25% | 46.38 (3.47%) | 0.134x | 0 | {'exit_rule_jeisson': 2} | 59 |
| snipper:R4 | 1h | 10x isolated | 2257 / 65 / 89 / 59 / 63 | 65 | 2.37 | 50 | 59 | 1263.84 | -25.66% | 618.33 (33.66%) | 2.183x | 1 | {'exit_invalidation': 19, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'liquidation': 1, 'end_of_data': 1} | 3451 |
| snipper:R4@7x | 1h | 7x isolated | 2257 / 65 / 89 / 59 / 64 | 65 | 2.37 | 50 | 59 | 1264.93 | -25.59% | 617.28 (33.6%) | 2.183x | 0 | {'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'end_of_data': 1} | 3451 |
| snipper:R4@5x | 1h | 5x isolated | 2257 / 65 / 89 / 59 / 64 | 65 | 2.37 | 50 | 59 | 1264.93 | -25.59% | 617.28 (33.6%) | 2.183x | 0 | {'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'end_of_data': 1} | 3451 |
| snipper:R4@3x | 1h | 3x isolated | 2257 / 65 / 89 / 59 / 64 | 65 | 2.37 | 50 | 59 | 1264.93 | -25.59% | 617.28 (33.6%) | 2.183x | 0 | {'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'end_of_data': 1} | 3451 |
| snipper:R4@2x | 1h | 2x isolated | 2257 / 65 / 89 / 59 / 64 | 65 | 2.37 | 50 | 59 | 1263.85 | -25.66% | 593.95 (32.76%) | 2.011x | 0 | {'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'end_of_data': 1} | 3451 |
| snipper:R4@1x | 1h | 1x isolated | 2257 / 65 / 89 / 59 / 64 | 65 | 2.28 | 48 | 59 | 1414.99 | -16.77% | 444.45 (24.57%) | 1.089x | 0 | {'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'end_of_data': 1} | 3451 |

Buy-and-hold over the window: pro:R4 11.76%, pro_1d:R4 11.57%, snipper:R4 10.5%.

## Leverage sweep of `snipper:R4` (same signals; only margin and liquidation distance change)

| run | liquidations | book return | max DD equity | long: n / exp OOS / PF / DD% / verdict | short: n / exp OOS / PF / DD% / verdict | GO |
|---|---|---|---|---|---|---|
| snipper:R4 | 1 | -25.66% | 33.66% | 31 / -0.097 / 0.88 / 19.15% / NO-GO | 34 / -0.166 / 0.70 / 18.86% / NO-GO | no |
| snipper:R4@7x | 0 | -25.59% | 33.6% | 31 / -0.097 / 0.88 / 19.16% / NO-GO | 34 / -0.163 / 0.70 / 18.8% / NO-GO | no |
| snipper:R4@5x | 0 | -25.59% | 33.6% | 31 / -0.097 / 0.88 / 19.16% / NO-GO | 34 / -0.163 / 0.70 / 18.8% / NO-GO | no |
| snipper:R4@3x | 0 | -25.59% | 33.6% | 31 / -0.097 / 0.88 / 19.16% / NO-GO | 34 / -0.163 / 0.70 / 18.8% / NO-GO | no |
| snipper:R4@2x | 0 | -25.66% | 32.76% | 31 / -0.097 / 0.88 / 18.96% / NO-GO | 34 / -0.163 / 0.70 / 18.79% / NO-GO | no |
| snipper:R4@1x | 0 | -16.77% | 24.57% | 31 / -0.016 / 1.00 / 14.17% / NO-GO | 34 / -0.068 / 0.74 / 16.6% / NO-GO | no |

**Pre-registered fallback**: highest leverage whose BOTH cells are GO: **none** (no leverage in {10x, 7x, 5x, 3x, 2x, 1x} passes).

## Reference: round 2-3 (`impulse-2.1.0`, phase_lost exit, time stop; same window, same costs)

| run | side | n (OOS) | exp. R net | exp. OOS | PF | win | max DD R | r2 verdict | book return | book DD | exit mix |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:H1 | long | 30 (11) | -0.403 | -0.542 | 0.51 | 23% | 15.7 | NO-PASS | -22.68% | 31.25% | {'exit_phase_lost': 36, 'exit_invalidation': 14, 'exit_time_stop': 5, 'exit_rule_jeisson': 2} |
| pro:H1 | short | 27 (11) | 0.001 | -0.016 | 1.00 | 59% | 3.8 | INCONCLUSIVE | -22.68% | 31.25% | {'exit_phase_lost': 36, 'exit_invalidation': 14, 'exit_time_stop': 5, 'exit_rule_jeisson': 2} |
| pro:H2 | long | 12 (4) | 0.086 | -0.266 | 1.14 | 42% | 4.5 | INCONCLUSIVE | 3.71% | 10.7% | {'exit_phase_lost': 28, 'exit_invalidation': 6, 'exit_time_stop': 3, 'exit_rule_jeisson': 1} |
| pro:H2 | short | 26 (9) | 0.048 | 0.062 | 1.21 | 54% | 2.5 | INCONCLUSIVE | 3.71% | 10.7% | {'exit_phase_lost': 28, 'exit_invalidation': 6, 'exit_time_stop': 3, 'exit_rule_jeisson': 1} |
| pro_1d:H1 | long | 6 (2) | 0.220 | -0.009 | 1.33 | 50% | 2.6 | INCONCLUSIVE | 1.92% | 9.3% | {'exit_phase_lost': 5, 'exit_invalidation': 1, 'exit_time_stop': 1, 'end_of_data': 1} |
| pro_1d:H1 | short | 2 (1) | -0.076 | -0.071 | 0.00 | 0% | 0.2 | INCONCLUSIVE | 1.92% | 9.3% | {'exit_phase_lost': 5, 'exit_invalidation': 1, 'exit_time_stop': 1, 'end_of_data': 1} |
| pro_1d:H2 | long | 1 (0) | 1.690 | — | inf | 100% | 0.0 | INCONCLUSIVE | 2.52% | 3.7% | {'exit_phase_lost': 3} |
| pro_1d:H2 | short | 2 (1) | -0.208 | -0.337 | 0.00 | 0% | 0.4 | INCONCLUSIVE | 2.52% | 3.7% | {'exit_phase_lost': 3} |

Source: `r2_sequential_20261101T071222Z.json`.

## Follower windows used (IS fit, frozen)

* pro:R4: {'ao': 2, 'adx': 4, 'macd': 3, 'rsi': 2} (ttl 4), tf_status {'4h': 'ok', '1d': 'ok', '1w': 'ok'}, first decision 2024-11-01T00:00
* pro_1d:R4: {'ao': 3, 'adx': 3, 'macd': 2, 'rsi': 5} (ttl 5), tf_status {'1d': 'ok', '1w': 'ok', '1M': 'ok'}, first decision 2024-11-01T00:00
* snipper:R4: {'ao': 2, 'adx': 5, 'macd': 3, 'rsi': 3} (ttl 5), tf_status {'1h': 'ok', '4h': 'ok', '1d': 'ok'}, first decision 2024-11-01T00:00

## ML RSI repaint (causal vs TV-anchored window, percentile thresholds)

* 4h: 1500 bars 2026-02-24 -> 2026-10-31: upper mean |Δ| 0.407 (max 1.568), lower mean |Δ| 1.016 (max 2.66), regime disagreement 5.73%, last bar identical True.
* 1h: 2998 bars 2026-06-29 -> 2026-10-31: upper mean |Δ| 1.389 (max 15.142), lower mean |Δ| 2.066 (max 6.692), regime disagreement 9.91%, last bar identical True.

## §R2.g — the owner's short (82450, 2026-10-09) replayed with the NEW chain (one trade; validates nothing)

### pro:R4 (4h) — `owner_bar` 2026-10-09T00:00 close 82418.88 (owner ~82450)

* Machine there: state **in_position**, alert None, phase expansion, bbwp 75.8, verde -10.89, guardian {'1d': 1, '1w': 1}, ML RSI trigger red / guardian green, reasons hold_no_follower_confirm.
* Model's own shorts Sep-Oct 2026: none.
* **Anchored replay**: layer 1 445.2066 USDT at 82418.88, invalidation 87232.13 (invalidation_ctx_swing), 1R 26.0 USDT, liq 321474. Events: 2026-10-09T08:00 exit exit_ctx_mlrsi_against; 2026-10-14T20:00 hold add_rejected_min_gap; 2026-10-15T00:00 hold add_rejected_min_gap; 2026-10-15T20:00 reduce partial_take_mlrsi,mlrsi_red_to_gray; 2026-10-16T16:00 hold info_phase_lost,add_rejected_phase; 2026-10-16T20:00 hold info_phase_lost,add_rejected_phase; 2026-10-17T00:00 hold info_phase_lost; 2026-10-17T04:00 hold info_phase_lost; 2026-10-17T08:00 hold info_phase_lost; 2026-10-17T12:00 hold info_phase_lost; 2026-10-17T16:00 hold info_phase_lost; 2026-10-17T20:00 hold info_phase_lost. **EXIT exit_ctx_mlrsi_against** at 2026-10-09T04:00 price 82653.53: net -2.6274 USDT = **-0.10 R** (1 layers, 0 partial takes).

### snipper:R4 (1h) — `owner_bar` 2026-10-12T18:00 close 82454.84 (owner ~82450)

* Machine there: state **in_position**, alert None, phase expansion, bbwp 86.7, verde -17.57, guardian {'4h': 1, '1d': 1}, ML RSI trigger red / guardian gray, reasons hold_no_follower_confirm.
* Model's own shorts Sep-Oct 2026: 2026-10-08T15:00 -> 2026-10-21T15:00 exit_ctx_mlrsi_against (2 layers, -1.09 R, -27.9 USDT); 2026-10-24T15:00 -> 2026-10-31T23:00 end_of_data (3 layers, 0.49 R, 12.3 USDT)
* **Anchored replay**: layer 1 1470.9323 USDT at 82454.84, invalidation 84360.75 (invalidation_ctx_swing), 1R 34.0 USDT, liq 90195. Events: 2026-10-13T00:00 add_layer add_layer_follower_confirm; 2026-10-13T05:00 reduce partial_take_mlrsi,mlrsi_red_to_gray; 2026-10-13T11:00 hold add_rejected_not_in_profit; 2026-10-13T15:00 hold info_phase_lost; 2026-10-13T16:00 hold info_phase_lost; 2026-10-13T17:00 hold info_phase_lost; 2026-10-13T18:00 hold info_phase_lost,add_rejected_not_in_profit; 2026-10-13T19:00 hold info_phase_lost,add_rejected_not_in_profit; 2026-10-13T20:00 hold info_phase_lost; 2026-10-13T21:00 hold info_phase_lost; 2026-10-13T22:00 hold info_phase_lost; 2026-10-13T23:00 hold info_phase_lost. **EXIT exit_invalidation** at 2026-10-21T15:00 price 84545.78: net -96.5805 USDT = **-2.84 R** (3 layers, 1 partial takes). **Still open at 77551.91**: 3 layer(s), avg 79071.80, move on layer 1 5.94%, 1 partial take(s), unrealized gross 32.636 USDT, net of costs/funding/exit estimate 23.3342 USDT (**0.73 R**).

