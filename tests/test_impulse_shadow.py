"""Round 8 shadow runner (`impulse_shadow`): replay from the anchor, activation cut, regime labels,
idempotent JSONL, dry-run writes nothing, ntfy line never carries the topic, incremental cache merge,
and the incremental runner (machine snapshots, ML RSI cache, `calculate_impulse`) being byte-identical
to the full replay.

Frames are indicator COLUMNS (the S02 worked example of the round-2 goldens moved to a 1h
trigger with a 4h guardian and a 1d context), injected by monkeypatching
`impulse_shadow.enriched_frames` so no TV enrichment / market data is involved. Every
expected count below is derived from the rule: leader verde zero cross up at bar 10, AO at 11,
MACD at 12 -> ENTER long at 12 (close 13:00Z); guardian ML RSI red from the 4h candle that
closes at 20:00Z -> `exit_ctx_mlrsi_against` on the 1h candle closing at 20:00Z (bar 19)."""

import json

import numpy as np
import pandas as pd
import pytest

from controllers.metrics import impulse_shadow as sh
from controllers.metrics.impulse_regime import DOWN, UP
from controllers.metrics.indicators_service import IndicatorsService
from controllers.metrics.ml_rsi import MlRsiParams, ml_rsi_frame

N = 30
START = "2026-01-10T00:00:00Z"


def _trigger_1h(n=N):
    index = pd.date_range(START, periods=n, freq="1h", tz="UTC")
    close = np.full(n, 60000.0)
    close[12:] = 61300.0
    low = close - 100.0
    low[5] = 59200.0
    ao = np.zeros(n)
    ao[11:] = 50.0
    macd = np.zeros(n)
    macd[12:] = 20.0
    verde = np.full(n, -5.0)
    verde[10:] = 5.0
    return pd.DataFrame({
        "open": close, "close": close, "high": close + 100.0, "low": low, "volume": 1.0, "bbwp": 60.0,
        "konkorde_marron": 50.0, "konkorde_media": 5.0, "konkorde_verde": verde, "konkorde_azul": 1.0,
        "adx14": 20.0, "plus_di": 20.0, "minus_di": 20.0, "ao": ao, "macd": macd, "macd_signal": 10.0,
        "rsi14": 50.0, "atr14": 500.0, "ml_rsi_regime": "green",
    }, index=index)


def _ctx(freq, n, start, regime="gray"):
    index = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    close = np.full(n, 60000.0)
    return pd.DataFrame({"open": close, "close": close, "high": close + 500, "low": close - 500, "volume": 1.0, "bbwp": 55.0,
                         "konkorde_marron": 50.0, "konkorde_media": 5.0, "konkorde_verde": 10.0, "konkorde_azul": 1.0,
                         "adx14": 25.0, "plus_di": 25.0, "minus_di": 15.0, "ao": 100.0, "macd": 10.0, "macd_signal": 5.0,
                         "atr14": 1500.0, "ml_rsi_regime": regime}, index=index)


def _frames(red_from="2026-01-10T16:00:00Z", n_trigger=N):
    """Frames as the loaders would serve them when the trigger has `n_trigger` closed candles."""
    g = _ctx("4h", 12, "2026-01-09T00:00:00Z")
    regime = pd.Series("gray", index=g.index)
    regime[g.index >= pd.Timestamp(red_from)] = "red"
    g["ml_rsi_regime"] = regime
    d1 = _ctx("D", 12, "2025-12-30T00:00:00Z")
    d1["close"] = np.linspace(50000.0, 62000.0, 12)  # rising: the last closed daily candle is above its EMA -> up
    trig = _trigger_1h().iloc[:n_trigger]
    last_close = trig.index[-1] + pd.Timedelta(hours=1)
    g = g[g.index + pd.Timedelta(hours=4) <= last_close]
    d1 = d1[d1.index + pd.Timedelta(days=1) <= last_close]
    return {"1h": trig, "4h": g, "1d": d1}


def _loaders(frames):
    return {sym: (lambda tf, f=frames: f[tf]) for sym in ("BTC/USDT", "NEAR/USDT")}


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(sh, "enriched_frames", lambda params, loader, **kw: ({tf: loader(tf) for tf in ("1h", "4h", "1d")},
                                                                             {"1h": "ok", "4h": "ok", "1d": "ok"}))


def _run(tmp_path, now, activation="2026-01-10T05:00:00Z", dry_run=False, sent=None, ok=True, frames=None, resume=True):
    sent = [] if sent is None else sent

    def notify(line):
        sent.append(line)
        return ok

    return sh.shadow_run(state_dir=tmp_path, loaders=_loaders(frames or _frames()), now_ms=sh.ms_of(now), dry_run=dry_run,
                         anchor=START, activation=activation, symbols=("BTC/USDT", "NEAR/USDT"), entries=("base",),
                         notify=notify, log=lambda _m: None, warmup=0, resume=resume), sent


def _files(d):
    return tuple((d / name).read_text() if (d / name).exists() else None for name in (sh.EVENTS_FILE, sh.TRADES_FILE, sh.STATE_FILE))


def test_replay_records_enter_and_exit_with_regime_labels(patched, tmp_path):
    summary, sent = _run(tmp_path, "2026-01-11T06:30:00Z")
    events = sh.read_jsonl(tmp_path / sh.EVENTS_FILE)
    trades = sh.read_jsonl(tmp_path / sh.TRADES_FILE)
    enters = [e for e in events if e["action"] == "enter"]
    exits = [e for e in events if e["action"] == "exit"]
    assert len(enters) == 2 and len(exits) == 2 and len(trades) == 2  # one machine per symbol, base run only
    e = next(x for x in enters if x["symbol"] == "NEAR/USDT")
    assert e["side"] == "long" and e["candle_open"] == "2026-01-10T12:00:00+00:00" and e["candle_close"] == "2026-01-10T13:00:00+00:00"
    assert e["regime_own"] == UP and e["regime_btc"] == UP  # both series rise; BTC labels every asset
    assert e["books"] == {"long_only": True, "short_only": False, "regime_own": True, "regime_btc": True, "regime": True}
    assert e["run"] == "snipper:base:spec:cross5" and e["price"] == 61300.0 and e["invalidation"] == 59200.0
    x = next(x for x in exits if x["symbol"] == "NEAR/USDT")
    assert x["candle_close"] == "2026-01-10T20:00:00+00:00" and "exit_ctx_mlrsi_against" in x["reasons"] and x["carried"] is False
    t = next(t for t in trades if t["symbol"] == "NEAR/USDT")
    assert t["entry_time"] == "2026-01-10T12:00:00+00:00" and t["exit_reason"] == "exit_ctx_mlrsi_against"
    assert t["regime_own"] == UP and t["books"]["regime_own"] is True and t["block"] == "out_of_sample"
    assert summary["events_new"] == len(events) and summary["trades_new"] == 2 and summary["ntfy_sent"] == 4
    assert len(sent) == 4 and all(l.startswith("r8 ") for l in sent)
    state = json.loads((tmp_path / sh.STATE_FILE).read_text())
    assert state["counts"] == {"events": len(events), "trades": 2, "runs": 1} and state["ntfy_pending"] == []
    # the machine snapshots land under <state-dir>/cache, one per (entry, symbol), at the candle before the last one
    snaps = sorted((tmp_path / sh.CACHE_DIR).glob("machine_*.json"))
    assert [p.name for p in snaps] == ["machine_base_BTC-USDT.json", "machine_base_NEAR-USDT.json"]
    snap = json.loads(snaps[0].read_text())
    assert snap["bar"] == N - 2 and snap["candle_open"] == "2026-01-11T04:00:00+00:00" and snap["machine"]["pos"] is None


def test_second_run_on_the_same_candle_appends_nothing_and_notifies_nothing(patched, tmp_path):
    _run(tmp_path, "2026-01-11T06:30:00Z")
    before = (tmp_path / sh.EVENTS_FILE).read_text(), (tmp_path / sh.TRADES_FILE).read_text()
    summary, sent = _run(tmp_path, "2026-01-11T06:45:00Z")
    assert summary["events_new"] == 0 and summary["trades_new"] == 0 and sent == []
    assert ((tmp_path / sh.EVENTS_FILE).read_text(), (tmp_path / sh.TRADES_FILE).read_text()) == before
    assert json.loads((tmp_path / sh.STATE_FILE).read_text())["counts"]["runs"] == 2
    assert summary["perf"]["resumed"] == 2 and summary["perf"]["bars_driven"] == 2  # only the last candle is re-driven


def test_resume_from_snapshot_is_byte_identical_to_the_full_replay(patched, tmp_path):
    """Run 1 with 15 closed candles (position OPEN at bar 12, snapshot at bar 13), run 2 with 30:
    the resumed machine + ledger (funding / costs accumulated across the resume, exit at bar 19)
    must leave exactly the files the full replay of both runs leaves."""
    inc, full = tmp_path / "inc", tmp_path / "full"
    s1, _ = _run(inc, "2026-01-10T15:30:00Z", frames=_frames(n_trigger=15))
    snap = json.loads((inc / sh.CACHE_DIR / "machine_base_NEAR-USDT.json").read_text())
    assert snap["bar"] == 13 and snap["machine"]["pos"]["entry_bar"] == 12 and snap["ledger"]["side"] == "long"
    s2, _ = _run(inc, "2026-01-11T06:30:00Z", frames=_frames(n_trigger=30))
    assert s2["perf"]["resumed"] == 2 and s2["perf"]["rebuilt"] == 0 and s2["perf"]["bars_driven"] == 2 * (30 - 14)
    _run(full, "2026-01-10T15:30:00Z", frames=_frames(n_trigger=15), resume=False)
    s2f, _ = _run(full, "2026-01-11T06:30:00Z", frames=_frames(n_trigger=30), resume=False)
    assert s2f["perf"]["resumed"] == 0
    assert _files(inc) == _files(full)
    assert len(sh.read_jsonl(inc / sh.TRADES_FILE)) == 2 and sh.read_jsonl(inc / sh.TRADES_FILE)[0]["exit_reason"] == "exit_ctx_mlrsi_against"


def test_snapshot_is_rejected_when_the_candles_it_was_built_on_change(patched, tmp_path):
    inc, full = tmp_path / "inc", tmp_path / "full"
    _run(inc, "2026-01-10T15:30:00Z", frames=_frames(n_trigger=15))
    changed = _frames(n_trigger=30)
    changed["1h"].iloc[5, changed["1h"].columns.get_loc("low")] = 59100.0  # inside the snapshot's prefix -> new invalidation
    s2, _ = _run(inc, "2026-01-11T06:30:00Z", frames=changed)
    assert s2["perf"]["resumed"] == 0 and s2["perf"]["rebuilt"] == 2
    _run(full, "2026-01-10T15:30:00Z", frames=_frames(n_trigger=15), resume=False)
    _run(full, "2026-01-11T06:30:00Z", frames=changed, resume=False)
    assert _files(inc) == _files(full)
    # the rebuilt snapshot carries the changed candle: the new invalidation shows in the state, the recorded enter stays
    snap = json.loads((inc / sh.CACHE_DIR / "machine_base_NEAR-USDT.json").read_text())
    assert snap["bar"] == 28 and snap["trigger_sha"] == sh.frame_prefix_sha(changed["1h"], 29)


def test_activation_cut_excludes_earlier_decisions_and_flags_carried_exits(patched, tmp_path):
    # activation after the entry (13:00Z) but before the exit (20:00Z): no enter, the exit is `carried`, no trade
    summary, sent = _run(tmp_path, "2026-01-11T06:30:00Z", activation="2026-01-10T15:00:00Z")
    events = sh.read_jsonl(tmp_path / sh.EVENTS_FILE)
    assert not [e for e in events if e["action"] == "enter"]
    assert all(e["carried"] for e in events if e["action"] == "exit") and sh.read_jsonl(tmp_path / sh.TRADES_FILE) == []
    assert all(" carried " in l for l in sent)


def test_carried_flag_survives_a_resume(patched, tmp_path):
    inc, full = tmp_path / "inc", tmp_path / "full"
    kw = {"activation": "2026-01-10T15:00:00Z"}
    _run(inc, "2026-01-10T15:30:00Z", frames=_frames(n_trigger=15), **kw)
    _run(inc, "2026-01-11T06:30:00Z", frames=_frames(n_trigger=30), **kw)
    _run(full, "2026-01-11T06:30:00Z", frames=_frames(n_trigger=30), resume=False, **kw)
    inc_events, full_events = sh.read_jsonl(inc / sh.EVENTS_FILE), sh.read_jsonl(full / sh.EVENTS_FILE)
    assert [e["key"] for e in inc_events] == [e["key"] for e in full_events] and all(e["carried"] for e in inc_events)


def test_dry_run_writes_nothing_and_does_not_notify(patched, tmp_path):
    summary, sent = _run(tmp_path, "2026-01-11T06:30:00Z", dry_run=True)
    assert summary["dry_run"] and summary["events_new"] > 0 and sent == []
    assert not (tmp_path / sh.EVENTS_FILE).exists() and not (tmp_path / sh.STATE_FILE).exists()
    assert not (tmp_path / sh.CACHE_DIR).exists()


def test_failed_notifications_are_kept_pending_and_retried(patched, tmp_path):
    summary, sent = _run(tmp_path, "2026-01-11T06:30:00Z", ok=False)
    assert summary["ntfy_failed"] == 4 and json.loads((tmp_path / sh.STATE_FILE).read_text())["ntfy_pending"] == sent
    summary2, sent2 = _run(tmp_path, "2026-01-11T07:30:00Z", ok=True)
    assert sent2 == sent and summary2["ntfy_sent"] == 4 and json.loads((tmp_path / sh.STATE_FILE).read_text())["ntfy_pending"] == []


def test_ntfy_line_format_and_no_topic_leak():
    ev = {"run": "snipper:adx_turn:spec:cross5", "symbol": "NEAR/USDT", "action": "enter", "side": "short",
          "candle_close": "2026-11-01T18:00:00+00:00", "price": 2.3456, "invalidation": 2.5, "regime_own": DOWN, "regime_btc": UP,
          "books": {"long_only": False, "short_only": True, "regime_own": True, "regime_btc": False}}
    line = sh.ntfy_line(ev)
    assert line == "r8 ENTER SHORT NEAR/USDT adx_turn 1h@2026-11-01T18:00Z px 2.3456 inv 2.5 reg own=down btc=up books=short_only,regime_own"
    ex = {**ev, "action": "exit", "reasons": ["hold", "exit_invalidation"], "carried": False}
    tr = {"r_net": -1.0, "pnl_net_usdt": -33.5, "regime_own": DOWN, "regime_btc": UP}
    assert sh.ntfy_line(ex, tr) == "r8 EXIT SHORT NEAR/USDT adx_turn 1h@2026-11-01T18:00Z px 2.3456 -1.00R -33.50 USDT (exit_invalidation) reg own=down btc=up"
    assert "ntfy" not in line and "topic" not in line


def test_ntfy_send_posts_to_base_topic_and_is_false_without_topic(monkeypatch):
    calls = []

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def opener(req, timeout):
        calls.append((req.full_url, req.data, req.get_method()))
        return Resp()

    assert sh.ntfy_send("hello", base="https://ntfy.example/", topic="t-123", opener=opener) is True
    assert calls == [("https://ntfy.example/t-123", b"hello", "POST")]
    assert sh.ntfy_send("hello", base="https://ntfy.example", topic="", opener=opener) is False and len(calls) == 1


def test_merge_rows_is_a_union_where_fresh_wins():
    cached = [[1, 1, 1, 1, 1, 1], [2, 2, 2, 2, 2, 2]]
    fresh = [[2, 9, 9, 9, 9, 9], [3, 3, 3, 3, 3, 3]]
    assert sh.merge_rows(cached, fresh) == [[1, 1, 1, 1, 1, 1], [2, 9, 9, 9, 9, 9], [3, 3, 3, 3, 3, 3]]


def test_load_incremental_extends_the_cache_from_its_last_row(tmp_path):
    hour = sh.TIMEFRAME_MS["1h"]
    t0 = 1_700_000_000_000 - (1_700_000_000_000 % hour)
    served = {t0 + i * hour: [t0 + i * hour, 1.0, 2.0, 0.5, 1.5, 10.0] for i in range(10)}
    asked = []

    def fetch(symbol, timeframe, since, limit):
        asked.append(since)
        return [r for ts, r in sorted(served.items()) if ts >= since][:limit]

    end = t0 + 6 * hour
    df, info = sh.load_incremental("BTC/USDT", "1h", since_ms=t0, end_ms=end, cache_dir=tmp_path, fetch=fetch, now_ms=end)
    assert info == {"rows": 6, "fetched": 6, "last_open": sh.iso(t0 + 5 * hour)} and asked == [t0]
    # one hour later: only the new candle is fetched, from the last cached open + 1h
    df2, info2 = sh.load_incremental("BTC/USDT", "1h", since_ms=t0, end_ms=end + hour, cache_dir=tmp_path, fetch=fetch, now_ms=end + hour)
    assert info2["rows"] == 7 and info2["fetched"] == 1 and asked[-1] == t0 + 6 * hour
    assert list(df2["timestamp"]) == [t0 + i * hour for i in range(7)]
    # the forming candle (closes after now) is never kept — and not even fetched
    df3, _ = sh.load_incremental("BTC/USDT", "1h", since_ms=t0, end_ms=end + 2 * hour, cache_dir=tmp_path, fetch=fetch, now_ms=end + hour + 1)
    assert len(df3) == 7 and len(asked) == 2
    # the same closed window again: nothing fetched, the file is not rewritten
    stamp = sh.cache_path(tmp_path, "BTC/USDT", "1h").stat().st_mtime_ns
    df4, info4 = sh.load_incremental("BTC/USDT", "1h", since_ms=t0, end_ms=end + hour, cache_dir=tmp_path, fetch=fetch, now_ms=end + hour)
    assert len(df4) == 7 and info4["fetched"] == 0 and len(asked) == 2 and sh.cache_path(tmp_path, "BTC/USDT", "1h").stat().st_mtime_ns == stamp


def _random_ohlcv(n=600, seed=7):
    rng = np.random.default_rng(seed)
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    high = close * (1.0 + rng.uniform(0.0, 0.01, n))
    low = close * (1.0 - rng.uniform(0.0, 0.01, n))
    open_ = np.r_[close[0], close[:-1]]
    index = pd.date_range("2025-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"timestamp": (index.asi8 // 1_000_000).astype("int64"), "open": open_, "high": high, "low": low,
                         "close": close, "volume": rng.uniform(10.0, 100.0, n)}, index=index)


def _same_column(a: pd.Series, b: pd.Series) -> bool:
    if a.dtype == object or b.dtype == object:
        return a.tolist() == b.tolist()
    return np.array_equal(a.to_numpy(dtype=float), b.to_numpy(dtype=float), equal_nan=True)


def test_calculate_impulse_columns_are_identical_to_calculate_all():
    df = _random_ohlcv()
    impulse = IndicatorsService(df, bbwp_definition="tv")
    impulse.calculate_impulse()
    full = IndicatorsService(df, bbwp_definition="tv")
    full.calculate_all()
    needed = ("rsi14", "adx14", "plus_di", "minus_di", "bbwp", "ao", "konkorde_verde", "konkorde_media", "konkorde_azul",
              "konkorde_marron", "macd", "macd_signal", "atr14", "ml_rsi_regime", "ml_rsi", "ml_rsi_upper", "ml_rsi_lower")
    for col in needed:
        assert col in impulse.df.columns, col
    for col in impulse.df.columns:
        assert _same_column(impulse.df[col], full.df[col]), col
    assert "bbwp_legacy" not in impulse.df.columns and "tsa_trend_speed" not in impulse.df.columns
    with pytest.raises(ValueError):
        IndicatorsService(df, bbwp_definition="legacy").calculate_impulse()


def test_ml_rsi_cached_is_identical_to_ml_rsi_frame_and_only_extends(tmp_path, monkeypatch):
    close = _random_ohlcv(400)["close"]
    p = MlRsiParams(max_points=50)
    path = tmp_path / "mlrsi.npz"
    want = ml_rsi_frame(close, p, mode="causal")

    def same(frame):
        return all(_same_column(frame[c], want[c]) for c in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower", "ml_rsi_regime"))

    # cold: no cache -> full compute, cache written
    assert same(sh.ml_rsi_cached(close, path, p, write=True)) and path.exists()
    # a prefix cache (300 rows) must only compute the 100 new thresholds, with the same numbers
    sh.ml_rsi_cached(close.iloc[:300], path, p, write=True)
    calls = []
    real = sh.thresholds
    monkeypatch.setattr(sh, "thresholds", lambda w, pp: (calls.append(len(w)), real(w, pp))[1])
    assert same(sh.ml_rsi_cached(close, path, p, write=True)) and len(calls) == 100
    # a changed candle inside the cached prefix invalidates it: everything is recomputed
    calls.clear()
    bumped = close.copy()
    bumped.iloc[10] *= 1.05
    out = sh.ml_rsi_cached(bumped, path, p, write=False)
    assert len(calls) == 400
    assert all(_same_column(out[c], ml_rsi_frame(bumped, p, mode="causal")[c]) for c in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower", "ml_rsi_regime"))
    # the ML RSI columns served from the cache are exactly what `_calc_ml_rsi` puts on the frame
    df = _random_ohlcv(400)
    via_cache = sh.enrich_impulse(df, mlrsi_cache=tmp_path / "x.npz", write=True)
    direct = sh.enrich_impulse(df)
    for col in ("ml_rsi", "ml_rsi_upper", "ml_rsi_lower", "ml_rsi_regime"):
        assert _same_column(via_cache[col], direct[col]), col


def test_floor_hour_and_report_closure(patched, tmp_path):
    assert sh.floor_hour_ms(sh.ms_of("2026-11-01T17:59:59Z")) == sh.ms_of("2026-11-01T17:00:00Z")
    _run(tmp_path, "2026-01-11T06:30:00Z")
    rep = sh.shadow_report(tmp_path, now_ms=sh.ms_of("2026-01-12T05:00:00Z"))
    base = rep["runs"]["snipper:base:spec:cross5"]
    assert base["signals"]["long"] == {"n": 2, "own_up": 2, "own_down": 0, "btc_up": 2, "btc_down": 0}
    assert base["books"]["long_only"]["n"] == 2 and base["books"]["short_only"]["n"] == 0 and base["books"]["regime_own"]["n"] == 2
    assert rep["closure"]["closed"] is False and rep["days_elapsed"] == 2.0  # activation 10th 05:00Z -> 12th 05:00Z
    md = sh.report_markdown(rep)
    assert "| snipper:base:spec:cross5 | long | 2 | 2 | 0 | 2 | 0 |" in md
