#!/usr/bin/env python3
"""
AutoGLM API Server - 异步 + SSE 实现

提供 HTTP API 接口供前端调用 AutoGLM 任务执行。

接口说明:
- POST /api/autoglm/execute  - 提交任务，返回 task_id + stream_url
- GET  /api/autoglm/stream/{task_id} - SSE 流端点
- POST /api/autoglm/cancel/{task_id} - 取消任务
- GET  /api/autoglm/health  - 健康检查

SSE 事件:
- connected     - 连接建立
- log_summary   - 日志/状态更新
- task_completed - 任务完成
- task_error    - 任务错误
- task_cancelled - 任务取消
"""

import asyncio
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# ============== FastAPI App ==============

app = FastAPI(
    title="AutoGLM API",
    description="异步 + SSE 实现的 AutoGLM 任务执行接口",
    version="1.0.0",
)

# CORS 配置，允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== 默认配置 ==============

# 默认 API Key（ModelScope）
DEFAULT_API_KEY = "ms-f31f6d28-c208-4ddf-b5f0-9da3b59e4b94"

# 默认模型配置
DEFAULT_BASE_URL = "https://api-inference.modelscope.cn/v1"
DEFAULT_MODEL = "ZhipuAI/AutoGLM-Phone-9B"
DEFAULT_MAX_STEPS = 100
DEFAULT_PRIVACY_DEBUG = True
DEFAULT_SAVE_PRIVACY_IMAGES = True
DEFAULT_LANG = "cn"
OPEN_AUTOGLM_DIR = os.environ.get(
    "MASKCLAW_OPEN_AUTOGLM_DIR",
    r"D:\学习笔记\工4\实验设计\Open-AutoGLM-main\Open-AutoGLM-main"
)


# ============== 数据模型 ==============

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskRequest(BaseModel):
    """任务请求模型（简化版，前端只需传 task）"""
    task: str  # 任务描述（必填）
    base_url: str = DEFAULT_BASE_URL  # 模型 API 地址
    model: str = DEFAULT_MODEL  # 模型名称
    api_key: str = DEFAULT_API_KEY  # API Key（默认）
    device_id: str = ""  # 设备 ID（可选，自动选择第一个设备）
    max_steps: int = DEFAULT_MAX_STEPS  # 最大步数
    privacy_debug: bool = DEFAULT_PRIVACY_DEBUG  # 隐私调试模式
    save_privacy_images: bool = DEFAULT_SAVE_PRIVACY_IMAGES  # 保存隐私图片
    lang: str = DEFAULT_LANG  # 语言


class TaskResponse(BaseModel):
    """任务提交响应"""
    task_id: str
    status: str
    stream_url: str
    message: str = ""


class TaskInfo(BaseModel):
    """任务信息"""
    task_id: str
    status: str
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    request: Optional[dict] = None
    result: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    service: str = "autoglm"
    timestamp: float


# ============== 任务存储 ==============

# 全局任务字典
tasks: dict[str, dict] = {}
tasks_lock = threading.Lock()


def create_task(task_id: str, request: TaskRequest) -> None:
    """创建任务记录"""
    with tasks_lock:
        tasks[task_id] = {
            "status": TaskStatus.PENDING.value,
            "created_at": time.time(),
            "started_at": None,
            "completed_at": None,
            "request": request.model_dump(),
            "result": None,
            "error": None,
            "queue": queue.Queue(),
            "process": None,
            "thread": None,
        }


def get_task(task_id: str) -> Optional[dict]:
    """获取任务记录"""
    with tasks_lock:
        return tasks.get(task_id)


def update_task_status(task_id: str, status: TaskStatus) -> None:
    """更新任务状态"""
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id]["status"] = status.value
            if status == TaskStatus.RUNNING:
                tasks[task_id]["started_at"] = time.time()
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                tasks[task_id]["completed_at"] = time.time()


def set_task_result(task_id: str, result: str, error: Optional[str] = None) -> None:
    """设置任务结果"""
    with tasks_lock:
        if task_id in tasks:
            tasks[task_id]["result"] = result
            tasks[task_id]["error"] = error


def cleanup_task(task_id: str) -> None:
    """清理任务记录"""
    with tasks_lock:
        if task_id in tasks:
            # 终止进程
            proc = tasks[task_id].get("process")
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            # 从字典中移除
            del tasks[task_id]


# ============== 日志转换 ==============

def convert_to_log_summary(line: str) -> Optional[dict]:
    """
    将 AutoGLM 输出行转换为 LogSummary 格式

    前端期望的格式:
    {
        "action_metadata": {
            "action": str,       # 操作类型
            "app_context": str,  # 当前应用
            "description": str, # 描述
            "timestamp": str     # 时间戳
        },
        "l1_detection": {
            "detected_fields": [],  # 检测到的字段
            "pii_type": str,        # PII 类型
            "masked_preview": str,  # 打码预览
            "masked_regions": []    # 打码区域
        },
        "l2_reasoning": {
            "reasoning": str,      # 推理过程
            "rule_match": str,     # 匹配的规则
            "decision": str,       # 决策
            "confidence": float   # 置信度
        },
        "outcome": {
            "final_action": str,  # 最终动作
            "safe_image": str,    # 安全图片
            "field": str,         # 字段
            "message": str        # 消息
        }
    }
    """
    line = line.strip()
    if not line or line.startswith("="):
        return None

    timestamp = datetime.now().isoformat()
    result: dict[str, Any] = {
        "action_metadata": {
            "action": "unknown",
            "app_context": "unknown",
            "description": line,
            "timestamp": timestamp,
        }
    }

    # 隐私代理相关
    if "[privacy-proxy]" in line or "privacy" in line.lower():
        if "process #" in line:
            # 隐私处理信息
            matched = re.search(r"matched_rules?=(.+?)(?:,|\s*$)", line)
            masked = re.search(r"masked_count=(\d+)", line)
            result["l1_detection"] = {
                "detected_fields": [],
                "pii_type": "privacy_sensitive",
                "masked_preview": "***",
                "masked_regions": [],
            }
            result["outcome"] = {
                "final_action": "privacy_mask",
                "message": line,
            }
            if matched:
                result["l1_detection"]["detected_fields"] = [matched.group(1).strip()]
            if masked:
                result["outcome"]["field"] = f"{masked.group(1)} fields masked"
        return result

    # 思考过程
    if "thinking" in line.lower() or "💭" in line or "🤔" in line:
        result["action_metadata"]["action"] = "thinking"
        result["action_metadata"]["description"] = re.sub(r"[💭🤔🔍🎯✅❌⚠️🔧]+", "", line).strip()
        result["l2_reasoning"] = {
            "reasoning": line,
            "rule_match": "",
            "decision": "analyzing",
            "confidence": 0.8,
        }
        return result

    # 系统检查
    if any(x in line for x in ["Checking", "check", "🔍"]):
        result["action_metadata"]["action"] = "system_check"
        result["outcome"] = {"final_action": "check", "message": line}
        if "✅" in line or "OK" in line:
            result["outcome"]["message"] = "检查通过: " + line
        elif "❌" in line or "FAILED" in line:
            result["outcome"]["message"] = "检查失败: " + line
        return result

    # 任务信息
    if "Task:" in line or "task" in line.lower():
        result["action_metadata"]["action"] = "task_start"
        result["outcome"] = {"final_action": "start", "message": line}
        return result

    # 步骤信息
    if "Step" in line or any(x in line for x in ["→", "->", "click", "swipe", "input", "press"]):
        result["action_metadata"]["action"] = "execute"
        result["outcome"] = {"final_action": "execute", "message": line}

        # 识别具体动作
        if "click" in line.lower():
            result["action_metadata"]["action"] = "click"
            result["outcome"]["final_action"] = "click"
        elif "swipe" in line.lower():
            result["action_metadata"]["action"] = "swipe"
            result["outcome"]["final_action"] = "swipe"
        elif "input" in line.lower() or "type" in line.lower():
            result["action_metadata"]["action"] = "input"
            result["outcome"]["final_action"] = "input_text"
        elif "press" in line.lower() or "key" in line.lower():
            result["action_metadata"]["action"] = "press_key"
            result["outcome"]["final_action"] = "press_key"
        return result

    # 完成信息
    if any(x in line for x in ["completed", "done", "finished", "success", "🎉", "✅"]):
        result["action_metadata"]["action"] = "completed"
        result["outcome"] = {"final_action": "success", "message": line}
        return result

    # 错误信息
    if any(x in line for x in ["error", "failed", "exception", "❌", "failed"]):
        result["action_metadata"]["action"] = "error"
        result["outcome"] = {"final_action": "error", "message": line}
        return result

    # 设备/应用信息
    if any(x in line for x in ["Device:", "device", "App:", "app", "screen"]):
        result["action_metadata"]["action"] = "device_status"
        result["outcome"] = {"final_action": "status", "message": line}
        return result

    # 默认：作为一般日志返回
    result["action_metadata"]["description"] = line
    return result


def send_sse_event(q: queue.Queue, event: str, data: dict) -> None:
    """发送 SSE 事件到队列，同时打印到终端"""
    q.put({"event": event, "data": data})

    # 打印到终端
    task_id = data.get("task_id", "")
    if event == "task_received":
        print(f"[{task_id}] 任务已接收: {data.get('message', '')}")
    elif event == "log_summary":
        desc = data.get("action_metadata", {}).get("description", "")
        if desc:
            print(f"[{task_id}] {desc}")
    elif event == "task_completed":
        print(f"[{task_id}] 任务完成")
    elif event == "task_error":
        print(f"[{task_id}] 任务失败: {data.get('error', '')}")
    elif event == "task_cancelled":
        print(f"[{task_id}] 任务已取消")


# ============== 任务执行 ==============

def execute_task(task_id: str) -> None:
    """
    在后台线程中执行 AutoGLM 任务

    流程:
    1. 发送 connected 事件
    2. 启动 main.py 进程
    3. 实时捕获输出并发送 log_summary 事件
    4. 发送 task_completed/task_error 事件
    """
    task = get_task(task_id)
    if not task:
        return

    req = TaskRequest(**task["request"])
    q = task["queue"]

    # 发送 connected 事件
    send_sse_event(q, "connected", {
        "task_id": task_id,
        "status": "connected",
        "message": "已连接到 AutoGLM 任务执行器",
    })

    update_task_status(task_id, TaskStatus.RUNNING)

    # 构建环境变量
    env = os.environ.copy()
    env["PHONE_AGENT_PRIVACY_PROXY"] = "true"
    env["PHONE_AGENT_PRIVACY_SERVER_URL"] = "http://127.0.0.1:9001"
    env["PHONE_AGENT_PRIVACY_COMMAND"] = "analyze privacy and mask sensitive data"
    env["PHONE_AGENT_PRIVACY_CONNECT_TIMEOUT"] = "5"
    env["PHONE_AGENT_PRIVACY_TIMEOUT"] = "60"
    env["PHONE_AGENT_PRIVACY_RETRY_COUNT"] = "2"
    env["PHONE_AGENT_PRIVACY_RETRY_INTERVAL_MS"] = "500"
    env["PHONE_AGENT_PRIVACY_INSTALL_HOOK"] = "true"
    env["PHONE_AGENT_MAX_IMAGE_SIDE"] = "2048"
    env["PHONE_AGENT_PRIVACY_DEBUG"] = "true" if req.privacy_debug else "false"
    env["PHONE_AGENT_PRIVACY_SAVE_IMAGES"] = "true" if req.save_privacy_images else "false"
    env["PHONE_AGENT_PRIVACY_SAVE_DIR"] = "logs/privacy_proxy"

    # 构建命令
    cmd = [
        sys.executable,
        str(Path(OPEN_AUTOGLM_DIR) / "main.py"),
        "--device-type", "adb",
        "--base-url", req.base_url,
        "--model", req.model,
        "--apikey", req.api_key,
        "--max-steps", str(req.max_steps),
        "--lang", req.lang,
    ]

    if req.device_id:
        cmd.extend(["--device-id", req.device_id])

    cmd.append(req.task)

    # 发送启动信息
    send_sse_event(q, "log_summary", {
        "action_metadata": {
            "action": "start",
            "app_context": "autoglm",
            "description": f"正在启动任务: {req.task}",
            "timestamp": datetime.now().isoformat(),
        },
        "outcome": {
            "final_action": "start",
            "message": f"命令: {' '.join(cmd[:6])}...",
        },
    })

    # 启动进程
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            env=env,
        )
        task["process"] = process

        # 实时读取输出
        output_lines = []
        for line in process.stdout:
            output_lines.append(line)

            # 转换并发送日志
            log_entry = convert_to_log_summary(line)
            if log_entry:
                send_sse_event(q, "log_summary", log_entry)

            # 检查是否被取消
            current_task = get_task(task_id)
            if current_task and current_task["status"] == TaskStatus.CANCELLED.value:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                send_sse_event(q, "task_cancelled", {
                    "task_id": task_id,
                    "message": "任务已被用户取消",
                })
                update_task_status(task_id, TaskStatus.CANCELLED)
                return

        # 等待进程结束
        process.wait()
        return_code = process.returncode

        # 发送完成事件
        full_output = "".join(output_lines)

        if return_code == 0:
            update_task_status(task_id, TaskStatus.COMPLETED)
            set_task_result(task_id, full_output)
            send_sse_event(q, "task_completed", {
                "task_id": task_id,
                "status": "completed",
                "message": "任务执行完成",
                "output": full_output[-1000:] if len(full_output) > 1000 else full_output,
            })
        else:
            update_task_status(task_id, TaskStatus.FAILED)
            set_task_result(task_id, full_output, f"Exit code: {return_code}")
            send_sse_event(q, "task_error", {
                "task_id": task_id,
                "status": "failed",
                "error": f"任务执行失败，退出码: {return_code}",
                "output": full_output[-1000:] if len(full_output) > 1000 else full_output,
            })

    except FileNotFoundError as e:
        error_msg = f"找不到 Python 或 main.py: {e}"
        update_task_status(task_id, TaskStatus.FAILED)
        set_task_result(task_id, "", error_msg)
        send_sse_event(q, "task_error", {
            "task_id": task_id,
            "status": "failed",
            "error": error_msg,
        })
    except Exception as e:
        error_msg = f"任务执行异常: {str(e)}"
        update_task_status(task_id, TaskStatus.FAILED)
        set_task_result(task_id, "", error_msg)
        send_sse_event(q, "task_error", {
            "task_id": task_id,
            "status": "failed",
            "error": error_msg,
        })
    finally:
        # 发送结束信号
        q.put(None)


# ============== SSE 流生成器 ==============

def sse_generator(task_id: str):
    """SSE 流生成器"""
    task = get_task(task_id)
    if not task:
        yield f"event: error\ndata: {json.dumps({'error': 'Task not found'})}\n\n"
        return

    q = task["queue"]
    while True:
        try:
            event = q.get(timeout=60)  # 60秒超时
            if event is None:  # 结束信号
                break
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        except queue.Empty:
            # 发送心跳
            yield f"event: ping\ndata: {json.dumps({'task_id': task_id, 'timestamp': time.time()})}\n\n"

            # 检查任务是否已结束
            current_task = get_task(task_id)
            if not current_task:
                break
            if current_task["status"] in (
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            ):
                break


# ============== API 路由 ==============

@app.post("/api/autoglm/execute", response_model=TaskResponse)
async def execute_autoglm_task(request: TaskRequest):
    """
    提交 AutoGLM 任务

    请求:
    {
        "task": "打开微信，给Theodora第一条朋友圈点赞",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "model": "ZhipuAI/AutoGLM-Phone-9B",
        "api_key": "your-api-key",
        "device_id": "",
        "max_steps": 100,
        "privacy_debug": true,
        "save_privacy_images": true
    }

    响应:
    {
        "task_id": "uuid",
        "status": "pending",
        "stream_url": "/api/autoglm/stream/{task_id}"
    }
    """
    # 生成任务 ID
    task_id = str(uuid.uuid4())

    # 创建任务记录
    create_task(task_id, request)

    # 启动后台线程执行任务
    thread = threading.Thread(target=execute_task, args=(task_id,), daemon=True)
    with tasks_lock:
        tasks[task_id]["thread"] = thread
    thread.start()

    return TaskResponse(
        task_id=task_id,
        status="pending",
        stream_url=f"/api/autoglm/stream/{task_id}",
        message="任务已提交，正在启动执行",
    )


# ============== 兼容前端原有路径 ==============

@app.post("/autoglm/api/task/run", response_model=TaskResponse)
async def execute_autoglm_task_compat(request: TaskRequest):
    """
    兼容前端原有路径的接口

    前端调用: POST /autoglm/api/task/run
    后端实际: POST /api/autoglm/execute

    功能完全相同，仅路径兼容。
    """
    return await execute_autoglm_task(request)


@app.get("/autoglm/api/task/stream")
async def stream_autoglm_task_compat(task_id: str):
    """
    兼容前端原有 SSE 路径 (query 参数方式)

    前端调用: GET /autoglm/api/task/stream?task_id=xxx
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return StreamingResponse(
        sse_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/autoglm/api/autoglm/stream/{task_id}")
async def stream_autoglm_task_v2(task_id: str, auth: str = None):
    """
    兼容前端 SSE 路径 (RESTful 方式)

    前端调用: GET /autoglm/api/autoglm/stream/{task_id}?auth=xxx
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return StreamingResponse(
        sse_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/autoglm/api/task/cancel/{task_id}")
async def cancel_autoglm_task_compat(task_id: str):
    """
    兼容前端原有取消任务路径

    前端调用: POST /autoglm/api/task/cancel/{task_id}
    后端实际: POST /api/autoglm/cancel/{task_id}
    """
    return await cancel_autoglm_task(task_id)


@app.get("/api/autoglm/stream/{task_id}")
async def stream_autoglm_task(task_id: str):
    """
    SSE 流端点

    前端通过 EventSource 连接此端点接收实时日志和状态更新。

    事件类型:
    - connected: 连接建立
    - log_summary: 日志/状态更新
    - task_completed: 任务完成
    - task_error: 任务错误
    - task_cancelled: 任务取消
    - ping: 心跳（每60秒）
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        sse_generator(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )


@app.post("/api/autoglm/cancel/{task_id}")
async def cancel_autoglm_task(task_id: str):
    """
    取消 AutoGLM 任务

    请求:
    POST /api/autoglm/cancel/{task_id}

    响应:
    {
        "task_id": "uuid",
        "status": "cancelled",
        "message": "任务已取消"
    }
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    current_status = task["status"]

    if current_status in (TaskStatus.COMPLETED.value, TaskStatus.FAILED.value, TaskStatus.CANCELLED.value):
        return JSONResponse({
            "task_id": task_id,
            "status": current_status,
            "message": f"任务已经是 {current_status} 状态，无法取消",
        })

    update_task_status(task_id, TaskStatus.CANCELLED)

    # 终止进程
    proc = task.get("process")
    if proc and proc.poll() is None:
        proc.terminate()

    return {
        "task_id": task_id,
        "status": "cancelled",
        "message": "任务取消请求已发送",
    }


@app.get("/api/autoglm/status/{task_id}")
async def get_task_status(task_id: str):
    """
    获取任务状态

    请求:
    GET /api/autoglm/status/{task_id}

    响应:
    {
        "task_id": "uuid",
        "status": "running",
        "created_at": 1234567890.123,
        "started_at": 1234567890.456,
        "completed_at": null,
        "result": null,
        "error": null
    }
    """
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks[task_id]
    return TaskInfo(
        task_id=task_id,
        status=task["status"],
        created_at=task["created_at"],
        started_at=task.get("started_at"),
        completed_at=task.get("completed_at"),
        request=task.get("request"),
        result=task.get("result"),
        error=task.get("error"),
    )


@app.get("/api/autoglm/tasks")
async def list_tasks():
    """
    列出所有任务

    响应:
    {
        "tasks": [
            {"task_id": "uuid", "status": "running", "created_at": 1234567890.123},
            ...
        ],
        "total": 5
    }
    """
    with tasks_lock:
        task_list = [
            {
                "task_id": tid,
                "status": t["status"],
                "created_at": t["created_at"],
                "started_at": t.get("started_at"),
                "completed_at": t.get("completed_at"),
            }
            for tid, t in tasks.items()
        ]

    return {
        "tasks": task_list,
        "total": len(task_list),
    }


@app.get("/api/autoglm/health", response_model=HealthResponse)
async def health_check():
    """
    健康检查

    响应:
    {
        "status": "ok",
        "service": "autoglm",
        "timestamp": 1234567890.123
    }
    """
    return HealthResponse(
        status="ok",
        service="autoglm",
        timestamp=time.time(),
    )


@app.delete("/api/autoglm/cleanup")
async def cleanup_completed_tasks():
    """
    清理已结束的任务记录

    响应:
    {
        "cleaned": 3,
        "remaining": 2
    }
    """
    global tasks

    with tasks_lock:
        to_remove = [
            tid for tid, t in tasks.items()
            if t["status"] in (
                TaskStatus.COMPLETED.value,
                TaskStatus.FAILED.value,
                TaskStatus.CANCELLED.value,
            )
        ]

        for tid in to_remove:
            # 终止进程
            proc = tasks[tid].get("process")
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            del tasks[tid]

        remaining = len(tasks)

    return {
        "cleaned": len(to_remove),
        "remaining": remaining,
    }


# ============== 主入口 ==============

def main():
    """启动服务器"""
    import uvicorn

    print("=" * 60)
    print("AutoGLM API Server - 异步 + SSE 实现")
    print("=" * 60)
    print()
    print("接口列表:")
    print("  POST /api/autoglm/execute    - 提交任务")
    print("  GET  /api/autoglm/stream/{id} - SSE 流")
    print("  POST /api/autoglm/cancel/{id} - 取消任务")
    print("  GET  /api/autoglm/status/{id} - 任务状态")
    print("  GET  /api/autoglm/tasks      - 任务列表")
    print("  GET  /api/autoglm/health    - 健康检查")
    print("  DELETE /api/autoglm/cleanup  - 清理已完成任务")
    print()
    print("端口: 28080")
    print()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=28080,
        log_level="info",
    )


if __name__ == "__main__":
    main()
