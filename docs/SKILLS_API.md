# Skills API 文档

本文档定义了 MaskClaw 框架中三大核心 Skills 的输入输出契约。

## 目录

- [1. Smart Masker](#1-smart-masker)
- [2. Behavior Monitor](#2-behavior-monitor)
- [3. Skill Evolution](#3-skill-evolution)

---

## 1. Smart Masker

**智能视觉打码模块**，基于 RapidOCR 识别敏感文本区域并进行视觉脱敏处理。

### 1.1 类：`VisualMasker`

```python
from skills.smart_masker import VisualMasker

masker = VisualMasker()
result = masker.process_image(image_path, sensitive_keywords)
```

### 1.2 方法

#### `process_image(image_path, sensitive_keywords, method='blur')`

对图片中的敏感区域进行打码处理。

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `image_path` | `str` | ✅ | 图片路径或 Base64 编码的图片 |
| `sensitive_keywords` | `List[str]` | ✅ | 敏感关键词列表 |
| `method` | `str` | ❌ | 打码方式：`blur`（高斯模糊，默认）/ `mosaic`（马赛克）/ `block`（色块） |

### 1.3 返回值

```json
{
  "success": true,
  "masked_image_path": "temp/masked_xxx.jpg",
  "detected_regions": [
    {
      "text": "13812345678",
      "bbox": [x1, y1, x2, y2],
      "keyword_matched": "手机号"
    }
  ],
  "regions_count": 1,
  "processing_time_ms": 45
}
```

### 1.4 核心能力

| 能力 | 说明 |
|:---|:---|
| **RapidOCR 识别** | 高性能 OCR 引擎，毫秒级文本检测与识别 |
| **语义相似匹配** | 支持模糊匹配，关键词部分匹配也能识别 |
| **多种打码方式** | 高斯模糊、马赛克、色块覆盖 |
| **坐标精确定位** | 返回打码区域坐标，便于后续处理 |

### 1.5 示例

```python
from skills.smart_masker import VisualMasker

masker = VisualMasker()

# 敏感关键词列表
keywords = ["手机号", "身份证", "银行卡", "密码"]

# 处理图片
result = masker.process_image(
    image_path="test.jpg",
    sensitive_keywords=keywords,
    method="blur"
)

print(f"检测到 {result['regions_count']} 个敏感区域")
print(f"脱敏图片已保存至: {result['masked_image_path']}")
```

---

## 2. Behavior Monitor

**行为监控模块**，标准化所有事件到共享 Schema，捕获用户参与的操作行为。

### 2.1 类：`BehaviorMonitor`

```python
from skills.behavior_monitor import BehaviorMonitor

monitor = BehaviorMonitor()
```

### 2.2 日志类型

| 类型 | 说明 |
|:---|:---|
| `behavior_log.jsonl` | 用户未参与的操作日志（level=1） |
| `correction_log.jsonl` | 用户参与的操作日志（level=2） |
| `session_trace.jsonl` | 结构化行为链（v2.0 新格式） |

### 2.3 核心方法

#### `log_action(event_type, session_id, action_data)`

记录一次行为事件。

```python
monitor.log_action(
    event_type="user_correction",
    session_id="sess_abc123",
    action_data={
        "action_type": "fill_form",
        "field": "phone_number",
        "proposed_value": "13812345678",
        "was_corrected": True,
        "correction_type": "user_override",
        "user_corrected_value": "138****8888"
    }
)
```

#### `get_session_trace(scenario_tag)`

获取指定场景的行为链。

```python
trace = monitor.get_session_trace(scenario_tag="微信好友验证")
```

### 2.4 返回值

```json
{
  "success": true,
  "log_id": "log_20260331_123456",
  "logged": true,
  "timestamp": 1711867260000,
  "will_trigger_evolution": true
}
```

### 2.5 过期时间配置

| 操作类型 | 默认过期时间 |
|:---|:---|
| `allow` | 24 小时 |
| `block` | 24 小时 |
| `mask` | 24 小时 |
| `ask` | 7 天 |

---

## 3. Skill Evolution

**SOP 自进化模块**，基于爬山法持续优化 SOP（标准操作流程）。

### 3.1 核心流程（爬山法）

```
┌─────────────────────────────────────────────────────────────┐
│  第 1 步：agent 对 skill 做一个小改动                       │
│         （比如：加一条"必须核对输入数据"的规则）               │
├─────────────────────────────────────────────────────────────┤
│  第 2 步：用改动后的 skill 跑 10 个测试用例                  │
├─────────────────────────────────────────────────────────────┤
│  第 3 步：用 checklist 给每个输出打分                       │
│         （4 个检查项全过 = 100 分，3 个过 = 75 分...）        │
├─────────────────────────────────────────────────────────────┤
│  第 4 步：算平均分                                          │
│         - 比上一轮高 → 保留改动                              │
│         - 比上一轮低 → 撤销改动                              │
├─────────────────────────────────────────────────────────────┤
│  第 5 步：重复，直到连续 3 轮分数超过 90% 或你喊停           │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 子模块

| 模块 | 说明 |
|:---|:---|
| **SemanticEvaluator** | LLM-as-a-Judge，快速验证逻辑 |
| **ChecklistEvaluator** | 4项检查评分 |
| **FinalSandbox** | 严格验证后发布 |

### 3.3 数据库表

| 表名 | 说明 |
|:---|:---|
| `session_trace` | 会话轨迹 |
| `sop_draft` | SOP 草稿（多轮迭代） |
| `sop_version` | 已发布版本 |

### 3.4 核心方法

#### `evolve_skill(skill_name, test_cases)`

对指定 Skill 进行自进化优化。

```python
from skills.evolution_mechanic import EvolutionEngine

engine = EvolutionEngine()

result = engine.evolve_skill(
    skill_name="smart_masker",
    test_cases=[
        {"input": "test1.jpg", "expected_keywords": ["手机号"]},
        {"input": "test2.jpg", "expected_keywords": ["银行卡"]}
    ]
)
```

### 3.5 返回值

```json
{
  "success": true,
  "evolution_result": {
    "iterations": 5,
    "final_score": 92.5,
    "improvements": [
      "添加了"模糊匹配"规则",
      "优化了 OCR 识别精度"
    ],
    "new_version": "v1.3.0"
  },
  "passed_sandbox": true
}
```

---

## 五级置信度判决

| 判决 | 条件 | 系统行为 |
|:---:|:---|:---|
| **Allow** | 规则库完整匹配，安全 | 直接放行 |
| **Block** | 规则库完整匹配，风险明确 | 直接拦截 |
| **Mask** | 规则库完整匹配，需脱敏 | 执行打码后放行 |
| **Ask** | 规则库信息不完整 | 主动向用户确认 |
| **Unsure** | 新场景无记录 | 标记并等待用户教授 |

---

## 错误码

| 错误码 | 说明 | 处理建议 |
|:---:|:---|:---|
| `MASK_001` | 图片解码失败 | 检查图片格式 |
| `MASK_002` | 图片过大 | 压缩后重试 |
| `MASK_003` | OCR 识别失败 | 检查图片质量 |
| `MONITOR_001` | 日志写入失败 | 检查存储权限 |
| `EVOLUTION_001` | 规则生成失败 | 减少测试用例批次 |
| `EVOLUTION_002` | 沙盒测试超时 | 检查测试环境 |
