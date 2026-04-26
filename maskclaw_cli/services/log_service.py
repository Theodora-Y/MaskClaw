from __future__ import annotations

from urllib.parse import urlencode
from urllib.parse import urlparse

from maskclaw_cli.context import ConfigStore, MaskClawConfig
from maskclaw_cli.services.http_client import ApiError, request_json
from maskclaw_cli.services.local_log_service import LocalLogService


class LogService:
    def __init__(
        self,
        store: ConfigStore | None = None,
        local_service: LocalLogService | None = None,
    ) -> None:
        self.store = store or ConfigStore()
        self.local_service = local_service or LocalLogService()

    def recent(
        self,
        user_id: str | None = None,
        source: str = "timeline",
        event_type: str | None = None,
        log_type: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        config, resolved_user_id = self._resolve_context(user_id)
        if self._should_try_remote(config):
            try:
                if source == "raw":
                    limit = page * page_size
                    query = urlencode({"log_type": log_type, "limit": limit})
                    payload = request_json(
                        "GET",
                        f"{config.api_base_url}/evolution/source/logs/{resolved_user_id}?{query}",
                        token=config.token,
                    )
                    start_idx = (page - 1) * page_size
                    end_idx = start_idx + page_size
                    logs = {}
                    total = 0
                    for name, records in payload.get("logs", {}).items():
                        total += len(records)
                        logs[name] = records[start_idx:end_idx]
                    payload["logs"] = logs
                    payload["pagination"] = {
                        "page": page,
                        "page_size": page_size,
                        "total": total,
                        "has_next": page * page_size < total,
                    }
                    return payload

                query_parts = {
                    "range": "all",
                    "page": page,
                    "page_size": page_size,
                }
                if event_type:
                    query_parts["event_types"] = event_type
                query = urlencode(query_parts)
                return request_json(
                    "GET",
                    f"{config.api_base_url}/evolution/events/{resolved_user_id}?{query}",
                    token=config.token,
                )
            except ApiError as exc:
                if not self._should_fallback_to_local(config, exc):
                    raise

        return self.local_service.recent(
            user_id=resolved_user_id,
            source=source,
            event_type=event_type,
            log_type=log_type,
            page=page,
            page_size=page_size,
        )

    def tail(
        self,
        user_id: str | None = None,
        log_type: str = "all",
        limit: int = 10,
    ) -> dict:
        _, resolved_user_id = self._resolve_context(user_id)
        return self.local_service.tail(
            user_id=resolved_user_id,
            log_type=log_type,
            limit=limit,
        )

    def _resolve_context(self, user_id: str | None = None) -> tuple[MaskClawConfig, str]:
        config = self.store.load()
        resolved_user_id = user_id or config.current_user_id or ""
        if not resolved_user_id:
            raise ValueError("No user selected. Run `maskclaw auth login` or `maskclaw auth use-user` first.")
        if user_id and config.current_user_id and user_id != config.current_user_id:
            raise ValueError(
                f"Current token belongs to {config.current_user_id}. Re-login before operating as {user_id}."
            )
        return config, resolved_user_id

    @staticmethod
    def _should_try_remote(config: MaskClawConfig) -> bool:
        return bool(config.token)

    @staticmethod
    def _should_fallback_to_local(config: MaskClawConfig, exc: ApiError) -> bool:
        if exc.status != 0:
            return False
        parsed = urlparse(config.api_base_url)
        host = (parsed.hostname or "").strip().lower()
        if config.mode == "personal":
            return True
        return host in {"127.0.0.1", "localhost", "::1"}
