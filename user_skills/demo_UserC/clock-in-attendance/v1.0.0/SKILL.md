---
name: clock-in-attendance
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538803
user_id: demo_UserC
confidence: 0.8
needs_review: false
status: sandbox_passed
description: >
  在 考勤系统 场景下，在企业考勤系统中完成上下班打卡 时保护 打卡位置 的隐私规则。
  策略为 mask。
---

## 何时使用
在考勤系统的在企业考勤系统中完成上下班打卡时，该技能被触发。

## 执行步骤
- [ ] 步骤1：打开考勤系统应用，点击“打卡”按钮进入打卡页面。
- [ ] 步骤2：选择当前打卡类型（上班或下班），确认打卡时间与地点信息，点击“确认打卡”提交。
- [ ] 步骤3：系统提示打卡成功后，返回主界面；若提示失败，根据错误信息重新操作或联系HR解决。

## 边界情况
- [特殊情况1]：网络连接失败时，提示用户检查网络并重试。
- [特殊情况2]：用户拒绝授权位置信息时，系统无法记录准确打卡位置，需手动输入或联系HR处理。