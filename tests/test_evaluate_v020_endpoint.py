"""GET /v1/setups/evaluate under rule_version 0.2.0 (spec §I) — HTTP contract.

Same technique as test_setups_evaluate_endpoint.py: `_enriched_frame` is
monkeypatched with deterministic frames, no network. One coherent engineered
market exercises every v0.2.0 block at once:

* 4h  — M11-G1 color flip -> FALSE_ENTRY_CONFIRMED (p_false 0.80)
* 30m — fresh AO cross + E1 turn -> M1 CONFIRMED (the H1 Rule-1 source)
* 15m — M1m ignition timeout, overridden by the 30m -> CONFIRMED_BY_HIGHER_TF
* 1h  — FALSE_ENTRY_PROBABLE + contrary AO re-cross with bearish DI -> M2
* 1d  — VT-G1 rounded BBWP dome with bearish DI -> vol_turn_rounded
* 1w  — benign
"""

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.metrics.setup_evaluation_service import SetupEvaluationService

API_KEY = "test-key"

V2_MONITOR_BLOCKS = {
    "false_entry_watch", "tf_status", "false_ignition_watch",
    "contrary_impulse", "confluence", "vol_turn_rounded",
}
V2_FE_KEYS = {
    "timeframe", "direction", "state", "early_warning", "event_age",
    "consecutive_ao_candles", "adx_turn", "p_false", "cross_candle_ts",
    "color_flip_age", "p_false_boosts", "higher_tf", "ignition_from_below",
}
V2_FE_STATES = {
    "WATCHING", "CONFIRMED", "FALSE_ENTRY_PROBABLE", "WHIPSAW",
    "FALSE_ENTRY_CONFIRMED", "CONFIRMED_BY_HIGHER_TF",
}
V2_TFS = ("15m", "30m", "1h", "4h", "1d", "1w")

_FREQ = {"15m": "15min", "30m": "30min", "1h": "1h", "4h": "4h", "1d": "D", "1w": "7D"}
_START = {
    "15m": "2026-02-27", "30m": "2026-02-27", "1h": "2026-02-27",
    "4h": "2026-02-20", "1d": "2026-01-01", "1w": "2025-06-01",
}


def _frame(tf, n=60, *, ao=1.0, adx=20.0, plus=25.0, minus=15.0, bbwp=40.0,
           konkorde=5.0):
    index = pd.date_range(_START[tf], periods=n, freq=_FREQ[tf], tz="UTC")

    def col(value):
        if np.isscalar(value):
            return np.full(n, float(value))
        value = np.asarray(value, dtype=float)
        arr = np.full(n, value[0])
        arr[-len(value):] = value
        return arr

    return pd.DataFrame(
        {
            "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
            "volume": 1000.0,
            "sma200": 90.0, "sma50": 95.0, "ema50": 96.0, "ema200": 92.0,
            "adx14": col(adx), "plus_di": col(plus), "minus_di": col(minus),
            "ao": col(ao), "bbwp": col(bbwp), "atr14": 2.0,
            "konkorde_marron": col(konkorde),
        },
        index=index,
    )


def _market_frames():
    m1m_adx_t0_at_8 = np.array(
        [15.8, 15.9, 16.0, 16.1, 16.2, 16.3, 17.5, 19.2, 21.5,
         22.0, 22.3, 22.5, 22.6, 22.7, 22.8, 22.9, 23.0]
    )
    bbwp_alternating = np.where(np.arange(60) % 2 == 0, 31.0, 30.0)
    return {
        # M1m FALSE_IGNITION_PROBABLE up (t0 age 8, no body) — H1 override target.
        "15m": _frame("15m", ao=-1.1, adx=m1m_adx_t0_at_8, plus=28.0, minus=15.0,
                      bbwp=bbwp_alternating),
        # M1 CONFIRMED up: fresh cross (age 2) + E1-G1 turn on the last candle.
        "30m": _frame("30m", ao=np.array([-1.0, 0.5, 0.9, 1.4]),
                      adx=np.array([18, 18, 18, 18, 18, 18, 18.5, 21.5, 24.5]),
                      plus=28.0, minus=15.0, bbwp=60.0),
        # FALSE_ENTRY_PROBABLE up (age 5, flat ADX) + contrary re-cross at age 0
        # with the DI color already bearish -> M2 trigger (c).
        "1h": _frame("1h", ao=np.array([-0.5, 0.4, 0.8, 1.1, 1.3, 1.6, -0.2]),
                     plus=np.array([28, 28, 28, 28, 28, 28, 15]),
                     minus=np.array([15, 15, 15, 15, 15, 15, 28]),
                     bbwp=60.0),
        # M11-G1 color flip: aligned DI at t0, flips bearish at post-cross age 2.
        "4h": _frame("4h", ao=np.array([-0.5, 0.4, 0.9, 0.7]),
                     plus=np.array([26, 27, 24, 19]),
                     minus=np.array([16, 17, 22, 25]),
                     bbwp=60.0, konkorde=-0.5),
        # VT-G1 rounded dome during a bearish 1d move -> vol_turn_rounded "v".
        "1d": _frame("1d", ao=1.0,
                     bbwp=np.array([60, 68, 75, 82, 88, 90, 88, 85, 81, 72]),
                     plus=15.0, minus=28.0),
        "1w": _frame("1w"),
    }


def _client(monkeypatch, frames):
    monkeypatch.setenv("API_KEYS", API_KEY)
    monkeypatch.setattr(
        SetupEvaluationService,
        "_enriched_frame",
        lambda self, timeframe: frames[timeframe],
    )
    from routes import routes

    app = FastAPI(title="setups-evaluate-v020-test")
    app.include_router(routes)
    return TestClient(app)


def _get(client, **params):
    return client.get(
        "/v1/setups/evaluate",
        params={"symbol": "BTC/USDT", **params},
        headers={"X-API-Key": API_KEY},
    )


def _fe(body):
    return {(m["timeframe"], m["direction"]): m for m in body["monitors"]["false_entry_watch"]}


def _fi(body):
    return {(m["timeframe"], m["direction"]): m for m in body["monitors"]["false_ignition_watch"]}


# ---------------------------------------------------------------------------
# Contract shape under 0.2.0
# ---------------------------------------------------------------------------

def test_v020_contract_shape(monkeypatch):
    monkeypatch.setenv("RULE_VERSION", "0.2.0")
    client = _client(monkeypatch, _market_frames())
    body = _get(client).json()

    assert set(body.keys()) == {"symbol", "rule_version", "evaluated_at", "setups", "monitors"}
    assert body["rule_version"] == "0.2.0"
    # The setups contract is UNCHANGED (still the four 0.1.0 documents).
    assert [s["setup_id"] for s in body["setups"]] == [
        "PB-1D-LONG", "PB-1D-SHORT", "IMP-4H-LONG", "IMP-4H-SHORT",
    ]
    assert set(body["monitors"].keys()) == V2_MONITOR_BLOCKS
    # 15m formally joins the operative set (6 TFs).
    assert set(body["monitors"]["tf_status"].keys()) == set(V2_TFS)
    assert all(v == "ok" for v in body["monitors"]["tf_status"].values())
    for entry in body["monitors"]["false_entry_watch"]:
        assert set(entry.keys()) == V2_FE_KEYS
        assert entry["state"] in V2_FE_STATES
        assert pd.Timestamp(entry["cross_candle_ts"]).tzinfo is not None


def test_v020_color_flip_adjudicates_on_4h(monkeypatch):
    monkeypatch.setenv("RULE_VERSION", "0.2.0")
    client = _client(monkeypatch, _market_frames())
    watch = _fe(_get(client).json())[("4h", "up")]

    assert watch["state"] == "FALSE_ENTRY_CONFIRMED"
    assert watch["p_false"] == 0.70  # measured prior (replay 120d 2026-07-16)
    assert watch["color_flip_age"] == 2
    assert watch["event_age"] == 2
    assert watch["higher_tf"] is None
    assert watch["p_false_boosts"] == []


def test_v020_h1_overrides_15m_ignition_timeout(monkeypatch):
    # H1-G3 (adapted to the B.3.5 anchors: the 15m watch IS M1m): the 15m
    # timeout must NOT adjudicate false — the 30m CONFIRMED governs.
    monkeypatch.setenv("RULE_VERSION", "0.2.0")
    client = _client(monkeypatch, _market_frames())
    body = _get(client).json()

    assert _fe(body)[("30m", "up")]["state"] == "CONFIRMED"
    watch = _fi(body)[("15m", "up")]
    assert watch["state"] == "CONFIRMED_BY_HIGHER_TF"
    assert watch["higher_tf"] == {"source_tf": "30m"}
    assert watch["p_false_ignition"] is None
    assert watch["t0_age"] == 8
    assert watch["shadow"] is False
    assert watch["alertable"] is False  # 15m never pushes (addendum B.3.5)


def test_v020_m2_contrary_impulse_on_1h(monkeypatch):
    monkeypatch.setenv("RULE_VERSION", "0.2.0")
    client = _client(monkeypatch, _market_frames())
    body = _get(client).json()

    assert _fe(body)[("1h", "up")]["state"] == "FALSE_ENTRY_PROBABLE"
    assert _fe(body)[("1h", "up")]["p_false"] == 0.40  # measured timeout prior

    contrary = body["monitors"]["contrary_impulse"]
    assert len(contrary) == 1
    entry = contrary[0]
    assert entry["timeframe"] == "1h"
    assert entry["direction"] == "down"
    assert entry["profile"] == "snipper"
    assert entry["trigger"] == "ao_recross_color"
    assert entry["source"]["kind"] == "m1"
    assert entry["source"]["state"] == "FALSE_ENTRY_PROBABLE"


def test_v020_vol_turn_rounded_block(monkeypatch):
    monkeypatch.setenv("RULE_VERSION", "0.2.0")
    client = _client(monkeypatch, _market_frames())
    body = _get(client).json()

    assert body["monitors"]["vol_turn_rounded"] == [
        {"timeframe": "1d", "variant": "v", "move_direction": "down"}
    ]
    # No confluence in this market (1h AO just flipped negative, 15m BBWP dead).
    assert body["monitors"]["confluence"] == []


# ---------------------------------------------------------------------------
# Version selection plumbing
# ---------------------------------------------------------------------------

def test_rule_version_query_param_overrides_env_default(monkeypatch):
    monkeypatch.delenv("RULE_VERSION", raising=False)
    client = _client(monkeypatch, _market_frames())

    default = _get(client).json()
    assert default["rule_version"] == "0.1.0"
    assert set(default["monitors"].keys()) == {"false_entry_watch", "tf_status"}

    v020 = _get(client, rule_version="0.2.0").json()
    assert v020["rule_version"] == "0.2.0"
    assert set(v020["monitors"].keys()) == V2_MONITOR_BLOCKS


def test_rule_version_021_runs_the_same_pack_and_reports_its_label(monkeypatch):
    # 0.2.0 and 0.2.1 execute the SAME corrected code (spec §I.9); the
    # reported rule_version is the caller's label, verbatim.
    monkeypatch.delenv("RULE_VERSION", raising=False)
    client = _client(monkeypatch, _market_frames())

    v021 = _get(client, rule_version="0.2.1").json()
    assert v021["rule_version"] == "0.2.1"
    assert set(v021["monitors"].keys()) == V2_MONITOR_BLOCKS

    v020 = _get(client, rule_version="0.2.0").json()
    assert v020["rule_version"] == "0.2.0"
    assert v020["monitors"] == v021["monitors"]  # no code fork


def test_unsupported_rule_version_is_a_400(monkeypatch):
    monkeypatch.delenv("RULE_VERSION", raising=False)
    client = _client(monkeypatch, _market_frames())
    response = _get(client, rule_version="9.9.9")
    assert response.status_code == 400
    assert "rule_version" in response.json()["error"]
