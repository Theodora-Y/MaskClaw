# model_server/ollama_api.py
"""
Ollama 本地大模型 API 服务

提供与 MiniCPM/Gemma API 兼容的接口，支持本地部署的 gemma:2b 等模型
启动端口: 8005

使用方式：
1. 安装 Ollama: https://ollama.com
2. 下载模型: ollama pull gemma:2b
3. 启动此服务: python model_server/ollama_api.py
4. 在代码中调用 http://localhost:8005/chat
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Ollama Local LLM API")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== 配置 ==============

# Ollama 服务地址（默认本地）
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# 默认模型（可以通过 API 参数覆盖）
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma:2b")

# 生成的默认参数
DEFAULT_PARAMS = {
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 40,
    "num_predict": 512,
    "stop": [],
}


class ChatMessage(BaseModel):
    """聊天消息格式"""
    role: str
    content: str


class ChatRequest(BaseModel):
    """聊天请求格式"""
    model: str = DEFAULT_MODEL
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 40
    max_tokens: Optional[int] = 512
    stream: bool = False


class CompletionRequest(BaseModel):
    """补全请求格式（兼容非对话场景）"""
    model: str = DEFAULT_MODEL
    prompt: str
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 40
    max_tokens: Optional[int] = 512
    stream: bool = False


# ============== Ollama 客户端 ==============

class OllamaClient:
    """Ollama API 客户端（兼容 OpenAI SDK 格式）"""

    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.chat_endpoint = f"{self.base_url}/api/chat"
        self.generate_endpoint = f"{self.base_url}/api/generate"
        self.tags_endpoint = f"{self.base_url}/api/tags"

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """发送聊天请求到 Ollama"""
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        # 添加可选参数
        for key in ["temperature", "top_p", "top_k", "num_predict"]:
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(self.chat_endpoint, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"无法连接到 Ollama 服务，请确保 Ollama 已在运行 (地址: {self.base_url})"
            )
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail=str(e))

    def generate(
        self,
        model: str,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """发送生成请求到 Ollama"""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }
        for key in ["temperature", "top_p", "top_k", "num_predict"]:
            if key in kwargs and kwargs[key] is not None:
                payload[key] = kwargs[key]

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(self.generate_endpoint, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"无法连接到 Ollama 服务，请确保 Ollama 已在运行 (地址: {self.base_url})"
            )

    def list_models(self) -> List[str]:
        """获取已下载的模型列表"""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(self.tags_endpoint)
                response.raise_for_status()
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"无法连接到 Ollama 服务 (地址: {self.base_url})"
            )


# 全局客户端
ollama_client = OllamaClient()


# ============== API 路由 ==============

@app.get("/")
async def root():
    """API 根路径"""
    return {
        "service": "Ollama Local LLM API",
        "version": "1.0.0",
        "base_url": OLLAMA_BASE_URL,
        "default_model": DEFAULT_MODEL,
        "endpoints": {
            "POST /chat": "聊天接口（与 OpenAI 兼容）",
            "POST /completion": "文本补全接口",
            "GET /models": "列出可用模型",
            "GET /health": "健康检查"
        }
    }


@app.post("/chat")
async def chat(request: ChatRequest):
    """
    聊天接口 - 与 OpenAI Chat API 兼容

    请求示例：
    ```json
    {
        "model": "gemma:2b",
        "messages": [
            {"role": "user", "content": "你好，请介绍一下自己"}
        ]
    }
    ```
    """
    # 转换为 Ollama 格式
    ollama_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in request.messages
    ]

    result = ollama_client.chat(
        model=request.model,
        messages=ollama_messages,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        num_predict=request.max_tokens,
    )

    return {
        "status": "success",
        "model": request.model,
        "response": result.get("message", {}).get("content", ""),
        "usage": {
            "prompt_tokens": result.get("prompt_eval_count", 0),
            "completion_tokens": result.get("eval_count", 0),
        },
        "raw": result
    }


@app.post("/completion")
async def completion(request: CompletionRequest):
    """
    文本补全接口

    请求示例：
    ```json
    {
        "model": "gemma:2b",
        "prompt": "从前有座山，"
    }
    ```
    """
    result = ollama_client.generate(
        model=request.model,
        prompt=request.prompt,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        num_predict=request.max_tokens,
    )

    return {
        "status": "success",
        "model": request.model,
        "response": result.get("response", ""),
        "usage": {
            "prompt_tokens": result.get("prompt_eval_count", 0),
            "completion_tokens": result.get("eval_count", 0),
        },
        "raw": result
    }


@app.get("/models")
async def list_models():
    """列出 Ollama 中已下载的模型"""
    models = ollama_client.list_models()
    return {
        "status": "success",
        "models": models,
        "count": len(models)
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        models = ollama_client.list_models()
        return {
            "status": "healthy",
            "ollama_url": OLLAMA_BASE_URL,
            "available_models": models,
            "default_model": DEFAULT_MODEL
        }
    except HTTPException as e:
        return {
            "status": "unhealthy",
            "detail": e.detail
        }


# ============== OpenAI SDK 兼容层 ==============

class OpenAICompatibleClient:
    """
    OpenAI SDK 兼容的客户端

    使用方式（与 OpenAI SDK 完全兼容）：
    ```python
    from openai import OpenAI

    client = OpenAI(
        base_url="http://localhost:8005/v1",
        api_key="ollama"  # 占位符
    )

    response = client.chat.completions.create(
        model="gemma:2b",
        messages=[{"role": "user", "content": "你好"}]
    )
    print(response.choices[0].message.content)
    ```
    """

    def __init__(self, base_url: str = "http://localhost:8005"):
        self.base_url = base_url.rstrip("/")
        self._chat_completions = _ChatCompletionsProxy(f"{self.base_url}/chat")

    @property
    def chat(self):
        return _ChatNamespace(proxy=self._chat_completions)


class _ChatNamespace:
    def __init__(self, proxy):
        self._proxy = proxy

    @property
    def completions(self):
        return self._proxy


class _ChatCompletionsProxy:
    def __init__(self, endpoint: str):
        self._endpoint = endpoint

    def create(self, model: str, messages: List[Dict], **kwargs):
        """创建聊天完成（兼容 OpenAI SDK 格式）"""
        # 构建请求
        payload = {
            "model": model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", 512),
        }

        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            payload["top_k"] = kwargs["top_k"]

        # 发送请求
        with httpx.Client(timeout=120.0) as client:
            response = client.post(self._endpoint, json=payload)
            response.raise_for_status()
            result = response.json()

        # 转换为 OpenAI 格式
        return _ChatCompletionResponse(result)


class _ChatCompletionResponse:
    """模拟 OpenAI 的 ChatCompletion 响应格式"""

    def __init__(self, ollama_result: Dict):
        self.id = f"chatcmpl-{os.urandom(8).hex()}"
        self.object = "chat.completion"
        self.created = 1234567890
        self.model = ollama_result.get("model", "unknown")

        content = ollama_result.get("response", "")

        self.choices = [_Choice(message=_Message(content=content))]
        self.usage = _Usage(
            prompt_tokens=ollama_result.get("usage", {}).get("prompt_tokens", 0),
            completion_tokens=ollama_result.get("usage", {}).get("completion_tokens", 0),
            total_tokens=ollama_result.get("usage", {}).get("prompt_tokens", 0) +
                         ollama_result.get("usage", {}).get("completion_tokens", 0)
        )


class _Choice:
    def __init__(self, message):
        self.message = message
        self.index = 0
        self.finish_reason = "stop"


class _Message:
    def __init__(self, content: str):
        self.content = content
        self.role = "assistant"


class _Usage:
    def __init__(self, prompt_tokens: int, completion_tokens: int, total_tokens: int):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


# 挂载到 /v1 路径（OpenAI SDK 兼容）
@app.post("/v1/chat/completions")
async def v1_chat_completions(request: ChatRequest):
    """OpenAI SDK 兼容的 /v1/chat/completions 端点"""
    return await chat(request)


@app.post("/v1/completions")
async def v1_completions(request: CompletionRequest):
    """OpenAI SDK 兼容的 /v1/completions 端点"""
    return await completion(request)


@app.get("/v1/models")
async def v1_models():
    """OpenAI SDK 兼容的模型列表"""
    models = ollama_client.list_models()
    return {
        "object": "list",
        "data": [
            {
                "id": model,
                "object": "model",
                "created": 1234567890,
                "owned_by": "ollama"
            }
            for model in models
        ]
    }


# ============== 启动服务 ==============

if __name__ == "__main__":
    print("=" * 60)
    print("Ollama 本地 LLM API 服务")
    print("=" * 60)
    print(f"Ollama 地址: {OLLAMA_BASE_URL}")
    print(f"默认模型: {DEFAULT_MODEL}")
    print(f"API 端口: 8005")
    print("=" * 60)
    print("可用接口:")
    print("  POST /chat              - 聊天接口")
    print("  POST /completion        - 文本补全")
    print("  GET  /models            - 列出可用模型")
    print("  GET  /health            - 健康检查")
    print("  POST /v1/chat/completions - OpenAI SDK 兼容")
    print("=" * 60)
    print("启动 Ollama (如果未运行):")
    print("  ollama serve")
    print("下载模型:")
    print("  ollama pull gemma:2b")
    print("  ollama pull llama3.2")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8005)
