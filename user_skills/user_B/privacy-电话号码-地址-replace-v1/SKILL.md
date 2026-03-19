---
name: privacy-电话号码-地址-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773922605
user_id: user_B
confidence: 0.79
needs_review: false
status: sandbox_passed
description: >
  在 在微信中通过Agent发送消息 场景下保护 电话号码/地址 字段。
  策略为 replace。
---

# 在微信中通过Agent发送消息

## 触发条件
- app_context 匹配: wechat
- action 匹配: send_message
- 字段: 电话号码/地址

## 执行规则
- strategy: replace
- replacement: 公司地址：北京市朝阳区XX大厦
- rule_text: 在微信中，当Agent尝试发送电话号码或地址时，用户希望将其替换为公司地址
