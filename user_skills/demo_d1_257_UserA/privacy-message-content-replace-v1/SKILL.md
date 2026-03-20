---
name: privacy-message-content-replace-v1
version: v0.1.0
generated_by: skill-evolution-mechanic
generated_ts: 1773986224
user_id: demo_d1_257_UserA
confidence: 0.94
needs_review: false
status: sandbox_passed
description: >
  在 在 wechat 场景下，Agent 打算发送消息 场景下保护 message_content 字段。
  策略为 replace。
---

# 在 wechat 场景下，Agent 打算发送消息

## 何时使用
在 WeChat 场景下，当 Agent 准备发送消息时，如果需要对 message_content 进行隐私保护处理。

## 执行步骤
- [ ] 检查当前操作是否为 send_message，并确认涉及 message_content 字段。
- [ ] 根据规则策略（block 或 replace），决定处理方式：
  - 如果 strategy=block，则直接拦截消息发送并提示用户；
  - 如果 strategy=replace，则将 message_content 替换为 user_provided_replacement。
- [ ] 完成替换或拦截后，继续执行后续操作。

## 边界情况
- [特殊情况1]：如果 message_content 为空，则无需进行任何替换或拦截，直接发送原始消息。
- [特殊情况2]：如果 user_provided_replacement 不合法（如格式错误），则使用默认的占位符内容进行替换。
- [特殊情况3]：如果 WeChat 环境发生变化（如切换到其他应用），则不触发此隐私保护规则。
