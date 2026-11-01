"""Impulse engine v2 (impulsos-v2) — offline, synthetic indicator columns.

Spec: docs/impulsos-v2.md. The analyst's numeric goldens live in
`test_impulse_golden.py`; this file covers the engine mechanics: profiles,
replay state machine, no-lookahead, multi-TF alignment, speed, the column
contract with `IndicatorsService` and the HTTP surface.
"""

import time

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.metrics import impulse_service
from controllers.metrics.impulse_service import (
    RULE_VERSION,
    ImpulseEngine,
    ImpulseEvaluationService,
    ImpulseParams,
)
from controllers.metrics.trade_profiles import TRADE_PROFILES, profile_timeframes

API_KEY = "test-key"
FREQ = {"15m": "15min", "1h": "h", "4h": "4h", "1d": "D", "1w": "7D"}
DECISION_KEYS = {
    "timestamp", "timeframe", "trigger_tf", "candle_close", "profile", "side",
    "phase", "action", "reasons", "confidence", "side_score", "context_bias",
    "stop_price", "exit_price", "context", "rule_version",
}


# ---------------------------------------------------------------------------
# Synthetic frames
# ---------------------------------------------------------------------------

def _frame(tf: str, n: int, start: str, side: str = "long", **cols) -> pd.DataFrame:
    """Indicator-only frame whose every side component votes `side`."""
    index = pd.date_range(start, periods=n, freq=FREQ[tf], tz="UTC")
    sign = 1.0 if side == "long" else -1.0
    base = {
        "close": 100.0 + sign * np.linspace(0.0, 20.0, n),
        "konkorde_marron": 50.0 + sign * np.linspace(2.0, 10.0, n),  # edge rising away from 0
        "konkorde_media": 50.0,
        "konkorde_azul": sign * 1.0,
        "ao": sign * np.linspace(0.5, 2.0, n),
        "plus_di": 28.0 if side == "long" else 15.0,
        "minus_di": 15.0 if side == "long" else 28.0,
        "macd": sign * 1.0, "macd_signal": sign * 0.5,
        "bbwp": 35.0,
        "adx14": np.linspace(10.0, 45.0, n),  # ~0.6 pts/bar: "ADX rising"
        "atr14": 2.0,
    }
    base.update(cols)
    if "konkorde_verde" not in cols:
        # 2.1.0 zero line: same shape as the 2.0.0 edge (marron - media).
        base["konkorde_verde"] = np.asarray(base["konkorde_marron"], dtype=float) - np.asarray(
            base["konkorde_media"], dtype=float)
    return pd.DataFrame(base, index=index)


def _breakout_tail(n: int) -> np.ndarray:
    bbwp = np.full(n, 35.0)
    bbwp[-6:] = [15.0, 15.0, 15.0, 25.0, 40.0, 55.0]
    return bbwp


def _pro_frames(trigger_side="long", d1_side="long", w1_side="long", **trigger_cols):
    n = 60
    cols = {"bbwp": _breakout_tail(n)}
    cols.update(trigger_cols)
    return {
        # last 4h candle opens 2026-03-01 20:00, closes 2026-03-02 00:00 UTC
        "4h": _frame("4h", n, "2026-02-20", trigger_side, **cols),
        "1d": _frame("1d", 60, "2026-01-01", d1_side),
        "1w": _frame("1w", 30, "2025-10-13", w1_side),
    }


def _pro() -> ImpulseEngine:
    return ImpulseEngine(ImpulseParams.for_profile("pro"))


# ---------------------------------------------------------------------------
# Profiles + params
# ---------------------------------------------------------------------------

def test_trade_profiles_contract():
    assert set(TRADE_PROFILES) == {"scalper", "snipper", "pro", "ancient"}
    assert TRADE_PROFILES["pro"]["max_leverage"] == 5.0
    assert TRADE_PROFILES["snipper"]["max_leverage"] == 10.0
    assert TRADE_PROFILES["ancient"]["default_leverage"] == 1.0
    assert all(p["r_target"] is None for p in TRADE_PROFILES.values())
    assert all(p["confirm_tf"] == p["context_tfs"][0] for p in TRADE_PROFILES.values())
    assert profile_timeframes("pro") == ("4h", "1d", "1w")
    assert profile_timeframes("scalper") == ("15m", "1h", "4h")


def test_params_for_profile_and_validation():
    params = ImpulseParams.for_profile("snipper")
    assert (params.trigger_tf, params.confirm_tf) == ("1h", "4h")
    assert params.context_order() == ("4h", "1d")
    assert params.atr_mult_stop == 1.5 and params.time_stop_bars == 48
    assert params.rule_version == RULE_VERSION == "impulse-2.1.0"
    assert params.konkorde_line == "verde"
    assert ImpulseParams(konkorde_line="edge").konkorde_line == "edge"
    with pytest.raises(ValueError):
        ImpulseParams(konkorde_line="marron")
    with pytest.raises(ValueError):
        ImpulseParams.for_profile("whale")
    spec_named = ImpulseParams.from_mapping({"profile": "pro", "compression_max": 25, "red_drop_min": 9})
    assert spec_named.bbwp_compression_max == 25 and spec_named.bbwp_exit_drop_pts == 9


# ---------------------------------------------------------------------------
# Entry / exit mechanics not covered by the goldens
# ---------------------------------------------------------------------------

def test_enter_long_returns_full_decision_shape():
    decision = _pro().evaluate(_pro_frames())
    body = decision.to_dict()
    assert set(body) == DECISION_KEYS
    assert (decision.action, decision.side, decision.phase) == ("enter", "long", "ignition")
    assert decision.stop_price == pytest.approx(120.0 - 1.5 * 2.0)
    assert decision.timestamp == int(pd.Timestamp("2026-03-01 20:00", tz="UTC").value // 10**6)
    assert body["candle_close"].startswith("2026-03-02T00:00:00")
    assert decision.context_bias == {"1d": 1, "1w": 1}


def test_enter_short_mirror():
    decision = _pro().evaluate(_pro_frames("short", "short", "short"))
    assert (decision.action, decision.side) == ("enter", "short")
    assert decision.stop_price == pytest.approx(80.0 + 1.5 * 2.0)


def test_guardian_missing_blocks_entry():
    frames = _pro_frames()
    del frames["1d"]
    decision = _pro().evaluate(frames)
    assert decision.action == "none" and "context_missing" in decision.reasons


def test_only_guardian_blocks():
    assert _pro().evaluate(_pro_frames(w1_side="short")).action == "enter"
    assert "context_against" in _pro().evaluate(_pro_frames(d1_side="short")).reasons


def test_low_band_trigger_ignores_konkorde():
    n = 60
    frames = {
        "15m": _frame("15m", n, "2026-03-01", "long", bbwp=_breakout_tail(n), konkorde_marron=40.0),
        "1h": _frame("1h", 30, "2026-02-28", "long"),
    }
    decision = ImpulseEngine(ImpulseParams.for_profile("scalper")).evaluate(frames)
    assert decision.context["votes"]["konkorde"] is None
    assert "band_konkorde_excluded" in decision.reasons
    assert (decision.action, decision.side) == ("enter", "long")


def test_stop_gap_fills_at_open():
    n = 10
    frames = {"4h": _frame("4h", n, "2026-02-20", "long", bbwp=60.0,
                           open=np.full(n, 110.0), low=np.full(n, 109.0), high=np.full(n, 121.0))}
    frames["4h"].iloc[-1, frames["4h"].columns.get_loc("open")] = 95.0
    frames["4h"].iloc[-1, frames["4h"].columns.get_loc("low")] = 94.0
    decision = _pro().evaluate(frames, position="long", entry_price=104.0, stop_price=101.0)
    assert decision.action == "exit" and decision.reasons == ["exit_stop_atr"]
    assert decision.exit_price == 95.0


def test_invalid_position_is_rejected():
    with pytest.raises(ValueError):
        _pro().evaluate(_pro_frames(), position="sideways")


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------

def _replay_frame() -> pd.DataFrame:
    n = 80
    bbwp = np.full(n, 35.0)
    bbwp[51:58] = 15.0
    bbwp[58:61] = [25.0, 40.0, 55.0]
    bbwp[61:74] = np.linspace(58.0, 82.0, 13)
    bbwp[74:] = [85.0, 93.0, 84.0, 80.0, 78.0, 76.0]
    marron = 50.0 + np.linspace(2.0, 10.0, n)
    marron[76:] = [52.0, 47.0, 46.0, 46.0]  # edge +2 at bar 76, -3 at bar 77
    return _frame("4h", n, "2026-01-01", "long", bbwp=bbwp, konkorde_marron=marron)


def test_replay_enters_then_exits_on_owner_rule():
    frames = {"4h": _replay_frame(), "1d": _frame("1d", 60, "2025-11-15", "long")}
    decisions = _pro().replay(frames, warmup=20)
    actions = {i + 20: d.action for i, d in enumerate(decisions)}
    assert actions[60] == "enter"
    assert all(actions[i] == "hold" for i in range(61, 77))
    assert actions[77] == "exit"
    assert {"exit_rule_jeisson", "exit_bbwp_red_drop"} <= set(decisions[77 - 20].reasons)
    assert decisions[70 - 20].context["bars_held"] == 10
    assert list(actions.values()).count("enter") == 1


def test_zero_line_is_verde_by_default_and_names_reasons():
    n = 60
    # verde crosses 0 two bars ago and keeps rising; marron - media stays negative.
    verde = np.linspace(-20.0, -1.0, n)
    verde[-3:] = [-1.0, 4.0, 9.0]
    frames = _pro_frames(konkorde_verde=verde, konkorde_marron=np.linspace(45.0, 40.0, n))
    decision = _pro().evaluate(frames)
    assert (decision.action, decision.side) == ("enter", "long")
    assert {"konkorde_verde_positive", "konkorde_verde_cross_up"} <= set(decision.reasons)
    assert not any(r.startswith("konkorde_edge_") for r in decision.reasons)
    assert decision.context["konkorde_line"] == "verde"
    assert decision.context["values"]["edge"] == pytest.approx(9.0)

    # Same frames on the 2.0.0 line: edge = marron - 50 < 0 and falling votes against the long.
    edge = ImpulseEngine(ImpulseParams.for_profile("pro", konkorde_line="edge")).evaluate(frames)
    assert edge.action == "none" and edge.context["votes"]["konkorde"] == -1
    assert edge.context["konkorde_line"] == "edge"


def test_owner_exit_reason_names_follow_the_zero_line():
    frames = {"4h": _replay_frame(), "1d": _frame("1d", 60, "2025-11-15", "long")}
    decisions = _pro().replay(frames, warmup=20)
    exit_reasons = decisions[77 - 20].reasons
    assert "exit_konkorde_cross_against" in exit_reasons  # unchanged across lines
    hold_76 = decisions[76 - 20].reasons
    assert not any(r.startswith("konkorde_edge_") for r in hold_76)


def _random_frames(n_trigger: int, seed: int = 7):
    rng = np.random.default_rng(seed)

    def series(tf, n, start):
        index = pd.date_range(start, periods=n, freq=FREQ[tf], tz="UTC")
        walk = lambda scale: np.cumsum(rng.normal(0, scale, n))  # noqa: E731
        close = 100.0 + walk(1.0)
        return pd.DataFrame(
            {
                "close": close, "high": close + 0.5, "low": close - 0.5,
                "bbwp": np.clip(50.0 + walk(6.0), 0.0, 100.0),
                "konkorde_marron": 50.0 + walk(2.0),
                "konkorde_media": 50.0 + walk(1.0),
                "konkorde_verde": 55.0 + walk(2.0),
                "konkorde_azul": walk(1.0),
                "adx14": np.clip(25.0 + walk(1.0), 5.0, 60.0),
                "plus_di": np.clip(20.0 + walk(1.0), 1.0, 60.0),
                "minus_di": np.clip(20.0 + walk(1.0), 1.0, 60.0),
                "ao": walk(0.5),
                "macd": walk(0.3),
                "macd_signal": walk(0.3),
                "atr14": 2.0,
            },
            index=index,
        )

    days = n_trigger * 4 // 24 + 2
    return {
        "4h": series("4h", n_trigger, "2025-01-01"),
        "1d": series("1d", days, "2025-01-01"),
        "1w": series("1w", days // 7 + 2, "2024-12-30"),
    }


def test_replay_has_no_lookahead():
    full = _random_frames(400)
    cut = full["4h"].index[299] + pd.Timedelta(hours=4)  # close of trigger row 299
    truncated = {tf: df[df.index < cut] for tf, df in full.items()}
    engine = _pro()
    past = [d.to_dict() for d in engine.replay(truncated, warmup=50)]
    whole = [d.to_dict() for d in engine.replay(full, warmup=50)]
    assert len(past) == 250
    assert whole[: len(past)] == past


def test_evaluate_cuts_context_after_trigger_close():
    frames = _random_frames(120)
    trigger = frames["4h"].iloc[:100]
    decision = _pro().evaluate({**frames, "4h": trigger})
    trigger_close = trigger.index[-1] + pd.Timedelta(hours=4)
    for tf, duration in (("1d", pd.Timedelta(days=1)), ("1w", pd.Timedelta(days=7))):
        info = decision.context["timeframes"][tf]
        if info["available"]:
            assert pd.Timestamp(info["candle_ts"], unit="ms", tz="UTC") + duration <= trigger_close


def test_replay_speed_on_long_history():
    frames = _random_frames(17_500)
    started = time.perf_counter()
    decisions = _pro().replay(frames, warmup=300)
    assert len(decisions) == 17_200
    assert time.perf_counter() - started < 60.0


# ---------------------------------------------------------------------------
# Real indicator columns (pins the column contract with IndicatorsService)
# ---------------------------------------------------------------------------

def test_engine_runs_on_indicators_service_columns():
    from controllers.metrics.indicators_service import IndicatorsService

    rng = np.random.default_rng(11)
    n = 500
    close = 100.0 + np.cumsum(rng.normal(0, 1.0, n))
    index = pd.date_range("2025-01-01", periods=n, freq="4h", tz="UTC")
    raw = pd.DataFrame(
        {
            "timestamp": (index.asi8 // 10**6).astype("int64"),
            "open": close, "high": close + 1.0, "low": close - 1.0,
            "close": close, "volume": rng.uniform(100, 1000, n),
        },
        index=index,
    )
    service = IndicatorsService(raw, bbwp_definition="tv")
    service.calculate_all()
    for column in impulse_service.INDICATOR_COLUMNS:
        assert column in service.df.columns, column
    decision = _pro().evaluate({"4h": service.df})
    assert decision.action == "none"  # guardian frame absent -> never enters
    assert decision.context["values"]["bbwp"] is not None


# ---------------------------------------------------------------------------
# HTTP: /v1/impulse/evaluate and the opt-in `impulse` key on /v1/metrics/get
# ---------------------------------------------------------------------------

def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("API_KEYS", API_KEY)
    from routes import routes

    app = FastAPI(title="impulse-test")
    app.include_router(routes)
    return TestClient(app)


def test_impulse_endpoint_with_patched_market_data(monkeypatch):
    frames = _pro_frames()
    monkeypatch.setattr(ImpulseEvaluationService, "_enriched_frame", lambda self, tf: frames[tf])
    client = _client(monkeypatch)

    assert client.get("/v1/impulse/evaluate", params={"symbol": "BTC/USDT"}).status_code == 401

    response = client.get(
        "/v1/impulse/evaluate",
        params={"symbol": "BTC/USDT", "profile": "pro"},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200
    body = response.json()
    assert DECISION_KEYS <= set(body)
    assert body["action"] == "enter" and body["side"] == "long"
    assert body["profile"] == "pro" and body["rule_version"] == RULE_VERSION
    assert body["tf_status"] == {"4h": "ok", "1d": "ok", "1w": "ok"}
    assert body["trade_profile"]["max_leverage"] == 5.0

    held = client.get(
        "/v1/impulse/evaluate",
        params={"symbol": "BTC/USDT", "position": "long", "entry_price": 110, "stop_price": 100, "bars_held": 2},
        headers={"X-API-Key": API_KEY},
    ).json()
    assert held["action"] == "hold" and held["side"] == "long"

    bad = client.get(
        "/v1/impulse/evaluate",
        params={"symbol": "BTC/USDT", "profile": "whale"},
        headers={"X-API-Key": API_KEY},
    )
    assert bad.status_code == 400


def test_impulse_endpoint_degrades_failed_context_tf(monkeypatch):
    frames = _pro_frames()

    def loader(self, tf):
        if tf == "1w":
            raise RuntimeError("no history")
        return frames[tf]

    monkeypatch.setattr(ImpulseEvaluationService, "_enriched_frame", loader)
    body = ImpulseEvaluationService(symbol="BTC/USDT", profile="pro").evaluate()
    assert body["tf_status"]["1w"] == "failed:RuntimeError"
    assert body["context_bias"]["1w"] is None
    assert body["action"] == "enter"


LEGACY_METRICS_KEYS = {"exchange", "symbol", "timeframe", "timestamp", "indicators", "signals"}


def _patch_metrics_pipeline(monkeypatch):
    from controllers.metrics import metrics_controller

    class FakeMarket:
        def __init__(self, *args, **kwargs):
            pass

        def get_ohlcv(self, **kwargs):
            return pd.DataFrame({"close": [1.0, 2.0]})

    class FakeIndicators:
        def __init__(self, *args, **kwargs):
            pass

        def calculate_all(self):
            return {"rsi14": 50.0}

    class FakeRules:
        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, indicators):
            return {"signal": "neutral"}

    monkeypatch.setattr(metrics_controller, "MarketDataService", FakeMarket)
    monkeypatch.setattr(metrics_controller, "IndicatorsService", FakeIndicators)
    monkeypatch.setattr(metrics_controller, "RulesService", FakeRules)


def test_metrics_get_payload_unchanged_without_impulse_profile(monkeypatch):
    _patch_metrics_pipeline(monkeypatch)

    def _must_not_run(self, **kwargs):
        raise AssertionError("impulse engine must not run without impulse_profile")

    monkeypatch.setattr(ImpulseEvaluationService, "__init__", _must_not_run)
    client = _client(monkeypatch)
    response = client.get(
        "/v1/metrics/get", params={"symbol": "BTC/USDT"}, headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 200
    assert set(response.json()) == LEGACY_METRICS_KEYS


def test_metrics_get_adds_impulse_key_on_request(monkeypatch):
    _patch_metrics_pipeline(monkeypatch)
    monkeypatch.setattr(ImpulseEvaluationService, "evaluate", lambda self: {"action": "none", "profile": self.profile})
    client = _client(monkeypatch)
    response = client.get(
        "/v1/metrics/get",
        params={"symbol": "BTC/USDT", "impulse_profile": "snipper"},
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == LEGACY_METRICS_KEYS | {"impulse"}
    assert body["impulse"] == {"action": "none", "profile": "snipper"}
