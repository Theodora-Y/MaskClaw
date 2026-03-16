# FastAPI 服务 - 隐私代理 HTTP 接口

from fastapi import FastAPI, UploadFile, File, Form, Body
from fastapi.responses import Response
from typing import Dict, Any, Literal
import json
import base64

app = FastAPI(title="隐私保护代理 API", version="1.0.0")

_agent = None

def get_agent():
    global _agent
    if _agent is None:
        from proxy_agent import PrivacyProxyAgent
        _agent = PrivacyProxyAgent()
    return _agent


def multipart_response(meta: Dict, image_bytes: bytes, mime_type: str) -> Response:
    """构建 multipart/mixed 响应"""
    boundary = "----privacy-agent-boundary"
    body = b"".join([
        b"--" + boundary.encode() + b"\r\n",
        b"Content-Type: application/json; charset=utf-8\r\n\r\n",
        json.dumps(meta, ensure_ascii=False).encode(),
        b"\r\n",
        b"--" + boundary.encode() + b"\r\n",
        f"Content-Type: {mime_type}\r\n".encode(),
        b'Content-Disposition: inline; filename="masked"\r\n\r\n',
        image_bytes,
        b"\r\n",
        b"--" + boundary.encode() + b"--\r\n",
    ])
    return Response(content=body, media_type=f"multipart/mixed; boundary={boundary}")


@app.get("/")
def root():
    return {"status": "ok", "message": "隐私保护代理服务运行中"}


@app.post("/process")
async def process_screenshot(
    image: UploadFile = File(...),
    command: str = Form("分析当前页面隐私"),
    return_base64: bool = Form(False)
):
    agent = get_agent()
    result = agent.process_image_bytes(await image.read(), image.filename or "image.jpg", command)

    meta = {
        "success": True,
        "matched_rules": result.matched_rules,
        "analysis": result.analysis,
        "masked_count": result.masked_count,
        "mime_type": result.masked_mime_type,
    }

    if return_base64:
        meta["image_base64"] = base64.b64encode(result.masked_image_bytes).decode()
        return meta

    return multipart_response(meta, result.masked_image_bytes, result.masked_mime_type)


@app.get("/rules")
def list_rules():
    return {"rules": get_agent().list_rules()}


@app.post("/rules")
def add_rule(rule: Dict[str, Any] = Body(...)):
    return {"status": "ok", "rule": get_agent().upsert_rule(rule)}


@app.post("/hook")
def hook_control(action: Literal["install", "uninstall", "status"] = Form(...)):
    from proxy_agent import ScreenshotHook, install_hook

    if action == "install":
        install_hook()
        return {"installed": True}
    if action == "uninstall":
        ScreenshotHook.uninstall()
        return {"installed": False}
    return {"installed": ScreenshotHook._is_installed}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
