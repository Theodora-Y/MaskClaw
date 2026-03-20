---
name: privacy-file-content-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773986235
user_id: demo_d1_257b_UserA
confidence: 0.94
needs_review: false
status: sandbox_passed
description: >
  在 在wechat场景下，Agent尝试发送文件时 场景下保护 file_content 字段。
  策略为 replace。
---

# 在wechat场景下，Agent尝试发送文件时

## 何时使用
在微信场景下，当Agent尝试发送文件时，如果触发了隐私保护规则，需要对发送内容进行处理。

## 执行步骤
- [ ] 检查当前操作是否为在微信中发送文件。
- [ ] 如果策略为替换（replace），将文件的`file_content`替换为用户提供的替换内容`user_provided_replacement`。
- [ ] 继续执行发送文件的操作。

## 边界情况
- [特殊情况1]：如果用户提供的替换内容为空或无效，使用默认的隐私保护占位符。
- [特殊情况2]：如果文件类型不支持替换，直接拦截并提示用户无法进行替换操作。
