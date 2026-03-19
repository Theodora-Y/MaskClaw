---
name: skill-evolution-mechanic
version: v0.1.0
description: >
  消费 behavior-monitor 产生的纠错日志，通过反思与泛化，
  提炼个性化隐私规则，经沙盒验证后写入本地 RAG 知识库。
  当 correction_log 累积了足够纠错信号、或系统进入空闲时段时触发。
  适用于 AutoGLM、OpenClaw 等 GUI Agent 框架的 L3 自进化层。
---

# Skill Evolution Mechanic

## 何时触发

- correction_log 中同类操作累积 N>=2 条有效纠错记录
- 系统空闲时段（夜间定时任务）
- 实验/演示模式：--mock-input 注入数据集模拟信号

## 职责边界

**做的事：**
读取 correction_log → 分组计算 confidence
→ 调用 MiniCPM 提炼规则 → 沙盒验证 → 写入 RAG

**不做的事：**
- 不监听 UI 事件（behavior-monitor 负责）
- 不做实时拦截（proxy_agent L2 负责）
- 不直接修改任何已有文件

**注意：**
沙盒验证阶段需读取 behavior_log 中 resolution=allow
的历史记录，属于离线校验输入，不违反职责边界。

## 输入来源

**实验/演示模式（当前阶段）：**
使用 P-GUI-Evo 数据集的 simulation_feedback 字段
作为模拟纠错信号。
数据集中 expected_feedback ≠ 模型实际输出的条目
视为负反馈，写入 correction_log 供本 Skill 处理。
使用 --mock-input 参数直接注入。

**产品模式（未来）：**
读取 memory/logs/{user_id}/correction_log.jsonl
来自真实用户的打断和修正行为。

输入字段说明：
```json
{
  "event_id": "user_B_001",
  "user_id": "user_B",
  "ts": 1700000000,
  "app_context": "forum_register",
  "action": "fill_home_address",
  "field": "home_address",
  "value_preview": "北京市海淀区xx路",
  "correction_type": "user_modified",
  "correction_value": "公司地址",
  "processed": false
}
```

只处理 correction_type 为以下三种的条目：
- `user_modified`
- `user_denied`
- `user_interrupted`

## 工作流

### Step 1：分组
- [ ] 读取 correction_log，过滤 processed=false 且类型有效的条目
- [ ] 过滤掉 value_preview == correction_value 的条目（未真正纠正）
- [ ] 按 (user_id, action, app_context, field) 分组
- [ ] 过滤掉分组数量 < 2 的组（信号不足）
- [ ] 运行 `scripts/extract_rule.py --step group`

### Step 2：计算 confidence
- [ ] 对每组调用 confidence 计算公式
      详见 [confidence 计算策略](references/confidence_policy.md)
- [ ] confidence < 0.6 → 写入 pending 队列，跳过本组
- [ ] confidence 0.6~0.75 → 进入 Step 3，结果标记 needs_review=true
- [ ] confidence > 0.75 → 进入 Step 3，正常写入
- [ ] 运行 `scripts/extract_rule.py --step score`

### Step 3：调用 MiniCPM 提炼规则
- [ ] 读取 Prompt 模板：prompts/evolution_rule_extract.txt
- [ ] 将本组日志按模板格式填入 {examples}（每组最多取 5 条）
- [ ] POST 至 http://127.0.0.1:8000/chat
- [ ] 解析输出，提取结构化规则 JSON
      详见 [规则结构](references/rule_schema.md)
- [ ] 解析失败：记录错误，跳过本组，不中断整体流程
- [ ] 运行 `scripts/extract_rule.py --step extract`

其中 {examples} 由脚本动态填入，每条格式：
```
记录N：
  场景：{app_context}
  Agent想做：{action}，填入"{value_preview}"
  用户反应：{correction_type}，改为"{correction_value}"
```

### Step 4：沙盒验证
- [ ] 调用沙盒验证流程
      详见 [沙盒设计方案](references/sandbox_policy.md)
- [ ] 验证通过 → 进入 Step 5
- [ ] 验证失败 → 写入 candidate_rules_rejected.jsonl，跳过
- [ ] 运行 `scripts/extract_rule.py --step sandbox`

### Step 5：写入 RAG
- [ ] 调用 chroma_manager.add_rule(user_id, rule)
- [ ] 同步追加到 memory/chroma_storage/rules.json
- [ ] 将本批次条目标记 processed=true
- [ ] 输出报告：新增规则数 / 拒绝数 / pending 数
- [ ] 运行 `scripts/extract_rule.py --step commit`

### Step 6：发布用户 Skill
- [ ] 基于通过沙盒验证的规则生成 Skill 目录与文件
- [ ] 发布路径使用 `user_skills/{user_id}/{skill_name}/`
- [ ] 目录内至少包含：`SKILL.md` 与 `rules.json`
- [ ] 若同名旧版本存在，旧版本标记 deprecated，新版本递增
- [ ] 运行 `scripts/extract_rule.py --step release`

## 输出

写入 Chroma（collection: privacy_rules）：
```json
{
  "rule_id": "user_B_20260318_001",
  "user_id": "user_B",
  "scene": "非电商平台注册",
  "app_context_hint": "non_ecommerce",
  "sensitive_field": "home_address",
  "strategy": "replace",
  "replacement": "公司地址",
  "rule_text": "在非电商平台注册时，用公司地址替代家庭住址",
  "confidence": 0.82,
  "trigger_count": 3,
  "needs_review": false,
  "status": "active",
  "created_ts": 1700000000,
  "version": "v0.1.0"
}
```

本地归档：
```
memory/chroma_storage/rules.json      ← active 规则备份
memory/candidate_rules_pending.jsonl  ← confidence 不足
memory/candidate_rules_rejected.jsonl ← 沙盒验证失败
user_skills/{user_id}/{skill_name}/   ← 发布后的用户个性化 Skill
```

## 局限性声明

当前版本（v0.1.0）为实验系统：
- confidence 阈值和沙盒验证提供基础门卫，但规则写入
  决策仍有模型参与，工业落地需引入人工审批环节。
- 对抗性验证（Adversarial Review）尚未实现，
  属于后续迭代目标。

## 注意事项
- MiniCPM 接口：POST http://127.0.0.1:8000/chat
- 模型：MiniCPM-o-2_6，Prompt 必须给严格 JSON 格式约束
- 支持 --mock-input 参数离线验收
- 任何步骤报错只跳过当前组，不中断整体流程
- 进化即压缩：每次迭代后归纳删减本文档冗余内容