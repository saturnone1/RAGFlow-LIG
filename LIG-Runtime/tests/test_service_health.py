from __future__ import annotations

import lig_runtime.service_health as service_health


class _Response:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int) -> bytes:
        return self._body


def test_health_uses_public_ping_without_an_api_key(monkeypatch):
    requested = []

    def fake_urlopen(url, timeout):
        requested.append((url, timeout))
        return _Response(200, b"pong")

    monkeypatch.delenv("RAGFLOW_MCP_HOST_API_KEY", raising=False)
    monkeypatch.setattr(service_health, "urlopen", fake_urlopen)

    assert service_health.main() == 0
    assert requested == [("http://127.0.0.1:9380/api/v1/system/ping", 10)]


def test_health_rejects_an_unexpected_ping_response(monkeypatch):
    monkeypatch.setattr(service_health, "urlopen", lambda *_args, **_kwargs: _Response(200, b"not-ready"))
    assert service_health.main() == 1
