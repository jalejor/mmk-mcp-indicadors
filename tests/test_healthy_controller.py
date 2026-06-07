"""Health controller tests — covers the structured payload + exchange probe.

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
    """When the exchange probe raises, the endpoint must downgrade to degraded."""
    monkeypatch.setattr(healthy_module, "_probe_exchange", lambda: "error: boom")
    out = healthy_module.healthy()
    assert out["status"] == "degraded"
    assert out["exchange_status"].startswith("error")
    assert out["exchange"]


def test_healthy_returns_ok_when_probe_succeeds(monkeypatch):
    monkeypatch.setattr(healthy_module, "_probe_exchange", lambda: "ok")
    out = healthy_module.healthy()
    assert out["status"] == "healthy"
    assert out["exchange_status"] == "ok"
