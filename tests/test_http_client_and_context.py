from __future__ import annotations

import json
from pathlib import Path

from maskclaw_cli.context import ConfigStore
from maskclaw_cli.services import http_client


def test_should_bypass_proxy_for_loopback_and_private_hosts():
    assert http_client._should_bypass_proxy("http://127.0.0.1:8001/auth/login") is True
    assert http_client._should_bypass_proxy("http://localhost:8001/") is True
    assert http_client._should_bypass_proxy("http://10.0.0.8:8000/health") is True
    assert http_client._should_bypass_proxy("https://example.com/api") is False


def test_request_json_uses_empty_proxy_handler_for_loopback(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"ok": true}'

    class FakeOpener:
        def open(self, request, timeout=0):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            return FakeResponse()

    def fake_build_opener(*handlers):
        captured["handlers"] = handlers
        return FakeOpener()

    monkeypatch.setattr(http_client.urllib.request, "build_opener", fake_build_opener)
    payload = http_client.request_json("GET", "http://127.0.0.1:8001/")
    assert payload == {"ok": True}
    assert captured["url"] == "http://127.0.0.1:8001/"
    assert len(captured["handlers"]) == 1
    proxy_handler = captured["handlers"][0]
    assert isinstance(proxy_handler, http_client.urllib.request.ProxyHandler)


def test_config_store_load_skips_permission_error_and_uses_fallback(monkeypatch):
    fallback = Path("D:/学习笔记/工4/实验设计/MaskClaw/.maskclaw_test_fallback.json")
    fallback.write_text(
        json.dumps({"current_user_id": "demo_UserC", "api_base_url": "http://127.0.0.1:8001"}, ensure_ascii=False),
        encoding="utf-8",
    )

    class DeniedPath:
        def exists(self):
            raise PermissionError("denied")

    store = ConfigStore(path=DeniedPath())  # type: ignore[arg-type]
    store.fallback_path = fallback
    try:
        config = store.load()
        assert config.current_user_id == "demo_UserC"
        assert config.api_base_url == "http://127.0.0.1:8001"
    finally:
        try:
            fallback.unlink()
        except FileNotFoundError:
            pass
