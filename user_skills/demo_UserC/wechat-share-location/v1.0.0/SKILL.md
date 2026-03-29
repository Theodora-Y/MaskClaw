---
name: wechat-share-location
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538698
user_id: demo_UserC
confidence: 0.8
needs_review: false
status: sandbox_passed
description: >
  在 微信 场景下，在微信聊天中发送或分享实时位置 时保护 实时位置 的隐私规则。
  策略为 mask。
---

## 何时使用
在微信的聊天中发送或分享实时位置时，该技能被触发。

## 执行步骤
- [ ] 步骤1：打开微信，进入目标聊天对话
- [ ] 步骤2：点击输入框右侧的‘+’图标，选择‘位置’
- [ ] 步骤3：确认分享位置后，点击‘分享实时位置’（若提示需授权，请点击‘授权’）
- [ ] 步骤4：发送成功后，自动记录位置信息，事后手动关闭位置共享功能（通过点击位置图标右上角的‘X’关闭）

## 边界情况
- [特殊情况1]：用户未授权位置权限时，拦截操作并提示用户授权
- [特殊情况2]：操作超时或网络失败时，提示用户重试并记录错误日志