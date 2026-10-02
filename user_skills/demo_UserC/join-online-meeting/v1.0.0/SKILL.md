---
name: join-online-meeting
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538796
user_id: demo_UserC
confidence: 0.8
needs_review: false
status: sandbox_passed
description: “Protects meeting host identity and home environment privacy when joining online video meetings via link. Use when the user clicks a meeting link to join a video conference (Zoom, Teams, Google Meet, 腾讯会议) — masks host identity in logs, enforces virtual background before camera activation, and prevents accidental screen sharing of private content.”
---

## 何时使用

Use when the on-device agent detects the user joining a video meeting via link or invitation (`app_context: meeting`). Triggers on: clicking a meeting URL, opening a meeting app invite, or joining a scheduled conference call.

**触发关键词**: 视频会议、在线会议、会议链接、加入会议、Zoom、Teams、Google Meet、腾讯会议、隐私保护、背景模糊、虚拟背景

## 执行步骤

1. **验证会议来源**: Before the agent proceeds with joining, verify the meeting link domain matches a known conferencing provider (e.g., `zoom.us`, `teams.microsoft.com`, `meet.google.com`, `meeting.tencent.com`). If the domain is unrecognized, warn the user: “会议链接来源未知，请确认后再加入”.
2. **脱敏主持人身份**: When the meeting metadata is captured (host name, email, organization), apply masking before logging:
   - 主持人姓名: `李明` → `李*`
   - 主持人邮箱: `liming@company.com` → `l****@company.com`
   - 会议ID: `123-456-789` → `***-***-789`
3. **强制背景保护**: Before the camera is activated, check whether a virtual background or blur effect is enabled. If not, instruct the agent to enable background blur or a virtual background to protect the home environment. Flag to user: “已自动启用背景模糊以保护家庭环境隐私”.
4. **屏幕共享审查**: Before allowing screen sharing, scan the active screen for sensitive content (open chat windows, financial apps, medical records). If detected, warn the user: “当前屏幕包含敏感内容，建议切换到演示窗口后再共享”.
5. **验证隐私设置**: Confirm all privacy measures are active (background masked, microphone muted, screen sharing restricted) before finalizing the join action. Log the privacy check result.

## 边界情况

- **多平台会议切换**: If the user switches between meeting platforms mid-session (e.g., Zoom to Teams), re-run the full privacy check sequence for the new platform — settings do not carry over.
- **主持人身份已公开**: If the meeting is a public webinar where the host identity is intentionally visible, skip host identity masking but still enforce background and screen sharing protections.
- **用户主动关闭隐私保护**: If the user disables virtual background or unmutes intentionally, log the decision but do not block — respect user autonomy while recording the choice in the audit trail.