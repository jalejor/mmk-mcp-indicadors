"""Integration tests for GET /v1/setups/evaluate (F0.5-API).

No network: `SetupEvaluationService._enriched_frame` is monkeypatched with
deterministic, already-enriched frames (same technique as the setup backtest
tests). Two engineered markets are covered:

* TRIGGERED — IMP-4H-LONG with a fresh Konkorde cross, fresh rising AO and an
  E1-G1-shaped ADX turn pivoting from 18 (A-grade).
* VETOED — same market but the AO zero-cross happened 7 closed candles ago:
  the trigger logic still passes, `stale_ao_cross` suppresses the entry
  (the owner's false-entry case, spec §B.3 V1).
"""

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from controllers.metrics.setup_evaluation_service import SetupEvaluationService

API_KEY = "test-key"

TOP_LEVEL_KEYS = {"symbol", "rule_version", "evaluated_at", "setups"}
SETUP_KEYS = {
    "setup_id", "side", "band", "context_tf", "trigger_tf", "status",
    "conditions", "vetoes", "adx_turn_grade", "evidence",
}
CONDITION_KEYS = {"name", "passed", "value"}
VETO_KEYS = {"name", "hit", "detail"}
EVIDENCE_KEYS = {"price", "bbwp", "ao", "adx", "konkorde_marron"}
STATUSES = {"no_context", "context_ok", "triggered", "vetoed", "invalidated"}


# ---------------------------------------------------------------------------
# Deterministic enriched frames (no network, no pandas-ta)
# ---------------------------------------------------------------------------

def _frame_1d() -> pd.DataFrame:
    """Benign daily context: uptrend (close > sma200), no PB pullback."""
    n = 60
    index = pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
            "volume": 1000.0,
            "sma200": 90.0, "sma50": 95.0, "ema50": 96.0, "ema200": 92.0,
            "adx14": 20.0, "plus_di": 25.0, "minus_di": 15.0,
            "ao": 1.0, "bbwp": 40.0, "atr14": 1.5,
            "konkorde_marron": 5.0,
        },
        index=index,
    )


def _frame_4h(*, stale_ao: bool) -> pd.DataFrame:
    """4h trigger frame engineered for IMP-4H-LONG.

    Fresh Konkorde cross (age 1) + rising positive AO + E1-G1 ADX turn
    (pivot from 18 -> A-grade). With `stale_ao=True` the AO cross fired 7
    closed candles ago (> max_event_age=5) -> stale_ao_cross veto.
    """
    n = 60
    # Last 4h candle opens 2026-02-29 20:00, closes 2026-03-01 00:00 UTC.
    index = pd.date_range("2026-02-20", periods=n, freq="4h", tz="UTC")

    adx = np.full(n, 18.0)
    adx[-3:] = [18.5, 21.5, 24.5]  # E1-G1 turn firing on the last closed bar

    ao = np.full(n, -1.0)
    if stale_ao:
        ao[-8:] = [0.3, 0.6, 0.9, 1.2, 1.5, 1.8, 2.1, 2.3]  # cross age 7
    else:
        ao[-3:] = [0.5, 0.9, 1.4]  # cross age 2 (fresh)

    konkorde = np.full(n, -0.5)
    konkorde[-2:] = [0.7, 1.3]  # zero-cross up, age 1 (fresh)

    return pd.DataFrame(
        {
            "open": 100.0, "high": 100.5, "low": 99.5, "close": 100.0,
            "volume": 1000.0,
            "sma200": 90.0, "sma50": 95.0, "ema50": 96.0, "ema200": 92.0,
            "adx14": adx, "plus_di": 28.0, "minus_di": 15.0,
            "ao": ao, "bbwp": 60.0, "atr14": 2.0,
            "konkorde_marron": konkorde,
        },
        index=index,
    )


def _patch_frames(monkeypatch, *, stale_ao: bool) -> None:
    frames = {"1d": _frame_1d(), "4h": _frame_4h(stale_ao=stale_ao)}
    monkeypatch.setattr(
        SetupEvaluationService,
        "_enriched_frame",
        lambda self, timeframe: frames[timeframe],
    )


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("API_KEYS", API_KEY)
    from routes import routes

    app = FastAPI(title="setups-evaluate-test")
    app.include_router(routes)
    return TestClient(app)


def _get(client: TestClient, **kwargs):
    headers = kwargs.pop("headers", {"X-API-Key": API_KEY})
    return client.get("/v1/setups/evaluate", params={"symbol": "BTC/USDT"}, headers=headers)


# ---------------------------------------------------------------------------
# Auth (same X-API-Key gate as every /v1 route)
# ---------------------------------------------------------------------------

def test_evaluate_requires_api_key(monkeypatch):
    _patch_frames(monkeypatch, stale_ao=False)
    client = _client(monkeypatch)
    assert _get(client, headers={}).status_code == 401
    assert _get(client, headers={"X-API-Key": "wrong"}).status_code == 401


def test_evaluate_returns_200_with_valid_key(monkeypatch):
    _patch_frames(monkeypatch, stale_ao=False)
    client = _client(monkeypatch)
    response = _get(client)
    assert response.status_code == 200
    assert response.json()["symbol"] == "BTC/USDT"


# ---------------------------------------------------------------------------
# Contract shape (agreed with the frontend — do not change silently)
# ---------------------------------------------------------------------------

def test_contract_shape_is_complete(monkeypatch):
    _patch_frames(monkeypatch, stale_ao=False)
    client = _client(monkeypatch)
    body = _get(client).json()

    assert set(body.keys()) == TOP_LEVEL_KEYS
    assert body["rule_version"] == "0.1.0"
    # evaluated_at must be parseable ISO-8601 UTC.
    evaluated_at = pd.Timestamp(body["evaluated_at"])
    assert evaluated_at.tzinfo is not None

    assert [s["setup_id"] for s in body["setups"]] == [
        "PB-1D-LONG", "PB-1D-SHORT", "IMP-4H-LONG", "IMP-4H-SHORT",
    ]
    for setup in body["setups"]:
        assert set(setup.keys()) == SETUP_KEYS
        assert setup["side"] in ("long", "short")
        assert setup["band"] == "high_tf"
        assert setup["status"] in STATUSES
        assert set(setup["conditions"].keys()) == {"context", "trigger", "invalidation"}
        for block in setup["conditions"].values():
            for condition in block:
                assert set(condition.keys()) == CONDITION_KEYS
                assert isinstance(condition["name"], str)
                assert isinstance(condition["passed"], bool)
                assert condition["value"] is None or isinstance(condition["value"], float)
        for veto in setup["vetoes"]:
            assert set(veto.keys()) == VETO_KEYS
            assert isinstance(veto["hit"], bool)
        assert setup["adx_turn_grade"] in ("A", "B", None)
        assert set(setup["evidence"].keys()) == EVIDENCE_KEYS


# ---------------------------------------------------------------------------
# Synthetic market: TRIGGERED
# ---------------------------------------------------------------------------

def test_imp_4h_long_triggers_on_fresh_confirmed_market(monkeypatch):
    _patch_frames(monkeypatch, stale_ao=False)
    client = _client(monkeypatch)
    setups = {s["setup_id"]: s for s in _get(client).json()["setups"]}

    imp = setups["IMP-4H-LONG"]
    assert imp["status"] == "triggered"
    assert imp["adx_turn_grade"] == "A"  # turn pivots from 18, inside [12, 20]
    assert all(v["hit"] is False for v in imp["vetoes"])
    assert all(c["passed"] for c in imp["conditions"]["context"])
    assert all(c["passed"] for c in imp["conditions"]["trigger"])
    assert not any(c["passed"] for c in imp["conditions"]["invalidation"])

    evidence = imp["evidence"]
    assert evidence["price"] == pytest.approx(100.0)
    assert evidence["bbwp"] == pytest.approx(60.0)
    assert evidence["ao"] == pytest.approx(1.4)
    assert evidence["adx"] == pytest.approx(24.5)
    assert evidence["konkorde_marron"] == pytest.approx(1.3)

    # Same market, other setups: daily uptrend without a pullback.
    assert setups["PB-1D-LONG"]["status"] == "no_context"
    # PB-1D-SHORT's invalidation (close_above_sma200) matches immediately.
    assert setups["PB-1D-SHORT"]["status"] == "invalidated"
    # No bearish ADX turn -> the short impulse never has context.
    assert setups["IMP-4H-SHORT"]["status"] == "no_context"


# ---------------------------------------------------------------------------
# Synthetic market: VETOED (the owner's stale-cross false entry)
# ---------------------------------------------------------------------------

def test_imp_4h_long_vetoed_on_stale_ao_cross(monkeypatch):
    _patch_frames(monkeypatch, stale_ao=True)
    client = _client(monkeypatch)
    setups = {s["setup_id"]: s for s in _get(client).json()["setups"]}

    imp = setups["IMP-4H-LONG"]
    assert imp["status"] == "vetoed"
    # Trigger logic itself passed (fresh konkorde cross, AO positive+rising).
    assert all(c["passed"] for c in imp["conditions"]["trigger"])

    vetoes = {v["name"]: v for v in imp["vetoes"]}
    assert vetoes["stale_ao_cross"]["hit"] is True
    assert vetoes["stale_konkorde_cross"]["hit"] is False
    assert vetoes["no_adx_turn_confirmation"]["hit"] is False
    # V2 still ran and found the confirming turn (grade survives the veto).
    assert imp["adx_turn_grade"] == "A"
