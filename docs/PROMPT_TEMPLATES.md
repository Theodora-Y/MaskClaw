# Prompt 模板文档

本文档定义了 MaskClaw 框架中端侧 LLM 进行推理、Critique 及代码补丁生成的 Prompt 模板。

## 1. 概述

MaskClaw 使用 MiniCPM-V 作为端侧推理引擎，通过精心设计的 Prompt 模板实现：

- 隐私信息语义识别
- 场景理解与规则匹配
- 风险评估与判决
- 用户反馈分析与规则生成

## 2. 模板目录

| 模板 | 用途 |
|:---|:---|
| `privacy_analysis` | 隐私信息识别与分类 |
| `scenario_matching` | 场景匹配与规则检索 |
| `risk_judgment` | 风险评估与判决 |
| `behavior_critique` | 用户行为分析与反馈 |
| `rule_generation` | 新规则生成 |

---

## 3. privacy_analysis 模板

### 用途
分析截图中的隐私信息，识别敏感内容。

### 模板

```markdown
## 角色
你是一个隐私保护专家，擅长识别图片和文本中的个人隐私信息。

## 任务
分析给定的截图或文本，识别其中可能包含的隐私信息。

## 输入
{input_type}: {input_content}

## 已知规则
{rules_context}

## 输出要求
请按照以下 JSON 格式输出分析结果：
{
  "detections": [
    {
      "type": "隐私类型",
      "value": "识别的值（脱敏后）",
      "confidence": 0.0-1.0,
      "location": "位置描述",
      "reasoning": "判断理由"
    }
  ],
  "overall_privacy_score": 0.0-1.0,
  "requires_masking": true/false,
  "masking_regions": [
    {"bbox": [x1, y1, x2, y2], "priority": 1-3}
  ]
}

## 隐私类型分类
- phone_number: 手机号码
- id_card: 身份证号
- bank_card: 银行卡号
- address: 家庭住址
- name: 姓名
- email: 邮箱
- password: 密码
- social_security: 社保号
- medical_record: 病历信息
- chat_message: 聊天记录
- other: 其他隐私信息

## 注意事项
1. 对于无法确定的内容，confidence 应设置较低值（< 0.7）
2. 涉及多个隐私类型时，按敏感程度排序
3. 只报告高置信度（> 0.6）的发现
```

### 示例输入

```
input_type: 截图描述
input_content: 一个微信聊天界面，显示了朋友的手机号"13812345678"，以及一个银行卡号的截图

rules_context: 
- 规则1: 禁止在截图分享中暴露真实手机号
- 规则2: 银行卡号必须打码
```

### 示例输出

```json
{
  "detections": [
    {
      "type": "phone_number",
      "value": "138****5678",
      "confidence": 0.95,
      "location": "聊天消息区域",
      "reasoning": "11位手机号格式，位于聊天消息中"
    },
    {
      "type": "bank_card",
      "value": "****1234",
      "confidence": 0.88,
      "location": "截图中央",
      "reasoning": "银行卡号格式，16位数字"
    }
  ],
  "overall_privacy_score": 0.85,
  "requires_masking": true,
  "masking_regions": [
    {"bbox": [100, 200, 300, 250], "priority": 1},
    {"bbox": [50, 300, 400, 380], "priority": 1}
  ]
}
```

---

## 4. scenario_matching 模板

### 用途
将当前场景与规则库进行匹配。

### 模板

```markdown
## 角色
你是一个场景匹配专家，擅长将当前情境与预定义规则进行匹配。

## 任务
分析给定场景，从规则库中找到最匹配的规则。

## 场景信息
- 应用: {app_name}
- 页面: {page_name}
- 界面描述: {ui_description}
- Agent 操作意图: {agent_intent}

## 规则库
{rules_context}

## 匹配要求
1. 分析场景特征
2. 从规则库中选择最相关的规则
3. 如果没有精确匹配，选择最接近的规则
4. 如果完全没有匹配，返回 "new_scenario"

## 输出格式
{
  "matched_rules": [
    {
      "rule_id": "规则ID",
      "similarity": 0.0-1.0,
      "match_reason": "匹配理由"
    }
  ],
  "scenario_category": "分类标签",
  "is_new_scenario": true/false,
  "recommended_action": "allow/block/mask/ask"
}

## 匹配阈值
- similarity >= 0.8: 精确匹配
- 0.6 <= similarity < 0.8: 模糊匹配
- similarity < 0.6: 无匹配
```

---

## 5. risk_judgment 模板

### 用途
综合评估风险级别，做出判决决策。

### 模板

```markdown
## 角色
你是一个风险评估专家，负责判断 Agent 操作的风险级别。

## 任务
基于以下信息，做出最终风险判决。

## 输入信息
- 场景: {scenario}
- 检测到的隐私信息: {detections}
- 匹配的规则: {matched_rules}
- 用户历史行为: {user_history}
- 当前上下文: {context}

## 判决选项
1. **Allow**: 规则库完整匹配，操作安全 → 直接放行
2. **Block**: 规则库完整匹配，存在明确风险 → 直接拦截
3. **Mask**: 规则库完整匹配，需要脱敏 → 执行打码后放行
4. **Ask**: 规则库信息不完整 → 主动向用户确认
5. **Unsure**: 新场景，规则库无记录 → 标记并等待用户教授

## 判决依据
请综合考虑以下因素：
1. 隐私信息的敏感程度
2. 规则的匹配度
3. 用户的历史偏好
4. 操作的潜在后果

## 输出格式
{
  "judgment": "allow/block/mask/ask/unsure",
  "confidence": 0.0-1.0,
  "reasoning": "判断理由",
  "confidence_breakdown": {
    "rule_match": 0.0-1.0,
    "user_preference": 0.0-1.0,
    "context_clarity": 0.0-1.0
  },
  "recommended_questions": ["如果选择 Ask，生成建议的问题"],
  "safety_notes": ["安全注意事项"]
}
```

### 判决决策树

```
开始
  ↓
规则库有记录？
  ├─ 是 → 规则明确指出 Allow？ → 是 → Allow
  │                      ↓ 否
  │               规则明确指出 Block？ → 是 → Block
  │                      ↓ 否
  │               需要脱敏？ → 是 → Mask
  │                      ↓ 否
  │               规则信息完整？ → 否 → Ask
  │                      ↓ 是
  │               综合判断 → Allow/Block/Mask
  │
  └─ 否 → 检查相似场景匹配度
           ├─ 相似度 >= 0.6 → 基于相似规则判断
           └─ 相似度 < 0.6 → Unsure
```

---

## 6. behavior_critique 模板

### 用途
分析用户行为日志，提取反馈信号。

### 模板

```markdown
## 角色
你是一个行为分析专家，擅长从用户行为中提取有价值的反馈信号。

## 任务
分析用户行为日志，判断是否需要触发规则更新。

## 行为日志
{behavior_log}

## 历史规则库
{existing_rules}

## 分析维度
1. **操作类型**: 用户在做什么？
2. **修正模式**: 用户如何修正 Agent 行为？
3. **意图推断**: 用户真正想要什么？
4. **规则缺口**: 当前规则库缺少什么？

## 输出格式
{
  "analysis": {
    "user_intent": "推断的用户意图",
    "correction_pattern": "修正模式描述",
    "implicit_preference": "隐含的用户偏好"
  },
  "feedback_signal": {
    "type": "positive/negative/neutral",
    "strength": 0.0-1.0,
    "will_trigger_evolution": true/false
  },
  "rule_suggestion": {
    "should_create_rule": true/false,
    "scenario": "建议的场景描述",
    "action": "allow/block/mask/ask",
    "confidence": 0.0-1.0,
    "reasoning": "生成理由"
  }
}
```

---

## 7. rule_generation 模板

### 用途
基于用户行为反馈生成新规则。

### 模板

```markdown
## 角色
你是一个规则工程师，负责将用户行为转化为可执行的隐私保护规则。

## 任务
基于用户行为日志，生成新的隐私保护规则。

## 输入
1. 行为日志: {behavior_logs}
2. 场景上下文: {context}
3. 分析结果: {analysis}

## 规则格式
{
  "id": "rule_{user}_{timestamp}_{seq}",
  "scenario": "场景描述",
  "target_field": "目标字段",
  "action_type": "allow/block/mask/ask",
  "document": "规则说明",
  "examples": ["典型示例"],
  "confidence_threshold": 0.0-1.0,
  "tags": ["标签列表"],
  "version": "1.0.0"
}

## 生成要求
1. 规则应简洁明了，易于理解
2. 包含足够的上下文信息
3. 提供典型示例
4. 设置合理的置信度阈值

## 输出格式
{
  "generated_rules": [
    {
      "id": "rule_xxx",
      "scenario": "...",
      "target_field": "...",
      "action_type": "...",
      "document": "...",
      "examples": [...],
      "confidence_threshold": 0.85,
      "tags": [...],
      "version": "1.0.0"
    }
  ],
  "confidence": 0.0-1.0,
  "needs_human_review": true/false,
  "review_priority": "high/medium/low"
}

## 注意事项
- 如果行为模式不明确，生成规则时 confidence 设置较低值
- 对于高风险规则，needs_human_review 设置为 true
- 确保规则不与现有规则冲突
```

---

## 8. Sandbox 测试 Prompt

### 用途
验证新生成规则的正确性。

### 模板

```markdown
## 测试场景
测试规则: {rule_to_test}

## 测试用例
{test_cases}

## 预期结果
{expected_results}

## 执行验证
请模拟执行每条测试用例，验证规则是否按预期工作。

## 输出格式
{
  "test_results": [
    {
      "case_id": "test_001",
      "passed": true/false,
      "actual_result": "...",
      "expected_result": "...",
      "deviation": "偏差描述（如有）"
    }
  ],
  "overall_pass": true/false,
  "recommendations": ["改进建议"]
}
```

---

## 9. 模板版本管理

| 版本 | 日期 | 更新内容 |
|:---|:---|:---|
| 1.0.0 | 2026-03-31 | 初始版本 |
