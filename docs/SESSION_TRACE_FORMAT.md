# Session Trace JSONL 日志格式规范

## 版本: v2.0

### 设计原则
1. **行为链归一化**：使用 `_scenario_tag` 作为 Session 的唯一识别标志
2. **单文件内聚**：actions 作为数组嵌套在主记录中
3. **元数据瘦身**：剔除数据库索引元数据，保留业务语义核心字段

---

## 格式结构

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `chain_id` | string | ✅ | 行为链唯一标识，格式: `{user_id}_{scenario_tag}_{ts}` |
| `user_id` | string | ✅ | 用户标识 |
| `app_context` | string | ✅ | 应用上下文 (如: 钉钉, 微信, 医院OA) |
| `scenario_tag` | string | ✅ | 场景标签，作为链的唯一识别标志 |
| `rule_type` | string | ✅ | 规则类型: H(高隐私), S(敏感), N(普通) |
| `start_ts` | int | ✅ | 行为链开始时间戳 |
| `end_ts` | int | ✅ | 行为链结束时间戳 |
| `action_count` | int | ✅ | 动作总数 |
| `has_correction` | bool | ✅ | 是否包含用户纠错 |
| `correction_count` | int | ✅ | 纠错动作数量 |
| `final_resolution` | string | ✅ | 最终决策结果: allow/block/mask/ask |
| `processed` | bool | ✅ | 是否已被进化引擎处理 |

### actions 数组

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `action_index` | int | ✅ | 动作序号 (0-based) |
| `ts` | int | ✅ | 动作时间戳 |
| `action` | string | ✅ | 动作类型: fill_form, share_or_send, view_record, edit_record 等 |
| `field` | string | ❌ | 字段名: phone_number, medical_record, home_address 等 |
| `resolution` | string | ✅ | 决策结果: allow/block/mask/ask/interrupt/correction |
| `value_preview` | string | ❌ | 脱敏后的值预览 |
| `is_correction` | bool | ✅ | 是否为用户纠错动作 |
| `correction_type` | string | ❌ | 纠错类型: user_denied/user_modified/user_interrupted |
| `correction_value` | string | ❌ | 用户修正后的替代值 |
| `pii_type` | string | ❌ | PII类型: PHONE_NUMBER, MedicalRecord, IDCard 等 |
| `relationship_tag` | string | ❌ | 关系标签: 患者本人, 同科室同事, 陌生人 等 |
| `agent_intent` | string | ❌ | Agent 意图描述 |
| `quality_score` | float | ❌ | 质量评分 (0-5) |
| `quality_flag` | string | ❌ | 质量标志: pass/review/fail |

---

## 示例

```json
{
  "chain_id": "d1_UserA_钉钉发送病历截图给同事_1773564069",
  "user_id": "d1_UserA",
  "app_context": "钉钉",
  "scenario_tag": "钉钉发送病历截图给同事",
  "rule_type": "H",
  "start_ts": 1773564069,
  "end_ts": 1773567270,
  "action_count": 3,
  "has_correction": true,
  "correction_count": 2,
  "final_resolution": "block",
  "processed": false,
  "actions": [
    {
      "action_index": 0,
      "ts": 1773564069,
      "action": "share_or_send",
      "field": "medical_record",
      "resolution": "block",
      "value_preview": "UserA_screenshot.png",
      "is_correction": false,
      "pii_type": "MedicalRecord",
      "relationship_tag": "同科室同事",
      "agent_intent": "发送病历截图到钉钉对话",
      "quality_score": 3.6,
      "quality_flag": "pass"
    },
    {
      "action_index": 1,
      "ts": 1773565884,
      "action": "share_or_send",
      "field": "medical_record",
      "resolution": "block",
      "value_preview": "UserA_screenshot.png",
      "is_correction": false,
      "pii_type": "MedicalRecord",
      "relationship_tag": "同科室同事",
      "agent_intent": "新版钉钉UI结构调整后发送病历截图",
      "quality_score": 3.6,
      "quality_flag": "pass"
    },
    {
      "action_index": 2,
      "ts": 1773567270,
      "action": "share_or_send",
      "field": "medical_record",
      "resolution": "correction",
      "value_preview": "UserA_screenshot.png",
      "is_correction": true,
      "correction_type": "user_denied",
      "correction_value": null,
      "pii_type": "MedicalRecord",
      "relationship_tag": "同科室同事",
      "agent_intent": "发送病历截图到钉钉对话",
      "quality_score": 3.6,
      "quality_flag": "pass"
    }
  ]
}
```

---

## 迁移说明

### 旧格式字段映射

| 旧字段 | 新字段/处理 |
|--------|-------------|
| `_source_entry_id` | 废弃 |
| `_source_candidate_id` | 废弃 |
| `_parent_entry_id` | 用于聚类，不保留 |
| `_bucket` | 废弃 |
| `_rule_type` | 保留 |
| `_gold_rule_summary` | 废弃 (语义已通过 agent_intent 表达) |
| `_pii_type` | 保留 |
| `_relationship_tag` | 保留 |
| `_app_platform` | 转换为 app_context |
| `_scenario_tag` | 保留，作为链标识 |
| `_agent_intent` | 保留 |
| `_quality_score` | 保留 |
| `_quality_flag` | 保留 |
| `_shift_type` | 废弃 |
| `level` | 废弃，改为 `has_correction` |
| `event_id` | 废弃，改为 `chain_id` + `action_index` |

---

## 文件命名

- 旧格式: `{user_id}/behavior_log.jsonl`, `{user_id}/correction_log.jsonl`
- 新格式: `{user_id}/session_trace.jsonl`
