# Skills API 文档

本文档定义了 MaskClaw 框架中四大核心 Skills 的输入输出契约。

## 目录

- [1. PII_Detection](#1-pii_detection)
- [2. Smart_Masker](#2-smart_masker)
- [3. Behavior_Monitor](#3-behavior_monitor)
- [4. Skill_Evolution](#4-skill_evolution)

---

## 1. PII_Detection

**隐私信息检测模块**，负责识别图片中的格式化敏感信息。

### 1.1 输入

| 字段 | 类型 | 必填 | 说明 |
|:---|:---:|:---:|:---|
| `image` | `str` | ✅ | Base64 编码的图片数据 |
| `mode` | `str` | ❌ | 检测模式：`fast`（默认，快速检测）或 `full`（完整检测，含语义判断） |

### 1.2 输出

```json
{
  "success": true,
  "detections": [
    {
      "type": "phone_number",
      "value": "138****8888",
      "confidence": 0.95,
      "bbox": [x1, y1, x2, y2],
      "reason": "11位手机号格式"
    },
    {
      "type": "id_card",
      "value": "110***********1234",
      "confidence": 0.88,
      "bbox": [x1, y1, x2, y2],
      "reason": "身份证号格式"
    }
  ],
  "summary": {
    "total_detections": 2,
    "high_confidence_count": 2,
    "requires_masking": true
  }
}
```

### 1.3 检测类型

| 类型 | 说明 | 检测方法 |
|:---|:---|:---|
| `phone_number` | 手机号码 | 正则 + OCR |
| `id_card` | 身份证号 | 正则 + OCR |
| `bank_card` | 银行卡号 | Luhn算法 + OCR |
| `address` | 家庭住址 | 语义识别 |
| `name` | 姓名 | 语义识别 |
| `email` | 邮箱 | 正则 + OCR |
| `password` | 密码字段 | UI标签识别 |
| `custom` | 自定义规则 | 用户规则库 |

---

## 2. Smart_Masker

**智能视觉打码模块**，对敏感区域进行本地模糊处理。

### 2.1 输入

| 字段 | 类型 | 必填 | 说明 |
|:---|:---:|:---:|:---|
| `image` | `str` | ✅ | Base64 编码的原始图片 |
| `regions` | `List[Dict]` | ✅ | 需要打码的区域列表 |
| `method` | `str` | ❌ | 打码方式：`mosaic`（马赛克，默认）/ `blur`（高斯模糊）/ `block`（色块覆盖） |
| `intensity` | `int` | ❌ | 打码强度 1-10，默认 5 |

### 2.2 regions 格式

```json
[
  {
    "bbox": [x1, y1, x2, y2],
    "reason": "phone_number",
    "priority": 1
  },
  {
    "bbox": [x1, y1, x2, y2],
    "reason": "id_card",
    "priority": 1
  }
]
```

### 2.3 输出

```json
{
  "success": true,
  "masked_image": "<base64_encoded_image>",
  "regions_processed": 2,
  "processing_time_ms": 45,
  "method_used": "mosaic"
}
```

### 2.4 打码方法对比

| 方法 | 效果 | 适用场景 | 性能 |
|:---|:---|:---|:---|
| `mosaic` | 马赛克模糊 | 大面积区域 | ⚡ 最快 |
| `blur` | 高斯模糊 | 文字区域 | ⚡ 快 |
| `block` | 色块覆盖 | 强隐私区域 | ⚡⚡⚡ 最快 |

---

## 3. Behavior_Monitor

**行为监控模块**，持续监听 Agent 操作行为，捕获用户主动干预动作。

### 3.1 输入

| 字段 | 类型 | 必填 | 说明 |
|:---|:---:|:---:|:---|
| `session_id` | `str` | ✅ | 会话 ID |
| `action_type` | `str` | ✅ | 动作类型 |
| `action_data` | `Dict` | ❌ | 动作详情 |

### 3.2 action_type 类型

| 类型 | 说明 |
|:---|:---|
| `agent_operation` | Agent 发起操作 |
| `user_correction` | 用户主动修正 |
| `user_rejection` | 用户拒绝操作 |
| `user_override` | 用户覆盖操作 |
| `user_feedback` | 用户反馈 |

### 3.3 输出

```json
{
  "success": true,
  "log_id": "log_20260331_123456",
  "logged": true,
  "timestamp": 1711867260000,
  "will_trigger_evolution": true
}
```

### 3.4 日志流格式

```json
{
  "timestamp": 1711867260000,
  "session_id": "sess_abc123",
  "user_id": "user_001",
  "action": "agent_operation",
  "details": {
    "action_type": "fill_form",
    "field": "phone_number",
    "proposed_value": "13812345678",
    "was_corrected": true,
    "correction_type": "user_override",
    "user_corrected_value": "138****8888"
  },
  "context": {
    "app": "wechat",
    "scenario": "friend_verification"
  }
}
```

---

## 4. Skill_Evolution

**规则自进化模块**，从纠错日志中智能抽取新规则，经沙盒测试验证后自动挂载上线。

### 4.1 输入

| 字段 | 类型 | 必填 | 说明 |
|:---|:---:|:---:|:---|
| `logs` | `List[Dict]` | ✅ | 行为日志列表 |
| `mode` | `str` | ❌ | 进化模式：`auto`（自动）或 `manual`（人工审核） |

### 4.2 输出

```json
{
  "success": true,
  "evolution_result": {
    "rules_generated": [
      {
        "id": "rule_user_001_20260331_01",
        "scenario": "微信好友验证页",
        "target_field": "手机号",
        "pattern": "填写手机号用于好友验证",
        "action": "mask",
        "confidence": 0.85,
        "source_logs": ["log_20260331_123456", "log_20260331_123457"],
        "status": "pending_review"
      }
    ],
    "rules_updated": [],
    "rules_deprecated": []
  },
  "sandbox_test_required": true,
  "estimated_review_time": "1-2 hours"
}
```

### 4.3 进化流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  行为日志   │ → │  模式识别   │ → │  规则抽取   │ → │  沙盒测试   │
│  Logs       │    │  Pattern    │    │  Rule Gen   │    │  Sandbox    │
│             │    │  Mining      │    │             │    │  Test       │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                    ↓
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  版本发布   │ ← │  人工审核   │ ← │  测试报告   │ ← │  测试执行   │
│  Deploy     │    │  Review     │    │  Report     │    │  Execute    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
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
| `PII_001` | 图片解码失败 | 检查图片格式 |
| `PII_002` | 图片过大 | 压缩后重试 |
| `MASK_001` | 区域坐标无效 | 检查 bbox 格式 |
| `MONITOR_001` | 日志写入失败 | 检查存储权限 |
| `EVOLUTION_001` | 规则生成失败 | 减少日志批次 |
| `EVOLUTION_002` | 沙盒测试超时 | 检查测试环境 |
