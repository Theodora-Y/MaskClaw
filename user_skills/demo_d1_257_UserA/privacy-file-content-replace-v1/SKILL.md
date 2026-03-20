---
name: privacy-file-content-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773986219
user_id: demo_d1_257_UserA
confidence: 0.94
needs_review: false
status: sandbox_passed
description: >
  在 在 wechat 场景下，Agent 想要 send_file 时 场景下保护 file_content 字段。
  策略为 replace。
---

# 在 wechat 场景下，Agent 想要 send_file 时

## 何时使用
在微信场景下，当您需要发送文件时，如果涉及文件内容需要替换为用户提供的替代内容。

## 执行步骤
- [ ] 检查当前操作是否为通过微信发送文件，并确认涉及的文件内容。
- [ ] 如果操作策略为“replace”，将原文件内容替换为用户提供的替代内容（user_provided_replacement）。
- [ ] 继续执行文件发送操作。

## 边界情况
- [特殊情况1]：如果用户未提供替代内容，则系统应提示用户补充替代内容后继续操作。
- [特殊情况2]：如果文件内容格式不支持替换，则保留原内容并提示用户。
