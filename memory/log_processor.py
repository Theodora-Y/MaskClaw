"""
LogProcessor - 异步日志处理队列

功能：
1. 接收 Windows 客户端上传的原始日志
2. 调用 MiniCPM 整理成可视化摘要
3. 通过 SSE 推送到前端
4. 持久化到 behavior_log.jsonl / correction_log.jsonl
"""

import json
import queue
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# 存储所有活跃的 SSE 客户端回调
_sse_clients: Dict[str, List[Callable]] = {}
_sse_lock = threading.Lock()


def register_sse_client(user_id: str, callback: Callable) -> None:
    """注册 SSE 客户端回调。"""
    with _sse_lock:
        if user_id not in _sse_clients:
            _sse_clients[user_id] = []
        _sse_clients[user_id].append(callback)


def unregister_sse_client(user_id: str, callback: Callable) -> None:
    """取消注册 SSE 客户端。"""
    with _sse_lock:
        if user_id in _sse_clients:
            try:
                _sse_clients[user_id].remove(callback)
            except ValueError:
                pass


def _notify_sse_clients(user_id: str, data: Dict[str, Any]) -> None:
    """通知所有 SSE 客户端。"""
    with _sse_lock:
        callbacks = _sse_clients.get(user_id, [])

    for callback in callbacks:
        try:
            callback(data)
        except Exception:
            pass


class LogProcessor:
    """异步日志处理器。"""

    def __init__(
        self,
        incoming_dir: str = "memory/incoming",
        logs_dir: str = "memory/logs",
        minicpm_url: str = "http://127.0.0.1:8000/chat",
        batch_size: int = 5,
        process_interval: float = 2.0,
    ):
        self.incoming_dir = Path(incoming_dir)
        self.logs_dir = Path(logs_dir)
        self.minicpm_url = minicpm_url
        self.batch_size = batch_size
        self.process_interval = process_interval

        # 创建目录
        self.incoming_dir.mkdir(parents=True, exist_ok=True)

        # 消息队列
        self._queue: queue.Queue = queue.Queue()

        # 启动处理线程
        self._running = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True)
        self._thread.start()

    def submit(self, user_id: str, logs: List[Dict[str, Any]]) -> int:
        """提交日志批次到处理队列。

        Args:
            user_id: 用户 ID
            logs: 日志列表

        Returns:
            提交的日志数量
        """
        # 先写入 incoming 目录
        self._save_raw_logs(user_id, logs)

        # 入队
        for log in logs:
            self._queue.put((user_id, log))

        return len(logs)

    def _save_raw_logs(self, user_id: str, logs: List[Dict[str, Any]]) -> None:
        """保存原始日志到 incoming 目录。"""
        user_dir = self.incoming_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        raw_file = user_dir / "raw_logs.jsonl"
        with raw_file.open("a", encoding="utf-8") as f:
            for log in logs:
                f.write(json.dumps(log, ensure_ascii=False) + "\n")

    def _process_loop(self) -> None:
        """后台处理循环。"""
        batch: List[tuple] = []
        last_process = time.time()

        while self._running:
            try:
                # 非阻塞获取
                try:
                    item = self._queue.get_nowait()
                    batch.append(item)
                except queue.Empty:
                    pass

                now = time.time()
                should_process = (
                    len(batch) >= self.batch_size
                    or (batch and now - last_process >= self.process_interval)
                )

                if should_process and batch:
                    self._process_batch(batch)
                    batch = []
                    last_process = now

                time.sleep(0.5)

            except Exception:
                pass

    def _process_batch(self, batch: List[tuple]) -> None:
        """处理一批日志。"""
        for user_id, log in batch:
            try:
                processed = self._process_single_log(log)

                # SSE 推送到前端
                _notify_sse_clients(user_id, processed)

                # 持久化到日志文件
                self._persist_log(user_id, log, processed)

            except Exception:
                pass

    def _process_single_log(self, log: Dict[str, Any]) -> Dict[str, Any]:
        """处理单条日志，生成可视化摘要。"""
        ts = log.get("ts", int(time.time()))
        action = log.get("action", "unknown")
        resolution = log.get("resolution", "unknown")
        agent_intent = log.get("agent_intent", "")
        pii_type = log.get("pii_type", "")
        rule_match = log.get("rule_match", "")
        minicpm_reasoning = log.get("minicpm_reasoning", "")

        # 如果没有 MiniCPM 推理，生成默认摘要
        if not minicpm_reasoning:
            if resolution == "block":
                minicpm_reasoning = f"匹配规则 [{rule_match or '隐私保护策略'}]，已阻止 {action}"
            elif resolution == "mask":
                minicpm_reasoning = f"检测到 [{pii_type}]，已自动打码"
            elif resolution == "allow":
                minicpm_reasoning = f"未检测到敏感信息，{action} 已放行"
            else:
                minicpm_reasoning = f"处理完成: {resolution}"

        # 构建可视化摘要
        summary = {
            # Action Metadata
            "action_metadata": {
                "action": action,
                "description": agent_intent or f"执行 {action}",
                "app_context": log.get("app_context", "unknown"),
                "field": log.get("field"),
            },
            # L1 静态识别
            "l1_detection": {
                "pii_type": pii_type,
                "rule_match": rule_match,
                "masked_preview": log.get("masked_image_path"),
            },
            # L2 MiniCPM 推理
            "l2_reasoning": {
                "reasoning": minicpm_reasoning,
                "resolution": resolution,
                "quality_score": log.get("quality_score"),
            },
            # Outcome
            "outcome": {
                "final_image": log.get("safe_image_path"),
                "resolution": resolution,
                "event_id": log.get("event_id"),
                "ts": ts,
            },
            # 原始数据（供调试）
            "_raw": log,
        }

        return summary

    def _persist_log(self, user_id: str, raw_log: Dict[str, Any], processed: Dict[str, Any]) -> None:
        """持久化日志到 behavior_log.jsonl / correction_log.jsonl。"""
        user_dir = self.logs_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        ts = raw_log.get("ts", int(time.time()))
        event_id = raw_log.get("event_id", f"{user_id}_{ts}")
        resolution = raw_log.get("resolution", "unknown")

        # 基础记录
        record = {
            "event_id": event_id,
            "user_id": user_id,
            "ts": ts,
            "app_context": raw_log.get("app_context", "unknown"),
            "action": raw_log.get("action", "unknown"),
            "field": raw_log.get("field"),
            "resolution": resolution,
            "value_preview": raw_log.get("value_preview"),
            "correction_type": raw_log.get("correction_type"),
            "correction_value": raw_log.get("correction_value"),
            "pii_types_involved": [raw_log.get("pii_type")] if raw_log.get("pii_type") else [],
            "rule_type": raw_log.get("rule_type", "N"),
            "relationship_tag": raw_log.get("relationship_tag"),
            "agent_intent": raw_log.get("agent_intent"),
            "processed": False,
            # 可视化摘要
            "visual_summary": {
                "action_description": processed.get("action_metadata", {}).get("description"),
                "l1_detection": processed.get("l1_detection"),
                "l2_reasoning": processed.get("l2_reasoning"),
            },
        }

        # 判断是 correction 还是 behavior
        is_correction = raw_log.get("correction_type") or raw_log.get("action") == "user_correction"

        behavior_file = user_dir / "behavior_log.jsonl"
        with behavior_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        if is_correction:
            correction_file = user_dir / "correction_log.jsonl"
            with correction_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def stop(self) -> None:
        """停止处理线程。"""
        self._running = False
        self._thread.join(timeout=5)


# 全局单例
_log_processor: Optional[LogProcessor] = None
_processor_lock = threading.Lock()


def get_log_processor() -> LogProcessor:
    """获取全局 LogProcessor 实例。"""
    global _log_processor
    if _log_processor is None:
        with _processor_lock:
            if _log_processor is None:
                _log_processor = LogProcessor()
    return _log_processor
