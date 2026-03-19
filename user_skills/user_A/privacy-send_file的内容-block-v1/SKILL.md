---
name: privacy-send_file的内容-block-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773923963
user_id: user_A
confidence: 0.6
needs_review: true
status: sandbox_passed
description: >
  在 在微信中发送敏感医疗文件时 场景下保护 send_file的内容 字段。
  策略为 block。
---

# 在微信中发送敏感医疗文件时

## 触发条件
- app_context 匹配: wechat
- action 匹配: send_file
- 字段: send_file的内容

## 执行规则
- strategy: block
- replacement: None
- rule_text: 在微信中发送敏感医疗文件时，将文件内容替换为None
