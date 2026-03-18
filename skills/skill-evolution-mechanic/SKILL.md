---
name: skill-evolution-mechanic
description: >
  分析 behavior-monitor 输出的用户纠错日志，自动提炼个性化隐私规则，
  经沙盒验证后写入本地 RAG 知识库。
  当 correction_log 中累积了足够的用户纠错信号、需要更新规则库时使用。
  适用于 AutoGLM、OpenClaw 等 GUI Agent 框架的 L3 自进化层。
  即使用户未明确要求"更新规则"，系统空闲或夜间自动触发时也应激活本技能。
---

# Skill Evolution Mechanic

## 何时使用

以下任一条件满足时触发：
- 同一用户同一类操作，累积了 N>=2 条有效纠错记录
- 用户主动请求"总结我的习惯"或"更新隐私规则"
- 系统进入空闲时段（夜间定时任务）

## 职责边界

**做的事：**
- 读取 correction_log，分组计算 confidence，调用 MiniCPM 提炼规则
- 沙盒验证新规则不与历史 Allow 记录冲突
- 写入 Chroma RAG，标记日志 processed=true

**不做的事：**
- 不监听 UI 事件（behavior-monitor 负责）
- 不做实时检索和拦截（proxy_agent L2 负责）
- 不修改 proxy_agent.py 或其他已有文件

说明：
- 沙盒验证阶段允许读取 behavior_log 中 resolution=allow 的历史记录，这属于离线校验输入，不属于实时拦截职责。

## 输入格式

读取 `memory/logs/{user_id}/correction_log.jsonl`

每条记录是单条合并记录（已含 correction_type 和 correction_value），
无需配对处理：
```json
{
  "event_id": "user_B_001",
  "user_id": "user_B",
  "ts": 1700000000,
  "app_context": "forum_register",
  "action": "fill_home_address",
  "field": "home_address",
  "value_preview": "北京市海淀区xx路",
  "resolution": "ask",
  "level": 2,
  "correction_type": "user_modified",
  "correction_value": "公司地址",
  "processed": false,
  "expire_ts": 1700600000
}
```

只处理 correction_type 为以下三种的条目：
- `user_denied`
- `user_modified`
- `user_interrupted`

## 工作流

### Step 1：分组
- [ ] 读取 `memory/logs/{user_id}/correction_log.jsonl`
- [ ] 过滤 processed=false 且 correction_type 有效的条目
- [ ] 按 (user_id, action, app_context) 分组
- [ ] 过滤掉 value_preview == correction_value 的条目
- [ ] 过滤掉分组数量 < 2 的组
- [ ] 转换为脚本输入数组（当前脚本最小字段：action/correction）
- [ ] 运行 `scripts/extract_rule.py --input <normalized_logs.json> --min-support 2`

### Step 2：计算 confidence
- [ ] 对每组调用 confidence 计算逻辑
      详见 [confidence 计算策略](references/confidence_policy.md)
- [ ] confidence < 0.6：写入 pending 队列，跳过
- [ ] confidence >= 0.6：进入 Step 3
- [ ] 当前版本说明：scripts/extract_rule.py 仅实现最小候选抽取（基于 min-support），
  score/extract/sandbox/commit 属于后续实现阶段。

### Step 3：调用 MiniCPM 提炼规则
- [ ] 按以下 Prompt 模板打包输入（每组最多取5条）
- [ ] POST 请求发送至 http://127.0.0.1:8000/chat
- [ ] 解析输出，提取结构化规则 JSON
      详见 [规则结构](references/rule_schema.md)
- [ ] 解析失败：记录错误，跳过本组，不中断整体流程
- [ ] 当前版本说明：该步骤尚未在 scripts/extract_rule.py 中实现。

**Prompt 模板：**
```
你是隐私规则分析助手。分析以下用户行为，提炼一条隐私保护规则。

{examples}

规律分析：用户在什么场景下，不希望Agent填写什么内容，希望用什么替代？

严格按以下JSON格式输出，不要输出任何其他内容：
{
  "scene": "场景描述，尽量具体",
  "sensitive_field": "敏感字段名",
  "strategy": "block或replace",
  "replacement": "替换值，strategy=block时填null",
  "rule_text": "一句话自然语言规则描述"
}
```

examples 的每条格式：
```
记录N：
  场景：{app_context}
  Agent想做：{action}，填入"{value_preview}"
  用户反应：{correction_type}，改为"{correction_value}"
```

### Step 4：沙盒验证
- [ ] 读取该用户 `memory/logs/{user_id}/behavior_log.jsonl`
      中 resolution=allow 的历史记录
- [ ] 逐条检验：新规则是否会误拦历史 Allow 操作

**冲突判断逻辑：**
```
新规则的 scene 和 sensitive_field
与历史 Allow 记录的 app_context 和 action 进行匹配：
  - 完全匹配 → 冲突，拒绝写入
  - 部分匹配 → 尝试缩窄 scene 条件后重新验证
  - 无匹配   → 通过
```

- [ ] 二次验证仍冲突：拒绝，写入
      `memory/candidate_rules_rejected.jsonl`
- [ ] 验证通过：进入 Step 5
- [ ] 当前版本说明：该步骤尚未在 scripts/extract_rule.py 中实现。

### Step 5：写入 RAG
- [ ] 将 rule_text 向量化（embedding）
- [ ] 写入 Chroma collection `privacy_rules`
- [ ] 同步追加到 `memory/chroma_storage/rules.json`
- [ ] 将本批次条目标记 processed=true
- [ ] 输出报告：新增规则数 / 拒绝数 / pending 数
- [ ] 当前版本说明：该步骤尚未在 scripts/extract_rule.py 中实现。

## 输出

**写入 Chroma（collection: privacy_rules）：**
```json
{
  "rule_id": "user_B_20260318_001",
  "user_id": "user_B",
  "scene": "非电商平台注册",
  "sensitive_field": "home_address",
  "strategy": "replace",
  "replacement": "公司地址",
  "rule_text": "在非电商平台注册时，用公司地址替代家庭住址",
  "confidence": 0.82,
  "trigger_count": 3,
  "needs_review": false,
  "status": "active",
  "created_ts": 1700000000
}
```

**本地归档：**
```
memory/chroma_storage/rules.json     ← active 规则备份
memory/candidate_rules_pending.jsonl ← confidence 不足
memory/candidate_rules_rejected.jsonl← 沙盒验证失败
```

## 注意事项
- MiniCPM 接口：POST http://127.0.0.1:8000/chat
- 模型为 MiniCPM-o-2_6，Prompt 必须给严格 JSON 格式约束
- 支持 --mock-input 参数离线验收
- 任何步骤报错只跳过当前组，不中断整体流程
- 当前 scripts/extract_rule.py 的可用参数：--input / --mock-input / --min-support