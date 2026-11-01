"""Offline tests for the impulsos-v2 backtest harness (no network)."""

from datetime import datetime, timezone

import pandas as pd
import pytest

from controllers.metrics.impulse_backtest import (
    BLOCK_IS,
    BLOCK_OOS,
    closed_only,
    cost_in_r,
    drawdown,
    fetch_ohlcv_forward,
    load_ohlcv,
    rows_to_frame,
    simulate_decisions,
    split_metrics,
    trades_from_engine,
    verdict,
)

UTC = timezone.utc
DAY_MS = 86_400_000


def _frame(closes, highs=None, lows=None, start="2026-01-01", atr=10.0):
    idx = pd.date_range(start, periods=len(closes), freq="D", tz="UTC")
    df = pd.DataFrame(
        {
            "timestamp": (idx.asi8 // 1_000_000).astype("int64"),
            "open": closes,
            "high": highs or [c + 1 for c in closes],
            "low": lows or [c - 1 for c in closes],
            "close": closes,
            "volume": [1.0] * len(closes),
            "atr14": [atr] * len(closes),
        },
        index=idx,
    )
    return df


def _dec(df, i, action, side=None):
    return {"timestamp": df.index[i], "action": action, "side": side}


def _sim(df, decisions, direction="long", split="2026-01-04"):
    return simulate_decisions(
        df, decisions, direction=direction, atr_mult_stop=1.5,
        split=datetime.fromisoformat(split).replace(tzinfo=UTC),
        start=datetime(2025, 1, 1, tzinfo=UTC), end=datetime(2027, 1, 1, tzinfo=UTC),
        symbol="BTC/USDT", timeframe="1d",
    )


def test_long_signal_exit_net_of_costs():
    df = _frame([100, 105, 110, 120, 118])
    trades = _sim(df, [_dec(df, 0, "enter", "long"), _dec(df, 3, "exit", "long")])
    assert len(trades) == 1
    t = trades[0]
    assert t.exit_reason == "signal_exit" and t.bars_held == 3
    assert t.r_gross == pytest.approx(20 / 15)
    assert t.cost_r == pytest.approx(cost_in_r(100, 120, 15))
    assert t.r_net == pytest.approx(20 / 15 - 0.0015 * 220 / 15, abs=1e-6)
    assert t.block == BLOCK_IS


def test_stop_first_even_when_exit_signal_same_bar():
    df = _frame([100, 101, 95], lows=[99, 100, 80])
    trades = _sim(df, [_dec(df, 0, "enter", "long"), _dec(df, 2, "exit", "long")])
    assert trades[0].exit_reason == "stop"
    assert trades[0].exit_price == pytest.approx(85.0)
    assert trades[0].r_gross == pytest.approx(-1.0)


def test_stop_fills_at_worse_gapped_open():
    df = _frame([100, 101, 70], lows=[99, 100, 60])
    df.loc[df.index[2], "open"] = 75.0  # gapped below the 85 stop
    trades = _sim(df, [_dec(df, 0, "enter", "long")])
    assert trades[0].exit_reason == "stop" and trades[0].exit_price == pytest.approx(75.0)


def test_short_funding_and_time_stop():
    df = _frame([100, 99, 98, 97, 96])
    trades = simulate_decisions(
        df, [_dec(df, 0, "enter", "short")], direction="short", atr_mult_stop=1.5,
        split=datetime(2026, 1, 4, tzinfo=UTC), start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2027, 1, 1, tzinfo=UTC), timeframe="1d", time_stop_bars=2,
    )
    t = trades[0]
    assert t.exit_reason == "time_stop" and t.bars_held == 2
    assert t.funding_r == pytest.approx(0.0001 * 6 * 100 / 15)  # 48h = 6 x 8h
    assert t.r_net == pytest.approx(t.r_gross - t.cost_r - t.funding_r, abs=1e-6)


def test_trades_from_engine_uses_engine_prices():
    df = _frame([100, 104, 108, 90, 95, 97])
    ms = lambda i: int(df["timestamp"].iloc[i])  # noqa: E731
    decisions = [
        {"timestamp": ms(0), "action": "enter", "side": "long", "stop_price": 85.0, "reasons": ["entry"], "confidence": 0.7},
        {"timestamp": ms(1), "action": "hold", "side": "long"},
        {"timestamp": ms(2), "action": "exit", "side": "long", "exit_price": 108.0, "reasons": ["exit_rule_jeisson"]},
        {"timestamp": ms(3), "action": "enter", "side": "short", "stop_price": 105.0},
        {"timestamp": ms(4), "action": "exit", "side": "short", "exit_price": 99.0, "reasons": ["exit_stop_atr"]},
        {"timestamp": ms(5), "action": "none", "side": "none"},
    ]
    trades = trades_from_engine(
        df, decisions, split=datetime(2026, 1, 3, tzinfo=UTC), start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2027, 1, 1, tzinfo=UTC), profile="ancient", symbol="BTC/USDT", timeframe="1d",
        funded_sides=("short",),
    )
    long_t, short_t = trades
    assert long_t.exit_reason == "exit_rule_jeisson" and long_t.r_gross == pytest.approx(8 / 15)
    assert long_t.funding_r == 0 and long_t.confidence == 0.7 and long_t.block == BLOCK_IS
    assert short_t.exit_reason == "exit_stop_atr" and short_t.exit_price == 99.0
    assert short_t.r_gross == pytest.approx(-9 / 15) and short_t.funding_r > 0
    assert short_t.block == BLOCK_OOS


def test_verdict_rules():
    df = _frame([100, 105, 110])
    few = split_metrics(_sim(df, [_dec(df, 0, "enter", "long"), _dec(df, 2, "exit")]))
    assert verdict(few)["verdict"] == "INCONCLUSIVE"


def test_short_direction_and_opposite_enter_closes():
    df = _frame([100, 97, 90, 92, 91], highs=[101, 98, 91, 93, 92])
    decisions = [_dec(df, 0, "enter", "short"), _dec(df, 2, "enter", "long")]
    shorts = _sim(df, decisions, direction="short")
    assert len(shorts) == 1 and shorts[0].exit_reason == "signal_exit"
    assert shorts[0].r_gross == pytest.approx(10 / 15)
    # The long enter at bar 2 is ignored by the short book and vice versa.
    longs = _sim(df, decisions, direction="long")
    assert len(longs) == 1 and longs[0].entry_time.startswith("2026-01-03")
    assert longs[0].exit_reason == "end_of_data"


def test_no_entry_on_last_bar_and_split_blocks():
    df = _frame([100, 101, 102, 103, 104, 105])
    decisions = [
        _dec(df, 0, "enter", "long"), _dec(df, 1, "exit"),
        _dec(df, 4, "enter", "long"), _dec(df, 5, "exit", "long"),
    ]
    trades = _sim(df, decisions)
    assert [t.block for t in trades] == [BLOCK_IS, BLOCK_OOS]
    only_last = _sim(df, [_dec(df, 5, "enter", "long")])
    assert only_last == []
    m = split_metrics(trades)
    assert m[BLOCK_IS]["n"] == 1 and m[BLOCK_OOS]["n"] == 1 and m["all"]["n"] == 2


def test_timestamp_conventions_ms_and_close_time():
    df = _frame([100, 105, 110])
    as_open = [
        {"timestamp": int(df["timestamp"].iloc[0]), "action": "enter", "side": "long"},
        {"timestamp": df.index[2].isoformat(), "action": "exit", "side": "long"},
    ]
    trades = _sim(df, as_open)
    assert trades[0].entry_price == 100 and trades[0].exit_price == 110
    as_close = [
        {"timestamp": df.index[0] + pd.Timedelta(days=1), "action": "enter", "side": "long"},
        {"timestamp": df.index[2] + pd.Timedelta(days=1), "action": "exit", "side": "long"},
    ]
    trades = simulate_decisions(
        df, as_close, direction="long", atr_mult_stop=1.5,
        split=datetime(2026, 1, 4, tzinfo=UTC), start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2027, 1, 1, tzinfo=UTC), timeframe="1d", timestamp_is_close=True,
    )
    assert trades[0].entry_price == 100 and trades[0].exit_price == 110


def test_drawdown_in_r_and_pct():
    df = _frame([100, 85, 100, 85, 100], lows=[99, 80, 99, 80, 99])
    decisions = [_dec(df, 0, "enter", "long"), _dec(df, 2, "enter", "long")]
    trades = _sim(df, decisions)
    dd = drawdown(trades)
    assert dd["max_drawdown_R"] == pytest.approx(-sum(t.r_net for t in trades), abs=1e-3)
    assert dd["max_drawdown_pct"] > 0


def test_forward_pagination_skips_leading_gap_and_stops():
    data = [[i * DAY_MS, 1, 1, 1, 1, 1] for i in range(1000, 1450)]
    calls = []

    def fetch(symbol, timeframe, since, limit):  # bitget-like: window [since, since+limit*tf)
        calls.append(since)
        return [r for r in data if since <= r[0] < since + limit * DAY_MS]

    rows = fetch_ohlcv_forward(fetch, symbol="X", timeframe="1d", since_ms=0, end_ms=2000 * DAY_MS)
    assert [r[0] for r in rows] == [r[0] for r in data]
    assert len(calls) <= 12  # walks empty pages to end_ms, never loops


def test_forward_pagination_patches_holes_from_fallback():
    data = [[i * DAY_MS, 1, 1, 1, 1, 1] for i in range(0, 1000)]
    hole = range(300 * DAY_MS, 650 * DAY_MS)  # ccxt serves nothing here (bitget hand-over)

    def fetch(symbol, timeframe, since, limit):
        return [r for r in data if since <= r[0] < since + limit * DAY_MS and r[0] not in hole]

    def raw(symbol, timeframe, since, limit):
        return [r for r in data if since <= r[0] < since + limit * DAY_MS]

    rows = fetch_ohlcv_forward(fetch, symbol="X", timeframe="1d", since_ms=0,
                               end_ms=1000 * DAY_MS, fallback=raw)
    assert [r[0] for r in rows] == [r[0] for r in data]


def test_closed_only_drops_forming_candle_and_end():
    df = rows_to_frame([[i * DAY_MS, 1, 1, 1, 1, 1] for i in range(10)])
    out = closed_only(df, "1d", datetime.fromtimestamp(8 * DAY_MS / 1000, tz=UTC), now_ms=9.5 * DAY_MS)
    assert out["timestamp"].iloc[-1] == 7 * DAY_MS
    out2 = closed_only(df, "1d", datetime.fromtimestamp(20 * DAY_MS / 1000, tz=UTC), now_ms=9.5 * DAY_MS)
    assert out2["timestamp"].iloc[-1] == 8 * DAY_MS  # bar 9 still forming


def test_load_ohlcv_caches(tmp_path):
    base = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)
    data = [[base + i * DAY_MS, 1, 2, 0.5, 1.5, 3] for i in range(400)]
    calls = []

    def fetch(symbol, timeframe, since, limit):
        calls.append(since)
        return [r for r in data if r[0] >= since][:limit]

    start = datetime(2025, 12, 1, tzinfo=UTC)
    end = datetime(2026, 1, 15, tzinfo=UTC)
    df1, info1 = load_ohlcv("BTC/USDT", "1d", start, end, cache_dir=str(tmp_path), warmup_bars=300, fetch=fetch)
    n_calls = len(calls)
    df2, info2 = load_ohlcv("BTC/USDT", "1d", start, end, cache_dir=str(tmp_path), warmup_bars=300, fetch=fetch)
    assert info1.source == "exchange" and info2.source == "cache"
    assert len(calls) == n_calls
    assert info1.sha256 == info2.sha256 and len(df1) == len(df2)
    assert df1.index[-1] < pd.Timestamp(end)
