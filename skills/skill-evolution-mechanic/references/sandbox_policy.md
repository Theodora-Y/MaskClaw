# 沙盒验证设计方案
version: v0.1.0

---

## 定位

沙盒验证是 Evolution Mechanic 的 Step 5，
是新 Skill 写入 user_skills/ 之前的最后门卫。

类比软件工程的回归测试（evals/）：
新 Skill 发布前，必须保证历史上用户认可的操作
不会被新规则误拦。

要求：
"每次进化一个版本后，必须跑 evals/ 回归测试
才能合入主干——这是工业级生命线。"

---

## 文件位置

**输入1：新候选规则（内存传入，不落盘）**
Step 4 生成的 rule dict，包含：
scene / app_context_hint / sensitive_field / strategy /
replacement / rule_text / confidence

**输入2：历史 Allow 记录（测试用例库）**
```
memory/logs/{user_id}/behavior_log.jsonl
```
过滤条件：resolution == "allow"
这些是用户过去默认接受的操作，
新规则不能破坏它们。

实验/演示模式下：
从 P-GUI-Evo 数据集中
expected_feedback == "Allow" 的条目构造。

**输入3：本次 correction 来源场景（排除名单）**
```
memory/logs/{user_id}/correction_log.jsonl
```
本次触发 Evolution 的那批条目的 app_context。
这些场景本来就是要被新规则覆盖的，
它们的历史 Allow 记录不算冲突。

**验证通过后写入：**
```
user_skills/{user_id}/{skill_name}/
  SKILL.md
  rules.json          ← 同时写入 Chroma RAG
```

**验证失败后写入：**
```
memory/candidate_rules_rejected.jsonl
```

**confidence 不足（未进入沙盒）：**
```
memory/candidate_rules_pending.jsonl
```

---

## 进入沙盒的前提条件

以下所有条件必须同时满足：

- confidence >= 0.6（否则进 pending，不进沙盒）
- rule_text 非空
- strategy 只能是 block 或 replace
- strategy=replace 时 replacement 不能为空
- scene 非空且不是纯通用词（如"任何"单独出现需警惕）

不满足任一条件 → 写入 pending，不进入沙盒。

---

## 核心排除逻辑

在做冲突检查之前，先建立排除名单：
```python
# 本次触发 Evolution 的场景，不算冲突
correction_sources = set(
    entry["app_context"]
    for entry in current_correction_batch
)

# 历史 Allow 里，app_context 在排除名单的跳过
allow_records = [
    r for r in behavior_log_allow
    if r["app_context"] not in correction_sources
]
```

原因：correction_log 里的场景，是系统以前
没有规则所以放行的，现在要用新规则覆盖，
这些历史 Allow 不应该阻止新规则写入。

---

## 验证流程

### 第一轮：字段匹配检查
```
对排除名单过滤后的每条历史 Allow 记录：

Step A：field 匹配
  新规则的 sensitive_field
  是否与该记录的 field 相同？
  → 不同：跳过（无关字段）
  → 相同：进入 Step B

Step B：场景覆盖检查
  新规则的 app_context_hint 是否覆盖该记录的 app_context？
  → 不覆盖：通过
  → 覆盖：冲突，进入第二轮
```

### 场景覆盖判断规则（推荐）

| app_context_hint | 覆盖范围 |
|---|---|
| `all` | 覆盖所有 app |
| 具体 app 名（如 `wechat`） | 只覆盖该 app |
| `non_ecommerce` | 覆盖电商白名单以外的所有 app |
| `ecommerce` | 只覆盖电商白名单内的 app |
| `except:{app}` | 覆盖除指定 app 外的所有场景 |

**电商白名单：**
taobao / tmall / jd / pinduoduo / xianyu / kaola

### 第二轮：尝试缩窄规则

第一轮发现冲突时，先尝试缩窄，不直接拒绝：
```
冲突示例：
  新规则 app_context_hint：all
  冲突记录：taobao + fill_shipping_address

缩窄操作：
  把冲突的 app_context 从覆盖范围中排除
  app_context_hint 从 all 改为 non_ecommerce

重新走第一轮：
  → 不再冲突：使用缩窄版本继续
  → 仍然冲突：记录所有冲突原因，拒绝写入
```

缩窄最多执行一次，不做递归缩窄。
缩窄后在 rule_dict 里记录：
```json
{
  "scene_narrowed": true,
  "original_scene": "all",
  "narrowed_reason": "与taobao历史Allow记录冲突"
}
```

---

## 结果处理

### 通过

使用（可能已缩窄的）规则进入 Step 6，
写入 user_skills/{user_id}/{skill_name}/
同时将 rules.json 写入 Chroma RAG。

### 拒绝

写入 memory/candidate_rules_rejected.jsonl：
```json
{
  "rule_id": "user_B_20260318_001",
  "rule_text": "任何场景下禁止填写家庭住址",
  "status": "rejected",
  "rejected_ts": 1700000000,
  "conflict_reason": "缩窄后仍与历史Allow记录冲突",
  "conflict_details": [
    {
      "app_context": "taobao",
      "action": "fill_shipping_address",
      "field": "home_address"
    },
    {
      "app_context": "jd",
      "action": "fill_shipping_address",
      "field": "home_address"
    }
  ]
}
```

---

## 实验/演示模式

使用 P-GUI-Evo 数据集模拟时：

**Allow 记录来源：**
数据集中 expected_feedback == "Allow" 的条目
构造为模拟 Allow 记录。

**排除名单来源：**
数据集中 expected_feedback ≠ 模型实际输出
（触发本次 Evolution 的那批条目）的
app_context 构造排除名单。

--mock-input 参数时自动切换此模式。

---

## 当前版本局限性

v0.1.0 实现静态字段匹配，不做完整 Replay。

**Replay 方案（v0.2.0 目标）：**
```
新规则注入沙盒 Agent
  ↓
重新跑历史 Allow 记录
  ↓
对比结果是否变化
  ↓
有变化 = 冲突
```

---

## 与 evals/ 的关系
```
v0.1.0：沙盒字段匹配 = 轻量门卫
v0.2.0：沙盒 + evals/ Replay = 完整 CI/CD
```