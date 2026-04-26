from __future__ import annotations

import base64
import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from typer.testing import CliRunner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from maskclaw_cli.main import app


@pytest.fixture()
def runner(monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    config_path = PROJECT_ROOT / ".maskclaw_test_config.json"
    try:
        config_path.unlink()
    except FileNotFoundError:
        pass
    monkeypatch.setenv("MASKCLAW_CONFIG_PATH", str(config_path))
    try:
        yield CliRunner()
    finally:
        try:
            config_path.unlink()
        except FileNotFoundError:
            pass


@pytest.fixture()
def event_json_path() -> Path:
    return PROJECT_ROOT / "tests" / "data" / "guard_event.json"


@pytest.fixture()
def sample_image_path() -> Path:
    base = PROJECT_ROOT / ".pytest_tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"guard_case_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    image_path = path / "sample.png"
    image_path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnV7m8AAAAASUVORK5CYII="
        )
    )
    try:
        yield image_path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture()
def cli_app():
    return app
