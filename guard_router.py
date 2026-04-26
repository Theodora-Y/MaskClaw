from __future__ import annotations

from fastapi import APIRouter, Body, File, Form, Header, HTTPException, UploadFile

from auth_router import _extract_bearer_token, verify_token
from guard_backend_service import GuardBackendService


guard_router = APIRouter(prefix="/guard", tags=["guard"])


def _resolve_user_id(path_or_body_user_id: str | None, authorization: str | None) -> str:
    if authorization:
        token = _extract_bearer_token(authorization)
        token_uid = verify_token(token)
        if not token_uid:
            raise HTTPException(status_code=401, detail={"error": "invalid_token"})
        if path_or_body_user_id and str(path_or_body_user_id).strip() and token_uid != str(path_or_body_user_id).strip():
            raise HTTPException(status_code=403, detail={"error": "forbidden"})
        return token_uid

    user_id = str(path_or_body_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail={"error": "missing_user_id", "message": "user_id 不能为空"})
    return user_id


def _guard_service() -> GuardBackendService:
    return GuardBackendService()


@guard_router.post("/decide")
def guard_decide(
    body: dict = Body(...),
    authorization: str | None = Header(default=None),
):
    user_id = _resolve_user_id(body.get("user_id"), authorization)
    event = dict(body)
    event["user_id"] = user_id
    try:
        return _guard_service().decide(event)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "invalid_guard_event", "message": str(exc)}) from exc


@guard_router.post("/analyze")
async def guard_analyze(
    image: UploadFile = File(...),
    user_id: str | None = Form(default=None),
    command: str = Form(default="分析当前页面隐私"),
    authorization: str | None = Header(default=None),
):
    resolved_user_id = _resolve_user_id(user_id, authorization)
    payload = _guard_service().analyze_image_bytes(
        await image.read(),
        image.filename or "image.png",
        user_id=resolved_user_id,
        command=command,
    )
    return payload


@guard_router.post("/redact")
async def guard_redact(
    image: UploadFile = File(...),
    user_id: str | None = Form(default=None),
    command: str = Form(default="分析当前页面隐私"),
    method: str = Form(default="blur"),
    authorization: str | None = Header(default=None),
):
    normalized_method = str(method or "blur").strip().lower()
    if normalized_method not in {"blur", "mosaic", "block"}:
        raise HTTPException(status_code=400, detail={"error": "invalid_method", "message": "method 必须是 blur、mosaic 或 block"})

    resolved_user_id = _resolve_user_id(user_id, authorization)
    payload = _guard_service().redact_image_bytes(
        await image.read(),
        image.filename or "image.png",
        user_id=resolved_user_id,
        command=command,
        method=normalized_method,
    )
    return payload
