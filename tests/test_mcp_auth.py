"""Security test: the mounted MCP transport must enforce the same API key as
the protected `/v1/*` HTTP endpoints.

Regression guard for the P0 where `FastApiMCP(app).mount()` exposed the MCP
SSE/messages endpoints WITHOUT any auth on an `--allow-unauthenticated`
Cloud Run service, giving anonymous callers the same ccxt compute as the
protected routes.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from mcp_server import start_mcp
from security import api_key_dependency


def _app_with_mcp() -> FastAPI:
    app = FastAPI(title="mcp-auth-test")
    start_mcp(app)
    return app


def _mcp_routes(app: FastAPI):
    """Return the MCP routes (SSE GET handshake + messages POST)."""
    return [
        r
        for r in app.routes
        if getattr(r, "operation_id", None) in {"mcp_connection", "mcp_messages"}
    ]


def test_mcp_routes_are_mounted():
    app = _app_with_mcp()
    op_ids = {getattr(r, "operation_id", None) for r in _mcp_routes(app)}
    assert "mcp_connection" in op_ids  # SSE GET handshake
    assert "mcp_messages" in op_ids  # messages POST


def test_mcp_routes_carry_the_api_key_dependency():
    """Both MCP endpoints must register `api_key_dependency` so the key is
    enforced (the SSE GET would otherwise hang an unauthenticated TestClient,
    so we assert on the wired dependency instead of opening the stream)."""
    app = _app_with_mcp()
    mcp_routes = _mcp_routes(app)
    assert mcp_routes, "MCP routes were not mounted"
    for route in mcp_routes:
        # Route-level dependencies are exposed as sub-Dependants whose resolved
        # callable lives in `.call`.
        dep_calls = [d.call for d in route.dependant.dependencies]
        assert api_key_dependency in dep_calls, (
            f"MCP route {route.path} is missing api_key_dependency"
        )


def test_mcp_messages_rejects_without_key(monkeypatch):
    """With API_KEYS set, POSTing to the MCP messages endpoint without the
    header must be rejected with 401 (never reaching the transport)."""
    monkeypatch.setenv("API_KEYS", "secret-key")
    app = _app_with_mcp()
    client = TestClient(app)
    resp = client.post("/mcp/messages/", json={"jsonrpc": "2.0", "method": "ping"})
    assert resp.status_code == 401


def test_mcp_messages_passes_auth_with_valid_key(monkeypatch):
    """With a valid key the auth gate is cleared; the request then reaches the
    transport (missing SSE session) rather than being rejected as 401. The
    transport may either return a non-401 status or raise — both prove that the
    auth dependency let the request through."""
    monkeypatch.setenv("API_KEYS", "secret-key")
    app = _app_with_mcp()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/mcp/messages/",
        headers={"X-API-Key": "secret-key"},
        json={"jsonrpc": "2.0", "method": "ping"},
    )
    assert resp.status_code != 401
