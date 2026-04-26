from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from typing import Any

from maskclaw_cli.context import PROJECT_ROOT, ConfigStore, default_config_path
from maskclaw_cli.services.runtime_service import RuntimeService, probe_http


class DoctorService:
    def __init__(self, store: ConfigStore | None = None) -> None:
        self.store = store or ConfigStore()
        self.runtime = RuntimeService(self.store)

    def run(self) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        config = self.store.load()
        capability_bindings = config.model_roles if isinstance(config.model_roles, dict) else {}
        service_status = {row["service"]: row for row in self.runtime.status()}

        checks.append(self._check("python", True, sys.version.split()[0], sys.executable))
        checks.append(self._check("project-root", PROJECT_ROOT.exists(), str(PROJECT_ROOT), ""))
        checks.append(self._check("config-path", True, str(default_config_path()), "created on first write"))
        checks.append(self._check("service-catalog-version", True, str(config.service_catalog_version), "role-based service catalog"))

        for module in ["typer", "fastapi", "uvicorn", "pydantic"]:
            checks.append(self._check(f"python-module:{module}", importlib.util.find_spec(module) is not None, module, ""))

        for command in ["npm"]:
            checks.append(self._check(f"command:{command}", shutil.which(command) is not None, shutil.which(command) or "", ""))

        required_paths = [
            "api_server.py",
            "evolution_daemon.py",
            "model_server",
            "frontend/ui-app/package.json",
            "autoglm_server.py",
            "windows_sdk/autoglm_server.py",
            "user_skills",
            "memory",
            "prompts",
            "skill_registry/skill_registry.db",
        ]
        for rel in required_paths:
            path = PROJECT_ROOT / Path(rel)
            checks.append(self._check(f"path:{rel}", path.exists(), str(path), ""))

        autoglm_dir = Path(config.autoglm_dir)
        checks.append(
            self._check(
                "bridge-autoglm:autoglm-dir",
                autoglm_dir.exists(),
                str(autoglm_dir),
                "used when starting bridge-autoglm",
            )
        )

        for capability in ["privacy", "skillgen", "feedback"]:
            service_id = str(capability_bindings.get(capability) or "")
            ok = bool(service_id)
            note = ""
            if ok and service_id not in service_status:
                ok = False
                note = "bound service missing from role catalog"
            elif ok:
                bound_row = service_status[service_id]
                note = bound_row.get("endpoint") or ("managed service" if bound_row.get("managed") else "external service")
            checks.append(self._check(f"model-role:{capability}", ok, service_id, note))

        for service_id in [
            "api",
            "evolution-daemon",
            "bridge-autoglm",
            "frontend",
            "minicpm-privacy",
            "minicpm-skillgen",
            "minicpm-feedback",
            "ollama-proxy",
        ]:
            row = service_status.get(service_id)
            if not row:
                checks.append(self._check(f"service:{service_id}", False, "", "missing from runtime catalog"))
                continue

            configured = True
            note_bits: list[str] = [f"required={row.get('required', False)}", f"managed={row.get('managed', False)}"]
            if not row.get("managed") and not row.get("endpoint"):
                configured = False
                note_bits.append("external endpoint missing")
            elif row.get("endpoint"):
                note_bits.append("listening" if probe_http(row["endpoint"]) else "not listening")
            if row.get("depends_on"):
                note_bits.append(f"depends={row['depends_on']}")
            if row.get("capabilities"):
                note_bits.append(f"roles={row['capabilities']}")
            checks.append(self._check(f"service:{service_id}", configured, row.get("status", ""), ", ".join(note_bits)))

        checks.append(self._check("mode", True, config.mode, "serve orchestration mode"))
        checks.append(self._check("model-backend", True, config.model_backend, config.model_endpoint))
        checks.append(self._check("current-user", bool(config.current_user_id), config.current_user_id or "", "login or pass --user"))
        return checks

    @staticmethod
    def _check(name: str, ok: bool, value: str, note: str) -> dict[str, Any]:
        return {"check": name, "ok": ok, "value": value, "note": note}
