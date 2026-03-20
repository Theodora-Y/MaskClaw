# FastAPI 服务 - 隐私代理 HTTP 接口

from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, Header, Query
from fastapi.responses import Response, JSONResponse, StreamingResponse
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
from pathlib import Path
from skill_registry.skill_db import SkillDB

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="隐私保护代理 API", version="1.0.0")

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
