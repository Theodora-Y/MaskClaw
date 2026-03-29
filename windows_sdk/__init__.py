"""
Privacy Guard Telemetry Probe SDK for Windows

轻量级日志采集 SDK，用于 AutoGLM Windows 客户端。
"""

from .telemetry_probe import init, log_action, log_agent_fill, log_share_or_send, log_user_correction, flush, get_queue_size

__all__ = [
    "init",
    "log_action",
    "log_agent_fill",
    "log_share_or_send",
    "log_user_correction",
    "flush",
    "get_queue_size",
]
