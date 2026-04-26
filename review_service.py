from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skill_registry.skill_db import SkillDB


PROJECT_ROOT = Path(__file__).resolve().parent
USER_SKILLS_ROOT = PROJECT_ROOT / "user_skills"
SKILL_DB_PATH = PROJECT_ROOT / "skill_registry" / "skill_registry.db"


class ReviewService:
    def __init__(
        self,
        db: SkillDB | None = None,
        user_skills_root: str | Path | None = None,
    ) -> None:
        self.db = db or SkillDB(db_path=str(SKILL_DB_PATH))
        self.user_skills_root = Path(user_skills_root or USER_SKILLS_ROOT)

    def list_reviews(
        self,
        user_id: str,
        status: str | None = "pending",
        page: int = 1,
        page_size: int = 20,
        lifecycle_status: str | None = None,
    ) -> dict[str, Any]:
        items, total = self.db.get_notifications(
            user_id=user_id,
            status=status,
            page=1,
            page_size=1000,
        )
        unread = self.db.get_unread_count(user_id)
        enriched = [self._build_review_item(user_id, item, include_preview=False) for item in items]
        if lifecycle_status and lifecycle_status != "all":
            enriched = [item for item in enriched if item.get("target", {}).get("current_state") == lifecycle_status]
        total = len(enriched)
        offset = max(page - 1, 0) * page_size
        enriched = enriched[offset : offset + page_size]
        return {
            "user_id": user_id,
            "items": enriched,
            "total": total,
            "unread": unread,
            "page": page,
            "page_size": page_size,
            "status": status or "all",
            "lifecycle_status": lifecycle_status or "all",
        }

    def get_review(self, user_id: str, notif_id: int) -> dict[str, Any]:
        notification = self._require_notification(user_id, notif_id)
        return self._build_review_item(user_id, notification, include_preview=True)

    def approve_review(self, user_id: str, notif_id: int) -> dict[str, Any]:
        notification = self._require_notification(user_id, notif_id)
        skill_sync = self._apply_approve(user_id, notification)
        self.db.set_notification_status(user_id, notif_id, "confirmed", mark_read=True)
        refreshed = self._require_notification(user_id, notif_id)
        return {
            "ok": True,
            "notif_id": notif_id,
            "status": "confirmed",
            "notification": refreshed,
            "skill_sync": skill_sync,
        }

    def reject_review(self, user_id: str, notif_id: int, reason: str | None = None) -> dict[str, Any]:
        notification = self._require_notification(user_id, notif_id)
        skill_sync = self._apply_reject(user_id, notification, reason)
        self.db.set_notification_status(user_id, notif_id, "dismissed", mark_read=True)
        refreshed = self._require_notification(user_id, notif_id)
        return {
            "ok": True,
            "notif_id": notif_id,
            "status": "dismissed",
            "notification": refreshed,
            "skill_sync": skill_sync,
        }

    def _apply_approve(self, user_id: str, notification: dict[str, Any]) -> dict[str, Any]:
        target = self._resolve_target(
            user_id,
            notification.get("skill_name"),
            notification.get("skill_version"),
        )
        if target["source_kind"] == "none":
            return {
                "applied": False,
                "source_kind": "none",
                "action": "notification_only",
                "warning": "Notification confirmed, but no skill/SOP target could be resolved.",
            }

        if target["source_kind"] == "skills":
            if target["current_state"] not in {"pending", "draft"}:
                raise ValueError(
                    f"Only draft/pending skills can be approved. Current state: {target['current_state']}."
                )
            restored = self.db.restore_skill(
                user_id,
                str(target["skill_name"]),
                str(target["version"]),
                str(self.user_skills_root),
            )
            return {
                "applied": restored,
                "source_kind": "skills",
                "action": "activated" if restored else "activate_failed",
                "skill_name": target["skill_name"],
                "version": target["version"],
            }

        if target["current_state"] not in {"pending", "draft"}:
            raise ValueError(
                f"Only draft/pending SOP versions can be approved. Current state: {target['current_state']}."
            )
        restored = self.db.activate_sop_version(
            user_id,
            str(target["skill_name"]),
            str(target["version"]),
        )
        return {
            "applied": restored,
            "source_kind": "sop_version",
            "action": "activated" if restored else "activate_failed",
            "skill_name": target["skill_name"],
            "version": target["version"],
        }

    def _apply_reject(
        self,
        user_id: str,
        notification: dict[str, Any],
        reason: str | None = None,
    ) -> dict[str, Any]:
        target = self._resolve_target(
            user_id,
            notification.get("skill_name"),
            notification.get("skill_version"),
        )
        reject_reason = (reason or "review_rejected").strip() or "review_rejected"
        if target["source_kind"] == "none":
            return {
                "applied": False,
                "source_kind": "none",
                "action": "notification_only",
                "warning": "Notification dismissed, but no skill/SOP target could be resolved.",
            }

        if target["source_kind"] == "skills":
            if target["current_state"] not in {"pending", "draft"}:
                raise ValueError(
                    f"Only draft/pending skills can be rejected. Current state: {target['current_state']}."
                )
            rejected = self.db.set_skill_lifecycle_status(
                user_id,
                str(target["skill_name"]),
                str(target["version"]),
                status="rejected",
                reason=reject_reason,
            )
            return {
                "applied": rejected,
                "source_kind": "skills",
                "action": "rejected",
                "skill_name": target["skill_name"],
                "version": target["version"],
            }

        if target["current_state"] not in {"pending", "draft"}:
            raise ValueError(
                f"Only draft/pending SOP versions can be rejected. Current state: {target['current_state']}."
            )
        archived = self.db.set_sop_version_status(
            user_id,
            str(target["skill_name"]),
            str(target["version"]),
            status="rejected",
            reason=reject_reason,
        )
        return {
            "applied": archived,
            "source_kind": "sop_version",
            "action": "rejected",
            "skill_name": target["skill_name"],
            "version": target["version"],
        }

    def _require_notification(self, user_id: str, notif_id: int) -> dict[str, Any]:
        notification = self.db.get_notification(user_id, notif_id)
        if not notification:
            raise KeyError("notification_not_found")
        return notification

    def _build_review_item(
        self,
        user_id: str,
        notification: dict[str, Any],
        include_preview: bool,
    ) -> dict[str, Any]:
        target = self._resolve_target(
            user_id,
            notification.get("skill_name"),
            notification.get("skill_version"),
        )
        payload = {
            "notification": notification,
            "target": target,
        }
        if include_preview:
            payload["action_preview"] = self._build_action_preview(target)
        return payload

    def _build_action_preview(self, target: dict[str, Any]) -> dict[str, Any]:
        if target["source_kind"] == "none":
            return {
                "approve": "Confirm notification only.",
                "reject": "Dismiss notification only.",
            }
        if target["source_kind"] == "skills":
            if target["current_state"] in {"pending", "draft"}:
                return {
                    "approve": "Activate this candidate skill and move it into the active skill directory.",
                    "reject": "Reject this candidate skill and keep it in the review area.",
                }
            return {
                "approve": "This review item is no longer pending activation.",
                "reject": "This review item is no longer pending rejection.",
            }
        if target["current_state"] in {"pending", "draft"}:
            return {
                "approve": "Activate this candidate SOP version.",
                "reject": "Reject this candidate SOP version and keep it out of the active set.",
            }
        return {
            "approve": "This review item is no longer pending activation.",
            "reject": "This review item is no longer pending rejection.",
        }

    def _resolve_target(
        self,
        user_id: str,
        skill_name: Any,
        version: Any,
    ) -> dict[str, Any]:
        skill_name_text = str(skill_name or "").strip()
        version_text = str(version or "").strip()
        if not skill_name_text or not version_text:
            return {
                "source_kind": "none",
                "exists": False,
                "skill_name": skill_name_text,
                "version": version_text,
                "current_state": "unknown",
                "summary": {},
                "skill_md_preview": "",
                "rules_preview": {},
            }

        detail = self.db.get_skill_detail(user_id, skill_name_text, version_text)
        if not detail:
            return {
                "source_kind": "none",
                "exists": False,
                "skill_name": skill_name_text,
                "version": version_text,
                "current_state": "missing",
                "summary": {},
                "skill_md_preview": "",
                "rules_preview": {},
            }

        source_kind = str(detail.get("source_table") or "none")
        current_state = str(detail.get("status") or "unknown")

        rules_preview = self._normalize_rules(detail.get("rules_json_content"))
        skill_md_preview = self._trim_preview(str(detail.get("skill_md_content") or ""))
        summary = {
            "skill_name": skill_name_text,
            "version": version_text,
            "source_kind": source_kind,
            "current_state": current_state,
            "path": str(detail.get("path") or ""),
            "storage_bucket": detail.get("storage_bucket") or "unknown",
            "scene": detail.get("scene") or detail.get("app_context") or "",
            "strategy": detail.get("strategy") or detail.get("task_description") or "",
            "confidence": detail.get("confidence"),
            "superseded_by": detail.get("superseded_by"),
            "archived_reason": detail.get("archived_reason"),
        }
        return {
            "source_kind": source_kind,
            "exists": True,
            "skill_name": skill_name_text,
            "version": version_text,
            "current_state": current_state,
            "summary": summary,
            "storage_bucket": summary["storage_bucket"],
            "skill_md_preview": skill_md_preview,
            "rules_preview": rules_preview,
        }

    @staticmethod
    def _normalize_rules(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                data = json.loads(value)
                return data if isinstance(data, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _trim_preview(text: str, limit: int = 600) -> str:
        normalized = text.strip()
        if len(normalized) <= limit:
            return normalized
        return normalized[: max(0, limit - 3)] + "..."
