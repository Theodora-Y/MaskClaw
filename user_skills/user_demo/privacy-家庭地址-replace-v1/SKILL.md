---
name: privacy-家庭地址-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773915605
user_id: user_demo
confidence: 0.76
needs_review: false
status: sandbox_passed
description: >
  在 论坛注册过程中 场景下保护 家庭地址 字段。
  策略为 replace。
---

# 论坛注册过程中

## 触发条件
- app_context 匹配: forum_register
- action 匹配: fill_home_address
- 字段: 家庭地址

## 执行规则
- strategy: replace
- replacement: 公司地址
- rule_text: 在论坛注册场景下，当Agent尝试填写家庭地址时，用户希望将其替换为公司地址。
