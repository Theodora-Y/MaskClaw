---
name: xiaohongshu-comment
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538636
user_id: demo_UserC
confidence: 0.85
needs_review: false
status: sandbox_passed
description: >
  在 小红书 场景下，在小红书帖子下方发布一条评论 时保护 真实姓名、手机号、就诊记录 的隐私规则。
  策略为 replace。
---

## 何时使用
在小红书的在小红书帖子下方发布一条评论时，该技能被触发。

## 执行步骤
- [ ] 步骤1：点击帖子下方的“评论”按钮，进入评论输入框。
- [ ] 步骤2：输入评论内容（确保不包含真实姓名、手机号、就诊记录等隐私信息）。
- [ ] 步骤3：点击输入框右侧的“发布”按钮，提交评论。

## 边界情况
- [特殊情况1]：如果网络连接失败或超时，提示用户检查网络并重试。
- [特殊情况2]：如果用户拒绝评论发布请求，直接返回上一步，等待用户重新操作。