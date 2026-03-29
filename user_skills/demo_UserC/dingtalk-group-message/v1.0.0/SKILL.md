---
name: dingtalk-group-message
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538671
user_id: demo_UserC
confidence: 0.85
needs_review: false
status: sandbox_passed
description: >
  在 钉钉 场景下，在钉钉的工作群聊中发送一条消息 时保护 客户信息 的隐私规则。
  策略为 mask。
---

## 何时使用
在钉钉的工作群聊中发送一条消息时，该技能被触发。

## 执行步骤
- [ ] 步骤1：打开钉钉应用，进入工作群聊页面（点击群聊名称或图标）。
- [ ] 步骤2：点击输入框，等待输入键盘弹出。
- [ ] 步骤3：输入消息内容，确保不包含未脱敏的客户信息（如客户姓名、联系方式等）。
- [ ] 步骤4：点击发送按钮（右下角的对勾图标）完成消息发送。

## 边界情况
- [特殊情况1]：如果网络连接不稳定，发送失败，提示用户检查网络并重试。
- [特殊情况2]：如果用户拒绝发送消息，自动退出操作流程并记录用户反馈。