---
name: privacy-message-content-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773986241
user_id: demo_d1_257b_UserA
confidence: 0.94
needs_review: false
status: sandbox_passed
description: >
  在 在wechat场景下，Agent尝试发送包含特定图片内容的消息时 场景下保护 message_content 字段。
  策略为 replace。
---

# 在wechat场景下，Agent尝试发送包含特定图片内容的消息时

## 何时使用
在微信场景下，当Agent尝试发送包含特定图片内容的消息时，会触发此规则。

## 执行步骤
- [ ] 检查message_content是否包含需要替换的特定图片内容。
- [ ] 如果需要替换，则将message_content中的特定图片内容替换为用户提供的替代内容（user_provided_replacement）。
- [ ] 继续执行发送消息的操作。

## 边界情况
- [特殊情况1]：如果message_content为空或不包含任何内容，则无需进行替换操作。
- [特殊情况2]：如果用户未提供替代内容（user_provided_replacement），则直接拦截该消息发送。
