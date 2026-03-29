"""
Privacy Guard Telemetry Probe - Windows 端日志采集 SDK

功能：
1. 轻量级探针，Hook AutoGLM 操作并记录
2. 本地缓冲队列，避免网络阻塞
3. 异步上传到服务器

使用方式：
```python
from telemetry_probe import init, log_action

# 初始化（启动时调用一次）
init(user_id="win_user_001", server_url="http://your-server.com")

# Agent 执行操作时调用
log_action(
    action="agent_fill",
    app_context="taobao",
    field="phone_number",
    resolution="mask",
    agent_intent="自动填入手机号",
    pii_type="PHONE_NUMBER",
    masked_image_path="temp/masked_xxx.jpg",
    safe_image_path="temp/safe_xxx.jpg"
)
```
"""

import json
import os
import queue
import threading
import time
import uuid
from typing import Any, Dict, List, Optional

__version__ = "1.0.0"

# 全局配置
_config: Dict[str, Any] = {
    "user_id": "",
    "server_url": "",
    "api_key": "",
    "buffer_size": 10,
    "flush_interval": 5,  # 秒
    "max_retry": 3,
    "debug": False,
}

# 日志缓冲队列
_log_queue: queue.Queue = queue.Queue()
_upload_thread: Optional[threading.Thread] = None
_initialized = False


class LogEntry:
    """单条日志条目。"""

    def __init__(
        self,
        action: str,
        app_context: str,
        resolution: str,
        field: Optional[str] = None,
        agent_intent: Optional[str] = None,
        pii_type: Optional[str] = None,
        relationship_tag: Optional[str] = None,
        masked_image_path: Optional[str] = None,
        safe_image_path: Optional[str] = None,
        minicpm_reasoning: Optional[str] = None,
        rule_match: Optional[str] = None,
        quality_score: Optional[float] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        self.ts = int(time.time())
        self.event_id = f"{_config['user_id']}_{self.ts}_{uuid.uuid4().hex[:6]}"
        self.action = action
        self.app_context = app_context
        self.resolution = resolution
        self.field = field
        self.agent_intent = agent_intent
        self.pii_type = pii_type
        self.relationship_tag = relationship_tag
        self.masked_image_path = masked_image_path
        self.safe_image_path = safe_image_path
        self.minicpm_reasoning = minicpm_reasoning
        self.rule_match = rule_match
        self.quality_score = quality_score
        self.extra = extra or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "user_id": _config["user_id"],
            "ts": self.ts,
            "action": self.action,
            "app_context": self.app_context,
            "resolution": self.resolution,
            "field": self.field,
            "agent_intent": self.agent_intent,
            "pii_type": self.pii_type,
            "relationship_tag": self.relationship_tag,
            "masked_image_path": self.masked_image_path,
            "safe_image_path": self.safe_image_path,
            "minicpm_reasoning": self.minicpm_reasoning,
            "rule_match": self.rule_match,
            "quality_score": self.quality_score,
            **{k: v for k, v in self.extra.items() if v is not None},
        }


def init(
    user_id: str,
    server_url: str,
    api_key: str = "",
    buffer_size: int = 10,
    flush_interval: float = 5.0,
    debug: bool = False,
) -> None:
    """初始化 SDK。

    Args:
        user_id: 用户标识
        server_url: 服务器地址，如 "http://your-server.com"
        api_key: API 密钥（用于鉴权）
        buffer_size: 缓冲日志条数，达到此数量立即上传
        flush_interval: 定时上传间隔（秒）
        debug: 调试模式
    """
    global _initialized, _config, _upload_thread

    _config.update({
        "user_id": user_id,
        "server_url": server_url.rstrip("/"),
        "api_key": api_key,
        "buffer_size": buffer_size,
        "flush_interval": flush_interval,
        "debug": debug,
    })

    if _initialized:
        if _config["debug"]:
            print("[TelemetryProbe] 已初始化，跳过")
        return

    _initialized = True
    _upload_thread = threading.Thread(target=_upload_worker, daemon=True)
    _upload_thread.start()

    if _config["debug"]:
        print(f"[TelemetryProbe] 初始化完成 user_id={user_id}, server={server_url}")


def log_action(
    action: str,
    app_context: str,
    resolution: str,
    field: Optional[str] = None,
    agent_intent: Optional[str] = None,
    pii_type: Optional[str] = None,
    relationship_tag: Optional[str] = None,
    masked_image_path: Optional[str] = None,
    safe_image_path: Optional[str] = None,
    minicpm_reasoning: Optional[str] = None,
    rule_match: Optional[str] = None,
    quality_score: Optional[float] = None,
    **kwargs,
) -> str:
    """记录一条 Agent 操作。

    Args:
        action: 操作类型 (agent_fill, agent_click, share_or_send, view_record...)
        app_context: 应用上下文 (taobao, wechat, hospital_oa...)
        resolution: 决策结果 (allow, block, mask, ask, interrupt)
        field: 涉及的字段名 (phone_number, address, medical_record...)
        agent_intent: Agent 意图描述
        pii_type: PII 类型
        relationship_tag: 关系标签
        masked_image_path: 已打码图片路径（本地）
        safe_image_path: 最终安全版图片路径（本地）
        minicpm_reasoning: MiniCPM 推理结果
        rule_match: 匹配的规则名称
        quality_score: 质量评分

    Returns:
        event_id: 生成的唯一事件ID
    """
    if not _initialized:
        raise RuntimeError("TelemetryProbe 未初始化，请先调用 init()")

    entry = LogEntry(
        action=action,
        app_context=app_context,
        resolution=resolution,
        field=field,
        agent_intent=agent_intent,
        pii_type=pii_type,
        relationship_tag=relationship_tag,
        masked_image_path=masked_image_path,
        safe_image_path=safe_image_path,
        minicpm_reasoning=minicpm_reasoning,
        rule_match=rule_match,
        quality_score=quality_score,
        extra=kwargs,
    )

    _log_queue.put(entry)

    if _config["debug"]:
        print(f"[TelemetryProbe] 记录: {action} -> {resolution}")

    return entry.event_id


def log_agent_fill(
    field: str,
    value_preview: str,
    resolution: str,
    app_context: str = "unknown",
    agent_intent: Optional[str] = None,
    pii_type: Optional[str] = None,
    relationship_tag: Optional[str] = None,
    masked_image_path: Optional[str] = None,
    safe_image_path: Optional[str] = None,
    rule_match: Optional[str] = None,
    quality_score: Optional[float] = None,
    **kwargs,
) -> str:
    """快捷方法：记录 Agent 填入操作。"""
    return log_action(
        action="agent_fill",
        app_context=app_context,
        field=field,
        resolution=resolution,
        agent_intent=agent_intent or f"自动填入 {field}",
        pii_type=pii_type,
        relationship_tag=relationship_tag,
        masked_image_path=masked_image_path,
        safe_image_path=safe_image_path,
        rule_match=rule_match,
        quality_score=quality_score,
        extra={"value_preview": value_preview, **kwargs},
    )


def log_share_or_send(
    field: str,
    resolution: str,
    app_context: str = "unknown",
    agent_intent: Optional[str] = None,
    pii_type: Optional[str] = None,
    relationship_tag: Optional[str] = None,
    masked_image_path: Optional[str] = None,
    safe_image_path: Optional[str] = None,
    minicpm_reasoning: Optional[str] = None,
    rule_match: Optional[str] = None,
    quality_score: Optional[float] = None,
    **kwargs,
) -> str:
    """快捷方法：记录分享/发送操作。"""
    return log_action(
        action="share_or_send",
        app_context=app_context,
        field=field,
        resolution=resolution,
        agent_intent=agent_intent or f"准备分享/发送 {field}",
        pii_type=pii_type,
        relationship_tag=relationship_tag,
        masked_image_path=masked_image_path,
        safe_image_path=safe_image_path,
        minicpm_reasoning=minicpm_reasoning,
        rule_match=rule_match,
        quality_score=quality_score,
        **kwargs,
    )


def log_user_correction(
    original_action: str,
    correction_type: str,
    resolution: str,
    app_context: str = "unknown",
    field: Optional[str] = None,
    correction_value: Optional[str] = None,
    agent_intent: Optional[str] = None,
    **kwargs,
) -> str:
    """快捷方法：记录用户纠错操作。"""
    return log_action(
        action="user_correction",
        app_context=app_context,
        field=field,
        resolution=resolution,
        agent_intent=agent_intent,
        extra={
            "original_action": original_action,
            "correction_type": correction_type,
            "correction_value": correction_value,
            **kwargs,
        },
    )


def _upload_worker() -> None:
    """后台线程：定时上传日志。"""
    last_flush = time.time()
    batch: List[LogEntry] = []

    while True:
        time.sleep(0.5)  # 快速检查队列

        # 消费队列
        while not _log_queue.empty():
            try:
                entry = _log_queue.get_nowait()
                batch.append(entry)
            except queue.Empty:
                break

        now = time.time()
        should_flush = (
            len(batch) >= _config["buffer_size"]
            or (batch and now - last_flush >= _config["flush_interval"])
        )

        if should_flush:
            _do_upload(batch)
            batch = []
            last_flush = now


def _do_upload(batch: List[LogEntry]) -> None:
    """执行上传。"""
    if not batch:
        return

    try:
        import requests

        payload = {
            "user_id": _config["user_id"],
            "logs": [entry.to_dict() for entry in batch],
        }

        headers = {"Content-Type": "application/json"}
        if _config["api_key"]:
            headers["X-API-KEY"] = _config["api_key"]

        resp = requests.post(
            f"{_config['server_url']}/logs/upload",
            json=payload,
            headers=headers,
            timeout=5,
        )

        if resp.status_code == 200:
            if _config["debug"]:
                print(f"[TelemetryProbe] 上传成功: {len(batch)} 条")
        else:
            if _config["debug"]:
                print(f"[TelemetryProbe] 上传失败: {resp.status_code}")

    except Exception as e:
        if _config["debug"]:
            print(f"[TelemetryProbe] 上传异常: {e}")


def flush() -> int:
    """立即flush所有缓冲日志，返回flush的数量。"""
    batch = []
    while not _log_queue.empty():
        try:
            batch.append(_log_queue.get_nowait())
        except queue.Empty:
            break

    if batch:
        _do_upload(batch)

    return len(batch)


def get_queue_size() -> int:
    """返回当前缓冲队列大小。"""
    return _log_queue.qsize()
