"""Make accidental real HTTP requests fail in the offline test suite."""

import httpx
import pytest


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("Real HTTP is disabled in tests; use a mock transport")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
