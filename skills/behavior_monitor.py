"""Behavior monitor runtime module.

This file is the runtime implementation used by the project code.
It standardizes all events into the shared schema defined in log_schema.md.

日志分为两类（旧格式）：
- behavior_log.jsonl: 用户未参与的操作（level=1）
- correction_log.jsonl: 用户参与的操作（level=2）

新版格式（v2.0）：
- session_trace.jsonl: 结构化行为链，包含同一任务的所有动作
  使用 _scenario_tag 作为行为链的唯一识别标志
"""

import json
import os
import threading
import time
import uuid
from collections import defaultdict
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
    """按用户分组的日志记录器，只记录 correction_log。"""

    def __init__(self, user_id: str, base_dir: str = "memory/logs"):
        self.user_id = user_id
        self.base_dir = Path(base_dir)
        self.user_dir = self.base_dir / user_id
        self.correction_log_file = self.user_dir / "correction_log.jsonl"
        self._correction_lock = threading.Lock()

    def _ensure_dir(self) -> None:
        self.user_dir.mkdir(parents=True, exist_ok=True)

    def write_correction_log(self, record: Dict[str, Any]) -> None:
        """写入用户参与的日志（level=2）"""
        self._ensure_dir()
        _atomic_write_jsonl(self.correction_log_file, record, self._correction_lock)

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
    # v2.0 新增参数
    scenario_tag: Optional[str] = None,
    rule_type: str = "N",
    relationship_tag: Optional[str] = None,
    agent_intent: Optional[str] = None,
    quality_score: Optional[float] = None,
    quality_flag: Optional[str] = None,
) -> str:
    """核心日志记录接口 (v2.0 - 支持双写)。

    写入位置：
    1. 旧格式: behavior_log.jsonl / correction_log.jsonl (兼容)
    2. 新格式: session_trace.jsonl (结构化行为链)

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
        # v2.0 新增参数
        scenario_tag: 场景标签，用于行为链归一化（必填）
        rule_type: 规则类型 (H/S/N)
        relationship_tag: 关系标签
        agent_intent: Agent意图描述
        quality_score: 质量评分
        quality_flag: 质量标志

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

    # ========== v2.0 只写: session_trace.jsonl + correction_log.jsonl ==========
    logger = UserLogger(user_id=user_id, base_dir=base_dir)

    # 只写入 correction_log（纠错记录）
    if resolution not in ["allow", "block", "mask"]:
        logger.write_correction_log(record)

    # ========== v2.0: session_trace.jsonl ==========
    if scenario_tag:
        # 将 meta 信息传递给行为链记录器
        meta_fields = {
            "_rule_type": rule_type,
            "_pii_type": "|".join(pii_types_involved) if pii_types_involved else None,
            "_relationship_tag": relationship_tag,
            "_agent_intent": agent_intent,
            "_quality_score": quality_score,
            "_quality_flag": quality_flag,
        }
        meta_fields = {k: v for k, v in meta_fields.items() if v is not None}

        log_action_to_chain(
            user_id=user_id,
            action=action,
            resolution=resolution,
            scenario_tag=scenario_tag,
            app_context=app_context,
            field=field,
            value_preview=value_preview,
            correction_type=correction_type,
            correction_value=correction_value,
            rule_type=rule_type,
            pii_type=meta_fields.get("_pii_type"),
            relationship_tag=relationship_tag,
            agent_intent=agent_intent,
            quality_score=quality_score,
            quality_flag=quality_flag,
            base_dir=base_dir,
            auto_flush=(correction_type is not None),
        )

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


# ============== v2.0 结构化行为链日志 ==============

class TraceChainCache:
    """内存中的行为链缓存，按 user_id -> scenario_tag -> chain 分层管理。"""

    def __init__(self):
        # 结构: {user_id: {scenario_tag: chain_dict}}
        self._cache: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self._lock = threading.Lock()

    def get_or_create_chain(
        self,
        user_id: str,
        scenario_tag: str,
        app_context: str,
        rule_type: str,
    ) -> Dict[str, Any]:
        """获取或创建一条行为链。"""
        with self._lock:
            if scenario_tag not in self._cache[user_id]:
                chain_id = f"{user_id}_{scenario_tag}_{int(time.time())}"
                chain = {
                    "chain_id": chain_id,
                    "user_id": user_id,
                    "app_context": app_context,
                    "scenario_tag": scenario_tag,
                    "rule_type": rule_type or "N",
                    "start_ts": int(time.time()),
                    "end_ts": int(time.time()),
                    "action_count": 0,
                    "has_correction": False,
                    "correction_count": 0,
                    "final_resolution": "unknown",
                    "processed": False,
                    "actions": [],
                }
                self._cache[user_id][scenario_tag] = chain
            return self._cache[user_id][scenario_tag]

    def add_action(
        self,
        user_id: str,
        scenario_tag: str,
        action_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """向行为链添加一个动作。"""
        app_context = action_data.get("app_context", "unknown")
        rule_type = action_data.get("_rule_type", "N")

        chain = self.get_or_create_chain(user_id, scenario_tag, app_context, rule_type)

        with self._lock:
            action_index = chain["action_count"]
            is_correction = action_data.get("correction_type") not in (None, "")

            action_record = {
                "action_index": action_index,
                "ts": action_data.get("ts", int(time.time())),
                "action": action_data.get("action", "unknown"),
                "field": action_data.get("field"),
                "resolution": action_data.get("resolution", "unknown"),
                "value_preview": action_data.get("value_preview"),
                "is_correction": is_correction,
                "correction_type": action_data.get("correction_type"),
                "correction_value": action_data.get("correction_value"),
                "pii_type": action_data.get("_pii_type"),
                "relationship_tag": action_data.get("_relationship_tag"),
                "agent_intent": action_data.get("_agent_intent"),
                "quality_score": action_data.get("_quality_score"),
                "quality_flag": action_data.get("_quality_flag"),
            }

            # 只保留非 None 的字段
            action_record = {k: v for k, v in action_record.items() if v is not None}

            chain["actions"].append(action_record)
            chain["action_count"] += 1
            chain["end_ts"] = action_record["ts"]
            chain["final_resolution"] = action_record["resolution"]

            if is_correction:
                chain["has_correction"] = True
                chain["correction_count"] += 1

            return chain

    def get_all_chains(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有行为链。"""
        with self._lock:
            return list(self._cache.get(user_id, {}).values())

    def get_chain(self, user_id: str, scenario_tag: str) -> Optional[Dict[str, Any]]:
        """获取指定的行为链。"""
        with self._lock:
            return self._cache.get(user_id, {}).get(scenario_tag)

    def flush_chain(self, user_id: str, scenario_tag: str) -> Optional[Dict[str, Any]]:
        """将行为链从缓存移除并返回（用于持久化）。"""
        with self._lock:
            chain = self._cache.get(user_id, {}).pop(scenario_tag, None)
            return chain


# 全局行为链缓存实例
_trace_chain_cache = TraceChainCache()


class TraceChainLogger:
    """v2.0 结构化行为链日志记录器。"""

    def __init__(self, user_id: str, base_dir: str = "memory/logs"):
        self.user_id = user_id
        self.base_dir = Path(base_dir)
        self.user_dir = self.base_dir / user_id
        self.trace_file = self.user_dir / "session_trace.jsonl"
        self._lock = threading.Lock()

    def _ensure_dir(self) -> None:
        self.user_dir.mkdir(parents=True, exist_ok=True)

    def write_chain(self, chain: Dict[str, Any]) -> None:
        """持久化一条行为链到 session_trace.jsonl。"""
        self._ensure_dir()
        with self._lock:
            with self.trace_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(chain, ensure_ascii=False) + "\n")

    def read_chains(self, limit: int = 100, unprocessed_only: bool = False) -> List[Dict[str, Any]]:
        """读取行为链日志。"""
        if not self.trace_file.exists():
            return []

        chains = []
        with self._lock:
            with self.trace_file.open("r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    if line.strip():
                        try:
                            chain = json.loads(line)
                            if unprocessed_only and chain.get("processed"):
                                continue
                            chains.append(chain)
                        except json.JSONDecodeError:
                            continue
        return chains

    def mark_processed(self, chain_id: str) -> bool:
        """标记行为链已处理。"""
        if not self.trace_file.exists():
            return False

        updated_lines = []
        found = False
        with self._lock:
            with self.trace_file.open("r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:
                if line.strip():
                    try:
                        chain = json.loads(line)
                        if chain.get("chain_id") == chain_id:
                            chain["processed"] = True
                            found = True
                        updated_lines.append(json.dumps(chain, ensure_ascii=False) + "\n")
                    except json.JSONDecodeError:
                        updated_lines.append(line)

            if found:
                with self.trace_file.open("w", encoding="utf-8") as f:
                    f.writelines(updated_lines)

        return found


def log_action_to_chain(
    user_id: str,
    action: str,
    resolution: str,
    scenario_tag: str,
    app_context: str,
    field: Optional[str] = None,
    value_preview: Optional[str] = None,
    correction_type: Optional[str] = None,
    correction_value: Optional[str] = None,
    rule_type: str = "N",
    pii_type: Optional[str] = None,
    relationship_tag: Optional[str] = None,
    agent_intent: Optional[str] = None,
    quality_score: Optional[float] = None,
    quality_flag: Optional[str] = None,
    base_dir: str = "memory/logs",
    auto_flush: bool = False,
) -> Dict[str, Any]:
    """v2.0 核心日志记录接口 - 写入结构化行为链。

    Args:
        user_id: 用户标识
        action: 操作类型
        resolution: 决策结果 (allow/block/mask/ask/interrupt)
        scenario_tag: 场景标签，作为行为链的唯一识别标志
        app_context: 应用上下文
        field: 字段名
        value_preview: 脱敏后的预览值
        correction_type: 纠错类型 (user_denied/user_modified/user_interrupted)
        correction_value: 用户修正后的替代值
        rule_type: 规则类型 (H/S/N)
        pii_type: PII类型
        relationship_tag: 关系标签
        agent_intent: Agent意图描述
        quality_score: 质量评分
        quality_flag: 质量标志
        base_dir: 日志根目录
        auto_flush: 是否在纠错后自动持久化

    Returns:
        更新后的行为链
    """
    ts = int(time.time())

    action_data = {
        "ts": ts,
        "action": action,
        "resolution": resolution,
        "field": field,
        "value_preview": value_preview,
        "correction_type": correction_type,
        "correction_value": correction_value,
        "_rule_type": rule_type,
        "_pii_type": pii_type,
        "_relationship_tag": relationship_tag,
        "_agent_intent": agent_intent,
        "_quality_score": quality_score,
        "_quality_flag": quality_flag,
        "app_context": app_context,
    }

    # 添加到内存缓存
    chain = _trace_chain_cache.add_action(user_id, scenario_tag, action_data)

    # 如果是纠错动作，自动持久化
    if auto_flush and correction_type:
        flush_and_save_chain(user_id, scenario_tag, base_dir)

    return chain


def flush_and_save_chain(user_id: str, scenario_tag: str, base_dir: str = "memory/logs") -> Optional[Dict[str, Any]]:
    """将行为链从缓存持久化到磁盘。"""
    chain = _trace_chain_cache.flush_chain(user_id, scenario_tag)
    if chain:
        logger = TraceChainLogger(user_id, base_dir)
        logger.write_chain(chain)
    return chain


def flush_all_user_chains(user_id: str, base_dir: str = "memory/logs") -> int:
    """将用户所有未持久化的行为链持久化到磁盘。"""
    chains = _trace_chain_cache.get_all_chains(user_id)
    count = 0
    for chain in chains:
        scenario_tag = chain.get("scenario_tag", "")
        if scenario_tag:
            flush_and_save_chain(user_id, scenario_tag, base_dir)
            count += 1
    return count


def get_pending_chains(user_id: str, base_dir: str = "memory/logs") -> List[Dict[str, Any]]:
    """获取用户未处理的行为链（从缓存和磁盘）。"""
    chains = []

    # 从缓存获取
    chains.extend(_trace_chain_cache.get_all_chains(user_id))

    # 从磁盘获取未处理的
    logger = TraceChainLogger(user_id, base_dir)
    chains.extend(logger.read_chains(unprocessed_only=True))

    # 去重（基于 chain_id）
    seen = set()
    unique_chains = []
    for chain in chains:
        cid = chain.get("chain_id")
        if cid and cid not in seen:
            seen.add(cid)
            unique_chains.append(chain)

    return unique_chains


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
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    print("=" * 60)
    print("测试 v2.0 结构化行为链日志")
    print("=" * 60)

    # 测试1: 使用新接口 log_action_to_chain
    print("\n=== 测试 log_action_to_chain (v2.0) ===\n")

    # 模拟一个行为链：Agent 尝试分享病历，用户拒绝
    chain_1 = log_action_to_chain(
        user_id="test_user_v2",
        action="share_or_send",
        resolution="block",
        scenario_tag="钉钉发送病历截图给同事",
        app_context="钉钉",
        field="medical_record",
        value_preview="screenshot.png",
        rule_type="H",
        pii_type="MedicalRecord",
        relationship_tag="同科室同事",
        agent_intent="发送病历截图到钉钉对话",
        quality_score=3.6,
        quality_flag="pass",
        base_dir="memory/logs",
        auto_flush=False,  # 先累积动作，最后再持久化
    )
    print(f"1. 添加动作到链: {chain_1['chain_id']}, action_count={chain_1['action_count']}")

    # 同一场景的第二次尝试（模拟 UI 更新后）
    chain_2 = log_action_to_chain(
        user_id="test_user_v2",
        action="share_or_send",
        resolution="block",
        scenario_tag="钉钉发送病历截图给同事",
        app_context="钉钉",
        field="medical_record",
        value_preview="screenshot.png",
        rule_type="H",
        pii_type="MedicalRecord",
        relationship_tag="同科室同事",
        agent_intent="新版钉钉UI结构调整后发送病历截图",
        quality_score=3.6,
        quality_flag="pass",
        base_dir="memory/logs",
        auto_flush=False,
    )
    print(f"2. 添加动作到链: {chain_2['chain_id']}, action_count={chain_2['action_count']}")

    # 用户纠错动作 - 会触发 auto_flush
    chain_3 = log_action_to_chain(
        user_id="test_user_v2",
        action="share_or_send",
        resolution="correction",
        scenario_tag="钉钉发送病历截图给同事",
        app_context="钉钉",
        field="medical_record",
        value_preview="screenshot.png",
        correction_type="user_denied",
        correction_value=None,
        rule_type="H",
        pii_type="MedicalRecord",
        relationship_tag="同科室同事",
        agent_intent="发送病历截图到钉钉对话",
        quality_score=3.6,
        quality_flag="pass",
        base_dir="memory/logs",
        auto_flush=True,  # 纠错后自动持久化
    )
    print(f"3. 纠错动作 (auto_flush): {chain_3['chain_id']}")
    print(f"   has_correction={chain_3['has_correction']}, correction_count={chain_3['correction_count']}")

    # 验证 session_trace.jsonl
    trace_logger = TraceChainLogger("test_user_v2", base_dir="memory/logs")
    print("\n=== session_trace.jsonl 内容 ===")
    for chain in trace_logger.read_chains(limit=10):
        print(f"\nchain_id: {chain['chain_id']}")
        print(f"  scenario_tag: {chain['scenario_tag']}")
        print(f"  action_count: {chain['action_count']}")
        print(f"  has_correction: {chain['has_correction']}")
        print(f"  actions:")
        for act in chain.get("actions", []):
            print(f"    - [{act['action_index']}] ts={act['ts']}, action={act['action']}, "
                  f"resolution={act['resolution']}, is_correction={act['is_correction']}")

    # 测试2: 使用旧的 log_event (双写)
    print("\n" + "=" * 60)
    print("=== 测试 log_event (双写模式) ===")
    print("=" * 60 + "\n")

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
        scenario_tag="淘宝填写收货地址",
        rule_type="S",
        relationship_tag="本人",
        agent_intent="自动填充家庭地址",
    )
    print(f"1. allow 操作 (level=1): {event_id_1}")

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
        scenario_tag="淘宝填写联系方式",
        rule_type="H",
        relationship_tag="本人",
        agent_intent="自动填充手机号",
    )
    print(f"2. ask 操作 (level=2): {event_id_2}")

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
        scenario_tag="淘宝填写联系方式",
        rule_type="H",
        relationship_tag="本人",
        agent_intent="自动填充手机号",
    )
    print(f"3. user_modified: {event_id_3}")

    # 验证旧格式文件
    logger = UserLogger("win_user_001", base_dir="memory/logs")
    print("\n=== behavior_log.jsonl (最后3条) ===")
    for r in logger.read_behavior_logs(limit=3):
        print(json.dumps(r, ensure_ascii=False))

    print("\n=== correction_log.jsonl (最后3条) ===")
    for r in logger.read_correction_logs(limit=3):
        print(json.dumps(r, ensure_ascii=False))

    print("\n=== session_trace.jsonl (淘宝相关) ===")
    for chain in trace_logger.read_chains(limit=10):
        if "淘宝" in chain.get("scenario_tag", ""):
            print(json.dumps(chain, ensure_ascii=False, indent=2))

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)
