---
name: privacy-send_file内容-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773922600
user_id: user_A
confidence: 0.6
needs_review: true
status: sandbox_passed
description: >
  在 在微信中通过Agent发送文件 场景下保护 send_file内容 字段。
  策略为 replace。
---

# 在微信中通过Agent发送文件

## 触发条件
- app_context 匹配: wechat
- action 匹配: send_file
- 字段: send_file内容

## 执行规则
- strategy: replace
- replacement: None
- rule_text: 在微信中通过Agent发送文件时，将敏感的病历、诊断报告、住院记录等替换为None
