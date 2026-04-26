from __future__ import annotations

from urllib.parse import urlencode
from urllib.parse import urlparse

from maskclaw_cli.context import ConfigStore, MaskClawConfig
from maskclaw_cli.services.http_client import ApiError, request_json
from maskclaw_cli.services.local_review_service import LocalReviewService


class ReviewClientService:
    def __init__(
        self,
        store: ConfigStore | None = None,
        local_service: LocalReviewService | None = None,
    ) -> None:
        self.store = store or ConfigStore()
        self.local_service = local_service or LocalReviewService()

    def list_pending(
        self,
        user_id: str | None = None,
        status: str = "pending",
        lifecycle_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        config, resolved_user_id = self._resolve_context(user_id)
        if self._should_try_remote(config):
            query_payload = {
                "status": status,
                "page": page,
                "page_size": page_size,
            }
            if lifecycle_status and lifecycle_status != "all":
                query_payload["lifecycle_status"] = lifecycle_status
            query = urlencode(query_payload)
            try:
                return request_json(
                    "GET",
                    f"{config.api_base_url}/review/{resolved_user_id}/pending?{query}",
                    token=config.token,
                )
            except ApiError as exc:
                if not self._should_fallback_to_local(config, exc):
                    raise
        return self.local_service.list_pending(
            resolved_user_id,
            status=status,
            lifecycle_status=lifecycle_status,
            page=page,
            page_size=page_size,
        )

    def show(self, notif_id: int, user_id: str | None = None) -> dict:
        config, resolved_user_id = self._resolve_context(user_id)
        if self._should_try_remote(config):
            try:
                return request_json(
                    "GET",
                    f"{config.api_base_url}/review/{resolved_user_id}/{notif_id}",
                    token=config.token,
                )
            except ApiError as exc:
                if not self._should_fallback_to_local(config, exc):
                    raise
        return self.local_service.show(resolved_user_id, notif_id)

    def approve(self, notif_id: int, user_id: str | None = None) -> dict:
        config, resolved_user_id = self._resolve_context(user_id)
        self._require_remote_write_context(config)
        try:
            return request_json(
                "PUT",
                f"{config.api_base_url}/review/{resolved_user_id}/{notif_id}/approve",
                token=config.token,
            )
        except ApiError as exc:
            raise ValueError(
                "Review write commands require the local API to be online. "
                "Run `maskclaw serve up --mode personal --no-frontend --no-bridge` and login again."
            ) from exc

    def reject(self, notif_id: int, reason: str | None = None, user_id: str | None = None) -> dict:
        config, resolved_user_id = self._resolve_context(user_id)
        self._require_remote_write_context(config)
        payload = {"reason": reason} if reason else None
        try:
            return request_json(
                "PUT",
                f"{config.api_base_url}/review/{resolved_user_id}/{notif_id}/reject",
                payload=payload,
                token=config.token,
            )
        except ApiError as exc:
            raise ValueError(
                "Review write commands require the local API to be online. "
                "Run `maskclaw serve up --mode personal --no-frontend --no-bridge` and login again."
            ) from exc

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
    def _require_remote_write_context(config: MaskClawConfig) -> None:
        if not config.token:
            raise ValueError(
                "Review write commands require a logged-in token. "
                "Run `maskclaw auth login` after starting the local API."
            )

    @staticmethod
    def _should_fallback_to_local(config: MaskClawConfig, exc: ApiError) -> bool:
        if exc.status != 0:
            return False
        parsed = urlparse(config.api_base_url)
        host = (parsed.hostname or "").strip().lower()
        if config.mode == "personal":
            return True
        return host in {"127.0.0.1", "localhost", "::1"}
