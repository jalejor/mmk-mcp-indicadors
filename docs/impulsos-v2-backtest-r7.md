# Impulsos v2 — round 7 results (multi-asset replication of the frozen 2.3.0 chain, 9 Bitget perps)

Protocol: `docs/PREREG_IMPULSOS_v2_r7.md` (frozen before this run). Run 20261101T163117Z in the lab service `backtest`, harness `scripts/run_impulse_backtest_r7.py`. Raw JSON (every trade, cell, family, p-values): `r7_impulse_20261101T163117Z.json`. Window 2024-11-01 -> 2026-10-31, IS/OOS split 2026-01-01. Universe: BTC/USDT, ETH/USDT, SOL/USDT, XRP/USDT, DOGE/USDT, NEAR/USDT, BNB/USDT, LINK/USDT, ADA/USDT (new = replication assets: ETH/USDT, SOL/USDT, XRP/USDT, DOGE/USDT, NEAR/USDT, BNB/USDT, LINK/USDT, ADA/USDT; seen in rounds 1-6: BTC/USDT).

## Data manifest

| symbol @ TF | rows | first open | last open | gaps | sha256 (12) | source | s |
|---|---|---|---|---|---|---|---|
| BTC/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `a9ec96296cf4` | cache | 0.0 |
| BTC/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `1fd23248b1c1` | cache | 0.0 |
| BTC/USDT@1w | 403 | 2019-02-04T00:00 | 2026-10-19T00:00 | 0 | `3c483695e2db` | cache | 0.0 |
| ETH/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `2ad6db212c25` | exchange | 9.7 |
| ETH/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `8e918749b2f3` | cache | 0.0 |
| ETH/USDT@1w | 403 | 2019-02-04T00:00 | 2026-10-19T00:00 | 0 | `cbc218c025bc` | cache | 0.0 |
| SOL/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `3e70a8f970c2` | exchange | 9.6 |
| SOL/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `fed745e682a1` | cache | 0.0 |
| SOL/USDT@1w | 279 | 2021-06-21T00:00 | 2026-10-19T00:00 | 0 | `4491cd4d33c0` | cache | 0.0 |
| XRP/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `67f08e4203a2` | exchange | 9.7 |
| XRP/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `b9871aa7d557` | exchange | 4.3 |
| XRP/USDT@1w | 390 | 2019-05-06T00:00 | 2026-10-19T00:00 | 0 | `da776aec9a59` | exchange | 4.7 |
| DOGE/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `7bf2e7c03b36` | exchange | 9.7 |
| DOGE/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `51c6a328568f` | exchange | 4.5 |
| DOGE/USDT@1w | 288 | 2021-04-19T00:00 | 2026-10-19T00:00 | 0 | `1f929c643010` | exchange | 4.6 |
| NEAR/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `7e34b645f301` | exchange | 10.2 |
| NEAR/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `5e8357561c28` | exchange | 4.6 |
| NEAR/USDT@1w | 235 | 2022-04-25T00:00 | 2026-10-19T00:00 | 0 | `caf0e731c549` | exchange | 4.7 |
| BNB/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `84e4e6c10dea` | exchange | 9.5 |
| BNB/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `a32575ffde71` | exchange | 4.2 |
| BNB/USDT@1w | 282 | 2021-05-31T00:00 | 2026-10-19T00:00 | 0 | `9759376fc5ea` | exchange | 4.5 |
| LINK/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `cf76b478912b` | exchange | 10.2 |
| LINK/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `bb51c521011f` | exchange | 4.4 |
| LINK/USDT@1w | 289 | 2021-04-12T00:00 | 2026-10-19T00:00 | 0 | `06582ad004d7` | exchange | 4.4 |
| ADA/USDT@4h | 4680 | 2024-09-12T00:00 | 2026-10-31T20:00 | 0 | `90a7eb88f3c8` | exchange | 10.0 |
| ADA/USDT@1d | 1030 | 2024-01-06T00:00 | 2026-10-31T00:00 | 0 | `e4270abcc42e` | exchange | 5.0 |
| ADA/USDT@1w | 240 | 2022-03-21T00:00 | 2026-10-19T00:00 | 0 | `c3772ed9f1eb` | exchange | 4.3 |
| BTC/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `87e7dbf8ecdb` | cache | 0.2 |
| ETH/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `2625f1631577` | exchange | 31.6 |
| SOL/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `10db092ac02c` | exchange | 29.9 |
| XRP/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `3c99cfbc9f04` | exchange | 31.8 |
| DOGE/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `048efe1d315c` | exchange | 33.7 |
| NEAR/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `3929e2ccf04a` | exchange | 32.2 |
| BNB/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `c79efe9c5384` | exchange | 33.1 |
| LINK/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `230378e065f7` | exchange | 32.2 |
| ADA/USDT@1h | 17820 | 2024-10-19T12:00 | 2026-10-31T23:00 | 0 | `68aff1433511` | exchange | 32.7 |

## A. PRIMARY pooled cells — 8 new assets, trigger gate as written, reference books (Holm alpha 0.05, m = 12)

GO iff r4 gate (n >= 30, n_oos >= 10, exp OOS > 0, PF >= 1.2, liq 0, pooled DD < 35 % of the pooled start) AND Holm-adjusted one-sided cluster-bootstrap p of the OOS expectancy < 0.05. These are the only GO-eligible pooled cells.

| cell | side | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | win | max DD USDT (% start) | net USDT | liq | p OOS>0 | corrected | r4 gate | **r7 verdict** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:base:spec:pro5 [new8] | long | 47 (26/21) | 0.746 | [-0.307, 2.126] | 0.878 | 0.584 | 2.20 | 23% | 319.81 (3.08%) | 854.49 | 0 | 0.2940 | Holm p_adj 1.0000 (m=12) | GO | **NO-GO** (p_adj=1.0 (multiple comparisons, m=12)) |
| pro:base:spec:pro5 [new8] | short | 45 (26/19) | -0.384 | [-0.786, 0.029] | -0.393 | -0.372 | 0.50 | 38% | 484.95 (4.66%) | -484.62 | 0 | 0.8399 | Holm p_adj 1.0000 (m=12) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:adx_turn:spec:pro5 [new8] | long | 39 (18/21) | 0.640 | [-0.529, 2.197] | 0.880 | 0.434 | 1.91 | 23% | 367.86 (3.54%) | 625.74 | 0 | 0.3527 | Holm p_adj 1.0000 (m=12) | GO | **NO-GO** (p_adj=1.0 (multiple comparisons, m=12)) |
| pro:adx_turn:spec:pro5 [new8] | short | 38 (26/12) | -0.497 | [-0.962, 0.095] | -0.266 | -0.998 | 0.42 | 24% | 599.71 (5.77%) | -542.17 | 0 | 0.9997 | Holm p_adj 1.0000 (m=12) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:bbwp_fresh_blue:spec:pro5 [new8] | long | 30 (16/14) | 0.906 | [-0.622, 2.959] | 0.747 | 1.088 | 2.32 | 23% | 452.51 (4.35%) | 730.33 | 0 | 0.2475 | Holm p_adj 1.0000 (m=12) | GO | **NO-GO** (p_adj=1.0 (multiple comparisons, m=12)) |
| pro:bbwp_fresh_blue:spec:pro5 [new8] | short | 43 (25/18) | -0.167 | [-0.678, 0.431] | -0.076 | -0.293 | 0.77 | 37% | 334.57 (3.22%) | -208.05 | 0 | 0.7876 | Holm p_adj 1.0000 (m=12) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:spec:cross5 [new8] | long | 229 (132/97) | 0.566 | [-0.128, 1.475] | 0.583 | 0.542 | 1.76 | 21% | 1907.48 (14.03%) | 2860.95 | 0 | 0.3034 | Holm p_adj 1.0000 (m=12) | GO | **NO-GO** (p_adj=1.0 (multiple comparisons, m=12)) |
| snipper:base:spec:cross5 [new8] | short | 288 (180/108) | -0.076 | [-0.256, 0.117] | -0.195 | 0.122 | 0.87 | 33% | 1463.27 (10.76%) | -834.4 | 0 | 0.2723 | Holm p_adj 1.0000 (m=12) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:adx_turn:spec:cross5 [new8] | long | 162 (95/67) | 1.012 | [0.108, 2.252] | 0.745 | 1.389 | 2.35 | 25% | 1726.14 (12.69%) | 5531.56 | 0 | 0.1071 | Holm p_adj 1.0000 (m=12) | GO | **NO-GO** (p_adj=1.0 (multiple comparisons, m=12)) |
| snipper:adx_turn:spec:cross5 [new8] | short | 198 (117/81) | 0.041 | [-0.211, 0.313] | -0.045 | 0.167 | 1.06 | 35% | 1040.33 (7.65%) | -59.04 | 0 | 0.2688 | Holm p_adj 1.0000 (m=12) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:bbwp_fresh_blue:spec:cross5 [new8] | long | 177 (108/69) | 1.059 | [0.168, 2.338] | 1.403 | 0.521 | 2.49 | 25% | 1492.23 (10.97%) | 7792.12 | 0 | 0.1372 | Holm p_adj 1.0000 (m=12) | GO | **NO-GO** (p_adj=1.0 (multiple comparisons, m=12)) |
| snipper:bbwp_fresh_blue:spec:cross5 [new8] | short | 215 (128/87) | -0.153 | [-0.352, 0.064] | -0.144 | -0.167 | 0.77 | 30% | 2699.98 (19.85%) | -1859.0 | 0 | 0.8150 | Holm p_adj 1.0000 (m=12) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |

## B. SECONDARY pooled cells — all 9 / as-run gate (E20) / 10x isolated book (informational, never GO-eligible)

Holm inside each (family, gate, book) group for reading only; the r7 verdict here is NO-GO or INCONCLUSIVE by construction.

| cell | side | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | win | max DD USDT (% start) | net USDT | liq | p OOS>0 | corrected | r4 gate | **r7 verdict** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:base:spec:pro5 [all9] | long | 51 (28/23) | 0.694 | [-0.297, 1.969] | 0.886 | 0.460 | 2.14 | 25% | 348.13 (2.98%) | 864.94 | 0 | 0.3187 | Holm p_adj 1.0000 (m=6) | GO | **NO-GO** (not in a corrected family) |
| pro:base:spec:pro5 [all9] | short | 52 (31/21) | -0.429 | [-0.795, -0.054] | -0.433 | -0.424 | 0.44 | 37% | 616.07 (5.27%) | -616.07 | 0 | 0.8926 | Holm p_adj 1.0000 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:base:asrun:pro5 [new8] | long | 69 (39/30) | 0.831 | [-0.078, 1.856] | 0.912 | 0.726 | 2.24 | 30% | 596.44 (5.73%) | 1379.94 | 0 | 0.1565 | Holm p_adj 0.8910 (m=6) | GO | **NO-GO** (not in a corrected family) |
| pro:base:asrun:pro5 [all9] | long | 76 (43/33) | 0.741 | [-0.093, 1.673] | 0.844 | 0.607 | 2.13 | 30% | 659.88 (5.64%) | 1353.29 | 0 | 0.1806 | Holm p_adj 1.0000 (m=6) | GO | **NO-GO** (not in a corrected family) |
| pro:base:asrun:pro5 [new8] | short | 49 (26/23) | -0.397 | [-0.836, 0.025] | -0.501 | -0.279 | 0.51 | 41% | 579.72 (5.57%) | -572.08 | 0 | 0.8117 | Holm p_adj 1.0000 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:base:asrun:pro5 [all9] | short | 56 (31/25) | -0.372 | [-0.775, 0.020] | -0.505 | -0.208 | 0.53 | 39% | 632.89 (5.41%) | -610.65 | 0 | 0.7485 | Holm p_adj 1.0000 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:adx_turn:spec:pro5 [all9] | long | 42 (19/23) | 0.663 | [-0.446, 2.075] | 1.043 | 0.349 | 1.98 | 24% | 381.53 (3.26%) | 701.36 | 0 | 0.3769 | Holm p_adj 1.0000 (m=6) | GO | **NO-GO** (not in a corrected family) |
| pro:adx_turn:spec:pro5 [all9] | short | 42 (28/14) | -0.560 | [-0.998, -0.010] | -0.334 | -1.014 | 0.37 | 24% | 726.65 (6.21%) | -669.12 | 0 | 1.0000 | Holm p_adj 1.0000 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:adx_turn:asrun:pro5 [new8] | long | 43 (21/22) | 0.470 | [-0.642, 1.947] | 0.616 | 0.331 | 1.59 | 23% | 513.28 (4.94%) | 474.47 | 0 | 0.3941 | Holm p_adj 1.0000 (m=6) | GO | **NO-GO** (not in a corrected family) |
| pro:adx_turn:asrun:pro5 [all9] | long | 46 (22/24) | 0.511 | [-0.550, 1.905] | 0.768 | 0.276 | 1.67 | 24% | 474.82 (4.06%) | 560.86 | 0 | 0.4103 | Holm p_adj 1.0000 (m=6) | GO | **NO-GO** (not in a corrected family) |
| pro:adx_turn:asrun:pro5 [new8] | short | 38 (26/12) | -0.394 | [-0.915, 0.336] | -0.115 | -1.000 | 0.53 | 26% | 502.86 (4.84%) | -445.38 | 0 | 0.9999 | Holm p_adj 1.0000 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:adx_turn:asrun:pro5 [all9] | short | 42 (28/14) | -0.467 | [-0.956, 0.204] | -0.173 | -1.055 | 0.47 | 26% | 629.59 (5.38%) | -572.11 | 0 | 1.0000 | Holm p_adj 1.0000 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:bbwp_fresh_blue:spec:pro5 [all9] | long | 34 (19/15) | 0.884 | [-0.514, 2.696] | 0.840 | 0.940 | 2.36 | 26% | 391.07 (3.34%) | 802.39 | 0 | 0.2699 | Holm p_adj 1.0000 (m=6) | GO | **NO-GO** (not in a corrected family) |
| pro:bbwp_fresh_blue:spec:pro5 [all9] | short | 47 (27/20) | -0.211 | [-0.679, 0.334] | -0.092 | -0.373 | 0.71 | 36% | 409.09 (3.5%) | -282.57 | 0 | 0.8601 | Holm p_adj 1.0000 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:bbwp_fresh_blue:asrun:pro5 [new8] | long | 45 (27/18) | 0.524 | [-0.678, 2.070] | 0.116 | 1.135 | 1.57 | 24% | 798.99 (7.68%) | 563.92 | 0 | 0.1485 | Holm p_adj 0.8910 (m=6) | GO | **NO-GO** (not in a corrected family) |
| pro:bbwp_fresh_blue:asrun:pro5 [all9] | long | 50 (31/19) | 0.525 | [-0.557, 1.930] | 0.224 | 1.016 | 1.61 | 26% | 755.24 (6.46%) | 629.7 | 0 | 0.1703 | Holm p_adj 1.0000 (m=6) | GO | **NO-GO** (not in a corrected family) |
| pro:bbwp_fresh_blue:asrun:pro5 [new8] | short | 48 (28/20) | -0.182 | [-0.683, 0.423] | 0.002 | -0.439 | 0.75 | 38% | 364.21 (3.5%) | -271.85 | 0 | 0.9117 | Holm p_adj 1.0000 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| pro:bbwp_fresh_blue:asrun:pro5 [all9] | short | 52 (30/22) | -0.209 | [-0.662, 0.343] | -0.001 | -0.493 | 0.71 | 37% | 402.09 (3.44%) | -328.8 | 0 | 0.9479 | Holm p_adj 1.0000 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:spec:cross5 [all9] | long | 254 (146/108) | 0.533 | [-0.093, 1.353] | 0.545 | 0.516 | 1.73 | 23% | 2055.28 (13.43%) | 3010.09 | 0 | 0.2817 | Holm p_adj 0.7600 (m=6) | GO | **NO-GO** (not in a corrected family) |
| snipper:base:spec:cross5 [all9] | short | 318 (200/118) | -0.079 | [-0.257, 0.110] | -0.206 | 0.136 | 0.87 | 33% | 1651.9 (10.8%) | -973.75 | 0 | 0.2403 | Holm p_adj 0.7600 (m=6) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:base:spec:iso10 [new8] | long | 236 (135/101) | 0.469 | [-0.184, 1.338] | 0.454 | 0.491 | 1.63 | 21% | 2123.15 (15.61%) | 2458.79 | 105 | 0.3138 | Holm p_adj 0.9608 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:base:spec:iso10 [all9] | long | 261 (149/112) | 0.446 | [-0.156, 1.241] | 0.428 | 0.470 | 1.61 | 22% | 2270.63 (14.84%) | 2605.2 | 107 | 0.2945 | Holm p_adj 0.8136 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:base:spec:iso10 [new8] | short | 295 (187/108) | -0.056 | [-0.229, 0.131] | -0.168 | 0.139 | 0.90 | 33% | 1462.1 (10.75%) | -659.08 | 105 | 0.2402 | Holm p_adj 0.9608 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 [all9] | short | 325 (207/118) | -0.060 | [-0.232, 0.124] | -0.181 | 0.151 | 0.90 | 32% | 1525.67 (9.97%) | -799.78 | 107 | 0.2145 | Holm p_adj 0.8136 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:base:asrun:cross5 [new8] | long | 286 (170/116) | 0.503 | [-0.080, 1.267] | 0.560 | 0.420 | 1.59 | 23% | 2894.88 (21.29%) | 3370.72 | 0 | 0.3036 | Holm p_adj 0.8010 (m=6) | GO | **NO-GO** (not in a corrected family) |
| snipper:base:asrun:cross5 [all9] | long | 317 (190/127) | 0.445 | [-0.089, 1.137] | 0.491 | 0.376 | 1.52 | 24% | 3084.2 (20.16%) | 3242.95 | 0 | 0.3163 | Holm p_adj 0.7887 (m=6) | GO | **NO-GO** (not in a corrected family) |
| snipper:base:asrun:cross5 [new8] | short | 289 (183/106) | 0.069 | [-0.165, 0.322] | -0.102 | 0.363 | 1.10 | 38% | 1622.86 (11.93%) | 1268.6 | 0 | 0.0936 | Holm p_adj 0.4680 (m=6) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:base:asrun:cross5 [all9] | short | 323 (204/119) | 0.033 | [-0.183, 0.273] | -0.126 | 0.306 | 1.05 | 36% | 1789.11 (11.69%) | 961.3 | 0 | 0.1177 | Holm p_adj 0.4708 (m=6) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:base:asrun:iso10 [new8] | long | 299 (181/118) | 0.403 | [-0.150, 1.125] | 0.420 | 0.377 | 1.47 | 22% | 3096.42 (22.77%) | 2515.93 | 117 | 0.3240 | Holm p_adj 0.6999 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:base:asrun:iso10 [all9] | long | 330 (201/129) | 0.356 | [-0.149, 1.028] | 0.368 | 0.337 | 1.41 | 23% | 3282.77 (21.46%) | 2388.21 | 118 | 0.3361 | Holm p_adj 0.6948 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:base:asrun:iso10 [new8] | short | 300 (193/107) | 0.066 | [-0.159, 0.310] | -0.111 | 0.385 | 1.10 | 37% | 1611.98 (11.85%) | 1205.56 | 117 | 0.0752 | Holm p_adj 0.4512 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:base:asrun:iso10 [all9] | short | 334 (214/120) | 0.031 | [-0.176, 0.262] | -0.134 | 0.326 | 1.05 | 35% | 1724.14 (11.27%) | 897.13 | 118 | 0.0996 | Holm p_adj 0.3984 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:adx_turn:spec:cross5 [all9] | long | 186 (108/78) | 0.917 | [0.114, 2.037] | 0.614 | 1.336 | 2.24 | 25% | 1889.17 (12.35%) | 5696.61 | 0 | 0.0661 | Holm p_adj 0.3966 (m=6) | GO | **NO-GO** (not in a corrected family) |
| snipper:adx_turn:spec:cross5 [all9] | short | 225 (135/90) | 0.049 | [-0.196, 0.309] | -0.069 | 0.226 | 1.07 | 35% | 1157.35 (7.56%) | -2.46 | 0 | 0.1900 | Holm p_adj 0.7600 (m=6) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:adx_turn:spec:iso10 [new8] | long | 164 (96/68) | 0.970 | [0.074, 2.185] | 0.696 | 1.357 | 2.28 | 24% | 1896.72 (13.95%) | 5486.37 | 53 | 0.1102 | Holm p_adj 0.6612 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:adx_turn:spec:iso10 [all9] | long | 188 (109/79) | 0.881 | [0.087, 1.983] | 0.571 | 1.308 | 2.18 | 24% | 2059.49 (13.46%) | 5648.48 | 54 | 0.0687 | Holm p_adj 0.4122 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:adx_turn:spec:iso10 [new8] | short | 201 (119/82) | 0.038 | [-0.211, 0.307] | -0.041 | 0.152 | 1.06 | 35% | 1131.18 (8.32%) | -144.67 | 53 | 0.2890 | Holm p_adj 0.9608 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:adx_turn:spec:iso10 [all9] | short | 228 (137/91) | 0.046 | [-0.195, 0.300] | -0.064 | 0.212 | 1.07 | 34% | 1248.03 (8.16%) | -88.09 | 54 | 0.2034 | Holm p_adj 0.8136 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:adx_turn:asrun:cross5 [new8] | long | 162 (95/67) | 0.983 | [0.061, 2.240] | 0.705 | 1.378 | 2.23 | 24% | 1733.08 (12.74%) | 5250.34 | 0 | 0.1120 | Holm p_adj 0.4680 (m=6) | GO | **NO-GO** (not in a corrected family) |
| snipper:adx_turn:asrun:cross5 [all9] | long | 187 (109/78) | 0.879 | [0.059, 1.991] | 0.564 | 1.318 | 2.09 | 25% | 2046.3 (13.37%) | 5416.76 | 0 | 0.0716 | Holm p_adj 0.3580 (m=6) | GO | **NO-GO** (not in a corrected family) |
| snipper:adx_turn:asrun:cross5 [new8] | short | 209 (129/80) | 0.094 | [-0.216, 0.429] | -0.146 | 0.481 | 1.12 | 36% | 1386.04 (10.19%) | 256.44 | 0 | 0.0725 | Holm p_adj 0.4350 (m=6) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:adx_turn:asrun:cross5 [all9] | short | 237 (148/89) | 0.143 | [-0.158, 0.487] | -0.153 | 0.634 | 1.19 | 35% | 1596.47 (10.43%) | 649.87 | 0 | 0.0345 | Holm p_adj 0.2070 (m=6) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:adx_turn:asrun:iso10 [new8] | long | 164 (97/67) | 0.951 | [0.041, 2.183] | 0.659 | 1.375 | 2.18 | 23% | 1864.65 (13.71%) | 5275.97 | 62 | 0.1130 | Holm p_adj 0.4520 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:adx_turn:asrun:iso10 [all9] | long | 189 (111/78) | 0.852 | [0.042, 1.943] | 0.526 | 1.315 | 2.05 | 24% | 2177.39 (14.23%) | 5439.38 | 63 | 0.0724 | Holm p_adj 0.3620 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:adx_turn:asrun:iso10 [new8] | short | 212 (131/81) | 0.096 | [-0.208, 0.428] | -0.129 | 0.460 | 1.13 | 35% | 1409.93 (10.37%) | 243.0 | 62 | 0.0800 | Holm p_adj 0.4512 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:adx_turn:asrun:iso10 [all9] | short | 240 (150/90) | 0.144 | [-0.150, 0.483] | -0.138 | 0.613 | 1.19 | 35% | 1609.43 (10.52%) | 635.97 | 63 | 0.0385 | Holm p_adj 0.2310 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:bbwp_fresh_blue:spec:cross5 [all9] | long | 202 (122/80) | 0.917 | [0.126, 2.050] | 1.208 | 0.473 | 2.29 | 25% | 1764.42 (11.53%) | 7696.09 | 0 | 0.1273 | Holm p_adj 0.6365 (m=6) | GO | **NO-GO** (not in a corrected family) |
| snipper:bbwp_fresh_blue:spec:cross5 [all9] | short | 236 (140/96) | -0.156 | [-0.369, 0.068] | -0.187 | -0.110 | 0.77 | 30% | 2824.37 (18.46%) | -2020.4 | 0 | 0.7233 | Holm p_adj 0.7600 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:bbwp_fresh_blue:spec:iso10 [new8] | long | 181 (109/72) | 1.011 | [0.132, 2.266] | 1.355 | 0.491 | 2.42 | 25% | 1669.53 (12.28%) | 7793.22 | 69 | 0.1426 | Holm p_adj 0.7130 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:bbwp_fresh_blue:spec:iso10 [all9] | long | 206 (123/83) | 0.877 | [0.103, 1.998] | 1.167 | 0.449 | 2.23 | 25% | 1941.2 (12.69%) | 7694.79 | 71 | 0.1311 | Holm p_adj 0.6555 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:bbwp_fresh_blue:spec:iso10 [new8] | short | 216 (129/87) | -0.132 | [-0.327, 0.085] | -0.117 | -0.155 | 0.79 | 30% | 2598.77 (19.11%) | -1594.52 | 69 | 0.8036 | Holm p_adj 0.9608 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:bbwp_fresh_blue:spec:iso10 [all9] | short | 237 (141/96) | -0.137 | [-0.343, 0.085] | -0.162 | -0.099 | 0.80 | 30% | 2737.82 (17.89%) | -1756.97 | 71 | 0.7075 | Holm p_adj 0.8136 (m=6) | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:bbwp_fresh_blue:asrun:cross5 [new8] | long | 204 (121/83) | 1.041 | [0.072, 2.344] | 1.284 | 0.686 | 2.24 | 28% | 2718.46 (19.99%) | 7611.84 | 0 | 0.2670 | Holm p_adj 0.8010 (m=6) | GO | **NO-GO** (not in a corrected family) |
| snipper:bbwp_fresh_blue:asrun:cross5 [all9] | long | 233 (139/94) | 0.898 | [0.040, 2.047] | 1.102 | 0.596 | 2.06 | 28% | 3027.26 (19.79%) | 7457.3 | 0 | 0.2696 | Holm p_adj 0.7887 (m=6) | GO | **NO-GO** (not in a corrected family) |
| snipper:bbwp_fresh_blue:asrun:cross5 [new8] | short | 236 (142/94) | 0.000 | [-0.267, 0.302] | -0.115 | 0.173 | 1.00 | 34% | 1917.16 (14.1%) | 530.37 | 0 | 0.2698 | Holm p_adj 0.8010 (m=6) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:bbwp_fresh_blue:asrun:cross5 [all9] | short | 258 (153/105) | -0.012 | [-0.271, 0.270] | -0.134 | 0.166 | 0.98 | 34% | 2009.11 (13.13%) | 424.07 | 0 | 0.2629 | Holm p_adj 0.7887 (m=6) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:bbwp_fresh_blue:asrun:iso10 [new8] | long | 208 (122/86) | 0.974 | [0.015, 2.253] | 1.238 | 0.599 | 2.13 | 27% | 2946.05 (21.66%) | 7457.01 | 65 | 0.2921 | Holm p_adj 0.6999 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:bbwp_fresh_blue:asrun:iso10 [all9] | long | 237 (140/97) | 0.841 | [-0.005, 1.980] | 1.063 | 0.522 | 1.97 | 27% | 3254.68 (21.27%) | 7302.53 | 66 | 0.2940 | Holm p_adj 0.6948 (m=6) | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:bbwp_fresh_blue:asrun:iso10 [new8] | short | 235 (142/93) | 0.024 | [-0.242, 0.327] | -0.092 | 0.201 | 1.03 | 34% | 1725.85 (12.69%) | 890.54 | 65 | 0.2333 | Holm p_adj 0.6999 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:bbwp_fresh_blue:asrun:iso10 [all9] | short | 257 (153/104) | 0.010 | [-0.249, 0.291] | -0.113 | 0.190 | 1.01 | 34% | 1817.8 (11.88%) | 782.96 | 66 | 0.2316 | Holm p_adj 0.6948 (m=6) | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |

## C. Per-asset cells — new assets, gate as written, reference books (Benjamini-Hochberg q 0.10, m = 96)

ASSET-GO = r4 gate on the asset's own book AND BH q-value < 0.10. An ASSET-GO is a replication candidate, not a paper gate: only a primary pooled GO moves anything.

| cell | side | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | win | max DD USDT (% start) | net USDT | liq | p OOS>0 | corrected | r4 gate | **r7 verdict** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:base:spec:pro5 · ETH/USDT | long | 6 (4/2) | -0.160 | [-0.814, 0.625] | -0.221 | -0.037 | 0.69 | 33% | 47.46 (3.65%) | -26.35 | 0 | 0.7497 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · SOL/USDT | long | 3 (2/1) | -0.958 | [-1.852, -0.189] | -1.342 | -0.189 | 0.00 | 0% | 69.46 (5.34%) | -69.46 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=3 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · XRP/USDT | long | 10 (6/4) | 1.333 | [-1.031, 6.358] | 3.034 | -1.218 | 2.84 | 20% | 226.52 (17.42%) | 303.3 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=10 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · DOGE/USDT | long | 3 (1/2) | -0.348 | [-1.769, 1.645] | 1.645 | -1.345 | 0.61 | 33% | 70.5 (5.42%) | -28.12 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=3 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · NEAR/USDT | long | 4 (2/2) | 4.852 | [-0.638, 13.380] | -0.638 | 10.343 | 16.21 | 50% | 32.57 (2.51%) | 516.11 | 0 | 0.0001 | BH q 0.0048 (m=96) | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · BNB/USDT | long | 6 (2/4) | 0.428 | [-0.841, 2.701] | 2.651 | -0.684 | 1.75 | 17% | 72.07 (5.54%) | 58.32 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · LINK/USDT | long | 6 (4/2) | 0.666 | [-0.798, 2.657] | -0.304 | 2.608 | 2.44 | 33% | 36.38 (2.8%) | 94.41 | 0 | 0.2575 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · ADA/USDT | long | 9 (5/4) | 0.071 | [-0.884, 1.748] | 0.745 | -0.771 | 1.11 | 11% | 163.69 (12.59%) | 6.28 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=9 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · ETH/USDT | short | 5 (2/3) | 0.062 | [-0.583, 0.706] | 0.830 | -0.450 | 1.20 | 60% | 40.64 (3.13%) | 7.59 | 0 | 0.9660 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · SOL/USDT | short | 8 (4/4) | -0.985 | [-1.631, -0.390] | -1.020 | -0.949 | 0.02 | 25% | 185.98 (14.31%) | -185.98 | 0 | 0.9813 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · XRP/USDT | short | 6 (4/2) | -0.908 | [-2.108, 0.482] | -1.175 | -0.377 | 0.29 | 17% | 186.63 (14.36%) | -186.63 | 0 | 0.7425 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · DOGE/USDT | short | 6 (3/3) | -0.391 | [-1.468, 0.370] | -0.109 | -0.673 | 0.35 | 50% | 74.95 (5.77%) | -60.84 | 0 | 0.7403 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · NEAR/USDT | short | 4 (4/0) | 0.042 | [-1.923, 1.456] | 0.042 | — | 1.06 | 75% | 79.63 (6.13%) | 0.37 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · BNB/USDT | short | 5 (3/2) | -0.716 | [-1.074, -0.145] | -0.950 | -0.365 | 0.09 | 20% | 94.62 (7.28%) | -94.62 | 0 | 0.7425 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · LINK/USDT | short | 6 (3/3) | -0.354 | [-1.021, 0.318] | 0.067 | -0.776 | 0.43 | 33% | 75.07 (5.77%) | -54.58 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · ADA/USDT | short | 5 (3/2) | 0.725 | [-1.010, 2.824] | -0.095 | 1.956 | 2.32 | 40% | 66.21 (5.09%) | 90.07 | 0 | 0.2575 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · ETH/USDT | long | 5 (3/2) | -0.135 | [-1.019, 0.836] | -0.058 | -0.250 | 0.77 | 40% | 58.52 (4.5%) | -18.78 | 0 | 0.7497 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · SOL/USDT | long | 3 (1/2) | -0.186 | [-1.289, 1.662] | -0.931 | 0.187 | 0.75 | 33% | 53.54 (4.12%) | -15.67 | 0 | 0.2575 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=3 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · XRP/USDT | long | 8 (4/4) | 1.395 | [-1.342, 7.255] | 4.097 | -1.307 | 2.58 | 12% | 215.67 (16.59%) | 258.7 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · DOGE/USDT | long | 4 (1/3) | -0.559 | [-1.714, 1.312] | 1.312 | -1.182 | 0.37 | 25% | 87.91 (6.76%) | -53.58 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · NEAR/USDT | long | 2 (0/2) | 9.484 | [0.922, 18.045] | — | 9.484 | inf | 100% | 0.0 (0.0%) | 516.02 | 0 | 0.0001 | BH q 0.0048 (m=96) | INCONCLUSIVE (n_total=2 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · BNB/USDT | long | 5 (3/2) | 0.357 | [-0.951, 2.529] | 1.211 | -0.923 | 1.63 | 20% | 45.38 (3.49%) | 42.01 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · LINK/USDT | long | 5 (3/2) | 0.539 | [-0.936, 2.972] | -0.840 | 2.608 | 2.04 | 20% | 65.85 (5.07%) | 59.52 | 0 | 0.2575 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · ADA/USDT | long | 7 (3/4) | -0.885 | [-1.384, -0.572] | -0.622 | -1.082 | 0.00 | 0% | 162.49 (12.5%) | -162.49 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · ETH/USDT | short | 5 (2/3) | -0.106 | [-0.780, 0.533] | 0.397 | -0.441 | 0.66 | 40% | 39.75 (3.06%) | -14.23 | 0 | 0.8509 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · SOL/USDT | short | 5 (4/1) | -0.861 | [-1.057, -0.686] | -0.890 | -0.746 | 0.00 | 0% | 106.97 (8.23%) | -106.97 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · XRP/USDT | short | 6 (5/1) | -1.343 | [-2.252, -0.546] | -0.966 | -3.228 | 0.00 | 0% | 255.21 (19.63%) | -255.21 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · DOGE/USDT | short | 4 (2/2) | -0.945 | [-2.465, 0.576] | -1.019 | -0.870 | 0.23 | 50% | 106.19 (8.17%) | -98.3 | 0 | 0.7425 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · NEAR/USDT | short | 4 (4/0) | 0.359 | [-0.566, 1.284] | 0.359 | — | 2.27 | 50% | 29.98 (2.31%) | 36.84 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · BNB/USDT | short | 5 (3/2) | -1.312 | [-1.561, -1.099] | -1.318 | -1.303 | 0.00 | 0% | 167.93 (12.92%) | -167.93 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · LINK/USDT | short | 6 (3/3) | -0.378 | [-1.021, 0.298] | 0.021 | -0.776 | 0.39 | 33% | 77.96 (6.0%) | -57.06 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · ADA/USDT | short | 3 (3/0) | 1.727 | [-1.334, 7.482] | 1.727 | — | 3.25 | 33% | 58.16 (4.47%) | 120.68 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=3 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · ETH/USDT | long | 5 (3/2) | -0.512 | [-1.019, 0.123] | -0.687 | -0.250 | 0.21 | 20% | 84.4 (6.49%) | -67.93 | 0 | 0.7497 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · SOL/USDT | long | 3 (2/1) | -0.744 | [-0.931, -0.458] | -0.694 | -0.843 | 0.00 | 0% | 52.76 (4.06%) | -52.76 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=3 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · XRP/USDT | long | 5 (4/1) | 3.814 | [-0.677, 12.197] | 4.943 | -0.705 | 10.93 | 40% | 51.91 (3.99%) | 482.91 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · DOGE/USDT | long | 2 (1/1) | -0.228 | [-1.769, 1.312] | 1.312 | -1.769 | 0.74 | 50% | 46.43 (3.57%) | -12.62 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=2 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · NEAR/USDT | long | 2 (1/1) | 8.804 | [-0.438, 18.045] | -0.438 | 18.045 | 41.20 | 50% | 11.94 (0.92%) | 483.75 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=2 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · BNB/USDT | long | 4 (2/2) | -0.592 | [-1.053, -0.262] | -0.262 | -0.923 | 0.00 | 0% | 55.54 (4.27%) | -55.54 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · LINK/USDT | long | 2 (0/2) | 2.608 | [-0.073, 5.289] | — | 2.608 | 72.83 | 50% | 1.86 (0.14%) | 130.77 | 0 | 0.2575 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=2 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · ADA/USDT | long | 7 (3/4) | -1.014 | [-1.973, -0.057] | -1.575 | -0.593 | 0.17 | 14% | 216.06 (16.62%) | -178.25 | 0 | 0.8561 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · ETH/USDT | short | 4 (2/2) | -0.045 | [-0.972, 1.159] | 0.864 | -0.953 | 0.91 | 25% | 49.02 (3.77%) | -3.49 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · SOL/USDT | short | 7 (3/4) | -1.080 | [-1.923, -0.281] | -1.628 | -0.669 | 0.07 | 29% | 191.38 (14.72%) | -182.55 | 0 | 0.8783 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · XRP/USDT | short | 5 (2/3) | -0.233 | [-1.355, 1.146] | -0.839 | 0.171 | 0.68 | 40% | 69.76 (5.37%) | -45.65 | 0 | 0.3706 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · DOGE/USDT | short | 6 (3/3) | -0.562 | [-1.556, -0.000] | -0.109 | -1.016 | 0.14 | 50% | 88.84 (6.83%) | -86.43 | 0 | 0.9660 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · NEAR/USDT | short | 5 (4/1) | 0.653 | [-0.166, 1.882] | 0.756 | 0.242 | 5.42 | 60% | 19.91 (1.53%) | 85.41 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · BNB/USDT | short | 6 (4/2) | -0.943 | [-1.286, -0.223] | -1.232 | -0.365 | 0.06 | 17% | 139.51 (10.73%) | -139.51 | 0 | 0.7425 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · LINK/USDT | short | 6 (4/2) | -0.277 | [-1.071, 0.631] | 0.089 | -1.010 | 0.59 | 33% | 52.29 (4.02%) | -44.36 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · ADA/USDT | short | 4 (3/1) | 2.293 | [-1.333, 5.919] | 1.605 | 4.357 | 4.44 | 50% | 63.9 (4.92%) | 208.52 | 0 | — | BH q — (m=96) | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:cross5 · ETH/USDT | long | 26 (14/12) | 0.681 | [-0.638, 2.100] | 1.242 | 0.026 | 1.76 | 27% | 501.03 (29.47%) | 477.11 | 0 | 0.5186 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:cross5 · SOL/USDT | long | 27 (17/10) | 0.087 | [-0.696, 1.106] | 0.150 | -0.019 | 1.12 | 22% | 206.73 (12.16%) | 32.69 | 0 | 0.5486 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:cross5 · XRP/USDT | long | 29 (16/13) | 1.522 | [-0.764, 5.333] | 3.105 | -0.426 | 3.05 | 28% | 690.41 (40.61%) | 1176.82 | 0 | 0.8655 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:cross5 · DOGE/USDT | long | 29 (16/13) | 0.369 | [-0.688, 2.008] | 0.808 | -0.172 | 1.51 | 21% | 354.75 (20.87%) | 269.99 | 0 | 0.6702 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:cross5 · NEAR/USDT | long | 31 (19/12) | 1.980 | [-0.820, 6.608] | -0.636 | 6.121 | 3.40 | 19% | 583.08 (34.3%) | 1242.48 | 0 | 0.1442 | BH q 1.0000 (m=96) | GO | **NO-GO** (q_value=1.0 (multiple comparisons, m=96)) |
| snipper:base:spec:cross5 · BNB/USDT | long | 29 (17/12) | 0.461 | [-0.659, 1.978] | 0.681 | 0.148 | 1.70 | 21% | 254.39 (14.96%) | 299.46 | 0 | 0.3973 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:cross5 · LINK/USDT | long | 33 (18/15) | -0.320 | [-0.824, 0.280] | -0.139 | -0.537 | 0.56 | 18% | 459.08 (27.0%) | -289.11 | 0 | 0.9084 | BH q 1.0000 (m=96) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:spec:cross5 · ADA/USDT | long | 25 (15/10) | -0.381 | [-0.760, 0.112] | -0.171 | -0.696 | 0.41 | 16% | 366.14 (21.54%) | -348.47 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:cross5 · ETH/USDT | short | 33 (21/12) | -0.211 | [-0.779, 0.538] | -0.506 | 0.305 | 0.73 | 24% | 392.49 (23.09%) | -286.15 | 0 | 0.3742 | BH q 1.0000 (m=96) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:base:spec:cross5 · SOL/USDT | short | 43 (25/18) | -0.012 | [-0.475, 0.522] | -0.224 | 0.282 | 0.98 | 42% | 221.75 (13.04%) | -61.68 | 0 | 0.2849 | BH q 1.0000 (m=96) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:base:spec:cross5 · XRP/USDT | short | 30 (22/8) | 0.075 | [-0.590, 0.843] | -0.208 | 0.854 | 1.11 | 33% | 473.96 (27.88%) | 150.12 | 0 | 0.1722 | BH q 1.0000 (m=96) | NO-GO (n_oos >= 10; PF >= 1.2) | **NO-GO** (n_oos >= 10; PF >= 1.2) |
| snipper:base:spec:cross5 · DOGE/USDT | short | 44 (24/20) | -0.132 | [-0.486, 0.329] | -0.042 | -0.239 | 0.78 | 30% | 324.26 (19.07%) | -240.69 | 0 | 0.7640 | BH q 1.0000 (m=96) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:spec:cross5 · NEAR/USDT | short | 32 (21/11) | -0.290 | [-0.709, 0.166] | -0.263 | -0.342 | 0.53 | 28% | 293.69 (17.28%) | -284.83 | 0 | 0.7625 | BH q 1.0000 (m=96) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:spec:cross5 · BNB/USDT | short | 36 (22/14) | -0.317 | [-0.659, 0.094] | -0.243 | -0.433 | 0.50 | 28% | 385.59 (22.68%) | -375.87 | 0 | 0.9810 | BH q 1.0000 (m=96) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:spec:cross5 · LINK/USDT | short | 30 (20/10) | -0.122 | [-0.709, 0.577] | -0.451 | 0.534 | 0.82 | 30% | 364.41 (21.44%) | -178.25 | 0 | 0.2799 | BH q 1.0000 (m=96) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:base:spec:cross5 · ADA/USDT | short | 40 (25/15) | 0.335 | [-0.108, 0.878] | 0.261 | 0.458 | 2.01 | 45% | 110.16 (6.48%) | 442.93 | 0 | 0.1800 | BH q 1.0000 (m=96) | GO | **NO-GO** (q_value=1.0 (multiple comparisons, m=96)) |
| snipper:adx_turn:spec:cross5 · ETH/USDT | long | 25 (13/12) | 0.192 | [-1.050, 1.590] | 0.418 | -0.054 | 1.20 | 16% | 401.01 (23.59%) | 62.85 | 0 | 0.5596 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · SOL/USDT | long | 21 (14/7) | -0.423 | [-1.026, 0.411] | -0.329 | -0.611 | 0.52 | 19% | 384.42 (22.61%) | -308.19 | 0 | 0.9065 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · XRP/USDT | long | 21 (14/7) | 2.090 | [-0.147, 5.173] | 1.699 | 2.872 | 4.79 | 38% | 350.76 (20.63%) | 1799.86 | 0 | 0.3097 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · DOGE/USDT | long | 18 (7/11) | 1.463 | [-0.596, 4.481] | 2.276 | 0.945 | 3.11 | 33% | 225.34 (13.26%) | 916.74 | 0 | 0.3271 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · NEAR/USDT | long | 25 (16/9) | 3.102 | [-0.842, 10.531] | 0.015 | 8.589 | 4.65 | 24% | 687.24 (40.43%) | 2521.46 | 0 | 0.0908 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · BNB/USDT | long | 18 (10/8) | 0.989 | [-0.535, 3.695] | 1.757 | 0.029 | 2.82 | 33% | 149.07 (8.77%) | 563.76 | 0 | 0.4984 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · LINK/USDT | long | 18 (11/7) | 0.398 | [-0.815, 2.215] | 1.046 | -0.621 | 1.54 | 22% | 390.03 (22.94%) | 163.16 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · ADA/USDT | long | 16 (10/6) | -0.298 | [-0.840, 0.377] | 0.090 | -0.946 | 0.55 | 19% | 256.39 (15.08%) | -188.09 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=16 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · ETH/USDT | short | 26 (18/8) | 0.003 | [-0.748, 0.856] | -0.352 | 0.802 | 1.00 | 23% | 246.17 (14.48%) | -56.6 | 0 | 0.2400 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · SOL/USDT | short | 32 (17/15) | 0.085 | [-0.482, 0.705] | 0.018 | 0.160 | 1.13 | 31% | 176.49 (10.38%) | 58.27 | 0 | 0.4023 | BH q 1.0000 (m=96) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:adx_turn:spec:cross5 · XRP/USDT | short | 18 (12/6) | -0.081 | [-1.053, 0.987] | -0.232 | 0.221 | 0.91 | 28% | 410.05 (24.12%) | -107.12 | 0 | 0.4276 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · DOGE/USDT | short | 30 (17/13) | -0.095 | [-0.590, 0.479] | 0.092 | -0.341 | 0.86 | 33% | 333.29 (19.61%) | -179.11 | 0 | 0.7876 | BH q 1.0000 (m=96) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:adx_turn:spec:cross5 · NEAR/USDT | short | 19 (11/8) | -0.079 | [-0.623, 0.564] | -0.177 | 0.056 | 0.85 | 37% | 131.21 (7.72%) | -100.16 | 0 | 0.3988 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=19 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · BNB/USDT | short | 22 (13/9) | -0.336 | [-0.874, 0.258] | -0.050 | -0.748 | 0.57 | 32% | 389.23 (22.9%) | -315.82 | 0 | 0.9774 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=22 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · LINK/USDT | short | 20 (10/10) | 0.243 | [-0.795, 1.502] | -0.272 | 0.759 | 1.31 | 40% | 268.58 (15.8%) | 169.97 | 0 | 0.2575 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=20 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · ADA/USDT | short | 31 (19/12) | 0.443 | [-0.085, 1.195] | 0.380 | 0.542 | 2.32 | 55% | 123.91 (7.29%) | 471.55 | 0 | 0.3139 | BH q 1.0000 (m=96) | GO | **NO-GO** (q_value=1.0 (multiple comparisons, m=96)) |
| snipper:bbwp_fresh_blue:spec:cross5 · ETH/USDT | long | 27 (17/10) | -0.167 | [-0.927, 0.918] | 0.334 | -1.020 | 0.81 | 15% | 488.04 (28.71%) | -143.35 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · SOL/USDT | long | 21 (12/9) | 0.439 | [-0.561, 1.716] | 0.656 | 0.148 | 1.67 | 29% | 211.14 (12.42%) | 296.78 | 0 | 0.4682 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · XRP/USDT | long | 26 (16/10) | 4.506 | [-0.170, 12.657] | 5.956 | 2.187 | 8.38 | 35% | 721.5 (42.44%) | 5615.11 | 0 | 0.2325 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · DOGE/USDT | long | 18 (9/9) | 1.319 | [-0.522, 3.781] | 1.596 | 1.042 | 3.03 | 33% | 164.43 (9.67%) | 824.02 | 0 | 0.2319 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · NEAR/USDT | long | 25 (15/10) | 0.851 | [-0.603, 2.907] | 0.204 | 1.821 | 2.09 | 28% | 494.44 (29.08%) | 635.69 | 0 | 0.0896 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · BNB/USDT | long | 17 (10/7) | 1.127 | [-0.619, 4.010] | 1.659 | 0.365 | 2.86 | 29% | 159.52 (9.38%) | 617.33 | 0 | 0.3284 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=17 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · LINK/USDT | long | 25 (18/7) | 0.143 | [-0.757, 1.394] | 0.168 | 0.077 | 1.21 | 20% | 296.57 (17.45%) | 54.37 | 0 | 0.4204 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · ADA/USDT | long | 18 (11/7) | -0.120 | [-0.919, 1.211] | 0.508 | -1.108 | 0.84 | 17% | 369.49 (21.73%) | -107.82 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · ETH/USDT | short | 26 (16/10) | -0.261 | [-0.871, 0.599] | -0.744 | 0.512 | 0.66 | 19% | 402.18 (23.66%) | -262.81 | 0 | 0.3276 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · SOL/USDT | short | 30 (17/13) | 0.010 | [-0.593, 0.758] | -0.067 | 0.111 | 1.02 | 33% | 416.79 (24.52%) | -34.15 | 0 | 0.4338 | BH q 1.0000 (m=96) | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:bbwp_fresh_blue:spec:cross5 · XRP/USDT | short | 22 (15/7) | -0.328 | [-0.998, 0.448] | -0.117 | -0.780 | 0.63 | 32% | 1287.54 (75.74%) | -807.97 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=22 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · DOGE/USDT | short | 31 (18/13) | 0.009 | [-0.443, 0.558] | 0.072 | -0.078 | 1.02 | 35% | 372.42 (21.91%) | 7.51 | 0 | 0.5855 | BH q 1.0000 (m=96) | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:bbwp_fresh_blue:spec:cross5 · NEAR/USDT | short | 24 (16/8) | -0.254 | [-0.824, 0.407] | -0.132 | -0.496 | 0.61 | 29% | 257.35 (15.14%) | -231.3 | 0 | 0.7879 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · BNB/USDT | short | 27 (15/12) | -0.298 | [-0.793, 0.333] | 0.076 | -0.765 | 0.57 | 26% | 469.74 (27.63%) | -356.41 | 0 | 1.0000 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · LINK/USDT | short | 23 (13/10) | -0.458 | [-0.962, 0.223] | -0.657 | -0.199 | 0.42 | 17% | 455.02 (26.77%) | -337.19 | 0 | 0.6233 | BH q 1.0000 (m=96) | INCONCLUSIVE (n_total=23 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · ADA/USDT | short | 32 (18/14) | 0.158 | [-0.178, 0.642] | 0.252 | 0.036 | 1.45 | 44% | 147.1 (8.65%) | 163.33 | 0 | 0.4663 | BH q 1.0000 (m=96) | GO | **NO-GO** (q_value=1.0 (multiple comparisons, m=96)) |

### C2. Per-asset cells, informational (BTC = seen asset; as-run gate; 10x isolated book)

| cell | side | n (IS/OOS) | exp. R net | CI95 (cluster) | exp. IS | exp. OOS | PF | win | max DD USDT (% start) | net USDT | liq | p OOS>0 | corrected | r4 gate | **r7 verdict** |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:base:spec:pro5 · BTC/USDT | long | 4 (2/2) | 0.080 | [-0.841, 1.056] | 1.000 | -0.841 | 1.19 | 50% | 41.47 (3.19%) | 10.45 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:base:spec:pro5 · BTC/USDT | short | 7 (5/2) | -0.722 | [-1.492, -0.099] | -0.644 | -0.917 | 0.06 | 29% | 131.44 (10.11%) | -131.44 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · BTC/USDT | long | 7 (4/3) | -0.140 | [-0.858, 0.645] | 0.187 | -0.577 | 0.73 | 29% | 77.22 (5.94%) | -26.65 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · ETH/USDT | long | 7 (3/4) | 0.181 | [-0.919, 1.697] | 0.748 | -0.244 | 1.33 | 29% | 82.62 (6.36%) | 26.87 | 0 | 0.7619 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · SOL/USDT | long | 8 (5/3) | -0.263 | [-1.287, 0.878] | -0.043 | -0.630 | 0.67 | 25% | 118.96 (9.15%) | -51.28 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · XRP/USDT | long | 14 (8/6) | 0.753 | [-1.450, 4.312] | 2.430 | -1.483 | 1.80 | 14% | 411.39 (31.65%) | 192.54 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=14 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · DOGE/USDT | long | 8 (4/4) | 0.041 | [-1.027, 1.808] | 0.984 | -0.902 | 1.06 | 25% | 131.36 (10.1%) | 4.55 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · NEAR/USDT | long | 7 (4/3) | 2.739 | [-0.580, 6.107] | -0.415 | 6.944 | 7.76 | 43% | 42.26 (3.25%) | 487.32 | 0 | 0.0001 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · BNB/USDT | long | 8 (4/4) | 0.762 | [-0.689, 2.767] | 1.048 | 0.475 | 2.63 | 25% | 63.02 (4.85%) | 147.15 | 0 | 0.2966 | — | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · LINK/USDT | long | 8 (5/3) | 1.117 | [-0.482, 3.588] | 0.101 | 2.810 | 3.24 | 62% | 70.76 (5.44%) | 226.34 | 0 | 0.0352 | — | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · ADA/USDT | long | 9 (6/3) | 1.456 | [-1.172, 4.360] | 1.187 | 1.995 | 2.87 | 33% | 177.66 (13.67%) | 346.44 | 0 | 0.2575 | — | INCONCLUSIVE (n_total=9 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · BTC/USDT | short | 7 (5/2) | -0.201 | [-1.028, 0.808] | -0.526 | 0.612 | 0.69 | 29% | 84.86 (6.53%) | -38.57 | 0 | 0.2503 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · ETH/USDT | short | 5 (2/3) | 0.501 | [-0.172, 1.097] | 1.010 | 0.162 | 4.54 | 60% | 19.95 (1.53%) | 67.27 | 0 | 0.4046 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · SOL/USDT | short | 8 (4/4) | -1.003 | [-1.886, -0.052] | -0.668 | -1.338 | 0.15 | 38% | 196.28 (15.1%) | -196.28 | 0 | 0.9813 | — | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · XRP/USDT | short | 7 (4/3) | -0.654 | [-1.825, 0.582] | -1.120 | -0.032 | 0.39 | 29% | 177.09 (13.62%) | -160.36 | 0 | 0.5923 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · DOGE/USDT | short | 8 (4/4) | -0.283 | [-0.761, 0.194] | -0.582 | 0.016 | 0.36 | 25% | 73.62 (5.66%) | -63.0 | 0 | 0.4364 | — | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · NEAR/USDT | short | 5 (4/1) | -0.276 | [-2.097, 1.177] | -0.152 | -0.770 | 0.69 | 60% | 96.34 (7.41%) | -39.56 | 0 | — | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · BNB/USDT | short | 5 (2/3) | -0.992 | [-1.649, -0.230] | -1.095 | -0.923 | 0.07 | 20% | 132.59 (10.2%) | -132.59 | 0 | 0.9648 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · LINK/USDT | short | 6 (3/3) | -0.255 | [-1.078, 0.550] | 0.242 | -0.753 | 0.55 | 50% | 69.21 (5.32%) | -42.26 | 0 | 0.9631 | — | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:base:asrun:pro5 · ADA/USDT | short | 5 (3/2) | 0.155 | [-2.447, 2.384] | -1.166 | 2.138 | 1.14 | 60% | 175.21 (13.48%) | -5.31 | 0 | 0.0001 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · BTC/USDT | long | 3 (1/2) | 0.966 | [-0.552, 3.970] | 3.970 | -0.536 | 3.70 | 33% | 27.6 (2.12%) | 75.61 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=3 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:spec:pro5 · BTC/USDT | short | 4 (2/2) | -1.165 | [-2.150, -0.237] | -1.221 | -1.109 | 0.03 | 25% | 126.94 (9.76%) | -126.94 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · BTC/USDT | long | 3 (1/2) | 1.104 | [-0.552, 3.970] | 3.970 | -0.329 | 6.04 | 33% | 16.83 (1.29%) | 86.39 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=3 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · ETH/USDT | long | 6 (4/2) | -0.393 | [-1.255, 0.568] | -0.464 | -0.250 | 0.48 | 33% | 79.0 (6.08%) | -62.66 | 0 | 0.7497 | — | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · SOL/USDT | long | 4 (2/2) | -0.310 | [-1.134, 0.965] | -0.760 | 0.140 | 0.56 | 25% | 68.29 (5.25%) | -32.72 | 0 | 0.2575 | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · XRP/USDT | long | 8 (4/4) | 1.512 | [-1.385, 8.008] | 4.394 | -1.369 | 2.54 | 12% | 245.62 (18.89%) | 273.74 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · DOGE/USDT | long | 5 (1/4) | -0.716 | [-1.490, 0.556] | 1.312 | -1.224 | 0.27 | 20% | 121.61 (9.35%) | -87.28 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · NEAR/USDT | long | 3 (1/2) | 5.925 | [-1.395, 18.249] | -1.395 | 9.586 | 13.74 | 67% | 36.34 (2.8%) | 471.46 | 0 | 0.0001 | — | INCONCLUSIVE (n_total=3 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · BNB/USDT | long | 5 (3/2) | 0.360 | [-0.941, 2.529] | 1.211 | -0.915 | 1.64 | 20% | 44.97 (3.46%) | 42.4 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · LINK/USDT | long | 5 (3/2) | 0.498 | [-1.161, 2.974] | -1.052 | 2.823 | 1.79 | 40% | 80.74 (6.21%) | 54.31 | 0 | 0.0001 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · ADA/USDT | long | 7 (3/4) | -0.970 | [-1.528, -0.523] | -0.556 | -1.280 | 0.00 | 0% | 184.79 (14.21%) | -184.79 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · BTC/USDT | short | 4 (2/2) | -1.156 | [-2.183, 0.101] | -0.925 | -1.387 | 0.13 | 25% | 126.73 (9.75%) | -126.73 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · ETH/USDT | short | 5 (2/3) | -0.164 | [-0.858, 0.504] | 0.585 | -0.664 | 0.59 | 40% | 50.11 (3.85%) | -20.27 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · SOL/USDT | short | 5 (4/1) | -0.961 | [-1.148, -0.773] | -1.014 | -0.746 | 0.00 | 0% | 117.67 (9.05%) | -117.67 | 0 | — | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · XRP/USDT | short | 6 (5/1) | -1.292 | [-2.126, -0.523] | -0.952 | -2.990 | 0.00 | 17% | 250.16 (19.24%) | -250.16 | 0 | — | — | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · DOGE/USDT | short | 4 (2/2) | -0.696 | [-1.968, 0.576] | -0.719 | -0.673 | 0.29 | 50% | 80.05 (6.16%) | -72.17 | 0 | 0.7425 | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · NEAR/USDT | short | 4 (4/0) | 0.379 | [-0.566, 1.324] | 0.379 | — | 2.34 | 50% | 29.99 (2.31%) | 37.89 | 0 | — | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · BNB/USDT | short | 5 (3/2) | -1.314 | [-1.561, -1.101] | -1.322 | -1.303 | 0.00 | 0% | 168.16 (12.94%) | -168.16 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · LINK/USDT | short | 6 (3/3) | -0.272 | [-0.879, 0.393] | 0.229 | -0.773 | 0.50 | 33% | 66.9 (5.15%) | -40.9 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:adx_turn:asrun:pro5 · ADA/USDT | short | 3 (3/0) | 2.621 | [-1.264, 10.096] | 2.621 | — | 4.52 | 33% | 56.58 (4.35%) | 186.04 | 0 | — | — | INCONCLUSIVE (n_total=3 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · BTC/USDT | long | 4 (3/1) | 0.720 | [-0.750, 2.885] | 1.336 | -1.130 | 2.92 | 50% | 41.12 (3.16%) | 72.06 | 0 | — | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:spec:pro5 · BTC/USDT | short | 4 (2/2) | -0.694 | [-1.163, -0.120] | -0.296 | -1.092 | 0.04 | 25% | 74.52 (5.73%) | -74.52 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · BTC/USDT | long | 5 (4/1) | 0.532 | [-0.788, 2.325] | 0.948 | -1.130 | 2.23 | 40% | 41.24 (3.17%) | 65.78 | 0 | — | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · ETH/USDT | long | 7 (5/2) | -0.861 | [-1.323, -0.241] | -1.105 | -0.250 | 0.10 | 14% | 167.77 (12.91%) | -152.48 | 0 | 0.7497 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · SOL/USDT | long | 5 (3/2) | -0.000 | [-1.525, 1.580] | 0.793 | -1.190 | 1.00 | 40% | 65.1 (5.01%) | 2.59 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · XRP/USDT | long | 5 (3/2) | 3.768 | [-1.603, 13.818] | 7.220 | -1.409 | 4.87 | 20% | 175.27 (13.48%) | 441.3 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · DOGE/USDT | long | 4 (2/2) | -0.579 | [-1.513, 0.705] | 0.098 | -1.257 | 0.36 | 25% | 63.68 (4.9%) | -59.66 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · NEAR/USDT | long | 7 (4/3) | 2.371 | [-1.559, 6.142] | -1.515 | 7.551 | 3.55 | 29% | 153.09 (11.78%) | 427.15 | 0 | 0.0001 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · BNB/USDT | long | 5 (3/2) | 0.712 | [-0.355, 2.494] | -0.054 | 1.860 | 4.82 | 40% | 22.77 (1.75%) | 80.52 | 0 | 0.2575 | — | INCONCLUSIVE (n_total=5 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · LINK/USDT | long | 4 (3/1) | 0.789 | [-1.036, 5.289] | -0.712 | 5.289 | 2.48 | 25% | 54.55 (4.2%) | 74.67 | 0 | — | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · ADA/USDT | long | 8 (4/4) | -1.279 | [-2.219, -0.237] | -1.805 | -0.753 | 0.14 | 12% | 293.45 (22.57%) | -250.16 | 0 | 0.8071 | — | INCONCLUSIVE (n_total=8 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · BTC/USDT | short | 4 (2/2) | -0.529 | [-1.052, 0.275] | -0.029 | -1.029 | 0.24 | 25% | 56.95 (4.38%) | -56.95 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · ETH/USDT | short | 4 (2/2) | -0.093 | [-0.952, 0.766] | 0.766 | -0.952 | 0.80 | 50% | 44.93 (3.46%) | -6.47 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · SOL/USDT | short | 10 (4/6) | -1.089 | [-1.879, -0.249] | -1.124 | -1.066 | 0.16 | 30% | 281.86 (21.68%) | -266.72 | 0 | 0.9840 | — | INCONCLUSIVE (n_total=10 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · XRP/USDT | short | 7 (4/3) | -0.183 | [-0.925, 0.750] | -0.649 | 0.437 | 0.67 | 43% | 95.35 (7.33%) | -52.48 | 0 | 0.3706 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · DOGE/USDT | short | 6 (3/3) | -0.503 | [-1.351, 0.076] | -0.151 | -0.855 | 0.18 | 33% | 83.04 (6.39%) | -74.97 | 0 | 0.8558 | — | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · NEAR/USDT | short | 4 (4/0) | 0.536 | [-0.345, 1.575] | 0.536 | — | 4.11 | 50% | 17.38 (1.34%) | 51.93 | 0 | — | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · BNB/USDT | short | 6 (4/2) | -0.945 | [-1.287, -0.225] | -1.235 | -0.365 | 0.06 | 17% | 140.64 (10.82%) | -140.64 | 0 | 0.7425 | — | INCONCLUSIVE (n_total=6 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · LINK/USDT | short | 7 (4/3) | -0.128 | [-0.819, 0.630] | 0.266 | -0.652 | 0.75 | 43% | 49.8 (3.83%) | -24.01 | 0 | 0.9660 | — | INCONCLUSIVE (n_total=7 < 30) | **INCONCLUSIVE** |
| pro:bbwp_fresh_blue:asrun:pro5 · ADA/USDT | short | 4 (3/1) | 2.811 | [-1.156, 7.330] | 2.595 | 3.461 | 5.87 | 50% | 56.49 (4.35%) | 241.51 | 0 | — | — | INCONCLUSIVE (n_total=4 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:cross5 · BTC/USDT | long | 25 (14/11) | 0.230 | [-0.386, 0.822] | 0.187 | 0.285 | 1.37 | 36% | 225.44 (13.26%) | 149.14 | 0 | 0.3037 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:cross5 · BTC/USDT | short | 30 (20/10) | -0.104 | [-0.739, 0.707] | -0.300 | 0.290 | 0.88 | 30% | 263.63 (15.51%) | -139.35 | 0 | 0.3932 | — | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:base:spec:iso10 · BTC/USDT | long | 25 (14/11) | 0.227 | [-0.391, 0.820] | 0.181 | 0.285 | 1.37 | 36% | 224.97 (13.23%) | 146.4 | 2 | 0.3037 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:iso10 · ETH/USDT | long | 26 (14/12) | 0.267 | [-0.726, 1.478] | 0.473 | 0.026 | 1.29 | 27% | 425.3 (25.02%) | 166.39 | 8 | 0.5186 | — | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:iso10 · SOL/USDT | long | 27 (17/10) | 0.086 | [-0.696, 1.107] | 0.148 | -0.019 | 1.12 | 22% | 213.63 (12.57%) | 32.5 | 14 | 0.5486 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:iso10 · XRP/USDT | long | 29 (16/13) | 1.514 | [-0.778, 5.325] | 3.090 | -0.427 | 3.02 | 28% | 700.89 (41.23%) | 1161.79 | 8 | 0.8655 | — | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:iso10 · DOGE/USDT | long | 31 (16/15) | 0.325 | [-0.661, 1.897] | 0.829 | -0.213 | 1.47 | 23% | 361.28 (21.25%) | 248.14 | 17 | 0.6934 | — | NO-GO (expectancy_oos > 0; liquidations == 0) | **NO-GO** (expectancy_oos > 0; liquidations == 0) |
| snipper:base:spec:iso10 · NEAR/USDT | long | 31 (19/12) | 2.084 | [-0.674, 6.613] | -0.474 | 6.134 | 3.90 | 19% | 503.82 (29.64%) | 1511.81 | 20 | 0.1272 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:base:spec:iso10 · BNB/USDT | long | 29 (17/12) | 0.280 | [-0.864, 1.837] | 0.388 | 0.126 | 1.36 | 17% | 304.64 (17.92%) | 122.22 | 6 | 0.4221 | — | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:iso10 · LINK/USDT | long | 34 (19/15) | -0.396 | [-0.882, 0.161] | -0.248 | -0.584 | 0.47 | 18% | 529.0 (31.12%) | -359.04 | 16 | 0.9183 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 · ADA/USDT | long | 29 (17/12) | -0.403 | [-0.725, 0.020] | -0.205 | -0.683 | 0.36 | 14% | 425.01 (25.0%) | -425.01 | 16 | 1.0000 | — | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:base:spec:iso10 · BTC/USDT | short | 30 (20/10) | -0.105 | [-0.742, 0.705] | -0.300 | 0.286 | 0.87 | 30% | 263.63 (15.51%) | -140.7 | 2 | 0.3950 | — | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 · ETH/USDT | short | 33 (21/12) | -0.195 | [-0.765, 0.545] | -0.479 | 0.302 | 0.74 | 24% | 355.21 (20.89%) | -266.23 | 8 | 0.3747 | — | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 · SOL/USDT | short | 45 (27/18) | -0.001 | [-0.435, 0.507] | -0.194 | 0.289 | 1.00 | 40% | 237.51 (13.97%) | -44.32 | 14 | 0.2783 | — | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 · XRP/USDT | short | 31 (23/8) | 0.103 | [-0.545, 0.848] | -0.158 | 0.854 | 1.16 | 35% | 526.02 (30.94%) | 208.64 | 8 | 0.1722 | — | NO-GO (n_oos >= 10; PF >= 1.2; liquidations == 0) | **NO-GO** (n_oos >= 10; PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 · DOGE/USDT | short | 44 (25/19) | -0.118 | [-0.458, 0.329] | -0.050 | -0.207 | 0.80 | 30% | 310.77 (18.28%) | -218.44 | 17 | 0.7270 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 · NEAR/USDT | short | 34 (22/12) | -0.243 | [-0.620, 0.182] | -0.229 | -0.268 | 0.55 | 26% | 328.51 (19.32%) | -308.37 | 20 | 0.7550 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 · BNB/USDT | short | 36 (22/14) | -0.323 | [-0.666, 0.089] | -0.252 | -0.433 | 0.49 | 28% | 378.71 (22.28%) | -368.99 | 6 | 0.9810 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 · LINK/USDT | short | 30 (20/10) | -0.112 | [-0.683, 0.586] | -0.459 | 0.583 | 0.82 | 27% | 345.82 (20.34%) | -169.04 | 16 | 0.2544 | — | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:base:spec:iso10 · ADA/USDT | short | 42 (27/15) | 0.364 | [-0.057, 0.883] | 0.318 | 0.445 | 2.12 | 45% | 97.48 (5.73%) | 507.66 | 16 | 0.1917 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:base:asrun:cross5 · BTC/USDT | long | 31 (20/11) | -0.099 | [-0.684, 0.566] | -0.100 | -0.097 | 0.88 | 29% | 325.73 (19.16%) | -127.77 | 0 | 0.5863 | — | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:asrun:cross5 · ETH/USDT | long | 31 (16/15) | 0.771 | [-0.493, 2.250] | 1.122 | 0.396 | 1.82 | 32% | 404.03 (23.77%) | 769.25 | 0 | 0.3702 | — | GO | **NO-GO** (not in a corrected family) |
| snipper:base:asrun:cross5 · SOL/USDT | long | 39 (23/16) | 0.161 | [-0.464, 1.005] | 0.478 | -0.295 | 1.22 | 31% | 447.81 (26.34%) | 111.27 | 0 | 0.7208 | — | NO-GO (expectancy_oos > 0) | **NO-GO** (expectancy_oos > 0) |
| snipper:base:asrun:cross5 · XRP/USDT | long | 33 (18/15) | 1.370 | [-0.635, 4.771] | 2.874 | -0.435 | 2.81 | 24% | 908.78 (53.46%) | 1106.92 | 0 | 0.8706 | — | NO-GO (expectancy_oos > 0; maxDD < 35% of start) | **NO-GO** (expectancy_oos > 0; maxDD < 35% of start) |
| snipper:base:asrun:cross5 · DOGE/USDT | long | 36 (22/14) | 0.216 | [-0.685, 1.332] | 0.278 | 0.118 | 1.25 | 17% | 438.61 (25.8%) | 141.4 | 0 | 0.4578 | — | GO | **NO-GO** (not in a corrected family) |
| snipper:base:asrun:cross5 · NEAR/USDT | long | 38 (27/11) | 1.611 | [-0.774, 6.376] | -0.517 | 6.835 | 2.71 | 21% | 674.62 (39.68%) | 1529.05 | 0 | 0.0971 | — | NO-GO (maxDD < 35% of start) | **NO-GO** (maxDD < 35% of start) |
| snipper:base:asrun:cross5 · BNB/USDT | long | 33 (20/13) | 0.506 | [-0.602, 1.867] | 0.959 | -0.190 | 1.67 | 27% | 419.2 (24.66%) | 440.85 | 0 | 0.6340 | — | NO-GO (expectancy_oos > 0) | **NO-GO** (expectancy_oos > 0) |
| snipper:base:asrun:cross5 · LINK/USDT | long | 40 (23/17) | -0.349 | [-1.056, 0.541] | -0.286 | -0.434 | 0.65 | 20% | 810.91 (47.7%) | -374.8 | 0 | 0.8582 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; maxDD < 35% of start) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; maxDD < 35% of start) |
| snipper:base:asrun:cross5 · ADA/USDT | long | 36 (21/15) | -0.088 | [-0.860, 1.057] | 0.465 | -0.862 | 0.90 | 17% | 868.83 (51.11%) | -353.22 | 0 | 1.0000 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; maxDD < 35% of start) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; maxDD < 35% of start) |
| snipper:base:asrun:cross5 · BTC/USDT | short | 34 (21/13) | -0.271 | [-0.836, 0.413] | -0.338 | -0.163 | 0.70 | 24% | 319.57 (18.8%) | -307.3 | 0 | 0.6134 | — | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:asrun:cross5 · ETH/USDT | short | 33 (21/12) | 0.028 | [-0.753, 1.076] | -0.479 | 0.916 | 1.04 | 30% | 393.35 (23.14%) | -50.62 | 0 | 0.2199 | — | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:base:asrun:cross5 · SOL/USDT | short | 42 (27/15) | -0.052 | [-0.749, 0.878] | -0.166 | 0.154 | 0.93 | 36% | 474.55 (27.91%) | -133.27 | 0 | 0.4712 | — | NO-GO (PF >= 1.2) | **NO-GO** (PF >= 1.2) |
| snipper:base:asrun:cross5 · XRP/USDT | short | 30 (21/9) | 0.531 | [-0.241, 1.471] | -0.049 | 1.887 | 1.93 | 47% | 478.06 (28.12%) | 1219.08 | 0 | 0.0009 | — | NO-GO (n_oos >= 10) | **NO-GO** (n_oos >= 10) |
| snipper:base:asrun:cross5 · DOGE/USDT | short | 42 (26/16) | 0.171 | [-0.336, 0.824] | 0.055 | 0.360 | 1.28 | 38% | 348.23 (20.48%) | 223.24 | 0 | 0.2748 | — | GO | **NO-GO** (not in a corrected family) |
| snipper:base:asrun:cross5 · NEAR/USDT | short | 35 (21/14) | -0.084 | [-0.539, 0.421] | 0.066 | -0.309 | 0.87 | 43% | 320.28 (18.84%) | -177.99 | 0 | 0.7549 | — | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:asrun:cross5 · BNB/USDT | short | 36 (22/14) | -0.120 | [-0.567, 0.363] | -0.074 | -0.191 | 0.81 | 33% | 355.83 (20.93%) | -183.63 | 0 | 0.6599 | — | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:asrun:cross5 · LINK/USDT | short | 34 (22/12) | -0.423 | [-0.854, 0.029] | -0.560 | -0.171 | 0.50 | 29% | 487.78 (28.69%) | -426.79 | 0 | 0.6487 | — | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:base:asrun:cross5 · ADA/USDT | short | 37 (23/14) | 0.529 | [-0.120, 1.389] | 0.350 | 0.823 | 2.32 | 46% | 183.75 (10.81%) | 798.58 | 0 | 0.2189 | — | GO | **NO-GO** (not in a corrected family) |
| snipper:base:asrun:iso10 · BTC/USDT | long | 31 (20/11) | -0.099 | [-0.684, 0.566] | -0.100 | -0.097 | 0.88 | 29% | 325.6 (19.15%) | -127.72 | 1 | 0.5863 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:base:asrun:iso10 · ETH/USDT | long | 31 (16/15) | 0.498 | [-0.602, 1.878] | 0.613 | 0.375 | 1.52 | 32% | 366.33 (21.55%) | 475.99 | 8 | 0.3788 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:base:asrun:iso10 · SOL/USDT | long | 40 (24/16) | 0.192 | [-0.426, 1.040] | 0.516 | -0.295 | 1.27 | 30% | 510.82 (30.05%) | 164.49 | 16 | 0.7208 | — | NO-GO (expectancy_oos > 0; liquidations == 0) | **NO-GO** (expectancy_oos > 0; liquidations == 0) |
| snipper:base:asrun:iso10 · XRP/USDT | long | 33 (18/15) | 1.331 | [-0.678, 4.729] | 2.804 | -0.436 | 2.68 | 24% | 915.56 (53.86%) | 1021.56 | 8 | 0.8707 | — | NO-GO (expectancy_oos > 0; liquidations == 0; maxDD < 35% of start) | **NO-GO** (expectancy_oos > 0; liquidations == 0; maxDD < 35% of start) |
| snipper:base:asrun:iso10 · DOGE/USDT | long | 36 (22/14) | 0.191 | [-0.717, 1.307] | 0.244 | 0.107 | 1.22 | 17% | 474.2 (27.89%) | 104.32 | 15 | 0.4641 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:base:asrun:iso10 · NEAR/USDT | long | 43 (32/11) | 1.416 | [-0.670, 5.704] | -0.446 | 6.834 | 2.68 | 19% | 641.31 (37.72%) | 1424.78 | 29 | 0.0974 | — | NO-GO (liquidations == 0; maxDD < 35% of start) | **NO-GO** (liquidations == 0; maxDD < 35% of start) |
| snipper:base:asrun:iso10 · BNB/USDT | long | 34 (21/13) | 0.341 | [-0.761, 1.707] | 0.669 | -0.190 | 1.41 | 24% | 516.01 (30.35%) | 240.25 | 5 | 0.6340 | — | NO-GO (expectancy_oos > 0; liquidations == 0) | **NO-GO** (expectancy_oos > 0; liquidations == 0) |
| snipper:base:asrun:iso10 · LINK/USDT | long | 40 (23/17) | -0.432 | [-1.094, 0.448] | -0.398 | -0.478 | 0.58 | 20% | 894.14 (52.6%) | -458.23 | 17 | 0.8752 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0; maxDD < 35% of start) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0; maxDD < 35% of start) |
| snipper:base:asrun:iso10 · ADA/USDT | long | 42 (25/17) | -0.204 | [-0.901, 0.815] | 0.294 | -0.936 | 0.77 | 17% | 945.33 (55.61%) | -457.24 | 19 | 1.0000 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0; maxDD < 35% of start) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0; maxDD < 35% of start) |
| snipper:base:asrun:iso10 · BTC/USDT | short | 34 (21/13) | -0.273 | [-0.837, 0.412] | -0.338 | -0.166 | 0.70 | 24% | 320.69 (18.86%) | -308.44 | 1 | 0.6155 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:base:asrun:iso10 · ETH/USDT | short | 33 (21/12) | 0.051 | [-0.727, 1.091] | -0.444 | 0.916 | 1.07 | 30% | 350.42 (20.61%) | -47.57 | 8 | 0.2199 | — | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:base:asrun:iso10 · SOL/USDT | short | 43 (28/15) | 0.049 | [-0.636, 0.945] | -0.009 | 0.158 | 1.07 | 35% | 527.31 (31.02%) | 10.77 | 16 | 0.4681 | — | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:base:asrun:iso10 · XRP/USDT | short | 31 (22/9) | 0.565 | [-0.167, 1.472] | 0.024 | 1.887 | 2.10 | 48% | 471.7 (27.75%) | 1330.39 | 8 | 0.0009 | — | NO-GO (n_oos >= 10; liquidations == 0) | **NO-GO** (n_oos >= 10; liquidations == 0) |
| snipper:base:asrun:iso10 · DOGE/USDT | short | 43 (26/17) | 0.176 | [-0.315, 0.835] | 0.081 | 0.322 | 1.30 | 37% | 334.58 (19.68%) | 238.23 | 15 | 0.2898 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:base:asrun:iso10 · NEAR/USDT | short | 39 (25/14) | -0.156 | [-0.565, 0.345] | -0.188 | -0.097 | 0.77 | 38% | 300.24 (17.66%) | -271.63 | 29 | 0.5984 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:base:asrun:iso10 · BNB/USDT | short | 36 (22/14) | -0.126 | [-0.572, 0.358] | -0.084 | -0.191 | 0.81 | 33% | 319.31 (18.78%) | -183.93 | 5 | 0.6599 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:base:asrun:iso10 · LINK/USDT | short | 34 (22/12) | -0.405 | [-0.808, 0.043] | -0.541 | -0.156 | 0.50 | 26% | 447.97 (26.35%) | -390.21 | 17 | 0.6413 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:base:asrun:iso10 · ADA/USDT | short | 41 (27/14) | 0.372 | [-0.208, 1.190] | 0.145 | 0.809 | 1.83 | 44% | 162.57 (9.56%) | 519.51 | 19 | 0.2236 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:adx_turn:spec:cross5 · BTC/USDT | long | 24 (13/11) | 0.276 | [-0.584, 1.337] | -0.346 | 1.012 | 1.41 | 21% | 343.37 (20.2%) | 165.05 | 0 | 0.1627 | — | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:cross5 · BTC/USDT | short | 27 (18/9) | 0.104 | [-0.576, 1.072] | -0.221 | 0.754 | 1.15 | 30% | 214.74 (12.63%) | 56.58 | 0 | 0.2869 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · BTC/USDT | long | 24 (13/11) | 0.273 | [-0.589, 1.335] | -0.352 | 1.012 | 1.41 | 21% | 345.66 (20.33%) | 162.11 | 1 | 0.1627 | — | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · ETH/USDT | long | 25 (13/12) | 0.189 | [-1.047, 1.582] | 0.412 | -0.054 | 1.20 | 16% | 400.72 (23.57%) | 62.75 | 4 | 0.5596 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · SOL/USDT | long | 21 (14/7) | -0.437 | [-1.048, 0.403] | -0.350 | -0.611 | 0.51 | 19% | 400.33 (23.55%) | -323.15 | 8 | 0.9065 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · XRP/USDT | long | 21 (14/7) | 2.099 | [-0.138, 5.183] | 1.713 | 2.872 | 4.87 | 38% | 361.02 (21.24%) | 1846.54 | 4 | 0.3097 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · DOGE/USDT | long | 18 (7/11) | 1.460 | [-0.602, 4.474] | 2.291 | 0.931 | 3.10 | 33% | 221.93 (13.05%) | 910.62 | 9 | 0.3290 | — | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · NEAR/USDT | long | 26 (16/10) | 3.053 | [-0.705, 10.283] | 0.157 | 7.686 | 5.09 | 23% | 614.34 (36.14%) | 2696.45 | 13 | 0.1043 | — | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · BNB/USDT | long | 18 (10/8) | 0.695 | [-0.866, 3.447] | 1.253 | -0.004 | 1.95 | 28% | 230.97 (13.59%) | 347.78 | 3 | 0.5457 | — | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · LINK/USDT | long | 18 (11/7) | 0.398 | [-0.815, 2.215] | 1.046 | -0.621 | 1.54 | 22% | 388.77 (22.87%) | 168.17 | 4 | 1.0000 | — | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · ADA/USDT | long | 17 (11/6) | -0.346 | [-0.864, 0.318] | -0.020 | -0.945 | 0.50 | 18% | 275.56 (16.21%) | -222.79 | 8 | 1.0000 | — | INCONCLUSIVE (n_total=17 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · BTC/USDT | short | 27 (18/9) | 0.104 | [-0.576, 1.072] | -0.221 | 0.754 | 1.15 | 30% | 214.41 (12.61%) | 56.58 | 1 | 0.2869 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · ETH/USDT | short | 26 (18/8) | 0.005 | [-0.767, 0.869] | -0.349 | 0.802 | 1.01 | 23% | 259.03 (15.24%) | -57.76 | 4 | 0.2400 | — | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · SOL/USDT | short | 32 (17/15) | 0.113 | [-0.446, 0.724] | 0.073 | 0.160 | 1.19 | 31% | 167.6 (9.86%) | 91.34 | 8 | 0.4025 | — | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:adx_turn:spec:iso10 · XRP/USDT | short | 18 (12/6) | -0.014 | [-0.957, 1.026] | -0.131 | 0.221 | 0.98 | 28% | 360.69 (21.22%) | -54.57 | 4 | 0.4276 | — | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · DOGE/USDT | short | 31 (18/13) | -0.119 | [-0.596, 0.435] | 0.042 | -0.341 | 0.83 | 32% | 328.22 (19.31%) | -216.4 | 9 | 0.7876 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:adx_turn:spec:iso10 · NEAR/USDT | short | 20 (11/9) | -0.132 | [-0.663, 0.509] | -0.170 | -0.086 | 0.77 | 35% | 226.71 (13.34%) | -206.59 | 13 | 0.5867 | — | INCONCLUSIVE (n_total=20 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · BNB/USDT | short | 22 (13/9) | -0.334 | [-0.873, 0.260] | -0.047 | -0.748 | 0.57 | 32% | 351.7 (20.69%) | -297.28 | 3 | 0.9774 | — | INCONCLUSIVE (n_total=22 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · LINK/USDT | short | 21 (11/10) | 0.217 | [-0.744, 1.455] | -0.320 | 0.807 | 1.29 | 38% | 244.12 (14.36%) | 153.99 | 4 | 0.2417 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:spec:iso10 · ADA/USDT | short | 31 (19/12) | 0.427 | [-0.103, 1.180] | 0.370 | 0.517 | 2.21 | 55% | 131.48 (7.73%) | 442.6 | 8 | 0.3193 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:adx_turn:asrun:cross5 · BTC/USDT | long | 25 (14/11) | 0.201 | [-0.745, 1.300] | -0.389 | 0.953 | 1.24 | 28% | 427.72 (25.16%) | 166.42 | 0 | 0.1881 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · ETH/USDT | long | 24 (12/12) | 0.319 | [-0.954, 1.698] | 0.546 | 0.091 | 1.35 | 17% | 332.69 (19.57%) | 155.18 | 0 | 0.4789 | — | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · SOL/USDT | long | 22 (15/7) | -0.330 | [-0.993, 0.547] | -0.208 | -0.589 | 0.64 | 23% | 447.37 (26.32%) | -290.28 | 0 | 0.8778 | — | INCONCLUSIVE (n_total=22 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · XRP/USDT | long | 21 (14/7) | 2.095 | [-0.161, 5.173] | 1.723 | 2.840 | 4.70 | 38% | 369.78 (21.75%) | 1817.43 | 0 | 0.3136 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · DOGE/USDT | long | 18 (7/11) | 1.405 | [-0.650, 4.432] | 2.243 | 0.871 | 2.90 | 22% | 257.45 (15.14%) | 890.11 | 0 | 0.3319 | — | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · NEAR/USDT | long | 24 (15/9) | 3.265 | [-0.944, 11.053] | 0.166 | 8.431 | 4.52 | 25% | 641.69 (37.75%) | 2417.53 | 0 | 0.1239 | — | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · BNB/USDT | long | 18 (10/8) | 0.985 | [-0.568, 3.708] | 1.750 | 0.028 | 2.72 | 33% | 153.28 (9.02%) | 544.81 | 0 | 0.5001 | — | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · LINK/USDT | long | 16 (9/7) | 0.110 | [-1.171, 2.244] | 0.734 | -0.691 | 1.12 | 19% | 344.69 (20.28%) | 28.8 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=16 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · ADA/USDT | long | 19 (13/6) | -0.433 | [-0.887, 0.202] | -0.221 | -0.892 | 0.43 | 16% | 313.24 (18.43%) | -313.24 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=19 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · BTC/USDT | short | 28 (19/9) | 0.507 | [-0.613, 2.107] | -0.198 | 1.996 | 1.62 | 32% | 234.7 (13.81%) | 393.43 | 0 | 0.1266 | — | INCONCLUSIVE (n_total=28 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · ETH/USDT | short | 27 (19/8) | -0.029 | [-0.943, 1.058] | -0.564 | 1.241 | 0.97 | 22% | 397.0 (23.35%) | -98.93 | 0 | 0.1337 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · SOL/USDT | short | 31 (17/14) | 0.420 | [-0.568, 1.636] | 0.015 | 0.911 | 1.56 | 26% | 200.67 (11.8%) | 355.39 | 0 | 0.1884 | — | GO | **NO-GO** (not in a corrected family) |
| snipper:adx_turn:asrun:cross5 · XRP/USDT | short | 19 (13/6) | 0.097 | [-0.803, 1.095] | -0.153 | 0.638 | 1.12 | 37% | 412.48 (24.26%) | 106.19 | 0 | 0.2708 | — | INCONCLUSIVE (n_total=19 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · DOGE/USDT | short | 29 (17/12) | -0.002 | [-0.543, 0.619] | 0.051 | -0.077 | 1.00 | 38% | 260.8 (15.34%) | -68.32 | 0 | 0.5866 | — | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · NEAR/USDT | short | 21 (13/8) | -0.225 | [-0.783, 0.354] | -0.441 | 0.125 | 0.71 | 38% | 265.7 (15.63%) | -247.07 | 0 | 0.3060 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · BNB/USDT | short | 24 (15/9) | -0.330 | [-0.843, 0.265] | -0.091 | -0.728 | 0.59 | 33% | 379.19 (22.31%) | -325.66 | 0 | 0.9696 | — | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · LINK/USDT | short | 26 (16/10) | -0.127 | [-1.022, 1.000] | -0.677 | 0.753 | 0.88 | 35% | 441.08 (25.95%) | -192.9 | 0 | 0.2590 | — | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:cross5 · ADA/USDT | short | 32 (19/13) | 0.673 | [-0.093, 1.786] | 0.560 | 0.838 | 2.76 | 56% | 160.75 (9.46%) | 727.74 | 0 | 0.3203 | — | GO | **NO-GO** (not in a corrected family) |
| snipper:adx_turn:asrun:iso10 · BTC/USDT | long | 25 (14/11) | 0.198 | [-0.748, 1.297] | -0.395 | 0.953 | 1.23 | 28% | 429.95 (25.29%) | 163.41 | 1 | 0.1881 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · ETH/USDT | long | 24 (12/12) | 0.311 | [-0.958, 1.685] | 0.531 | 0.091 | 1.34 | 17% | 331.7 (19.51%) | 151.36 | 4 | 0.4789 | — | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · SOL/USDT | long | 22 (15/7) | -0.347 | [-1.016, 0.534] | -0.234 | -0.589 | 0.62 | 23% | 465.72 (27.4%) | -310.26 | 10 | 0.8778 | — | INCONCLUSIVE (n_total=22 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · XRP/USDT | long | 21 (14/7) | 2.104 | [-0.149, 5.181] | 1.736 | 2.840 | 4.78 | 38% | 380.59 (22.39%) | 1864.23 | 4 | 0.3136 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · DOGE/USDT | long | 18 (7/11) | 1.402 | [-0.655, 4.418] | 2.258 | 0.857 | 2.89 | 22% | 257.05 (15.12%) | 889.14 | 11 | 0.3322 | — | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · NEAR/USDT | long | 25 (16/9) | 3.208 | [-0.804, 10.868] | 0.259 | 8.453 | 4.93 | 24% | 598.8 (35.22%) | 2609.06 | 15 | 0.1196 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · BNB/USDT | long | 18 (10/8) | 0.690 | [-0.898, 3.459] | 1.246 | -0.006 | 1.90 | 28% | 245.16 (14.42%) | 333.73 | 3 | 0.5544 | — | INCONCLUSIVE (n_total=18 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · LINK/USDT | long | 17 (10/7) | 0.164 | [-1.168, 2.148] | 0.763 | -0.691 | 1.18 | 18% | 348.38 (20.49%) | 62.26 | 7 | 1.0000 | — | INCONCLUSIVE (n_total=17 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · ADA/USDT | long | 19 (13/6) | -0.456 | [-0.923, 0.183] | -0.255 | -0.891 | 0.41 | 16% | 323.55 (19.03%) | -323.55 | 8 | 1.0000 | — | INCONCLUSIVE (n_total=19 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · BTC/USDT | short | 28 (19/9) | 0.507 | [-0.613, 2.107] | -0.198 | 1.996 | 1.62 | 32% | 234.34 (13.78%) | 392.97 | 1 | 0.1266 | — | INCONCLUSIVE (n_total=28 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · ETH/USDT | short | 27 (19/8) | -0.027 | [-0.961, 1.071] | -0.561 | 1.241 | 0.97 | 22% | 397.51 (23.38%) | -100.32 | 4 | 0.1337 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · SOL/USDT | short | 31 (17/14) | 0.461 | [-0.504, 1.659] | 0.091 | 0.910 | 1.65 | 26% | 204.54 (12.03%) | 409.37 | 10 | 0.1885 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:adx_turn:asrun:iso10 · XRP/USDT | short | 19 (13/6) | 0.160 | [-0.704, 1.142] | -0.061 | 0.638 | 1.23 | 37% | 362.78 (21.34%) | 165.36 | 4 | 0.2708 | — | INCONCLUSIVE (n_total=19 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · DOGE/USDT | short | 30 (18/12) | -0.004 | [-0.549, 0.596] | 0.045 | -0.077 | 0.99 | 37% | 260.35 (15.31%) | -78.3 | 11 | 0.5866 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:adx_turn:asrun:iso10 · NEAR/USDT | short | 22 (13/9) | -0.237 | [-0.758, 0.329] | -0.393 | -0.012 | 0.69 | 36% | 319.54 (18.8%) | -319.54 | 15 | 0.4935 | — | INCONCLUSIVE (n_total=22 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · BNB/USDT | short | 24 (15/9) | -0.329 | [-0.839, 0.265] | -0.089 | -0.728 | 0.60 | 33% | 342.62 (20.15%) | -309.1 | 3 | 0.9696 | — | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · LINK/USDT | short | 27 (17/10) | -0.146 | [-1.002, 0.939] | -0.686 | 0.772 | 0.86 | 33% | 439.63 (25.86%) | -218.87 | 7 | 0.2524 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:adx_turn:asrun:iso10 · ADA/USDT | short | 32 (19/13) | 0.654 | [-0.108, 1.770] | 0.544 | 0.815 | 2.63 | 56% | 157.32 (9.25%) | 694.38 | 8 | 0.3253 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:bbwp_fresh_blue:spec:cross5 · BTC/USDT | long | 25 (14/11) | -0.087 | [-0.686, 0.556] | -0.295 | 0.177 | 0.88 | 24% | 391.19 (23.01%) | -96.03 | 0 | 0.3821 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:cross5 · BTC/USDT | short | 21 (12/9) | -0.179 | [-1.176, 1.082] | -0.645 | 0.443 | 0.83 | 29% | 264.36 (15.55%) | -161.41 | 0 | 0.3394 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · BTC/USDT | long | 25 (14/11) | -0.090 | [-0.689, 0.551] | -0.301 | 0.177 | 0.88 | 24% | 390.46 (22.97%) | -98.43 | 2 | 0.3821 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · ETH/USDT | long | 27 (17/10) | -0.170 | [-0.930, 0.914] | 0.330 | -1.020 | 0.81 | 15% | 491.79 (28.93%) | -145.57 | 6 | 1.0000 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · SOL/USDT | long | 21 (12/9) | 0.433 | [-0.563, 1.713] | 0.647 | 0.148 | 1.65 | 29% | 219.17 (12.89%) | 296.06 | 10 | 0.4682 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · XRP/USDT | long | 26 (16/10) | 4.514 | [-0.162, 12.669] | 5.968 | 2.187 | 8.49 | 35% | 751.73 (44.22%) | 5741.22 | 6 | 0.2325 | — | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · DOGE/USDT | long | 19 (9/10) | 1.277 | [-0.457, 3.684] | 1.650 | 0.940 | 3.17 | 37% | 165.93 (9.76%) | 862.89 | 8 | 0.2307 | — | INCONCLUSIVE (n_total=19 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · NEAR/USDT | long | 25 (15/10) | 0.940 | [-0.481, 2.982] | 0.345 | 1.831 | 2.36 | 28% | 419.83 (24.7%) | 758.18 | 19 | 0.0877 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · BNB/USDT | long | 17 (10/7) | 0.817 | [-0.951, 3.772] | 1.161 | 0.327 | 2.02 | 24% | 289.91 (17.05%) | 392.21 | 4 | 0.3360 | — | INCONCLUSIVE (n_total=17 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · LINK/USDT | long | 27 (19/8) | 0.065 | [-0.762, 1.251] | 0.093 | -0.001 | 1.09 | 19% | 293.46 (17.26%) | -2.91 | 10 | 0.5523 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · ADA/USDT | long | 19 (11/8) | -0.117 | [-0.846, 1.154] | 0.495 | -0.960 | 0.84 | 16% | 364.59 (21.45%) | -108.85 | 6 | 1.0000 | — | INCONCLUSIVE (n_total=19 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · BTC/USDT | short | 21 (12/9) | -0.181 | [-1.178, 1.080] | -0.645 | 0.439 | 0.82 | 29% | 264.05 (15.53%) | -162.45 | 2 | 0.3424 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · ETH/USDT | short | 26 (16/10) | -0.266 | [-0.874, 0.591] | -0.733 | 0.482 | 0.65 | 19% | 396.54 (23.33%) | -266.04 | 6 | 0.3390 | — | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · SOL/USDT | short | 30 (17/13) | 0.042 | [-0.543, 0.783] | -0.014 | 0.115 | 1.07 | 33% | 408.62 (24.04%) | 1.13 | 10 | 0.4327 | — | NO-GO (PF >= 1.2; liquidations == 0) | **NO-GO** (PF >= 1.2; liquidations == 0) |
| snipper:bbwp_fresh_blue:spec:iso10 · XRP/USDT | short | 22 (15/7) | -0.243 | [-0.899, 0.536] | 0.008 | -0.780 | 0.70 | 32% | 1195.45 (70.32%) | -646.37 | 6 | 1.0000 | — | INCONCLUSIVE (n_total=22 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · DOGE/USDT | short | 30 (18/12) | 0.052 | [-0.405, 0.601] | 0.096 | -0.014 | 1.09 | 37% | 336.38 (19.79%) | 62.65 | 8 | 0.5342 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:bbwp_fresh_blue:spec:iso10 · NEAR/USDT | short | 26 (17/9) | -0.250 | [-0.733, 0.345] | -0.155 | -0.430 | 0.60 | 27% | 295.0 (17.35%) | -270.85 | 19 | 0.8003 | — | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · BNB/USDT | short | 27 (15/12) | -0.296 | [-0.791, 0.333] | 0.079 | -0.765 | 0.57 | 26% | 441.64 (25.98%) | -328.31 | 4 | 1.0000 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · LINK/USDT | short | 23 (13/10) | -0.410 | [-0.886, 0.245] | -0.624 | -0.131 | 0.45 | 17% | 415.13 (24.42%) | -298.88 | 10 | 0.5885 | — | INCONCLUSIVE (n_total=23 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:spec:iso10 · ADA/USDT | short | 32 (18/14) | 0.148 | [-0.187, 0.633] | 0.252 | 0.014 | 1.41 | 44% | 157.32 (9.25%) | 152.15 | 6 | 0.4979 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |
| snipper:bbwp_fresh_blue:asrun:cross5 · BTC/USDT | long | 29 (18/11) | -0.108 | [-0.802, 0.565] | -0.123 | -0.083 | 0.88 | 28% | 414.94 (24.41%) | -154.53 | 0 | 0.5656 | — | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · ETH/USDT | long | 27 (15/12) | -0.284 | [-1.144, 0.891] | 0.475 | -1.232 | 0.73 | 19% | 522.38 (30.73%) | -174.95 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · SOL/USDT | long | 25 (16/9) | 0.518 | [-0.303, 1.657] | 0.560 | 0.444 | 1.72 | 44% | 344.61 (20.27%) | 502.63 | 0 | 0.3263 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · XRP/USDT | long | 28 (16/12) | 3.218 | [-0.540, 10.595] | 6.046 | -0.552 | 5.42 | 29% | 1328.95 (78.17%) | 2941.47 | 0 | 0.8891 | — | INCONCLUSIVE (n_total=28 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · DOGE/USDT | long | 20 (11/9) | 1.007 | [-0.635, 3.204] | 1.026 | 0.983 | 2.35 | 30% | 308.02 (18.12%) | 698.35 | 0 | 0.2333 | — | INCONCLUSIVE (n_total=20 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · NEAR/USDT | long | 24 (15/9) | 3.587 | [-0.461, 11.031] | 0.570 | 8.616 | 5.26 | 33% | 378.62 (22.27%) | 3502.2 | 0 | 0.0715 | — | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · BNB/USDT | long | 25 (14/11) | 0.669 | [-0.733, 2.756] | 1.191 | 0.004 | 1.82 | 24% | 313.58 (18.45%) | 430.94 | 0 | 0.5224 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · LINK/USDT | long | 28 (17/11) | 0.023 | [-0.922, 1.227] | 0.091 | -0.082 | 1.03 | 32% | 374.03 (22.0%) | 4.26 | 0 | 0.5844 | — | INCONCLUSIVE (n_total=28 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · ADA/USDT | long | 27 (17/10) | -0.247 | [-1.022, 0.853] | 0.262 | -1.114 | 0.74 | 15% | 610.59 (35.92%) | -293.08 | 0 | 1.0000 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · BTC/USDT | short | 22 (11/11) | -0.138 | [-1.017, 1.013] | -0.382 | 0.106 | 0.86 | 32% | 237.97 (14.0%) | -106.3 | 0 | 0.4693 | — | INCONCLUSIVE (n_total=22 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · ETH/USDT | short | 30 (19/11) | -0.530 | [-1.093, 0.301] | -1.016 | 0.310 | 0.45 | 17% | 603.94 (35.53%) | -523.52 | 0 | 0.3701 | — | NO-GO (PF >= 1.2; maxDD < 35% of start) | **NO-GO** (PF >= 1.2; maxDD < 35% of start) |
| snipper:bbwp_fresh_blue:asrun:cross5 · SOL/USDT | short | 27 (15/12) | 0.838 | [-0.324, 2.350] | 0.435 | 1.341 | 2.21 | 48% | 306.04 (18.0%) | 951.24 | 0 | 0.1237 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · XRP/USDT | short | 26 (17/9) | 0.201 | [-0.541, 1.101] | 0.021 | 0.542 | 1.28 | 42% | 593.6 (34.92%) | 586.43 | 0 | 0.3051 | — | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · DOGE/USDT | short | 34 (20/14) | 0.242 | [-0.299, 0.911] | 0.478 | -0.094 | 1.46 | 41% | 283.78 (16.69%) | 348.22 | 0 | 0.5969 | — | NO-GO (expectancy_oos > 0) | **NO-GO** (expectancy_oos > 0) |
| snipper:bbwp_fresh_blue:asrun:cross5 · NEAR/USDT | short | 29 (18/11) | -0.030 | [-0.679, 0.795] | 0.108 | -0.255 | 0.95 | 41% | 348.91 (20.52%) | -138.83 | 0 | 0.6844 | — | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · BNB/USDT | short | 30 (18/12) | -0.307 | [-0.782, 0.345] | -0.076 | -0.654 | 0.57 | 23% | 364.82 (21.46%) | -340.47 | 0 | 0.9681 | — | NO-GO (expectancy_oos > 0; PF >= 1.2) | **NO-GO** (expectancy_oos > 0; PF >= 1.2) |
| snipper:bbwp_fresh_blue:asrun:cross5 · LINK/USDT | short | 28 (17/11) | -0.521 | [-1.262, 0.634] | -1.068 | 0.323 | 0.53 | 18% | 566.57 (33.33%) | -511.45 | 0 | 0.4194 | — | INCONCLUSIVE (n_total=28 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:cross5 · ADA/USDT | short | 32 (18/14) | 0.141 | [-0.259, 0.653] | 0.233 | 0.024 | 1.36 | 44% | 161.82 (9.52%) | 158.74 | 0 | 0.4871 | — | GO | **NO-GO** (not in a corrected family) |
| snipper:bbwp_fresh_blue:asrun:iso10 · BTC/USDT | long | 29 (18/11) | -0.108 | [-0.802, 0.565] | -0.123 | -0.083 | 0.88 | 28% | 414.75 (24.4%) | -154.49 | 1 | 0.5656 | — | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · ETH/USDT | long | 27 (15/12) | -0.289 | [-1.149, 0.887] | 0.466 | -1.232 | 0.73 | 19% | 524.57 (30.86%) | -179.89 | 5 | 1.0000 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · SOL/USDT | long | 25 (16/9) | 0.538 | [-0.280, 1.667] | 0.591 | 0.444 | 1.77 | 44% | 366.42 (21.55%) | 540.41 | 9 | 0.3263 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · XRP/USDT | long | 28 (16/12) | 3.173 | [-0.595, 10.585] | 5.967 | -0.552 | 5.11 | 29% | 1337.33 (78.67%) | 2814.72 | 5 | 0.8891 | — | INCONCLUSIVE (n_total=28 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · DOGE/USDT | long | 21 (11/10) | 0.915 | [-0.654, 3.051] | 1.024 | 0.795 | 2.21 | 29% | 350.61 (20.62%) | 661.55 | 8 | 0.2710 | — | INCONCLUSIVE (n_total=21 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · NEAR/USDT | long | 24 (15/9) | 3.677 | [-0.339, 11.096] | 0.710 | 8.624 | 5.89 | 33% | 350.6 (20.62%) | 3814.19 | 16 | 0.0716 | — | INCONCLUSIVE (n_total=24 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · BNB/USDT | long | 25 (14/11) | 0.459 | [-0.971, 2.596] | 0.835 | -0.020 | 1.48 | 20% | 406.62 (23.92%) | 229.86 | 5 | 0.5502 | — | INCONCLUSIVE (n_total=25 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · LINK/USDT | long | 30 (18/12) | -0.075 | [-0.993, 1.067] | 0.079 | -0.307 | 0.91 | 30% | 424.01 (24.94%) | -71.78 | 10 | 0.7001 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:bbwp_fresh_blue:asrun:iso10 · ADA/USDT | long | 28 (17/11) | -0.309 | [-1.062, 0.768] | 0.240 | -1.156 | 0.69 | 14% | 660.16 (38.83%) | -352.05 | 7 | 1.0000 | — | INCONCLUSIVE (n_total=28 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · BTC/USDT | short | 22 (11/11) | -0.140 | [-1.019, 1.011] | -0.382 | 0.102 | 0.85 | 32% | 237.97 (14.0%) | -107.58 | 1 | 0.4705 | — | INCONCLUSIVE (n_total=22 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · ETH/USDT | short | 30 (19/11) | -0.525 | [-1.089, 0.305] | -1.007 | 0.307 | 0.45 | 17% | 598.12 (35.18%) | -518.58 | 5 | 0.3711 | — | NO-GO (PF >= 1.2; liquidations == 0; maxDD < 35% of start) | **NO-GO** (PF >= 1.2; liquidations == 0; maxDD < 35% of start) |
| snipper:bbwp_fresh_blue:asrun:iso10 · SOL/USDT | short | 27 (15/12) | 0.894 | [-0.247, 2.385] | 0.530 | 1.350 | 2.41 | 48% | 313.2 (18.42%) | 1049.82 | 9 | 0.1221 | — | INCONCLUSIVE (n_total=27 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · XRP/USDT | short | 26 (17/9) | 0.259 | [-0.464, 1.157] | 0.110 | 0.542 | 1.40 | 42% | 539.7 (31.75%) | 743.65 | 5 | 0.3051 | — | INCONCLUSIVE (n_total=26 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · DOGE/USDT | short | 33 (20/13) | 0.286 | [-0.268, 0.947] | 0.495 | -0.035 | 1.56 | 42% | 247.28 (14.55%) | 400.53 | 8 | 0.5467 | — | NO-GO (expectancy_oos > 0; liquidations == 0) | **NO-GO** (expectancy_oos > 0; liquidations == 0) |
| snipper:bbwp_fresh_blue:asrun:iso10 · NEAR/USDT | short | 29 (18/11) | 0.001 | [-0.621, 0.818] | 0.082 | -0.133 | 1.00 | 41% | 315.3 (18.55%) | -118.53 | 16 | 0.6237 | — | INCONCLUSIVE (n_total=29 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · BNB/USDT | short | 30 (18/12) | -0.312 | [-0.793, 0.344] | -0.084 | -0.654 | 0.57 | 23% | 343.33 (20.2%) | -325.51 | 5 | 0.9681 | — | NO-GO (expectancy_oos > 0; PF >= 1.2; liquidations == 0) | **NO-GO** (expectancy_oos > 0; PF >= 1.2; liquidations == 0) |
| snipper:bbwp_fresh_blue:asrun:iso10 · LINK/USDT | short | 28 (17/11) | -0.493 | [-1.224, 0.659] | -1.044 | 0.358 | 0.54 | 18% | 551.38 (32.43%) | -487.32 | 10 | 0.4038 | — | INCONCLUSIVE (n_total=28 < 30) | **INCONCLUSIVE** |
| snipper:bbwp_fresh_blue:asrun:iso10 · ADA/USDT | short | 32 (18/14) | 0.132 | [-0.268, 0.651] | 0.233 | 0.002 | 1.33 | 44% | 170.15 (10.01%) | 146.47 | 7 | 0.5130 | — | NO-GO (liquidations == 0) | **NO-GO** (liquidations == 0) |

## D. Which assets add / subtract (primary pooled cells; `adds` = removing the asset lowers the pooled expectancy)

| cell | side | asset | n (OOS) | sum R | exp. R | exp. OOS | net USDT | pooled exp. without it | pooled exp. OOS without it | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| pro:base:spec:pro5 | long | ADA/USDT | 9 (4) | 0.642 | 0.071 | -0.771 | 6.28 | 0.906 | 0.902 | subtracts |
| pro:base:spec:pro5 | long | BNB/USDT | 6 (4) | 2.567 | 0.428 | -0.684 | 58.32 | 0.793 | 0.882 | subtracts |
| pro:base:spec:pro5 | long | DOGE/USDT | 3 (2) | -1.044 | -0.348 | -1.345 | -28.12 | 0.821 | 0.787 | subtracts |
| pro:base:spec:pro5 | long | ETH/USDT | 6 (2) | -0.958 | -0.160 | -0.037 | -26.35 | 0.879 | 0.649 | subtracts |
| pro:base:spec:pro5 | long | LINK/USDT | 6 (2) | 3.999 | 0.666 | 2.608 | 94.41 | 0.758 | 0.371 | subtracts |
| pro:base:spec:pro5 | long | NEAR/USDT | 4 (2) | 19.41 | 4.852 | 10.343 | 516.11 | 0.364 | -0.444 | adds |
| pro:base:spec:pro5 | long | SOL/USDT | 3 (1) | -2.873 | -0.958 | -0.189 | -69.46 | 0.863 | 0.622 | subtracts |
| pro:base:spec:pro5 | long | XRP/USDT | 10 (4) | 13.333 | 1.333 | -1.218 | 303.3 | 0.588 | 1.008 | adds |
| pro:base:spec:pro5 | short | ADA/USDT | 5 (2) | 3.626 | 0.725 | 1.956 | 90.07 | -0.523 | -0.646 | adds |
| pro:base:spec:pro5 | short | BNB/USDT | 5 (2) | -3.581 | -0.716 | -0.365 | -94.62 | -0.342 | -0.373 | subtracts |
| pro:base:spec:pro5 | short | DOGE/USDT | 6 (3) | -2.345 | -0.391 | -0.673 | -60.84 | -0.383 | -0.315 | subtracts |
| pro:base:spec:pro5 | short | ETH/USDT | 5 (3) | 0.31 | 0.062 | -0.450 | 7.59 | -0.440 | -0.357 | adds |
| pro:base:spec:pro5 | short | LINK/USDT | 6 (3) | -2.126 | -0.354 | -0.776 | -54.58 | -0.389 | -0.296 | adds |
| pro:base:spec:pro5 | short | NEAR/USDT | 4 (0) | 0.167 | 0.042 | — | 0.37 | -0.425 | -0.372 | adds |
| pro:base:spec:pro5 | short | SOL/USDT | 8 (4) | -7.876 | -0.985 | -0.949 | -185.98 | -0.254 | -0.218 | subtracts |
| pro:base:spec:pro5 | short | XRP/USDT | 6 (2) | -5.451 | -0.908 | -0.377 | -186.63 | -0.303 | -0.371 | subtracts |
| pro:adx_turn:spec:pro5 | long | ADA/USDT | 7 (4) | -6.195 | -0.885 | -1.082 | -162.49 | 0.973 | 0.790 | subtracts |
| pro:adx_turn:spec:pro5 | long | BNB/USDT | 5 (2) | 1.786 | 0.357 | -0.923 | 42.01 | 0.681 | 0.577 | subtracts |
| pro:adx_turn:spec:pro5 | long | DOGE/USDT | 4 (3) | -2.235 | -0.559 | -1.182 | -53.58 | 0.777 | 0.703 | subtracts |
| pro:adx_turn:spec:pro5 | long | ETH/USDT | 5 (2) | -0.673 | -0.135 | -0.250 | -18.78 | 0.754 | 0.506 | subtracts |
| pro:adx_turn:spec:pro5 | long | LINK/USDT | 5 (2) | 2.698 | 0.539 | 2.608 | 59.52 | 0.654 | 0.205 | subtracts |
| pro:adx_turn:spec:pro5 | long | NEAR/USDT | 2 (2) | 18.967 | 9.484 | 9.484 | 516.02 | 0.162 | -0.519 | adds |
| pro:adx_turn:spec:pro5 | long | SOL/USDT | 3 (2) | -0.557 | -0.186 | 0.187 | -15.67 | 0.709 | 0.460 | subtracts |
| pro:adx_turn:spec:pro5 | long | XRP/USDT | 8 (4) | 11.162 | 1.395 | -1.307 | 258.7 | 0.445 | 0.843 | adds |
| pro:adx_turn:spec:pro5 | short | ADA/USDT | 3 (0) | 5.18 | 1.727 | — | 120.68 | -0.687 | -0.998 | adds |
| pro:adx_turn:spec:pro5 | short | BNB/USDT | 5 (2) | -6.561 | -1.312 | -1.303 | -167.93 | -0.373 | -0.937 | subtracts |
| pro:adx_turn:spec:pro5 | short | DOGE/USDT | 4 (2) | -3.778 | -0.945 | -0.870 | -98.3 | -0.444 | -1.023 | subtracts |
| pro:adx_turn:spec:pro5 | short | ETH/USDT | 5 (3) | -0.529 | -0.106 | -0.441 | -14.23 | -0.556 | -1.183 | adds |
| pro:adx_turn:spec:pro5 | short | LINK/USDT | 6 (3) | -2.265 | -0.378 | -0.776 | -57.06 | -0.519 | -1.071 | adds |
| pro:adx_turn:spec:pro5 | short | NEAR/USDT | 4 (0) | 1.437 | 0.359 | — | 36.84 | -0.598 | -0.998 | adds |
| pro:adx_turn:spec:pro5 | short | SOL/USDT | 5 (1) | -4.305 | -0.861 | -0.746 | -106.97 | -0.442 | -1.020 | subtracts |
| pro:adx_turn:spec:pro5 | short | XRP/USDT | 6 (1) | -8.057 | -1.343 | -3.228 | -255.21 | -0.338 | -0.795 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | long | ADA/USDT | 7 (4) | -7.095 | -1.014 | -0.593 | -178.25 | 1.490 | 1.760 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | long | BNB/USDT | 4 (2) | -2.37 | -0.592 | -0.923 | -55.54 | 1.137 | 1.423 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | long | DOGE/USDT | 2 (1) | -0.457 | -0.228 | -1.769 | -12.62 | 0.987 | 1.307 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | long | ETH/USDT | 5 (2) | -2.56 | -0.512 | -0.250 | -67.93 | 1.190 | 1.311 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | long | LINK/USDT | 2 (2) | 5.217 | 2.608 | 2.608 | 130.77 | 0.784 | 0.834 | adds |
| pro:bbwp_fresh_blue:spec:pro5 | long | NEAR/USDT | 2 (1) | 17.607 | 8.804 | 18.045 | 483.75 | 0.342 | -0.217 | adds |
| pro:bbwp_fresh_blue:spec:pro5 | long | SOL/USDT | 3 (1) | -2.231 | -0.744 | -0.843 | -52.76 | 1.089 | 1.236 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | long | XRP/USDT | 5 (1) | 19.068 | 3.814 | -0.705 | 482.91 | 0.324 | 1.226 | adds |
| pro:bbwp_fresh_blue:spec:pro5 | short | ADA/USDT | 4 (1) | 9.172 | 2.293 | 4.357 | 208.52 | -0.419 | -0.566 | adds |
| pro:bbwp_fresh_blue:spec:pro5 | short | BNB/USDT | 6 (2) | -5.657 | -0.943 | -0.365 | -139.51 | -0.041 | -0.284 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | short | DOGE/USDT | 6 (3) | -3.374 | -0.562 | -1.016 | -86.43 | -0.102 | -0.148 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | short | ETH/USDT | 4 (2) | -0.179 | -0.045 | -0.953 | -3.49 | -0.179 | -0.210 | adds |
| pro:bbwp_fresh_blue:spec:pro5 | short | LINK/USDT | 6 (2) | -1.664 | -0.277 | -1.010 | -44.36 | -0.149 | -0.203 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | short | NEAR/USDT | 5 (1) | 3.268 | 0.653 | 0.242 | 85.41 | -0.274 | -0.324 | adds |
| pro:bbwp_fresh_blue:spec:pro5 | short | SOL/USDT | 7 (4) | -7.563 | -1.080 | -0.669 | -182.55 | 0.011 | -0.185 | subtracts |
| pro:bbwp_fresh_blue:spec:pro5 | short | XRP/USDT | 5 (3) | -1.165 | -0.233 | 0.171 | -45.65 | -0.158 | -0.386 | subtracts |
| snipper:base:spec:cross5 | long | ADA/USDT | 25 (10) | -9.514 | -0.381 | -0.696 | -348.47 | 0.682 | 0.684 | subtracts |
| snipper:base:spec:cross5 | long | BNB/USDT | 29 (12) | 13.365 | 0.461 | 0.148 | 299.46 | 0.581 | 0.598 | subtracts |
| snipper:base:spec:cross5 | long | DOGE/USDT | 29 (13) | 10.698 | 0.369 | -0.172 | 269.99 | 0.594 | 0.653 | subtracts |
| snipper:base:spec:cross5 | long | ETH/USDT | 26 (12) | 17.706 | 0.681 | 0.026 | 477.11 | 0.551 | 0.615 | adds |
| snipper:base:spec:cross5 | long | LINK/USDT | 33 (15) | -10.547 | -0.320 | -0.537 | -289.11 | 0.715 | 0.739 | subtracts |
| snipper:base:spec:cross5 | long | NEAR/USDT | 31 (12) | 61.373 | 1.980 | 6.121 | 1242.48 | 0.344 | -0.246 | adds |
| snipper:base:spec:cross5 | long | SOL/USDT | 27 (10) | 2.357 | 0.087 | -0.019 | 32.69 | 0.630 | 0.607 | subtracts |
| snipper:base:spec:cross5 | long | XRP/USDT | 29 (13) | 44.145 | 1.522 | -0.426 | 1176.82 | 0.427 | 0.692 | adds |
| snipper:base:spec:cross5 | short | ADA/USDT | 40 (15) | 13.401 | 0.335 | 0.458 | 442.93 | -0.143 | 0.068 | adds |
| snipper:base:spec:cross5 | short | BNB/USDT | 36 (14) | -11.415 | -0.317 | -0.433 | -375.87 | -0.042 | 0.205 | subtracts |
| snipper:base:spec:cross5 | short | DOGE/USDT | 44 (20) | -5.809 | -0.132 | -0.239 | -240.69 | -0.066 | 0.204 | subtracts |
| snipper:base:spec:cross5 | short | ETH/USDT | 33 (12) | -6.973 | -0.211 | 0.305 | -286.15 | -0.059 | 0.099 | subtracts |
| snipper:base:spec:cross5 | short | LINK/USDT | 30 (10) | -3.666 | -0.122 | 0.534 | -178.25 | -0.071 | 0.080 | subtracts |
| snipper:base:spec:cross5 | short | NEAR/USDT | 32 (11) | -9.276 | -0.290 | -0.342 | -284.83 | -0.050 | 0.174 | subtracts |
| snipper:base:spec:cross5 | short | SOL/USDT | 43 (18) | -0.526 | -0.012 | 0.282 | -61.68 | -0.088 | 0.090 | adds |
| snipper:base:spec:cross5 | short | XRP/USDT | 30 (8) | 2.252 | 0.075 | 0.854 | 150.12 | -0.094 | 0.063 | adds |
| snipper:adx_turn:spec:cross5 | long | ADA/USDT | 16 (6) | -4.774 | -0.298 | -0.946 | -188.09 | 1.155 | 1.619 | subtracts |
| snipper:adx_turn:spec:cross5 | long | BNB/USDT | 18 (8) | 17.804 | 0.989 | 0.029 | 563.76 | 1.014 | 1.574 | subtracts |
| snipper:adx_turn:spec:cross5 | long | DOGE/USDT | 18 (11) | 26.327 | 1.463 | 0.945 | 916.74 | 0.955 | 1.477 | adds |
| snipper:adx_turn:spec:cross5 | long | ETH/USDT | 25 (12) | 4.787 | 0.192 | -0.054 | 62.85 | 1.161 | 1.704 | subtracts |
| snipper:adx_turn:spec:cross5 | long | LINK/USDT | 18 (7) | 7.164 | 0.398 | -0.621 | 163.16 | 1.088 | 1.624 | subtracts |
| snipper:adx_turn:spec:cross5 | long | NEAR/USDT | 25 (9) | 77.541 | 3.102 | 8.589 | 2521.46 | 0.630 | 0.272 | adds |
| snipper:adx_turn:spec:cross5 | long | SOL/USDT | 21 (7) | -8.878 | -0.423 | -0.611 | -308.19 | 1.225 | 1.623 | subtracts |
| snipper:adx_turn:spec:cross5 | long | XRP/USDT | 21 (7) | 43.894 | 2.090 | 2.872 | 1799.86 | 0.851 | 1.216 | adds |
| snipper:adx_turn:spec:cross5 | short | ADA/USDT | 31 (12) | 13.727 | 0.443 | 0.542 | 471.55 | -0.033 | 0.102 | adds |
| snipper:adx_turn:spec:cross5 | short | BNB/USDT | 22 (9) | -7.389 | -0.336 | -0.748 | -315.82 | 0.089 | 0.281 | subtracts |
| snipper:adx_turn:spec:cross5 | short | DOGE/USDT | 30 (13) | -2.855 | -0.095 | -0.341 | -179.11 | 0.066 | 0.264 | subtracts |
| snipper:adx_turn:spec:cross5 | short | ETH/USDT | 26 (8) | 0.08 | 0.003 | 0.802 | -56.6 | 0.047 | 0.097 | subtracts |
| snipper:adx_turn:spec:cross5 | short | LINK/USDT | 20 (10) | 4.87 | 0.243 | 0.759 | 169.97 | 0.019 | 0.084 | adds |
| snipper:adx_turn:spec:cross5 | short | NEAR/USDT | 19 (8) | -1.502 | -0.079 | 0.056 | -100.16 | 0.054 | 0.179 | subtracts |
| snipper:adx_turn:spec:cross5 | short | SOL/USDT | 32 (15) | 2.719 | 0.085 | 0.160 | 58.27 | 0.033 | 0.168 | adds |
| snipper:adx_turn:spec:cross5 | short | XRP/USDT | 18 (6) | -1.451 | -0.081 | 0.221 | -107.12 | 0.054 | 0.163 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | long | ADA/USDT | 18 (7) | -2.165 | -0.120 | -1.108 | -107.82 | 1.192 | 0.705 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | long | BNB/USDT | 17 (7) | 19.15 | 1.127 | 0.365 | 617.33 | 1.052 | 0.538 | adds |
| snipper:bbwp_fresh_blue:spec:cross5 | long | DOGE/USDT | 18 (9) | 23.742 | 1.319 | 1.042 | 824.02 | 1.029 | 0.443 | adds |
| snipper:bbwp_fresh_blue:spec:cross5 | long | ETH/USDT | 27 (10) | -4.515 | -0.167 | -1.020 | -143.35 | 1.280 | 0.782 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | long | LINK/USDT | 25 (7) | 3.567 | 0.143 | 0.077 | 54.37 | 1.210 | 0.571 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | long | NEAR/USDT | 25 (10) | 21.268 | 0.851 | 1.821 | 635.69 | 1.093 | 0.300 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | long | SOL/USDT | 21 (9) | 9.211 | 0.439 | 0.148 | 296.78 | 1.142 | 0.577 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | long | XRP/USDT | 26 (10) | 117.166 | 4.506 | 2.187 | 5615.11 | 0.465 | 0.238 | adds |
| snipper:bbwp_fresh_blue:spec:cross5 | short | ADA/USDT | 32 (14) | 5.046 | 0.158 | 0.036 | 163.33 | -0.208 | -0.206 | adds |
| snipper:bbwp_fresh_blue:spec:cross5 | short | BNB/USDT | 27 (12) | -8.034 | -0.298 | -0.765 | -356.41 | -0.133 | -0.072 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | short | DOGE/USDT | 31 (13) | 0.285 | 0.009 | -0.078 | 7.51 | -0.181 | -0.183 | adds |
| snipper:bbwp_fresh_blue:spec:cross5 | short | ETH/USDT | 26 (10) | -6.773 | -0.261 | 0.512 | -262.81 | -0.139 | -0.256 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | short | LINK/USDT | 23 (10) | -10.532 | -0.458 | -0.199 | -337.19 | -0.117 | -0.163 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | short | NEAR/USDT | 24 (8) | -6.084 | -0.254 | -0.496 | -231.3 | -0.141 | -0.134 | subtracts |
| snipper:bbwp_fresh_blue:spec:cross5 | short | SOL/USDT | 30 (13) | 0.307 | 0.010 | 0.111 | -34.15 | -0.180 | -0.216 | adds |
| snipper:bbwp_fresh_blue:spec:cross5 | short | XRP/USDT | 22 (7) | -7.223 | -0.328 | -0.780 | -807.97 | -0.134 | -0.114 | subtracts |

## E. Books (one ledger per run and asset, long + short; gate as written only — as-run books are in the JSON)

| run | symbol | trades | entries blocked by the filter | avg layers | equity final | return | max DD equity USDT (%) | liquidations | funding / fees USDT | exit mix | B&H | tf_status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pro:base:spec:pro5 | BTC/USDT | 11 | 0 | 2.18 | 1179.01 | -9.31% | 224.17 (15.98%) | 0 | 49.96 / 14.26 | {'exit_ctx_mlrsi_against': 7, 'exit_invalidation': 2, 'exit_rule_jeisson': 2} | 11.76% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:base:spec:pro5 | ETH/USDT | 11 | 0 | 2.27 | 1281.24 | -1.44% | 147.26 (10.6%) | 0 | 32.94 / 10.66 | {'exit_ctx_mlrsi_against': 7, 'exit_invalidation': 3, 'end_of_data': 1} | -9.9% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:base:spec:pro5 | SOL/USDT | 11 | 0 | 2.45 | 1044.56 | -19.65% | 259.6 (19.95%) | 0 | 17.81 / 7.97 | {'exit_invalidation': 3, 'exit_ctx_mlrsi_against': 7, 'exit_rule_jeisson': 1} | -42.86% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:base:spec:pro5 | XRP/USDT | 16 | 0 | 1.81 | 1416.67 | 8.97% | 665.13 (31.95%) | 0 | 47.3 / 18.97 | {'exit_ctx_mlrsi_against': 7, 'exit_invalidation': 9} | 141.06% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:base:spec:pro5 | DOGE/USDT | 9 | 0 | 2.67 | 1211.04 | -6.84% | 271.25 (18.37%) | 0 | 28.46 / 7.79 | {'exit_invalidation': 3, 'exit_ctx_mlrsi_against': 5, 'exit_rule_jeisson': 1} | -52.24% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:base:spec:pro5 | NEAR/USDT | 8 | 0 | 2.75 | 1816.48 | 39.73% | 353.1 (16.82%) | 0 | 36.42 / 5.89 | {'exit_ctx_mlrsi_against': 3, 'exit_rule_jeisson': 3, 'exit_invalidation': 1, 'end_of_data': 1} | 10.38% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:base:spec:pro5 | BNB/USDT | 11 | 0 | 1.91 | 1263.7 | -2.79% | 352.1 (21.79%) | 0 | 50.07 / 14.55 | {'exit_ctx_mlrsi_against': 7, 'exit_invalidation': 3, 'exit_rule_jeisson': 1} | 21.54% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:base:spec:pro5 | LINK/USDT | 12 | 0 | 2.5 | 1339.83 | 3.06% | 137.63 (10.18%) | 0 | 28.84 / 11.53 | {'exit_ctx_mlrsi_against': 7, 'exit_rule_jeisson': 2, 'exit_invalidation': 2, 'end_of_data': 1} | 2.29% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:base:spec:pro5 | ADA/USDT | 14 | 0 | 2.07 | 1396.35 | 7.41% | 403.34 (23.42%) | 0 | 28.96 / 12.04 | {'exit_ctx_mlrsi_against': 7, 'exit_rule_jeisson': 3, 'exit_invalidation': 4} | -43.33% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:adx_turn:spec:pro5 | BTC/USDT | 7 | 22 | 2.43 | 1248.67 | -3.95% | 180.75 (12.65%) | 0 | 45.22 / 11.74 | {'exit_rule_jeisson': 1, 'exit_invalidation': 2, 'exit_ctx_mlrsi_against': 4} | 11.76% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:adx_turn:spec:pro5 | ETH/USDT | 10 | 17 | 2.1 | 1267.0 | -2.54% | 172.13 (12.23%) | 0 | 28.32 / 9.07 | {'exit_ctx_mlrsi_against': 6, 'exit_invalidation': 3, 'end_of_data': 1} | -9.9% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:adx_turn:spec:pro5 | SOL/USDT | 8 | 23 | 2.12 | 1177.36 | -9.43% | 165.52 (12.73%) | 0 | 17.89 / 5.65 | {'exit_invalidation': 4, 'exit_ctx_mlrsi_against': 4} | -42.86% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:adx_turn:spec:pro5 | XRP/USDT | 14 | 23 | 2.07 | 1303.49 | 0.27% | 735.12 (36.06%) | 0 | 46.63 / 17.08 | {'exit_ctx_mlrsi_against': 6, 'exit_invalidation': 7, 'exit_rule_jeisson': 1} | 141.06% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:adx_turn:spec:pro5 | DOGE/USDT | 8 | 21 | 2.5 | 1148.12 | -11.68% | 419.17 (26.82%) | 0 | 32.5 / 7.98 | {'exit_ctx_mlrsi_against': 5, 'exit_rule_jeisson': 1, 'exit_invalidation': 2} | -52.24% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:adx_turn:spec:pro5 | NEAR/USDT | 6 | 26 | 2.33 | 1852.87 | 42.53% | 360.17 (16.82%) | 0 | 28.19 / 4.46 | {'exit_rule_jeisson': 2, 'exit_invalidation': 1, 'exit_ctx_mlrsi_against': 2, 'end_of_data': 1} | 10.38% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:adx_turn:spec:pro5 | BNB/USDT | 10 | 27 | 1.9 | 1174.08 | -9.69% | 321.9 (21.55%) | 0 | 36.58 / 14.76 | {'exit_ctx_mlrsi_against': 5, 'exit_invalidation': 5} | 21.54% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:adx_turn:spec:pro5 | LINK/USDT | 11 | 14 | 2.27 | 1302.46 | 0.19% | 198.59 (14.4%) | 0 | 25.36 / 10.69 | {'exit_ctx_mlrsi_against': 5, 'exit_rule_jeisson': 2, 'exit_invalidation': 3, 'end_of_data': 1} | 2.29% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:adx_turn:spec:pro5 | ADA/USDT | 10 | 19 | 2.4 | 1258.19 | -3.22% | 140.1 (10.53%) | 0 | 23.55 / 9.1 | {'exit_ctx_mlrsi_against': 6, 'exit_rule_jeisson': 2, 'exit_invalidation': 2} | -43.33% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:bbwp_fresh_blue:spec:pro5 | BTC/USDT | 8 | 25 | 2.25 | 1297.54 | -0.19% | 152.46 (10.51%) | 0 | 38.92 / 10.63 | {'exit_ctx_mlrsi_against': 5, 'exit_invalidation': 2, 'exit_rule_jeisson': 1} | 11.76% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:bbwp_fresh_blue:spec:pro5 | ETH/USDT | 9 | 19 | 2.22 | 1228.58 | -5.49% | 187.51 (13.55%) | 0 | 24.95 / 8.33 | {'exit_ctx_mlrsi_against': 6, 'exit_invalidation': 3} | -9.9% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:bbwp_fresh_blue:spec:pro5 | SOL/USDT | 10 | 29 | 2.2 | 1064.69 | -18.1% | 251.13 (19.27%) | 0 | 9.88 / 7.08 | {'exit_invalidation': 5, 'exit_ctx_mlrsi_against': 3, 'exit_rule_jeisson': 1, 'end_of_data': 1} | -42.86% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:bbwp_fresh_blue:spec:pro5 | XRP/USDT | 10 | 24 | 2.2 | 1737.26 | 33.64% | 368.62 (17.71%) | 0 | 44.26 / 12.41 | {'exit_ctx_mlrsi_against': 6, 'exit_invalidation': 3, 'end_of_data': 1} | 141.06% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:bbwp_fresh_blue:spec:pro5 | DOGE/USDT | 8 | 16 | 2.62 | 1200.95 | -7.62% | 345.96 (22.48%) | 0 | 28.92 / 7.29 | {'exit_invalidation': 3, 'exit_ctx_mlrsi_against': 4, 'end_of_data': 1} | -52.24% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:bbwp_fresh_blue:spec:pro5 | NEAR/USDT | 7 | 33 | 2.14 | 1869.16 | 43.78% | 363.34 (16.82%) | 0 | 22.97 / 5.52 | {'exit_rule_jeisson': 3, 'exit_invalidation': 1, 'exit_ctx_mlrsi_against': 2, 'end_of_data': 1} | 10.38% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:bbwp_fresh_blue:spec:pro5 | BNB/USDT | 10 | 30 | 1.9 | 1104.96 | -15.0% | 244.55 (18.15%) | 0 | 30.09 / 13.09 | {'exit_ctx_mlrsi_against': 6, 'exit_invalidation': 4} | 21.54% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:bbwp_fresh_blue:spec:pro5 | LINK/USDT | 8 | 14 | 2.5 | 1386.41 | 6.65% | 129.26 (8.54%) | 0 | 24.28 / 8.62 | {'exit_invalidation': 2, 'exit_ctx_mlrsi_against': 5, 'exit_rule_jeisson': 1} | 2.29% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| pro:bbwp_fresh_blue:spec:pro5 | ADA/USDT | 11 | 25 | 2.27 | 1330.27 | 2.33% | 235.57 (17.46%) | 0 | 28.38 / 11.22 | {'exit_invalidation': 3, 'exit_ctx_mlrsi_against': 6, 'exit_rule_jeisson': 2} | -43.33% | {'4h': 'ok', '1d': 'ok', '1w': 'ok'} |
| snipper:base:spec:cross5 | BTC/USDT | 55 | 0 | 2.29 | 1709.8 | 0.58% | 327.86 (18.12%) | 0 | 160.59 / 282.06 | {'exit_invalidation': 16, 'exit_ctx_mlrsi_against': 32, 'exit_rule_jeisson': 6, 'end_of_data': 1} | 10.5% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:cross5 | ETH/USDT | 59 | 0 | 2.07 | 1890.97 | 11.23% | 544.52 (25.2%) | 0 | 120.7 / 202.99 | {'exit_invalidation': 24, 'exit_ctx_mlrsi_against': 31, 'exit_rule_jeisson': 4} | -10.67% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:cross5 | SOL/USDT | 70 | 0 | 1.84 | 1671.01 | -1.71% | 525.59 (27.58%) | 0 | 91.01 / 175.41 | {'exit_invalidation': 25, 'exit_ctx_mlrsi_against': 33, 'exit_rule_jeisson': 11, 'end_of_data': 1} | -43.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:cross5 | XRP/USDT | 59 | 0 | 2.24 | 3026.94 | 78.06% | 1318.86 (33.25%) | 0 | 212.68 / 369.47 | {'exit_ctx_mlrsi_against': 36, 'exit_invalidation': 16, 'exit_rule_jeisson': 6, 'end_of_data': 1} | 144.84% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:cross5 | DOGE/USDT | 73 | 0 | 1.92 | 1729.3 | 1.72% | 712.16 (29.28%) | 0 | 105.55 / 215.3 | {'exit_invalidation': 28, 'exit_ctx_mlrsi_against': 37, 'exit_rule_jeisson': 8} | -53.68% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:cross5 | NEAR/USDT | 63 | 0 | 1.95 | 2657.65 | 56.33% | 828.21 (43.37%) | 0 | 77.44 / 104.57 | {'exit_ctx_mlrsi_against': 29, 'exit_rule_jeisson': 11, 'exit_invalidation': 23} | 9.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:cross5 | BNB/USDT | 65 | 0 | 1.91 | 1623.59 | -4.49% | 625.13 (29.77%) | 0 | 139.43 / 252.72 | {'exit_rule_jeisson': 9, 'exit_invalidation': 22, 'exit_ctx_mlrsi_against': 34} | 21.75% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:cross5 | LINK/USDT | 63 | 0 | 2.02 | 1232.63 | -27.49% | 840.12 (44.69%) | 0 | 63.29 / 126.51 | {'exit_invalidation': 26, 'exit_rule_jeisson': 7, 'exit_ctx_mlrsi_against': 30} | 2.14% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:cross5 | ADA/USDT | 65 | 0 | 1.88 | 1794.46 | 5.56% | 357.78 (17.17%) | 0 | 70.39 / 134.79 | {'exit_invalidation': 19, 'exit_rule_jeisson': 13, 'exit_ctx_mlrsi_against': 32, 'end_of_data': 1} | -43.61% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:iso10 | BTC/USDT | 55 | 0 | 2.29 | 1705.71 | 0.34% | 327.86 (18.12%) | 2 | 160.32 / 283.95 | {'exit_invalidation': 14, 'exit_ctx_mlrsi_against': 32, 'exit_rule_jeisson': 6, 'liquidation': 2, 'end_of_data': 1} | 10.5% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:iso10 | ETH/USDT | 59 | 0 | 2.07 | 1600.17 | -5.87% | 486.53 (26.24%) | 8 | 99.46 / 189.3 | {'exit_invalidation': 19, 'exit_ctx_mlrsi_against': 28, 'liquidation': 8, 'exit_rule_jeisson': 4} | -10.67% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:iso10 | SOL/USDT | 72 | 0 | 1.85 | 1688.17 | -0.7% | 549.78 (28.28%) | 14 | 92.9 / 205.67 | {'liquidation': 14, 'exit_ctx_mlrsi_against': 29, 'exit_rule_jeisson': 11, 'exit_invalidation': 17, 'end_of_data': 1} | -43.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:iso10 | XRP/USDT | 60 | 0 | 2.22 | 3070.42 | 80.61% | 1247.61 (31.46%) | 8 | 216.79 / 413.17 | {'exit_ctx_mlrsi_against': 32, 'exit_invalidation': 13, 'liquidation': 8, 'exit_rule_jeisson': 6, 'end_of_data': 1} | 144.84% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:iso10 | DOGE/USDT | 75 | 0 | 1.91 | 1729.7 | 1.75% | 720.7 (29.46%) | 17 | 105.36 / 246.46 | {'liquidation': 17, 'exit_ctx_mlrsi_against': 32, 'exit_invalidation': 18, 'exit_rule_jeisson': 8} | -53.68% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:iso10 | NEAR/USDT | 65 | 0 | 1.94 | 2903.44 | 70.79% | 916.31 (37.23%) | 20 | 82.84 / 145.32 | {'exit_ctx_mlrsi_against': 25, 'exit_rule_jeisson': 11, 'liquidation': 20, 'exit_invalidation': 9} | 9.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:iso10 | BNB/USDT | 65 | 0 | 1.91 | 1453.23 | -14.52% | 762.22 (36.48%) | 6 | 131.56 / 250.07 | {'exit_rule_jeisson': 9, 'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 30, 'liquidation': 6} | 21.75% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:iso10 | LINK/USDT | 64 | 0 | 2.0 | 1171.92 | -31.06% | 900.6 (47.7%) | 16 | 60.47 / 148.07 | {'liquidation': 16, 'exit_rule_jeisson': 6, 'exit_ctx_mlrsi_against': 28, 'exit_invalidation': 14} | 2.14% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:base:spec:iso10 | ADA/USDT | 71 | 0 | 1.83 | 1782.65 | 4.86% | 338.69 (17.06%) | 16 | 73.74 / 167.18 | {'liquidation': 16, 'exit_rule_jeisson': 13, 'exit_ctx_mlrsi_against': 29, 'exit_invalidation': 12, 'end_of_data': 1} | -43.61% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:cross5 | BTC/USDT | 51 | 138 | 1.98 | 1921.63 | 13.04% | 458.36 (25.44%) | 0 | 130.64 / 257.06 | {'exit_invalidation': 22, 'exit_ctx_mlrsi_against': 24, 'exit_rule_jeisson': 4, 'end_of_data': 1} | 10.5% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:cross5 | ETH/USDT | 51 | 101 | 1.96 | 1706.25 | 0.37% | 502.41 (25.7%) | 0 | 95.27 / 165.95 | {'exit_invalidation': 23, 'exit_ctx_mlrsi_against': 26, 'exit_rule_jeisson': 2} | -10.67% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:cross5 | SOL/USDT | 53 | 132 | 1.87 | 1450.08 | -14.7% | 556.32 (27.75%) | 0 | 65.82 / 147.82 | {'exit_invalidation': 23, 'exit_rule_jeisson': 7, 'exit_ctx_mlrsi_against': 23} | -43.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:cross5 | XRP/USDT | 39 | 128 | 2.33 | 3392.74 | 99.57% | 842.94 (29.87%) | 0 | 127.64 / 195.89 | {'exit_ctx_mlrsi_against': 31, 'exit_invalidation': 7, 'exit_rule_jeisson': 1} | 144.84% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:cross5 | DOGE/USDT | 48 | 136 | 2.02 | 2437.63 | 43.39% | 838.8 (25.6%) | 0 | 90.15 / 187.5 | {'exit_invalidation': 15, 'exit_ctx_mlrsi_against': 27, 'exit_rule_jeisson': 6} | -53.68% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:cross5 | NEAR/USDT | 44 | 124 | 2.09 | 4121.3 | 142.43% | 1127.01 (38.78%) | 0 | 102.25 / 111.59 | {'exit_invalidation': 17, 'exit_ctx_mlrsi_against': 20, 'exit_rule_jeisson': 7} | 9.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:cross5 | BNB/USDT | 40 | 108 | 2.17 | 1947.93 | 14.58% | 570.83 (22.85%) | 0 | 135.69 / 214.03 | {'exit_rule_jeisson': 6, 'exit_ctx_mlrsi_against': 20, 'exit_invalidation': 14} | 21.75% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:cross5 | LINK/USDT | 38 | 131 | 2.32 | 2033.13 | 19.6% | 465.45 (19.88%) | 0 | 81.13 / 135.89 | {'exit_invalidation': 12, 'exit_ctx_mlrsi_against': 23, 'exit_rule_jeisson': 3} | 2.14% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:cross5 | ADA/USDT | 47 | 154 | 1.91 | 1983.46 | 16.67% | 433.48 (20.25%) | 0 | 62.05 / 117.86 | {'exit_ctx_mlrsi_against': 23, 'exit_rule_jeisson': 9, 'exit_invalidation': 14, 'end_of_data': 1} | -43.61% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:iso10 | BTC/USDT | 51 | 138 | 1.98 | 1918.69 | 12.86% | 460.41 (25.56%) | 1 | 130.45 / 257.81 | {'exit_invalidation': 21, 'exit_ctx_mlrsi_against': 24, 'exit_rule_jeisson': 4, 'liquidation': 1, 'end_of_data': 1} | 10.5% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:iso10 | ETH/USDT | 51 | 101 | 1.96 | 1705.0 | 0.29% | 514.77 (26.18%) | 4 | 95.33 / 177.22 | {'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 25, 'liquidation': 4, 'exit_rule_jeisson': 2} | -10.67% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:iso10 | SOL/USDT | 53 | 132 | 1.87 | 1468.19 | -13.64% | 563.95 (27.77%) | 8 | 66.45 / 166.21 | {'liquidation': 8, 'exit_rule_jeisson': 7, 'exit_invalidation': 17, 'exit_ctx_mlrsi_against': 21} | -43.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:iso10 | XRP/USDT | 39 | 128 | 2.33 | 3491.97 | 105.41% | 791.37 (27.98%) | 4 | 130.53 / 210.77 | {'exit_ctx_mlrsi_against': 29, 'liquidation': 4, 'exit_invalidation': 5, 'exit_rule_jeisson': 1} | 144.84% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:iso10 | DOGE/USDT | 49 | 138 | 2.0 | 2394.22 | 40.84% | 833.8 (25.83%) | 9 | 88.45 / 204.27 | {'liquidation': 9, 'exit_ctx_mlrsi_against': 23, 'exit_invalidation': 11, 'exit_rule_jeisson': 6} | -53.68% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:iso10 | NEAR/USDT | 46 | 132 | 2.07 | 4189.86 | 146.46% | 1265.25 (35.61%) | 13 | 105.27 / 152.34 | {'liquidation': 13, 'exit_ctx_mlrsi_against': 17, 'exit_invalidation': 9, 'exit_rule_jeisson': 7} | 9.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:iso10 | BNB/USDT | 40 | 108 | 2.17 | 1750.5 | 2.97% | 756.7 (30.29%) | 3 | 128.66 / 211.92 | {'exit_rule_jeisson': 6, 'exit_ctx_mlrsi_against': 18, 'exit_invalidation': 13, 'liquidation': 3} | 21.75% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:iso10 | LINK/USDT | 39 | 137 | 2.28 | 2022.16 | 18.95% | 439.09 (19.05%) | 4 | 80.48 / 153.39 | {'liquidation': 4, 'exit_ctx_mlrsi_against': 22, 'exit_invalidation': 10, 'exit_rule_jeisson': 3} | 2.14% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:adx_turn:spec:iso10 | ADA/USDT | 48 | 167 | 1.9 | 1919.81 | 12.93% | 471.14 (22.2%) | 8 | 59.83 / 129.25 | {'liquidation': 8, 'exit_rule_jeisson': 9, 'exit_ctx_mlrsi_against': 17, 'exit_invalidation': 13, 'end_of_data': 1} | -43.61% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:cross5 | BTC/USDT | 46 | 102 | 2.24 | 1442.56 | -15.14% | 639.45 (33.83%) | 0 | 126.71 / 233.75 | {'exit_ctx_mlrsi_against': 23, 'exit_invalidation': 19, 'exit_rule_jeisson': 3, 'end_of_data': 1} | 10.5% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:cross5 | ETH/USDT | 53 | 116 | 1.81 | 1293.85 | -23.89% | 632.7 (33.47%) | 0 | 71.39 / 149.88 | {'exit_invalidation': 24, 'exit_ctx_mlrsi_against': 26, 'exit_rule_jeisson': 3} | -10.67% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:cross5 | SOL/USDT | 51 | 71 | 1.98 | 1962.63 | 15.45% | 717.6 (31.45%) | 0 | 95.26 / 154.87 | {'exit_invalidation': 17, 'exit_ctx_mlrsi_against': 27, 'exit_rule_jeisson': 6, 'end_of_data': 1} | -43.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:cross5 | XRP/USDT | 48 | 102 | 2.1 | 6507.14 | 282.77% | 1883.03 (29.84%) | 0 | 293.19 / 502.78 | {'exit_invalidation': 14, 'exit_ctx_mlrsi_against': 29, 'exit_rule_jeisson': 4, 'end_of_data': 1} | 144.84% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:cross5 | DOGE/USDT | 49 | 120 | 2.02 | 2531.52 | 48.91% | 623.95 (25.14%) | 0 | 107.2 / 179.8 | {'exit_invalidation': 18, 'exit_ctx_mlrsi_against': 25, 'exit_rule_jeisson': 6} | -53.68% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:cross5 | NEAR/USDT | 49 | 83 | 1.92 | 2104.38 | 23.79% | 699.31 (30.6%) | 0 | 70.3 / 107.55 | {'exit_invalidation': 18, 'exit_ctx_mlrsi_against': 22, 'exit_rule_jeisson': 9} | 9.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:cross5 | BNB/USDT | 44 | 127 | 1.95 | 1960.92 | 15.35% | 767.18 (29.52%) | 0 | 132.31 / 216.1 | {'exit_rule_jeisson': 6, 'exit_invalidation': 15, 'exit_ctx_mlrsi_against': 23} | 21.75% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:cross5 | LINK/USDT | 48 | 110 | 2.02 | 1417.18 | -16.64% | 617.75 (33.38%) | 0 | 63.54 / 106.32 | {'exit_invalidation': 20, 'exit_rule_jeisson': 3, 'exit_ctx_mlrsi_against': 25} | 2.14% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:cross5 | ADA/USDT | 50 | 118 | 1.92 | 1755.5 | 3.26% | 530.04 (23.89%) | 0 | 59.92 / 122.72 | {'exit_ctx_mlrsi_against': 27, 'exit_rule_jeisson': 9, 'exit_invalidation': 13, 'end_of_data': 1} | -43.61% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:iso10 | BTC/USDT | 46 | 102 | 2.24 | 1439.11 | -15.35% | 642.44 (33.99%) | 2 | 126.5 / 235.55 | {'exit_ctx_mlrsi_against': 23, 'exit_invalidation': 17, 'exit_rule_jeisson': 3, 'liquidation': 2, 'end_of_data': 1} | 10.5% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:iso10 | ETH/USDT | 53 | 116 | 1.81 | 1288.39 | -24.21% | 639.46 (33.8%) | 6 | 71.32 / 162.84 | {'exit_invalidation': 20, 'exit_ctx_mlrsi_against': 24, 'liquidation': 6, 'exit_rule_jeisson': 3} | -10.67% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:iso10 | SOL/USDT | 51 | 74 | 1.98 | 1997.19 | 17.48% | 718.52 (31.1%) | 10 | 95.35 / 179.56 | {'liquidation': 10, 'exit_ctx_mlrsi_against': 23, 'exit_rule_jeisson': 6, 'exit_invalidation': 11, 'end_of_data': 1} | -43.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:iso10 | XRP/USDT | 48 | 102 | 2.1 | 6794.85 | 299.7% | 1929.86 (29.45%) | 6 | 302.39 / 554.24 | {'exit_invalidation': 10, 'exit_ctx_mlrsi_against': 27, 'liquidation': 6, 'exit_rule_jeisson': 4, 'end_of_data': 1} | 144.84% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:iso10 | DOGE/USDT | 49 | 123 | 2.02 | 2625.54 | 54.44% | 589.91 (23.34%) | 8 | 110.13 / 196.82 | {'liquidation': 8, 'exit_ctx_mlrsi_against': 25, 'exit_invalidation': 10, 'exit_rule_jeisson': 6} | -53.68% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:iso10 | NEAR/USDT | 51 | 86 | 1.9 | 2187.32 | 28.67% | 718.23 (28.27%) | 19 | 72.24 / 151.3 | {'liquidation': 19, 'exit_ctx_mlrsi_against': 17, 'exit_rule_jeisson': 9, 'exit_invalidation': 6} | 9.53% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:iso10 | BNB/USDT | 44 | 127 | 1.95 | 1763.9 | 3.76% | 942.19 (36.25%) | 4 | 126.07 / 214.84 | {'exit_rule_jeisson': 6, 'exit_invalidation': 14, 'exit_ctx_mlrsi_against': 20, 'liquidation': 4} | 21.75% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:iso10 | LINK/USDT | 50 | 117 | 1.96 | 1398.21 | -17.75% | 589.52 (32.65%) | 10 | 62.28 / 126.48 | {'liquidation': 10, 'exit_rule_jeisson': 3, 'exit_ctx_mlrsi_against': 23, 'exit_invalidation': 14} | 2.14% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |
| snipper:bbwp_fresh_blue:spec:iso10 | ADA/USDT | 51 | 124 | 1.9 | 1743.3 | 2.55% | 535.38 (24.2%) | 6 | 59.14 / 133.34 | {'liquidation': 6, 'exit_rule_jeisson': 9, 'exit_ctx_mlrsi_against': 23, 'exit_invalidation': 12, 'end_of_data': 1} | -43.61% | {'1h': 'ok', '4h': 'ok', '1d': 'ok'} |

## F. Continuity with round 6 (BTC-only trades of the round-7 runs vs the round-6 cells)

* `pro:base:spec:pro5` vs r6 `pro:A_spec_on`: **identical** — long r7 n 4 / 10.45 USDT vs r6 n 4 / 10.45 USDT; short r7 n 7 / -131.44 USDT vs r6 n 7 / -131.44 USDT
* `pro:base:asrun:pro5` vs r6 `pro:A_on`: **identical** — long r7 n 7 / -26.65 USDT vs r6 n 7 / -26.65 USDT; short r7 n 7 / -38.57 USDT vs r6 n 7 / -38.57 USDT
* `snipper:base:spec:iso10` vs r6 `snipper:A_spec_on`: **identical** — long r7 n 25 / 146.4 USDT vs r6 n 25 / 146.4 USDT; short r7 n 30 / -140.7 USDT vs r6 n 30 / -140.7 USDT
* `snipper:base:asrun:iso10` vs r6 `snipper:A_on`: **identical** — long r7 n 31 / -127.72 USDT vs r6 n 31 / -127.72 USDT; short r7 n 34 / -308.44 USDT vs r6 n 34 / -308.44 USDT
* `snipper:base:asrun:cross5` vs r6 `snipper:B_risk_cross5:base`: **identical** — long r7 n 31 / -127.77 USDT vs r6 n 31 / -127.77 USDT; short r7 n 34 / -307.3 USDT vs r6 n 34 / -307.3 USDT
* `snipper:bbwp_fresh_blue:asrun:iso10` vs r6 `snipper:B_risk_iso10:bbwp_fresh_blue`: **identical** — long r7 n 29 / -154.49 USDT vs r6 n 29 / -154.49 USDT; short r7 n 22 / -107.58 USDT vs r6 n 22 / -107.58 USDT
* `snipper:bbwp_fresh_blue:asrun:cross5` vs r6 `snipper:B_risk_cross5:bbwp_fresh_blue`: **identical** — long r7 n 29 / -154.53 USDT vs r6 n 29 / -154.53 USDT; short r7 n 22 / -106.3 USDT vs r6 n 22 / -106.3 USDT
* `snipper:adx_turn:asrun:iso10` vs r6 `snipper:B_risk_iso10:adx_turn`: **identical** — long r7 n 25 / 163.41 USDT vs r6 n 25 / 163.41 USDT; short r7 n 28 / 392.97 USDT vs r6 n 28 / 392.97 USDT
* `snipper:adx_turn:asrun:cross5` vs r6 `snipper:B_risk_cross5:adx_turn`: **identical** — long r7 n 25 / 166.42 USDT vs r6 n 25 / 166.42 USDT; short r7 n 28 / 393.43 USDT vs r6 n 28 / 393.43 USDT

## G. Follower windows (frozen on BTC, rounds 2 / 4) and context status per asset

* pro: {'ao': 2, 'adx': 4, 'macd': 3, 'rsi': 2}; tf_status BTC/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}; ETH/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}; SOL/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}; XRP/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}; DOGE/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}; NEAR/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}; BNB/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}; LINK/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}; ADA/USDT {'4h': 'ok', '1d': 'ok', '1w': 'ok'}
* snipper: {'ao': 2, 'adx': 5, 'macd': 3, 'rsi': 3}; tf_status BTC/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}; ETH/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}; SOL/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}; XRP/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}; DOGE/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}; NEAR/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}; BNB/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}; LINK/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}; ADA/USDT {'1h': 'ok', '4h': 'ok', '1d': 'ok'}

GO cells: none.
