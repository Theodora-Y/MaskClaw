---
name: privacy-send_message的内容-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773923969
user_id: user_B
confidence: 0.76
needs_review: false
status: sandbox_passed
description: >
  在 在微信平台，Agent尝试填写公司地址时 场景下保护 send_message的内容 字段。
  策略为 replace。
---

# 在微信平台，Agent尝试填写公司地址时

## 触发条件
- app_context 匹配: wechat
- action 匹配: send_message
- 字段: send_message的内容

## 执行规则
- strategy: replace
- replacement: 公司地址：北京市朝阳区XX大厦
- rule_text: 在微信平台，当Agent尝试填写公司地址时，将敏感地址信息替换为用户指定的公司地址：北京市朝阳区XX大厦
