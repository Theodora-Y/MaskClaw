---
name: wechat-send-message
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538568
user_id: demo_UserA
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
- [ ] 步骤1：点击微信聊天窗口中的输入框。
- [ ] 步骤2：读取当前聊天内容，确定当前对话场景
- [ ] 步骤3：按照上下文，考虑回复内容。
- [ ] 步骤4：输入需要发送的文字内容（确保不包含敏感信息）。
- [ ] 步骤5：点击发送按钮（绿色对勾图标）完成消息发送。

## 边界情况
- [特殊情况1]：如果消息内容包含敏感字段，自动触发脱敏处理并重新生成安全内容后发送。
- [特殊情况2]：网络连接失败或操作超时，提示用户检查网络状态并重试。