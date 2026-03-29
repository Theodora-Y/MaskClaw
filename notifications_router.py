"""Notifications Router - 系统通知 CRUD 接口（JWT 认证）。

接口清单：
    GET  /notifications/{user_id}                     → 获取通知列表
    PUT  /notifications/{user_id}/{notif_id}/read    → 标记单条已读
    PUT  /notifications/{user_id}/read-all           → 全部标记已读
    PUT  /notifications/{user_id}/{notif_id}/confirm → 确认通知
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jwt
from fastapi import APIRouter, Header, HTTPException, Query

# ── 与 auth_router.py 共用同一 JWT 配置 ──────────────────────
from auth_router import JWT_SECRET, verify_token, _extract_bearer_token

PROJECT_ROOT = Path(__file__).resolve().parent
SKILL_DB_PATH = PROJECT_ROOT / "skill_registry" / "skill_registry.db"

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


# ──────────────────── 认证工具（复用 auth_router）────────────────────


def _require_jwt(path_user_id: str, authorization: str | None) -> str:
    """验证 Bearer token，user_id 必须匹配路径参数。"""
    token = _extract_bearer_token(authorization)
    token_uid = verify_token(token)
    if not token_uid:
        raise HTTPException(status_code=401, detail={"error": "invalid_token"})
    if token_uid != path_user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    return token_uid


def _get_skill_db():
    from skill_registry.skill_db import SkillDB
    return SkillDB(db_path=str(SKILL_DB_PATH))


# ──────────────────── 接口实现 ────────────────────

@notifications_router.get("/{user_id}")
def get_notifications(
    user_id: str,
    status: str | None = Query(default=None, description="pending | confirmed | dismissed"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
):
    """
    获取用户通知列表。

    响应：
    {
      "user_id": "demo_UserC",
      "items": [NotificationRecord, ...],
      "total": 10,
      "unread": 5,
      "page": 1,
      "page_size": 20
    }
    """
    _require_jwt(user_id, authorization)

    db = _get_skill_db()
    items, total = db.get_notifications(
        user_id=user_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    unread = db.get_unread_count(user_id)

    return {
        "user_id": user_id,
        "items": items,
        "total": total,
        "unread": unread,
        "page": page,
        "page_size": page_size,
    }


@notifications_router.put("/{user_id}/{notif_id}/read")
def mark_notification_read(
    user_id: str,
    notif_id: int,
    authorization: str | None = Header(default=None),
):
    """
    标记单条通知为已读。

    响应：{ "ok": true, "notif_id": 5 }
    """
    _require_jwt(user_id, authorization)

    db = _get_skill_db()
    ok = db.mark_notification_read(user_id, notif_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "notification_not_found"})
    return {"ok": True, "notif_id": notif_id}


@notifications_router.put("/{user_id}/read-all")
def mark_all_notifications_read(
    user_id: str,
    authorization: str | None = Header(default=None),
):
    """
    全部标记为已读。

    响应：{ "ok": true, "count": 5 }
    """
    _require_jwt(user_id, authorization)

    db = _get_skill_db()
    count = db.mark_all_notifications_read(user_id)
    return {"ok": True, "count": count}


@notifications_router.put("/{user_id}/{notif_id}/confirm")
def confirm_notification(
    user_id: str,
    notif_id: int,
    authorization: str | None = Header(default=None),
):
    """
    确认通知（标记 confirmed + 已读）。

    响应：{ "ok": true, "notif_id": 5, "status": "confirmed" }
    """
    _require_jwt(user_id, authorization)

    db = _get_skill_db()
    ok = db.mark_notification_read(user_id, notif_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "notification_not_found"})
    return {"ok": True, "notif_id": notif_id, "status": "confirmed"}


@notifications_router.put("/{user_id}/{notif_id}/dismiss")
def dismiss_notification(
    user_id: str,
    notif_id: int,
    authorization: str | None = Header(default=None),
):
    """
    拒绝/忽略通知。

    响应：{ "ok": true, "notif_id": 5, "status": "dismissed" }
    """
    _require_jwt(user_id, authorization)

    db = _get_skill_db()
    ok = db.dismiss_notification(user_id, notif_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "notification_not_found"})
    return {"ok": True, "notif_id": notif_id, "status": "dismissed"}
