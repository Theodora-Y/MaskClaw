# 隐私规则检索与决策实验

这个独立模块接收结构化的截图证据，检索本地隐私规则，并逐个敏感区域给出 `ALLOW`、`MASK` 或 `ASK`。它尚未接入仓库现有的 `proxy_agent.py` 或 `memory/rag_client.py`，也不执行图片打码。

## 在线流程

1. `Evidence` 保存应用、任务、接收方、敏感类型和区域。检索 query 只使用标签与上下文，不包含 OCR 原文或像素框。
2. `SemanticRuleRetriever` 用本地 `BAAI/bge-small-zh-v1.5` 为规则和 query 生成向量；先按规则元数据排除不适用候选，再结合向量相似度与元数据分数排序。模型权重须事先存放在本机，不由代码下载。
3. `DecisionEngine` 处理规则冲突。敏感字段无合适规则时返回 `ASK`；单字段 `ALLOW` 不能放行同屏其他敏感字段。
4. `vision_rag.analyze` 对每个区域独立判断并汇总整图动作：有 `ASK` 则暂停，有 `MASK` 则只列出待打码区域，否则 `ALLOW`。可选的本地模型复核只能引用已检索到的规则。

规则位于 `default_rules.json`，包含 50 条按敏感类型、应用、任务和接收方限定的策略。此处 `ALLOW` 只针对证据中描述的目标任务，不代表原始截图可以直接转发。

## 使用结构化证据

在项目根目录运行，`model_path` 指向已存在的本地 BGE 权重目录：

```python
from rag import Evidence
from rag.semantic import SemanticRuleRetriever
from rag.vision_rag import analyze

evidence = Evidence.from_dict({
    "app": "微信",
    "task": "发送消息",
    "recipient": "陌生人",
    "pii_types": ["phone"],
    "regions": [{"pii_type": "phone", "bbox": [10, 10, 90, 30], "confidence": 0.99}],
    "model_confidence": 0.95,
})
retriever = SemanticRuleRetriever("path/to/bge-small-zh-v1.5")
print(analyze(evidence, retriever))
```

本地验证使用 Python 3.13、PyTorch 2.7.1、Transformers 4.53.2、Hugging Face Hub 0.36.0、NumPy 1.26.4。`vision_rag.py` 的图片入口另需 Pillow 和 Requests，并要求本地 MiniCPM `/chat` 服务。这个提交不包含模型权重、截图、测试集或 API 密钥。
