---
name: his-patient-record
version: v1.0.0
generated_by: skill-evolution-mechanic
generated_ts: 1774538623
user_id: demo_UserA
confidence: 0.85
needs_review: false
status: sandbox_passed
description: “Masks patient personally identifiable information when the agent interacts with hospital HIS systems. Use when entering, querying, or displaying patient medical records (患者病历) in a HIS system — applies field-level masking to names, IDs, diagnoses, and contact info before data is logged, displayed, or transmitted.”
---

## 何时使用

Use when the on-device agent accesses a hospital HIS (Hospital Information System) for patient record operations (`app_context: his`). Triggers on: querying patient records, entering new medical records, viewing patient details, or exporting/printing patient data.

**触发关键词**: HIS系统、病历管理、患者信息、病历查询、病历录入、患者隐私、脱敏、医疗数据保护、PHI、个人健康信息

## 执行步骤

1. **识别敏感字段**: When patient record data is accessed, identify all sensitive fields in the response:
   - 患者姓名 (patient name)
   - 身份证号 (national ID)
   - 住院号/患者ID (admission/patient ID)
   - 手机号 (phone number)
   - 家庭住址 (home address)
   - 诊断信息 (diagnosis)
   - 过敏史 (allergy history)
2. **应用脱敏规则**: Apply the `mask` strategy to each field before the agent logs or displays the data:
   - 患者姓名: `王小明` → `王**`
   - 身份证号: `110101199501011234` → `1101***********234`
   - 住院号: `ZY20240315001` → `ZY*****001`
   - 手机号: `13912345678` → `139****5678`
   - 家庭住址: `北京市海淀区中关村大街1号` → `北京市海淀区[已脱敏]`
   - 诊断信息: `2型糖尿病` → `[已脱敏]`
3. **验证脱敏完整性**: After masking, re-scan the output to ensure no raw PII remains. If the query returns multiple patient records (list view), apply masking to every record in the result set.
4. **审计日志记录**: Log each access event with: operator ID, timestamp, accessed patient record ID (masked), operation type (query/edit/export), and whether masking was applied. This creates a compliance-ready audit trail.

## 边界情况

- **批量查询结果**: When a query returns multiple patient records, apply masking consistently across all records — do not mask some and leave others exposed due to pagination or lazy loading.
- **紧急医疗场景**: If the user indicates an emergency access scenario (急诊), allow temporary unmasked access to critical fields (name, allergy history, blood type) but log the emergency override with reason and timestamp.
- **数据导出/打印**: When patient data is exported to PDF, printed, or copied to clipboard, apply masking to the exported output as well — the export path must not bypass on-screen masking rules.