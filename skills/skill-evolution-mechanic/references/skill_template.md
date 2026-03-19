# 自动生成 Skill 的固定模板
version: v0.1.0

---

## 说明

Evolution Mechanic 生成新 Skill 时，
SKILL.md 的格式由本模板保证，
MiniCPM 只负责填入内容字段，不自由生成格式。

---

## SKILL.md 模板

以下 {占位符} 由脚本从 MiniCPM 输出中填入：

---
name: privacy-{sensitive_field}-{strategy}-v{version}
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: {created_ts}
user_id: {user_id}
confidence: {confidence}
needs_review: {needs_review}
status: sandbox_passed
description: >
  {description_line1}
  {description_line2}
---

# {title}

## 触发条件
{trigger_condition}

## 执行规则
策略：{strategy}
涉及字段：{sensitive_field}
替换值：{replacement}（strategy=block 时无此项）

## 规则来源
从 {trigger_count} 次用户纠错行为中自动提炼
置信度：{confidence}
详见 rules.json

---

## 占位符填写规则

| 占位符 | 来源 | 示例 |
|---|---|---|
| sensitive_field | MiniCPM 输出 | home-address |
| strategy | MiniCPM 输出 | replace / block |
| version | 脚本自增 | 1 |
| created_ts | 系统时间 | 1700000000 |
| user_id | correction_log | user_B |
| confidence | 脚本计算 | 0.82 |
| needs_review | confidence 是否在 0.6~0.75 | false |
| title | MiniCPM 的 scene 字段 | 非电商场景地址替换 |
| trigger_condition | 脚本根据 scene + field 生成 | app_context 不在电商白名单内且 action 涉及 home_address |
| description_line1 | 脚本根据 scene 生成 | 在非电商平台填写地址类字段时激活 |
| description_line2 | 脚本根据 strategy 生成 | 当 Agent 在非电商场景填写 home_address 时使用 |
| replacement | MiniCPM 输出 | 公司地址 |
| trigger_count | 分组数量 | 3 |

---

## rules.json 模板

同一次生成，rules.json 同步写入 Chroma RAG：

{
  "rule_id": "{user_id}_{date}_{seq}",
  "user_id": "{user_id}",
  "scene": "{scene}",
  "sensitive_field": "{sensitive_field}",
  "strategy": "{strategy}",
  "replacement": "{replacement}",
  "rule_text": "{rule_text}",
  "confidence": {confidence},
  "trigger_count": {trigger_count},
  "needs_review": {needs_review},
  "status": "active",
  "created_ts": {created_ts},
  "version": "v0.1.0"
}

---

## 目录命名规则

user_skills/{user_id}/
  privacy-{sensitive_field}-{strategy}-v{version}/
    SKILL.md
    rules.json

示例：
  user_skills/user_B/
    privacy-home-address-replace-v1/
      SKILL.md
      rules.json

version 从 1 开始，同一用户同一字段同一策略
有新版本时递增：v1 → v2 → v3
旧版本保留不删除，status 改为 deprecated

Skill 名生成约束（文件系统）：
- 仅允许 `a-z`、`0-9`、`-`。
- 输入字段先转小写，`_` 转 `-`，连续 `-` 合并。
- 非法字符全部移除或替换为 `-`，不能保留中文或其他 Unicode。

字段转换示例：
- `home_address` -> `home-address`
- `file_content` -> `file-content`
- `phone` -> `phone`
```

---

现在三个文件的关系完整了：
```
skill_template.md  → 定义格式
rule_schema.md     → 定义 rules.json 字段
confidence_policy.md → 定义何时触发生成