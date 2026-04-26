from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from auth_router import _extract_bearer_token, verify_token
from review_service import ReviewService


PROJECT_ROOT = Path(__file__).resolve().parent
SKILL_DB_PATH = PROJECT_ROOT / "skill_registry" / "skill_registry.db"

review_router = APIRouter(prefix="/review", tags=["review"])


class ReviewRejectRequest(BaseModel):
    reason: str | None = None


def _require_jwt(path_user_id: str, authorization: str | None) -> str:
    token = _extract_bearer_token(authorization)
    token_uid = verify_token(token)
    if not token_uid:
        raise HTTPException(status_code=401, detail={"error": "invalid_token"})
    if token_uid != path_user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    return token_uid


def _get_review_service() -> ReviewService:
    return ReviewService()


@review_router.get("/{user_id}/pending")
def list_pending_reviews(
    user_id: str,
    status: str = Query(default="pending", pattern="^(pending|confirmed|dismissed|all)$"),
    lifecycle_status: str = Query(default="all", pattern="^(draft|pending|active|rejected|archived|all)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
):
    _require_jwt(user_id, authorization)
    status_filter = None if status == "all" else status
    return _get_review_service().list_reviews(
        user_id=user_id,
        status=status_filter,
        page=page,
        page_size=page_size,
        lifecycle_status=None if lifecycle_status == "all" else lifecycle_status,
    )


@review_router.get("/{user_id}/{notif_id}")
def get_review_detail(
    user_id: str,
    notif_id: int,
    authorization: str | None = Header(default=None),
):
    _require_jwt(user_id, authorization)
    try:
        return _get_review_service().get_review(user_id, notif_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": exc.args[0]}) from exc


@review_router.put("/{user_id}/{notif_id}/approve")
def approve_review(
    user_id: str,
    notif_id: int,
    authorization: str | None = Header(default=None),
):
    _require_jwt(user_id, authorization)
    try:
        return _get_review_service().approve_review(user_id, notif_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": exc.args[0]}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": "invalid_lifecycle_transition", "message": str(exc)}) from exc


@review_router.put("/{user_id}/{notif_id}/reject")
def reject_review(
    user_id: str,
    notif_id: int,
    payload: ReviewRejectRequest | None = None,
    authorization: str | None = Header(default=None),
):
    _require_jwt(user_id, authorization)
    try:
        return _get_review_service().reject_review(user_id, notif_id, payload.reason if payload else None)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error": exc.args[0]}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"error": "invalid_lifecycle_transition", "message": str(exc)}) from exc
