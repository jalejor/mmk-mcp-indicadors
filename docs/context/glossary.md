# Glossary

Domain and code terms used across the service.

## Market data

- **OHLCV** — Open, High, Low, Close, Volume candle series fetched from an
  exchange via ccxt. The internal DataFrame is indexed by a UTC `datetime`.
- **Timeframe** — candle duration in ccxt notation (`1m`, `5m`, `15m`, `1h`,
  `4h`, `1d`, `1w`, `1M`, …). Human aliases `daily/weekly/monthly` (and Spanish
  `diario/semanal/mensual`) are accepted by metrics/dominance.
- **Span** — a retrospective range string used when `start`/`end` are omitted,
  e.g. `48h`, `7d`, `2w`, `1m`. ⚠️ Unit letters are **not consistent** across
  services (see [known-errors.md](known-errors.md#e2)):
  - `AveragesService`: `h`=hours, `d`=days, `w`=weeks, `m`=months (~30d).
  - `ChartService`: `h/d/w` plus `M`=months; `m`/minutes not supported.
- **Exchange** — `binance` or `bitget` (ccxt spot). Default is **`bitget`**
  (`DEFAULT_EXCHANGE`); see [decisions.md](decisions.md#d1).

## Indicators (`IndicatorsService`)

- **RSI(14)** — Relative Strength Index; momentum oscillator 0–100. Key
  `rsi14`.
- **ADX(14) / +DI / -DI** — Average Directional Index (trend strength) plus the
  directional indicators used to decide bullish vs bearish. Keys `adx14`,
  `plus_di`, `minus_di`.
- **BBW** — Bollinger Band Width: `(Upper − Lower) / Middle × 100`. Key `bbw`.
- **BBWP** — Bollinger Band Width **Percentile**: rank (0–100) of the current
  BBW within a rolling `bbwp_lookback` (default 252) window. Near 100 =
  volatility expansion, near 0 = historic compression. Keys `bbwp`, `bbwp_ma4`
  (4-bar smoothing). ⚠️ Because BBWP is a **0–100 percentile**, the rule
  thresholds are `bbwp_high=80` / `bbwp_low=20`, not the `4.0/1.5` still shown in
  older docs (see [known-errors.md](known-errors.md#e3)).
- **AO** — Awesome Oscillator (5/34 median-price momentum). Key `ao`.
- **SMA/EMA 50 & 200** — simple/exponential moving averages. Keys `sma50`,
  `ema50`, `sma200`, `ema200`.
- **MACD(12,26,9)** — Moving Average Convergence Divergence. Keys `macd`,
  `macd_signal`, `macd_histogram`.
- **Stoch-RSI(14)** — Stochastic RSI %K/%D. Keys `stoch_rsi_k`, `stoch_rsi_d`.
- **ATR(14)** — Average True Range, absolute volatility in price units. Key
  `atr`. Drives ATR-based position sizing.
- **volatility_20** — realised volatility: rolling 20-bar stdev of returns, in %.

### Konkorde (by Blai5)

A composite volume/flow indicator. Three lines, all re-centred on zero so a
reading of 0 means neutral:

- **`konkorde_azul`** (blue) — retail / weak-hands flow (PVI oscillator, `OscP`).
- **`konkorde_verde`** (green) — trend / strong-hands flow.
- **`konkorde_marron`** (brown) — net strong-hands position; the decisive line.
- **`konkorde_value`** — **DEPRECATED** alias of `konkorde_marron`, still read by
  `RulesService` for the buy/sell vote. Positive ⇒ buying pressure.
- **`konkorde_signal`** — classification string. Emitted values are
  `bullish_strong`, `bullish_weak`, `bearish_strong`, `bearish_weak`,
  `neutral`. ⚠️ Older API docs show a bare `"bullish"`, which the code never
  emits (see [known-errors.md](known-errors.md#e4)).
- **PVI / NVI** — Positive/Negative Volume Index: cumulative volume-weighted
  price-change indices, updated only when volume rises (PVI) or falls (NVI).
- **MFI(14)** — Money Flow Index; volume-weighted RSI (computed over the typical
  price `tprice = OHLC4`).

## Rules & signals (`RulesService`)

- **Signal** — one of `entry` (open long), `exit` (open short / close long),
  `neutral`. Fires only when the winning side's weighted score ≥
  `max(4.0, 0.6 × total_score)` and beats the other side.
- **Vote / support** — each indicator that agrees appends a **signal code** to
  `support_entry` or `support_exit` (e.g. `rsi_oversold`, `konkorde_buy`,
  `macd_bullish`, `adx_trend_bullish`, `ao_positive`, `ema50_gt_sma50`,
  `stoch_rsi_oversold`, `low_volatility`, `vol_low`/`vol_high`).
- **Family / weight** — each signal code maps to an indicator **family**
  (`_SIGNAL_FAMILY`) with a weight (`DEFAULT_WEIGHTS`: konkorde 3.0, ao 2.0,
  adx 2.0, macd 1.5, rsi/bbwp/stoch_rsi/ma_cross 1.0, volatility 0.5).
  Overridable via `<FAMILY>_WEIGHT` env vars.
- **entry_score / exit_score** — sum of weights of the supporting signals.
- **entry_votes / exit_votes** — raw count of supporting signals (unweighted).
- **Regime** — market state inferred from BBWP/ADX:
  - `compression` — BBWP < `bbwp_low`; **blocks all signals**.
  - `exhaustion` — BBWP > `bbwp_high`.
  - `trending` — ADX > `adx_trend` (×1.5 ADX weight).
  - `ranging` — ADX < 20 (×1.5 RSI/Stoch-RSI weight).
  - `transitional` — none of the above.
- **regime_adjustments** — list describing which weight biases were applied.
- **explain_entry / explain_exit** — Spanish human-readable strings for each
  supporting signal code.
- **Threshold** — configurable trigger levels (`rsi_overbought/oversold`,
  `adx_trend`, `bbwp_high/low`), layered defaults → global env → per-symbol env →
  constructor arg. Per-symbol env key = symbol with `/`→`_`, upper-cased
  (`BTC_USDT_RSI_OVERSOLD`).

## Sizing & trading (`MovementsService`, `BacktestService`, `sizing_profiles`)

- **Risk profile** — `low` / `medium` / `high`. Maps to
  `ATR_PROFILES` `(atr_mult_stop, r_multiple_target)` =
  `(1.0,2.0)/(1.5,3.0)/(2.0,4.0)` and legacy `RISK_PROFILES`
  `(target_pct, stop_pct)` = `(2.5,1.5)/(5.0,3.0)/(10.0,5.0)`.
- **ATR sizing** — stop = `ATR × atr_mult_stop`; target = `stop_distance ×
  r_multiple`; quantity = `dollar_risk / stop_distance`, where `dollar_risk =
  capital × risk_per_trade_pct/100`. Default sizing mode.
- **Legacy percent sizing** — fixed `(target_pct, stop_pct)` off the last close;
  used only when `use_atr_sizing=False`.
- **R-multiple** — profit/loss expressed in units of the initial risk (stop
  distance). A trade that gains 2× its risk is `+2R`.
- **position_size_usd** — notional deployed (`quantity × entry price`), **not**
  the dollar risk. (Label was corrected in commit `db4a0e8`.)
- **dollar_risk / dollar_target** — $ lost at a full stop / gained at target.
- **confidence** — `entry_votes / (entry_votes + exit_votes)` for the side.
- **atr_fallback** — flag set when ATR sizing degrades to percent mode because
  ATR could not be computed.

## Backtest metrics (`BacktestService`)

- **win_rate**, **avg_win_R / avg_loss_R**, **expectancy_R** — per-trade
  R-multiple statistics.
- **profit_factor** — gross wins / gross losses ($).
- **max_drawdown_pct** — largest peak-to-trough equity drop.
- **sharpe_ratio** — per-bar return Sharpe, annualised via `_BARS_PER_YEAR`.
- **exit_reason** — `target` | `stop` | `end_of_data`.
- **warmup_bars** — leading bars used only to prime indicators (never traded).

## Other

- **Dominance** — a coin's share of total crypto market cap (CoinGecko
  `market_cap_percentage`), e.g. BTC dominance.
- **Major rebound** — in `AveragesService`, the largest single-candle close-to-
  close % change in the range (`bullish`/`bearish`).
- **MCP** — Model Context Protocol; the SSE transport mounted at `<prefix>/mcp`
  that exposes the HTTP operations as tools for AI editors (via `mcp-proxy`).
