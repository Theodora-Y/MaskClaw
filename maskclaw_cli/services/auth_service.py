from __future__ import annotations

from maskclaw_cli.context import ConfigStore, MaskClawConfig
from maskclaw_cli.services.http_client import request_json


class AuthService:
    def __init__(self, store: ConfigStore | None = None) -> None:
        self.store = store or ConfigStore()

    def login(self, email: str, password: str, api_base_url: str | None = None) -> tuple[MaskClawConfig, str]:
        config = self.store.load()
        if api_base_url:
            config.api_base_url = api_base_url.rstrip("/")
        data = request_json(
            "POST",
            f"{config.api_base_url}/auth/login",
            {"email": email, "password": password},
        )
        config.current_user_id = str(data.get("user_id") or "")
        config.username = str(data.get("username") or "")
        config.token = str(data.get("token") or "")
        path = self.store.save(config)
        return config, str(path)

    def whoami(self) -> MaskClawConfig:
        return self.store.load()

    def logout(self) -> str:
        return str(self.store.clear_auth())

    def use_user(self, user_id: str, username: str | None = None) -> tuple[MaskClawConfig, str]:
        config = self.store.load()
        config.current_user_id = user_id
        config.username = username or user_id
        config.token = None
        path = self.store.save(config)
        return config, str(path)
