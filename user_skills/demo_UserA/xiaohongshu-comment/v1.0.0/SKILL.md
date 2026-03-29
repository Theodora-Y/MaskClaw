---
name: xiaohongshu-comment
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538576
user_id: demo_UserA
confidence: 0.85
needs_review: false
status: sandbox_passed
description: >
  在 小红书 场景下，在小红书帖子下方发布一条评论 时保护 真实姓名、手机号、就诊记录 的隐私规则。
  策略为 mask。
---

## 何时使用
在小红书的在小红书帖子下方发布一条评论时，该技能被触发。

## 执行步骤
- [ ] 步骤1：打开小红书应用，进入目标帖子页面
- [ ] 步骤2：点击帖子下方的“评论”按钮
- [ ] 步骤3：在弹出的评论输入框中输入评论内容（确保不包含真实姓名、手机号、就诊记录等隐私信息）
- [ ] 步骤4：点击输入框右侧的“发送”按钮提交评论

## 边界情况
- [特殊情况1]：如果网络连接失败，提示用户检查网络并重新尝试
- [特殊情况2]：如果用户拒绝评论操作，直接返回帖子页面
- [特殊情况3]：如果评论内容包含敏感隐私信息，自动触发mask策略进行脱敏处理后提交