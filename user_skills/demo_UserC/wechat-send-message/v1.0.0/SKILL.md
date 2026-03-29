---
name: wechat-send-message
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538629
user_id: demo_UserC
confidence: 0.85
needs_review: false
status: sandbox_passed
description: >
  在 微信 场景下，在微信聊天窗口中发送一条文字消息 时保护 病历、身份证、家庭住址 的隐私规则。
  策略为 mask。
---

## 何时使用
在微信的聊天窗口中发送一条文字消息时，该技能被触发。

## 执行步骤
- [ ] 步骤1：点击微信聊天窗口中的输入框
- [ ] 步骤2：输入需要发送的文字内容
- [ ] 步骤3：检查消息内容是否包含敏感信息（如病历、身份证、家庭住址等）
- [ ] 步骤4：若包含敏感信息，执行脱敏操作（mask或replace）后发送
- [ ] 步骤5：点击发送按钮
- [ ] 步骤6：确认消息已成功发送

## 边界情况
- [特殊情况1]：网络连接失败时，提示用户网络异常，等待重新尝试
- [特殊情况2]：用户拒绝脱敏请求时，提示用户修改内容或取消发送
- [特殊情况3]：消息发送超时，提示用户操作超时，建议重试