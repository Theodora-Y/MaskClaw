# 规则结构定义
version: v0.1.0

---

## 定位

rules.json 是 Evolution Mechanic 的最终输出之一，
承担双重职责：

**职责1：作为生成的 Skill 的组成部分**
存放在 user_skills/{user_id}/{skill_name}/
供 AutoGLM 读取，知道这个 Skill 的具体规则内容。

**职责2：写入 Chroma RAG**
向量化后存入 Chroma collection: privacy_rules
供 MiniCPM 在 L2 检索时查询，做隐私判决。

同一份 rules.json，两处使用，内容完全一致。

---

## 存储位置

**Skill 目录内：**
```
user_skills/{user_id}/
  privacy-{field}-{strategy}-v{version}/
    rules.json
```

**Chroma RAG：**
```
memory/chroma_storage/
  collection: privacy_rules
  向量化字段：rule_text
  metadata：其余所有字段
```

**未通过沙盒的规则归档：**
```
memory/candidate_rules_pending.jsonl   ← confidence 不足
memory/candidate_rules_rejected.jsonl  ← 沙盒验证失败
```

---

## 字段定义
```json
{
  "rule_id": "user_B_20260318_001",
  "user_id": "user_B",
  "scene": "非电商平台注册",
  "app_context_hint": "non_ecommerce",
  "sensitive_field": "home_address",
  "strategy": "replace",
  "replacement": "公司地址",
  "rule_text": "在非电商平台注册时，用公司地址替代家庭住址",
  "confidence": 0.82,
  "trigger_count": 3,
  "needs_review": false,
  "status": "active",
  "created_ts": 1700000000,
  "version": "v0.1.0",
  "skill_path": "user_skills/user_B/privacy-home-address-replace-v1",
  "source_event_ids": ["user_B_001", "user_B_002", "user_B_003"],
  "scene_narrowed": false,
  "original_scene": null
}
```

---

## 字段说明

| 字段 | 类型 | 来源 | 说明 |
|---|---|---|---|
| `rule_id` | string | 脚本生成 | 格式：`{user_id}_{日期}_{3位序号}` |
| `user_id` | string | correction_log | 所属用户 |
| `scene` | string | MiniCPM 输出 | 规则生效的场景，尽量具体 |
| `app_context_hint` | string | MiniCPM/脚本 | 英文场景提示：`wechat`/`all`/`non_ecommerce`/`ecommerce`，用于沙盒覆盖判断 |
| `sensitive_field` | string | MiniCPM 输出 | 涉及的字段名 |
| `strategy` | string | MiniCPM 输出 | 只能是 `block` 或 `replace` |
| `replacement` | string \| null | MiniCPM 输出 | strategy=replace 时的替代值；block 时为 null |
| `rule_text` | string | MiniCPM 输出 | 自然语言规则描述，**这个字段被向量化存入 Chroma** |
| `confidence` | float | 脚本计算 | 0 到 1，由 confidence_policy.md 的公式计算，不由模型输出 |
| `trigger_count` | int | 脚本统计 | 触发本条规则抽取的有效纠错次数 |
| `needs_review` | bool | 脚本判断 | confidence 在 0.6~0.75 之间时为 true |
| `status` | string | 脚本写入 | `active` / `pending` / `rejected` / `deprecated` |
| `created_ts` | int | 系统时间 | Unix 时间戳，秒级 |
| `version` | string | 脚本写入 | 与所在 Skill 的版本号一致 |
| `skill_path` | string | 脚本生成 | 对应 Skill 目录的相对路径 |
| `source_event_ids` | list[string] | correction_log | 来源日志的 event_id 列表，用于溯源 |
| `scene_narrowed` | bool | 沙盒验证 | 沙盒验证时是否缩窄了 scene 条件 |
| `original_scene` | string \| null | 沙盒验证 | 缩窄前的原始 scene；未缩窄时为 null |

命名边界约束：
- 代码字段和值中用于匹配与文件命名的标识（如 `app_context_hint`、`sensitive_field`）使用英文。
- 面向用户展示的自然语言字段（如 `scene`、`rule_text`）可使用中文。

---

## strategy 的含义

**block：**
proxy_agent 直接拦截此类操作，不执行，提示用户。
```
场景：微信传输含病历的文件
strategy: block, replacement: null
→ Agent 尝试发送时，proxy 拦截，弹窗告知
```

**replace：**
proxy_agent 把 Agent 填入的值替换成 replacement 后执行。
```
场景：非电商平台注册填家庭住址
strategy: replace, replacement: 公司地址
→ Agent 填入家庭住址，proxy 自动替换为公司地址
```

---

## status 枚举

| 值 | 含义 | 存在位置 |
|---|---|---|
| `active` | 生效中 | user_skills/ + Chroma |
| `pending` | confidence 不足，继续观察 | candidate_rules_pending.jsonl |
| `rejected` | 沙盒验证失败 | candidate_rules_rejected.jsonl |
| `deprecated` | 有新版本替代，旧版本保留 | user_skills/（原目录保留） |

---

## 版本管理

同一用户同一字段同一策略出现更好的规则时：
- 旧版本 status 改为 `deprecated`，目录保留不删除
- 新版本写入新目录，version 递增：v1 → v2
- Chroma 中旧规则标记 deprecated，新规则写入
```
user_skills/user_B/
  privacy-home-address-replace-v1/  ← deprecated
    rules.json (status: deprecated)
  privacy-home-address-replace-v2/  ← active
    rules.json (status: active)
```

---

## rejected 规则的额外字段

写入 candidate_rules_rejected.jsonl 时
额外附加冲突原因：
```json
{
  "rule_id": "...",
  "rule_text": "任何场景下禁止填写家庭住址",
  "status": "rejected",
  "rejected_ts": 1700000000,
  "conflict_reason": "缩窄后仍与历史Allow记录冲突",
  "conflict_details": [
    {
      "app_context": "taobao",
      "action": "fill_shipping_address",
      "field": "home_address"
    }
  ]
}
```