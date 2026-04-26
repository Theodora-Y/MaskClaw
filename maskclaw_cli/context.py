from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FALLBACK_CONFIG_PATH = PROJECT_ROOT / ".maskclaw" / "config.json"
SERVICE_CATALOG_VERSION = 1


def ensure_project_root_on_path() -> None:
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def default_config_path() -> Path:
    override = os.environ.get("MASKCLAW_CONFIG_PATH")
    if override:
        return Path(override)
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
        return base / "MaskClaw" / "config.json"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "maskclaw" / "config.json"


@dataclass
class MaskClawConfig:
    current_user_id: str | None = None
    username: str | None = None
    token: str | None = None
    api_base_url: str = "http://127.0.0.1:8001"
    model_backend: str = "ollama"
    model_name: str = "gemma:2b"
    model_endpoint: str = "http://127.0.0.1:8005"
    mode: str = "personal"
    output_format: str = "table"
    autoglm_dir: str = r"D:\学习笔记\工4\实验设计\Open-AutoGLM-main\Open-AutoGLM-main"
    service_catalog_version: int = SERVICE_CATALOG_VERSION
    service_roles: dict[str, dict[str, Any]] = field(default_factory=dict)
    model_roles: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaskClawConfig":
        allowed = {field.name for field in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in data.items() if k in allowed})


def _service_spec(
    *,
    enabled: bool,
    managed: bool,
    cwd: Path | str,
    command: list[str],
    endpoint: str,
    healthcheck: str = "tcp",
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "enabled": enabled,
        "managed": managed,
        "cwd": str(cwd) if cwd else "",
        "command": list(command),
        "endpoint": endpoint,
        "healthcheck": healthcheck,
        "depends_on": list(depends_on or []),
    }


def _default_model_roles(config: MaskClawConfig) -> dict[str, str]:
    if config.mode == "enterprise" or config.model_backend == "minicpm":
        return {
            "privacy": "minicpm-privacy",
            "skillgen": "minicpm-skillgen",
            "feedback": "minicpm-feedback",
        }
    if config.model_backend in {"ollama", "gemma"}:
        return {
            "privacy": "ollama-proxy",
            "skillgen": "ollama-proxy",
            "feedback": "ollama-proxy",
        }
    return {"privacy": "", "skillgen": "", "feedback": ""}


def _default_service_roles(config: MaskClawConfig) -> dict[str, dict[str, Any]]:
    python_exe = sys.executable
    legacy_endpoint = config.model_endpoint
    ollama_endpoint = legacy_endpoint if config.model_backend in {"ollama", "gemma"} else "http://127.0.0.1:8005"
    minicpm_privacy_endpoint = legacy_endpoint if config.model_backend == "minicpm" and legacy_endpoint else "http://127.0.0.1:8000/chat"
    minicpm_skillgen_endpoint = os.environ.get("MASKCLAW_MINICPM_SKILLGEN_ENDPOINT", "")
    minicpm_feedback_endpoint = os.environ.get("MASKCLAW_MINICPM_FEEDBACK_ENDPOINT", "")

    return {
        "api": _service_spec(
            enabled=True,
            managed=True,
            cwd=PROJECT_ROOT,
            command=[python_exe, "api_server.py"],
            endpoint="http://127.0.0.1:8001",
        ),
        "evolution-daemon": _service_spec(
            enabled=True,
            managed=True,
            cwd=PROJECT_ROOT,
            command=[python_exe, "evolution_daemon.py"],
            endpoint="",
            healthcheck="process",
        ),
        "bridge-autoglm": _service_spec(
            enabled=True,
            managed=True,
            cwd=PROJECT_ROOT,
            command=[python_exe, "autoglm_server.py"],
            endpoint="http://127.0.0.1:28080/api/autoglm/health",
        ),
        "frontend": _service_spec(
            enabled=True,
            managed=True,
            cwd=PROJECT_ROOT / "frontend" / "ui-app",
            command=["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"],
            endpoint="http://127.0.0.1:5173",
        ),
        "minicpm-privacy": _service_spec(
            enabled=True,
            managed=False,
            cwd="",
            command=[],
            endpoint=minicpm_privacy_endpoint,
        ),
        "minicpm-skillgen": _service_spec(
            enabled=True,
            managed=False,
            cwd="",
            command=[],
            endpoint=minicpm_skillgen_endpoint,
        ),
        "minicpm-feedback": _service_spec(
            enabled=True,
            managed=False,
            cwd="",
            command=[],
            endpoint=minicpm_feedback_endpoint,
        ),
        "ollama-proxy": _service_spec(
            enabled=config.model_backend in {"ollama", "gemma"},
            managed=config.model_backend in {"ollama", "gemma"},
            cwd=PROJECT_ROOT / "model_server",
            command=[python_exe, "ollama_api.py"],
            endpoint=ollama_endpoint,
        ),
    }


def ensure_service_catalog(config: MaskClawConfig) -> MaskClawConfig:
    defaults = _default_service_roles(config)
    current = config.service_roles or {}
    merged: dict[str, dict[str, Any]] = {}

    for service_id, default_spec in defaults.items():
        raw_spec = current.get(service_id, {})
        if not isinstance(raw_spec, dict):
            raw_spec = {}
        merged_spec = dict(default_spec)
        for key in ["cwd", "command", "endpoint", "healthcheck", "depends_on"]:
            if key in raw_spec and raw_spec[key] not in (None, ""):
                merged_spec[key] = raw_spec[key]
        merged[service_id] = merged_spec

    for service_id, raw_spec in current.items():
        if service_id not in merged and isinstance(raw_spec, dict):
            merged[service_id] = raw_spec

    role_defaults = _default_model_roles(config)
    current_roles = config.model_roles if isinstance(config.model_roles, dict) else {}
    merged_roles = dict(role_defaults)
    for role_name, service_id in current_roles.items():
        if service_id:
            merged_roles[role_name] = service_id

    config.service_roles = merged
    config.model_roles = merged_roles
    config.service_catalog_version = SERVICE_CATALOG_VERSION
    return config


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_config_path()
        self.fallback_path = FALLBACK_CONFIG_PATH

    def load(self) -> MaskClawConfig:
        for candidate in (self.path, self.fallback_path):
            try:
                exists = candidate.exists()
            except OSError:
                continue
            if not exists:
                continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return ensure_service_catalog(MaskClawConfig.from_dict(data))
            except Exception:
                continue
        return ensure_service_catalog(MaskClawConfig())

    def save(self, config: MaskClawConfig) -> Path:
        config = ensure_service_catalog(config)
        payload = json.dumps(asdict(config), ensure_ascii=False, indent=2)
        for candidate in (self.path, self.fallback_path):
            try:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_text(payload, encoding="utf-8")
                return candidate
            except PermissionError:
                continue
        raise PermissionError(f"Unable to write CLI config to {self.path} or fallback {self.fallback_path}")

    def clear_auth(self) -> Path:
        config = self.load()
        config.current_user_id = None
        config.username = None
        config.token = None
        return self.save(config)
