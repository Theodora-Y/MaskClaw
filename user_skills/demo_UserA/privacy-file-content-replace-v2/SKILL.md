---
name: privacy-file-content-replace-v2
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1774001523
user_id: demo_UserA
confidence: 0.82
needs_review: false
status: sandbox_passed
description: >
  在 在 wechat 场景下，用户希望修改 Agent 的操作内容 场景下保护 file_content 字段。
  策略为 replace。
---

# 在 wechat 场景下，用户希望修改 Agent 的操作内容

## 何时使用
在微信场景下，当 Agent 想要发送文件内容时，如果用户希望修改 Agent 的操作内容，该规则会被触发。

## 执行步骤
- [ ] 检查当前操作是否为在微信中发送文件。
- [ ] 如果策略为 replace，则将文件内容替换为用户提供的替代值（user_provided_replacement）。
- [ ] 继续执行发送文件的操作。

## 边界情况
- [特殊情况1]：如果用户未提供替代值，系统将使用默认空值或保留原内容。
- [特殊情况2]：如果替换后的文件内容格式不符合要求，系统将提示用户重新提供有效内容。
