from __future__ import annotations

import importlib
import json
import subprocess
import sys

from maskclaw_cli.context import PROJECT_ROOT, ensure_project_root_on_path


def test_ensure_project_root_on_path_enables_root_module_import(monkeypatch):
    temp_dir = PROJECT_ROOT / ".pytest_entry_tmp"
    temp_dir.mkdir(exist_ok=True)
    monkeypatch.chdir(temp_dir)
    trimmed = [path for path in sys.path if path not in {"", str(PROJECT_ROOT)}]
    monkeypatch.setattr(sys, "path", trimmed)
    sys.modules.pop("review_service", None)
    importlib.invalidate_caches()

    try:
        importlib.import_module("review_service")
    except ModuleNotFoundError:
        pass
    else:
        raise AssertionError("review_service should not be importable before ensure_project_root_on_path()")

    ensure_project_root_on_path()
    module = importlib.import_module("review_service")
    assert hasattr(module, "ReviewService")


def test_api_server_core_import_exposes_auth_review_and_evolution_routes():
    script = (
        "import json, api_server; "
        "paths=sorted({getattr(route, 'path', '') for route in api_server.app.routes}); "
        "print(json.dumps(paths, ensure_ascii=False))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout.strip())
    assert "/auth/login" in payload
    assert "/guard/decide" in payload
    assert "/guard/analyze" in payload
    assert "/guard/redact" in payload
    assert "/review/{user_id}/pending" in payload
    assert "/evolution/events/{user_id}" in payload
    assert "/evolution/source/logs/{user_id}" in payload
