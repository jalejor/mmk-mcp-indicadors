"""Auth dependency tests.

We exercise the dependency directly instead of spinning up a full FastAPI
test client to keep the suite light and offline-friendly.
"""

import pytest
from fastapi import HTTPException

from security import api_key_dependency


class _Req:
    """Tiny shim so api_key_dependency receives a duck-typed Request."""


def test_auth_disabled_when_api_keys_unset(monkeypatch):
    monkeypatch.delenv("API_KEYS", raising=False)
    # Should not raise.
    api_key_dependency(request=_Req(), x_api_key=None)


def test_auth_disabled_when_api_keys_blank(monkeypatch):
    monkeypatch.setenv("API_KEYS", "")
    api_key_dependency(request=_Req(), x_api_key=None)


def test_invalid_key_raises(monkeypatch):
    monkeypatch.setenv("API_KEYS", "valid-key,other-key")
    with pytest.raises(HTTPException) as exc:
        api_key_dependency(request=_Req(), x_api_key="bad-key")
    assert exc.value.status_code == 401


def test_missing_key_raises_when_required(monkeypatch):
    monkeypatch.setenv("API_KEYS", "valid-key")
    with pytest.raises(HTTPException) as exc:
        api_key_dependency(request=_Req(), x_api_key=None)
    assert exc.value.status_code == 401


def test_valid_key_passes(monkeypatch):
    monkeypatch.setenv("API_KEYS", "valid-key,other-key")
    api_key_dependency(request=_Req(), x_api_key="other-key")
