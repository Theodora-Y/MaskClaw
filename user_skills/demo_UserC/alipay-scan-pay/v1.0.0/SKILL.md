---
name: alipay-scan-pay
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538708
user_id: demo_UserC
confidence: 0.8
needs_review: false
status: sandbox_passed
description: “Masks payment amount and merchant identity when the agent processes Alipay QR-code scan payments. Use when the user scans a merchant payment QR code (商家收款码) via Alipay — intercepts transaction data and replaces sensitive fields (支付金额, 商家信息) with '[已脱敏]' before logging or displaying.”
---

## 何时使用

Use when the on-device agent detects an Alipay scan-to-pay transaction (`app_context: alipay`). Triggers when the user scans a merchant QR code, initiates payment, or when the agent logs/displays transaction records.

**触发关键词**: 支付宝、扫码支付、扫一扫、付款、收款码、付款码、QR支付、支付记录、商家付款

## 执行步骤

1. **拦截交易数据**: When the agent captures or logs Alipay payment activity, extract the following sensitive fields from the transaction context: payment amount (支付金额), merchant name (商家名称), merchant ID, and payment method (支付方式).
2. **应用脱敏规则**: Apply the `mask` strategy to each sensitive field before logging or displaying:
   - 支付金额: `¥128.50` → `¥***.** `
   - 商家名称: `星巴克咖啡(望京店)` → `[已脱敏]`
   - 银行卡号: `6222 **** **** 1234` → `6222 **** **** ****`
   - 交易订单号: `2024031512345678` → `20240315****5678`
3. **截图脱敏**: If the agent takes a payment screenshot as a receipt, apply overlay masking to the amount and merchant fields in the captured image before saving. Flag to the user: “支付记录截图已脱敏”.
4. **验证脱敏完整性**: Re-scan the output (log entry, displayed text, or saved screenshot) to confirm no raw payment amount or merchant identity is exposed. If any leak is detected, re-apply masking before output.

## 边界情况

- **多笔连续支付**: When the user makes multiple consecutive payments, apply masking to each transaction independently — do not batch or skip masking for subsequent payments.
- **支付失败后重试**: If a payment fails and is retried, mask the transaction data for both the failed and successful attempts to prevent the failed attempt from leaking unmasked data in error logs.
- **用户需要查看原始金额**: If the user explicitly requests to see the unmasked amount (e.g., for expense reporting), prompt for confirmation, display temporarily, and log the access decision to the audit trail.