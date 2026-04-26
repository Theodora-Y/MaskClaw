from __future__ import annotations

from dataclasses import asdict
from typing import Any

from maskclaw_cli.context import ConfigStore, MaskClawConfig, ensure_service_catalog
from maskclaw_cli.services.runtime_service import probe_http


SUPPORTED_BACKENDS = {
    "minicpm": {
        "description": "Enterprise or lab MiniCPM service, usually running inside an intranet.",
        "default_endpoint": "http://127.0.0.1:8000",
    },
    "ollama": {
        "description": "Local Ollama-compatible model service, commonly used with gemma:2b.",
        "default_endpoint": "http://127.0.0.1:8005",
    },
    "gemma": {
        "description": "Alias for a local Gemma backend. Prefer ollama --model gemma:2b for now.",
        "default_endpoint": "http://127.0.0.1:8005",
    },
    "none": {
        "description": "Disable model startup. Useful for CLI-only skill audit work.",
        "default_endpoint": "",
    },
}


class ModelService:
    def __init__(self, store: ConfigStore | None = None) -> None:
        self.store = store or ConfigStore()

    def list_backends(self) -> list[dict[str, str]]:
        return [
            {
                "backend": name,
                "endpoint": meta["default_endpoint"],
                "description": meta["description"],
            }
            for name, meta in SUPPORTED_BACKENDS.items()
        ]

    def use_backend(
        self,
        backend: str,
        endpoint: str | None = None,
        model_name: str | None = None,
        mode: str | None = None,
    ) -> tuple[MaskClawConfig, str]:
        if backend not in SUPPORTED_BACKENDS:
            supported = ", ".join(SUPPORTED_BACKENDS)
            raise ValueError(f"Unsupported backend '{backend}'. Supported: {supported}")
        config = self.store.load()
        config.model_backend = backend
        config.model_endpoint = endpoint if endpoint is not None else SUPPORTED_BACKENDS[backend]["default_endpoint"]
        if model_name:
            config.model_name = model_name
        if mode:
            config.mode = mode
        config = ensure_service_catalog(config)
        path = self.store.save(config)
        return config, str(path)

    def status(self) -> dict[str, Any]:
        config = self.store.load()
        alive = probe_http(config.model_endpoint) if config.model_endpoint else False
        return {
            **asdict(config),
            "model_alive": alive,
        }
