# Impulsos v2 — round 5 backtest results (`impulse-2.3.0`: ENTRY filters on the frozen 2.2.0 chain)

Protocol: `docs/PREREG_IMPULSOS_v2_r5.md` (frozen before this run). Run 20261101T152827Z in the lab service `backtest`, harness `scripts/run_impulse_backtest_r5.py`. Raw JSON (every trade, flags, classifier, owner bar): `r5_impulse_20261101T152827Z.json`.

## Data manifest

| symbol @ TF | rows | first open | last open | gaps | sha256 (12) | source |
|---|---|---|---|---|---|---|
| BTC/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `a9ec96296cf4` | cache |
| BTC/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `1fd23248b1c1` | cache |
| BTC/USDT@1w | 403 | 2019-02-04T00:00 | 2026-10-19T00:00 | 0 | `3c483695e2db` | cache |
| BTC/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `87e7dbf8ecdb` | cache |
| BTC/USDT@1M | 100 | 2018-07-01T00:00 | 2026-10-01T00:00 | 0 | `2564ebf1f1c1` | cache |
| ETH/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `8e918749b2f3` | exchange |
| ETH/USDT@1w | 403 | 2019-02-04T00:00 | 2026-10-19T00:00 | 0 | `cbc218c025bc` | exchange |
| ETH/USDT@1M | 100 | 2018-07-01T00:00 | 2026-10-01T00:00 | 0 | `34b4e8c1e5b4` | exchange |
| SOL/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `fed745e682a1` | exchange |
| SOL/USDT@1w | 279 | 2021-06-21T00:00 | 2026-10-19T00:00 | 0 | `4491cd4d33c0` | exchange |
| SOL/USDT@1M | 65 | 2021-06-01T00:00 | 2026-10-01T00:00 | 0 | `c82ab38c9813` | exchange |

## Cells (1R = layer-1 risk = 2 % E0; IS 2024-11 -> 2025-12, OOS 2026-01 -> 2026-10; `base` = 2.2.0 entry)

r4 verdict (unchanged from round 4b): GO iff n >= 30, n_oos >= 10, expectancy OOS > 0, PF >= 1.2, liquidations 0, max DD (cumulative net USDT of the cell) < 35 % of one book's start. `pro_1d` cells pool BTC + ETH + SOL (one book per symbol; DD % refers to one book's equity). r2 §6 = round-2 R-based verdict, for continuity.

| Cell | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | win | max DD USDT (% start) | net USDT | **r4 verdict** | r2 §6 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 4h long **pro:base** (5x cross, 1300 USDT) | 7 (4/3) | -0.140 | [-0.858, 0.645] | 0.187 | -0.577 | 0.73 | 29% | 77.22 (5.94%) | -26.65 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 4h short **pro:base** (5x cross, 1300 USDT) | 7 (5/2) | -0.201 | [-1.028, 0.808] | -0.526 | 0.612 | 0.69 | 29% | 84.86 (6.53%) | -38.57 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 4h long **pro:adx_turn** (5x cross, 1300 USDT) | 3 (1/2) | 1.104 | [-0.552, 3.970] | 3.970 | -0.329 | 6.04 | 33% | 16.83 (1.29%) | 86.39 | INCONCLUSIVE (n_total=3 < 30) | INCONCLUSIVE |
| 4h short **pro:adx_turn** (5x cross, 1300 USDT) | 4 (2/2) | -1.156 | [-2.183, 0.101] | -0.925 | -1.387 | 0.13 | 25% | 126.73 (9.75%) | -126.73 | INCONCLUSIVE (n_total=4 < 30) | INCONCLUSIVE |
| 4h long **pro:adx_turn_origin** (5x cross, 1300 USDT) | 2 (1/1) | 1.271 | [-1.428, 3.970] | 3.970 | -1.428 | 2.78 | 50% | 39.98 (3.08%) | 63.24 | INCONCLUSIVE (n_total=2 < 30) | INCONCLUSIVE |
| 4h short **pro:adx_turn_origin** (5x cross, 1300 USDT) | 4 (2/2) | 0.008 | [-0.751, 0.766] | -0.055 | 0.070 | 1.02 | 50% | 23.11 (1.78%) | 0.1 | INCONCLUSIVE (n_total=4 < 30) | INCONCLUSIVE |
| 4h long **pro:ao_divergence** (5x cross, 1300 USDT) | 3 (2/1) | 2.460 | [-0.149, 4.934] | 2.393 | 2.594 | 50.65 | 67% | 3.86 (0.3%) | 196.57 | INCONCLUSIVE (n_total=3 < 30) | INCONCLUSIVE |
| 4h short **pro:ao_divergence** (5x cross, 1300 USDT) | 1 (1/0) | -0.908 | [-0.908, -0.908] | -0.908 | — | 0.00 | 0% | 25.86 (1.99%) | -25.86 | INCONCLUSIVE (n_total=1 < 30) | INCONCLUSIVE |
| 4h long **pro:ao_divergence_any_tf** (5x cross, 1300 USDT) | 2 (1/1) | 3.764 | [2.594, 4.934] | 4.934 | 2.594 | inf | 100% | 0.0 (0.0%) | 200.15 | INCONCLUSIVE (n_total=2 < 30) | INCONCLUSIVE |
| 4h short **pro:ao_divergence_any_tf** (5x cross, 1300 USDT) | 2 (2/0) | -0.564 | [-0.908, -0.220] | -0.564 | — | 0.00 | 0% | 31.56 (2.43%) | -31.56 | INCONCLUSIVE (n_total=2 < 30) | INCONCLUSIVE |
| 4h long **pro:bbwp_fresh** (5x cross, 1300 USDT) | 6 (4/2) | 0.352 | [-0.749, 1.907] | 0.948 | -0.841 | 1.78 | 33% | 55.68 (4.28%) | 51.34 | INCONCLUSIVE (n_total=6 < 30) | INCONCLUSIVE |
| 4h short **pro:bbwp_fresh** (5x cross, 1300 USDT) | 4 (2/2) | -0.529 | [-1.052, 0.275] | -0.029 | -1.029 | 0.24 | 25% | 56.95 (4.38%) | -56.95 | INCONCLUSIVE (n_total=4 < 30) | INCONCLUSIVE |
| 4h long **pro:bbwp_fresh_blue** (5x cross, 1300 USDT) | 5 (4/1) | 0.532 | [-0.788, 2.325] | 0.948 | -1.130 | 2.23 | 40% | 41.24 (3.17%) | 65.78 | INCONCLUSIVE (n_total=5 < 30) | INCONCLUSIVE |
| 4h short **pro:bbwp_fresh_blue** (5x cross, 1300 USDT) | 4 (2/2) | -0.529 | [-1.052, 0.275] | -0.029 | -1.029 | 0.24 | 25% | 56.95 (4.38%) | -56.95 | INCONCLUSIVE (n_total=4 < 30) | INCONCLUSIVE |
| 1h long **snipper:base** (10x isolated, 1700 USDT) | 31 (20/11) | -0.099 | [-0.684, 0.566] | -0.100 | -0.097 | 0.88 | 29% | 325.6 (19.15%) | -127.72 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | NO-PASS |
| 1h short **snipper:base** (10x isolated, 1700 USDT) | 34 (21/13) | -0.273 | [-0.837, 0.412] | -0.338 | -0.166 | 0.70 | 24% | 320.69 (18.86%) | -308.44 | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | NO-PASS |
| 1h long **snipper:adx_turn** (10x isolated, 1700 USDT) | 25 (14/11) | 0.198 | [-0.748, 1.297] | -0.395 | 0.953 | 1.23 | 28% | 429.95 (25.29%) | 163.41 | INCONCLUSIVE (n_total=25 < 30) | INCONCLUSIVE |
| 1h short **snipper:adx_turn** (10x isolated, 1700 USDT) | 28 (19/9) | 0.507 | [-0.613, 2.107] | -0.198 | 1.996 | 1.62 | 32% | 234.34 (13.78%) | 392.97 | INCONCLUSIVE (n_total=28 < 30) | INCONCLUSIVE |
| 1h long **snipper:adx_turn_origin** (10x isolated, 1700 USDT) | 13 (8/5) | -0.057 | [-0.988, 1.047] | -0.213 | 0.192 | 0.93 | 23% | 113.83 (6.7%) | -46.77 | INCONCLUSIVE (n_total=13 < 30) | INCONCLUSIVE |
| 1h short **snipper:adx_turn_origin** (10x isolated, 1700 USDT) | 20 (12/8) | -0.581 | [-1.139, 0.099] | -0.939 | -0.044 | 0.38 | 25% | 404.53 (23.8%) | -342.75 | INCONCLUSIVE (n_total=20 < 30) | INCONCLUSIVE |
| 1h long **snipper:ao_divergence** (10x isolated, 1700 USDT) | 9 (6/3) | 0.104 | [-1.007, 1.272] | 0.321 | -0.329 | 1.17 | 44% | 129.33 (7.61%) | 19.97 | INCONCLUSIVE (n_total=9 < 30) | INCONCLUSIVE |
| 1h short **snipper:ao_divergence** (10x isolated, 1700 USDT) | 8 (4/4) | 1.088 | [-1.017, 4.004] | -0.578 | 2.753 | 2.62 | 38% | 84.81 (4.99%) | 285.53 | INCONCLUSIVE (n_total=8 < 30) | INCONCLUSIVE |
| 1h long **snipper:ao_divergence_any_tf** (10x isolated, 1700 USDT) | 13 (9/4) | 0.009 | [-0.982, 1.077] | 0.364 | -0.788 | 1.01 | 38% | 223.08 (13.12%) | -27.77 | INCONCLUSIVE (n_total=13 < 30) | INCONCLUSIVE |
| 1h short **snipper:ao_divergence_any_tf** (10x isolated, 1700 USDT) | 9 (4/5) | 0.942 | [-0.946, 3.884] | -0.358 | 1.983 | 2.51 | 44% | 89.98 (5.29%) | 284.47 | INCONCLUSIVE (n_total=9 < 30) | INCONCLUSIVE |
| 1h long **snipper:bbwp_fresh** (10x isolated, 1700 USDT) | 28 (17/11) | -0.196 | [-0.863, 0.572] | -0.410 | 0.136 | 0.79 | 25% | 477.84 (28.11%) | -201.36 | INCONCLUSIVE (n_total=28 < 30) | INCONCLUSIVE |
| 1h short **snipper:bbwp_fresh** (10x isolated, 1700 USDT) | 28 (16/12) | -0.243 | [-0.949, 0.722] | -0.428 | 0.003 | 0.75 | 29% | 235.11 (13.83%) | -222.74 | INCONCLUSIVE (n_total=28 < 30) | INCONCLUSIVE |
| 1h long **snipper:bbwp_fresh_blue** (10x isolated, 1700 USDT) | 29 (18/11) | -0.108 | [-0.802, 0.565] | -0.123 | -0.083 | 0.88 | 28% | 414.75 (24.4%) | -154.49 | INCONCLUSIVE (n_total=29 < 30) | INCONCLUSIVE |
| 1h short **snipper:bbwp_fresh_blue** (10x isolated, 1700 USDT) | 22 (11/11) | -0.140 | [-1.019, 1.011] | -0.382 | 0.102 | 0.85 | 32% | 237.97 (14.0%) | -107.58 | INCONCLUSIVE (n_total=22 < 30) | INCONCLUSIVE |
| 1d long **pro_1d:base** (5x cross, 1300 USDT, pooled 3 symbols) | 7 (6/1) | -0.434 | [-0.933, 0.145] | -0.426 | -0.485 | 0.26 | 14% | 104.33 (8.03%) | -76.88 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 1d short **pro_1d:base** (5x cross, 1300 USDT, pooled 3 symbols) | 7 (2/5) | 0.206 | [-0.612, 1.094] | -1.033 | 0.701 | 1.55 | 57% | 53.16 (4.09%) | 32.86 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 1d long **pro_1d:adx_turn** (5x cross, 1300 USDT, pooled 3 symbols) | 2 (2/0) | -0.115 | [-1.209, 0.980] | -0.115 | — | 0.81 | 50% | 31.43 (2.42%) | -5.96 | INCONCLUSIVE (n_total=2 < 30) | INCONCLUSIVE |
| 1d short **pro_1d:adx_turn** (5x cross, 1300 USDT, pooled 3 symbols) | 4 (4/0) | -0.289 | [-0.702, 0.859] | -0.289 | — | 0.43 | 50% | 52.8 (4.06%) | -30.52 | INCONCLUSIVE (n_total=4 < 30) | INCONCLUSIVE |
| 1d long **pro_1d:adx_turn_origin** (5x cross, 1300 USDT, pooled 3 symbols) | 1 (1/0) | -1.209 | [-1.209, -1.209] | -1.209 | — | 0.00 | 0% | 31.43 (2.42%) | -31.43 | INCONCLUSIVE (n_total=1 < 30) | INCONCLUSIVE |
| 1d short **pro_1d:adx_turn_origin** (5x cross, 1300 USDT, pooled 3 symbols) | 2 (2/0) | 0.124 | [-0.611, 0.859] | 0.124 | — | 1.40 | 50% | 15.51 (1.19%) | 6.0 | INCONCLUSIVE (n_total=2 < 30) | INCONCLUSIVE |
| 1d long **pro_1d:ao_divergence** (5x cross, 1300 USDT, pooled 3 symbols) | 2 (2/0) | -0.379 | [-0.547, -0.212] | -0.379 | — | 0.00 | 0% | 19.72 (1.52%) | -19.72 | INCONCLUSIVE (n_total=2 < 30) | INCONCLUSIVE |
| 1d short **pro_1d:ao_divergence** (5x cross, 1300 USDT, pooled 3 symbols) | 0 (0/0) | — | — | — | — | — | — | — | — | INCONCLUSIVE (n_total=0 < 30) | INCONCLUSIVE |
| 1d long **pro_1d:ao_divergence_any_tf** (5x cross, 1300 USDT, pooled 3 symbols) | 3 (2/1) | -0.396 | [-0.547, -0.212] | -0.379 | -0.429 | 0.00 | 0% | 30.88 (2.38%) | -30.88 | INCONCLUSIVE (n_total=3 < 30) | INCONCLUSIVE |
| 1d short **pro_1d:ao_divergence_any_tf** (5x cross, 1300 USDT, pooled 3 symbols) | 1 (1/0) | -0.611 | [-0.611, -0.611] | -0.611 | — | 0.00 | 0% | 15.72 (1.21%) | -15.72 | INCONCLUSIVE (n_total=1 < 30) | INCONCLUSIVE |
| 1d long **pro_1d:bbwp_fresh** (5x cross, 1300 USDT, pooled 3 symbols) | 7 (5/2) | -0.480 | [-0.953, 0.106] | -0.489 | -0.457 | 0.24 | 14% | 112.51 (8.65%) | -85.06 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 1d short **pro_1d:bbwp_fresh** (5x cross, 1300 USDT, pooled 3 symbols) | 3 (1/2) | 0.067 | [-1.455, 1.171] | -1.455 | 0.828 | 1.14 | 67% | 37.65 (2.9%) | 3.3 | INCONCLUSIVE (n_total=3 < 30) | INCONCLUSIVE |
| 1d long **pro_1d:bbwp_fresh_blue** (5x cross, 1300 USDT, pooled 3 symbols) | 7 (5/2) | -0.480 | [-0.953, 0.106] | -0.489 | -0.457 | 0.24 | 14% | 112.51 (8.65%) | -85.06 | INCONCLUSIVE (n_total=7 < 30) | INCONCLUSIVE |
| 1d short **pro_1d:bbwp_fresh_blue** (5x cross, 1300 USDT, pooled 3 symbols) | 3 (1/2) | 0.067 | [-1.455, 1.171] | -1.455 | 0.828 | 1.14 | 67% | 37.65 (2.9%) | 3.3 | INCONCLUSIVE (n_total=3 < 30) | INCONCLUSIVE |

## Book level (one ledger per run and symbol, long + short)

| run | symbol | tf | lev | decisions (alert / enter / add / reduce / exit) | entries blocked by the filter | trades | avg layers | partial takes | equity final | return | max DD equity USDT (%) | liquidations | exit mix | B&H |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:base | BTC/USDT | 4h | 5x cross | 381 / 14 / 16 / 11 / 14 | 0 | 14 | 2.14 | 11 | 1234.78 | -5.02% | 204.79 (14.34%) | 0 | {'exit_ctx_mlrsi_against': 10, 'exit_invalidation': 2, 'exit_rule_jeisson': 2} | 11.76% |
| pro:adx_turn | BTC/USDT | 4h | 5x cross | 1137 / 7 / 11 / 7 / 7 | 54 | 7 | 2.57 | 7 | 1259.66 | -3.1% | 169.77 (11.88%) | 0 | {'exit_rule_jeisson': 1, 'exit_invalidation': 2, 'exit_ctx_mlrsi_against': 4} | 11.76% |
| pro:adx_turn_origin | BTC/USDT | 4h | 5x cross | 1375 / 6 / 8 / 6 / 6 | 83 | 6 | 2.33 | 6 | 1363.34 | 4.87% | 130.16 (8.92%) | 0 | {'exit_rule_jeisson': 2, 'exit_invalidation': 2, 'exit_ctx_mlrsi_against': 2} | 11.76% |
| pro:ao_divergence | BTC/USDT | 4h | 5x cross | 1754 / 4 / 4 / 4 / 4 | 120 | 4 | 2.0 | 4 | 1470.71 | 13.13% | 104.25 (7.09%) | 0 | {'exit_ctx_mlrsi_against': 2, 'exit_rule_jeisson': 1, 'exit_invalidation': 1} | 11.76% |
| pro:ao_divergence_any_tf | BTC/USDT | 4h | 5x cross | 1413 / 4 / 4 / 4 / 4 | 103 | 4 | 2.0 | 4 | 1468.59 | 12.97% | 104.1 (7.09%) | 0 | {'exit_ctx_mlrsi_against': 2, 'exit_rule_jeisson': 1, 'exit_invalidation': 1} | 11.76% |
| pro:bbwp_fresh | BTC/USDT | 4h | 5x cross | 966 / 10 / 10 / 9 / 10 | 38 | 10 | 2.0 | 9 | 1294.39 | -0.43% | 161.81 (11.11%) | 0 | {'exit_ctx_mlrsi_against': 7, 'exit_invalidation': 2, 'exit_rule_jeisson': 1} | 11.76% |
| pro:bbwp_fresh_blue | BTC/USDT | 4h | 5x cross | 1114 / 9 / 10 / 8 / 9 | 52 | 9 | 2.11 | 8 | 1308.83 | 0.68% | 147.02 (10.1%) | 0 | {'exit_ctx_mlrsi_against': 6, 'exit_invalidation': 2, 'exit_rule_jeisson': 1} | 11.76% |
| snipper:base | BTC/USDT | 1h | 10x isolated | 2257 / 65 / 89 / 59 / 63 | 0 | 65 | 2.37 | 59 | 1263.84 | -25.66% | 618.33 (33.66%) | 1 | {'exit_invalidation': 19, 'exit_ctx_mlrsi_against': 38, 'exit_rule_jeisson': 6, 'liquidation': 1, 'end_of_data': 1} | 10.5% |
| snipper:adx_turn | BTC/USDT | 1h | 10x isolated | 4202 / 53 / 67 / 50 / 51 | 278 | 53 | 2.26 | 50 | 2256.39 | 32.73% | 584.58 (30.46%) | 1 | {'exit_invalidation': 22, 'exit_ctx_mlrsi_against': 24, 'exit_rule_jeisson': 5, 'liquidation': 1, 'end_of_data': 1} | 10.5% |
| snipper:adx_turn_origin | BTC/USDT | 1h | 10x isolated | 7559 / 33 / 32 / 29 / 33 | 623 | 33 | 1.97 | 29 | 1310.48 | -22.91% | 523.3 (30.44%) | 0 | {'exit_invalidation': 16, 'exit_ctx_mlrsi_against': 14, 'exit_rule_jeisson': 3} | 10.5% |
| snipper:ao_divergence | BTC/USDT | 1h | 10x isolated | 8947 / 17 / 19 / 16 / 17 | 725 | 17 | 2.12 | 16 | 2005.5 | 17.97% | 267.38 (13.87%) | 0 | {'exit_invalidation': 7, 'exit_ctx_mlrsi_against': 10} | 10.5% |
| snipper:ao_divergence_any_tf | BTC/USDT | 1h | 10x isolated | 8020 / 22 / 30 / 21 / 22 | 609 | 22 | 2.36 | 21 | 1956.7 | 15.1% | 365.31 (15.73%) | 0 | {'exit_invalidation': 8, 'exit_ctx_mlrsi_against': 13, 'exit_rule_jeisson': 1} | 10.5% |
| snipper:bbwp_fresh | BTC/USDT | 1h | 10x isolated | 3309 / 56 / 80 / 53 / 54 | 123 | 56 | 2.43 | 53 | 1275.9 | -24.95% | 718.62 (39.11%) | 1 | {'exit_ctx_mlrsi_against': 27, 'exit_invalidation': 23, 'exit_rule_jeisson': 4, 'liquidation': 1, 'end_of_data': 1} | 10.5% |
| snipper:bbwp_fresh_blue | BTC/USDT | 1h | 10x isolated | 4144 / 51 / 74 / 48 / 49 | 202 | 51 | 2.45 | 48 | 1437.93 | -15.42% | 689.92 (35.22%) | 1 | {'exit_ctx_mlrsi_against': 26, 'exit_invalidation': 20, 'exit_rule_jeisson': 3, 'liquidation': 1, 'end_of_data': 1} | 10.5% |
| pro_1d:base | BTC/USDT | 1d | 5x cross | 175 / 2 / 2 / 2 / 2 | 0 | 2 | 2.0 | 2 | 1329.28 | 2.25% | 46.38 (3.47%) | 0 | {'exit_rule_jeisson': 2} | 11.57% |
| pro_1d:base | ETH/USDT | 1d | 5x cross | 66 / 5 / 8 / 5 / 4 | 0 | 5 | 2.6 | 5 | 1252.42 | -3.66% | 102.69 (7.68%) | 0 | {'exit_ctx_mlrsi_against': 3, 'exit_rule_jeisson': 1, 'end_of_data': 1} | -10.19% |
| pro_1d:base | SOL/USDT | 1d | 5x cross | 162 / 7 / 5 / 4 / 6 | 0 | 7 | 1.71 | 4 | 1274.28 | -1.98% | 110.62 (8.35%) | 0 | {'exit_ctx_mlrsi_against': 3, 'exit_invalidation': 1, 'exit_rule_jeisson': 2, 'end_of_data': 1} | -42.54% |
| pro_1d:adx_turn | BTC/USDT | 1d | 5x cross | 229 / 1 / 2 / 1 / 1 | 8 | 1 | 3.0 | 1 | 1325.47 | 1.96% | 44.92 (3.37%) | 0 | {'exit_rule_jeisson': 1} | 11.57% |
| pro_1d:adx_turn | ETH/USDT | 1d | 5x cross | 394 / 2 / 2 / 1 / 2 | 24 | 2 | 2.0 | 1 | 1263.47 | -2.81% | 55.22 (4.21%) | 0 | {'exit_rule_jeisson': 1, 'exit_ctx_mlrsi_against': 1} | -10.19% |
| pro_1d:adx_turn | SOL/USDT | 1d | 5x cross | 201 / 3 / 4 / 3 / 3 | 14 | 3 | 2.33 | 3 | 1274.58 | -1.96% | 72.98 (5.52%) | 0 | {'exit_ctx_mlrsi_against': 2, 'exit_rule_jeisson': 1} | -42.54% |
| pro_1d:adx_turn_origin | BTC/USDT | 1d | 5x cross | 471 / 0 / 0 / 0 / 0 | 24 | 0 | 0.0 | 0 | 1300.0 | 0.0% | 0.0 (0.0%) | 0 | {} | 11.57% |
| pro_1d:adx_turn_origin | ETH/USDT | 1d | 5x cross | 501 / 0 / 0 / 0 / 0 | 28 | 0 | 0.0 | 0 | 1300.0 | 0.0% | 0.0 (0.0%) | 0 | {} | -10.19% |
| pro_1d:adx_turn_origin | SOL/USDT | 1d | 5x cross | 201 / 3 / 4 / 3 / 3 | 14 | 3 | 2.33 | 3 | 1274.58 | -1.96% | 72.98 (5.52%) | 0 | {'exit_ctx_mlrsi_against': 2, 'exit_rule_jeisson': 1} | -42.54% |
| pro_1d:ao_divergence | BTC/USDT | 1d | 5x cross | 279 / 1 / 2 / 1 / 1 | 11 | 1 | 3.0 | 1 | 1294.5 | -0.42% | 32.97 (2.53%) | 0 | {'exit_rule_jeisson': 1} | 11.57% |
| pro_1d:ao_divergence | ETH/USDT | 1d | 5x cross | 501 / 0 / 0 / 0 / 0 | 28 | 0 | 0.0 | 0 | 1300.0 | 0.0% | 0.0 (0.0%) | 0 | {} | -10.19% |
| pro_1d:ao_divergence | SOL/USDT | 1d | 5x cross | 430 / 1 / 0 / 1 / 1 | 30 | 1 | 1.0 | 1 | 1285.78 | -1.09% | 42.76 (3.22%) | 0 | {'exit_invalidation': 1} | -42.54% |
| pro_1d:ao_divergence_any_tf | BTC/USDT | 1d | 5x cross | 279 / 1 / 2 / 1 / 1 | 11 | 1 | 3.0 | 1 | 1294.5 | -0.42% | 32.97 (2.53%) | 0 | {'exit_rule_jeisson': 1} | 11.57% |
| pro_1d:ao_divergence_any_tf | ETH/USDT | 1d | 5x cross | 471 / 1 / 0 / 1 / 0 | 25 | 1 | 1.0 | 1 | 1288.84 | -0.86% | 11.25 (0.87%) | 0 | {'end_of_data': 1} | -10.19% |
| pro_1d:ao_divergence_any_tf | SOL/USDT | 1d | 5x cross | 330 / 2 / 0 / 2 / 2 | 23 | 2 | 1.0 | 2 | 1270.06 | -2.3% | 58.68 (4.42%) | 0 | {'exit_invalidation': 1, 'exit_ctx_mlrsi_against': 1} | -42.54% |
| pro_1d:bbwp_fresh | BTC/USDT | 1d | 5x cross | 227 / 1 / 2 / 1 / 1 | 6 | 1 | 3.0 | 1 | 1327.46 | 2.11% | 46.38 (3.47%) | 0 | {'exit_rule_jeisson': 1} | 11.57% |
| pro_1d:bbwp_fresh | ETH/USDT | 1d | 5x cross | 202 / 5 / 6 / 5 / 4 | 3 | 5 | 2.2 | 5 | 1255.29 | -3.44% | 102.69 (7.68%) | 0 | {'exit_ctx_mlrsi_against': 3, 'exit_rule_jeisson': 1, 'end_of_data': 1} | -10.19% |
| pro_1d:bbwp_fresh | SOL/USDT | 1d | 5x cross | 183 / 4 / 5 / 4 / 3 | 6 | 4 | 2.25 | 4 | 1235.5 | -4.96% | 91.4 (6.9%) | 0 | {'exit_ctx_mlrsi_against': 2, 'exit_rule_jeisson': 1, 'end_of_data': 1} | -42.54% |
| pro_1d:bbwp_fresh_blue | BTC/USDT | 1d | 5x cross | 227 / 1 / 2 / 1 / 1 | 6 | 1 | 3.0 | 1 | 1327.46 | 2.11% | 46.38 (3.47%) | 0 | {'exit_rule_jeisson': 1} | 11.57% |
| pro_1d:bbwp_fresh_blue | ETH/USDT | 1d | 5x cross | 202 / 5 / 6 / 5 / 4 | 3 | 5 | 2.2 | 5 | 1255.29 | -3.44% | 102.69 (7.68%) | 0 | {'exit_ctx_mlrsi_against': 3, 'exit_rule_jeisson': 1, 'end_of_data': 1} | -10.19% |
| pro_1d:bbwp_fresh_blue | SOL/USDT | 1d | 5x cross | 183 / 4 / 5 / 4 / 3 | 6 | 4 | 2.25 | 4 | 1235.5 | -4.96% | 91.4 (6.9%) | 0 | {'exit_ctx_mlrsi_against': 2, 'exit_rule_jeisson': 1, 'end_of_data': 1} | -42.54% |

## Classifier study on the BASELINE trades (prereg §6b; flags at the entry candle, no re-run)

KEEP iff n_pass >= 10 AND expectancy of the passed trades > 0 AND passed > rejected on all, IS and OOS (each block with >= 3 trades on both sides); DROP when comparable and any leg fails; INCONCLUSIVE when not comparable. Caveat: a filtered RUN changes the path (position occupancy), so this is a reading of the signal, not of the book.

### pro (4h, baseline n 14, symbols BTC/USDT)

| filter | n pass (long/short) / n rej (pass rate) | exp. R pass (CI95) | exp. R rej | IS pass vs rej (n) | OOS pass vs rej (n) | PF pass / rej | verdict |
|---|---|---|---|---|---|---|---|
| `adx_turn` | 2 (1L/1S) / 12 (0.143) | 0.057 [-0.552, 0.666] | -0.208 | 0.666 vs -0.319 (1/8) | -0.552 vs 0.011 (1/4) | 1.21 / 0.67 | **INCONCLUSIVE (n_pass=2 < 10; in_sample: n_pass 1 / n_rej 8 < 3; out_of_sample: n_pass 1 / n_rej 4 < 3)** |
| `adx_turn_origin` | 1 (0L/1S) / 13 (0.071) | 0.666 [0.666, 0.666] | -0.235 | 0.666 vs -0.319 (1/8) | — vs -0.101 (0/5) | inf / 0.62 | **INCONCLUSIVE (n_pass=1 < 10; in_sample: n_pass 1 / n_rej 8 < 3; out_of_sample: n_pass 0 / n_rej 5 < 3)** |
| `ao_divergence` | 0 (0L/0S) / 14 (0.0) | — — | -0.171 | — vs -0.209 (0/9) | — vs -0.101 (0/5) | — / 0.70 | **INCONCLUSIVE (n_pass=0 < 10; in_sample: n_pass 0 / n_rej 9 < 3; out_of_sample: n_pass 0 / n_rej 5 < 3)** |
| `ao_divergence_any_tf` | 1 (1L/0S) / 13 (0.071) | -0.656 [-0.656, -0.656] | -0.133 | -0.656 vs -0.153 (1/8) | — vs -0.101 (0/5) | 0.00 / 0.77 | **INCONCLUSIVE (n_pass=1 < 10; in_sample: n_pass 1 / n_rej 8 < 3; out_of_sample: n_pass 0 / n_rej 5 < 3)** |
| `bbwp_fresh` | 8 (5L/3S) / 6 (0.571) | -0.114 [-0.739, 0.694] | -0.246 | 0.386 vs -0.954 (5/4) | -0.948 vs 1.169 (3/2) | 0.78 / 0.62 | **INCONCLUSIVE (n_pass=8 < 10; out_of_sample: n_pass 3 / n_rej 2 < 3)** |
| `bbwp_fresh_blue` | 7 (4L/3S) / 7 (0.5) | -0.051 [-0.761, 0.928] | -0.290 | 0.386 vs -0.954 (5/4) | -1.145 vs 0.595 (2/3) | 0.90 / 0.54 | **INCONCLUSIVE (n_pass=7 < 10; out_of_sample: n_pass 2 / n_rej 3 < 3)** |

### snipper (1h, baseline n 65, symbols BTC/USDT)

| filter | n pass (long/short) / n rej (pass rate) | exp. R pass (CI95) | exp. R rej | IS pass vs rej (n) | OOS pass vs rej (n) | PF pass / rej | verdict |
|---|---|---|---|---|---|---|---|
| `adx_turn` | 19 (10L/9S) / 46 (0.292) | -0.677 [-1.155, -0.106] | 0.012 | -0.577 vs -0.038 (14/27) | -0.958 vs 0.082 (5/19) | 0.33 / 1.01 | **DROP (exp_pass_all > 0; exp_pass_all > exp_rej_all; exp_pass_is > exp_rej_is; exp_pass_oos > exp_rej_oos)** |
| `adx_turn_origin` | 9 (4L/5S) / 56 (0.138) | -0.589 [-1.445, 1.022] | -0.125 | -0.511 vs -0.152 (8/33) | -1.207 vs -0.088 (1/23) | 0.44 / 0.85 | **INCONCLUSIVE (n_pass=9 < 10; out_of_sample: n_pass 1 / n_rej 23 < 3)** |
| `ao_divergence` | 1 (0L/1S) / 64 (0.015) | -0.771 [-0.771, -0.771] | -0.180 | -0.771 vs -0.208 (1/40) | — vs -0.135 (0/24) | 0.00 / 0.79 | **INCONCLUSIVE (n_pass=1 < 10; in_sample: n_pass 1 / n_rej 40 < 3; out_of_sample: n_pass 0 / n_rej 24 < 3)** |
| `ao_divergence_any_tf` | 5 (3L/2S) / 60 (0.077) | 0.047 [-0.807, 0.900] | -0.209 | 0.334 vs -0.282 (4/37) | -1.099 vs -0.092 (1/23) | 1.11 / 0.77 | **INCONCLUSIVE (n_pass=5 < 10; out_of_sample: n_pass 1 / n_rej 23 < 3)** |
| `bbwp_fresh` | 39 (20L/19S) / 26 (0.6) | -0.053 [-0.679, 0.660] | -0.395 | -0.072 vs -0.379 (21/20) | -0.030 vs -0.448 (18/6) | 0.94 / 0.52 | **DROP (exp_pass_all > 0)** |
| `bbwp_fresh_blue` | 32 (19L/13S) / 33 (0.492) | 0.021 [-0.752, 0.846] | -0.394 | 0.008 vs -0.355 (15/26) | 0.032 vs -0.539 (17/7) | 1.02 / 0.52 | **KEEP** |

### pro_1d (1d, baseline n 14, symbols BTC/USDT, ETH/USDT, SOL/USDT)

| filter | n pass (long/short) / n rej (pass rate) | exp. R pass (CI95) | exp. R rej | IS pass vs rej (n) | OOS pass vs rej (n) | PF pass / rej | verdict |
|---|---|---|---|---|---|---|---|
| `adx_turn` | 1 (0L/1S) / 13 (0.071) | -0.611 [-0.611, -0.611] | -0.076 | -0.611 vs -0.573 (1/7) | — vs 0.503 (0/6) | 0.00 / 0.84 | **INCONCLUSIVE (n_pass=1 < 10; in_sample: n_pass 1 / n_rej 7 < 3; out_of_sample: n_pass 0 / n_rej 6 < 3)** |
| `adx_turn_origin` | 1 (0L/1S) / 13 (0.071) | -0.611 [-0.611, -0.611] | -0.076 | -0.611 vs -0.573 (1/7) | — vs 0.503 (0/6) | 0.00 / 0.84 | **INCONCLUSIVE (n_pass=1 < 10; in_sample: n_pass 1 / n_rej 7 < 3; out_of_sample: n_pass 0 / n_rej 6 < 3)** |
| `ao_divergence` | 0 (0L/0S) / 14 (0.0) | — — | -0.114 | — vs -0.578 (0/8) | — vs 0.503 (0/6) | — / 0.76 | **INCONCLUSIVE (n_pass=0 < 10; in_sample: n_pass 0 / n_rej 8 < 3; out_of_sample: n_pass 0 / n_rej 6 < 3)** |
| `ao_divergence_any_tf` | 1 (0L/1S) / 13 (0.071) | -0.611 [-0.611, -0.611] | -0.076 | -0.611 vs -0.573 (1/7) | — vs 0.503 (0/6) | 0.00 / 0.84 | **INCONCLUSIVE (n_pass=1 < 10; in_sample: n_pass 1 / n_rej 7 < 3; out_of_sample: n_pass 0 / n_rej 6 < 3)** |
| `bbwp_fresh` | 8 (5L/3S) / 6 (0.571) | -0.178 [-0.821, 0.453] | -0.029 | -0.519 vs -0.676 (5/3) | 0.390 vs 0.617 (3/3) | 0.66 / 0.93 | **INCONCLUSIVE (n_pass=8 < 10)** |
| `bbwp_fresh_blue` | 8 (5L/3S) / 6 (0.571) | -0.178 [-0.821, 0.453] | -0.029 | -0.519 vs -0.676 (5/3) | 0.390 vs 0.617 (3/3) | 0.66 / 0.93 | **INCONCLUSIVE (n_pass=8 < 10)** |

## Pre-registered fallback

No SNIPPER cell failed only the liquidation leg; no 7x re-run.

## Baseline continuity with round 4b (same data, same chain: the `base` cells must reproduce r4b)

* pro: **identical** — long r5 base n 7 / -26.65 USDT vs r4b n 7 / -26.65 USDT; short r5 base n 7 / -38.57 USDT vs r4b n 7 / -38.57 USDT
* snipper: **identical** — long r5 base n 31 / -127.72 USDT vs r4b n 31 / -127.72 USDT; short r5 base n 34 / -308.44 USDT vs r4b n 34 / -308.44 USDT
* pro_1d: **DIFFERENT** — long r5 base n 7 / -76.88 USDT vs r4b n 1 / 27.46 USDT; short r5 base n 7 / 32.86 USDT vs r4b n 1 / 1.82 USDT

## H-owner — the owner's short candle (82450, Oct 2026) seen by the filters (informational)

* **pro** (4h) owner bar 2026-10-09T00:00 close 82418.88, baseline state in_position: phase expansion (bbwp 75.8, blue_recent False); ADX 36.5, short turn onsets in the last 4 candles none, origin —; bear divergence trigger False / guardian True. Flags if it were an entry: adx_turn=0, adx_turn_origin=0, ao_divergence=0, ao_divergence_any_tf=1, bbwp_fresh=0, bbwp_fresh_blue=0.
* **snipper** (1h) owner bar 2026-10-12T18:00 close 82454.84, baseline state in_position: phase expansion (bbwp 86.7, blue_recent False); ADX 28.6, short turn onsets in the last 5 candles ['2026-10-12T14:00:00+00:00'], origin 21.4; bear divergence trigger True / guardian False. Flags if it were an entry: adx_turn=1, adx_turn_origin=0, ao_divergence=1, ao_divergence_any_tf=1, bbwp_fresh=0, bbwp_fresh_blue=0.

## Follower windows used (IS fit, frozen since rounds 2 / 4)

* pro: {'ao': 2, 'adx': 4, 'macd': 3, 'rsi': 2}, tf_status BTC/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}
* snipper: {'ao': 2, 'adx': 5, 'macd': 3, 'rsi': 3}, tf_status BTC/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}
* pro_1d: {'ao': 3, 'adx': 3, 'macd': 2, 'rsi': 5}, tf_status BTC/USDT {'1d': 'ok', '1w': 'ok', '1M': 'ok'}; ETH/USDT {'1d': 'ok', '1w': 'ok', '1M': 'ok'}; SOL/USDT {'1d': 'ok', '1w': 'ok', '1M': 'ok'}
