# Real-candle golden fixtures

`btc_usdt_bitget_{tf}_20260713T1600.json` — the last 520 BTC/USDT spot
candles per timeframe (30m / 1h / 4h / 1d) **closed at or before 2026-07-13
16:00:00 UTC**, fetched from Bitget via ccxt with `limit=200` forward
pagination (the E13 gotcha: larger limits silently break `since` on the
bitget history endpoint). Format: `[[open_ts_ms, open, high, low, close,
volume], ...]`, oldest first, closed candles only.

This is the evaluation instant of the two v0.2.0 real goldens
(docs/STRATEGY_SETUPS_SPEC.md §I.3 / §I.5, owner case 2026-07-13):

* **H1 golden** — the 1d bearish impulse (−2.27%): at 16:00 UTC the 4h
  down-watch is `CONFIRMED` (grade A turn, age 0) while the 30m and 1h
  down-watches sit in `FALSE_ENTRY_PROBABLE` by timeout. H1 Rule 1 must
  override both to `CONFIRMED_BY_HIGHER_TF`.
* **C1 golden (C1-G1)** — `{30m, 1h, 4h}` are fully bear-aligned from 16:00
  to 20:00 UTC while the 1d is still retracing (never bear-aligned); the
  window must fire bear.

The fixtures are immutable (spec §0.4): re-fetching a different range or
re-cutting a different instant is a NEW fixture, never an overwrite.
Consumed by `tests/test_v020_real_goldens.py`.

## Addendum 2026-07-17 — 1w fixture (replay-smoke net)

`btc_usdt_bitget_1w_20260713T1600.json` — the 298 BTC/USDT weekly candles
closed at or before the SAME instant (2026-07-13 16:00 UTC), cut from the
immutable §I.6 replay data set (`data_manifest.json`, sha256-manifested
Bitget candles, 2026-07-16). Same row format. NEW fixture per the rule
above — nothing was overwritten.

Added for `tests/test_v020_replay_smoke.py`: the 1w is the adversarial TF
for the H1 freshness invariant — a weekly CONFIRMED lingers for months, so
without the v0.2.1 freshness grant condition it rescues every lower-TF
watch in its direction (the shipped-0.2.0 P0). The smoke walk needs it in
the ladder for the bug class to be visible in aggregates.
