"""v0.1.0 no-regression guard for the RULE_VERSION gate (spec §0.4 / §I).

CRITICAL: with RULE_VERSION unset (or explicitly 0.1.0) the evaluate contract
must be byte-identical to the pre-v0.2.0 behaviour, even on a market that the
0.2.0 rules WOULD adjudicate differently (a DI color flip). The engineered 4h
frame is the M11-G1 market: v0.2.0 says FALSE_ENTRY_CONFIRMED, v0.1.0 must
keep saying WATCHING with the exact v1 payload keys and no new blocks.
"""

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.metrics.setup_evaluation_service import SetupEvaluationService

API_KEY = "test-key"

V1_MONITOR_KEYS = {
    "timeframe", "direction", "state", "early_warning", "event_age",
    "consecutive_ao_candles", "adx_turn", "p_false", "cross_candle_ts",
}
V1_STATES = {"WATCHING", "CONFIRMED", "FALSE_ENTRY_PROBABLE", "WHIPSAW"}
V1_TFS = {"30m", "1h", "4h", "1d", "1w"}


def _frame_1d():
    n = 60
    index = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
            "volume": 1000.0,
            "sma200": 90.0, "sma50": 95.0, "ema50": 96.0, "ema200": 92.0,
            "adx14": 20.0, "plus_di": 25.0, "minus_di": 15.0,
            "ao": 1.0, "bbwp": 40.0, "atr14": 1.5, "konkorde_marron": 5.0,
        },
        index=index,
    )


def _frame_4h_color_flip():
    """M11-G1 market: cross up age 2, DI flips bearish at post-cross age 2."""
    n = 60
    index = pd.date_range("2026-02-20", periods=n, freq="4h", tz="UTC")
    ao = np.full(n, -0.5)
    ao[-3:] = [0.4, 0.9, 0.7]
    plus = np.full(n, 26.0)
    plus[-3:] = [27, 24, 19]
    minus = np.full(n, 16.0)
    minus[-3:] = [17, 22, 25]
    return pd.DataFrame(
        {
            "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
            "volume": 1000.0,
            "sma200": 90.0, "sma50": 95.0, "ema50": 96.0, "ema200": 92.0,
            "adx14": 20.0, "plus_di": plus, "minus_di": minus,
            "ao": ao, "bbwp": 60.0, "atr14": 2.0, "konkorde_marron": -0.5,
        },
        index=index,
    )


FRAMES = {
    "1d": _frame_1d(), "4h": _frame_4h_color_flip(),
    "30m": _frame_1d(), "1h": _frame_1d(), "1w": _frame_1d(),
}


def _client(monkeypatch):
    monkeypatch.setenv("API_KEYS", API_KEY)
    monkeypatch.setattr(
        SetupEvaluationService,
        "_enriched_frame",
        lambda self, timeframe: FRAMES[timeframe],
    )
    from routes import routes

    app = FastAPI(title="v010-no-regression-test")
    app.include_router(routes)
    return TestClient(app)


def _get(client, **params):
    return client.get(
        "/v1/setups/evaluate",
        params={"symbol": "BTC/USDT", **params},
        headers={"X-API-Key": API_KEY},
    )


@pytest.mark.parametrize("env_value", [None, "0.1.0"])
def test_v010_contract_is_untouched(monkeypatch, env_value):
    if env_value is None:
        monkeypatch.delenv("RULE_VERSION", raising=False)
    else:
        monkeypatch.setenv("RULE_VERSION", env_value)
    client = _client(monkeypatch)
    body = _get(client).json()

    assert body["rule_version"] == "0.1.0"
    # No new blocks, no 15m, no v2 keys, no v2 states.
    assert set(body["monitors"].keys()) == {"false_entry_watch", "tf_status"}
    assert set(body["monitors"]["tf_status"].keys()) == V1_TFS
    for entry in body["monitors"]["false_entry_watch"]:
        assert set(entry.keys()) == V1_MONITOR_KEYS
        assert entry["state"] in V1_STATES

    # The color-flip market stays WATCHING under v0.1.0 (the flip is 0.2.0-only).
    watch = {
        (m["timeframe"], m["direction"]): m
        for m in body["monitors"]["false_entry_watch"]
    }[("4h", "up")]
    assert watch["state"] == "WATCHING"
    assert watch["p_false"] is None


def test_setups_block_is_identical_across_rule_versions(monkeypatch):
    # The 0.2.0 pack is additive monitor blocks ONLY: the setups evaluation
    # (the 0.1.0 documents) must produce the exact same output either way.
    monkeypatch.delenv("RULE_VERSION", raising=False)
    client = _client(monkeypatch)

    v010 = _get(client).json()
    v020 = _get(client, rule_version="0.2.0").json()

    assert v010["setups"] == v020["setups"]
    assert v020["rule_version"] == "0.2.0"
    # And the v1 sub-blocks keep existing under 0.2.0 (superset, not replace).
    assert "false_entry_watch" in v020["monitors"]
    assert "tf_status" in v020["monitors"]
