---
name: dingtalk-video-meeting
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538726
user_id: demo_UserC
confidence: 0.8
needs_review: false
status: sandbox_passed
description: “Enforces privacy masking when initiating or joining DingTalk (钉钉) video meetings. Use when the user starts or joins a video conference in DingTalk — masks participant identities in logs, ensures virtual background is active before camera enablement, enforces recording restrictions, and prevents meeting links from leaking to unauthorized parties.”
---

## 何时使用

Use when the on-device agent detects the user initiating or joining a DingTalk video meeting (`app_context: dingtalk`). Triggers on: tapping “发起会议” or “加入会议” in DingTalk, clicking a DingTalk meeting link, or accepting a DingTalk meeting invitation.

**触发关键词**: 钉钉、钉钉会议、视频会议、发起会议、加入会议、DingTalk、钉钉视频、隐私设置、会议录制、屏幕共享

## 执行步骤

1. **会议元数据脱敏**: When the agent captures meeting metadata, apply masking before logging:
   - 参会人姓名: `张三` → `张*`
   - 参会人工号: `EMP20240101` → `EMP****0101`
   - 会议链接: `https://meeting.dingtalk.com/j/abc123` → `https://meeting.dingtalk.com/j/[已脱敏]`
   - 会议密码: `123456` → `******`
2. **背景隐私保护**: Before the camera is activated, verify that DingTalk's virtual background or background blur is enabled. If not, instruct the agent to enable it. Flag to user: “入会前确认背景，敏感内容不得出现在镜头前”.
3. **会议隐私设置检查**: Verify the following DingTalk privacy settings are configured:
   - “仅参会人员可见” (participants only) is enabled
   - “禁止录音录像” (recording disabled) is set unless the host explicitly allows it
   - “自动分享屏幕” (auto screen share) is disabled
   If any setting is misconfigured, alert the user with the specific setting to adjust.
4. **会议链接保护**: Monitor for any attempt to share the meeting link outside the invited participant group (e.g., copying to a public chat or external app). If detected, warn: “会议链接不应分享给非参会人员”.
5. **验证隐私状态**: Before finalizing the join/create action, confirm all privacy checks pass. Log the verification result with timestamp.

## 边界情况

- **大型会议/网络研讨会**: For DingTalk webinars or meetings with 50+ participants, participant identity masking still applies to agent logs but skip the virtual background enforcement prompt (impractical for large events).
- **用户拒绝隐私设置**: If the user declines to modify privacy settings, log the refusal with timestamp and reason but do not block meeting entry — provide a reminder: “建议手动调整隐私设置以保护个人信息”.
- **会议录制请求**: If the host enables recording during the meeting, notify the user immediately: “当前会议已开始录制” and log the recording activation event.