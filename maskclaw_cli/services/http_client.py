from __future__ import annotations

import ipaddress
import json
import uuid
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse


class ApiError(RuntimeError):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _should_bypass_proxy(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").strip().lower()
        if not host:
            return False
        if host in {"localhost", "::1"}:
            return True
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        return bool(address.is_loopback or address.is_private or address.is_link_local)
    except Exception:
        return False


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    token: str | None = None,
    timeout: float = 8.0,
) -> Any:
    body = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    opener = (
        urllib.request.build_opener(urllib.request.ProxyHandler({}))
        if _should_bypass_proxy(url)
        else urllib.request.build_opener()
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8-sig")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8-sig", errors="replace")
        message = raw
        try:
            data = json.loads(raw)
            detail = data.get("detail", data)
            if isinstance(detail, dict):
                message = str(detail.get("error") or detail.get("message") or detail)
            else:
                message = str(detail)
        except Exception:
            pass
        raise ApiError(exc.code, message) from exc
    except urllib.error.URLError as exc:
        raise ApiError(0, str(exc.reason)) from exc


def request_multipart_json(
    method: str,
    url: str,
    *,
    fields: dict[str, Any] | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
    token: str | None = None,
    timeout: float = 30.0,
) -> Any:
    boundary = f"maskclaw-{uuid.uuid4().hex}"
    body = _encode_multipart(fields or {}, files or {}, boundary)
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=body, method=method.upper(), headers=headers)
    opener = (
        urllib.request.build_opener(urllib.request.ProxyHandler({}))
        if _should_bypass_proxy(url)
        else urllib.request.build_opener()
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8-sig")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8-sig", errors="replace")
        message = raw
        try:
            data = json.loads(raw)
            detail = data.get("detail", data)
            if isinstance(detail, dict):
                message = str(detail.get("error") or detail.get("message") or detail)
            else:
                message = str(detail)
        except Exception:
            pass
        raise ApiError(exc.code, message) from exc
    except urllib.error.URLError as exc:
        raise ApiError(0, str(exc.reason)) from exc


def _encode_multipart(
    fields: dict[str, Any],
    files: dict[str, tuple[str, bytes, str]],
    boundary: str,
) -> bytes:
    chunks: list[bytes] = []
    for key, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    for key, (filename, content, content_type) in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                (
                    f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8"),
                content,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks)
