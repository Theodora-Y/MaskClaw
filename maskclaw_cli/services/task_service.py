from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any


BASE_URL = "http://127.0.0.1:28080"


class TaskApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 8.0,
) -> Any:
    headers = {"Content-Type": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8-sig")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8-sig", errors="replace")
        message = raw
        try:
            data = json.loads(raw)
            message = str(data.get("detail") or data.get("error") or data.get("message") or data)
        except Exception:
            pass
        raise TaskApiError(exc.code, message) from exc
    except urllib.error.URLError as exc:
        raise TaskApiError(0, str(exc.reason)) from exc


class TaskService:
    def run(
        self,
        task: str,
        max_steps: int = 100,
        lang: str = "cn",
        api_key: str | None = None,
        base_url: str = "https://api-inference.modelscope.cn/v1",
        model: str = "ZhipuAI/AutoGLM-Phone-9B",
        device_id: str = "",
        privacy_debug: bool = True,
        save_privacy_images: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "task": task,
            "max_steps": max_steps,
            "lang": lang,
            "base_url": base_url,
            "model": model,
            "privacy_debug": privacy_debug,
            "save_privacy_images": save_privacy_images,
        }
        if api_key:
            payload["api_key"] = api_key
        if device_id:
            payload["device_id"] = device_id

        return _request_json("POST", f"{BASE_URL}/api/autoglm/execute", payload)

    def list(self) -> dict[str, Any]:
        return _request_json("GET", f"{BASE_URL}/api/autoglm/tasks")

    def status(self, task_id: str) -> dict[str, Any]:
        return _request_json("GET", f"{BASE_URL}/api/autoglm/status/{task_id}")

    def cancel(self, task_id: str) -> dict[str, Any]:
        return _request_json("POST", f"{BASE_URL}/api/autoglm/cancel/{task_id}")

    def logs(self, task_id: str, limit: int = 50) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        url = f"{BASE_URL}/api/autoglm/stream/{task_id}"
        request = urllib.request.Request(url, method="GET", headers={"Accept": "text/event-stream"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        try:
            response = opener.open(request, timeout=30)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8-sig", errors="replace")
            try:
                data = json.loads(raw)
                raise TaskApiError(exc.code, str(data.get("detail") or data.get("error") or data))
            except Exception:
                raise TaskApiError(exc.code, raw or str(exc))
        except urllib.error.URLError as exc:
            raise TaskApiError(0, str(exc.reason))

        import select
        import socket

        sock = response.fp.raw._sock  # type: ignore
        received = b""

        while len(events) < limit:
            ready, _, _ = select.select([sock], [], [], 5)
            if not ready:
                break
            chunk = sock.recv(4096)
            if not chunk:
                break
            received += chunk

            for line in received.split(b"\n"):
                line = line.strip()
                if not line:
                    continue
                decoded = line.decode("utf-8", errors="replace")
                if decoded.startswith("event:"):
                    event_type = decoded[len("event:") :].strip()
                elif decoded.startswith("data:"):
                    data_str = decoded[len("data:") :].strip()
                    try:
                        data = json.loads(data_str)
                        events.append({"event": event_type, "data": data})
                    except Exception:
                        pass

            received = b""

        return events
