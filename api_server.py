# FastAPI 服务 - 隐私代理 HTTP 接口

from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, Header, Query, Request
from fastapi.responses import Response, JSONResponse, StreamingResponse
from fastapi.routing import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Literal, List, Optional
import json
import base64
import os
import time
import hmac
import hashlib
import io
import tarfile
import logging
import asyncio
from pathlib import Path
from skill_registry.skill_db import SkillDB
from memory.chat_history_db import ChatHistoryDB
from memory.rag_client import RAGClient
from auth_router import auth_router
from notifications_router import notifications_router

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="隐私保护代理 API", version="1.0.0")

# 添加 CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(notifications_router)

# ============== JWT 前端控制台专用路由（避免与 HMAC 端点冲突）==============
# 前端通过 /console/* 调用，使用 Authorization: Bearer JWT 认证

console_router = APIRouter(prefix="/console", tags=["console"])


class SkillMetaUpdateRequest(BaseModel):
    confidence: float | None = None
    scene: str | None = None
    rule_text: str | None = None
    strategy: str | None = None
    sensitive_field: str | None = None


class SkillArchiveRequest(BaseModel):
    reason: str | None = "user_archived"


class SkillDeleteRequest(BaseModel):
    confirm: bool = False


def _require_jwt(authorization: str | None) -> str:
    """从 Authorization: Bearer <token> 中提取 user_id"""
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "missing_auth"})
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"error": "invalid_auth_header"})
    token = parts[1].strip()
    from auth_router import verify_token
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail={"error": "invalid_token"})
    return user_id


def _get_skill_db():
    return SkillDB(db_path=str(PROJECT_ROOT / "skill_registry" / "skill_registry.db"))


@console_router.get("/skills/active/{user_id}")
def console_get_active(
    user_id: str,
    authorization: str | None = Header(default=None),
):
    """JWT 版：返回用户所有 active Skill"""
    token_uid = _require_jwt(authorization)
    if token_uid != user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    db = _get_skill_db()
    skills = db.get_active_skills(user_id)
    return {"user_id": user_id, "skills": skills, "count": len(skills)}


@console_router.get("/skills/all/{user_id}")
def console_get_all_skills(
    user_id: str,
    authorization: str | None = Header(default=None),
):
    """JWT 版：返回用户所有 Skill（含 active + archived）"""
    token_uid = _require_jwt(authorization)
    if token_uid != user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    db = _get_skill_db()
    active = db.get_active_skills(user_id)
    archived = db.get_archived_skills(user_id)
    return {
        "user_id": user_id,
        "active": active,
        "archived": archived,
        "total": len(active) + len(archived),
    }


@console_router.post("/skills/archive/{user_id}/{skill_name}/{version}")
def console_archive(
    user_id: str,
    skill_name: str,
    version: str,
    payload: SkillArchiveRequest | None = None,
    authorization: str | None = Header(default=None),
):
    """JWT 版：停用（归档）指定 Skill"""
    token_uid = _require_jwt(authorization)
    if token_uid != user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    db = _get_skill_db()
    reason = (payload.reason or "user_archived") if payload else "user_archived"
    ok = db.archive_skill(user_id, skill_name, version, reason=reason)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "skill_not_found_or_already_archived"})
    return {"success": True, "user_id": user_id, "skill_name": skill_name, "version": version}


@console_router.post("/skills/restore/{user_id}/{skill_name}/{version}")
def console_restore(
    user_id: str,
    skill_name: str,
    version: str,
    authorization: str | None = Header(default=None),
):
    """JWT 版：恢复已归档的 Skill"""
    token_uid = _require_jwt(authorization)
    if token_uid != user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    db = _get_skill_db()
    ok = db.restore_skill(user_id, skill_name, version, str(USER_SKILLS_ROOT))
    if not ok:
        raise HTTPException(status_code=400, detail={"error": "restore_failed_check_content_or_already_active"})
    return {"success": True, "user_id": user_id, "skill_name": skill_name, "version": version}


@console_router.delete("/skills/{user_id}/{skill_name}/{version}")
def console_delete(
    user_id: str,
    skill_name: str,
    version: str,
    payload: SkillDeleteRequest | None = None,
    authorization: str | None = Header(default=None),
):
    """JWT 版：删除 Skill（归档 + 删除文件系统文件）"""
    token_uid = _require_jwt(authorization)
    if token_uid != user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    if payload and not payload.confirm:
        raise HTTPException(status_code=400, detail={"error": "delete_not_confirmed"})
    db = _get_skill_db()
    ok = db.archive_skill(user_id, skill_name, version, reason="user_deleted", delete_files=True)
    if not ok:
        raise HTTPException(status_code=404, detail={"error": "skill_not_found"})
    return {"success": True, "user_id": user_id, "skill_name": skill_name, "version": version}


@console_router.put("/skills/{user_id}/{skill_name}")
def console_update_meta(
    user_id: str,
    skill_name: str,
    payload: SkillMetaUpdateRequest,
    authorization: str | None = Header(default=None),
):
    """JWT 版：更新 Skill 元数据，并同步写回 rules.json 文件"""
    token_uid = _require_jwt(authorization)
    if token_uid != user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    db = _get_skill_db()
    active = db.get_active_skills(user_id)
    target = next((s for s in active if str(s.get("skill_name")) == skill_name), None)
    if not target:
        raise HTTPException(status_code=404, detail={"error": "skill_not_found"})

    skill_id = target["id"]
    skill_path = target.get("path") or ""

    # --- 1. 更新 DB ---
    conn = db._connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE skills SET
                confidence = COALESCE(?, confidence),
                scene = COALESCE(?, scene),
                rule_text = COALESCE(?, rule_text),
                strategy = COALESCE(?, strategy),
                sensitive_field = COALESCE(?, sensitive_field)
            WHERE id = ?
            """,
            (payload.confidence, payload.scene, payload.rule_text,
             payload.strategy, payload.sensitive_field, skill_id),
        )

        # --- 2. 同步写回 rules.json ---
        if skill_path and (payload.scene is not None or payload.rule_text is not None):
            # 重新读取更新后的行（含最新 rules_json_content）
            row = cur.execute(
                "SELECT rules_json_content, path FROM skills WHERE id = ?", (skill_id,)
            ).fetchone()
            if row and row["rules_json_content"]:
                try:
                    rj = json.loads(row["rules_json_content"])
                    if payload.scene is not None:
                        rj["scene"] = payload.scene
                    if payload.rule_text is not None:
                        rj["rule_text"] = payload.rule_text
                    rules_json_path = Path(skill_path) / "rules.json"
                    rules_json_path.write_text(json.dumps(rj, ensure_ascii=False, indent=2), encoding="utf-8")

                    # 同时更新 DB 里的 rules_json_content（保持一致）
                    cur.execute(
                        "UPDATE skills SET rules_json_content = ? WHERE id = ?",
                        (json.dumps(rj, ensure_ascii=False, indent=2), skill_id),
                    )
                    logger.info(f"[console_update_meta] synced rules.json for {skill_name} at {rules_json_path}")
                except Exception as e:
                    logger.warning(f"[console_update_meta] failed to sync rules.json: {e}")

        conn.commit()
    finally:
        conn.close()
    return {"success": True, "user_id": user_id, "skill_name": skill_name}


@console_router.post("/logs/import/{user_id}")
async def console_import_logs(
    user_id: str,
    log_type: str = Query(default="correction", pattern="^(correction|behavior|session_trace)$"),
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    """JWT 版：批量导入 jsonl 日志（方案A）"""
    token_uid = _require_jwt(authorization)
    if token_uid != user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    from auth_router import MEMORY_ROOT
    log_dir = MEMORY_ROOT / "logs" / user_id
    log_dir.mkdir(parents=True, exist_ok=True)
    name_map = {
        "correction": "correction_log.jsonl",
        "behavior": "behavior_log.jsonl",
        "session_trace": "session_trace.jsonl",
    }
    file_name = name_map.get(log_type, "imported.jsonl")
    file_path = log_dir / file_name

    existing_ids: set[str] = set()
    if file_path.exists():
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    eid = obj.get("event_id") or obj.get("ts") or ""
                    existing_ids.add(str(eid))
                except Exception:
                    pass

    count = 0
    error_lines: list[int] = []
    content = await file.read()
    with file_path.open("a", encoding="utf-8") as f:
        for line_no, raw_line in enumerate(content.decode("utf-8", errors="replace").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                eid = str(obj.get("event_id") or obj.get("ts") or "")
                if eid and eid in existing_ids:
                    continue
                f.write(line + "\n")
                count += 1
            except Exception:
                error_lines.append(line_no)

    return {
        "success": True,
        "user_id": user_id,
        "log_type": log_type,
        "file": file_name,
        "imported": count,
        "skipped": len(existing_ids),
        "parse_errors": len(error_lines),
        "error_lines": error_lines[:10],
    }


app.include_router(console_router)

# ============== 配置 ==============
PROJECT_ROOT = Path(__file__).parent
USER_SKILLS_ROOT = PROJECT_ROOT / "user_skills"
MEMORY_ROOT = PROJECT_ROOT / "memory"

# 认证密钥
AUTH_SECRET = os.environ.get("PRIVACY_AGENT_AUTH_SECRET", "change-me-in-production")
AUTH_TIMESTAMP_TOLERANCE = 300  # 5分钟

_agent = None
_skill_db: Optional[SkillDB] = None


def get_agent():
    global _agent
    if _agent is None:
        from proxy_agent import PrivacyProxyAgent
        _agent = PrivacyProxyAgent()
    return _agent


def get_skill_db() -> SkillDB:
    global _skill_db
    if _skill_db is None:
        _skill_db = SkillDB(db_path=str(PROJECT_ROOT / "skill_registry" / "skill_registry.db"))
    return _skill_db


# ============== 认证工具 ==============

def verify_hmac_signature(user_id: str, timestamp: str, signature: str) -> bool:
    """验证 HMAC 签名"""
    try:
        ts = int(timestamp)
        if abs(int(time.time()) - ts) > AUTH_TIMESTAMP_TOLERANCE:
            return False
        
        message = f"{user_id}{timestamp}"
        expected = base64.b64encode(
            hmac.new(
                AUTH_SECRET.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def require_auth(user_id: str, x_timestamp: str = Header(None), x_signature: str = Header(None)):
    """验证请求认证"""
    if not x_timestamp or not x_signature:
        raise HTTPException(
            status_code=401,
            detail={"code": "MISSING_AUTH_HEADERS", "message": "缺少认证头"}
        )
    if not verify_hmac_signature(user_id, x_timestamp, x_signature):
        raise HTTPException(
            status_code=401,
            detail={"code": "INVALID_SIGNATURE", "message": "签名验证失败"}
        )


# ============== 原有接口 ==============

@app.get("/")
def root():
    return {"status": "ok", "message": "隐私保护代理服务运行中"}


@app.post("/process")
async def process_screenshot(
    image: UploadFile = File(...),
    user_id: str = Form(None),
    command: str = Form("分析当前页面隐私"),
    return_base64: bool = Form(False)
):
    """处理截图 - 隐私保护核心接口"""
    if not user_id or not str(user_id).strip():
        raise HTTPException(status_code=400, detail="user_id 不能为空")
    
    user_id = str(user_id).strip()
    agent = get_agent()
    result = agent.process_image_bytes(
        await image.read(),
        image.filename or "image.jpg",
        command,
        user_id=user_id
    )

    meta = {
        "success": True,
        "matched_rules": result.matched_rules,
        "analysis": result.analysis,
        "masked_count": result.masked_count,
        "mime_type": result.masked_mime_type,
    }

    if return_base64:
        meta["image_base64"] = base64.b64encode(result.masked_image_bytes).decode()
        return meta

    return _multipart_response(meta, result.masked_image_bytes, result.masked_mime_type)


@app.get("/rules")
def list_rules():
    return {"rules": get_agent().list_rules()}


@app.post("/rules")
def add_rule(rule: Dict[str, Any] = Body(...)):
    return {"status": "ok", "rule": get_agent().upsert_rule(rule)}


@app.post("/hook")
def hook_control(action: Literal["install", "uninstall", "status"] = Form(...)):
    from proxy_agent import ScreenshotHook, PrivacyProxyAgent
    agent = PrivacyProxyAgent()
    if action == "install":
        ScreenshotHook.install(agent)
        return {"installed": True}
    if action == "uninstall":
        ScreenshotHook.uninstall()
        return {"installed": False}
    return {"installed": ScreenshotHook._is_installed}


# ============== 核心：极简 Skill 同步接口 ==============

@app.post("/skills/sync")
def sync_skills(
    body: Dict[str, Any] = Body(...),
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    """
    增量 Skill 同步接口

    客户端发送：
        POST /skills/sync
        {
            "user_id": "demo_UserA",
            "installed_skills": {
                "privacy-file-content-replace-v1": "旧hash值",
                "privacy-old-skill-v1": "旧hash值"
            }
        }

    服务端响应：
        - 有更新：返回 JSON（to_update / to_delete 列表）+ tar.gz（只含差异部分）
        - 无更新：返回 {"updated": false, "message": "已是最新"}
    """
    user_id = body.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空")

    # 验证签名
    require_auth(user_id, x_timestamp, x_signature)

    db = get_skill_db()
    active_rows = db.get_active_skills(user_id)
    if not active_rows:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 没有任何 Skills")

    server_skills = {
        str(r.get("skill_name", "")): {
            "content_hash": str(r.get("content_hash", "")),
            "path": str(r.get("path", "")),
        }
        for r in active_rows
        if str(r.get("skill_name", ""))
    }
    client_skills = body.get("installed_skills", {})

    # 对比：找出新增/更新/删除
    to_update: List[str] = []   # 需要更新的 skill 名称
    to_delete: List[str] = []   # 服务端已删除但客户端还有的

    for skill_name, server_meta in server_skills.items():
        client_hash = client_skills.get(skill_name, "")
        server_hash = server_meta.get("content_hash", "")
        if client_hash != server_hash:
            to_update.append(skill_name)

    for skill_name in client_skills:
        if skill_name not in server_skills:
            to_delete.append(skill_name)

    # 无更新
    if not to_update and not to_delete:
        return {
            "updated": False,
            "user_id": user_id,
            "message": "已是最新"
        }

    logger.info(f"增量 Sync: user_id={user_id}, to_update={to_update}, to_delete={to_delete}")

    # 增量打包（只打包 to_update 的 Skill 目录）
    tar_buffer = io.BytesIO()
    updated_count = 0

    try:
        with tarfile.open(fileobj=tar_buffer, mode="w:gz", format=tarfile.PAX_FORMAT) as tar:
            for skill_name in to_update:
                skill_path = str(server_skills.get(skill_name, {}).get("path", ""))
                skill_dir = Path(skill_path)
                if skill_dir.exists() and skill_dir.is_dir():
                    arcname = f"{user_id}/{skill_dir.name}"
                    tar.add(skill_dir, arcname=arcname)
                    updated_count += 1

        tar_buffer.seek(0)
        tar_bytes = tar_buffer.getvalue()

        # 返回增量信息和 tar.gz 流
        response_meta = {
            "updated": True,
            "user_id": user_id,
            "to_update": to_update,
            "to_delete": to_delete,
            "updated_count": updated_count,
            "deleted_count": len(to_delete),
            "message": f"需要更新 {updated_count} 个，删除 {len(to_delete)} 个"
        }

        filename = f"skills_delta_{user_id}_{int(time.time())}.tar.gz"

        return StreamingResponse(
            io.BytesIO(tar_bytes),
            media_type="application/gzip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Updated": "true",
                "X-Update-Count": str(updated_count),
                "X-Delete-Count": str(len(to_delete)),
                "X-User-ID": user_id,
                "X-Update-List": json.dumps(to_update),
                "X-Delete-List": json.dumps(to_delete),
                "X-Meta": base64.b64encode(json.dumps(response_meta).encode()).decode(),
            }
        )

    except Exception as e:
        logger.error(f"增量打包失败: user_id={user_id}, error={e}")
        raise HTTPException(status_code=500, detail=f"打包失败: {e}")


def _get_user_version_tag(user_dir: Path) -> str:
    """
    生成用户的版本标签
    格式: {最新skill的mtime}_{skill总数}
    例如: 20260318_v3
    
    这样客户端只需比较字符串即可判断是否需要更新
    """
    if not user_dir.exists():
        return "unknown"
    
    # 获取所有 skill 目录
    skill_dirs = [d for d in user_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    
    if not skill_dirs:
        return "empty"
    
    # 最新修改时间
    latest_mtime = max(d.stat().st_mtime for d in skill_dirs)
    latest_date = time.strftime("%Y%m%d", time.localtime(latest_mtime))
    
    # skill 数量
    count = len(skill_dirs)
    
    return f"{latest_date}_v{count}"


def _multipart_response(meta: Dict, image_bytes: bytes, mime_type: str) -> Response:
    """构建 multipart/mixed 响应"""
    boundary = "----privacy-agent-boundary"
    body = b"".join([
        b"--" + boundary.encode() + b"\r\n",
        b"Content-Type: application/json; charset=utf-8\r\n\r\n",
        json.dumps(meta, ensure_ascii=False).encode(),
        b"\r\n",
        b"--" + boundary.encode() + b"\r\n",
        f"Content-Type: {mime_type}\r\n".encode(),
        b'Content-Disposition: inline; filename="masked"\r\n\r\n',
        image_bytes,
        b"\r\n",
        b"--" + boundary.encode() + b"--\r\n",
    ])
    return Response(content=body, media_type=f"multipart/mixed; boundary={boundary}")


@app.get("/skills/search")
def search_skills(
    user_id: str,
    task_goal: str = "",
    app_context: str = "",
    action_keywords: str = "",
    limit: int = Query(default=5, ge=1, le=20),
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    """
    根据任务上下文检索匹配的 skills

    客户端调用：
        GET /skills/search?user_id=demo_UserA&task_goal=发送病历&app_context=hospital_oa

    响应示例：
        {
            "skills": [
                {
                    "skill_name": "hospital-privacy-protect",
                    "version": "v1.0.0",
                    "app_context": "hospital_oa",
                    "confidence": 0.95,
                    "trigger_count": 12,
                    ...
                }
            ],
            "matched_by": {
                "app_context": "hospital_oa",
                "task_goal": "发送病历",
            },
            "total": 1
        }
    """
    require_auth(user_id, x_timestamp, x_signature)

    db = get_skill_db()
    skills = db.search_skills(
        user_id=user_id,
        task_goal=task_goal,
        app_context=app_context,
        action_keywords=action_keywords,
        limit=limit,
    )

    return {
        "skills": skills,
        "matched_by": {
            "task_goal": task_goal or None,
            "app_context": app_context or None,
            "action_keywords": action_keywords or None,
        },
        "total": len(skills),
    }


@app.get("/skills/detail")
def get_skill_detail(
    user_id: str,
    skill_name: str,
    version: str = "",
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    """
    获取完整 skill 详情（包含 SKILL.md 和 rules.json 内容）

    客户端调用：
        GET /skills/detail?user_id=demo_UserA&skill_name=hospital-privacy-protect&version=v1.0.0

    响应示例：
        {
            "skill_name": "hospital-privacy-protect",
            "version": "v1.0.0",
            "skill_md_content": "完整 SKILL.md 内容...",
            "rules_json_content": [...],
            ...
        }
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空")

    require_auth(user_id, x_timestamp, x_signature)

    db = get_skill_db()
    skill = db.get_skill_detail(user_id, skill_name, version)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill {skill_name}@{version} 不存在")

    return skill


@app.post("/skills/rag/query")
def rag_query_skills(
    body: Dict[str, Any] = Body(...),
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    """
    RAG 向量检索，查找相关隐私规则

    客户端调用：
        POST /skills/rag/query
        {
            "user_id": "demo_UserA",
            "query": "用户想分享医院联系人截图",
            "app_context": "hospital_oa",
            "top_k": 3
        }

    响应示例：
        {
            "rules": [
                "禁止在外部平台分享含敏感信息的截图",
                "截图前需检查是否包含身份证号、银行卡号等"
            ],
            "sources": [
                {"skill_name": "...", "confidence": 0.9}
            ]
        }
    """
    user_id = body.get("user_id")
    query = body.get("query", "")
    app_context = body.get("app_context", "")
    top_k = body.get("top_k", 3)

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空")

    require_auth(user_id, x_timestamp, x_signature)

    # 使用 ChromaDB 进行向量检索
    try:
        rag = RAGClient()
        results = rag.query(
            query_text=query,
            collection_name=f"rules_{user_id}",
            where={"app_context": app_context} if app_context else None,
            top_k=top_k,
        )

        return {
            "rules": results.get("documents", []),
            "metadatas": results.get("metadatas", []),
            "distances": results.get("distances", []),
            "sources": [
                {"skill_name": m.get("skill_name", ""), "confidence": m.get("confidence", 0)}
                for m in results.get("metadatas", [])
            ],
        }
    except Exception as e:
        logger.warning(f"RAG 查询失败: {e}, 返回空结果")
        return {"rules": [], "metadatas": [], "distances": [], "sources": []}


# ============== 辅助接口（可选，用于查看状态）==============

@app.get("/skills/{user_id}/version")
def get_user_version(
    user_id: str,
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    """
    查询用户当前版本（无需下载 tar.gz）
    用于客户端快速检查是否需要同步
    """
    require_auth(user_id, x_timestamp, x_signature)
    
    db = get_skill_db()
    active_rows = db.get_active_skills(user_id)

    if not active_rows:
        raise HTTPException(status_code=404, detail=f"用户 {user_id} 没有 Skills")

    latest_created = max(int(r.get("created_ts", 0) or 0) for r in active_rows)
    latest_date = time.strftime("%Y%m%d", time.localtime(latest_created))
    current_version = f"{latest_date}_v{len(active_rows)}"

    skills = []
    for r in active_rows:
        skill_dir = Path(str(r.get("path", "")))
        skill_info = {
            "name": str(r.get("skill_name", "")),
            "version": str(r.get("version", "")),
            "mtime": int(r.get("created_ts", 0) or 0),
            "files": [f.name for f in skill_dir.iterdir() if skill_dir.exists() and f.is_file()],
            "confidence": r.get("confidence"),
            "strategy": r.get("strategy"),
        }
        skills.append(skill_info)
    
    return {
        "user_id": user_id,
        "version": current_version,
        "skill_count": len(skills),
        "skills": sorted(skills, key=lambda x: x["mtime"], reverse=True)
    }


@app.get("/skills/active/{user_id}")
def get_active_skills(
    user_id: str,
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    require_auth(user_id, x_timestamp, x_signature)
    return {"user_id": user_id, "skills": get_skill_db().get_active_skills(user_id)}


@app.get("/skills/archived/{user_id}")
def get_archived_skills(
    user_id: str,
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    require_auth(user_id, x_timestamp, x_signature)
    return {"user_id": user_id, "skills": get_skill_db().get_archived_skills(user_id)}


@app.get("/skills/history/{user_id}/{skill_name}")
def get_skill_history(
    user_id: str,
    skill_name: str,
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    require_auth(user_id, x_timestamp, x_signature)
    return {
        "user_id": user_id,
        "skill_name": skill_name,
        "history": get_skill_db().get_skill_history(user_id, skill_name),
    }


@app.post("/skills/restore/{user_id}/{skill_name}/{version}")
def restore_skill(
    user_id: str,
    skill_name: str,
    version: str,
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    require_auth(user_id, x_timestamp, x_signature)
    ok = get_skill_db().restore_skill(user_id, skill_name, version, str(USER_SKILLS_ROOT))
    if not ok:
        raise HTTPException(status_code=400, detail="恢复失败：版本不存在或已是 active")
    return {"success": True, "user_id": user_id, "skill_name": skill_name, "version": version}


@app.get("/evolution/status")
def get_evolution_status():
    """查询各用户 correction_log 统计"""
    logs_root = MEMORY_ROOT / "logs"
    
    if not logs_root.exists():
        return {"total_users": 0, "ready_users": 0, "users": []}
    
    from evolution_daemon import CorrectionLogReader
    reader = CorrectionLogReader(logs_root)
    
    user_ids = reader.get_all_user_ids()
    stats = []
    
    for uid in user_ids:
        unprocessed = reader.get_unprocessed_count(uid)
        stats.append({
            "user_id": uid,
            "unprocessed_count": unprocessed,
            "threshold": 3,
            "ready": unprocessed >= 3
        })
    
    return {
        "total_users": len(user_ids),
        "ready_users": sum(1 for s in stats if s["ready"]),
        "users": sorted(stats, key=lambda x: x["unprocessed_count"], reverse=True)
    }


@app.post("/evolution/trigger")
def trigger_evolution(
    user_id: str = Form(...),
    x_timestamp: str = Header(None),
    x_signature: str = Header(None),
):
    """手动触发指定用户的进化流程"""
    require_auth(user_id, x_timestamp, x_signature)
    
    from evolution_daemon import EvolutionTrigger, DaemonConfig
    start_time = time.time()
    
    try:
        config = DaemonConfig(
            logs_root="memory/logs",
            memory_root="memory",
            user_skills_root="user_skills",
            run_once=True,
        )
        trigger = EvolutionTrigger(config)
        result = trigger._run_evolution(user_id)
        result["elapsed_seconds"] = round(time.time() - start_time, 2)
        return result
    except Exception as e:
        return {
            "success": False,
            "user_id": user_id,
            "error": str(e),
            "elapsed_seconds": round(time.time() - start_time, 2)
        }


# ============== 日志接收与推送接口 ==============

@app.post("/logs/upload")
async def upload_logs(
    body: Dict[str, Any] = Body(...),
    x_api_key: str = Header(None),
):
    """
    接收 Windows 客户端上传的日志

    请求格式：
    {
        "user_id": "win_user_001",
        "logs": [
            {
                "action": "agent_fill",
                "app_context": "taobao",
                "resolution": "mask",
                "field": "phone_number",
                "agent_intent": "自动填入手机号",
                "pii_type": "PHONE_NUMBER",
                "masked_image_path": "temp/masked_xxx.jpg",
                "safe_image_path": "temp/safe_xxx.jpg"
            },
            ...
        ]
    }

    返回：
    {
        "status": "accepted",
        "count": 5
    }
    """
    user_id = body.get("user_id")
    logs = body.get("logs", [])

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空")

    if not logs:
        raise HTTPException(status_code=400, detail="logs 不能为空")

    # 验证 API Key（可选）
    if x_api_key:
        # TODO: 实现 API Key 验证
        pass

    # 提交到 LogProcessor
    processor = get_log_processor()
    count = processor.submit(user_id, logs)

    logger.info(f"接收日志: user_id={user_id}, count={count}")

    return {"status": "accepted", "count": count}


@app.get("/logs/stream/{user_id}")
async def stream_logs(
    user_id: str,
    x_api_key: str = Header(None),
):
    """
    SSE 流式推送日志到前端

    前端连接方式：
    ```javascript
    const es = new EventSource('/logs/stream/win_user_001');
    es.onmessage = (event) => {
        const data = JSON.parse(event.data);
        // data 包含可视化摘要
        console.log(data);
    };
    ```

    返回数据格式：
    {
        "event_type": "log_summary",
        "data": {
            "action_metadata": {...},
            "l1_detection": {...},
            "l2_reasoning": {...},
            "outcome": {...}
        }
    }
    """
    # TODO: 验证 API Key

    async def event_generator():
        from asyncio import Queue as AsyncQueue
        from asyncio import sleep

        client_queue: AsyncQueue = AsyncQueue()

        def sse_callback(data: Dict[str, Any]):
            try:
                client_queue.put_nowait(data)
            except Exception:
                pass

        # 注册客户端
        from memory.log_processor import register_sse_client, unregister_sse_client
        register_sse_client(user_id, sse_callback)

        try:
            # 发送连接成功消息
            yield {
                "event": "connected",
                "data": json.dumps({"status": "connected", "user_id": user_id}),
            }

            while True:
                try:
                    data = await asyncio.wait_for(client_queue.get(), timeout=30)
                    yield {
                        "event": "log",
                        "data": json.dumps(data),
                    }
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"ts": int(time.time())}),
                    }

        finally:
            unregister_sse_client(user_id, sse_callback)

    import asyncio
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/logs/latest/{user_id}")
def get_latest_logs(
    user_id: str,
    limit: int = Query(10, ge=1, le=100),
    x_api_key: str = Header(None),
):
    """获取用户最近的日志摘要。"""
    from memory.log_processor import get_log_processor

    processor = get_log_processor()
    logs_dir = processor.logs_dir / user_id
    behavior_file = logs_dir / "behavior_log.jsonl"

    if not behavior_file.exists():
        return {"user_id": user_id, "logs": [], "count": 0}

    logs = []
    with behavior_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines[-limit:]:
            if line.strip():
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    return {"user_id": user_id, "logs": logs, "count": len(logs)}


# ============== 任务执行管理 ==============

import uuid
import subprocess
import threading
import queue
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Task:
    task_id: str
    user_id: str
    task_description: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    process: Optional[Any] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    logs: List[Dict[str, Any]] = field(default_factory=list)

# 任务存储
_tasks: Dict[str, Task] = {}
_tasks_lock = threading.Lock()

# SSE 客户端回调
_sse_clients: Dict[str, List[Callable]] = {}
_sse_lock = threading.Lock()

def _notify_sse_clients(task_id: str, event_type: str, data: Dict[str, Any]):
    """通知所有 SSE 客户端"""
    with _sse_lock:
        callbacks = _sse_clients.get(task_id, [])
    for callback in callbacks:
        try:
            callback({"event_type": event_type, "data": data})
        except Exception:
            pass

def _process_log_to_summary(log: Dict[str, Any]) -> Dict[str, Any]:
    """将原始日志转换为可视化摘要格式"""
    
    action = log.get("action", "unknown")
    app_context = log.get("app_context", "")
    resolution = log.get("resolution", "")
    field_name = log.get("field", "")
    agent_intent = log.get("agent_intent", "")
    minicpm_reasoning = log.get("minicpm_reasoning", "")
    rule_match = log.get("rule_match", "")
    masked_image_base64 = ""
    safe_image_base64 = ""
    
    # 读取图片并转为 base64
    masked_path = log.get("masked_image_path", "")
    safe_path = log.get("safe_image_path", "")
    
    if masked_path and os.path.exists(masked_path):
        try:
            with open(masked_path, "rb") as f:
                masked_image_base64 = base64.b64encode(f.read()).decode()
        except Exception:
            pass
    
    if safe_path and os.path.exists(safe_path):
        try:
            with open(safe_path, "rb") as f:
                safe_image_base64 = base64.b64encode(f.read()).decode()
        except Exception:
            pass
    
    # 生成 Action Metadata
    action_metadata = {
        "action": action,
        "app_context": app_context,
        "description": agent_intent or f"Agent 执行操作: {action}",
        "timestamp": log.get("ts", int(time.time())),
    }
    
    # L1 静态识别
    l1_detection = {
        "detected_fields": [field_name] if field_name else [],
        "pii_type": log.get("pii_type", ""),
        "masked_preview": masked_image_base64,
        "masked_regions": [],  # 可以从图片分析获取
    }
    
    # L2 MiniCPM 推理
    l2_reasoning = {
        "reasoning": minicpm_reasoning,
        "rule_match": rule_match,
        "decision": resolution,
        "confidence": log.get("quality_score"),
    }
    
    # 处理结果
    outcome = {
        "final_action": resolution,
        "safe_image": safe_image_base64,
        "field": field_name,
        "message": _get_outcome_message(action, resolution, field_name),
    }
    
    return {
        "action_metadata": action_metadata,
        "l1_detection": l1_detection,
        "l2_reasoning": l2_reasoning,
        "outcome": outcome,
    }

def _get_outcome_message(action: str, resolution: str, field: str) -> str:
    """生成可读的结果消息"""
    messages = {
        ("agent_fill", "mask"): f"检测到敏感字段「{field}」，已自动脱敏",
        ("agent_fill", "block"): f"检测到敏感字段「{field}」，已阻止填入",
        ("agent_fill", "allow"): f"字段「{field}」无敏感信息，已放行",
        ("agent_fill", "ask"): f"字段「{field}」需用户确认",
        ("share_or_send", "mask"): f"分享内容包含敏感信息，已脱敏处理",
        ("share_or_send", "block"): f"分享内容包含敏感信息，已阻止",
        ("share_or_send", "allow"): f"分享内容安全，已放行",
    }
    
    key = (action, resolution)
    if key in messages:
        return messages[key]
    
    if resolution == "mask":
        return f"已自动脱敏处理"
    elif resolution == "block":
        return f"已阻止操作"
    elif resolution == "allow":
        return f"已放行"
    else:
        return f"操作完成 ({resolution})"


# 任务执行工作线程
def _run_task_worker(task: Task):
    """在工作线程中执行 AutoGLM 任务"""
    global _tasks
    
    task.status = TaskStatus.RUNNING
    task.started_at = time.time()
    
    # 通知客户端任务开始
    _notify_sse_clients(task.task_id, "action", {
        "task_id": task.task_id,
        "status": "running",
        "message": "任务已开始执行",
    })
    
    try:
        # TODO: 根据实际 AutoGLM 执行方式调整
        # 这里模拟执行，实际需要调用 Windows 上的 AutoGLM
        # 可以通过远程执行、消息队列等方式
        
        # 模拟执行过程
        for i in range(3):
            if task.status == TaskStatus.CANCELLED:
                return
            
            # 模拟日志
            log_entry = {
                "action": "agent_fill",
                "app_context": "auto_detected",
                "resolution": "mask",
                "field": f"field_{i}",
                "agent_intent": f"Agent 正在尝试填入第 {i+1} 个字段",
                "minicpm_reasoning": f"匹配到个性化规则：第 {i+1} 个字段为敏感信息，已自动修正",
                "rule_match": f"privacy-rule-{i+1}",
                "ts": int(time.time()),
            }
            task.logs.append(log_entry)
            
            # 转换为摘要并推送
            summary = _process_log_to_summary(log_entry)
            _notify_sse_clients(task.task_id, "log", summary)
            
            time.sleep(1)
        
        task.status = TaskStatus.COMPLETED
        task.result = {
            "success": True,
            "total_steps": len(task.logs),
            "masked_count": sum(1 for l in task.logs if l.get("resolution") == "mask"),
        }
        
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        _notify_sse_clients(task.task_id, "error", {
            "error": str(e),
            "message": f"任务执行失败: {e}",
        })
    finally:
        task.completed_at = time.time()
        _notify_sse_clients(task.task_id, "finished", {
            "task_id": task.task_id,
            "status": task.status.value,
            "result": task.result,
            "elapsed_seconds": round(task.completed_at - task.started_at, 2) if task.started_at else 0,
        })


# ============== 任务执行接口 ==============

@app.post("/task/run")
async def run_task(
    body: Dict[str, Any] = Body(...),
):
    """
    提交 AutoGLM 执行任务
    
    请求格式：
    {
        "user_id": "win_user_001",
        "task_description": "帮我在淘宝填收货地址",
        "autoglm_config": {
            "host": "127.0.0.1",
            "port": 9001,
        }
    }
    
    返回：
    {
        "task_id": "xxx",
        "status": "pending",
        "message": "任务已提交"
    }
    """
    user_id = body.get("user_id")
    task_description = body.get("task_description")
    
    if not user_id or not task_description:
        raise HTTPException(status_code=400, detail="user_id 和 task_description 不能为空")
    
    task_id = str(uuid.uuid4())
    
    task = Task(
        task_id=task_id,
        user_id=user_id,
        task_description=task_description,
    )
    
    with _tasks_lock:
        _tasks[task_id] = task
    
    # 启动工作线程执行任务
    thread = threading.Thread(target=_run_task_worker, args=(task,))
    thread.daemon = True
    thread.start()
    
    logger.info(f"任务已提交: task_id={task_id}, user_id={user_id}, task={task_description}")
    
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "任务已提交，正在执行中",
    }


@app.get("/task/stream/{task_id}")
async def stream_task_logs(
    task_id: str,
):
    """
    SSE 流式推送任务执行日志
    
    前端连接方式：
    ```javascript
    const es = new EventSource('/task/stream/' + taskId);
    es.addEventListener('action', (e) => { ... });
    es.addEventListener('log', (e) => { 
        const data = JSON.parse(e.data);
        // 显示可视化摘要
    });
    es.addEventListener('error', (e) => { ... });
    es.addEventListener('finished', (e) => { ... });
    ```
    """
    async def event_generator():
        from asyncio import Queue as AsyncQueue
        from asyncio import sleep
        
        client_queue: AsyncQueue = AsyncQueue()
        task_id_local = task_id
        
        def sse_callback(event_data: Dict[str, Any]):
            try:
                client_queue.put_nowait(event_data)
            except Exception:
                pass
        
        # 注册客户端
        with _sse_lock:
            if task_id_local not in _sse_clients:
                _sse_clients[task_id_local] = []
            _sse_clients[task_id_local].append(sse_callback)
        
        try:
            # 发送连接成功消息
            yield {
                "event": "connected",
                "data": json.dumps({"task_id": task_id, "status": "connected"}),
            }
            
            while True:
                try:
                    # 等待数据或超时
                    data = await asyncio.wait_for(client_queue.get(), timeout=30)
                    yield {
                        "event": data.get("event_type", "message"),
                        "data": json.dumps(data.get("data", {})),
                    }
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield {
                        "event": "heartbeat",
                        "data": json.dumps({"ts": int(time.time())}),
                    }
                
                # 检查任务是否完成
                with _tasks_lock:
                    task = _tasks.get(task_id_local)
                    if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                        break
                        
        finally:
            with _sse_lock:
                if task_id_local in _sse_clients:
                    try:
                        _sse_clients[task_id_local].remove(sse_callback)
                    except ValueError:
                        pass
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/task/cancel/{task_id}")
def cancel_task(
    task_id: str,
):
    """
    取消正在执行的任务
    
    返回：
    {
        "task_id": "xxx",
        "status": "cancelled",
        "message": "任务已取消"
    }
    """
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task.status == TaskStatus.COMPLETED:
            raise HTTPException(status_code=400, detail="任务已完成，无法取消")
        
        if task.status == TaskStatus.CANCELLED:
            raise HTTPException(status_code=400, detail="任务已取消")
        
        task.status = TaskStatus.CANCELLED
        task.completed_at = time.time()
        
        # 如果有进程，尝试终止
        if task.process:
            try:
                task.process.terminate()
            except Exception:
                pass
    
    _notify_sse_clients(task_id, "finished", {
        "task_id": task_id,
        "message": "任务已取消",
    })
    
    return {
        "task_id": task_id,
        "status": "cancelled",
        "message": "任务已取消",
    }


@app.get("/task/status/{task_id}")
def get_task_status(
    task_id: str,
):
    """
    查询任务状态
    
    返回：
    {
        "task_id": "xxx",
        "status": "running",
        "logs_count": 5,
        "created_at": 1234567890,
        "started_at": 1234567891,
    }
    """
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
    
    return {
        "task_id": task.task_id,
        "user_id": task.user_id,
        "task_description": task.task_description,
        "status": task.status.value,
        "logs_count": len(task.logs),
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
        "result": task.result,
        "error": task.error,
    }


@app.get("/task/logs/{task_id}")
def get_task_logs(
    task_id: str,
):
    """
    获取任务的所有日志（结构化摘要）
    """
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
    
    summaries = [_process_log_to_summary(log) for log in task.logs]
    
    return {
        "task_id": task_id,
        "status": task.status.value,
        "logs": summaries,
        "count": len(summaries),
    }


# ============== Windows 后端日志透传接口 ==============

@app.post("/autoglm/log")
async def receive_autoglm_log(
    body: Dict[str, Any] = Body(...),
):
    """
    接收 Windows 后端发送的 AutoGLM 执行日志，并广播给前端 SSE

    Windows 后端调用：
    POST http://服务器IP:28080/autoglm/log
    {
        "task_id": "xxx",
        "log_type": "action",  # action, thinking, error, log, privacy
        "message": "点击了淘宝按钮",
        "extra": {}  // 可选，附加数据
    }
    """
    task_id = body.get("task_id")
    log_type = body.get("log_type", "log")
    message = body.get("message", "")
    extra = body.get("extra", {})

    if not task_id:
        raise HTTPException(status_code=400, detail="task_id 不能为空")

    # 转换为 LogSummary 格式
    summary = {
        "step": 0,  # 前端会根据 logs.length + 1 计算
        "action": log_type,
        "app_context": "AutoGLM",
        "status": "running",
        "description": message,
        "timestamp": time.time(),
        "detail": extra if extra else None,
    }

    # 广播给所有 SSE 客户端
    _notify_sse_clients(task_id, log_type, summary)

    logger.info(f"[AutoGLM Log] task_id={task_id}, type={log_type}, msg={message[:50]}...")

    return {"status": "ok"}


@app.post("/autoglm/task/start")
async def start_autoglm_task(
    body: Dict[str, Any] = Body(...),
):
    """
    Windows 后端通知任务已开始

    Windows 后端调用：
    POST http://服务器IP:28080/autoglm/task/start
    {
        "task_id": "xxx",
        "task_description": "帮我在淘宝填收货地址",
        "user_id": "win_user_001"
    }
    """
    task_id = body.get("task_id")
    task_description = body.get("task_description", "")
    user_id = body.get("user_id", "unknown")

    if not task_id:
        raise HTTPException(status_code=400, detail="task_id 不能为空")

    # 在服务器端创建任务记录
    task = Task(
        task_id=task_id,
        user_id=user_id,
        task_description=task_description,
    )
    task.status = TaskStatus.RUNNING
    task.started_at = time.time()

    with _tasks_lock:
        _tasks[task_id] = task

    # 通知前端
    _notify_sse_clients(task_id, "action", {
        "task_id": task_id,
        "status": "running",
        "message": f"任务已开始: {task_description}",
    })

    logger.info(f"[AutoGLM Task] Started: task_id={task_id}, description={task_description}")

    return {"status": "ok"}


@app.post("/autoglm/task/finish")
async def finish_autoglm_task(
    body: Dict[str, Any] = Body(...),
):
    """
    Windows 后端通知任务已结束

    Windows 后端调用：
    POST http://服务器IP:28080/autoglm/task/finish
    {
        "task_id": "xxx",
        "status": "completed",  // completed, failed
        "error": "错误信息"  // 可选
    }
    """
    task_id = body.get("task_id")
    status = body.get("status", "completed")
    error = body.get("error")

    if not task_id:
        raise HTTPException(status_code=400, detail="task_id 不能为空")

    with _tasks_lock:
        task = _tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED if status == "completed" else TaskStatus.FAILED
            task.completed_at = time.time()
            task.error = error
            task.result = {
                "total_steps": len(task.logs),
            }

    # 通知前端
    _notify_sse_clients(task_id, "finished", {
        "task_id": task_id,
        "status": status,
        "message": "任务已完成" if status == "completed" else f"任务失败: {error}",
    })

    logger.info(f"[AutoGLM Task] Finished: task_id={task_id}, status={status}")

    return {"status": "ok"}


# ============== AutoGLM 日志存储接口（直接生成 session_trace）==============

from skills.behavior_monitor import TraceChainLogger, log_action_to_chain, flush_and_save_chain
from datetime import datetime

# 任务缓存：task_id -> {"user_id": "", "task_description": "", "scenario_tag": "", "actions": []}
_task_action_cache: Dict[str, Dict[str, Any]] = {}
_tasks_lock = threading.Lock()


@app.post("/autoglm/log/save")
async def save_autoglm_log(
    body: Dict[str, Any] = Body(...),
):
    """
    接收 AutoGLM 执行日志，直接生成 session_trace 行为链

    Windows 后端调用：
    POST http://127.0.0.1:9001/autoglm/log/save
    {
        "user_id": "UserA",
        "task_id": "xxx",
        "task_description": "帮我在淘宝填收货地址",
        "event": "log_summary",
        "data": {
            "action_metadata": {"action": "share_or_send", "app_context": "钉钉", ...},
            "outcome": {"final_action": "mask", ...},
            ...
        }
    }
    """
    user_id = body.get("user_id", "unknown")
    task_id = body.get("task_id", "unknown")
    task_description = body.get("task_description", "")
    event = body.get("event", "log_summary")
    data = body.get("data", {})

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 不能为空")

    # 初始化任务缓存
    with _tasks_lock:
        if task_id not in _task_action_cache:
            _task_action_cache[task_id] = {
                "user_id": user_id,
                "task_description": task_description,
                "scenario_tag": task_description[:50] if task_description else task_id,
                "actions": [],
                "start_ts": int(time.time()),
            }

    # 解析日志数据
    action_metadata = data.get("action_metadata", {})
    outcome = data.get("outcome", {})
    l1_detection = data.get("l1_detection", {})
    l2_reasoning = data.get("l2_reasoning", {})

    action = action_metadata.get("action", "unknown")
    app_context = action_metadata.get("app_context", "unknown")
    resolution = outcome.get("final_action", outcome.get("resolution", "unknown"))
    field = outcome.get("field", "")
    rule_match = l2_reasoning.get("rule_match", "")

    # 判断是否纠错（根据 resolution）
    is_correction = resolution in ["correction", "user_denied", "user_modified"]
    correction_type = None
    if is_correction:
        correction_type = resolution if resolution != "correction" else "user_denied"

    # 生成行为链记录
    action_record = {
        "action": action,
        "resolution": resolution,
        "field": field,
        "rule_match": rule_match,
        "app_context": app_context,
        "ts": int(time.time()),
        "is_correction": is_correction,
        "correction_type": correction_type,
        "pii_type": l1_detection.get("pii_type", ""),
        "agent_intent": action_metadata.get("description", ""),
        "quality_score": l2_reasoning.get("confidence"),
    }

    # 添加到缓存
    with _tasks_lock:
        if task_id in _task_action_cache:
            _task_action_cache[task_id]["actions"].append(action_record)
            _task_action_cache[task_id]["end_ts"] = int(time.time())

    logger.info(f"[AutoGLM Log] Saved action: user_id={user_id}, task_id={task_id}, action={action}, resolution={resolution}")

    return {"status": "ok", "saved": True}


@app.post("/autoglm/task/flush/{task_id}")
async def flush_autoglm_task(
    task_id: str,
    user_id: str = Query(...),
):
    """
    任务结束时，将缓存的 actions 生成 session_trace 行为链并写入磁盘

    Windows 后端在任务结束时调用：
    POST http://127.0.0.1:9001/autoglm/task/flush/{task_id}?user_id=UserA
    """
    with _tasks_lock:
        task_data = _task_action_cache.pop(task_id, None)

    if not task_data:
        return {"status": "ok", "message": "no cached actions", "saved": False}

    actions = task_data.get("actions", [])
    if not actions:
        return {"status": "ok", "message": "no actions", "saved": False}

    # 生成行为链
    scenario_tag = task_data.get("scenario_tag", task_id)
    start_ts = task_data.get("start_ts", int(time.time()) - 60)
    end_ts = task_data.get("end_ts", int(time.time()))
    uid = task_data.get("user_id", user_id)

    chain_id = f"{uid}_{scenario_tag}_{start_ts}"
    correction_count = sum(1 for a in actions if a.get("is_correction", False))

    # 确定最终决策
    final_resolution = "allow"
    for a in reversed(actions):
        if a.get("resolution") in ["block", "mask", "correction"]:
            final_resolution = a["resolution"]
            break

    # 生成行为链结构
    chain = {
        "chain_id": chain_id,
        "user_id": uid,
        "app_context": actions[0].get("app_context", "unknown") if actions else "unknown",
        "scenario_tag": scenario_tag,
        "rule_type": "H",  # 暂时固定为 H，后续可从日志中提取
        "start_ts": start_ts,
        "end_ts": end_ts,
        "action_count": len(actions),
        "has_correction": correction_count > 0,
        "correction_count": correction_count,
        "final_resolution": final_resolution,
        "processed": False,
        "actions": [
            {
                "action_index": i,
                "ts": a.get("ts", start_ts + i),
                "action": a.get("action", "unknown"),
                "resolution": a.get("resolution", "unknown"),
                "is_correction": a.get("is_correction", False),
                "correction_type": a.get("correction_type"),
                "field": a.get("field", ""),
                "rule_match": a.get("rule_match", ""),
                "pii_type": a.get("pii_type", ""),
                "agent_intent": a.get("agent_intent", ""),
                "quality_score": a.get("quality_score"),
            }
            for i, a in enumerate(actions)
        ],
    }

    # 写入 session_trace.jsonl
    logger = TraceChainLogger(uid, str(MEMORY_ROOT / "logs"))
    logger.write_chain(chain)

    logger.info(f"[AutoGLM] Flushed chain: chain_id={chain_id}, actions={len(actions)}")

    return {
        "status": "ok",
        "saved": True,
        "chain_id": chain_id,
        "action_count": len(actions),
    }


@app.get("/autoglm/chains/{user_id}")
async def list_autoglm_chains(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """列出用户的行为链日志"""
    logger = TraceChainLogger(user_id, str(MEMORY_ROOT / "logs"))
    chains = logger.read_chains(limit=limit)
    return {"user_id": user_id, "chains": chains, "count": len(chains)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
