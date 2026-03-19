## references/log_schema.md

---

### 日志文件说明

两个日志文件，职责不同：

- `behavior_log.jsonl` — 所有操作的轻量记录，包含 pending 状态的条目
- `correction_log.jsonl` — 只有用户参与的完整记录（Evolution Mechanic 的原料）

每行一个 JSON 对象，文件本身是 JSONL 格式，支持并发追加。

---

### 字段定义

**所有条目都有的基础字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `event_id` | string | 唯一标识，格式 `{user_id}_{timestamp}_{4位随机数}`，用于 update 时定位 |
| `user_id` | string | 用户标识，对应 logs/ 下的目录名 |
| `ts` | int | Unix 时间戳，秒级 |
| `app_context` | string | 当前操作的 App 或场景，如 `wechat`、`hospital_his`、`taobao` |
| `action` | string | Agent 意图执行的操作，见 event_types.md |
| `field` | string \| null | 操作涉及的字段，如 `home_address`、`phone`、`file_content`，无字段时为 null |
| `resolution` | string | proxy 的决策结果，枚举值见 event_types.md |
| `level` | int | 1 = 轻量记录，2 = 完整记录 |
| `processed` | bool | Evolution Mechanic 是否已处理，默认 false |
| `expire_ts` | int | 过期时间戳，超过后可被清理任务删除 |

**仅级别2完整记录才有的字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `value_preview` | string \| null | 操作内容的脱敏预览，如 `"病历截图.jpg"`、`"1381234****"`，绝不存原始值 |
| `correction_type` | string \| null | 用户反馈的类型，枚举：`user_allowed` / `user_denied` / `user_modified` / `user_interrupted` / `pending` |
| `correction_value` | string \| null | 用户修正后的替代值，如 `"公司地址"`；未修正时为 null；待处理时为 null |
| `pii_types_involved` | list[string] | 本次操作涉及的 PII 类型，如 `["PHONE_NUMBER", "HOME_ADDRESS"]`，来自 L1 的识别结果 |

补充规范：
- `app_context` 统一使用英文小写标识，例如 `wechat`、`taobao`、`hospital_his`。
- 代码字段与文件系统命名保持英文；面向用户的文案可使用中文。

---

### 示例

**级别1轻量记录（Allow，立即写完整）：**
```json
{
  "event_id": "user_A_1700000001_3821",
  "user_id": "user_A",
  "ts": 1700000001,
  "app_context": "taobao",
  "action": "fill_shipping_address",
  "field": "home_address",
  "resolution": "allow",
  "level": 1,
  "processed": false,
  "expire_ts": 1700086401
}
```

**级别2完整记录（Interrupt，用户主动打断）：**
```json
{
  "event_id": "user_A_1700000042_1156",
  "user_id": "user_A",
  "ts": 1700000042,
  "app_context": "wechat",
  "action": "send_file",
  "field": "file_content",
  "resolution": "interrupt",
  "level": 2,
  "processed": false,
  "expire_ts": 1700086442,
  "value_preview": "病历截图.jpg",
  "correction_type": "user_interrupted",
  "correction_value": null,
  "pii_types_involved": ["MEDICAL_RECORD"]
}
```

**级别2，阶段一写入（Ask，pending 状态）：**
```json
{
  "event_id": "user_B_1700000099_4472",
  "user_id": "user_B",
  "ts": 1700000099,
  "app_context": "forms_registration",
  "action": "fill_home_address",
  "field": "home_address",
  "resolution": "ask",
  "level": 2,
  "processed": false,
  "expire_ts": 1700086499,
  "value_preview": "上海市徐汇区****",
  "correction_type": "pending",
  "correction_value": null,
  "pii_types_involved": ["HOME_ADDRESS"]
}
```

**同一条目，阶段二用户响应后更新：**
```json
{
  "event_id": "user_B_1700000099_4472",
  "user_id": "user_B",
  "ts": 1700000099,
  "app_context": "forms_registration",
  "action": "fill_home_address",
  "field": "home_address",
  "resolution": "ask",
  "level": 2,
  "processed": false,
  "expire_ts": 1700086499,
  "value_preview": "上海市徐汇区****",
  "correction_type": "user_modified",
  "correction_value": "公司地址",
  "pii_types_involved": ["HOME_ADDRESS"]
}
```

---

### 清理规则

- `level=1` 的条目：`expire_ts` 设为写入时间 + 24小时
- `level=2` 的条目：`expire_ts` 设为写入时间 + 7天（给用户足够时间处理 pending）
- `processed=true` 的条目：Evolution 处理完后立即可清理，不等 expire
- `correction_type="pending"` 且超过 `expire_ts` 的条目：视为用户放弃处理，直接删除，**不进入** Evolution
