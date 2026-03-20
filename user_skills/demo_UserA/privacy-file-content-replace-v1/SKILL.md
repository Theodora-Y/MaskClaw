---
name: privacy-file-content-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773986210
user_id: demo_UserA
confidence: 0.82
needs_review: false
status: sandbox_passed
description: >
  在 在 wechat 场景下，用户与 Agent 进行交互时 场景下保护 file_content 字段。
  策略为 replace。
---

# 在 wechat 场景下，用户与 Agent 进行交互时

## 何时使用
在微信场景下，当用户与Agent进行交互时，如果涉及发送文件内容（如图片、文档等），且该内容需要替换为用户提供的替代文本时，触发此规则。

## 执行步骤
- [ ] 检查当前操作是否为通过微信发送文件，并确认文件内容字段存在。
- [ ] 根据策略（block或replace）执行处理：若为block，直接拦截发送操作并提示用户；若为replace，将文件内容替换为用户提供的替代文本。
- [ ] 继续执行后续操作或返回结果。

## 边界情况
- [特殊情况1]：如果用户未提供替代文本，直接拦截发送操作并提示用户补充信息。
- [特殊情况2]：如果文件内容为空，则无需替换，直接发送原始文件。
- [特殊情况3]：如果策略为block，且用户选择不拦截，则按原计划发送文件内容。
