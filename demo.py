# Demo 测试脚本

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proxy_agent import (
    PrivacyProxyAgent,
    get_privacy_agent,
    PromptLoader,
    ChromaMemory,
    MiniCPMClient,
    SmartMasker
)


def test_prompt_loader():
    """测试 Prompt 加载器"""
    print("\n" + "=" * 50)
    print("测试 PromptLoader")
    print("=" * 50)
    
    loader = PromptLoader()
    
    # 加载 retrieval_decision
    prompt = loader.load("retrieval_decision")
    print(f"retrieval_decision prompt 长度: {len(prompt)}")
    print(f"前100字符: {prompt[:100]}...")
    
    # 加载 relevance_assessment
    prompt2 = loader.load("relevance_assessment")
    print(f"relevance_assessment prompt 长度: {len(prompt2)}")


def test_chroma_memory():
    """测试 ChromaDB 存储"""
    print("\n" + "=" * 50)
    print("测试 ChromaMemory")
    print("=" * 50)
    
    chroma = ChromaMemory()
    
    # 检索测试
    results = chroma.retrieve("手机号注册", top_k=3)
    print(f"检索 '手机号注册' 结果数量: {len(results)}")
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.get('document', '')[:50]}...")
        print(f"     distance: {r.get('distance', 0):.4f}")
    
    # 添加规则测试
    test_rule = {
        "id": "test_rule_001",
        "scenario": "测试场景",
        "target_field": "测试字段",
        "document": "测试规则内容"
    }
    success = chroma.add_rule(test_rule)
    print(f"\n添加测试规则: {'成功' if success else '失败'}")


def test_minicpm_client():
    """测试 MiniCPM 客户端"""
    print("\n" + "=" * 50)
    print("测试 MiniCPMClient")
    print("=" * 50)
    
    client = MiniCPMClient()
    
    # 简单对话测试
    print("发送测试消息...")
    result = client.chat("你好，请回复 'OK'")
    print(f"结果: {result}")
    
    # 检索决策测试
    loader = PromptLoader()
    need_retrieve = client.decide_retrieval("注册账号需要填什么信息？", loader)
    print(f"\n是否需要检索: {need_retrieve}")


def test_smart_masker():
    """测试打码服务"""
    print("\n" + "=" * 50)
    print("测试 SmartMasker")
    print("=" * 50)
    
    masker = SmartMasker()
    
    # 检查打码器是否可用
    m = masker._get_masker()
    if m is None:
        print("⚠️ 打码器不可用 (可能缺少 skills.smart_masker 模块)")
    else:
        print("✅ 打码器已加载")


def test_full_flow():
    """测试完整流程"""
    print("\n" + "=" * 50)
    print("测试完整流程")
    print("=" * 50)
    
    # 初始化代理
    agent = get_privacy_agent()
    print("✅ PrivacyProxyAgent 初始化完成")
    
    # 检查组件状态
    print(f"  - prompt_loader: {type(agent.prompt_loader).__name__}")
    print(f"  - chroma_memory: {type(agent.chroma_memory).__name__}")
    print(f"  - minicpm_client: {type(agent.minicpm_client).__name__}")
    print(f"  - smart_masker: {type(agent.smart_masker).__name__}")


def test_api_server():
    """测试 API 服务"""
    print("\n" + "=" * 50)
    print("测试 API Server")
    print("=" * 50)
    
    import requests
    
    # 健康检查
    r = requests.get("http://127.0.0.1:8001/")
    print(f"健康检查: {r.json()}")
    
    # 获取规则
    r = rules = requests.get("http://127.0.0.1:8001/rules")
    print(f"规则数量: {len(r.json())}")


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║              隐私代理 Demo 测试脚本                        ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    # 逐个测试
    test_prompt_loader()
    test_chroma_memory()
    test_minicpm_client()
    test_smart_masker()
    test_full_flow()
    
    print("\n" + "=" * 50)
    print("所有测试完成")
    print("=" * 50)
