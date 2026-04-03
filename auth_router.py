from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import bcrypt
import jwt
from fastapi import APIRouter, Header, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

JWT_SECRET = os.environ.get("MASKCLAW_JWT_SECRET", "maskclaw_dev_secret_change_in_prod")
JWT_EXPIRE_HOURS = int(os.environ.get("MASKCLAW_JWT_EXPIRE_HOURS", "72"))

PROJECT_ROOT = Path(__file__).resolve().parent
USERS_DB_PATH = PROJECT_ROOT / "maskclaw.db"
SKILL_DB_PATH = PROJECT_ROOT / "skill_registry" / "skill_registry.db"
USER_SKILLS_ROOT = PROJECT_ROOT / "user_skills"
MEMORY_ROOT = PROJECT_ROOT / "memory"

APP_NAMES = {
    "wechat": "微信",
    "jd": "京东",
    "taobao": "淘宝",
    "alipay": "支付宝",
    "dingtalk": "钉钉",
    "feishu": "飞书",
    "his": "HIS系统",
    "unknown_app": "未知应用",
}
ACTION_NAMES = {
    "send_file": "发送文件",
    "fill_home_address": "填写家庭住址",
    "fill_form_field": "填写表单",
    "send_message": "发送消息",
    "upload_file": "上传文件",
    "share_content": "分享内容",
}
CORRECTION_NAMES = {
    "user_denied": "拒绝了这个操作",
    "user_modified": "将内容修改为自定义替代值",
    "user_approved": "手动放行了这个操作",
    "user_blocked": "手动拦截了这个操作",
}


auth_router = APIRouter(tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    username: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdateRequest(BaseModel):
    username: str | None = None
    occupation: str | None = None
    apps: list[str] | None = None
    sensitive_fields: list[str] | None = None
    onboarding_done: bool | None = None
    avatar_index: int | None = None
    grad_from: str | None = None
    grad_to: str | None = None


def _connect_users_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(USERS_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_users_db() -> None:
    USERS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect_users_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id          TEXT PRIMARY KEY,
                username         TEXT NOT NULL,
                email            TEXT UNIQUE NOT NULL,
                password_hash    TEXT NOT NULL,
                occupation       TEXT,
                apps             TEXT,
                sensitive_fields TEXT,
                onboarding_done  INTEGER DEFAULT 0,
                avatar_index     INTEGER DEFAULT 0,
                grad_from        TEXT,
                grad_to          TEXT,
                created_ts       INTEGER NOT NULL
            )
            """
        )

        # Add columns only if they don't exist (for existing databases)
        existing_cols = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
        if "avatar_index" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN avatar_index INTEGER DEFAULT 0")
        if "grad_from" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN grad_from TEXT")
        if "grad_to" not in existing_cols:
            conn.execute("ALTER TABLE users ADD COLUMN grad_to TEXT")
        conn.commit()


def seed_demo_accounts() -> None:
    accounts = [
        {
            "user_id": "demo_UserA",
            "username": "张医生",
            "email": "demo_usera@maskclaw.dev",
            "password": "demo1234",
            "occupation": "医疗顾问",
            "apps": ["微信", "HIS系统", "钉钉", "支付宝"],
            "sensitive_fields": ["医疗记录", "手机号", "家庭住址", "身份证"],
            "onboarding_done": 1,
        },
        {
            "user_id": "demo_UserB",
            "username": "李主播",
            "email": "demo_userb@maskclaw.dev",
            "password": "demo1234",
            "occupation": "带货主播",
            "apps": ["微信", "抖音", "淘宝/天猫", "支付宝", "小红书"],
            "sensitive_fields": ["手机号", "家庭住址", "收款信息", "行程位置"],
            "onboarding_done": 1,
        },
        {
            "user_id": "demo_UserC",
            "username": "王明",
            "email": "demo_userc@maskclaw.dev",
            "password": "demo1234",
            "occupation": "普通职员",
            "apps": ["微信", "支付宝", "钉钉", "京东"],
            "sensitive_fields": ["手机号", "身份证", "银行卡", "家庭住址"],
            "onboarding_done": 1,
        },
    ]

    USER_SKILLS_ROOT.mkdir(parents=True, exist_ok=True)

    with _connect_users_db() as conn:
        cur = conn.cursor()
        for acc in accounts:
            cur.execute(
                "SELECT user_id FROM users WHERE user_id = ? OR email = ?",
                (acc["user_id"], acc["email"]),
            )
            if cur.fetchone():
                continue

            password_hash = bcrypt.hashpw(acc["password"].encode(), bcrypt.gensalt()).decode()
            cur.execute(
                """
                INSERT INTO users (
                    user_id, username, email, password_hash,
                    occupation, apps, sensitive_fields, onboarding_done, created_ts
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    acc["user_id"],
                    acc["username"],
                    acc["email"],
                    password_hash,
                    acc["occupation"],
                    json.dumps(acc["apps"], ensure_ascii=False),
                    json.dumps(acc["sensitive_fields"], ensure_ascii=False),
                    acc["onboarding_done"],
                    1700000000,
                ),
            )
        conn.commit()

    for acc in accounts:
        (USER_SKILLS_ROOT / acc["user_id"]).mkdir(parents=True, exist_ok=True)


def make_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return str(payload["user_id"])
    except Exception:
        return None


def get_user(user_id: str) -> dict[str, Any] | None:
    with _connect_users_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def _get_user_by_email(email: str) -> dict[str, Any] | None:
    with _connect_users_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail={"error": "missing_auth"})
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail={"error": "invalid_auth_header"})
    return parts[1].strip()


def _require_jwt_user(path_user_id: str, authorization: str | None) -> str:
    token = _extract_bearer_token(authorization)
    token_user_id = verify_token(token)
    if not token_user_id:
        raise HTTPException(status_code=401, detail={"error": "invalid_token"})
    if token_user_id != path_user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    return token_user_id


def _require_jwt_user_or_anonymous(authorization: str | None) -> str:
    """尝试从 Bearer token 解析 user_id；token 无效或缺失时返回匿名占位 ID。"""
    if not authorization:
        return "anonymous"
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return "anonymous"
    token_user_id = verify_token(parts[1].strip())
    if not token_user_id:
        return "anonymous"
    return token_user_id


def _safe_json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def event_to_summary(event: dict[str, Any]) -> str:
    app = APP_NAMES.get(event.get("app_context", ""), event.get("app_context", "未知应用"))
    action = ACTION_NAMES.get(event.get("action", ""), event.get("action", "执行操作"))
    correction = CORRECTION_NAMES.get(
        event.get("correction_type", ""), event.get("correction_type", "进行了纠正")
    )
    return f"在{app}场景下，Agent尝试{action}，你{correction}"


def _connect_skill_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SKILL_DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _date_key(ts: int) -> str:
    dt = datetime.fromtimestamp(int(ts))
    return f"{dt.year}年{dt.month}月{dt.day}日"


def _parse_event_types(raw: Optional[str]) -> set[str]:
    allowed = {"added", "reinforced", "conflict", "disabled"}
    if not raw:
        return allowed

    parsed = {p.strip() for p in raw.split(",") if p.strip()}
    valid = {p for p in parsed if p in allowed}
    return valid or allowed


def _range_bounds(range_name: str, from_ts: Optional[int], to_ts: Optional[int]) -> tuple[Optional[int], Optional[int]]:
    if from_ts is not None or to_ts is not None:
        return from_ts, to_ts

    now = int(time.time())
    if range_name == "week":
        return now - 7 * 24 * 3600, now
    if range_name == "month":
        return now - 30 * 24 * 3600, now
    return None, None


def _in_window(ts: int, start_ts: Optional[int], end_ts: Optional[int]) -> bool:
    if start_ts is not None and ts < start_ts:
        return False
    if end_ts is not None and ts > end_ts:
        return False
    return True


def _build_correction_events(
    user_id: str,
    start_ts: Optional[int],
    end_ts: Optional[int],
) -> list[dict[str, Any]]:
    log_path = MEMORY_ROOT / "logs" / user_id / "correction_log.jsonl"
    if not log_path.exists():
        return []

    events: list[dict[str, Any]] = []
    with log_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                raw = json.loads(line)
            except Exception:
                continue

            ts = int(raw.get("ts") or 0)
            if ts <= 0 or not _in_window(ts, start_ts, end_ts):
                continue

            correction_type = str(raw.get("correction_type") or "")
            if correction_type in {"user_denied", "user_blocked"}:
                event_type = "conflict"
                type_label = "规则冲突"
                source = "用户纠错"
                conflict_note = "用户拒绝或拦截，需重新确认规则边界"
                action_label = "解决冲突"
            elif correction_type == "user_modified":
                event_type = "added"
                type_label = "规则新增"
                source = "用户纠错"
                conflict_note = None
                action_label = "查看详情"
            else:
                event_type = "reinforced"
                type_label = "规则强化"
                source = "用户纠错"
                conflict_note = None
                action_label = "查看详情"

            app = APP_NAMES.get(str(raw.get("app_context") or ""), str(raw.get("app_context") or "未知应用"))
            field = str(raw.get("field") or "隐私规则")
            # 可读标题：去掉方括号和 slug 格式
            title = f"{app}规则{type_label.replace('规则', '')}"

            events.append(
                {
                    "event_id": str(raw.get("event_id") or f"corr-{user_id}-{line_no}"),
                    "ts": ts,
                    "date_key": _date_key(ts),
                    "event_type": event_type,
                    "type_label": type_label,
                    "skill_name": None,
                    "title": title,
                    "summary": event_to_summary(raw),
                    "source": source,
                    "trigger_delta": 1 if event_type == "reinforced" else 0,
                    "conflict_note": conflict_note,
                    "action_label": action_label,
                    "action_target": {
                        "kind": "correction_log",
                        "event_id": str(raw.get("event_id") or ""),
                    },
                    "processed": bool(raw.get("processed", False)),
                    "source_ref": f"correction_log.jsonl:{line_no}",
                }
            )

    return events


def _build_publish_events(
    user_id: str,
    start_ts: Optional[int],
    end_ts: Optional[int],
) -> list[dict[str, Any]]:
    if not SKILL_DB_PATH.exists():
        return []

    events: list[dict[str, Any]] = []
    with _connect_skill_db() as conn:
        rows = conn.execute(
            """
            SELECT id, skill_name, version, scene, rule_text, created_ts
            FROM skills
            WHERE user_id = ? AND path != ''
            ORDER BY created_ts DESC
            """,
            (user_id,),
        ).fetchall()

        first_version_map: dict[str, int] = {}
        first_rows = conn.execute(
            """
            SELECT skill_name, MIN(created_ts) AS first_ts
            FROM skills
            WHERE user_id = ? AND path != ''
            GROUP BY skill_name
            """,
            (user_id,),
        ).fetchall()
        for r in first_rows:
            first_version_map[str(r["skill_name"])] = int(r["first_ts"] or 0)

        archived_rows = conn.execute(
            """
            SELECT id, skill_name, version, scene, archived_ts, archived_reason
            FROM skills
            WHERE user_id = ? AND path = '' AND archived_ts IS NOT NULL
            ORDER BY archived_ts DESC
            """,
            (user_id,),
        ).fetchall()

    for row in rows:
        ts = int(row["created_ts"] or 0)
        if ts <= 0 or not _in_window(ts, start_ts, end_ts):
            continue

        skill_name = str(row["skill_name"] or "unknown-skill")
        version = str(row["version"] or "")
        first_ts = int(first_version_map.get(skill_name, 0))
        is_first = first_ts == ts

        event_type = "added" if is_first else "reinforced"
        type_label = "规则新增" if is_first else "规则强化"
        source = "自动推导"
        trigger_delta = 0 if is_first else 1

        app_name = APP_NAMES.get(str(row['scene'] or ''), str(row['scene'] or '未知'))
        # scene 字段本身已经是可读中文描述（如"在微信中浏览朋友圈内容"），直接用作标题
        skill_title = str(row['scene'] or skill_name)
        summary = (
            f"系统在 {app_name} 场景发布了 {skill_name} {version}"
        )

        events.append(
            {
                "event_id": f"sop-{row['id']}",
                "ts": ts,
                "date_key": _date_key(ts),
                "event_type": event_type,
                "type_label": type_label,
                "skill_name": skill_name,
                "title": f"{skill_title} {type_label}",
                "summary": summary,
                "source": source,
                "trigger_delta": trigger_delta,
                "conflict_note": None,
                "action_label": "查看详情",
                "action_target": {
                    "kind": "skill_version",
                    "skill_name": skill_name,
                    "version": version,
                },
                "processed": True,
                "source_ref": f"skills:{row['id']}",
            }
        )

    for row in archived_rows:
        ts = int(row["archived_ts"] or 0)
        if ts <= 0 or not _in_window(ts, start_ts, end_ts):
            continue

        skill_name = str(row["skill_name"] or "unknown-skill")
        version = str(row["version"] or "")
        reason = str(row["archived_reason"] or "策略停用")
        scene = str(row["scene"] or skill_name)

        events.append(
            {
                "event_id": f"arch-{row['id']}",
                "ts": ts,
                "date_key": _date_key(ts),
                "event_type": "disabled",
                "type_label": "规则停用",
                "skill_name": skill_name,
                "title": f"{scene} 规则停用",
                "summary": f"{skill_name} {version} 已停用，原因：{reason}",
                "source": "自动推导",
                "trigger_delta": 0,
                "conflict_note": None,
                "action_label": "查看详情",
                "action_target": {
                    "kind": "archived_skill",
                    "skill_name": skill_name,
                    "version": version,
                },
                "processed": True,
                "source_ref": f"skills:{row['id']}",
            }
        )

    return events


def _group_events_by_date(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        key = str(e.get("date_key") or "未知日期")
        grouped.setdefault(key, []).append(e)

    def date_sort_key(k: str) -> int:
        try:
            normalized = k.replace("年", "-").replace("月", "-").replace("日", "")
            dt = datetime.strptime(normalized, "%Y-%m-%d")
            return int(dt.timestamp())
        except Exception:
            return 0

    groups = []
    for key in sorted(grouped.keys(), key=date_sort_key, reverse=True):
        items = sorted(grouped[key], key=lambda x: int(x.get("ts") or 0), reverse=True)
        groups.append({"date": key, "items": items})

    return groups


def _read_jsonl_records(
    file_path: Path,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    if not file_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue

            ts = int(item.get("ts") or item.get("timestamp") or 0)
            if ts > 0 and not _in_window(ts, start_ts, end_ts):
                continue

            rows.append(
                {
                    "line_no": line_no,
                    "ts": ts,
                    "raw": item,
                }
            )

    rows.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)
    return rows[:limit]


def _parse_frontmatter(skill_md_path: Path) -> dict[str, Any]:
    if not skill_md_path.exists():
        return {}

    text = skill_md_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return {}

    data: dict[str, Any] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


def _scan_user_skills(user_id: str) -> list[dict[str, Any]]:
    user_root = USER_SKILLS_ROOT / user_id
    if not user_root.exists():
        return []

    items: list[dict[str, Any]] = []
    for skill_md in user_root.rglob("SKILL.md"):
        front = _parse_frontmatter(skill_md)
        stat = skill_md.stat()
        items.append(
            {
                "path": str(skill_md.relative_to(PROJECT_ROOT)),
                "mtime": int(stat.st_mtime),
                "size": int(stat.st_size),
                "name": front.get("name") or skill_md.parent.parent.name,
                "version": front.get("version") or skill_md.parent.name,
                "generated_ts": int(front.get("generated_ts") or 0),
                "confidence": front.get("confidence"),
                "status": front.get("status"),
                "meta": front,
            }
        )

    items.sort(key=lambda x: int(x.get("generated_ts") or x.get("mtime") or 0), reverse=True)
    return items


def _get_sop_versions_raw(user_id: str) -> list[dict[str, Any]]:
    if not SKILL_DB_PATH.exists():
        return []

    with _connect_skill_db() as conn:
        rows = conn.execute(
            """
            SELECT id, skill_name, version, app_context, task_description,
                   source_sessions, status, created_ts, path
            FROM sop_version
            WHERE user_id = ?
            ORDER BY created_ts DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _build_source_timeline(
    user_id: str,
    start_ts: Optional[int],
    end_ts: Optional[int],
    limit: int,
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []

    for row in _get_sop_versions_raw(user_id):
        ts = int(row.get("created_ts") or 0)
        if ts > 0 and not _in_window(ts, start_ts, end_ts):
            continue
        timeline.append(
            {
                "ts": ts,
                "date_key": _date_key(ts) if ts > 0 else "未知日期",
                "source_kind": "sop_version",
                "event_kind": "publish",
                "source_ref": f"sop_version:{row.get('id')}",
                "data": row,
            }
        )

    user_log_root = MEMORY_ROOT / "logs" / user_id
    for log_name in ["correction_log.jsonl", "behavior_log.jsonl", "session_trace.jsonl"]:
        file_path = user_log_root / log_name
        for item in _read_jsonl_records(file_path, start_ts=start_ts, end_ts=end_ts, limit=limit):
            raw = item["raw"]
            event_kind = "trace" if log_name == "session_trace.jsonl" else "runtime_event"
            timeline.append(
                {
                    "ts": int(item.get("ts") or 0),
                    "date_key": _date_key(item["ts"]) if int(item.get("ts") or 0) > 0 else "未知日期",
                    "source_kind": "log_jsonl",
                    "event_kind": event_kind,
                    "source_ref": f"{log_name}:{item['line_no']}",
                    "data": raw,
                }
            )

    timeline.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)
    return timeline[:limit]


@auth_router.on_event("startup")
def _init_auth_components() -> None:
    init_users_db()
    seed_demo_accounts()


@auth_router.post("/auth/register")
def register(payload: RegisterRequest):
    email = payload.email.strip().lower()
    password = payload.password
    username = payload.username.strip()

    if not email or not password or not username:
        raise HTTPException(status_code=400, detail={"error": "missing_fields"})

    with _connect_users_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail={"error": "email_exists"})

        user_id = str(uuid.uuid4())
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        created_ts = int(datetime.utcnow().timestamp())

        cur.execute(
            """
            INSERT INTO users (user_id, username, email, password_hash, onboarding_done, created_ts)
            VALUES (?, ?, ?, ?, 0, ?)
            """,
            (user_id, username, email, password_hash, created_ts),
        )
        conn.commit()

    (USER_SKILLS_ROOT / user_id).mkdir(parents=True, exist_ok=True)

    token = make_token(user_id)
    return {
        "user_id": user_id,
        "username": username,
        "token": token,
        "onboarding_done": False,
    }


@auth_router.post("/auth/login")
def login(payload: LoginRequest):
    email = payload.email.strip().lower()
    password = payload.password

    user = _get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail={"error": "invalid_credentials"})

    password_hash = str(user.get("password_hash", ""))
    if not password_hash or not bcrypt.checkpw(password.encode(), password_hash.encode()):
        raise HTTPException(status_code=401, detail={"error": "invalid_credentials"})

    token = make_token(str(user["user_id"]))
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "token": token,
        "onboarding_done": bool(user.get("onboarding_done", 0)),
    }


@auth_router.get("/user/profile/{user_id}")
def get_profile(user_id: str, authorization: str | None = Header(default=None)):
    _require_jwt_user(user_id, authorization)

    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "occupation": user.get("occupation"),
        "apps": _safe_json_list(user.get("apps")),
        "sensitive_fields": _safe_json_list(user.get("sensitive_fields")),
        "onboarding_done": bool(user.get("onboarding_done", 0)),
        "avatar_index": int(user.get("avatar_index") or 0),
        "grad_from": user.get("grad_from"),
        "grad_to": user.get("grad_to"),
    }


@auth_router.put("/user/profile/{user_id}")
def update_profile(
    user_id: str,
    payload: ProfileUpdateRequest,
    authorization: str | None = Header(default=None),
):
    _require_jwt_user(user_id, authorization)

    onboarding_value = None
    if payload.onboarding_done is not None:
        onboarding_value = 1 if payload.onboarding_done else 0

    # 先查用户是否存在
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    with _connect_users_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE users
            SET
                username = COALESCE(?, username),
                occupation = COALESCE(?, occupation),
                apps = COALESCE(?, apps),
                sensitive_fields = COALESCE(?, sensitive_fields),
                onboarding_done = COALESCE(?, onboarding_done),
                avatar_index = COALESCE(?, avatar_index),
                grad_from = COALESCE(?, grad_from),
                grad_to = COALESCE(?, grad_to)
            WHERE user_id = ?
            """,
            (
                payload.username,
                payload.occupation,
                json.dumps(payload.apps, ensure_ascii=False) if payload.apps is not None else None,
                json.dumps(payload.sensitive_fields, ensure_ascii=False)
                if payload.sensitive_fields is not None
                else None,
                onboarding_value,
                payload.avatar_index,
                payload.grad_from,
                payload.grad_to,
                user_id,
            ),
        )
        conn.commit()

    return {"ok": True}


@auth_router.post("/user/complete-onboarding/{user_id}")
def complete_onboarding(
    user_id: str,
    payload: ProfileUpdateRequest,
    authorization: str | None = Header(default=None),
):
    """
    完成 onboarding 的两步合一：
    1. 更新 users 表（profile 数据）
    2. 为新用户播种默认 Skill
    """
    _require_jwt_user(user_id, authorization)

    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail={"error": "not_found"})

    # ── 1. 更新 users 表 ───────────────────────────────────
    onboarding_value = 1 if payload.onboarding_done else 0

    with _connect_users_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE users
            SET
                username = COALESCE(?, username),
                occupation = COALESCE(?, occupation),
                apps = COALESCE(?, apps),
                sensitive_fields = COALESCE(?, sensitive_fields),
                onboarding_done = COALESCE(?, onboarding_done),
                avatar_index = COALESCE(?, avatar_index),
                grad_from = COALESCE(?, grad_from),
                grad_to = COALESCE(?, grad_to)
            WHERE user_id = ?
            """,
            (
                payload.username,
                payload.occupation,
                json.dumps(payload.apps, ensure_ascii=False) if payload.apps is not None else None,
                json.dumps(payload.sensitive_fields, ensure_ascii=False)
                if payload.sensitive_fields is not None
                else None,
                onboarding_value,
                payload.avatar_index,
                payload.grad_from,
                payload.grad_to,
                user_id,
            ),
        )
        conn.commit()

    # ── 2. 播种默认 Skill ──────────────────────────────────
    from skill_registry.skill_db import SkillDB
    PROJECT_ROOT = Path(__file__).parent
    skill_db = SkillDB(db_path=str(PROJECT_ROOT / "skill_registry" / "skill_registry.db"))
    seeded_count = skill_db.seed_default_skills_for_user(user_id)

    return {"ok": True, "seeded_skills": seeded_count}


@auth_router.get("/evolution/log/{user_id}")
def evolution_log(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    _require_jwt_user(user_id, authorization)

    log_path = MEMORY_ROOT / "logs" / user_id / "correction_log.jsonl"
    if not log_path.exists():
        return []

    events = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                events.append(
                    {
                        "event_id": event.get("event_id"),
                        "ts": event.get("ts"),
                        "summary": event_to_summary(event),
                        "event_type": event.get("correction_type"),
                        "app_context": event.get("app_context"),
                        "processed": event.get("processed", False),
                    }
                )
            except Exception:
                continue

    events.sort(key=lambda x: x.get("ts") or 0, reverse=True)
    return events[:limit]


@auth_router.get("/evolution/events/{user_id}")
def evolution_events(
    user_id: str,
    range: str = Query(default="all", pattern="^(week|month|all)$"),
    event_types: str | None = Query(default=None, description="逗号分隔: added,reinforced,conflict,disabled"),
    from_ts: int | None = Query(default=None),
    to_ts: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    _require_jwt_user(user_id, authorization)

    enabled_types = _parse_event_types(event_types)
    start_ts, end_ts = _range_bounds(range, from_ts, to_ts)

    merged = []
    merged.extend(_build_correction_events(user_id, start_ts, end_ts))
    merged.extend(_build_publish_events(user_id, start_ts, end_ts))

    merged = [e for e in merged if str(e.get("event_type")) in enabled_types]
    merged.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)

    total = len(merged)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = merged[start_idx:end_idx]

    return {
        "user_id": user_id,
        "range": range,
        "filters": {
            "event_types": sorted(enabled_types),
            "from_ts": start_ts,
            "to_ts": end_ts,
        },
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": end_idx < total,
        },
        "groups": _group_events_by_date(page_items),
    }


@auth_router.get("/evolution/stats/{user_id}")
def evolution_stats(
    user_id: str,
    authorization: str | None = Header(default=None),
):
    _require_jwt_user(user_id, authorization)

    now_ts = int(time.time())
    week_start = now_ts - 7 * 24 * 3600

    publish_events = _build_publish_events(user_id, None, None)
    correction_events = _build_correction_events(user_id, None, None)

    rules_total = sum(1 for e in publish_events if e.get("event_type") in {"added", "reinforced"})
    added_this_week = sum(
        1
        for e in publish_events
        if e.get("event_type") == "added" and int(e.get("ts") or 0) >= week_start
    )
    evolved_this_week = sum(
        1
        for e in (publish_events + correction_events)
        if int(e.get("ts") or 0) >= week_start
    )

    return {
        "user_id": user_id,
        "rules_total": rules_total,
        "added_this_week": added_this_week,
        "evolved_this_week": evolved_this_week,
        "summary_text": f"规则库共 {rules_total} 条 · 本周新增 {added_this_week} · 本周进化 {evolved_this_week} 次",
    }


@auth_router.get("/evolution/source/skills/{user_id}")
def evolution_source_skills(
    user_id: str,
    authorization: str | None = Header(default=None),
):
    _require_jwt_user(user_id, authorization)

    skills_from_files = _scan_user_skills(user_id)
    versions_from_db = _get_sop_versions_raw(user_id)

    return {
        "user_id": user_id,
        "from_user_skills": skills_from_files,
        "from_sop_version": versions_from_db,
    }


@auth_router.get("/evolution/source/logs/{user_id}")
def evolution_source_logs(
    user_id: str,
    log_type: str = Query(default="all", pattern="^(all|correction|behavior|session_trace)$"),
    from_ts: int | None = Query(default=None),
    to_ts: int | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    authorization: str | None = Header(default=None),
):
    _require_jwt_user(user_id, authorization)

    user_log_root = MEMORY_ROOT / "logs" / user_id
    mapping = {
        "correction": ["correction_log.jsonl"],
        "behavior": ["behavior_log.jsonl"],
        "session_trace": ["session_trace.jsonl"],
        "all": ["correction_log.jsonl", "behavior_log.jsonl", "session_trace.jsonl"],
    }
    targets = mapping[log_type]

    payload: dict[str, Any] = {"user_id": user_id, "log_type": log_type, "logs": {}}
    for name in targets:
        path = user_log_root / name
        payload["logs"][name] = _read_jsonl_records(path, start_ts=from_ts, end_ts=to_ts, limit=limit)

    return payload


@auth_router.get("/evolution/source/timeline/{user_id}")
def evolution_source_timeline(
    user_id: str,
    range: str = Query(default="all", pattern="^(week|month|all)$"),
    from_ts: int | None = Query(default=None),
    to_ts: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=500),
    authorization: str | None = Header(default=None),
):
    _require_jwt_user(user_id, authorization)

    start_ts, end_ts = _range_bounds(range, from_ts, to_ts)
    merged = _build_source_timeline(user_id, start_ts, end_ts, limit=5000)

    total = len(merged)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = merged[start_idx:end_idx]

    return {
        "user_id": user_id,
        "range": range,
        "filters": {
            "from_ts": start_ts,
            "to_ts": end_ts,
        },
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": end_idx < total,
        },
        "groups": _group_events_by_date(page_items),
    }


# ============== AutoGLM 任务执行接口（前端调用）===============

@auth_router.post("/task/run")
async def frontend_run_task(
    body: dict[str, Any],
    authorization: str | None = Header(default=None),
):
    """
    前端提交 AutoGLM 执行任务
    
    请求格式：
    {
        "task_description": "帮我在淘宝填收货地址"
    }
    
    返回：
    {
        "task_id": "xxx",
        "status": "pending",
        "stream_url": "/task/stream/xxx"
    }
    """
    user_id = _require_jwt_user_or_anonymous(authorization)
    
    task_description = body.get("task_description")
    if not task_description:
        raise HTTPException(status_code=400, detail="task_description 不能为空")
    
    # 调用 api_server 的任务接口
    from api_server import _tasks, _run_task_worker, Task, TaskStatus
    import uuid
    import threading
    
    task_id = str(uuid.uuid4())
    
    task = Task(
        task_id=task_id,
        user_id=user_id,
        task_description=task_description,
    )
    
    # 添加到全局任务列表
    with threading.Lock():
        from api_server import _tasks_lock
        _tasks_lock.acquire()
        try:
            _tasks[task_id] = task
        finally:
            _tasks_lock.release()
    
    # 启动工作线程执行任务
    thread = threading.Thread(target=_run_task_worker, args=(task,))
    thread.daemon = True
    thread.start()
    
    return {
        "task_id": task_id,
        "status": "pending",
        "stream_url": f"/task/stream/{task_id}",
        "message": "任务已提交，正在执行中",
    }


@auth_router.get("/task/stream/{task_id}")
async def frontend_stream_task(
    task_id: str,
    authorization: str | None = Header(default=None),
):
    """
    前端 SSE 流式推送任务执行日志
    """
    user_id = _require_jwt_user_or_anonymous(authorization)
    
    import asyncio
    import json
    
    async def event_generator():
        from asyncio import Queue as AsyncQueue
        from api_server import _sse_clients, _sse_lock, _tasks, _tasks_lock, TaskStatus
        
        client_queue: AsyncQueue = AsyncQueue()
        task_id_local = task_id
        
        def sse_callback(event_data: dict):
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
            yield {
                "event": "connected",
                "data": json.dumps({"task_id": task_id, "status": "connected"}),
            }
            
            while True:
                try:
                    data = await asyncio.wait_for(client_queue.get(), timeout=30)
                    yield {
                        "event": data.get("event_type", "message"),
                        "data": json.dumps(data.get("data", {})),
                    }
                except asyncio.TimeoutError:
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


@auth_router.get("/task/status/{task_id}")
def frontend_get_task_status(
    task_id: str,
    authorization: str | None = Header(default=None),
):
    """
    前端查询任务状态
    """
    user_id = _require_jwt_user_or_anonymous(authorization)
    
    from api_server import _tasks, _tasks_lock, TaskStatus
    
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


@auth_router.get("/task/logs/{task_id}")
def frontend_get_task_logs(
    task_id: str,
    authorization: str | None = Header(default=None),
):
    """
    前端获取任务的所有日志（结构化摘要）
    """
    user_id = _require_jwt_user_or_anonymous(authorization)
    
    from api_server import _tasks, _tasks_lock, _process_log_to_summary
    
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


@auth_router.post("/task/cancel/{task_id}")
def frontend_cancel_task(
    task_id: str,
    authorization: str | None = Header(default=None),
):
    """
    前端取消正在执行的任务
    """
    user_id = _require_jwt_user_or_anonymous(authorization)
    
    from api_server import _tasks, _tasks_lock, TaskStatus, _notify_sse_clients
    
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
        
        if task.process:
            try:
                task.process.terminate()
            except Exception:
                pass
    
    _notify_sse_clients(task_id, "task_cancelled", {
        "task_id": task_id,
        "message": "任务已取消",
    })
    
    return {
        "task_id": task_id,
        "status": "cancelled",
        "message": "任务已取消",
    }
