---
name: privacy-file-content-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773986251
user_id: demo_d1_bucket_UserA
confidence: 0.82
needs_review: false
status: sandbox_passed
description: >
  在 在 wechat 场景下，Agent 想要 send_file 时 场景下保护 file_content 字段。
  策略为 replace。
---

# 在 wechat 场景下，Agent 想要 send_file 时

## 何时使用
在微信场景下，当您准备发送文件时，如果需要对文件内容进行隐私保护处理。

## 执行步骤
- [ ] 检查当前操作是否为在微信中发送文件。
- [ ] 根据隐私规则，将文件内容替换为用户提供的替代值。
- [ ] 继续执行发送文件的操作。

## 边界情况
- [特殊情况1]：如果用户未提供替代值，则无法完成替换操作。
- [特殊情况2]：如果文件内容为空，则直接跳过替换步骤。
