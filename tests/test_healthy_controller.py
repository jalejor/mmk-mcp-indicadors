"""Health controller tests — covers the new structured payload + Binance probe.

We import the module via `importlib` because `controllers/__init__.py`
shadows the submodule attribute with a `HealthyController` instance for
backwards compatibility.
"""

import importlib

healthy_module = importlib.import_module("controllers.healthy_controller")


def test_liveness_payload():
    out = healthy_module.liveness()
    assert out["status"] == "alive"
    assert "uptime_seconds" in out
    assert "version" in out


def test_healthy_handles_probe_failure(monkeypatch):
    """When the Binance probe raises, the endpoint must downgrade to degraded."""
    monkeypatch.setattr(healthy_module, "_probe_binance", lambda: "error: boom")
    out = healthy_module.healthy()
    assert out["status"] == "degraded"
    assert out["exchange_binance"].startswith("error")


def test_healthy_returns_ok_when_probe_succeeds(monkeypatch):
    monkeypatch.setattr(healthy_module, "_probe_binance", lambda: "ok")
    out = healthy_module.healthy()
    assert out["status"] == "healthy"
    assert out["exchange_binance"] == "ok"
