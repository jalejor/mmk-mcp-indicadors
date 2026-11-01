# Impulsos v2 — round 2 backtest results (`impulse-2.1.0`, sequential, PRO re-buys)

Protocol: `docs/PREREG_IMPULSOS_v2_r2.md` (frozen before this run). Run 20261101T071222Z in the lab service `backtest`, harness `scripts/run_impulse_backtest_r2.py`. Raw JSON (every trade, every decision count): `r2_sequential_20261101T071222Z.json`.

## Data manifest

| TF | rows | first open | last open | gaps | sha256 (12) | source |
|---|---|---|---|---|---|---|
| 4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `a9ec96296cf4` | cache |
| 1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `1fd23248b1c1` | cache |
| 1w | 403 | 2019-02-04T00:00 | 2026-10-19T00:00 | 0 | `3c483695e2db` | cache |
| 1M | 100 | 2018-07-01T00:00 | 2026-10-01T00:00 | 0 | `2564ebf1f1c1` | cache |

## Cells (§6 verdict on net R; 1R = layer-1 risk = 2% E0; IS 2024-11 -> 2025-12, OOS 2026-01 -> 2026-10)

| Cell | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | max DD R | win | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 4h long **pro:H1** | 30 (19/11) | -0.403 | [-0.878, 0.207] | -0.323 | -0.542 | 0.51 | 15.7 | 23% | NO-PASS (expectancy_total >= 0.10R; CI95 lower > 0; expectancy_oos > 0; expectancy_is > 0; PF >= 1.2; maxDD <= 10R) |
| 4h short **pro:H1** | 27 (16/11) | 0.001 | [-0.358, 0.324] | 0.013 | -0.016 | 1.00 | 3.8 | 59% | INCONCLUSIVE (n_total=27 < 30) |
| 4h long **pro:H2** | 12 (8/4) | 0.086 | [-0.798, 1.109] | 0.262 | -0.266 | 1.14 | 4.5 | 42% | INCONCLUSIVE (n_total=12 < 30) |
| 4h short **pro:H2** | 26 (17/9) | 0.048 | [-0.269, 0.337] | 0.041 | 0.062 | 1.21 | 2.5 | 54% | INCONCLUSIVE (n_total=26 < 30) |
| 1d long **pro_1d:H1** | 6 (4/2) | 0.220 | [-1.212, 1.819] | 0.334 | -0.009 | 1.33 | 2.6 | 50% | INCONCLUSIVE (n_total=6 < 30) |
| 1d short **pro_1d:H1** | 2 (1/1) | -0.076 | [-0.080, -0.071] | -0.080 | -0.071 | 0.00 | 0.2 | 0% | INCONCLUSIVE (n_total=2 < 30) |
| 1d long **pro_1d:H2** | 1 (1/0) | 1.690 | [1.690, 1.690] | 1.690 | — | inf | 0.0 | 100% | INCONCLUSIVE (n_total=1 < 30) |
| 1d short **pro_1d:H2** | 2 (1/1) | -0.208 | [-0.337, -0.080] | -0.080 | -0.337 | 0.00 | 0.4 | 0% | INCONCLUSIVE (n_total=2 < 30) |

Round-1 reference (same window, costs E16): round1 long 0.146 R, round1 short -0.374 R, legacy 1d long 0.215 R, legacy 4h long -0.141 R. Buy-and-hold: pro:H1 11.76%, pro:H2 11.76%, pro_1d:H1 11.57%, pro_1d:H2 11.57%.

## Book level (one ledger per run, 1300 USDT start, 5x cross)

| run | trigger | decisions (alert / enter / add / exit) | trades | avg layers | >= 2 layers | equity final | return | max DD equity | max exposure | liquidations | exit mix |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:H1 | 4h | 1305 / 57 / 26 / 57 | 57 | 1.46 | 20 | 1005.16 | -22.68% | 31.25% | 1.671x | 0 | {'exit_phase_lost': 36, 'exit_invalidation': 14, 'exit_time_stop': 5, 'exit_rule_jeisson': 2} |
| pro:H2 | 4h | 1933 / 38 / 10 / 38 | 38 | 1.26 | 10 | 1348.21 | 3.71% | 10.7% | 1.239x | 0 | {'exit_phase_lost': 28, 'exit_invalidation': 6, 'exit_time_stop': 3, 'exit_rule_jeisson': 1} |
| pro_1d:H1 | 1d | 224 / 8 / 6 / 7 | 8 | 1.75 | 5 | 1324.99 | 1.92% | 9.3% | 0.5x | 0 | {'exit_phase_lost': 5, 'exit_invalidation': 1, 'exit_time_stop': 1, 'end_of_data': 1} |
| pro_1d:H2 | 1d | 407 / 3 / 0 / 3 | 3 | 1.0 | 0 | 1332.77 | 2.52% | 3.7% | 0.222x | 0 | {'exit_phase_lost': 3} |

## Follower windows used (fitted on IS, frozen)

* pro:H1: {'ao': 2, 'adx': 4, 'macd': 3, 'rsi': 2} (ttl 4), tf_status {'4h': 'ok', '1d': 'ok', '1w': 'ok'}, first decision 2024-11-01T00:00
* pro:H2: {'ao': 2, 'adx': 4, 'macd': 3, 'rsi': 2} (ttl 4), tf_status {'4h': 'ok', '1d': 'ok', '1w': 'ok'}, first decision 2024-11-01T00:00
* pro_1d:H1: {'ao': 3, 'adx': 3, 'macd': 2, 'rsi': 5} (ttl 5), tf_status {'1d': 'ok', '1w': 'ok', '1M': 'ok'}, first decision 2024-11-01T00:00
* pro_1d:H2: {'ao': 3, 'adx': 3, 'macd': 2, 'rsi': 5} (ttl 5), tf_status {'1d': 'ok', '1w': 'ok', '1M': 'ok'}, first decision 2024-11-01T00:00

## ML RSI repaint (causal vs TV-anchored window, percentile thresholds)

* 4h: 1500 bars 2026-02-24 -> 2026-10-31: upper mean |Δ| 0.407 (max 1.568), lower mean |Δ| 1.016 (max 2.66), regime disagreement 5.73%, last bar identical True.
* 1d: 700 bars 2024-12-01 -> 2026-10-31: upper mean |Δ| 0.0 (max 0.0), lower mean |Δ| 0.0 (max 0.0), regime disagreement 0.0%, last bar identical True.

## §R2.g — the owner's open short (October 2026), informational

`owner_bar`: 4h candle open 2026-10-09T00:00:00+00:00 (close 2026-10-09T04:00:00+00:00), close **82418.88** (owner ~82450).

### Machine state at `owner_bar`

| run | state | alert side / age | confirmations | phase | bbwp | verde | media | guardian | ML RSI | last reasons |
|---|---|---|---|---|---|---|---|---|---|---|
| pro:H1 | flat | None / None | — | expansion | 75.8 | -10.89 | 12.46 | {'1d': 1, '1w': 1} | red | no_leader |
| pro:H2 | flat | None / None | — | expansion | 75.8 | -10.89 | 12.46 | {'1d': 1, '1w': 1} | red | no_leader |
| pro_1d:H1 | in_position | None / None | — | compression | 14.1 | 44.79 | 82.26 | {'1w': 1, '1M': 0} | green | phase_lost_suppressed_verde_favor, hold_follower_against |
| pro_1d:H2 | alert | short / 1 | {'ao': {'side': -1, 'bar': 1005, 'event': 'ao_turn_down'}, 'rsi': {'side': -1, 'bar': 1006, 'event': 'rsi_cross_50_down'}} | compression | 14.1 | 44.79 | 82.26 | {'1w': 1, '1M': 0} | green | entry_wait_bbwp_regime |

### Model's own short between 2026-09-15 and 2026-10-31

* **pro:H1**: ENTER short at 2026-10-22T08:00:00+00:00 close 82242.87, invalidation 84899.99 (invalidation_range), layer 1 616.7333 USDT (1R 19.9256), confirmations {'ao': {'side': -1, 'bar': 4621, 'event': 'ao_turn_down'}, 'rsi': {'side': -1, 'bar': 4621, 'event': 'rsi_cross_50_down'}}. Follow-up: 2026-10-22T12:00 hold add_rejected_min_gap; 2026-10-22T20:00 add_layer add_layer_follower_confirm; 2026-10-24T00:00 add_layer add_layer_follower_confirm; 2026-10-24T04:00 exit exit_phase_lost
* **pro:H2**: ENTER short at 2026-10-15T04:00:00+00:00 close 80925.0, invalidation 84166.67 (invalidation_range), layer 1 676.0918 USDT (1R 27.0827), confirmations {'macd': {'side': -1, 'bar': 4575, 'event': 'macd_cross_down'}, 'rsi': {'side': -1, 'bar': 4575, 'event': 'rsi_cross_50_down'}, 'ao': {'side': -1, 'bar': 4576, 'event': 'ao_zero_cross_down'}, 'adx': {'side': -1, 'bar': 4577, 'event': 'adx_turn_up_short'}}. Follow-up: 2026-10-16T16:00 exit exit_phase_lost
* **pro_1d:H1**: no short ENTER. States in window {'flat': 0, 'alert': 0, 'in_position': 47}; long entries 0; last reason codes: add_rejected_phase, hold_exit_incomplete, hold_follower_against, hold_no_follower_confirm, phase_lost_suppressed_verde_favor.
* **pro_1d:H2**: no short ENTER. States in window {'flat': 23, 'alert': 24, 'in_position': 0}; long entries 0; last reason codes: alert_replaced_opposite_leader, alert_waiting_confirmation, bbwp_ignition_repeat, entry_wait_bbwp_regime, konkorde_verde_turn_down, konkorde_verde_turn_up.

### Anchored replay: layer 1 short forced at `owner_bar` (§R2.c sizing, §R2.d invalidation), real rules after

* **H1**: layer 1 827.986 USDT at 82418.88, invalidation 85006.956084 (invalidation_atr), 1R 26.0 USDT. Events: 2026-10-10T04:00 exit exit_phase_lost; 2026-10-14T20:00 hold add_rejected_min_gap; 2026-10-15T00:00 hold add_rejected_min_gap; 2026-10-16T16:00 exit exit_phase_lost; 2026-10-22T12:00 hold add_rejected_min_gap; 2026-10-22T20:00 add_layer add_layer_follower_confirm; 2026-10-24T00:00 add_layer add_layer_follower_confirm; 2026-10-24T04:00 exit exit_phase_lost; 2026-10-31T04:00 hold add_rejected_phase; 2026-10-31T20:00 exit exit_rule_jeisson,exit_bbwp_red_turn,exit_konkorde_zero_cross_against. **EXIT exit_phase_lost** at 2026-10-10T00:00:00+00:00 price 82601.57: net -4.5713 USDT = -0.175821 R (1 layers).
* **H2**: layer 1 827.986 USDT at 82418.88, invalidation 85006.956084 (invalidation_atr), 1R 26.0 USDT. Events: 2026-10-10T04:00 exit exit_phase_lost; 2026-10-16T16:00 exit exit_phase_lost. **EXIT exit_phase_lost** at 2026-10-10T00:00:00+00:00 price 82601.57: net -4.5713 USDT = -0.175821 R (1 layers).

One trade; it validates nothing (§R2.g.5).

