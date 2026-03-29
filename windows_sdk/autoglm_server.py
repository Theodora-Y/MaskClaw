"""
AutoGLM API Server - Windows 端任务调度服务

功能：
1. 接收前端任务提交
2. 启动 AutoGLM 子进程执行
3. 通过 SSE 推送执行日志到前端
4. 支持任务取消与状态查询

SSH 远程端口转发：
  ssh -R 8080:localhost:8080 user@your-server -N

前端调用示例：
  curl -X POST http://localhost:8080/run-task \
    -H "Content-Type: application/json" \
    -d '{"task": "打开微信"}'
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

# ============== 配置 ==============

HOST = "0.0.0.0"
PORT = 28080

# 服务器地址（通过 SSH 隧道访问）
SERVER_URL = "http://127.0.0.1:28080"

# ============== 服务器通信 ==============

import requests

# AutoGLM 配置
AUTOGLM_BASE_URL = "https://api-inference.modelscope.cn/v1"
AUTOGLM_MODEL = "ZhipuAI/AutoGLM-Phone-9B"
AUTOGLM_API_KEY = "EMPTY"  # 留空或填入实际 key
DEFAULT_MAX_STEPS = 100
DEFAULT_LANG = "cn"

# ============== 任务管理 ==============

class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Task:
    def __init__(
        self,
        task_id: str,
        task_description: str,
        max_steps: int = DEFAULT_MAX_STEPS,
        lang: str = DEFAULT_LANG,
        privacy_debug: bool = True,
        save_privacy_images: bool = True,
    ):
        self.task_id = task_id
        self.task_description = task_description
        self.max_steps = max_steps
        self.lang = lang
        self.privacy_debug = privacy_debug
        self.save_privacy_images = save_privacy_images
        
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.pid: Optional[int] = None
        self.process: Optional[subprocess.Popen] = None
        self.return_code: Optional[int] = None
        self.error: Optional[str] = None
        self.logs: List[Dict[str, Any]] = []
        
        # SSE 客户端
        self.sse_callbacks: List[Callable] = []
        
    def add_sse_callback(self, callback: Callable):
        self.sse_callbacks.append(callback)
        
    def remove_sse_callback(self, callback: Callable):
        if callback in self.sse_callbacks:
            self.sse_callbacks.remove(callback)
    
    def emit(self, event_type: str, data: Any):
        """向所有 SSE 客户端发送事件"""
        payload = {"event_type": event_type, "data": data, "timestamp": time.time()}
        for callback in self.sse_callbacks:
            try:
                callback(payload)
            except Exception:
                pass
    
    def emit_log(self, message: str, log_type: str = "log", extra: Dict = None):
        """发送日志事件"""
        self.logs.append({
            "type": log_type,
            "content": message,
            "timestamp": time.time(),
            **(extra or {})
        })
        self.emit(log_type, message)
    
    def emit_finished(self, return_code: int = 0):
        """发送完成事件"""
        self.emit("finished", {
            "task_id": self.task_id,
            "return_code": return_code,
            "status": "completed" if return_code == 0 else "failed",
            "error": self.error,
            "logs_count": len(self.logs),
        })

# 全局任务存储
_tasks: Dict[str, Task] = {}
_tasks_lock = threading.Lock()

# SSE 管理
_sse_lock = threading.Lock()

def get_task(task_id: str) -> Optional[Task]:
    with _tasks_lock:
        return _tasks.get(task_id)

def create_task(task_description: str, **kwargs) -> Task:
    task_id = uuid.uuid4().hex[:8]
    task = Task(task_id=task_id, task_description=task_description, **kwargs)
    with _tasks_lock:
        _tasks[task_id] = task
    return task

def cancel_task(task_id: str) -> bool:
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            return False
        if task.status == TaskStatus.COMPLETED:
            return False
        if task.status == TaskStatus.CANCELLED:
            return False
            
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now().isoformat()
        
        # 终止子进程
        if task.process:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(task.pid), "/F"], 
                                 capture_output=True)
                else:
                    os.kill(task.pid, signal.SIGTERM)
            except Exception:
                pass
    
    task.emit_finished(-1)
    return True

# ============== 服务器通信 ==============

def _send_to_server(endpoint: str, data: Dict, timeout: int = 3) -> bool:
    """发送数据到服务器端"""
    try:
        resp = requests.post(
            f"{SERVER_URL}{endpoint}",
            json=data,
            timeout=timeout,
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[WARN] 发送到服务器失败: {e}")
        return False

def _send_log_to_server(task_id: str, log_type: str, message: str, extra: Dict = None):
    """发送日志到服务器端"""
    _send_to_server("/autoglm/log", {
        "task_id": task_id,
        "log_type": log_type,
        "message": message,
        "extra": extra or {},
    })

def _notify_task_start_to_server(task_id: str, task_description: str, user_id: str):
    """通知服务器任务已开始"""
    _send_to_server("/autoglm/task/start", {
        "task_id": task_id,
        "task_description": task_description,
        "user_id": user_id,
    })

def _notify_task_finish_to_server(task_id: str, status: str, error: str = None):
    """通知服务器任务已结束"""
    _send_to_server("/autoglm/task/finish", {
        "task_id": task_id,
        "status": status,
        "error": error,
    }, timeout=10)

# ============== AutoGLM 执行 ==============

def build_autoglm_command(task: Task) -> List[str]:
    """构建 AutoGLM 命令"""
    cmd = [
        sys.executable,  # 当前 Python 解释器
        "main.py",
        "--device-type", "adb",
        "--base-url", AUTOGLM_BASE_URL,
        "--model", AUTOGLM_MODEL,
        "--apikey", AUTOGLM_API_KEY,
        "--max-steps", str(task.max_steps),
        "--lang", task.lang,
        "--quiet",
        task.task_description,
    ]
    return cmd

def run_autoglm(task: Task):
    """在工作线程中运行 AutoGLM"""
    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now().isoformat()
    
    # 发送启动事件
    task.emit("action", f"开始执行任务: {task.task_description}")
    
    # 通知服务器任务已开始
    _notify_task_start_to_server(task.task_id, task.task_description, "win_user")
    
    try:
        cmd = build_autoglm_command(task)
        
        # 启动进程
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
        )
        
        task.process = process
        task.pid = process.pid
        
        # 发送进程信息
        task.emit("action", {
            "message": f"AutoGLM 进程已启动 (PID: {task.pid})",
            "pid": task.pid,
        })
        
        # 读取输出并发送 SSE
        step = 0
        for line in iter(process.stdout.readline, ""):
            if not line:
                break
                
            # 检查是否取消
            with _tasks_lock:
                if task.status == TaskStatus.CANCELLED:
                    process.terminate()
                    break
            
            line = line.strip()
            if not line:
                continue
            
            # 打印到终端（调试用）
            print(f"[AUTOGLM] {line}")
            
            # 发送到服务器端
            _send_log_to_server(task.task_id, "log", line)
            
            # 分类日志
            line_lower = line.lower()
            if "error" in line_lower or "exception" in line_lower:
                task.emit_log(line, "error")
            elif "thinking" in line_lower or "思考" in line:
                task.emit_log(line, "thinking")
            elif "action" in line_lower or "执行" in line or "点击" in line or "输入" in line:
                task.emit_log(line, "action")
            elif "privacy" in line_lower or "脱敏" in line or "mask" in line_lower:
                task.emit_log(line, "privacy")
            elif "完成" in line or "done" in line_lower or "finish" in line_lower:
                step += 1
                task.emit_log(line, "action")
            else:
                step += 1
                task.emit_log(line, "log")
        
        # 等待进程结束
        process.wait()
        task.return_code = process.returncode
        
        if task.status != TaskStatus.CANCELLED:
            if task.return_code == 0:
                task.status = TaskStatus.COMPLETED
                task.emit("action", "任务执行完成")
            else:
                task.status = TaskStatus.FAILED
                task.error = f"进程返回码: {task.return_code}"
                task.emit("error", task.error)
        
    except FileNotFoundError:
        task.status = TaskStatus.FAILED
        task.error = "main.py 未找到，请确保在 AutoGLM 目录下运行"
        task.emit("error", task.error)
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error = str(e)
        task.emit("error", task.error)
    finally:
        task.completed_at = datetime.now().isoformat()
        
        # 通知服务器任务已完成
        finish_status = "completed" if task.return_code == 0 else "failed"
        _notify_task_finish_to_server(task.task_id, finish_status, task.error)
        
        task.emit_finished(task.return_code or -1)

def submit_task(task_description: str, **kwargs) -> Task:
    """提交任务并启动执行"""
    task = create_task(task_description, **kwargs)
    
    # 在后台线程执行
    thread = threading.Thread(target=run_autoglm, args=(task,), daemon=True)
    thread.start()
    
    return task

# ============== SSE 生成器 ==============

class SSEClient:
    """SSE 客户端封装"""
    def __init__(self, send_fn: Callable):
        self.send = send_fn
        self.queue: asyncio.Queue = asyncio.Queue()
        self.closed = False
        
    async def put(self, data: Dict):
        if not self.closed:
            await self.queue.put(data)
    
    async def event_generator(self, task_id: str):
        """生成 SSE 事件"""
        yield self._sse_event("connected", {"status": "connected", "task_id": task_id})
        
        while not self.closed:
            try:
                # 等待数据，超时发送心跳
                data = await asyncio.wait_for(self.queue.get(), timeout=30)
                yield self._sse_event(data.get("event_type", "message"), data.get("data"))
            except asyncio.TimeoutError:
                # 发送心跳
                yield self._sse_event("heartbeat", {"timestamp": int(time.time())})
            
            # 检查任务是否完成
            task = get_task(task_id)
            if task and task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                break
        
        self.closed = True
    
    def _sse_event(self, event_type: str, data: Any) -> Dict:
        """生成 SSE 格式数据"""
        if isinstance(data, str):
            data_str = data
        else:
            data_str = json.dumps(data, ensure_ascii=False)
        
        return {
            "event": event_type,
            "data": data_str,
        }

# ============== HTTP 服务器 (使用内置 http.server) ==============

try:
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs
except ImportError:
    print("Python 3 required")
    sys.exit(1)

class AutoGLMHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[{self.log_date_time_string()}] {args[0]}")
    
    def send_cors_headers(self):
        """发送 CORS 头"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # SSE 流 (支持多种路径格式)
        if path.startswith("/api/autoglm/stream/") or path.startswith("/stream/"):
            task_id = path.split("/").pop()
            self._handle_stream(task_id)
            return
        
        # 任务状态 (支持多种路径格式)
        if path.startswith("/api/autoglm/status/") or path.startswith("/task/"):
            task_id = path.split("/").pop()
            self._handle_task_status(task_id)
            return
        
        # 所有任务
        if path == "/tasks" or path == "/api/autoglm/tasks":
            self._handle_list_tasks()
            return
        
        # 健康检查
        if path == "/health" or path == "/api/autoglm/health":
            self._send_json({"status": "ok", "timestamp": time.time()})
            return
        
        # 未知路由
        self._send_error(404, "Not Found")
    
    def do_POST(self):
        """处理 POST 请求"""
        parsed = urlparse(self.path)
        path = parsed.path
        
        # 读取请求体
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON")
            return
        
        # 提交任务 (支持多种路径格式)
        if path == "/api/autoglm/execute" or path == "/run-task" or path == "/api/task/run":
            self._handle_run_task(data)
            return
        
        # 取消任务
        if path.startswith("/api/autoglm/cancel/") or path.startswith("/cancel/"):
            # 提取 task_id
            task_id = path.split("/").pop()
            self._handle_cancel(task_id)
            return
        
        # 未知路由
        self._send_error(404, "Not Found")
    
    def _handle_run_task(self, data: Dict):
        """处理任务提交"""
        task_description = data.get("task", "")
        if not task_description:
            self._send_error(400, "task is required")
            return
        
        task = submit_task(
            task_description=task_description,
            max_steps=data.get("maxSteps", DEFAULT_MAX_STEPS),
            lang=data.get("lang", DEFAULT_LANG),
            privacy_debug=data.get("privacyDebug", True),
            save_privacy_images=data.get("savePrivacyImages", True),
        )
        
        # 获取 base_url
        base_url = self.headers.get('Host', f'localhost:{PORT}')
        # SSE 流地址（前端通过 Vite 代理访问）
        stream_url = f"/api/autoglm/stream/{task.task_id}"
        
        self._send_json({
            "task_id": task.task_id,
            "stream_url": stream_url,
            "status": task.status,
            "task": task.task_description,
            "started_at": task.started_at,
            "pid": task.pid,
        }, status=200)
    
    def _handle_stream(self, task_id: str):
        """处理 SSE 流"""
        task = get_task(task_id)
        if not task:
            self._send_error(404, "Task not found")
            return
        
        # 发送 SSE 头
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_cors_headers()
        self.end_headers()
        
        # 创建 SSE 客户端
        client = SSEClient(self.wfile.write)
        task.add_sse_callback(lambda data: asyncio.run(client.put(data)))
        
        # 运行事件循环
        try:
            for event in client.event_generator(task_id):
                if client.closed:
                    break
                # 写入 SSE 格式
                event_line = f"event: {event['event']}\ndata: {event['data']}\n\n"
                self.wfile.write(event_line.encode("utf-8"))
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            task.remove_sse_callback(lambda data: asyncio.run(client.put(data)))
    
    def _handle_task_status(self, task_id: str):
        """处理任务状态查询"""
        task = get_task(task_id)
        if not task:
            self._send_error(404, "Task not found")
            return
        
        self._send_json({
            "task_id": task.task_id,
            "status": task.status,
            "task": task.task_description,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "return_code": task.return_code,
            "pid": task.pid,
            "error": task.error,
            "logs_count": len(task.logs),
        })
    
    def _handle_list_tasks(self):
        """处理列出所有任务"""
        with _tasks_lock:
            tasks = [{
                "task_id": t.task_id,
                "status": t.status,
                "task": t.task_description,
                "created_at": t.created_at,
                "started_at": t.started_at,
            } for t in _tasks.values()]
        
        self._send_json({"tasks": tasks, "count": len(tasks)})
    
    def _handle_cancel(self, task_id: str):
        """处理任务取消"""
        success = cancel_task(task_id)
        if success:
            self._send_json({"task_id": task_id, "status": "cancelled"})
        else:
            self._send_error(400, "Cannot cancel task")
    
    def _send_json(self, data: Dict, status: int = 200):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    
    def _send_error(self, status: int, message: str):
        """发送错误响应"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode("utf-8"))

# ============== 启动服务器 ==============

def main():
    print("=" * 60)
    print("AutoGLM API Server")
    print("=" * 60)
    print(f"本地地址: http://localhost:{PORT}")
    print()
    print("SSH 远程端口转发（在一台能访问本机的 Linux 服务器上执行）：")
    print(f"  ssh -R 28080:localhost:{PORT} user@服务器IP")
    print()
    print("前端调用示例：")
    print(f'  curl -X POST http://localhost:{PORT}/run-task \\')
    print(f'    -H "Content-Type: application/json" \\')
    print('    -d \'{"task": "打开微信"}\'')
    print("=" * 60)
    
    server = HTTPServer((HOST, PORT), AutoGLMHandler)
    print(f"\nINFO:     Started server process [{os.getpid()}]")
    print(f"INFO:     Uvicorn running on http://{HOST}:{PORT} (Press CTRL+C to quit)")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nINFO:     Shutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()
