from __future__ import annotations

from pathlib import Path
from typing import Any

from maskclaw_cli.context import PROJECT_ROOT, ensure_project_root_on_path

ensure_project_root_on_path()

from review_service import ReviewService as BackendReviewService
from skill_registry.skill_db import SkillDB


class LocalReviewService:
    """Local/offline review operations for personal CLI usage.

    This avoids a hard dependency on the API process when the CLI is operating
    against the local workspace data layout.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self.db_path = self.project_root / "skill_registry" / "skill_registry.db"
        self.user_skills_root = self.project_root / "user_skills"

    def list_pending(
        self,
        user_id: str,
        status: str = "pending",
        lifecycle_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        service = self._service()
        payload = service.list_reviews(
            user_id=user_id,
            status=None if status == "all" else status,
            page=page,
            page_size=page_size,
            lifecycle_status=None if lifecycle_status == "all" else lifecycle_status,
        )
        payload["transport"] = "local"
        return payload

    def show(self, user_id: str, notif_id: int) -> dict[str, Any]:
        payload = self._service().get_review(user_id, notif_id)
        payload["transport"] = "local"
        return payload

    def approve(self, user_id: str, notif_id: int) -> dict[str, Any]:
        payload = self._service().approve_review(user_id, notif_id)
        payload["transport"] = "local"
        return payload

    def reject(self, user_id: str, notif_id: int, reason: str | None = None) -> dict[str, Any]:
        payload = self._service().reject_review(user_id, notif_id, reason)
        payload["transport"] = "local"
        return payload

    def _service(self) -> BackendReviewService:
        db = SkillDB(db_path=str(self.db_path))
        return BackendReviewService(db=db, user_skills_root=self.user_skills_root)
