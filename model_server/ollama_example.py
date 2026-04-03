"""
Ollama 本地模型使用示例

这个脚本展示了在 Cursor 项目中如何调用本地部署的 Ollama 模型。
支持三种调用方式：直接 HTTP、OpenAI SDK 兼容、命令行测试。
"""

import requests
import json

# ============== 配置 ==============
OLLAMA_API_URL = "http://localhost:8005"
MODEL = "gemma:2b"


def example_1_direct_http():
    """
    方式一：直接使用 HTTP 请求调用
    """
    print("\n" + "=" * 60)
    print("方式一：直接 HTTP 请求")
    print("=" * 60)

    response = requests.post(
        f"{OLLAMA_API_URL}/chat",
        json={
            "model": MODEL,
            "messages": [
                {"role": "user", "content": "你好，帮我解释一下什么是隐私保护"}
            ]
        }
    )

    result = response.json()
    print(f"状态: {result.get('status')}")
    print(f"模型: {result.get('model')}")
    print(f"回复: {result.get('response')}")
    print(f"Token使用: {result.get('usage')}")


def example_2_openai_sdk():
    """
    方式二：使用 OpenAI SDK（兼容 Ollama）
    需要先安装: pip install openai
    """
    print("\n" + "=" * 60)
    print("方式二：OpenAI SDK 兼容模式")
    print("=" * 60)

    try:
        from openai import OpenAI

        # 创建客户端（指向我们的 Ollama API 代理）
        client = OpenAI(
            base_url=f"{OLLAMA_API_URL}/v1",
            api_key="ollama"  # 占位符，Ollama 不需要真正的 API key
        )

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一个有帮助的AI助手"},
                {"role": "user", "content": "解释一下端侧AI的概念"}
            ],
            temperature=0.7,
            max_tokens=256
        )

        print(f"回复: {response.choices[0].message.content}")
        print(f"Token使用: {response.usage}")

    except ImportError:
        print("请先安装 OpenAI SDK: pip install openai")
    except Exception as e:
        print(f"错误: {e}")


def example_3_direct_ollama():
    """
    方式三：直接调用 Ollama 原生 API（绕过代理）
    如果你只想直接用 Ollama，不需要 FastAPI 代理层
    """
    print("\n" + "=" * 60)
    print("方式三：直接调用 Ollama 原生 API")
    print("=" * 60)

    # Ollama 原生地址
    OLLAMA_NATIVE_URL = "http://localhost:11434"

    response = requests.post(
        f"{OLLAMA_NATIVE_URL}/api/chat",
        json={
            "model": MODEL,
            "messages": [
                {"role": "user", "content": "什么是 MaskClaw？"}
            ],
            "stream": False
        },
        timeout=120
    )

    result = response.json()
    print(f"模型: {result.get('model')}")
    print(f"回复: {result.get('message', {}).get('content')}")


def example_4_vision_task():
    """
    方式四：多轮对话示例（适合隐私分析场景）
    """
    print("\n" + "=" * 60)
    print("方式四：多轮对话（隐私分析场景）")
    print("=" * 60)

    messages = [
        {"role": "system", "content": """你是一个隐私保护助手。
当用户发送包含个人信息的截图时，你应当：
1. 识别其中的敏感信息（如电话号码、身份证、银行卡等）
2. 给出脱敏建议
3. 不要存储或转发任何敏感信息"""},
        {"role": "user", "content": "这张截图中有一个手机号 138-1234-5678，需要怎么处理？"},
        {"role": "assistant", "content": "对于手机号 138-1234-5678，建议进行部分遮蔽处理，保留前三位和后四位，即显示为 138****5678，以保护用户隐私。"},
        {"role": "user", "content": "好的，那身份证号 110101199001011234 呢？"},
    ]

    response = requests.post(
        f"{OLLAMA_API_URL}/chat",
        json={
            "model": MODEL,
            "messages": messages,
            "temperature": 0.3,  # 降低温度以保持一致性
            "max_tokens": 256
        }
    )

    result = response.json()
    print(f"回复: {result.get('response')}")


def check_health():
    """检查服务健康状态"""
    print("\n" + "=" * 60)
    print("检查服务状态")
    print("=" * 60)

    try:
        response = requests.get(f"{OLLAMA_API_URL}/health", timeout=5)
        health = response.json()
        print(f"服务状态: {health.get('status')}")
        print(f"可用模型: {health.get('available_models', [])}")
        print(f"默认模型: {health.get('default_model')}")
    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到 API 服务")
        print("请确保已启动 Ollama 服务和 API 代理:")
        print("  1. 终端运行: ollama serve")
        print("  2. 终端运行: python model_server/ollama_api.py")


def list_models():
    """列出所有可用模型"""
    print("\n" + "=" * 60)
    print("列出可用模型")
    print("=" * 60)

    try:
        response = requests.get(f"{OLLAMA_API_URL}/models", timeout=5)
        result = response.json()
        print(f"状态: {result.get('status')}")
        print(f"已下载模型: {result.get('models', [])}")
    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到 API 服务")


if __name__ == "__main__":
    print("=" * 60)
    print("Ollama 本地模型调用示例")
    print("=" * 60)
    print(f"API 地址: {OLLAMA_API_URL}")
    print(f"默认模型: {MODEL}")
    print("=" * 60)

    # 首先检查服务状态
    check_health()
    list_models()

    # 执行各种示例
    try:
        example_1_direct_http()
    except Exception as e:
        print(f"示例1执行失败: {e}")

    try:
        example_2_openai_sdk()
    except Exception as e:
        print(f"示例2执行失败: {e}")

    try:
        example_3_direct_ollama()
    except Exception as e:
        print(f"示例3执行失败: {e}")

    try:
        example_4_vision_task()
    except Exception as e:
        print(f"示例4执行失败: {e}")

    print("\n" + "=" * 60)
    print("示例执行完成！")
    print("=" * 60)
