"""Behavior monitor runtime module.

This file is the runtime implementation used by the project code.
It standardizes all events into the shared schema defined in log_schema.md.

日志分为两类：
- behavior_log.jsonl: 用户未参与的操作（level=1）
- correction_log.jsonl: 用户参与的操作（level=2）
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# 默认过期时间配置（单位：秒）
DEFAULT_EXPIRE_SECONDS = {
    "allow": 24 * 3600,   # allow: 24小时
    "block": 24 * 3600,   # block: 24小时
    "mask": 24 * 3600,    # mask: 24小时
    "ask": 7 * 24 * 3600, # ask: 7天
    "defer": 7 * 24 * 3600,  # defer: 7天
    "interrupt": 7 * 24 * 3600,  # interrupt: 7天
}

CORRECTION_ACTION_MAP = {
    "clear": "user_modified",
    "delete": "user_modified",
    "undo": "user_modified",
    "cancel": "user_denied",
    "back": "user_interrupted",
    "input": "user_modified",
    "fill": "user_modified",
    "select": "user_modified",
}


def infer_correction(action: str) -> str:
    return CORRECTION_ACTION_MAP.get(str(action).lower(), "")


def normalize_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for raw in events:
        ts = raw.get("timestamp")
        if ts is None:
            ts = int(time.time())
        elif isinstance(ts, str):
            try:
                ts = int(datetime.fromisoformat(ts).timestamp())
            except ValueError:
                ts = int(time.time())

        action = str(raw.get("action", ""))
        correction = str(raw.get("correction", "")).strip() or infer_correction(action)
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {"raw_metadata": metadata}

        records.append(
            {
                "timestamp": int(ts),
                "action": action,
                "correction": correction,
                "metadata": metadata,
            }
        )
    return records


def build_report(records: List[Dict[str, Any]], session_id: Optional[str] = None) -> Dict[str, Any]:
    sid = session_id or f"sess-{uuid.uuid4().hex[:12]}"
    correction_count = sum(1 for r in records if r.get("correction"))
    return {
        "session_id": sid,
        "record_count": len(records),
        "records": records,
        "summary": {"correction_count": correction_count},
    }


def _atomic_write_jsonl(file_path: Path, record: Dict[str, Any], lock: threading.Lock) -> None:
    """线程安全的 JSONL 原子写入。

    使用文件锁 + 追加写入确保原子性和线程安全。
    """
    with lock:
        # 确保目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # 直接用 'a' 模式追加写入（原子操作）
        with file_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class UserLogger:
    """按用户分组的日志记录器，支持 behavior_log 和 correction_log 分离。"""

    def __init__(self, user_id: str, base_dir: str = "memory/logs"):
        self.user_id = user_id
        self.base_dir = Path(base_dir)
        self.user_dir = self.base_dir / user_id
        self.behavior_log_file = self.user_dir / "behavior_log.jsonl"
        self.correction_log_file = self.user_dir / "correction_log.jsonl"
        self._behavior_lock = threading.Lock()
        self._correction_lock = threading.Lock()

    def _ensure_dir(self) -> None:
        self.user_dir.mkdir(parents=True, exist_ok=True)

    def write_behavior_log(self, record: Dict[str, Any]) -> None:
        """写入用户未参与的日志（level=1）"""
        self._ensure_dir()
        _atomic_write_jsonl(self.behavior_log_file, record, self._behavior_lock)

    def write_correction_log(self, record: Dict[str, Any]) -> None:
        """写入用户参与的日志（level=2）"""
        self._ensure_dir()
        _atomic_write_jsonl(self.correction_log_file, record, self._correction_lock)

    def read_behavior_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """读取最近的 behavior 日志"""
        if not self.behavior_log_file.exists():
            return []
        records = []
        with self._behavior_lock:
            with self.behavior_log_file.open("r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    if line.strip():
                        records.append(json.loads(line))
        return records

    def read_correction_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """读取最近的 correction 日志"""
        if not self.correction_log_file.exists():
            return []
        records = []
        with self._correction_lock:
            with self.correction_log_file.open("r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    if line.strip():
                        records.append(json.loads(line))
        return records


def log_event(
    user_id: str,
    app_context: str,
    action: str,
    field: Optional[str],
    resolution: str,
    level: int,
    value_preview: Optional[str] = None,
    correction_type: Optional[str] = None,
    correction_value: Optional[str] = None,
    pii_types_involved: Optional[List[str]] = None,
    base_dir: str = "memory/logs",
    expire_seconds: Optional[int] = None,
) -> str:
    """核心日志记录接口。

    Args:
        user_id: 用户标识
        app_context: 应用上下文（如 "taobao", "wechat"）
        action: 操作类型（如 "agent_fill", "user_input"）
        field: 字段名（如 "home_address"）
        resolution: 决策结果（allow/block/mask/ask/defer/interrupt）
        level: 日志级别（1=用户未参与, 2=用户参与）
        value_preview: 脱敏后的预览值
        correction_type: 修正类型（user_modified/user_denied/user_interrupted）
        correction_value: 用户修正后的替代值
        pii_types_involved: 涉及的 PII 类型列表
        base_dir: 日志根目录
        expire_seconds: 自定义过期秒数（默认根据 resolution 自动选择）

    Returns:
        event_id: 生成的唯一事件ID
    """
    ts = int(time.time())
    event_id = f"{user_id}_{ts}_{uuid.uuid4().hex[:6]}"

    # 计算过期时间
    if expire_seconds is None:
        expire_seconds = DEFAULT_EXPIRE_SECONDS.get(resolution, 7 * 24 * 3600)
    expire_ts = ts + expire_seconds

    # 构建记录
    record: Dict[str, Any] = {
        "event_id": event_id,
        "user_id": user_id,
        "ts": ts,
        "app_context": app_context,
        "action": action,
        "field": field,
        "resolution": resolution,
        "level": level,
        "value_preview": value_preview,
        "correction_type": correction_type,
        "correction_value": correction_value,
        "pii_types_involved": pii_types_involved or [],
        "processed": False,
        "expire_ts": expire_ts,
    }

    logger = UserLogger(user_id=user_id, base_dir=base_dir)

    # 根据 resolution 决定写入哪些文件
    if resolution in ["allow", "block", "mask"]:
        # level=1: 只写 behavior_log
        logger.write_behavior_log(record)
    else:
        # level=2: 同时写 behavior_log 和 correction_log
        logger.write_behavior_log(record)
        logger.write_correction_log(record)

    return event_id


class SessionLogger:
    """Legacy: 兼容旧的 session 模式日志记录器。"""

    def __init__(self, base_dir: str = "logs"):
        self.base_dir = Path(base_dir)
        self.session_id = ""
        self.session_dir: Optional[Path] = None
        self.log_file: Optional[Path] = None
        self._lock = threading.Lock()

    def create_session(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_id = f"sess-{timestamp}-{uuid.uuid4().hex[:6]}"
        self.session_dir = self.base_dir / self.session_id
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.session_dir / "action_trace.jsonl"
        return self.session_id

    def write_record(self, record: Dict[str, Any]) -> None:
        if self.log_file is None:
            raise RuntimeError("Session not initialized")
        with self._lock:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")


class BehaviorMonitor:
    """Runtime behavior monitor with normalized output contract."""

    def __init__(self, device: Any = None, base_dir: str = "logs"):
        self.device = device
        self.session = SessionLogger(base_dir)
        self.session_id = self.session.create_session()
        self._lock = threading.Lock()
        self._records: List[Dict[str, Any]] = []
        self.is_monitoring = False
        self._user_id: Optional[str] = None
        self._app_context: Optional[str] = None

    def set_user_context(self, user_id: str, app_context: str = "") -> None:
        """设置用户上下文，供后续 log_event 使用。"""
        self._user_id = user_id
        self._app_context = app_context

    def _append_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        normalized = normalize_events([record])[0]
        self.session.write_record(normalized)
        with self._lock:
            self._records.append(normalized)
        return normalized

    def register_event(
        self,
        action: str,
        correction: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._append_record(
            {
                "timestamp": int(timestamp or time.time()),
                "action": action,
                "correction": correction,
                "metadata": metadata or {},
            }
        )

    def register_agent_action(
        self,
        target_id: str,
        text: str,
        reason: str = "",
        action_type: str = "input",
        screenshot: bool = False,
    ) -> Dict[str, Any]:
        action = action_type if action_type.startswith("agent_") else f"agent_{action_type}"
        metadata: Dict[str, Any] = {
            "role": "agent",
            "target_id": target_id,
            "content": text,
            "reason": reason,
            "screenshot_enabled": bool(screenshot),
        }
        return self.register_event(action=action, correction="", metadata=metadata)

    def register_user_action(self, action: str, target_id: str = "", content: str = "") -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "role": "user",
            "target_id": target_id,
            "content": content,
        }
        correction = infer_correction(action)
        return self.register_event(action=action, correction=correction, metadata=metadata)

    def register_system_event(self, event: str, details: str = "") -> Dict[str, Any]:
        return self.register_event(
            action=f"system_{event}",
            correction="",
            metadata={"role": "system", "details": details},
        )

    def start(self) -> None:
        self.is_monitoring = True

    def stop(self) -> None:
        self.is_monitoring = False

    def get_logs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._records)

    def export(self) -> Dict[str, Any]:
        return build_report(self.get_logs(), session_id=self.session_id)


if __name__ == "__main__":
    # 测试新的 log_event 接口
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    print("=== 测试 log_event ===\n")

    # 测试1: 用户未参与的 allow 操作
    event_id_1 = log_event(
        user_id="win_user_001",
        app_context="taobao",
        action="agent_fill",
        field="home_address",
        resolution="allow",
        level=1,
        value_preview="北京市海淀区xx路",
        pii_types_involved=["address"],
        base_dir="memory/logs",
    )
    print(f"1. allow 操作 (level=1): {event_id_1}")

    # 测试2: 用户参与的 ask 操作
    event_id_2 = log_event(
        user_id="win_user_001",
        app_context="taobao",
        action="agent_fill",
        field="phone_number",
        resolution="ask",
        level=2,
        value_preview="138****1234",
        pii_types_involved=["phone"],
        base_dir="memory/logs",
    )
    print(f"2. ask 操作 (level=2): {event_id_2}")

    # 测试3: 用户修正了操作
    event_id_3 = log_event(
        user_id="win_user_001",
        app_context="taobao",
        action="agent_fill",
        field="phone_number",
        resolution="ask",
        level=2,
        value_preview="138****1234",
        correction_type="user_modified",
        correction_value="公司电话",
        pii_types_involved=["phone"],
        base_dir="memory/logs",
    )
    print(f"3. user_modified: {event_id_3}")

    # 验证写入的文件
    logger = UserLogger("win_user_001", base_dir="memory/logs")
    print("\n=== behavior_log.jsonl ===")
    for r in logger.read_behavior_logs(limit=10):
        print(json.dumps(r, ensure_ascii=False))

    print("\n=== correction_log.jsonl ===")
    for r in logger.read_correction_logs(limit=10):
        print(json.dumps(r, ensure_ascii=False))

    print("\n测试完成!")
