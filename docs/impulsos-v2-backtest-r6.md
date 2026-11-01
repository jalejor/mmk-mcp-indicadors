# Impulsos v2 — round 6 results (ablations on the frozen 2.3.0 baseline: guardian ML RSI exit · snipper 10x isolated vs 5x cross)

Protocol: `docs/PREREG_IMPULSOS_v2_r6.md` (frozen before this run). Run 20261101T160537Z in the lab service `backtest`, harness `scripts/run_impulse_backtest_r6.py`. Raw JSON (every trade, pairing, time metrics): `r6_impulse_20261101T160537Z.json`. Window 2024-11-01 -> 2026-10-31 (730 days), IS/OOS split 2026-01-01.

## Data manifest

| symbol @ TF | rows | first open | last open | gaps | sha256 (12) | source |
|---|---|---|---|---|---|---|
| BTC/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `a9ec96296cf4` | cache |
| BTC/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `1fd23248b1c1` | cache |
| BTC/USDT@1w | 403 | 2019-02-04T00:00 | 2026-10-19T00:00 | 0 | `3c483695e2db` | cache |
| BTC/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `87e7dbf8ecdb` | cache |

## Cells (1R = layer-1 risk; r4 verdict unchanged: GO iff n >= 30, n_oos >= 10, exp OOS > 0, PF >= 1.2, liq 0, DD < 35 %)

| Cell | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | win | max DD USDT (% start) | net USDT | **r4 verdict** | r2 §6 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4h long **pro:A_on** (5x cross, 1300 USDT) | 7 (4/3) | -0.140 | [-0.858, 0.645] | 0.187 | -0.577 | 0.73 | 29% | 77.22 (5.94%) | -26.65 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 4h short **pro:A_on** (5x cross, 1300 USDT) | 7 (5/2) | -0.201 | [-1.028, 0.808] | -0.526 | 0.612 | 0.69 | 29% | 84.86 (6.53%) | -38.57 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 4h long **pro:A_exit_off** (5x cross, 1300 USDT) | 2 (2/0) | 0.525 | [-1.244, 2.294] | 0.525 | — | 1.84 | 50% | 33.83 (2.6%) | 25.81 | INCONCLUSIVE (n_total=2 < 30) | INCONCLUSIVE |
| 4h short **pro:A_exit_off** (5x cross, 1300 USDT) | 3 (3/0) | 0.065 | [-1.908, 2.373] | 0.065 | — | 1.09 | 33% | 57.45 (4.42%) | 2.74 | INCONCLUSIVE (n_total=3 < 30) | INCONCLUSIVE |
| 4h long **pro:A_both_off** (5x cross, 1300 USDT) | 2 (2/0) | 0.525 | [-1.244, 2.294] | 0.525 | — | 1.84 | 50% | 33.83 (2.6%) | 25.81 | INCONCLUSIVE (n_total=2 < 30) | INCONCLUSIVE |
| 4h short **pro:A_both_off** (5x cross, 1300 USDT) | 3 (3/0) | 0.065 | [-1.908, 2.373] | 0.065 | — | 1.09 | 33% | 57.45 (4.42%) | 2.74 | INCONCLUSIVE (n_total=3 < 30) | INCONCLUSIVE |
| 4h long **pro:A_spec_on** (5x cross, 1300 USDT) | 4 (2/2) | 0.080 | [-0.841, 1.056] | 1.000 | -0.841 | 1.19 | 50% | 41.47 (3.19%) | 10.45 | INCONCLUSIVE (n_total=4 < 30) | INCONCLUSIVE |
| 4h short **pro:A_spec_on** (5x cross, 1300 USDT) | 7 (5/2) | -0.722 | [-1.492, -0.099] | -0.644 | -0.917 | 0.06 | 29% | 131.44 (10.11%) | -131.44 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 4h long **pro:A_spec_exit_off** (5x cross, 1300 USDT) | 1 (1/0) | 1.774 | [1.774, 1.774] | 1.774 | — | inf | 100% | 0.0 (0.0%) | 46.11 | INCONCLUSIVE (n_total=1 < 30) | INCONCLUSIVE |
| 4h short **pro:A_spec_exit_off** (5x cross, 1300 USDT) | 3 (3/0) | -0.309 | [-2.742, 1.904] | -0.309 | — | 0.67 | 33% | 76.13 (5.86%) | -27.76 | INCONCLUSIVE (n_total=3 < 30) | INCONCLUSIVE |
| 1h long **snipper:A_on** (10x isolated, 1700 USDT) | 31 (20/11) | -0.099 | [-0.684, 0.566] | -0.100 | -0.097 | 0.88 | 29% | 325.6 (19.15%) | -127.72 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | NO-PASS |
| 1h short **snipper:A_on** (10x isolated, 1700 USDT) | 34 (21/13) | -0.273 | [-0.837, 0.412] | -0.338 | -0.166 | 0.70 | 24% | 320.69 (18.86%) | -308.44 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | NO-PASS |
| 1h long **snipper:A_exit_off** (10x isolated, 1700 USDT) | 6 (4/2) | -0.971 | [-2.836, 1.775] | -0.412 | -2.088 | 0.49 | 17% | 412.26 (24.25%) | -225.14 | INCONCLUSIVE (n_total=6 < 30) | INCONCLUSIVE |
| 1h short **snipper:A_exit_off** (10x isolated, 1700 USDT) | 8 (5/3) | 1.220 | [-2.551, 5.447] | 0.926 | 1.711 | 1.92 | 50% | 319.52 (18.8%) | 261.94 | INCONCLUSIVE (n_total=8 < 30) | INCONCLUSIVE |
| 1h long **snipper:A_both_off** (10x isolated, 1700 USDT) | 10 (6/4) | -1.332 | [-2.969, 0.610] | -1.126 | -1.641 | 0.30 | 10% | 635.15 (37.36%) | -448.03 | INCONCLUSIVE (n_total=10 < 30) | INCONCLUSIVE |
| 1h short **snipper:A_both_off** (10x isolated, 1700 USDT) | 8 (5/3) | 1.210 | [-2.150, 6.145] | 0.686 | 2.083 | 2.00 | 38% | 233.1 (13.71%) | 234.51 | INCONCLUSIVE (n_total=8 < 30) | INCONCLUSIVE |
| 1h long **snipper:A_spec_on** (10x isolated, 1700 USDT) | 25 (14/11) | 0.227 | [-0.391, 0.820] | 0.181 | 0.285 | 1.37 | 36% | 224.97 (13.23%) | 146.4 | INCONCLUSIVE (n_total=25 < 30) | INCONCLUSIVE |
| 1h short **snipper:A_spec_on** (10x isolated, 1700 USDT) | 30 (20/10) | -0.105 | [-0.742, 0.705] | -0.300 | 0.286 | 0.87 | 30% | 263.63 (15.51%) | -140.7 | NO-GO (PF >= 1.2; liquidations == 0) | NO-PASS |
| 1h long **snipper:A_spec_exit_off** (10x isolated, 1700 USDT) | 7 (4/3) | -1.035 | [-2.981, 1.585] | -0.369 | -1.923 | 0.44 | 14% | 459.02 (27.0%) | -271.9 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 1h short **snipper:A_spec_exit_off** (10x isolated, 1700 USDT) | 8 (5/3) | 0.796 | [-1.979, 4.765] | 0.659 | 1.025 | 1.67 | 50% | 251.12 (14.77%) | 171.51 | INCONCLUSIVE (n_total=8 < 30) | INCONCLUSIVE |
| 1h long **snipper:B_risk_iso10:base** (10x isolated, 1700 USDT) | 31 (20/11) | -0.099 | [-0.684, 0.566] | -0.100 | -0.097 | 0.88 | 29% | 325.6 (19.15%) | -127.72 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | NO-PASS |
| 1h short **snipper:B_risk_iso10:base** (10x isolated, 1700 USDT) | 34 (21/13) | -0.273 | [-0.837, 0.412] | -0.338 | -0.166 | 0.70 | 24% | 320.69 (18.86%) | -308.44 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | NO-PASS |
| 1h long **snipper:B_risk_cross5:base** (5x cross, 1700 USDT) | 31 (20/11) | -0.099 | [-0.684, 0.566] | -0.100 | -0.097 | 0.88 | 29% | 325.73 (19.16%) | -127.77 | NO-GO (expectancy_oos > 0; PF >= 1.2) | NO-PASS |
| 1h short **snipper:B_risk_cross5:base** (5x cross, 1700 USDT) | 34 (21/13) | -0.271 | [-0.836, 0.413] | -0.338 | -0.163 | 0.70 | 24% | 319.57 (18.8%) | -307.3 | NO-GO (expectancy_oos > 0; PF >= 1.2) | NO-PASS |
| 1h long **snipper:B_risk_iso10:bbwp_fresh_blue** (10x isolated, 1700 USDT) | 29 (18/11) | -0.108 | [-0.802, 0.565] | -0.123 | -0.083 | 0.88 | 28% | 414.75 (24.4%) | -154.49 | INCONCLUSIVE (n_total=29 < 30) | INCONCLUSIVE |
| 1h short **snipper:B_risk_iso10:bbwp_fresh_blue** (10x isolated, 1700 USDT) | 22 (11/11) | -0.140 | [-1.019, 1.011] | -0.382 | 0.102 | 0.85 | 32% | 237.97 (14.0%) | -107.58 | INCONCLUSIVE (n_total=22 < 30) | INCONCLUSIVE |
| 1h long **snipper:B_risk_cross5:bbwp_fresh_blue** (5x cross, 1700 USDT) | 29 (18/11) | -0.108 | [-0.802, 0.565] | -0.123 | -0.083 | 0.88 | 28% | 414.94 (24.41%) | -154.53 | INCONCLUSIVE (n_total=29 < 30) | INCONCLUSIVE |
| 1h short **snipper:B_risk_cross5:bbwp_fresh_blue** (5x cross, 1700 USDT) | 22 (11/11) | -0.138 | [-1.017, 1.013] | -0.382 | 0.106 | 0.86 | 32% | 237.97 (14.0%) | -106.3 | INCONCLUSIVE (n_total=22 < 30) | INCONCLUSIVE |
| 1h long **snipper:B_risk_iso10:adx_turn** (10x isolated, 1700 USDT) | 25 (14/11) | 0.198 | [-0.748, 1.297] | -0.395 | 0.953 | 1.23 | 28% | 429.95 (25.29%) | 163.41 | INCONCLUSIVE (n_total=25 < 30) | INCONCLUSIVE |
| 1h short **snipper:B_risk_iso10:adx_turn** (10x isolated, 1700 USDT) | 28 (19/9) | 0.507 | [-0.613, 2.107] | -0.198 | 1.996 | 1.62 | 32% | 234.34 (13.78%) | 392.97 | INCONCLUSIVE (n_total=28 < 30) | INCONCLUSIVE |
| 1h long **snipper:B_risk_cross5:adx_turn** (5x cross, 1700 USDT) | 25 (14/11) | 0.201 | [-0.745, 1.300] | -0.389 | 0.953 | 1.24 | 28% | 427.72 (25.16%) | 166.42 | INCONCLUSIVE (n_total=25 < 30) | INCONCLUSIVE |
| 1h short **snipper:B_risk_cross5:adx_turn** (5x cross, 1700 USDT) | 28 (19/9) | 0.507 | [-0.613, 2.107] | -0.198 | 1.996 | 1.62 | 32% | 234.7 (13.81%) | 393.43 | INCONCLUSIVE (n_total=28 < 30) | INCONCLUSIVE |
| 1h long **snipper:B_margin_iso10:base** (10x isolated, 1700 USDT) | 31 (20/11) | -0.072 | [-0.675, 0.624] | -0.095 | -0.030 | 0.91 | 29% | 459.57 (27.03%) | 145.05 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | NO-PASS |
| 1h short **snipper:B_margin_iso10:base** (10x isolated, 1700 USDT) | 34 (21/13) | -0.271 | [-0.832, 0.412] | -0.336 | -0.166 | 0.70 | 24% | 666.68 (39.22%) | -594.03 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0; maxDD < 35% of start) | NO-PASS |
| 1h long **snipper:B_margin_cross5:base** (5x cross, 1700 USDT) | 31 (20/11) | -0.072 | [-0.675, 0.624] | -0.095 | -0.030 | 0.91 | 29% | 242.68 (14.28%) | 93.44 | NO-GO (expectancy_oos > 0; PF >= 1.2) | NO-PASS |
| 1h short **snipper:B_margin_cross5:base** (5x cross, 1700 USDT) | 34 (21/13) | -0.270 | [-0.831, 0.415] | -0.336 | -0.163 | 0.70 | 24% | 326.11 (19.18%) | -270.18 | NO-GO (expectancy_oos > 0; PF >= 1.2) | NO-PASS |
| 1h long **snipper:B_margin_iso10:bbwp_fresh_blue** (10x isolated, 1700 USDT) | 29 (18/11) | -0.113 | [-0.804, 0.558] | -0.123 | -0.096 | 0.88 | 28% | 739.55 (43.5%) | -43.35 | INCONCLUSIVE (n_total=29 < 30) | INCONCLUSIVE |
| 1h short **snipper:B_margin_iso10:bbwp_fresh_blue** (10x isolated, 1700 USDT) | 22 (11/11) | -0.141 | [-1.020, 1.010] | -0.385 | 0.102 | 0.85 | 32% | 482.8 (28.4%) | -136.23 | INCONCLUSIVE (n_total=22 < 30) | INCONCLUSIVE |
| 1h long **snipper:B_margin_cross5:bbwp_fresh_blue** (5x cross, 1700 USDT) | 29 (18/11) | -0.113 | [-0.804, 0.558] | -0.123 | -0.096 | 0.88 | 28% | 376.57 (22.15%) | -0.06 | INCONCLUSIVE (n_total=29 < 30) | INCONCLUSIVE |
| 1h short **snipper:B_margin_cross5:bbwp_fresh_blue** (5x cross, 1700 USDT) | 22 (11/11) | -0.140 | [-1.018, 1.012] | -0.385 | 0.106 | 0.85 | 32% | 236.14 (13.89%) | -26.92 | INCONCLUSIVE (n_total=22 < 30) | INCONCLUSIVE |

## Books and R per unit of time (one ledger per run, long + short)

| run | tf | book | trades | net R | R / 30 d | R / day held | trades / 30 d | median hold h | time in market | avg layers | max exposure x | layers sized down | equity final | return | max DD equity USDT (%) | liquidations | funding / fees USDT | exit mix |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:A_on | 4h | 5x cross | 14 | -2.388 | -0.098 | -0.0038 | 0.58 | 1002.0 | 85.5% | 2.14 | 0.776 | 0 | 1234.78 | -5.02% | 204.79 (14.34%) | 0 | 57.51 / 20.59 | {'exit_ctx_mlrsi_against': 10, 'exit_invalidation': 2, 'exit_rule_jeisson': 2} |
| pro:A_exit_off | 4h | 5x cross | 5 | 1.246 | 0.051 | 0.0018 | 0.21 | 1036.0 | 95.9% | 2.6 | 0.776 | 0 | 1328.55 | 2.2% | 117.2 (8.52%) | 0 | 55.31 / 8.09 | {'exit_rule_jeisson': 3, 'exit_invalidation': 2} |
| pro:A_both_off | 4h | 5x cross | 5 | 1.246 | 0.051 | 0.0018 | 0.21 | 1036.0 | 95.9% | 2.6 | 0.776 | 0 | 1328.55 | 2.2% | 117.2 (8.52%) | 0 | 55.31 / 8.09 | {'exit_rule_jeisson': 3, 'exit_invalidation': 2} |
| pro:A_spec_on | 4h | 5x cross | 11 | -4.738 | -0.195 | -0.0078 | 0.45 | 1500.0 | 83.5% | 2.18 | 0.685 | 0 | 1179.01 | -9.31% | 224.17 (15.98%) | 0 | 49.96 / 14.26 | {'exit_ctx_mlrsi_against': 7, 'exit_invalidation': 2, 'exit_rule_jeisson': 2} |
| pro:A_spec_exit_off | 4h | 5x cross | 4 | 0.845 | 0.035 | 0.0012 | 0.16 | 3816.0 | 95.2% | 2.5 | 0.685 | 0 | 1318.35 | 1.41% | 116.18 (8.28%) | 0 | 56.03 / 6.22 | {'exit_rule_jeisson': 3, 'exit_invalidation': 1} |
| snipper:A_on | 1h | 10x isolated | 65 | -12.323 | -0.506 | -0.0217 | 2.67 | 164.0 | 77.8% | 2.37 | 2.183 | 0 | 1263.84 | -25.66% | 618.33 (33.66%) | 1 | 176.67 / 329.16 | {'exit_invalidation': 19, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'liquidation': 1, 'end_of_data': 1} |
| snipper:A_exit_off | 1h | 10x isolated | 14 | 3.937 | 0.162 | 0.0057 | 0.58 | 271.0 | 95.3% | 2.64 | 2.049 | 0 | 1736.8 | 2.16% | 614.7 (26.38%) | 1 | 256.88 / 113.46 | {'exit_invalidation': 7, 'exit_rule_jeisson': 5, 'liquidation': 1, 'end_of_data': 1} |
| snipper:A_both_off | 1h | 10x isolated | 18 | -3.642 | -0.15 | -0.0052 | 0.74 | 87.5 | 95.3% | 2.22 | 2.049 | 0 | 1486.48 | -12.56% | 662.01 (32.41%) | 1 | 244.52 / 125.63 | {'exit_invalidation': 11, 'exit_rule_jeisson': 5, 'liquidation': 1, 'end_of_data': 1} |
| snipper:A_spec_on | 1h | 10x isolated | 55 | 2.522 | 0.104 | 0.0045 | 2.26 | 176.0 | 76.3% | 2.29 | 2.129 | 0 | 1705.71 | 0.34% | 327.86 (18.12%) | 2 | 160.32 / 283.95 | {'exit_invalidation': 14, 'exit_ctx_mlrsi_against': 32, 'exit_rule_jeisson': 6, 'liquidation': 2, 'end_of_data': 1} |
| snipper:A_spec_exit_off | 1h | 10x isolated | 15 | -0.874 | -0.036 | -0.0013 | 0.62 | 192.0 | 94.8% | 2.33 | 1.678 | 0 | 1599.61 | -5.91% | 524.57 (25.16%) | 1 | 201.89 / 98.6 | {'exit_invalidation': 8, 'exit_rule_jeisson': 5, 'liquidation': 1, 'end_of_data': 1} |
| snipper:B_risk_iso10:base | 1h | 10x isolated | 65 | -12.323 | -0.506 | -0.0217 | 2.67 | 164.0 | 77.8% | 2.37 | 2.183 | 0 | 1263.84 | -25.66% | 618.33 (33.66%) | 1 | 176.67 / 329.16 | {'exit_invalidation': 19, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'liquidation': 1, 'end_of_data': 1} |
| snipper:B_risk_cross5:base | 1h | 5x cross | 65 | -12.28 | -0.505 | -0.0216 | 2.67 | 164.0 | 77.8% | 2.37 | 2.183 | 0 | 1264.93 | -25.59% | 617.28 (33.6%) | 0 | 176.72 / 328.07 | {'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'end_of_data': 1} |
| snipper:B_risk_iso10:bbwp_fresh_blue | 1h | 10x isolated | 51 | -6.213 | -0.255 | -0.0138 | 2.1 | 148.0 | 61.6% | 2.45 | 2.278 | 0 | 1437.93 | -15.42% | 689.92 (35.22%) | 1 | 171.78 / 304.72 | {'exit_ctx_mlrsi_against': 26, 'exit_invalidation': 20, 'exit_rule_jeisson': 3, 'liquidation': 1, 'end_of_data': 1} |
| snipper:B_risk_cross5:bbwp_fresh_blue | 1h | 5x cross | 51 | -6.17 | -0.254 | -0.0137 | 2.1 | 148.0 | 61.6% | 2.45 | 2.278 | 0 | 1439.17 | -15.34% | 688.82 (35.16%) | 0 | 171.83 / 303.56 | {'exit_ctx_mlrsi_against': 26, 'exit_invalidation': 21, 'exit_rule_jeisson': 3, 'end_of_data': 1} |
| snipper:B_risk_iso10:adx_turn | 1h | 10x isolated | 53 | 19.163 | 0.788 | 0.0438 | 2.18 | 146.0 | 59.9% | 2.26 | 2.183 | 0 | 2256.39 | 32.73% | 584.58 (30.46%) | 1 | 184.94 / 330.62 | {'exit_invalidation': 22, 'exit_ctx_mlrsi_against': 24, 'exit_rule_jeisson': 5, 'liquidation': 1, 'end_of_data': 1} |
| snipper:B_risk_cross5:adx_turn | 1h | 5x cross | 53 | 19.238 | 0.791 | 0.044 | 2.18 | 146.0 | 59.9% | 2.26 | 2.183 | 0 | 2259.85 | 32.93% | 585.48 (30.46%) | 0 | 185.22 / 329.93 | {'exit_invalidation': 23, 'exit_ctx_mlrsi_against': 24, 'exit_rule_jeisson': 5, 'end_of_data': 1} |
| snipper:B_margin_iso10:base | 1h | 10x isolated | 65 | -11.445 | -0.47 | -0.0201 | 2.67 | 164.0 | 77.8% | 2.4 | 2.005 | 0 | 1251.03 | -26.41% | 1086.98 (47.77%) | 1 | 302.17 / 510.72 | {'exit_invalidation': 19, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'liquidation': 1, 'end_of_data': 1} |
| snipper:B_margin_cross5:base | 1h | 5x cross | 65 | -11.402 | -0.469 | -0.0201 | 2.67 | 164.0 | 77.8% | 2.4 | 1.002 | 0 | 1523.26 | -10.4% | 506.03 (25.42%) | 0 | 165.26 / 272.53 | {'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'end_of_data': 1} |
| snipper:B_margin_iso10:bbwp_fresh_blue | 1h | 10x isolated | 51 | -6.381 | -0.262 | -0.0142 | 2.1 | 148.0 | 61.6% | 2.47 | 2.001 | 0 | 1520.42 | -10.56% | 1103.48 (47.5%) | 1 | 264.84 / 443.24 | {'exit_ctx_mlrsi_against': 26, 'exit_invalidation': 20, 'exit_rule_jeisson': 3, 'liquidation': 1, 'end_of_data': 1} |
| snipper:B_margin_cross5:bbwp_fresh_blue | 1h | 5x cross | 51 | -6.339 | -0.261 | -0.0141 | 2.1 | 148.0 | 61.6% | 2.47 | 1.002 | 0 | 1673.02 | -1.59% | 518.94 (25.8%) | 0 | 139.21 / 226.4 | {'exit_ctx_mlrsi_against': 26, 'exit_invalidation': 21, 'exit_rule_jeisson': 3, 'end_of_data': 1} |

## Part A — guardian ML RSI exit: ON vs OFF (prereg r6 §6 A, sides pooled; `A_on` = as run in r4b/r5 with the trigger gate OFF, E20; `A_spec_*` = rule doc as written, trigger gate ON)

| profile | pair | variant | n | exp. R all | exp. IS | exp. OOS | PF | liq | book return | max DD % | exit mix | common entries | mean ΔR (off − on) on common | longer without the exit | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pro | A_on->A_exit_off | A_on | 14 | -0.171 | -0.209 | -0.101 | 0.7 | 0 | -5.02% | 14.34% | {'exit_ctx_mlrsi_against': 10, 'exit_invalidation': 2, 'exit_rule_jeisson': 2} | — | — | — | — |
| pro | A_on->A_exit_off | A_exit_off | 5 | 0.249 | 0.249 | — | 1.36 | 0 | 2.2% | 8.52% | {'exit_rule_jeisson': 3, 'exit_invalidation': 2} | 5 (+0 new / 9 lost) | 0.571 | 3 | **INCONCLUSIVE** (n on/off 14/5, n_oos 5/0) |
| pro | A_on->A_both_off | A_on | 14 | -0.171 | -0.209 | -0.101 | 0.7 | 0 | -5.02% | 14.34% | {'exit_ctx_mlrsi_against': 10, 'exit_invalidation': 2, 'exit_rule_jeisson': 2} | — | — | — | — |
| pro | A_on->A_both_off | A_both_off | 5 | 0.249 | 0.249 | — | 1.36 | 0 | 2.2% | 8.52% | {'exit_rule_jeisson': 3, 'exit_invalidation': 2} | 5 (+0 new / 9 lost) | 0.571 | 3 | **INCONCLUSIVE** (n on/off 14/5, n_oos 5/0) |
| pro | A_spec_on->A_spec_exit_off | A_spec_on | 11 | -0.431 | -0.174 | -0.879 | 0.33 | 0 | -9.31% | 15.98% | {'exit_ctx_mlrsi_against': 7, 'exit_invalidation': 2, 'exit_rule_jeisson': 2} | — | — | — | — |
| pro | A_spec_on->A_spec_exit_off | A_spec_exit_off | 4 | 0.211 | 0.211 | — | 1.3 | 0 | 1.41% | 8.28% | {'exit_rule_jeisson': 3, 'exit_invalidation': 1} | 4 (+0 new / 7 lost) | 0.784 | 2 | **INCONCLUSIVE** (n on/off 11/4, n_oos 4/0) |
| snipper | A_on->A_exit_off | A_on | 65 | -0.190 | -0.222 | -0.135 | 0.78 | 1 | -25.66% | 33.66% | {'exit_invalidation': 19, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'liquidation': 1, 'end_of_data': 1} | — | — | — | — |
| snipper | A_on->A_exit_off | A_exit_off | 14 | 0.281 | 0.331 | 0.191 | 1.18 | 1 | 2.16% | 26.38% | {'exit_invalidation': 7, 'exit_rule_jeisson': 5, 'liquidation': 1, 'end_of_data': 1} | 10 (+4 new / 55 lost) | -0.464 | 7 | **INCONCLUSIVE** (n on/off 65/14, n_oos 24/5) |
| snipper | A_on->A_both_off | A_on | 65 | -0.190 | -0.222 | -0.135 | 0.78 | 1 | -25.66% | 33.66% | {'exit_invalidation': 19, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'liquidation': 1, 'end_of_data': 1} | — | — | — | — |
| snipper | A_on->A_both_off | A_both_off | 18 | -0.202 | -0.302 | -0.045 | 0.87 | 1 | -12.56% | 32.41% | {'exit_invalidation': 11, 'exit_rule_jeisson': 5, 'liquidation': 1, 'end_of_data': 1} | 7 (+11 new / 58 lost) | 0.125 | 4 | **INCONCLUSIVE** (n on/off 65/18, n_oos 24/7) |
| snipper | A_spec_on->A_spec_exit_off | A_spec_on | 55 | 0.046 | -0.102 | 0.285 | 1.06 | 2 | 0.34% | 18.12% | {'exit_invalidation': 14, 'exit_ctx_mlrsi_against': 32, 'exit_rule_jeisson': 6, 'liquidation': 2, 'end_of_data': 1} | — | — | — | — |
| snipper | A_spec_on->A_spec_exit_off | A_spec_exit_off | 15 | -0.058 | 0.202 | -0.449 | 0.96 | 1 | -5.91% | 25.16% | {'exit_invalidation': 8, 'exit_rule_jeisson': 5, 'liquidation': 1, 'end_of_data': 1} | 11 (+4 new / 44 lost) | -0.430 | 6 | **INCONCLUSIVE** (n on/off 55/15, n_oos 21/6) |

## Part B — SNIPPER 1h: 10x isolated vs 5x cross (prereg r6 §6 B; neither is a GO unless its cells are)

| sizing | entry | book | n | net R | R / 30 d | R / day held | liq | return | max DD % | trades identical? | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| risk | base | 10x isolated | 65 | -12.323 | -0.506 | -0.0217 | 1 | -25.66% | 33.66% | no | **CROSS5_SAFER** (liquidations_iso == 0; sum_r_iso >= sum_r_cross; maxDD%_iso <= maxDD%_cross) |
| risk | base | 5x cross | 65 | -12.28 | -0.505 | -0.0216 | 0 | -25.59% | 33.6% | no |  |
| risk | bbwp_fresh_blue | 10x isolated | 51 | -6.213 | -0.255 | -0.0138 | 1 | -15.42% | 35.22% | no | **CROSS5_SAFER** (liquidations_iso == 0; sum_r_iso >= sum_r_cross; maxDD%_iso <= maxDD%_cross) |
| risk | bbwp_fresh_blue | 5x cross | 51 | -6.17 | -0.254 | -0.0137 | 0 | -15.34% | 35.16% | no |  |
| risk | adx_turn | 10x isolated | 53 | 19.163 | 0.788 | 0.0438 | 1 | 32.73% | 30.46% | no | **CROSS5_SAFER** (liquidations_iso == 0; sum_r_iso >= sum_r_cross) |
| risk | adx_turn | 5x cross | 53 | 19.238 | 0.791 | 0.044 | 0 | 32.93% | 30.46% | no |  |
| margin | base | 10x isolated | 65 | -11.445 | -0.47 | -0.0201 | 1 | -26.41% | 47.77% | no | **CROSS5_SAFER** (liquidations_iso == 0; sum_r_iso >= sum_r_cross; maxDD%_iso <= maxDD%_cross) |
| margin | base | 5x cross | 65 | -11.402 | -0.469 | -0.0201 | 0 | -10.4% | 25.42% | no |  |
| margin | bbwp_fresh_blue | 10x isolated | 51 | -6.381 | -0.262 | -0.0142 | 1 | -10.56% | 47.5% | no | **CROSS5_SAFER** (liquidations_iso == 0; sum_r_iso >= sum_r_cross; maxDD%_iso <= maxDD%_cross) |
| margin | bbwp_fresh_blue | 5x cross | 51 | -6.339 | -0.261 | -0.0141 | 0 | -1.59% | 25.8% | no |  |

## Baseline continuity with round 5 (the `A_on` cells must reproduce the r5 `base` cells)

* pro: **identical** — long r6 n 7 / -26.65 USDT vs r5 n 7 / -26.65 USDT; short r6 n 7 / -38.57 USDT vs r5 n 7 / -38.57 USDT
* snipper: **identical** — long r6 n 31 / -127.72 USDT vs r5 n 31 / -127.72 USDT; short r6 n 34 / -308.44 USDT vs r5 n 34 / -308.44 USDT
