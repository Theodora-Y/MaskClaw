from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from maskclaw_cli.context import PROJECT_ROOT, ConfigStore, MaskClawConfig


LOG_DIR = PROJECT_ROOT / "logs"
SERVICE_ORDER = [
    "minicpm-privacy",
    "minicpm-skillgen",
    "minicpm-feedback",
    "ollama-proxy",
    "api",
    "evolution-daemon",
    "bridge-autoglm",
    "frontend",
]
REQUIRED_MODEL_CAPABILITIES = ("privacy", "skillgen", "feedback")


@dataclass
class ServiceSpec:
    service: str
    enabled: bool
    managed: bool
    required: bool
    cwd: Path | None
    command: list[str]
    endpoint: str
    healthcheck: str
    depends_on: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    log_file: Path | None = None
    pid_file: Path | None = None
    port: int | None = None


def probe_port(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_http(endpoint: str, timeout: float = 0.5) -> bool:
    if not endpoint:
        return False
    parsed = urlparse(endpoint)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return probe_port(host, port, timeout=timeout)


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return False
        output = (result.stdout or "").strip()
        return bool(output and not output.startswith("INFO:") and f'"{pid}"' in output)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _parse_port(endpoint: str) -> int | None:
    if not endpoint:
        return None
    parsed = urlparse(endpoint)
    if parsed.port:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    if parsed.scheme == "http":
        return 80
    return None


def _normalize_cwd(value: str | Path | None) -> Path | None:
    if not value:
        return None
    return Path(value)


def _normalize_command(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


class RuntimeService:
    def __init__(self, store: ConfigStore | None = None) -> None:
        self.store = store or ConfigStore()

    def _load_config(self) -> MaskClawConfig:
        return self.store.load()

    def _capability_bindings(self, config: MaskClawConfig) -> dict[str, str]:
        raw = config.model_roles if isinstance(config.model_roles, dict) else {}
        return {name: str(raw.get(name) or "") for name in REQUIRED_MODEL_CAPABILITIES}

    def _required_service_ids(
        self,
        config: MaskClawConfig,
        *,
        include_frontend: bool,
        include_bridge: bool,
    ) -> set[str]:
        required = {"api", "evolution-daemon"}
        if include_bridge:
            required.add("bridge-autoglm")
        if include_frontend:
            required.add("frontend")
        for service_id in self._capability_bindings(config).values():
            if service_id:
                required.add(service_id)
        return required

    def _dynamic_depends_on(
        self,
        config: MaskClawConfig,
        *,
        service_id: str,
        include_frontend: bool,
        include_bridge: bool,
    ) -> list[str]:
        role_bindings = self._capability_bindings(config)
        if service_id == "evolution-daemon":
            deps = ["api"]
            if role_bindings.get("skillgen"):
                deps.append(role_bindings["skillgen"])
            return list(dict.fromkeys(dep for dep in deps if dep))
        if service_id == "bridge-autoglm":
            deps = ["api"]
            if role_bindings.get("privacy"):
                deps.append(role_bindings["privacy"])
            return list(dict.fromkeys(dep for dep in deps if dep))
        if service_id == "frontend":
            deps = ["api"]
            if include_bridge:
                deps.append("bridge-autoglm")
            return deps
        return []

    def _log_file_for(self, service_id: str) -> Path:
        names = {
            "api": "api_server.log",
            "evolution-daemon": "evolution_daemon.log",
            "bridge-autoglm": "autoglm_bridge.log",
            "frontend": "frontend.log",
            "minicpm-privacy": "minicpm_privacy.log",
            "minicpm-skillgen": "minicpm_skillgen.log",
            "minicpm-feedback": "minicpm_feedback.log",
            "ollama-proxy": "ollama_proxy.log",
        }
        return LOG_DIR / names.get(service_id, f"{service_id.replace('-', '_')}.log")

    def _pid_file_for(self, service_id: str) -> Path:
        names = {
            "api": "api_server.pid",
            "evolution-daemon": "evolution_daemon.pid",
            "bridge-autoglm": "autoglm_bridge.pid",
            "frontend": "frontend.pid",
            "minicpm-privacy": "minicpm_privacy.pid",
            "minicpm-skillgen": "minicpm_skillgen.pid",
            "minicpm-feedback": "minicpm_feedback.pid",
            "ollama-proxy": "ollama_proxy.pid",
        }
        return LOG_DIR / names.get(service_id, f"{service_id.replace('-', '_')}.pid")

    def _service_specs(
        self,
        *,
        include_frontend: bool = True,
        include_bridge: bool = True,
        status_view: bool = False,
    ) -> list[ServiceSpec]:
        config = self._load_config()
        required_ids = self._required_service_ids(
            config,
            include_frontend=include_frontend if not status_view else True,
            include_bridge=include_bridge if not status_view else True,
        )
        capability_by_service: dict[str, list[str]] = {}
        for capability, service_id in self._capability_bindings(config).items():
            if service_id:
                capability_by_service.setdefault(service_id, []).append(capability)

        ordered_ids = list(dict.fromkeys(SERVICE_ORDER + list(config.service_roles.keys())))
        specs: list[ServiceSpec] = []
        for service_id in ordered_ids:
            raw = config.service_roles.get(service_id)
            if not isinstance(raw, dict):
                continue

            enabled = bool(raw.get("enabled", True))
            if not status_view:
                if service_id == "frontend" and not include_frontend:
                    enabled = False
                if service_id == "bridge-autoglm" and not include_bridge:
                    enabled = False
                if service_id not in required_ids:
                    enabled = False

            depends_on = raw.get("depends_on") or self._dynamic_depends_on(
                config,
                service_id=service_id,
                include_frontend=include_frontend,
                include_bridge=include_bridge,
            )
            spec = ServiceSpec(
                service=service_id,
                enabled=enabled,
                managed=bool(raw.get("managed", False)),
                required=service_id in required_ids and enabled,
                cwd=_normalize_cwd(raw.get("cwd")),
                command=_normalize_command(raw.get("command")),
                endpoint=str(raw.get("endpoint") or ""),
                healthcheck=str(raw.get("healthcheck") or "tcp"),
                depends_on=[str(item) for item in depends_on],
                capabilities=capability_by_service.get(service_id, []),
                log_file=self._log_file_for(service_id),
                pid_file=self._pid_file_for(service_id),
            )
            spec.port = _parse_port(spec.endpoint)
            specs.append(spec)
        return specs

    def _is_ready_status(self, status: str) -> bool:
        return status in {"running", "started", "already-running", "external-running", "dry-run"}

    def _read_pid(self, path: Path | None) -> int | None:
        if not path or not path.exists():
            return None
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except Exception:
            return None

    def _probe_spec(self, spec: ServiceSpec) -> bool:
        if spec.endpoint:
            return probe_http(spec.endpoint)
        pid = self._read_pid(spec.pid_file)
        return _pid_alive(pid) if pid else False

    def _build_env(self, spec: ServiceSpec) -> dict[str, str]:
        env = os.environ.copy()
        config = self._load_config()
        if spec.service == "bridge-autoglm":
            env["MASKCLAW_OPEN_AUTOGLM_DIR"] = config.autoglm_dir

        role_bindings = self._capability_bindings(config)
        service_roles = config.service_roles
        privacy_service = service_roles.get(role_bindings.get("privacy", ""), {})
        skillgen_service = service_roles.get(role_bindings.get("skillgen", ""), {})
        feedback_service = service_roles.get(role_bindings.get("feedback", ""), {})

        privacy_endpoint = str(privacy_service.get("endpoint") or "")
        skillgen_endpoint = str(skillgen_service.get("endpoint") or "")
        feedback_endpoint = str(feedback_service.get("endpoint") or "")

        if privacy_endpoint:
            env["MASKCLAW_MINICPM_PRIVACY_ENDPOINT"] = privacy_endpoint
        if skillgen_endpoint:
            env["MASKCLAW_MINICPM_SKILLGEN_ENDPOINT"] = skillgen_endpoint
        if feedback_endpoint:
            env["MASKCLAW_MINICPM_FEEDBACK_ENDPOINT"] = feedback_endpoint
        if spec.service == "ollama-proxy":
            parsed = urlparse(spec.endpoint)
            if parsed.port:
                env["OLLAMA_PROXY_PORT"] = str(parsed.port)
        return env

    def _command_for_start(self, spec: ServiceSpec) -> list[str]:
        command = list(spec.command)
        if spec.service == "evolution-daemon":
            config = self._load_config()
            role_bindings = self._capability_bindings(config)
            skillgen_service = config.service_roles.get(role_bindings.get("skillgen", ""), {})
            skillgen_endpoint = str(skillgen_service.get("endpoint") or "")
            if skillgen_endpoint and "--minicpm-url" not in command:
                command.extend(["--minicpm-url", skillgen_endpoint])
        return command

    def _base_row(self, spec: ServiceSpec) -> dict[str, Any]:
        return {
            "service": spec.service,
            "enabled": spec.enabled,
            "required": spec.required,
            "managed": spec.managed,
            "endpoint": spec.endpoint,
            "healthcheck": spec.healthcheck,
            "depends_on": ",".join(spec.depends_on),
            "capabilities": ",".join(spec.capabilities),
            "port": spec.port or "",
            "log": str(spec.log_file) if spec.log_file else "",
            "cwd": str(spec.cwd) if spec.cwd else "",
            "command": " ".join(spec.command),
        }

    def status(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        raw_rows: dict[str, dict[str, Any]] = {}
        for spec in self._service_specs(status_view=True):
            pid = self._read_pid(spec.pid_file)
            pid_alive = _pid_alive(pid) if pid else False
            port_alive = probe_http(spec.endpoint) if spec.endpoint else False
            row = self._base_row(spec)
            row.update(
                {
                    "pid": pid or "",
                    "pid_alive": pid_alive,
                    "port_alive": port_alive,
                    "status": self._infer_status(spec, port_alive=port_alive, pid_alive=pid_alive, pid=pid),
                    "error": self._log_error_summary(spec.log_file) if pid and not pid_alive else "",
                }
            )
            raw_rows[spec.service] = row

        for service_id, row in raw_rows.items():
            depends_on = [dep for dep in row["depends_on"].split(",") if dep]
            if depends_on:
                depends_ready = all(self._is_ready_status(raw_rows.get(dep, {}).get("status", "")) for dep in depends_on)
                row["depends_ready"] = depends_ready
                if row["status"] in {"running", "external-running"} and not depends_ready:
                    row["status"] = "degraded"
            else:
                row["depends_ready"] = True
            rows.append(row)
        return rows

    def _infer_status(self, spec: ServiceSpec, *, port_alive: bool, pid_alive: bool, pid: int | None) -> str:
        if not spec.enabled:
            return "disabled"
        if spec.managed:
            if spec.healthcheck == "process":
                if pid_alive:
                    return "running"
                if pid:
                    return "failed"
                return "stopped"
            if port_alive:
                return "running"
            if pid_alive:
                return "starting"
            if pid:
                return "failed"
            return "stopped"
        if not spec.endpoint:
            return "unconfigured"
        return "external-running" if port_alive else "external-missing"

    def _preflight_errors(self, specs: list[ServiceSpec], config: MaskClawConfig) -> list[dict[str, Any]]:
        errors: list[dict[str, Any]] = []
        service_map = {spec.service: spec for spec in specs}
        for capability in REQUIRED_MODEL_CAPABILITIES:
            service_id = str(config.model_roles.get(capability) or "")
            if not service_id:
                errors.append(
                    {
                        "service": f"role:{capability}",
                        "status": "missing-binding",
                        "required": True,
                        "managed": False,
                        "error": f"Model role '{capability}' is not bound to any service in mode={config.mode}.",
                    }
                )
                continue
            bound = service_map.get(service_id)
            if bound is None:
                errors.append(
                    {
                        "service": f"role:{capability}",
                        "status": "unknown-service",
                        "required": True,
                        "managed": False,
                        "error": f"Model role '{capability}' points to unknown service '{service_id}'.",
                    }
                )
                continue
            if not bound.enabled:
                errors.append(
                    {
                        "service": f"role:{capability}",
                        "status": "disabled-binding",
                        "required": True,
                        "managed": bound.managed,
                        "error": f"Model role '{capability}' is bound to disabled service '{service_id}'.",
                    }
                )
                continue
            if not bound.managed and not bound.endpoint:
                errors.append(
                    {
                        "service": f"role:{capability}",
                        "status": "unconfigured-endpoint",
                        "required": True,
                        "managed": False,
                        "error": f"External service '{service_id}' for role '{capability}' has no endpoint configured.",
                    }
                )
        return errors

    def start(
        self,
        no_frontend: bool = False,
        no_bridge: bool = False,
        dry_run: bool = False,
        only: set[str] | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        config = self._load_config()
        specs = [
            spec
            for spec in self._service_specs(include_frontend=not no_frontend, include_bridge=not no_bridge)
            if spec.enabled and (only is None or spec.service in only)
        ]

        results: list[dict[str, Any]] = []
        ok = True

        if dry_run:
            for spec in specs:
                row = self._base_row(spec)
                row["status"] = "dry-run"
                results.append(row)
            return results, True

        preflight = self._preflight_errors(specs, config) if only is None else []
        broken_roles = {
            row["service"].split(":", 1)[1]
            for row in preflight
            if isinstance(row.get("service"), str) and row["service"].startswith("role:")
        }
        if preflight:
            results.extend(preflight)
            ok = False

        service_states: dict[str, str] = {}
        for spec in specs:
            if spec.service == "evolution-daemon" and broken_roles:
                row = self._base_row(spec)
                row.update(
                    {
                        "status": "blocked-config",
                        "error": f"Missing required model role bindings: {', '.join(sorted(broken_roles))}",
                    }
                )
                results.append(row)
                service_states[spec.service] = row["status"]
                if spec.required:
                    ok = False
                continue
            if spec.service == "bridge-autoglm" and {"privacy", "feedback"} & broken_roles:
                row = self._base_row(spec)
                row.update(
                    {
                        "status": "blocked-config",
                        "error": f"Missing required model role bindings: {', '.join(sorted({'privacy', 'feedback'} & broken_roles))}",
                    }
                )
                results.append(row)
                service_states[spec.service] = row["status"]
                if spec.required:
                    ok = False
                continue
            dependency_errors = [dep for dep in spec.depends_on if service_states.get(dep) and not self._is_ready_status(service_states[dep])]
            if dependency_errors:
                row = self._base_row(spec)
                row.update(
                    {
                        "status": "blocked-dependency",
                        "error": f"Dependencies not ready: {', '.join(dependency_errors)}",
                    }
                )
                results.append(row)
                service_states[spec.service] = row["status"]
                if spec.required:
                    ok = False
                continue

            if not spec.managed:
                alive = self._probe_spec(spec)
                row = self._base_row(spec)
                if not spec.endpoint:
                    row.update({"status": "unconfigured", "error": "No endpoint configured for external service."})
                    ok = False if spec.required else ok
                else:
                    row["status"] = "external-running" if alive else "external-missing"
                    if spec.required and not alive:
                        ok = False
                results.append(row)
                service_states[spec.service] = row["status"]
                continue

            if spec.cwd is None or not spec.cwd.exists():
                row = self._base_row(spec)
                row.update({"status": "missing-cwd", "error": f"Working directory not found: {spec.cwd}"})
                results.append(row)
                service_states[spec.service] = row["status"]
                if spec.required:
                    ok = False
                continue

            if not spec.command:
                row = self._base_row(spec)
                row.update({"status": "missing-command", "error": "Managed service has no command configured."})
                results.append(row)
                service_states[spec.service] = row["status"]
                if spec.required:
                    ok = False
                continue

            if self._probe_spec(spec):
                row = self._base_row(spec)
                row["status"] = "already-running"
                results.append(row)
                service_states[spec.service] = row["status"]
                continue

            log_file = spec.log_file or (LOG_DIR / f"{spec.service}.log")
            pid_file = spec.pid_file or (LOG_DIR / f"{spec.service}.pid")
            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

            command = self._command_for_start(spec)
            with log_file.open("w", encoding="utf-8") as log:
                process = subprocess.Popen(
                    command,
                    cwd=str(spec.cwd),
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    creationflags=creationflags,
                    env=self._build_env(spec),
                )
            pid_file.write_text(str(process.pid), encoding="utf-8")
            state = self._wait_for_start(process, spec)
            if state["status"] == "start-failed" and pid_file.exists():
                pid_file.unlink()
            row = self._base_row(spec)
            row.update(
                {
                    "status": state["status"],
                    "error": state.get("error", ""),
                    "pid": process.pid,
                    "log": str(log_file),
                    "command": " ".join(command),
                }
            )
            results.append(row)
            service_states[spec.service] = row["status"]
            if spec.required and not self._is_ready_status(row["status"]):
                ok = False

        return results, ok

    def stop(self, only: set[str] | None = None) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for spec in self._service_specs(status_view=True):
            if only is not None and spec.service not in only:
                continue
            if not spec.managed:
                row = self._base_row(spec)
                row.update({"status": "external-unmanaged"})
                results.append(row)
                continue
            pid = self._read_pid(spec.pid_file)
            if not pid:
                results.append({"service": spec.service, "status": "no-pid"})
                continue
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                else:
                    os.kill(pid, signal.SIGTERM)
                results.append({"service": spec.service, "status": "stopped", "pid": pid})
            except Exception as exc:
                results.append({"service": spec.service, "status": "stop-failed", "pid": pid, "error": str(exc)})
            if spec.pid_file and spec.pid_file.exists():
                spec.pid_file.unlink()
        return results

    def _wait_for_start(self, process: subprocess.Popen[str], spec: ServiceSpec, timeout: float = 5.0) -> dict[str, Any]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if spec.endpoint and probe_http(spec.endpoint):
                return {"status": "started"}
            if spec.healthcheck == "process" and process.poll() is None:
                return {"status": "started"}
            log_summary = self._log_error_summary(spec.log_file)
            if "Uvicorn running on" in log_summary or "Application startup complete." in log_summary:
                return {"status": "started"}
            if process.poll() is not None:
                return {
                    "status": "start-failed",
                    "error": log_summary or f"Process exited with code {process.returncode}",
                }
            time.sleep(0.2)

        if process.poll() is None:
            if spec.endpoint and not probe_http(spec.endpoint):
                return {"status": "starting", "error": self._log_error_summary(spec.log_file)}
            return {"status": "started"}

        return {
            "status": "start-failed",
            "error": self._log_error_summary(spec.log_file) or f"Process exited with code {process.returncode}",
        }

    @staticmethod
    def _log_error_summary(log_file: Path | None, max_lines: int = 8) -> str:
        if not log_file or not log_file.exists():
            return ""
        try:
            lines = [line.strip() for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
        except Exception:
            return ""
        if not lines:
            return ""
        return " | ".join(lines[-max_lines:])
