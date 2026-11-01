# Impulsos v2 — round-7 trades split by two PRE-DEFINED regime identifiers (prior analysis of round 8)

Source: `r7_impulse_20261101T163117Z.json` (round 7, frozen 2.3.0 chain, 9 Bitget perps, window 2024-11-01 -> 2026-11-01, IS/OOS split 2026-01-01). Script `scripts/analyze_impulse_r7_regime.py`; raw `r7_regime_split_20261101T163117Z.json`. Identifiers fixed BEFORE this table existed (`docs/PREREG_IMPULSOS_v2_r8_shadow.md` §3):

* **R1 `own`** — the asset's own daily trend: last CLOSED 1d candle at the trigger candle's close, `close > EMA200` (pandas ewm span 200, adjust=True) -> `up`, else `down`.
* **R2 `btc`** — the same rule on BTC/USDT 1d applied to every asset (BTC as the regime leader).

Descriptive only: no cell is GO/NO-GO here. `exp.` = mean net R; CI95 = cluster bootstrap (symbol x month); `up − down` = difference of the two means with its bootstrap CI95 and the share of resamples where the difference ≤ 0.

## 1. Share of the window spent in `up` (per asset; the question is whether the window itself was one regime)

| asset | window | IS | OOS |
|---|---|---|---|
| BTC/USDT | 0.54 | 0.75 | 0.24 |
| ETH/USDT | 0.44 | 0.58 | 0.24 |
| SOL/USDT | 0.41 | 0.55 | 0.23 |
| XRP/USDT | 0.52 | 0.78 | 0.15 |
| DOGE/USDT | 0.28 | 0.46 | 0.04 |
| NEAR/USDT | 0.28 | 0.16 | 0.46 |
| BNB/USDT | 0.57 | 0.75 | 0.32 |
| LINK/USDT | 0.38 | 0.48 | 0.24 |
| ADA/USDT | 0.33 | 0.53 | 0.06 |

## 2. Per primary cell: each side split by regime

| cell | side | ident | regime | n (OOS) | exp. R | CI95 | exp. OOS | PF | win | net USDT | up − down [CI95] (p ≤ 0) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| snipper:base:spec:cross5 | long | — | all | 254 (108) | 0.533 | [-0.093, 1.353] | 0.516 | 1.73 | 0.23 | 3010.09 | |
| snipper:base:spec:cross5 | long | own | up | 105 (21) | 0.034 | [-0.455, 0.636] | -0.447 | 1.05 | 0.22 | -162.45 | -0.851 [-2.251, 0.326] (0.9045) |
| snipper:base:spec:cross5 | long | own | down | 149 (87) | 0.884 | [-0.121, 2.209] | 0.748 | 2.19 | 0.23 | 3172.54 |  |
| snipper:base:spec:cross5 | long | btc | up | 143 (24) | 0.537 | [-0.15, 1.455] | -0.667 | 1.76 | 0.24 | 2189.97 | 0.010 [-1.653, 1.392] (0.4591) |
| snipper:base:spec:cross5 | long | btc | down | 111 (84) | 0.527 | [-0.42, 2.053] | 0.854 | 1.70 | 0.21 | 820.12 |  |
| snipper:base:spec:cross5 | short | — | all | 318 (118) | -0.079 | [-0.257, 0.11] | 0.136 | 0.87 | 0.33 | -973.75 | |
| snipper:base:spec:cross5 | short | own | up | 125 (18) | -0.165 | [-0.415, 0.104] | -0.201 | 0.76 | 0.36 | -907.69 | -0.141 [-0.499, 0.214] (0.7728) |
| snipper:base:spec:cross5 | short | own | down | 193 (100) | -0.024 | [-0.259, 0.226] | 0.197 | 0.96 | 0.31 | -66.06 |  |
| snipper:base:spec:cross5 | short | btc | up | 182 (27) | -0.224 | [-0.421, -0.013] | -0.286 | 0.66 | 0.32 | -1588.4 | -0.339 [-0.744, 0.034] (0.96) |
| snipper:base:spec:cross5 | short | btc | down | 136 (91) | 0.115 | [-0.194, 0.454] | 0.261 | 1.19 | 0.33 | 614.65 |  |
| snipper:adx_turn:spec:cross5 | long | — | all | 186 (78) | 0.917 | [0.114, 2.036] | 1.336 | 2.24 | 0.25 | 5696.61 | |
| snipper:adx_turn:spec:cross5 | long | own | up | 84 (15) | 0.415 | [-0.288, 1.271] | -0.170 | 1.57 | 0.23 | 1107.71 | -0.914 [-2.957, 0.711] (0.8415) |
| snipper:adx_turn:spec:cross5 | long | own | down | 102 (63) | 1.330 | [0.009, 3.295] | 1.695 | 2.78 | 0.27 | 4588.9 |  |
| snipper:adx_turn:spec:cross5 | long | btc | up | 106 (13) | 0.646 | [-0.044, 1.478] | -0.567 | 1.89 | 0.24 | 2134.71 | -0.629 [-3.046, 1.161] (0.6861) |
| snipper:adx_turn:spec:cross5 | long | btc | down | 80 (65) | 1.275 | [-0.26, 3.676] | 1.717 | 2.69 | 0.25 | 3561.9 |  |
| snipper:adx_turn:spec:cross5 | short | — | all | 225 (90) | 0.049 | [-0.196, 0.309] | 0.226 | 1.07 | 0.35 | -2.46 | |
| snipper:adx_turn:spec:cross5 | short | own | up | 87 (15) | -0.046 | [-0.361, 0.279] | -0.545 | 0.93 | 0.39 | -234.85 | -0.154 [-0.648, 0.311] (0.7351) |
| snipper:adx_turn:spec:cross5 | short | own | down | 138 (75) | 0.109 | [-0.23, 0.477] | 0.380 | 1.16 | 0.32 | 232.39 |  |
| snipper:adx_turn:spec:cross5 | short | btc | up | 128 (21) | -0.131 | [-0.391, 0.137] | -0.592 | 0.81 | 0.35 | -790.9 | -0.417 [-0.968, 0.1] (0.9389) |
| snipper:adx_turn:spec:cross5 | short | btc | down | 97 (69) | 0.286 | [-0.156, 0.767] | 0.474 | 1.45 | 0.34 | 788.44 |  |
| snipper:bbwp_fresh_blue:spec:cross5 | long | — | all | 202 (80) | 0.917 | [0.126, 2.05] | 0.474 | 2.29 | 0.25 | 7696.09 | |
| snipper:bbwp_fresh_blue:spec:cross5 | long | own | up | 89 (15) | 1.239 | [-0.223, 3.627] | -0.078 | 2.72 | 0.20 | 4164.4 | 0.575 [-1.169, 3.027] (0.3373) |
| snipper:bbwp_fresh_blue:spec:cross5 | long | own | down | 113 (65) | 0.664 | [0.015, 1.457] | 0.601 | 1.94 | 0.29 | 3531.7 |  |
| snipper:bbwp_fresh_blue:spec:cross5 | long | btc | up | 115 (19) | 1.381 | [0.153, 3.308] | -0.124 | 3.00 | 0.27 | 5731.5 | 1.077 [-0.454, 3.108] (0.0994) |
| snipper:bbwp_fresh_blue:spec:cross5 | long | btc | down | 87 (61) | 0.304 | [-0.338, 1.156] | 0.660 | 1.41 | 0.23 | 1964.6 |  |
| snipper:bbwp_fresh_blue:spec:cross5 | short | — | all | 236 (96) | -0.156 | [-0.369, 0.068] | -0.110 | 0.77 | 0.30 | -2020.4 | |
| snipper:bbwp_fresh_blue:spec:cross5 | short | own | up | 91 (15) | -0.086 | [-0.449, 0.301] | -0.159 | 0.88 | 0.39 | -444.31 | 0.114 [-0.339, 0.575] (0.3212) |
| snipper:bbwp_fresh_blue:spec:cross5 | short | own | down | 145 (81) | -0.200 | [-0.451, 0.067] | -0.101 | 0.70 | 0.25 | -1576.1 |  |
| snipper:bbwp_fresh_blue:spec:cross5 | short | btc | up | 126 (19) | -0.127 | [-0.416, 0.18] | -0.015 | 0.81 | 0.36 | -661.91 | 0.061 [-0.394, 0.49] (0.3974) |
| snipper:bbwp_fresh_blue:spec:cross5 | short | btc | down | 110 (77) | -0.188 | [-0.487, 0.167] | -0.133 | 0.73 | 0.23 | -1358.5 |  |
| pro:base:spec:pro5 | long | — | all | 51 (23) | 0.694 | [-0.297, 1.969] | 0.460 | 2.14 | 0.26 | 864.94 | |
| pro:base:spec:pro5 | long | own | up | 28 (7) | 0.543 | [-0.561, 2.329] | -0.802 | 1.93 | 0.25 | 360.02 | -0.334 [-2.666, 1.989] (0.614) |
| pro:base:spec:pro5 | long | own | down | 23 (16) | 0.878 | [-0.526, 2.777] | 1.012 | 2.38 | 0.26 | 504.92 |  |
| pro:base:spec:pro5 | long | btc | up | 35 (7) | 0.538 | [-0.466, 2.042] | -0.856 | 1.90 | 0.26 | 455.02 | -0.498 [-3.426, 1.901] (0.6225) |
| pro:base:spec:pro5 | long | btc | down | 16 (16) | 1.035 | [-0.711, 3.66] | 1.035 | 2.64 | 0.25 | 409.92 |  |
| pro:base:spec:pro5 | short | — | all | 52 (21) | -0.429 | [-0.795, -0.054] | -0.424 | 0.44 | 0.36 | -616.06 | |
| pro:base:spec:pro5 | short | own | up | 21 (2) | -0.302 | [-0.784, 0.146] | 0.290 | 0.49 | 0.52 | -195.93 | 0.214 [-0.514, 0.897] (0.2698) |
| pro:base:spec:pro5 | short | own | down | 31 (19) | -0.516 | [-1.026, 0.053] | -0.499 | 0.42 | 0.26 | -420.13 |  |
| pro:base:spec:pro5 | short | btc | up | 25 (2) | -0.277 | [-0.721, 0.178] | -0.048 | 0.53 | 0.48 | -203.36 | 0.293 [-0.429, 1.005] (0.2091) |
| pro:base:spec:pro5 | short | btc | down | 27 (19) | -0.571 | [-1.116, 0.053] | -0.463 | 0.38 | 0.26 | -412.71 |  |
| pro:adx_turn:spec:pro5 | long | — | all | 42 (23) | 0.663 | [-0.446, 2.075] | 0.349 | 1.98 | 0.24 | 701.35 | |
| pro:adx_turn:spec:pro5 | long | own | up | 18 (4) | 0.700 | [-0.764, 3.131] | -0.946 | 2.07 | 0.17 | 308.79 | 0.065 [-2.485, 2.892] (0.4998) |
| pro:adx_turn:spec:pro5 | long | own | down | 24 (19) | 0.635 | [-0.634, 2.546] | 0.622 | 1.92 | 0.29 | 392.56 |  |
| pro:adx_turn:spec:pro5 | long | btc | up | 24 (6) | 0.412 | [-0.71, 2.321] | -0.995 | 1.62 | 0.17 | 242.25 | -0.587 [-3.327, 2.005] (0.656) |
| pro:adx_turn:spec:pro5 | long | btc | down | 18 (17) | 0.998 | [-0.681, 3.488] | 0.824 | 2.43 | 0.33 | 459.1 |  |
| pro:adx_turn:spec:pro5 | short | — | all | 42 (14) | -0.560 | [-0.998, -0.01] | -1.014 | 0.37 | 0.24 | -669.12 | |
| pro:adx_turn:spec:pro5 | short | own | up | 12 (0) | -0.573 | [-1.183, 0.001] | — | 0.24 | 0.33 | -205.63 | -0.018 [-0.945, 0.813] (0.4978) |
| pro:adx_turn:spec:pro5 | short | own | down | 30 (14) | -0.555 | [-1.104, 0.159] | -1.014 | 0.41 | 0.20 | -463.49 |  |
| pro:adx_turn:spec:pro5 | short | btc | up | 21 (2) | -0.080 | [-0.77, 0.873] | -0.200 | 0.87 | 0.33 | -80.37 | 0.961 [0.112, 1.996] (0.012) |
| pro:adx_turn:spec:pro5 | short | btc | down | 21 (12) | -1.041 | [-1.472, -0.611] | -1.149 | 0.09 | 0.14 | -588.74 |  |
| pro:bbwp_fresh_blue:spec:pro5 | long | — | all | 34 (15) | 0.884 | [-0.514, 2.696] | 0.940 | 2.36 | 0.27 | 802.39 | |
| pro:bbwp_fresh_blue:spec:pro5 | long | own | up | 16 (2) | 0.697 | [-0.907, 3.511] | -0.923 | 2.09 | 0.19 | 291.27 | -0.353 [-3.473, 3.033] (0.5985) |
| pro:bbwp_fresh_blue:spec:pro5 | long | own | down | 18 (13) | 1.050 | [-0.59, 3.476] | 1.226 | 2.59 | 0.33 | 511.13 |  |
| pro:bbwp_fresh_blue:spec:pro5 | long | btc | up | 19 (1) | 0.562 | [-0.851, 2.966] | -1.304 | 1.89 | 0.21 | 280.3 | -0.729 [-4.1, 2.584] (0.6749) |
| pro:bbwp_fresh_blue:spec:pro5 | long | btc | down | 15 (14) | 1.291 | [-0.673, 4.153] | 1.100 | 2.92 | 0.33 | 522.1 |  |
| pro:bbwp_fresh_blue:spec:pro5 | short | — | all | 47 (20) | -0.211 | [-0.679, 0.334] | -0.373 | 0.71 | 0.36 | -282.57 | |
| pro:bbwp_fresh_blue:spec:pro5 | short | own | up | 15 (2) | 0.049 | [-0.568, 0.701] | 0.393 | 1.10 | 0.53 | 15.67 | 0.383 [-0.555, 1.269] (0.2021) |
| pro:bbwp_fresh_blue:spec:pro5 | short | own | down | 32 (18) | -0.334 | [-0.918, 0.419] | -0.458 | 0.60 | 0.28 | -298.24 |  |
| pro:bbwp_fresh_blue:spec:pro5 | short | btc | up | 23 (3) | 0.146 | [-0.527, 1.056] | 0.237 | 1.29 | 0.43 | 58.69 | 0.701 [-0.248, 1.769] (0.0793) |
| pro:bbwp_fresh_blue:spec:pro5 | short | btc | down | 24 (17) | -0.554 | [-1.106, 0.096] | -0.480 | 0.40 | 0.29 | -341.27 |  |

## 3. The three round-8 books on the round-7 trades (what the backtest PREDICTS for the forward shadow)

`regime_own` = longs entered in `up` + shorts entered in `down` by R1; `regime_btc` the same by R2 (informational).

| cell | book | n (OOS) | exp. R | CI95 | exp. OOS | PF | win | net USDT | p(exp ≤ 0) |
|---|---|---|---|---|---|---|---|---|---|
| snipper:base:spec:cross5 | long_only | 254 (108) | 0.533 | [-0.093, 1.353] | 0.516 | 1.73 | 0.23 | 3010.09 | 0.0553 |
| snipper:base:spec:cross5 | short_only | 318 (118) | -0.079 | [-0.257, 0.11] | 0.136 | 0.87 | 0.33 | -973.75 | 0.8070 |
| snipper:base:spec:cross5 | regime_own | 298 (121) | -0.003 | [-0.236, 0.266] | 0.085 | 0.99 | 0.28 | -228.51 | 0.5296 |
| snipper:base:spec:cross5 | regime_btc | 279 (115) | 0.332 | [-0.06, 0.821] | 0.068 | 1.51 | 0.29 | 2804.62 | 0.0580 |
| snipper:adx_turn:spec:cross5 | long_only | 186 (78) | 0.917 | [0.114, 2.036] | 1.336 | 2.24 | 0.25 | 5696.61 | 0.0102 |
| snipper:adx_turn:spec:cross5 | short_only | 225 (90) | 0.049 | [-0.196, 0.309] | 0.226 | 1.07 | 0.35 | -2.46 | 0.3564 |
| snipper:adx_turn:spec:cross5 | regime_own | 222 (90) | 0.225 | [-0.113, 0.603] | 0.288 | 1.33 | 0.28 | 1340.11 | 0.1089 |
| snipper:adx_turn:spec:cross5 | regime_btc | 203 (82) | 0.474 | [0.048, 0.955] | 0.309 | 1.69 | 0.29 | 2923.15 | 0.0139 |
| snipper:bbwp_fresh_blue:spec:cross5 | long_only | 202 (80) | 0.917 | [0.126, 2.05] | 0.474 | 2.29 | 0.25 | 7696.09 | 0.0076 |
| snipper:bbwp_fresh_blue:spec:cross5 | short_only | 236 (96) | -0.156 | [-0.369, 0.068] | -0.110 | 0.77 | 0.30 | -2020.4 | 0.9172 |
| snipper:bbwp_fresh_blue:spec:cross5 | regime_own | 234 (96) | 0.347 | [-0.251, 1.25] | -0.097 | 1.50 | 0.23 | 2588.3 | 0.2152 |
| snipper:bbwp_fresh_blue:spec:cross5 | regime_btc | 225 (96) | 0.614 | [-0.051, 1.61] | -0.132 | 1.88 | 0.25 | 4373.0 | 0.0438 |
| pro:base:spec:pro5 | long_only | 51 (23) | 0.694 | [-0.297, 1.969] | 0.460 | 2.14 | 0.26 | 864.94 | 0.1100 |
| pro:base:spec:pro5 | short_only | 52 (21) | -0.429 | [-0.795, -0.054] | -0.424 | 0.44 | 0.36 | -616.06 | 0.9873 |
| pro:base:spec:pro5 | regime_own | 59 (26) | -0.013 | [-0.638, 0.897] | -0.580 | 0.98 | 0.25 | -60.11 | 0.5615 |
| pro:base:spec:pro5 | regime_btc | 62 (26) | 0.055 | [-0.587, 0.939] | -0.569 | 1.07 | 0.26 | 42.31 | 0.4819 |
| pro:adx_turn:spec:pro5 | long_only | 42 (23) | 0.663 | [-0.446, 2.075] | 0.349 | 1.98 | 0.24 | 701.35 | 0.1558 |
| pro:adx_turn:spec:pro5 | short_only | 42 (14) | -0.560 | [-0.998, -0.01] | -1.014 | 0.37 | 0.24 | -669.12 | 0.9772 |
| pro:adx_turn:spec:pro5 | regime_own | 48 (18) | -0.085 | [-0.808, 0.92] | -0.999 | 0.90 | 0.19 | -154.69 | 0.6180 |
| pro:adx_turn:spec:pro5 | regime_btc | 45 (18) | -0.266 | [-0.941, 0.766] | -1.098 | 0.70 | 0.16 | -346.49 | 0.7479 |
| pro:bbwp_fresh_blue:spec:pro5 | long_only | 34 (15) | 0.884 | [-0.514, 2.696] | 0.940 | 2.36 | 0.27 | 802.39 | 0.1339 |
| pro:bbwp_fresh_blue:spec:pro5 | short_only | 47 (20) | -0.211 | [-0.679, 0.334] | -0.373 | 0.71 | 0.36 | -282.57 | 0.7992 |
| pro:bbwp_fresh_blue:spec:pro5 | regime_own | 48 (20) | 0.010 | [-0.758, 1.152] | -0.505 | 1.01 | 0.25 | -6.98 | 0.5397 |
| pro:bbwp_fresh_blue:spec:pro5 | regime_btc | 43 (18) | -0.061 | [-0.828, 1.159] | -0.526 | 0.92 | 0.26 | -60.97 | 0.5962 |
