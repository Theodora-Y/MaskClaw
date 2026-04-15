---
name: send-work-email
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538604
user_id: demo_UserA
confidence: 0.85
needs_review: false
status: sandbox_passed
description: “Applies mask-based privacy protection to work emails sent via enterprise mailbox. Use when composing or sending work emails that may contain patient information (患者信息), internal contacts, or financial data — detects sensitive fields and replaces them with '[已脱敏]' before the email is dispatched.”
---

## 何时使用

Use when the on-device agent intercepts an outgoing work email via enterprise mailbox (企业邮箱) that may contain sensitive data. Triggers on actions: composing a new email, replying, or forwarding messages in the email app context (`app_context: email`).

**触发关键词**: 发送邮件、工作邮件、企业邮箱、患者信息、脱敏、数据保护、隐私保护、PHI、医疗信息

## 执行步骤

1. **扫描邮件内容**: Scan the email subject, body, and attachments for sensitive fields — patient names (患者姓名), patient IDs (患者ID/住院号), phone numbers (手机号), diagnosis information (诊断信息), internal directory entries (内部通讯录), and financial figures (财务数据).
2. **应用脱敏规则**: For each detected sensitive field, apply the `mask` strategy:
   - 患者姓名: `张三` → `张*`
   - 患者ID/住院号: `P20240315001` → `P*****001`
   - 手机号: `13812345678` → `138****5678`
   - 诊断信息: `高血压二期` → `[已脱敏]`
   - 财务金额: `¥52,000` → `¥**,***`
3. **验证脱敏结果**: Re-scan the processed email content to confirm no sensitive fields remain unmasked. If any are found, repeat step 2 for the missed fields.
4. **用户确认**: Present the masked version to the user for review before sending. If the user approves, proceed with dispatch; if the user requests changes, allow manual edits and re-validate.

## 边界情况

- **附件包含敏感信息**: If attachments (PDF, images, spreadsheets) contain patient data, flag the attachment to the user and recommend removing or redacting it before sending — attachment content scanning may be limited.
- **多个敏感字段重叠**: When a single text segment contains multiple sensitive field types (e.g., “患者张三，住院号P20240315001”), apply masking rules in order of specificity (ID → name → phone) to avoid partial masking artifacts.
- **用户拒绝脱敏**: If the user explicitly opts out of masking, log the decision with timestamp and reason to the audit trail, then allow the email to proceed — respect user autonomy while maintaining a record.