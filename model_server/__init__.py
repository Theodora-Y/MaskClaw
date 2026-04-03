# model_server/__init__.py
"""
模型服务统一入口

提供两种模型调用方式：
1. MiniCPM-V-4_5 (视觉模型) - 项目 models/OpenBMB/MiniCPM-V-4_5
2. Ollama gemma:2b (文本模型) - 本地 Ollama 服务

使用示例：
    from model_server import MiniCPMClient, OllamaClient

    # 调用 MiniCPM 视觉模型
    minicpm = MiniCPMClient()
    result = minicpm.chat("描述这张图片", image_path="screenshot.png")

    # 调用 Ollama gemma:2b
    ollama = OllamaClient()
    result = ollama.chat("解释什么是隐私保护")
"""

from .minicpm_api import MiniCPMModel
from .ollama_api import OllamaModel, OllamaClient

__all__ = ["MiniCPMModel", "OllamaModel", "OllamaClient"]
